"""MATU-51 · «Compré» y «Me quedan N» por la API, contra PostgreSQL (RF-10, RF-11, decisiones 136 a 146).

Corren como matu_app con cuentas de las fábricas. El reloj es el de entorno_iam: 20-10-2026 09:00 en
Santiago. El perfil por omisión de la fábrica (24 unidades a 4 por día, anotado el 20-10) se acaba el
26-10: le quedan 6 días y avisa con 7, así que está en su ventana. Cada prueba lleva la condición del
analista que verifica. Solo datos sintéticos.
"""

import logging
import threading
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
import pytest

from app.core.db import fabrica_sesiones, sesion_tenant
from app.modules.care_circle.application.retiro import SolicitudRetiro, retirar_autorizacion
from app.modules.care_circle.infrastructure.efectos_retiro import efectos_de
from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL
from app.modules.consumption.application.conservacion import conservar, conservar_quiebres
from app.modules.consumption.infrastructure.tarea_conservacion import ConservacionConsumoSql
from app.modules.consumption.infrastructure.tarea_quiebres import ConservacionQuiebresSql
from app.shared.auditoria_sql import RegistroAuditoriaSql
from tests.base_datos import DSN, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.consumption.conftest import EntornoConsumo
from tests.modules.consumption.test_alertas_api import _aparece_como_dato

pytestmark = [requiere_base, pytest.mark.rf("RF-11")]

V1 = '"v1"'
HOY = "2026-10-20"
COMPRE = "/{}/reponer"
QUEDAN = "/{}/recontar"


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _alerta(perfil: uuid.UUID, estado: str = "pendiente", fecha: str = "2026-10-26") -> uuid.UUID:
    with psycopg.connect(DSN, autocommit=True) as cx:
        cerrada = "now()" if estado in ("resuelta", "descartada") else "NULL"
        fila = cx.execute(
            "INSERT INTO alerta_quiebre (perfil_id, fecha_prevista, estado, cerrada_en)"
            f" VALUES (%s, %s, %s, {cerrada}) RETURNING id",
            (perfil, fecha, estado),
        ).fetchone()
    assert fila is not None
    return uuid.UUID(str(fila[0]))


def _alertas(perfil: uuid.UUID) -> list[tuple[Any, ...]]:
    return _filas("SELECT id, fecha_prevista::text, estado FROM alerta_quiebre WHERE perfil_id = %s ORDER BY 2", perfil)


def _reposiciones(perfil: uuid.UUID) -> list[tuple[Any, ...]]:
    return _filas(
        "SELECT id, cantidad_unidades, origen, registrada_por, ocurrida_en::text FROM reposicion WHERE perfil_id = %s",
        perfil,
    )


def _auditoria(grupo: uuid.UUID) -> list[tuple[Any, ...]]:
    return _filas(
        "SELECT accion, entidad, entidad_id, actor_tipo, actor_ref, request_id IS NOT NULL, detalle"
        " FROM auditoria WHERE grupo_id = %s ORDER BY id",
        grupo,
    )


def _compre(e: EntornoConsumo, usuario: UsuarioCreado, familia: FamiliaCreada, perfil: Any, cuerpo: Any,
            **cabeceras: str) -> Any:
    extra: dict[str, Any] = {"If_Match": V1, **cabeceras}
    return e.pedir("POST", usuario, familia, COMPRE.format(perfil), json=cuerpo, **extra)


def _quedan(e: EntornoConsumo, usuario: UsuarioCreado, familia: FamiliaCreada, perfil: Any, cuerpo: Any,
            **cabeceras: str) -> Any:
    extra: dict[str, Any] = {"If_Match": V1, **cabeceras}
    return e.pedir("POST", usuario, familia, QUEDAN.format(perfil), json=cuerpo, **extra)


def _cuidadora(familia: FamiliaCreada) -> UsuarioCreado:
    return familia.miembros["cuidador"].usuario


def _sin_cambios(perfil: uuid.UUID) -> None:
    assert _filas("SELECT stock_unidades, version FROM perfil_consumo WHERE id = %s", perfil) == [(24, 1)]
    assert _reposiciones(perfil) == []


