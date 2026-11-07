"""MATU-37 · Se acaban pronto, alertas, «Ya lo resolví» y el trabajo diario contra PostgreSQL (RF-12).

Corren como matu_app con cuentas de las fábricas. El reloj es el de entorno_iam: 20-10-2026 09:00 en
Santiago. El perfil por omisión de la fábrica (24 unidades a 4 por día, anotado el 20-10) se acaba el
26-10: le quedan 6 días y avisa con 7, así que está en su ventana. Solo datos sintéticos.
"""

import logging
import re
import uuid
from typing import Any

import psycopg
import pytest

from app.core.db import fabrica_sesiones
from app.modules.consumption.infrastructure.tarea_quiebres import grupos_activos, recalcular_grupo
from tests.base_datos import DSN, requiere_base
from tests.modules.consumption.conftest import EntornoConsumo

pytestmark = [requiere_base, pytest.mark.rf("RF-12")]

NOMBRE = "Pañal adulto M"
V1 = '"v1"'


def _aparece_como_dato(valor: str, texto: str) -> bool:
    """True si valor aparece completo en texto, no como parte de otra palabra, número, UUID o hex.

    Los límites excluyen letras, dígitos, _, - y punto. Un UUID son grupos hexadecimales separados por -, así
    que un grupo que sea justo «4321» (…-1767-4321-…, lo que hizo fallar el CI) no cuenta: siempre queda
    entre - o hex. Tampoco una duración como 4321.0 ms. Sí cuenta como valor JSON ("cantidad": 4321), tras
    = o entre espacios.
    """
    return re.search(rf"(?<![\w.-]){re.escape(valor)}(?![\w.-])", texto) is not None


@pytest.mark.parametrize(
    ("texto", "aparece"),
    [
        ('{"cantidad": 4321}', True),
        ("cantidad=4321 ", True),
        ("[4321]", True),
        ('"request_id": "6f1c2b9e-1767-4321-9a0b-0c1d2e3f4a5b"', False),
        ("a3f14321", False),
        ("43210", False),
        ('"duracion_ms": 4321.0', False),
        ("v4321", False),
    ],
)
def test_aparece_como_dato_no_confunde_un_uuid_con_el_valor(texto: str, aparece: bool) -> None:
    assert _aparece_como_dato("4321", texto) is aparece


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _acciones(grupo: uuid.UUID) -> list[tuple[str, str]]:
    return [
        (a, t) for a, t in _filas("SELECT accion, actor_tipo FROM auditoria WHERE grupo_id = %s ORDER BY id", grupo)
    ]


def _alerta(perfil: uuid.UUID, estado: str = "pendiente") -> uuid.UUID:
    with psycopg.connect(DSN, autocommit=True) as cx:
        cerrada = "now()" if estado in ("resuelta", "descartada") else "NULL"
        fila = cx.execute(
            "INSERT INTO alerta_quiebre (perfil_id, fecha_prevista, estado, cerrada_en)"
            f" VALUES (%s, '2026-10-26', %s, {cerrada}) RETURNING id",
            (perfil, estado),
        ).fetchone()
    assert fila is not None
    return uuid.UUID(str(fila[0]))


# --- Se acaban pronto ----------------------------------------------------------------------------------


