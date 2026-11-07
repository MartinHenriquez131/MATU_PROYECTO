"""MATU-60 · La lista de insumos y unidades_por_envase contra PostgreSQL (RF-15, RF-14, ADR-031).

Corren como matu_app con cuentas de las fábricas. El reloj es el de entorno_iam: 20-10-2026 09:00 en
Santiago, así que «hoy» es el 20-10. El perfil por omisión de la fábrica (24 unidades a 4 por día, anotado el
20-10) se acaba el 26-10: le quedan 6 días, avisa con 7 y está en la lista, con 120 - 24 = 96 unidades.
Solo datos sintéticos.
"""

import logging
import uuid
from datetime import date, timedelta
from typing import Any

import psycopg
import pytest

from tests.base_datos import DSN, requiere_base
from tests.modules.consumption.conftest import EntornoConsumo

pytestmark = [requiere_base, pytest.mark.rf("RF-15")]

LISTA = "/lista"
HOY = "2026-10-20"
CAMPOS_LINEA = {
    "perfil_id",
    "nombre",
    "unidad",
    "dias_restantes",
    "unidades_sugeridas",
    "unidades_por_envase",
    "envases_sugeridos",
}


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _alerta(perfil: uuid.UUID, fecha: str, estado: str = "pendiente") -> uuid.UUID:
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
    return _filas("SELECT id, estado, cerrada_en FROM alerta_quiebre WHERE perfil_id = %s ORDER BY id", perfil)


# --- Camino feliz ---------------------------------------------------------------------------------------