# --- «Compré»: camino feliz (condiciones 2, 3, 8, 9 y 11) ----------------------------------------------------


def test_compre_en_cantidad_sin_alerta_suma_anota_y_no_crea_alerta(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    # Anotado hace 4 días (16-10): quedan 24 - 16 = 8; + 40 = 48, alcanza 12 días: 01-11, fuera de la ventana
    perfil = e.fabrica.perfil_consumo(familia.persona, stock_medido_en=date(2026, 10, 16))
    cuidadora = _cuidadora(familia)

    respuesta = _compre(e, cuidadora, familia, perfil, {"cantidad": 40})

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["stock_unidades"], cuerpo["stock_medido_en"], cuerpo["fecha_quiebre_estimada"]) == (
        48, HOY, "2026-11-01")
    assert (cuerpo["dias_restantes"], cuerpo["avisando"], cuerpo["alerta_id"]) == (12, False, None)
    assert cuerpo["etag"] == '"v2"' and respuesta.headers["ETag"] == '"v2"'
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert cuerpo["actualizado_por"]["id"] == str(cuidadora.id)
    # Condición 3: ocurrida_en es hoy en Chile según el Reloj, no la fecha de la base
    [(rep_id, cantidad, origen, autor, ocurrida)] = _reposiciones(perfil)
    assert (cantidad, origen, autor, ocurrida) == (40, "declarada", cuidadora.id, HOY)
    # Condición 9: sin alerta y fuera de la ventana, no se crea ninguna fila en alerta_quiebre
    assert _alertas(perfil) == []
    assert _auditoria(familia.grupo.id) == [
        ("reposicion.declarar", "reposicion", rep_id, "usuario", cuidadora.id, True, None)]


def test_compre_en_envases_multiplica_por_las_unidades_del_envase(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, unidades_por_envase=30)
    respuesta = _compre(e, familia.admin, familia, perfil, {"envases": 2})
    assert respuesta.status_code == 200, respuesta.text
    # 24 + 60 = 84, a 4 por día alcanza 21 días: 10-11
    assert (respuesta.json()["stock_unidades"], respuesta.json()["fecha_quiebre_estimada"]) == (84, "2026-11-10")
    assert [r[1] for r in _reposiciones(perfil)] == [60]