def test_por_acabarse_trae_los_de_la_ventana_con_avisando(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    pronto = e.fabrica.perfil_consumo(familia.persona)
    e.fabrica.perfil_consumo(familia.persona, nombre_libre="Toallitas", stock_unidades=400)  # 100 días
    e.fabrica.perfil_consumo(familia.persona, nombre_libre="Crema", activo=False)
    observador = familia.miembros["observador"].usuario
    respuesta = e.pedir("GET", observador, familia, "/por-acabarse")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["Cache-Control"] == "no-store"
    [item] = respuesta.json()["items"]
    assert (item["id"], item["dias_restantes"], item["avisando"], item["alerta_id"]) == (str(pronto), 6, True, None)


def test_por_acabarse_sin_autorizacion_403_y_otro_grupo_404(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    sin = e.familia(con_autorizacion=False)
    assert e.pedir("GET", sin.admin, sin, "/por-acabarse").status_code == 403
    otra = e.familia()
    respuesta = e.pedir("GET", otra.admin, otra, "/por-acabarse", persona=sin.persona.id)
    assert respuesta.status_code == 404


# --- Lista y descartar ---------------------------------------------------------------------------------


def test_listar_y_descartar_una_alerta(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    alerta = _alerta(perfil)
    pagador = familia.miembros["pagador"].usuario
    lista = e.pedir("GET", pagador, familia, "/alertas")
    assert lista.status_code == 200
    assert [a["id"] for a in lista.json()["items"]] == [str(alerta)]
    # pagador lee pero no descarta: 404
    assert e.pedir("POST", pagador, familia, f"/alertas/{alerta}/descartar").status_code == 404
    respuesta = e.pedir("POST", familia.admin, familia, f"/alertas/{alerta}/descartar")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "descartada" and respuesta.json()["cerrada_en"] is not None
    otra_vez = e.pedir("POST", familia.admin, familia, f"/alertas/{alerta}/descartar")
    assert otra_vez.status_code == 409
    assert (otra_vez.json()["type"], otra_vez.json()["estado"]) == ("/errores/alerta-cerrada", "descartada")
    assert e.pedir("GET", familia.admin, familia, "/alertas").json()["items"] == []
    cerradas = e.pedir("GET", familia.admin, familia, "/alertas", params={"estado": ["descartada"]})
    assert [a["id"] for a in cerradas.json()["items"]] == [str(alerta)]
    assert ("alerta.descartar", "usuario") in _acciones(familia.grupo.id)


def test_descartar_alerta_de_otro_grupo_es_404(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    a, b = e.familia(), e.familia()
    alerta_b = _alerta(e.fabrica.perfil_consumo(b.persona))
    assert e.pedir("POST", a.admin, a, f"/alertas/{alerta_b}/descartar").status_code == 404
    assert e.pedir("POST", a.admin, a, "/alertas/no-es-uuid/descartar").status_code == 404
    assert _filas("SELECT estado FROM alerta_quiebre WHERE id = %s", alerta_b) == [("pendiente",)]


def test_estado_invalido_es_422(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    respuesta = e.pedir("GET", familia.admin, familia, "/alertas", params={"estado": ["borrada"]})
    assert respuesta.status_code == 422 and respuesta.json()["errores"][0]["campo"] == "estado"


# --- Ya lo resolví -------------------------------------------------------------------------------------


def test_resolver_sin_alerta_previa_apaga_el_aviso(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    cuidadora = familia.miembros["cuidador"].usuario
    respuesta = e.pedir("POST", cuidadora, familia, f"/{perfil}/resolver", If_Match=V1)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["avisando"] is False and cuerpo["alerta_id"] is not None
    assert _filas("SELECT estado FROM alerta_quiebre WHERE perfil_id = %s", perfil) == [("descartada",)]
    [item] = e.pedir("GET", cuidadora, familia, "/por-acabarse").json()["items"]
    assert item["avisando"] is False
    repetido = e.pedir("POST", cuidadora, familia, f"/{perfil}/resolver", If_Match=V1, json={"cantidad": None})
    assert repetido.status_code == 409 and repetido.json()["type"] == "/errores/alerta-cerrada"


def test_resolver_con_cantidad_suma_anota_la_reposicion_y_resuelve(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    # Anotado hoy (20-10): 24 a 4 por día. + 30 = 54, alcanza 13 días: 02-11, fuera de la ventana de 7
    perfil = e.fabrica.perfil_consumo(familia.persona)
    cuidadora = familia.miembros["cuidador"].usuario
    respuesta = e.pedir("POST", cuidadora, familia, f"/{perfil}/resolver", If_Match=V1, json={"cantidad": 30})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["stock_unidades"], cuerpo["stock_medido_en"], cuerpo["fecha_quiebre_estimada"]) == (
        54,
        "2026-10-20",
        "2026-11-02",
    )
    assert cuerpo["dias_restantes"] == 13 and cuerpo["avisando"] is False and cuerpo["alerta_id"] is None
    assert cuerpo["etag"] == '"v2"' and respuesta.headers["ETag"] == '"v2"'
    assert cuerpo["actualizado_por"]["id"] == str(cuidadora.id)
    assert _filas("SELECT estado FROM alerta_quiebre WHERE perfil_id = %s", perfil) == [("resuelta",)]
    assert _filas(
        "SELECT cantidad_unidades, origen, registrada_por, ocurrida_en::text FROM reposicion WHERE perfil_id = %s",
        perfil,
    ) == [(30, "declarada", cuidadora.id, "2026-10-20")]
    acciones = _acciones(familia.grupo.id)
    assert ("reposicion.declarar", "usuario") in acciones and ("alerta.resolver", "usuario") in acciones
    # Ya no está en «Se acaban pronto»
    assert e.pedir("GET", cuidadora, familia, "/por-acabarse").json()["items"] == []


def test_resolver_con_cantidad_y_stock_estimado_negativo_parte_de_cero(entorno_consumo: EntornoConsumo) -> None:
    from datetime import date

    e = entorno_consumo
    familia = e.familia()
    # Anotado el 10-10: 24 - 40 es negativo, queda 0; + 30 = 30, alcanza 7 días: 27-10
    perfil = e.fabrica.perfil_consumo(familia.persona, stock_medido_en=date(2026, 10, 10))
    respuesta = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", If_Match=V1, json={"cantidad": 30})
    assert respuesta.status_code == 200, respuesta.text
    assert (respuesta.json()["stock_unidades"], respuesta.json()["fecha_quiebre_estimada"]) == (30, "2026-10-27")


def test_resolver_cantidad_fuera_de_rango_es_422_sin_tocar_nada(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    for cantidad in (0, 10_001, -3):  # decisión 144: el tope es 10.000
        respuesta = e.pedir(
            "POST", familia.admin, familia, f"/{perfil}/resolver", If_Match=V1, json={"cantidad": cantidad}
        )
        assert respuesta.status_code == 422
        [error] = respuesta.json()["errores"]
        assert error["campo"] == "cantidad"
    assert _filas("SELECT 1 FROM alerta_quiebre WHERE perfil_id = %s", perfil) == []
    assert _filas("SELECT 1 FROM reposicion WHERE perfil_id = %s", perfil) == []


@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_pagador_y_observador_no_declaran_compras(entorno_consumo: EntornoConsumo, rol: str) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    usuario = familia.miembros[rol].usuario
    assert (
        e.pedir("POST", usuario, familia, f"/{perfil}/resolver", If_Match=V1, json={"cantidad": 30}).status_code == 404
    )
    assert _filas("SELECT 1 FROM reposicion WHERE perfil_id = %s", perfil) == []
    assert _filas("SELECT stock_unidades FROM perfil_consumo WHERE id = %s", perfil) == [(24,)]


def test_resolver_observador_404_y_perfil_inactivo_409(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    observador = familia.miembros["observador"].usuario
    assert e.pedir("POST", observador, familia, f"/{perfil}/resolver", If_Match=V1).status_code == 404
    inactivo = e.fabrica.perfil_consumo(familia.persona, nombre_libre="Crema", activo=False)
    respuesta = e.pedir("POST", familia.admin, familia, f"/{inactivo}/resolver", If_Match=V1)
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/perfil-inactivo"


def test_los_logs_y_la_auditoria_no_llevan_el_nombre(
    entorno_consumo: EntornoConsumo, caplog: pytest.LogCaptureFixture
) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, nombre_libre="Toallitas secretas")
    otro = e.fabrica.perfil_consumo(familia.persona, nombre_libre="Crema secreta")
    with caplog.at_level(logging.DEBUG):
        assert e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", If_Match=V1).status_code == 200
        con = e.pedir("POST", familia.admin, familia, f"/{otro}/resolver", If_Match=V1, json={"cantidad": 4321})
        assert con.status_code == 200
    textos = caplog.text + e.iam.salida_logs.getvalue()
    # «secret» tiene letras fuera de a-f y no puede salir en un UUID ni en hex: basta la subcadena. «4321» sí
    # puede ser un grupo de un UUID aleatorio, así que se busca como dato completo
    assert "secret" not in textos and not _aparece_como_dato("4321", textos) and "cantidad" not in textos
    # Sin la columna id: es el único número de la fila y, con la secuencia avanzada, podría valer 4321
    filas = _filas(
        "SELECT accion, (to_jsonb(a) - 'id')::text, detalle FROM auditoria a WHERE grupo_id = %s", familia.grupo.id
    )
    acciones = {f[0] for f in filas}
    assert {"alerta.descartar", "alerta.resolver", "reposicion.declarar"} <= acciones
    assert all("secret" not in f[1] and not _aparece_como_dato("4321", f[1]) and f[2] is None for f in filas)


# --- Trabajo diario ------------------------------------------------------------------------------------


def test_el_trabajo_diario_materializa_publica_y_no_duplica(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    fabrica = fabrica_sesiones()
    assert familia.grupo.id in grupos_activos(fabrica)
    resultado = recalcular_grupo(fabrica, familia.grupo.id, e.iam.reloj)
    assert resultado.materializadas == 1
    [(alerta_id, estado)] = _filas("SELECT id, estado FROM alerta_quiebre WHERE perfil_id = %s", perfil)
    assert estado == "pendiente"
    [(tipo, payload)] = _filas("SELECT tipo, payload FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id)
    assert tipo == "QuiebreProximo"
    assert payload == {
        "alerta_id": str(alerta_id),
        "perfil_id": str(perfil),
        "persona_cuidada_id": str(familia.persona.id),
    }
    assert ("alerta.materializar", "sistema") in _acciones(familia.grupo.id)
    # Una corrida doble no crea otra alerta ni otro evento
    assert recalcular_grupo(fabrica, familia.grupo.id, e.iam.reloj).materializadas == 0
    assert len(_filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id)) == 1
    # La pantalla ve la alerta en el ítem
    [item] = e.pedir("GET", familia.admin, familia, "/por-acabarse").json()["items"]
    assert item["alerta_id"] == str(alerta_id) and item["avisando"] is True


def test_el_trabajo_diario_no_avisa_sin_autorizacion(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    perfil = e.fabrica.perfil_consumo(familia.persona)
    resultado = recalcular_grupo(fabrica_sesiones(), familia.grupo.id, e.iam.reloj)
    assert resultado.materializadas == 0
    assert _filas("SELECT 1 FROM alerta_quiebre WHERE perfil_id = %s", perfil) == []
    assert _filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id) == []


def test_el_trabajo_diario_respeta_el_resolvi_de_la_familia(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    assert e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", If_Match=V1).status_code == 200
    assert recalcular_grupo(fabrica_sesiones(), familia.grupo.id, e.iam.reloj).materializadas == 0
    assert _filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id) == []


def test_la_conservacion_de_alertas_corre_como_operacion(entorno_consumo: EntornoConsumo) -> None:
    from datetime import UTC, datetime

    from app.modules.consumption.application.conservacion import conservar_quiebres
    from app.modules.consumption.infrastructure.tarea_quiebres import ConservacionQuiebresSql
    from tests.dobles.reloj_fijo import RelojFijo

    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "INSERT INTO alerta_quiebre (perfil_id, fecha_prevista, estado, creada_en, cerrada_en) VALUES"
            " (%(p)s, '2026-01-01', 'descartada', now() - interval '120 days', now() - interval '100 days'),"
            " (%(p)s, '2026-10-26', 'descartada', now(), now())",
            {"p": perfil},
        )
    resultado = conservar_quiebres(
        unidad=ConservacionQuiebresSql(fabrica_sesiones()), reloj=RelojFijo(datetime.now(UTC))
    )
    assert resultado.alertas_borradas >= 1
    assert _filas("SELECT fecha_prevista::text FROM alerta_quiebre WHERE perfil_id = %s", perfil) == [("2026-10-26",)]


# --- Decisión 80: «Ya lo resolví» es condicional (hallazgo P2 de la QA) ----------------------------------


def test_dos_resolver_con_cantidad_y_el_mismo_etag_suman_una_sola_vez(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    primero = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", json={"cantidad": 5}, If_Match=V1)
    assert primero.status_code == 200, primero.text
    assert primero.json()["etag"] == '"v2"'
    segundo = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", json={"cantidad": 5}, If_Match=V1)
    assert segundo.status_code == 412
    cuerpo = segundo.json()
    assert cuerpo["type"] == "/errores/version-desactualizada"
    assert cuerpo["actual"]["etag"] == '"v2"' and cuerpo["actual"]["stock_unidades"] == 29
    assert cuerpo["actual"]["actualizado_por"]["id"] == str(familia.admin.id)
    assert segundo.headers["ETag"] == '"v2"' and segundo.headers["Cache-Control"] == "no-store"
    assert _filas("SELECT count(*) FROM reposicion WHERE perfil_id = %s", perfil) == [(1,)]
    assert _filas("SELECT stock_unidades, version FROM perfil_consumo WHERE id = %s", perfil) == [(29, 2)]
    assert _filas("SELECT estado FROM alerta_quiebre WHERE perfil_id = %s", perfil) == [("resuelta",)]


@pytest.mark.parametrize("valor", [None, "", "*"])
def test_resolver_sin_if_match_es_428_y_no_toca_nada(entorno_consumo: EntornoConsumo, valor: str | None) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    extra: dict[str, Any] = {} if valor is None else {"If_Match": valor}
    respuesta = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", json={"cantidad": 5}, **extra)
    assert respuesta.status_code == 428 and respuesta.json()["type"] == "/errores/falta-version"
    assert _filas("SELECT 1 FROM alerta_quiebre WHERE perfil_id = %s", perfil) == []
    assert _filas("SELECT 1 FROM reposicion WHERE perfil_id = %s", perfil) == []


def test_descartar_con_etag_viejo_es_412_y_no_cierra(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, version=3)
    respuesta = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", If_Match=V1)
    assert respuesta.status_code == 412
    assert _filas("SELECT 1 FROM alerta_quiebre WHERE perfil_id = %s", perfil) == []


def test_por_acabarse_trae_el_etag_de_cada_insumo(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    e.fabrica.perfil_consumo(familia.persona, version=4)
    [item] = e.pedir("GET", familia.admin, familia, "/por-acabarse").json()["items"]
    assert item["etag"] == '"v4"'