def test_la_lista_trae_lo_que_avisa_con_la_cantidad_y_en_orden(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    p = familia.persona
    # 24 a 4 por día, anotado hoy: 6 días; 120 - 24 = 96 unidades, techo(96 / 20) = 5 envases
    panal = e.fabrica.perfil_consumo(p, nombre_libre="Pañal adulto talla M", unidades_por_envase=20)
    # 50 ml cada 7 días sin stock: se acaba hoy; 215 ml, 1 frasco de 250
    crema = e.fabrica.perfil_consumo(
        p,
        nombre_libre="Crema hidratante",
        unidad="ml",
        tasa_unidades=50,
        tasa_dias=7,
        stock_unidades=0,
        unidades_por_envase=250,
    )
    # 12 cada 3 días, 14 anotadas el 17-10: piso(14 × 3 / 12) = 3 días, se acaba hoy; quedan 2, 120 - 2 = 118
    toallitas = e.fabrica.perfil_consumo(
        p,
        nombre_libre="Toallitas húmedas",
        tasa_unidades=12,
        tasa_dias=3,
        stock_unidades=14,
        stock_medido_en=date(2026, 10, 17),
    )
    # La alerta de su fecha abierta: entra igual
    _alerta(toallitas, HOY)
    # Fuera de la lista: fuera de su ventana, desactivado y con la alerta de su fecha descartada
    e.fabrica.perfil_consumo(p, nombre_libre="Guantes", stock_unidades=400)
    e.fabrica.perfil_consumo(p, nombre_libre="Sabanilla", activo=False)
    descartado = e.fabrica.perfil_consumo(p, nombre_libre="Apósitos")
    _alerta(descartado, "2026-10-26", "descartada")

    respuesta = e.pedir("GET", familia.admin, familia, LISTA)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["Cache-Control"] == "no-store"
    cuerpo = respuesta.json()
    assert cuerpo["fecha"] == HOY
    # Mismo día (20-10): «Crema» antes que «Toallitas»; después el pañal (26-10)
    assert cuerpo["items"] == [
        {
            "perfil_id": str(crema),
            "nombre": "Crema hidratante",
            "unidad": "ml",
            "dias_restantes": 0,
            "unidades_sugeridas": 215,
            "unidades_por_envase": 250,
            "envases_sugeridos": 1,
        },
        {
            "perfil_id": str(toallitas),
            "nombre": "Toallitas húmedas",
            "unidad": "unidad",
            "dias_restantes": 0,
            "unidades_sugeridas": 118,
            "unidades_por_envase": None,
            "envases_sugeridos": None,
        },
        {
            "perfil_id": str(panal),
            "nombre": "Pañal adulto talla M",
            "unidad": "unidad",
            "dias_restantes": 6,
            "unidades_sugeridas": 96,
            "unidades_por_envase": 20,
            "envases_sugeridos": 5,
        },
    ]


def test_la_lista_es_lo_de_se_acaban_pronto_que_esta_avisando(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    p = familia.persona
    sin_alerta = e.fabrica.perfil_consumo(p, nombre_libre="Sin alerta")
    # La familia anotó de nuevo y la fecha cambió: la alerta abierta quedó de otra fecha. Entra igual
    desalineado = e.fabrica.perfil_consumo(p, nombre_libre="Desalineado", stock_unidades=20)
    _alerta(desalineado, "2026-10-26")
    resuelto = e.fabrica.perfil_consumo(p, nombre_libre="Resuelto", stock_unidades=16)
    _alerta(resuelto, "2026-10-24", "resuelta")
    pronto = e.pedir("GET", familia.admin, familia, "/por-acabarse").json()["items"]
    avisando = [i["id"] for i in pronto if i["avisando"]]
    lista = e.pedir("GET", familia.admin, familia, LISTA).json()["items"]
    assert [i["perfil_id"] for i in lista] == avisando
    assert set(avisando) == {str(sin_alerta), str(desalineado)}
    assert str(resuelto) in {i["id"] for i in pronto}


def test_ya_lo_resolvi_saca_el_insumo_de_la_lista_y_la_lista_no_escribe_nada(
    entorno_consumo: EntornoConsumo,
) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    _alerta(perfil, "2026-10-26")
    antes_auditoria = _filas("SELECT count(*) FROM auditoria WHERE grupo_id = %s", familia.grupo.id)
    antes_alertas = _alertas(perfil)
    for _ in range(2):
        assert [i["perfil_id"] for i in e.pedir("GET", familia.admin, familia, LISTA).json()["items"]] == [str(perfil)]
    # Leer la lista no audita, no crea ni cierra alertas y no publica eventos
    assert _filas("SELECT count(*) FROM auditoria WHERE grupo_id = %s", familia.grupo.id) == antes_auditoria
    assert _alertas(perfil) == antes_alertas
    assert _filas("SELECT count(*) FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id) == [(0,)]
    resuelto = e.pedir("POST", familia.admin, familia, f"/{perfil}/resolver", If_Match='"v1"')
    assert resuelto.status_code == 200, resuelto.text
    assert e.pedir("GET", familia.admin, familia, LISTA).json()["items"] == []


def test_la_lista_vacia(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    respuesta = e.pedir("GET", familia.admin, familia, LISTA)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"fecha": HOY, "items": []}
    assert respuesta.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("rol", ["cuidador", "pagador", "pagador_con_plan", "observador"])
def test_los_cuatro_roles_reciben_la_misma_lista(entorno_consumo: EntornoConsumo, rol: str) -> None:
    e = entorno_consumo
    familia = e.familia()
    e.fabrica.perfil_consumo(familia.persona, unidades_por_envase=20)
    del_admin = e.pedir("GET", familia.admin, familia, LISTA)
    del_rol = e.pedir("GET", familia.miembros[rol].usuario, familia, LISTA)
    assert del_rol.status_code == 200 and del_rol.json() == del_admin.json()
    assert len(del_rol.json()["items"]) == 1


def test_la_respuesta_trae_exactamente_los_campos_del_esquema(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    e.fabrica.perfil_consumo(familia.persona, nombre_libre="Pañal adulto talla M", unidades_por_envase=20)
    e.fabrica.perfil_consumo(familia.persona, nombre_libre="Toallitas húmedas", stock_unidades=8)
    respuesta = e.pedir("GET", familia.admin, familia, LISTA)
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"fecha", "items"}
    assert len(cuerpo["items"]) == 2 and all(set(linea) == CAMPOS_LINEA for linea in cuerpo["items"])
    # Ni la persona (nombre, nombre de pila ni id), ni el grupo, ni la tasa, el stock, la alerta o el etag
    texto = respuesta.text
    for prohibido in (
        familia.persona.nombre,
        familia.persona.nombre_pila,
        str(familia.persona.id),
        familia.grupo.nombre,
        str(familia.grupo.id),
        "tasa",
        "stock",
        "alerta",
        "etag",
        "fecha_quiebre",
        "precio",
    ):
        assert prohibido not in texto, prohibido


def test_el_nombre_es_el_del_producto_y_el_envase_nunca_sale_del_catalogo(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    categoria, producto = uuid.uuid4(), uuid.uuid4()
    # El catálogo no está en las fábricas: se siembra aquí, como superusuario, y se borra al final
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("INSERT INTO categoria_cuidado (id, nombre) VALUES (%s, 'Higiene de prueba')", (categoria,))
        cx.execute(
            "INSERT INTO producto (id, categoria_id, nombre, presentacion, unidad, unidades_por_envase)"
            " VALUES (%s, %s, 'Pañal sintético', 'Paquete x30', 'unidad', 30)",
            (producto, categoria),
        )
    perfil = None
    try:
        perfil = e.fabrica.perfil_consumo(familia.persona, producto_id=producto)
        [linea] = e.pedir("GET", familia.admin, familia, LISTA).json()["items"]
        # El nombre del producto, sin la presentación
        assert linea["nombre"] == "Pañal sintético"
        # El catálogo dice 30 por envase, pero la lista usa solo el dato del perfil (decisión 121)
        assert linea["unidades_por_envase"] is None and linea["envases_sugeridos"] is None
    finally:
        with psycopg.connect(DSN, autocommit=True) as cx:
            if perfil is not None:
                cx.execute("DELETE FROM perfil_consumo WHERE id = %s", (perfil,))
            cx.execute("DELETE FROM producto WHERE id = %s", (producto,))
            cx.execute("DELETE FROM categoria_cuidado WHERE id = %s", (categoria,))


# --- Autorización y 404 ---------------------------------------------------------------------------------


def _problema(respuesta: Any, status: int, tipo: str) -> dict[str, Any]:
    assert respuesta.status_code == status, respuesta.text
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    cuerpo: dict[str, Any] = respuesta.json()
    assert cuerpo["type"] == tipo
    return cuerpo


def test_sin_autorizacion_para_consumo_es_403(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    e.fabrica.perfil_consumo(familia.persona)
    cuerpo = _problema(e.pedir("GET", familia.admin, familia, LISTA), 403, "/errores/sin-consentimiento")
    assert cuerpo["finalidad"] == "consumo"
    assert "Pañal" not in str(cuerpo)


def test_con_la_revision_vencida_es_403(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    e.fabrica.autorizacion_consumo(
        familia.persona,
        otorgante=familia.admin,
        calidad="cuidador_de_hecho",
        otorgado_en=e.iam.reloj.ahora() - timedelta(days=366),
    )
    observador = familia.miembros["observador"].usuario
    cuerpo = _problema(e.pedir("GET", observador, familia, LISTA), 403, "/errores/revision-vencida")
    assert cuerpo["finalidad"] == "consumo"


def test_con_la_autorizacion_retirada_es_403(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    ahora = e.iam.reloj.ahora()
    e.fabrica.autorizacion_consumo(
        familia.persona,
        otorgante=familia.admin,
        otorgado_en=ahora - timedelta(days=10),
        revocado_en=ahora - timedelta(days=1),
    )
    e.fabrica.perfil_consumo(familia.persona)
    cuerpo = _problema(e.pedir("GET", familia.admin, familia, LISTA), 403, "/errores/sin-consentimiento")
    assert cuerpo["finalidad"] == "consumo"


def test_404_para_quien_no_es_miembro_otro_grupo_persona_inexistente_e_id_no_uuid(
    entorno_consumo: EntornoConsumo,
) -> None:
    e = entorno_consumo
    familia, otra = e.familia(), e.familia()
    e.fabrica.perfil_consumo(familia.persona)
    ruta = f"/v1/personas-cuidadas/{familia.persona.id}/consumo/lista"
    # No es miembro del grupo que pide en X-Grupo-Id
    _problema(e.iam.cliente.get(ruta, headers=e.cabeceras(otra.admin, familia.grupo.id)), 404, "/errores/no-encontrado")
    # La persona es de otro grupo
    _problema(e.pedir("GET", otra.admin, otra, LISTA, persona=familia.persona.id), 404, "/errores/no-encontrado")
    # Persona inexistente y un id que no es UUID
    _problema(e.pedir("GET", familia.admin, familia, LISTA, persona=uuid.uuid4()), 404, "/errores/no-encontrado")
    _problema(e.pedir("GET", familia.admin, familia, LISTA, persona="no-es-uuid"), 404, "/errores/no-encontrado")
    # Sin X-Grupo-Id o con uno que no es UUID
    token = {"Authorization": f"Bearer {e.token(familia.admin)}"}
    _problema(e.iam.cliente.get(ruta, headers=token), 404, "/errores/no-encontrado")
    _problema(e.iam.cliente.get(ruta, headers={**token, "X-Grupo-Id": "x"}), 404, "/errores/no-encontrado")


def test_sin_token_o_con_uno_invalido_es_401_con_no_store(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    ruta = f"/v1/personas-cuidadas/{familia.persona.id}/consumo/lista"
    _problema(e.iam.cliente.get(ruta, headers={"X-Grupo-Id": str(familia.grupo.id)}), 401, "/errores/no-autenticado")
    invalido = e.iam.cliente.get(
        ruta, headers={"Authorization": "Bearer no.es.un-token", "X-Grupo-Id": str(familia.grupo.id)}
    )
    _problema(invalido, 401, "/errores/token-invalido")


def test_los_logs_no_llevan_el_nombre_del_insumo(
    entorno_consumo: EntornoConsumo, caplog: pytest.LogCaptureFixture
) -> None:
    e = entorno_consumo
    familia = e.familia()
    e.fabrica.perfil_consumo(familia.persona, nombre_libre="Toallitas secretas")
    with caplog.at_level(logging.DEBUG):
        respuesta = e.pedir("GET", familia.admin, familia, LISTA)
        assert respuesta.status_code == 200 and "secret" in respuesta.text
    textos = caplog.text + e.iam.salida_logs.getvalue()
    # «secret» tiene letras fuera de a-f: no puede salir en un UUID ni en hex
    assert "secret" not in textos
    assert "/consumo/lista" in textos or "{persona_id}/consumo/lista" in textos


# --- unidades_por_envase en el perfil (RF-14, decisión 121) ----------------------------------------------


@pytest.mark.rf("RF-14")
def test_patch_pone_y_borra_el_envase_y_la_lista_lo_usa(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    cuidadora = familia.miembros["cuidador"].usuario
    creado = e.crear(cuidadora, familia, unidades_por_envase=20)
    assert creado.status_code == 201, creado.text
    perfil = creado.json()
    assert perfil["unidades_por_envase"] == 20
    assert _filas("SELECT unidades_por_envase FROM perfil_consumo WHERE id = %s", perfil["id"]) == [(20,)]
    [linea] = e.pedir("GET", cuidadora, familia, LISTA).json()["items"]
    assert (linea["unidades_sugeridas"], linea["envases_sugeridos"]) == (96, 5)

    cambiado = e.pedir(
        "PATCH", cuidadora, familia, f"/{perfil['id']}", json={"unidades_por_envase": 30}, If_Match='"v1"'
    )
    assert cambiado.status_code == 200, cambiado.text
    assert cambiado.json()["unidades_por_envase"] == 30 and cambiado.headers["ETag"] == '"v2"'
    assert cambiado.json()["stock_medido_en"] == perfil["stock_medido_en"]
    assert e.pedir("GET", cuidadora, familia, LISTA).json()["items"][0]["envases_sugeridos"] == 4

    borrado = e.pedir(
        "PATCH", cuidadora, familia, f"/{perfil['id']}", json={"unidades_por_envase": None}, If_Match='"v2"'
    )
    assert borrado.status_code == 200, borrado.text
    assert borrado.json()["unidades_por_envase"] is None and borrado.json()["etag"] == '"v3"'
    assert _filas("SELECT unidades_por_envase, version FROM perfil_consumo WHERE id = %s", perfil["id"]) == [(None, 3)]
    [linea] = e.pedir("GET", cuidadora, familia, LISTA).json()["items"]
    assert (linea["unidades_sugeridas"], linea["unidades_por_envase"], linea["envases_sugeridos"]) == (96, None, None)
    # Lo devuelven también «Se acaban pronto» y la lectura del perfil
    assert e.pedir("GET", cuidadora, familia, "/por-acabarse").json()["items"][0]["unidades_por_envase"] is None
    assert e.pedir("GET", cuidadora, familia, f"/{perfil['id']}").json()["unidades_por_envase"] is None
    acciones = [a for (a,) in _filas("SELECT accion FROM auditoria WHERE grupo_id = %s ORDER BY id", familia.grupo.id)]
    assert acciones.count("consumo.editar") == 2


@pytest.mark.rf("RF-14")
@pytest.mark.parametrize("valor", [0, 10_001])
def test_envase_fuera_de_rango_es_422_y_no_cambia_nada(entorno_consumo: EntornoConsumo, valor: int) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, unidades_por_envase=20)
    respuesta = e.pedir(
        "PATCH", familia.admin, familia, f"/{perfil}", json={"unidades_por_envase": valor}, If_Match='"v1"'
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0]["campo"] == "unidades_por_envase"
    assert _filas("SELECT unidades_por_envase, version FROM perfil_consumo WHERE id = %s", perfil) == [(20, 1)]
    creado = e.crear(familia.admin, familia, nombre_libre="Toallitas", unidades_por_envase=valor)
    assert creado.status_code == 422


@pytest.mark.rf("RF-14")
def test_pagador_y_observador_no_cambian_el_envase(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    for rol in ("pagador", "observador"):
        respuesta = e.pedir(
            "PATCH",
            familia.miembros[rol].usuario,
            familia,
            f"/{perfil}",
            json={"unidades_por_envase": 20},
            If_Match='"v1"',
        )
        assert respuesta.status_code == 404
    assert _filas("SELECT unidades_por_envase FROM perfil_consumo WHERE id = %s", perfil) == [(None,)]