def test_compre_en_envases_puede_pasar_de_10000(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    # 3 bidones de 5.000 ml a 1.000 ml por día: 15.000 + 24, alcanza 15 días
    perfil = e.fabrica.perfil_consumo(familia.persona, unidad="ml", tasa_unidades=1000, unidades_por_envase=5000)
    respuesta = _compre(e, familia.admin, familia, perfil, {"envases": 3})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["stock_unidades"] == 15_024
    assert [r[1] for r in _reposiciones(perfil)] == [15_000]


@pytest.mark.rf("RF-12")
def test_compre_resuelve_la_alerta_abierta_de_la_fecha(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    abierta = _alerta(perfil, "notificada")
    respuesta = _compre(e, familia.admin, familia, perfil, {"cantidad": 30})
    assert respuesta.status_code == 200, respuesta.text
    assert _alertas(perfil) == [(abierta, "2026-10-26", "resuelta")]
    acciones = [(f[0], f[2]) for f in _auditoria(familia.grupo.id)]
    [rep_id] = [r[0] for r in _reposiciones(perfil)]
    assert acciones == [("reposicion.declarar", rep_id), ("alerta.resolver", abierta)]
    # Ya no está en «Se acaban pronto» ni en la lista
    assert e.pedir("GET", familia.admin, familia, "/por-acabarse").json()["items"] == []
    assert e.pedir("GET", familia.admin, familia, "/lista").json()["items"] == []


@pytest.mark.rf("RF-12")
@pytest.mark.parametrize("estado", ["descartada", "resuelta"])
def test_compre_con_la_alerta_de_la_fecha_ya_cerrada_funciona_sin_409(
    entorno_consumo: EntornoConsumo, estado: str
) -> None:
    # Condición 10: por ejemplo después de «No avisar esta vez»
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    cerrada = _alerta(perfil, estado)
    respuesta = _compre(e, familia.admin, familia, perfil, {"cantidad": 30})
    assert respuesta.status_code == 200, respuesta.text
    assert _alertas(perfil) == [(cerrada, "2026-10-26", estado)]
    assert [f[0] for f in _auditoria(familia.grupo.id)] == ["reposicion.declarar"]


@pytest.mark.rf("RF-12")
def test_compre_en_la_ventana_y_sin_alerta_no_crea_alerta(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    # + 4 = 28, alcanza 7 días: sigue en la ventana de 7, avisando para la fecha nueva
    respuesta = _compre(e, familia.admin, familia, perfil, {"cantidad": 4})
    assert respuesta.status_code == 200, respuesta.text
    assert (respuesta.json()["avisando"], respuesta.json()["alerta_id"]) == (True, None)
    assert _alertas(perfil) == []


@pytest.mark.rf("RF-12")
def test_compre_descarta_las_alertas_de_otra_fecha_que_dejan_de_corresponder(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    de_la_fecha, vieja = _alerta(perfil), _alerta(perfil, fecha="2026-10-24")
    assert _compre(e, familia.admin, familia, perfil, {"cantidad": 40}).status_code == 200
    assert {a[0]: a[2] for a in _alertas(perfil)} == {de_la_fecha: "resuelta", vieja: "descartada"}
    acciones = {(f[0], f[2]) for f in _auditoria(familia.grupo.id)}
    assert {("alerta.resolver", de_la_fecha), ("alerta.descartar", vieja)} <= acciones


def test_compre_no_publica_eventos_ni_crea_pedidos(entorno_consumo: EntornoConsumo) -> None:
    # Condición 12 y decisión C: nada de capa 3
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    _alerta(perfil)
    assert _compre(e, familia.admin, familia, perfil, {"cantidad": 30}).status_code == 200
    assert _filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id) == []
    assert _filas("SELECT count(*) FROM pedido WHERE grupo_id = %s", familia.grupo.id) == [(0,)]


# --- «Compré»: caminos de error ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cuerpo", "campo", "tipo"),
    [
        ({"envases": 1, "cantidad": 1}, "cantidad", "envases_o_cantidad"),
        ({}, "cantidad", "envases_o_cantidad"),
        ({"envases": None, "cantidad": None}, "cantidad", "envases_o_cantidad"),
        ({"envases": 100}, "envases", None),
        ({"envases": 0}, "envases", None),
        ({"cantidad": 10_001}, "cantidad", None),
        ({"cantidad": 0}, "cantidad", None),
        ({"cantidad": 5, "ocurrida_en": "2026-10-01"}, "ocurrida_en", None),
        ({"cantidad": 5, "stock_unidades": 3}, "stock_unidades", None),
    ],
)
def test_compre_cuerpo_invalido_es_422_sin_tocar_nada(
    entorno_consumo: EntornoConsumo, cuerpo: dict[str, Any], campo: str, tipo: str | None
) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, unidades_por_envase=10)
    respuesta = _compre(e, familia.admin, familia, perfil, cuerpo)
    assert respuesta.status_code == 422, respuesta.text
    [error] = respuesta.json()["errores"]
    assert error["campo"] == campo and (tipo is None or error["tipo"] == tipo)
    assert respuesta.headers["Cache-Control"] == "no-store"
    _sin_cambios(perfil)


def test_compre_sin_cuerpo_es_422_y_la_cantidad_no_viaja_en_la_consulta(entorno_consumo: EntornoConsumo) -> None:
    # Condición 11: ?cantidad= no se lee; sin cuerpo es 422
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    respuesta = e.pedir("POST", familia.admin, familia, COMPRE.format(perfil), params={"cantidad": 5}, If_Match=V1)
    assert respuesta.status_code == 422
    _sin_cambios(perfil)


@pytest.mark.parametrize(
    ("opciones", "cuerpo", "campo", "tipo"),
    [
        ({}, {"envases": 1}, "envases", "sin_unidades_por_envase"),
        ({"stock_unidades": 95_000, "tasa_unidades": 10_000, "unidades_por_envase": 5000}, {"envases": 2},
         "envases", "stock_maximo"),
        ({"stock_unidades": 99_000, "tasa_unidades": 10_000}, {"cantidad": 5000}, "cantidad", "stock_maximo"),
        ({"stock_unidades": 10, "tasa_unidades": 1, "tasa_dias": 90}, {"cantidad": 10_000}, "cantidad",
         "cobertura_maxima"),
    ],
)
def test_compre_que_no_cabe_es_422_sin_tocar_nada(
    entorno_consumo: EntornoConsumo, opciones: dict[str, Any], cuerpo: dict[str, Any], campo: str, tipo: str
) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, **opciones)
    antes = _filas("SELECT stock_unidades, version FROM perfil_consumo WHERE id = %s", perfil)
    respuesta = _compre(e, familia.admin, familia, perfil, cuerpo)
    assert respuesta.status_code == 422, respuesta.text
    [error] = respuesta.json()["errores"]
    assert (error["campo"], error["tipo"]) == (campo, tipo)
    assert _filas("SELECT stock_unidades, version FROM perfil_consumo WHERE id = %s", perfil) == antes
    assert _reposiciones(perfil) == []


@pytest.mark.parametrize("valor", [None, "", "*"])
def test_compre_sin_if_match_es_428(entorno_consumo: EntornoConsumo, valor: str | None) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    extra: dict[str, Any] = {} if valor is None else {"If-Match": valor}
    respuesta = e.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/consumo/{perfil}/reponer",
        json={"cantidad": 5},
        headers=e.cabeceras(familia.admin, familia.grupo.id, **extra),
    )
    assert respuesta.status_code == 428 and respuesta.json()["type"] == "/errores/falta-version"
    _sin_cambios(perfil)


def test_dos_compre_con_el_mismo_etag_suman_una_sola_vez(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    abierta = _alerta(perfil)
    assert _compre(e, familia.admin, familia, perfil, {"cantidad": 5}).status_code == 200
    segundo = _compre(e, familia.admin, familia, perfil, {"cantidad": 5})
    assert segundo.status_code == 412
    assert segundo.json()["type"] == "/errores/version-desactualizada"
    assert segundo.json()["actual"]["etag"] == '"v2"' and segundo.headers["ETag"] == '"v2"'
    assert segundo.headers["Cache-Control"] == "no-store"
    assert len(_reposiciones(perfil)) == 1
    assert _filas("SELECT stock_unidades, version FROM perfil_consumo WHERE id = %s", perfil) == [(29, 2)]
    assert _alertas(perfil) == [(abierta, "2026-10-26", "resuelta")]


@pytest.mark.parametrize("ruta", ["compre", "quedan"])
def test_compre_y_me_quedan_en_un_insumo_sin_seguir_es_409(entorno_consumo: EntornoConsumo, ruta: str) -> None:
    # Decisión A3 de Jorge: un insumo «Sin seguir» no se repone ni se cuenta; el problema perfil-inactivo ya existe
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, activo=False)
    if ruta == "compre":
        respuesta = _compre(e, familia.admin, familia, perfil, {"cantidad": 5})
    else:
        respuesta = _quedan(e, familia.admin, familia, perfil, {"stock_unidades": 3})
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/perfil-inactivo"
    _sin_cambios(perfil)


# --- «Ya lo resolví» acepta lo mismo que «Compré» (decisión A2 de Jorge, 147) -------------------------------------


@pytest.mark.rf("RF-12")
def test_resolver_en_envases_suma_y_resuelve(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, unidades_por_envase=30)
    abierta = _alerta(perfil)
    respuesta = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", json={"envases": 2}, If_Match=V1)
    assert respuesta.status_code == 200, respuesta.text
    assert (respuesta.json()["stock_unidades"], respuesta.json()["etag"]) == (84, '"v2"')
    assert [r[1:3] for r in _reposiciones(perfil)] == [(60, "declarada")]
    assert _alertas(perfil) == [(abierta, "2026-10-26", "resuelta")]


@pytest.mark.rf("RF-12")
def test_resolver_con_99_envases_de_200_ml_acepta_19800(entorno_consumo: EntornoConsumo) -> None:
    # Punto A6 del diseñador: lo que «Compré» acepta, «Ya lo resolví» también, aunque pase de 10.000
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, unidad="ml", tasa_unidades=200, unidades_por_envase=200)
    respuesta = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", json={"envases": 99}, If_Match=V1)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["stock_unidades"] == 19_824
    assert [r[1] for r in _reposiciones(perfil)] == [19_800]


@pytest.mark.rf("RF-12")
def test_resolver_con_cantidad_sigue_igual(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, unidades_por_envase=30)
    respuesta = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", json={"cantidad": 6}, If_Match=V1)
    assert respuesta.status_code == 200, respuesta.text
    assert [r[1] for r in _reposiciones(perfil)] == [6]


@pytest.mark.rf("RF-12")
@pytest.mark.parametrize(
    ("envase", "cuerpo", "campo", "tipo"),
    [
        (30, {"envases": 1, "cantidad": 1}, "cantidad", "envases_o_cantidad"),
        (None, {"envases": 1}, "envases", "sin_unidades_por_envase"),
        (30, {"envases": 100}, "envases", None),
        (5000, {"envases": 99}, "envases", "stock_maximo"),
    ],
)
def test_resolver_en_envases_invalido_es_422_sin_tocar_nada(
    entorno_consumo: EntornoConsumo, envase: int | None, cuerpo: dict[str, Any], campo: str, tipo: str | None
) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, unidades_por_envase=envase)
    respuesta = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", json=cuerpo, If_Match=V1)
    assert respuesta.status_code == 422, respuesta.text
    [error] = respuesta.json()["errores"]
    assert error["campo"] == campo and (tipo is None or error["tipo"] == tipo)
    _sin_cambios(perfil)
    assert _alertas(perfil) == []


# --- Quién (condición 5, decisión B) ----------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("rol", ["pagador", "observador"])
@pytest.mark.parametrize("ruta", ["compre", "quedan"])
def test_pagador_y_observador_404(entorno_consumo: EntornoConsumo, rol: str, ruta: str) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    usuario = familia.miembros[rol].usuario
    if ruta == "compre":
        respuesta = _compre(e, usuario, familia, perfil, {"cantidad": 5})
    else:
        respuesta = _quedan(e, usuario, familia, perfil, {"stock_unidades": 3})
    assert respuesta.status_code == 404
    _sin_cambios(perfil)


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("ruta", ["compre", "quedan"])
def test_otro_grupo_y_perfil_ajeno_404(entorno_consumo: EntornoConsumo, ruta: str) -> None:
    e = entorno_consumo
    a, b = e.familia(), e.familia()
    perfil_b = e.fabrica.perfil_consumo(b.persona)
    otro = e.fabrica.perfil_consumo(a.persona)

    def pedir(familia: FamiliaCreada, perfil: Any, persona: Any = None) -> Any:
        sufijo = (COMPRE if ruta == "compre" else QUEDAN).format(perfil)
        cuerpo = {"cantidad": 5} if ruta == "compre" else {"stock_unidades": 3}
        return e.pedir("POST", familia.admin, familia, sufijo, persona=persona, json=cuerpo, If_Match=V1)

    # La persona de otro grupo, el perfil de otro grupo bajo mi persona y un id que no es UUID
    assert pedir(a, perfil_b, persona=b.persona.id).status_code == 404
    assert pedir(a, perfil_b).status_code == 404
    assert pedir(a, "no-es-uuid").status_code == 404
    _sin_cambios(perfil_b)
    assert _filas("SELECT version FROM perfil_consumo WHERE id = %s", otro) == [(1,)]


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("ruta", ["compre", "quedan"])
def test_autorizacion_retirada_es_403_sin_consentimiento(entorno_consumo: EntornoConsumo, ruta: str) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    e.fabrica.autorizacion_consumo(
        familia.persona, otorgante=familia.admin, otorgado_en=e.iam.reloj.ahora() - timedelta(days=10),
        revocado_en=e.iam.reloj.ahora() - timedelta(days=1),
    )
    perfil = e.fabrica.perfil_consumo(familia.persona)
    if ruta == "compre":
        respuesta = _compre(e, familia.admin, familia, perfil, {"cantidad": 5})
    else:
        respuesta = _quedan(e, familia.admin, familia, perfil, {"stock_unidades": 3})
    assert respuesta.status_code == 403
    assert (respuesta.json()["type"], respuesta.json()["finalidad"]) == ("/errores/sin-consentimiento", "consumo")
    _sin_cambios(perfil)


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("ruta", ["compre", "quedan"])
def test_revision_vencida_es_403(entorno_consumo: EntornoConsumo, ruta: str) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    e.fabrica.autorizacion_consumo(
        familia.persona, otorgante=familia.admin, calidad="cuidador_de_hecho",
        otorgado_en=e.iam.reloj.ahora() - timedelta(days=366),
    )
    perfil = e.fabrica.perfil_consumo(familia.persona)
    if ruta == "compre":
        respuesta = _compre(e, _cuidadora(familia), familia, perfil, {"cantidad": 5})
    else:
        respuesta = _quedan(e, _cuidadora(familia), familia, perfil, {"stock_unidades": 3})
    assert respuesta.status_code == 403
    assert (respuesta.json()["type"], respuesta.json()["finalidad"]) == ("/errores/revision-vencida", "consumo")
    _sin_cambios(perfil)


# --- «Me quedan N» (condiciones 1, 8 y 9) -------------------------------------------------------------------------


def test_me_quedan_reemplaza_el_stock_sin_anotar_una_compra(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, stock_medido_en=date(2026, 10, 16))
    cuidadora = _cuidadora(familia)
    respuesta = _quedan(e, cuidadora, familia, perfil, {"stock_unidades": 40})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["stock_unidades"], cuerpo["stock_medido_en"], cuerpo["fecha_quiebre_estimada"]) == (
        40, HOY, "2026-10-30")
    assert (cuerpo["avisando"], cuerpo["alerta_id"], cuerpo["etag"]) == (False, None, '"v2"')
    assert respuesta.headers["ETag"] == '"v2"' and respuesta.headers["Cache-Control"] == "no-store"
    assert _reposiciones(perfil) == []
    assert _alertas(perfil) == []
    assert _auditoria(familia.grupo.id) == [
        ("consumo.editar", "perfil_consumo", perfil, "usuario", cuidadora.id, True, None)]


@pytest.mark.rf("RF-12")
def test_me_quedan_descarta_las_alertas_que_dejan_de_corresponder(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    abierta = _alerta(perfil)
    # 200 alcanzan 50 días: sale de la ventana
    assert _quedan(e, familia.admin, familia, perfil, {"stock_unidades": 200}).status_code == 200
    assert _alertas(perfil) == [(abierta, "2026-10-26", "descartada")]
    assert [(f[0], f[2]) for f in _auditoria(familia.grupo.id)] == [
        ("consumo.editar", perfil), ("alerta.descartar", abierta)]


@pytest.mark.rf("RF-12")
def test_me_quedan_con_la_misma_fecha_deja_la_alerta_abierta(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    abierta = _alerta(perfil)
    # 25 a 4 por día sigue en el 26-10 (piso de 6,25): la alerta corresponde y sigue abierta
    respuesta = _quedan(e, familia.admin, familia, perfil, {"stock_unidades": 25})
    assert respuesta.status_code == 200
    assert (respuesta.json()["avisando"], respuesta.json()["alerta_id"]) == (True, str(abierta))
    assert _alertas(perfil) == [(abierta, "2026-10-26", "pendiente")]


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({}, "stock_unidades"),
        ({"stock_unidades": 100_001}, "stock_unidades"),
        ({"stock_unidades": -1}, "stock_unidades"),
        ({"stock_unidades": 3, "cantidad": 1}, "cantidad"),
    ],
)
def test_me_quedan_cuerpo_invalido_es_422(entorno_consumo: EntornoConsumo, cuerpo: dict[str, Any], campo: str) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    respuesta = _quedan(e, familia.admin, familia, perfil, cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0]["campo"] == campo
    _sin_cambios(perfil)


def test_me_quedan_cobertura_maxima_412_y_428(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    lento = e.fabrica.perfil_consumo(familia.persona, tasa_unidades=1, tasa_dias=90, nombre_libre="Crema")
    respuesta = _quedan(e, familia.admin, familia, lento, {"stock_unidades": 100})
    assert respuesta.status_code == 422
    assert (respuesta.json()["errores"][0]["campo"], respuesta.json()["errores"][0]["tipo"]) == (
        "stock_unidades", "cobertura_maxima")
    perfil = e.fabrica.perfil_consumo(familia.persona, version=3)
    assert _quedan(e, familia.admin, familia, perfil, {"stock_unidades": 3}).status_code == 412
    sin = e.pedir("POST", familia.admin, familia, QUEDAN.format(perfil), json={"stock_unidades": 3})
    assert sin.status_code == 428
    assert _filas("SELECT stock_unidades, version FROM perfil_consumo WHERE id = %s", perfil) == [(24, 3)]


# --- Logs y auditoría (condición 8) -----------------------------------------------------------------------------


def test_logs_errores_y_auditoria_sin_cantidad_stock_ni_nombre(
    entorno_consumo: EntornoConsumo, caplog: pytest.LogCaptureFixture
) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, nombre_libre="Toallitas secretas", unidades_por_envase=4321)
    otro = e.fabrica.perfil_consumo(familia.persona, nombre_libre="Crema secreta")
    _alerta(perfil)
    with caplog.at_level(logging.DEBUG):
        assert _compre(e, familia.admin, familia, perfil, {"envases": 1}).status_code == 200
        assert _quedan(e, familia.admin, familia, otro, {"stock_unidades": 4322}).status_code == 200
        error = _compre(e, familia.admin, familia, otro, {"cantidad": 43_210})
        assert error.status_code == 422
    textos = caplog.text + e.iam.salida_logs.getvalue()
    for valor in ("4321", "4322", "4325", "43210"):
        assert not _aparece_como_dato(valor, textos) and not _aparece_como_dato(valor, error.text)
    assert "secret" not in textos and "cantidad" not in textos and "stock_unidades" not in textos
    filas = _filas(
        "SELECT accion, (to_jsonb(a) - 'id')::text, detalle, ip FROM auditoria a WHERE grupo_id = %s", familia.grupo.id
    )
    assert {f[0] for f in filas} == {"reposicion.declarar", "alerta.resolver", "consumo.editar"}
    for _, fila, detalle, ip in filas:
        assert "secret" not in fila and detalle is None and ip is None
        assert not any(_aparece_como_dato(v, fila) for v in ("4321", "4322", "4325"))


# --- La carrera con el retiro (condición 7) -----------------------------------------------------------------------


@pytest.mark.rf("RF-10")
def test_compre_simultaneo_a_un_retiro_espera_y_termina_en_403(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    cabeceras = e.cabeceras(_cuidadora(familia), familia.grupo.id, **{"If-Match": V1})
    respuestas: list[Any] = []

    def comprar() -> None:
        respuestas.append(e.iam.cliente.post(
            f"/v1/personas-cuidadas/{familia.persona.id}/consumo/{perfil}/reponer",
            json={"cantidad": 30}, headers=cabeceras))

    fabrica = fabrica_sesiones()
    with sesion_tenant(fabrica, usuario_id=familia.admin.id, grupo_id=familia.grupo.id) as sesion:
        registro = RegistroAuditoriaSql(sesion, e.iam.reloj)
        retirar_autorizacion(
            SolicitudRetiro(usuario_id=familia.admin.id, rol="admin", persona_id=familia.persona.id,
                            finalidad="consumo"),
            e.iam.reloj, RepositorioRetirosSQL(sesion, familia.grupo.id, registro),
            efectos_de(sesion, familia.grupo.id, registro),
        )
        hilo = threading.Thread(target=comprar)
        hilo.start()
        hilo.join(timeout=1.0)
        assert hilo.is_alive()  # la compra espera el bloqueo del retiro (FOR SHARE contra FOR UPDATE)
    hilo.join(timeout=15)
    [respuesta] = respuestas
    assert respuesta.status_code == 403 and respuesta.json()["type"] == "/errores/sin-consentimiento"
    _sin_cambios(perfil)


# --- Conservación (decisión A, condición 6, migración 0017) -----------------------------------------------------


def _reposicion_hace(perfil: uuid.UUID, dias: int, origen: str = "declarada") -> uuid.UUID:
    with psycopg.connect(DSN, autocommit=True) as cx:
        fila = cx.execute(
            "INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, pedido_ref, ocurrida_en, registrada_en)"
            " VALUES (%s, 5, %s, CASE WHEN %s = 'pedido_matu' THEN gen_random_uuid() END, current_date,"
            " now() - make_interval(days => %s)) RETURNING id",
            (perfil, origen, origen, dias),
        ).fetchone()
    assert fila is not None
    return uuid.UUID(str(fila[0]))


def test_las_compras_declaradas_se_borran_a_los_90_dias(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    vieja, reciente = _reposicion_hace(perfil, 91), _reposicion_hace(perfil, 89)
    de_pedido = _reposicion_hace(perfil, 200, origen="pedido_matu")
    resultado = conservar_quiebres(
        unidad=ConservacionQuiebresSql(fabrica_sesiones()), reloj=RelojFijo(datetime.now(UTC))
    )
    assert resultado.reposiciones_borradas >= 1
    quedan = {f[0] for f in _filas("SELECT id FROM reposicion WHERE perfil_id = %s", perfil)}
    assert vieja not in quedan and {reciente, de_pedido} <= quedan


@pytest.mark.rf("RF-10")
def test_tras_90_dias_del_retiro_consumo_conservar_borra_las_compras(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    assert _compre(e, familia.admin, familia, perfil, {"cantidad": 30}).status_code == 200
    assert len(_reposiciones(perfil)) == 1
    ahora = datetime.now(UTC)
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE consentimiento SET revocado_en = %s, revocacion_motivo = 'retiro'"
                   " WHERE persona_cuidada_id = %s AND finalidad = 'consumo'", (ahora - timedelta(days=91),
                                                                               familia.persona.id))
    conservar(unidad=ConservacionConsumoSql(fabrica_sesiones()), reloj=RelojFijo(ahora))
    assert _filas("SELECT 1 FROM perfil_consumo WHERE id = %s", perfil) == []
    assert _filas("SELECT 1 FROM reposicion WHERE perfil_id = %s", perfil) == []


@pytest.mark.rf("RF-10")
def test_la_autorizacion_nueva_tras_90_dias_borra_las_compras(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    assert _compre(e, familia.admin, familia, perfil, {"cantidad": 30}).status_code == 200
    retiro = e.iam.cliente.post(f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos/consumo/retiro",
                                headers=e.cabeceras(familia.admin, familia.grupo.id))
    assert retiro.status_code == 200, retiro.text
    e.iam.reloj.avanzar(timedelta(days=90))
    e.tokens.clear()
    autorizar = e.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
        json={"finalidad": "consumo", "calidad_otorgante": "titular"},
        headers=e.cabeceras(familia.admin, familia.grupo.id),
    )
    assert autorizar.status_code == 201, autorizar.text
    assert _filas("SELECT 1 FROM perfil_consumo WHERE id = %s", perfil) == []
    assert _filas("SELECT 1 FROM reposicion WHERE perfil_id = %s", perfil) == []
