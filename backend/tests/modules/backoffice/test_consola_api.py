"""MATU-81 · La consola de operación contra PostgreSQL: el detalle del pedido con su línea de tiempo y sus acciones, la
búsqueda por referencia en el cuerpo, la lista con filtros, la conciliación, las incidencias (con If-Match), el
catálogo de los comercios ficticios, los retractos con sus productos y su motivo, el retracto por correo de un admin
(D-81-9) y la copia de los datos («Lo que pasó con tu pedido» y «El equipo de MATU revisó el pedido»).

C34: ninguna ruta de /v1/operacion lee persona_cuidada, direccion, pedido_entrega, consentimiento, plan_* ni
perfil_consumo (se capturan las sentencias). C11 y C7: ni la nota, ni la referencia, ni el buy_order van al log.
"""

import re
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.shared.notas_operacion import CustodiaNotas, obtener_custodia_notas
from tests.base_datos import requiere_base
from tests.modules.backoffice.conftest import Despacho
from tests.modules.backoffice.test_despacho_api import PRECIO_PANAL, _codigo, _parte, _preparar_todo, _validar
from tests.modules.ordering.conftest import COSTO_ENVIO

pytestmark = [pytest.mark.rf("RF-40"), requiere_base]

TABLAS_PROHIBIDAS = re.compile(
    r"\b(persona_cuidada|direccion|pedido_entrega|consentimiento|plan_\w+|perfil_consumo)\b(?!_)", re.IGNORECASE
)


def _entregado(d: Despacho, faltan: int = 0) -> tuple[Any, dict[str, Any], str]:
    familia, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag, faltan=faltan)
    assert _validar(d, parte, _codigo(d, parte)).json()["resultado"] == "correcto"
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino").status_code == 200
    return familia, pedido, parte


def _auditadas(d: Despacho, accion: str, entidad_id: str) -> list[tuple[Any, ...]]:
    return d.sql("SELECT actor_tipo, actor_ref, grupo_id IS NOT NULL, persona_cuidada_id IS NOT NULL FROM auditoria"
                 " WHERE accion = %s AND entidad_id = %s", accion, uuid.UUID(entidad_id))


def test_el_detalle_trae_partes_lineas_linea_de_tiempo_y_acciones_y_se_audita(despacho: Despacho) -> None:
    d = despacho
    familia, pedido, _ = _entregado(d, faltan=1)
    r = d.operacion("GET", f"/pedidos/{pedido['id']}")
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    v = r.json()
    assert v["estado"] == "en_ruta" and v["total_confirmado"] == 2 * PRECIO_PANAL + COSTO_ENVIO
    [linea] = v["lineas"]
    assert (linea["cantidad"], linea["unidades_faltantes"], linea["precio_unitario"]) == (2, 1, PRECIO_PANAL)
    assert linea["devolucion"] == "hecha" and linea["monto_devuelto"] == PRECIO_PANAL
    [parte] = v["partes"]
    assert parte["estado"] == "retirada" and parte["comercio"]["nombre_fantasia"]
    # P3: las acciones de en_ruta, con lo que devolverían (el faltante ya se devolvió)
    assert {(a["accion"], a["monto_a_devolver"]) for a in v["acciones"]} == {("entregado", 0), ("no_entregado", 0)}
    # C6: la línea de tiempo nombra al comercio y nunca a la cuenta de la familia
    tipos = {e["tipo"] for e in v["linea_de_tiempo"]}
    assert {"estado", "parte", "cobro", "anulacion"} <= tipos
    assert any(e["actor_tipo"] == "comercio" and e["comercio"] for e in v["linea_de_tiempo"])
    assert str(familia.admin.id) not in r.text and str(familia.grupo.id) not in r.text
    assert str(familia.persona.id) not in r.text
    # D-81-5: se audita con el grupo y la persona; la lista no
    assert _auditadas(d, "operacion.pedido_ver", pedido["id"]) == [("operacion", d.operador.id, True, True)]  # type: ignore[union-attr]
    d.operacion("GET", "/pedidos")
    assert len(_auditadas(d, "operacion.pedido_ver", pedido["id"])) == 1


def test_las_acciones_de_un_pedido_no_entregado_dicen_cuanto_se_devuelve(despacho: Despacho) -> None:
    d = despacho
    _, pedido, _ = _entregado(d)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/no-entregado").status_code == 200
    acciones = {a["accion"]: a["monto_a_devolver"] for a in d.operacion("GET", f"/pedidos/{pedido['id']}").json()[
        "acciones"]}
    assert acciones == {"en_camino": 0, "cancelar_con_devolucion": 2 * PRECIO_PANAL + COSTO_ENVIO}


def test_un_pedido_que_no_existe_es_404_y_una_cuenta_de_familia_tambien(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    assert d.operacion("GET", f"/pedidos/{uuid.uuid4()}").status_code == 404
    assert d.operacion("GET", "/pedidos/no-es-un-id").status_code == 404
    assert d.como(familia.admin, "GET", f"/v1/operacion/pedidos/{pedido['id']}").status_code == 404


def test_buscar_por_referencia_en_el_cuerpo_y_la_lista_con_filtros(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    referencia = d.sql("SELECT referencia FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))[0][0]
    r = d.operacion("POST", "/pedidos/buscar", {"referencia": referencia.lower()})
    assert r.status_code == 200 and [p["id"] for p in r.json()["pedidos"]] == [pedido["id"]]
    assert r.headers["cache-control"] == "no-store"
    fila = r.json()["pedidos"][0]
    assert (fila["numero_partes"], fila["incidencia_abierta"], fila["devolucion_sin_terminar"]) == (1, False, False)
    assert d.operacion("POST", "/pedidos/buscar", {"referencia": "NOEXISTE"}).json()["pedidos"] == []
    assert d.operacion("POST", "/pedidos/buscar", {}).status_code == 422
    # C7: la referencia no llega al log
    assert referencia not in d.e.iam.texto_log()
    # P4: grupos y estados
    ids = lambda q: [p["id"] for p in d.operacion("GET", f"/pedidos{q}").json()["pedidos"]]  # noqa: E731
    assert pedido["id"] in ids("?grupo=por_atender") and pedido["id"] in ids("") and pedido["id"] in ids("?grupo=todos")
    assert pedido["id"] not in ids("?grupo=cerrados") and pedido["id"] not in ids("?estado=en_ruta")
    assert pedido["id"] in ids(f"?estado=en_ruta&estado={d.estado_pedido(pedido['id'])}")
    assert d.operacion("GET", "/pedidos?estado=borrador").status_code == 422
    assert d.operacion("GET", "/pedidos?grupo=otro").status_code == 422


def test_la_conciliacion_del_pedido_y_los_cobros_pendientes(despacho: Despacho) -> None:
    d = despacho
    _, pedido, _ = _entregado(d, faltan=1)
    r = d.operacion("GET", f"/pedidos/{pedido['id']}/cobro")
    assert r.status_code == 200, r.text
    c = r.json()
    total = 2 * PRECIO_PANAL + COSTO_ENVIO
    assert (c["total_confirmado"], c["cobrado"], c["devuelto"], c["queda_cobrado"]) == (
        total, total, PRECIO_PANAL, total - PRECIO_PANAL)
    assert c["estado_cargo"] == "devuelto_parcial" and c["calza"] is True
    [venta] = c["ventas"]
    assert venta["estado"] == "aprobada" and venta["buy_order"]
    assert [(a["motivo"], a["monto"], a["estado"]) for a in c["anulaciones"]] == [
        ("producto_no_entregado", PRECIO_PANAL, "hecha")]
    # C18: nada de la tarjeta, el token ni la sesión de Transbank
    for prohibido in ("token", "session_id", "ultimos4", "tipo_tarjeta", "cuotas", "codigo_autorizacion"):
        assert prohibido not in r.text
    assert venta["buy_order"] not in d.e.iam.texto_log()
    assert len(_auditadas(d, "operacion.pedido_ver", pedido["id"])) == 1
    pendientes = d.operacion("GET", "/cobros/pendientes")
    assert pendientes.status_code == 200
    assert set(pendientes.json()) == {"ventas_sin_respuesta", "anulaciones_sin_terminar"}


@pytest.mark.rf("Ley-21.719")
def test_incidencias_crear_editar_con_if_match_y_resolver(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    nota = f"Nota sintética {uuid.uuid4().hex}"
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": "faltante", "descripcion": nota,
                                                                       "asignarme": True})
    assert r.status_code == 201, r.text
    inc = r.json()
    assert (inc["estado"], inc["asignada_a_mi"], inc["version"]) == ("abierta", True, 1)
    assert r.headers["etag"] == '"i1"'
    assert _auditadas(d, "incidencia.crear", inc["id"]) == [("operacion", d.operador.id, True, True)]  # type: ignore[union-attr]
    # Decisión 471: la respuesta trae el texto, y la columna guarda solo lo cifrado con la clave de las notas
    assert (inc["descripcion"], inc["resolucion"], inc["nota_disponible"]) == (nota, None, True)
    [(cifrada, clave, persona)] = d.sql(
        "SELECT i.descripcion, i.clave_notas_id, k.persona_cuidada_id FROM incidencia i"
        " JOIN clave_notas k ON k.id = i.clave_notas_id WHERE i.id = %s", uuid.UUID(inc["id"]))
    assert nota.encode() not in bytes(cifrada) and persona == familia.persona.id
    assert d.sql("SELECT count(*) FROM clave_datos WHERE dek_cifrada_con_kek = (SELECT dek_cifrada_con_kek"
                 " FROM clave_notas WHERE id = %s)", clave) == [(0,)]
    # Tipos de D-81-3 y el largo de C11
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias",
                       {"tipo": "desviacion_monto", "descripcion": "x"}).status_code == 422
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias",
                       {"tipo": "otro", "descripcion": "x" * 501}).status_code == 422
    # La lista y el filtro
    lista = d.operacion("GET", "/incidencias?estado=abierta").json()["incidencias"]
    assert inc["id"] in [i["id"] for i in lista]
    assert d.operacion("GET", "/incidencias?estado=otra").status_code == 422
    # P7: el PATCH exige If-Match
    ruta = f"/incidencias/{inc['id']}"
    assert d.operacion("PATCH", ruta, {"estado": "en_gestion"}).status_code == 428
    assert d.operacion("PATCH", ruta, {"estado": "en_gestion"}, **{"If-Match": '"i9"'}).status_code == 412
    r = d.operacion("PATCH", ruta, {"estado": "en_gestion", "asignacion": "sin_asignar"}, **{"If-Match": '"i1"'})
    assert r.status_code == 200 and r.json()["estado"] == "en_gestion" and r.json()["asignada"] is False
    assert r.headers["etag"] == '"i2"'
    # Resolver exige la resolución, y se audita sin el texto
    assert d.operacion("PATCH", ruta, {"estado": "resuelta"}, **{"If-Match": '"i2"'}).status_code == 422
    r = d.operacion("PATCH", ruta, {"estado": "resuelta", "resolucion": "Se devolvió lo que faltó"},
                    **{"If-Match": '"i2"'})
    assert r.status_code == 200 and r.json()["resuelta_en"] is not None
    assert (r.json()["descripcion"], r.json()["resolucion"]) == (nota, "Se devolvió lo que faltó")
    [(resolucion,)] = d.sql("SELECT resolucion FROM incidencia WHERE id = %s", uuid.UUID(inc["id"]))
    assert "Se devolvió".encode() not in bytes(resolucion)
    assert d.operacion("GET", ruta).json()["resolucion"] == "Se devolvió lo que faltó"
    assert len(_auditadas(d, "incidencia.resolver", inc["id"])) == 1
    assert d.operacion("PATCH", ruta, {"estado": "abierta"}, **{"If-Match": '"i3"'}).status_code == 409
    assert d.operacion("GET", ruta).headers["etag"] == '"i3"'
    # C11: la nota no va al log ni a la auditoría
    assert nota not in d.e.iam.texto_log()
    assert d.sql("SELECT count(*) FROM auditoria WHERE detalle::text LIKE %s", f"%{nota}%") == [(0,)]

    # D-81-4 y D-81-5: la familia lo ve en la copia de sus datos
    copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)
    assert copia.status_code == 200, copia.text
    [p] = [x for x in copia.json()["pedidos"] if x["referencia"] == inc["referencia"]]
    [paso] = p["lo_que_paso"]
    assert (paso["tipo"], paso["estado"], paso["nota"]) == ("faltante", "resuelta", nota)
    assert (paso["resolucion"], paso["nota_disponible"]) == ("Se devolvió lo que faltó", True)
    assert "incidencia" not in copia.text and "incidente" not in copia.text
    d.operacion("GET", f"/pedidos/{pedido['id']}")
    copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)
    revisiones = [h for h in copia.json()["historial"]["hechos"] if h["tipo"] == "matu_reviso_el_pedido"]
    assert revisiones and revisiones[0]["referencia"] == inc["referencia"] and revisiones[0]["quien"]["tipo"] == "matu"


def _incidencia_con_resolucion(d: Despacho, pedido: dict[str, Any], nota: str) -> dict[str, Any]:
    inc = d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": "otro", "descripcion": nota}).json()
    r = d.operacion("PATCH", f"/incidencias/{inc['id']}", {"resolucion": "Resolución sintética"},
                    **{"If-Match": '"i1"'})
    assert r.status_code == 200 and r.json()["resolucion"] == "Resolución sintética"
    return inc


def _destruir_clave_de_la_ficha(d: Despacho, familia: Any) -> None:
    """La clave de la ficha de la persona se destruye como la destruye plan_destruir_claves a los 90 días del retiro
    (superusuario: los disparadores corren igual)."""
    persona = familia.persona.id
    d.sql("INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
          " SELECT %s, %s, '\\x01', 1 WHERE NOT EXISTS (SELECT 1 FROM clave_datos WHERE persona_cuidada_id = %s"
          " AND destruida_en IS NULL)", familia.grupo.id, persona, persona)
    d.sql("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now()"
          " WHERE persona_cuidada_id = %s AND destruida_en IS NULL", persona)


@pytest.mark.rf("Ley-21.719")
def test_con_la_persona_borrada_la_nota_no_esta_disponible_en_la_consola(despacho: Despacho) -> None:
    """Decisión 471 y decisión de Jorge del 17-11: cuando se borran los datos de la persona (MATU-72), se destruye su
    clave de notas, y lo anotado queda ilegible: la consola lo muestra como no disponible, sin error. La copia de sus
    datos ya no existe (404). Una nota nueva va con una clave nueva y se lee."""
    d = despacho
    familia, pedido = d.pagado()
    nota = f"Nota sintética {uuid.uuid4().hex}"
    inc = _incidencia_con_resolucion(d, pedido, nota)
    persona = familia.persona.id
    borrado = d.e.pedir("POST", f"/v1/personas-cuidadas/{persona}/borrado", familia.admin, familia)
    assert borrado.status_code == 200, borrado.text
    assert d.sql("SELECT count(*) FROM clave_notas WHERE persona_cuidada_id = %s AND destruida_en IS NULL",
                 persona) == [(0,)]

    r = d.operacion("GET", f"/incidencias/{inc['id']}")
    assert r.status_code == 200, r.text
    assert (r.json()["descripcion"], r.json()["resolucion"], r.json()["nota_disponible"]) == (None, None, False)
    [en_lista] = [i for i in d.operacion("GET", "/incidencias").json()["incidencias"] if i["id"] == inc["id"]]
    assert en_lista["nota_disponible"] is False
    copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{persona}/datos", familia.admin, familia)
    assert copia.status_code == 404
    assert nota not in copia.text

    # Seguir trabajando la incidencia: resolverla con una resolución nueva, con la clave nueva
    version = r.headers["etag"]
    r = d.operacion("PATCH", f"/incidencias/{inc['id']}", {"estado": "resuelta", "resolucion": "Cerrada"},
                    **{"If-Match": version})
    assert r.status_code == 200 and r.json()["estado"] == "resuelta"
    # La nota de antes sigue ilegible, así que la incidencia sigue como no disponible
    assert r.json()["nota_disponible"] is False
    # Una nota nueva va con una clave nueva y se lee
    otra = d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": "otro", "descripcion": "Nueva"})
    assert otra.status_code == 201 and otra.json()["descripcion"] == "Nueva"
    assert d.sql("SELECT count(*) FROM clave_notas WHERE persona_cuidada_id = %s", persona) == [(2,)]
    assert nota not in d.e.iam.texto_log()


@pytest.mark.rf("Ley-21.719")
def test_destruir_la_clave_de_la_ficha_no_destruye_la_nota(despacho: Despacho) -> None:
    """Decisión de Jorge del 17-11: a los 90 días del retiro se destruye la clave de la ficha, pero la persona sigue en
    MATU y su pedido se guarda 2 años: la nota sigue legible en la consola y en la copia de sus datos. Falla con el
    disparador clave_datos_destruye_notas de antes."""
    d = despacho
    familia, pedido = d.pagado()
    nota = f"Nota sintética {uuid.uuid4().hex}"
    inc = _incidencia_con_resolucion(d, pedido, nota)
    persona = familia.persona.id
    [(clave,)] = d.sql("SELECT id FROM clave_notas WHERE persona_cuidada_id = %s AND destruida_en IS NULL", persona)
    _destruir_clave_de_la_ficha(d, familia)
    assert d.sql("SELECT count(*) FROM clave_datos WHERE persona_cuidada_id = %s AND destruida_en IS NULL",
                 persona) == [(0,)]
    assert d.sql("SELECT destruida_en IS NULL FROM clave_notas WHERE id = %s", clave) == [(True,)]

    r = d.operacion("GET", f"/incidencias/{inc['id']}")
    assert r.status_code == 200, r.text
    assert (r.json()["descripcion"], r.json()["resolucion"], r.json()["nota_disponible"]) == (
        nota, "Resolución sintética", True)
    copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{persona}/datos", familia.admin, familia)
    assert copia.status_code == 200, copia.text
    [p] = [x for x in copia.json()["pedidos"] if x["referencia"] == inc["referencia"]]
    [paso] = p["lo_que_paso"]
    assert (paso["nota"], paso["resolucion"], paso["nota_disponible"]) == (nota, "Resolución sintética", True)
    # Una nota nueva va con la misma clave
    otra = d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": "otro", "descripcion": "Nueva"})
    assert otra.status_code == 201
    assert d.sql("SELECT clave_notas_id FROM incidencia WHERE id = %s", uuid.UUID(otra.json()["id"])) == [(clave,)]
    assert nota not in d.e.iam.texto_log()


@contextmanager
def _con_custodia(d: Despacho, custodia: CustodiaNotas | None) -> Iterator[None]:
    """La custodia de las notas cambiada solo dentro del bloque: None (sin la KEK) u otra KEK."""
    app = d.e.iam.cliente.app
    assert isinstance(app, FastAPI)
    sobreescritas = app.dependency_overrides
    antes = sobreescritas[obtener_custodia_notas]
    sobreescritas[obtener_custodia_notas] = lambda: custodia
    try:
        yield
    finally:
        sobreescritas[obtener_custodia_notas] = antes


def _problema_503(r: Any, detalle: str) -> None:
    assert r.status_code == 503, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert (r.json()["status"], r.json()["detail"]) == (503, detalle)


DETALLE_CONSOLA = "Las notas no están disponibles en este momento"
DETALLE_COPIA = "Los datos no están disponibles en este momento. Cita el request_id si lo reportas"


@pytest.mark.rf("Ley-21.719")
@pytest.mark.parametrize("sin", ["kek", "otra_kek"])
def test_sin_la_kek_la_consola_y_la_copia_fallan_cerradas_con_503(despacho: Despacho, sin: str) -> None:
    """Decisión de Jorge del 17-11: sin la KEK de las notas, o con una que no abre la clave vigente, la copia de los
    datos responde 503 como la consola, con mensaje fijo y RFC 7807: nunca muestra como no disponible
    (``nota_disponible: false``) una nota que existe. Con la KEK de vuelta, la nota se lee."""
    d = despacho
    familia, pedido = d.pagado()
    nota = f"Nota sintética {uuid.uuid4().hex}"
    inc = _incidencia_con_resolucion(d, pedido, nota)
    persona = familia.persona.id
    ruta_copia = f"/v1/personas-cuidadas/{persona}/datos"
    custodia = None if sin == "kek" else CustodiaNotas(secrets.token_bytes(32), 1)
    with _con_custodia(d, custodia):
        for ruta in (f"/incidencias/{inc['id']}", "/incidencias"):
            _problema_503(d.operacion("GET", ruta), DETALLE_CONSOLA)
        copia = d.e.pedir("GET", ruta_copia, familia.admin, familia)
        _problema_503(copia, DETALLE_COPIA)
        assert nota not in copia.text and "nota_disponible" not in copia.text
        assert copia.headers["cache-control"] == "no-store"
    # La copia fallida no se registró (la transacción se revierte entera, C19)
    assert d.sql("SELECT count(*) FROM auditoria WHERE accion = 'persona.datos_descargar'"
                 " AND persona_cuidada_id = %s", persona) == [(0,)]
    copia = d.e.pedir("GET", ruta_copia, familia.admin, familia)
    assert copia.status_code == 200, copia.text
    [p] = [x for x in copia.json()["pedidos"] if x["referencia"] == inc["referencia"]]
    assert [(x["nota"], x["nota_disponible"]) for x in p["lo_que_paso"]] == [(nota, True)]
    assert nota not in d.e.iam.texto_log()


@pytest.mark.rf("Ley-21.719")
def test_sin_la_kek_la_copia_sin_notas_se_entrega(despacho: Despacho) -> None:
    """Sin notas de operación no hay nada que abrir: sin la KEK de las notas, la copia se entrega igual."""
    d = despacho
    familia, pedido = d.pagado()
    with _con_custodia(d, None):
        copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)
    assert copia.status_code == 200, copia.text
    [(referencia,)] = d.sql("SELECT referencia FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))
    [p] = [x for x in copia.json()["pedidos"] if x["referencia"] == referencia]
    assert p["lo_que_paso"] == []


def test_una_incidencia_solo_va_sobre_un_pedido_pagado(despacho: Despacho) -> None:
    from tests.modules.payments.conftest import pedido_confirmado

    d = despacho
    _, pedido = pedido_confirmado(d.e)
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": "otro", "descripcion": "x"})
    assert r.status_code == 404


def test_el_catalogo_se_edita_solo_en_los_comercios_ficticios_y_no_cambia_lo_confirmado(despacho: Despacho) -> None:
    from tests.modules.payments.conftest import pagar, pedido_confirmado

    d = despacho
    catalogo = d.operacion("GET", "/catalogo")
    assert catalogo.status_code == 200
    oferta_id = d.e.oferta("panal", "uno")
    [oferta] = [o for o in catalogo.json()["ofertas"] if o["id"] == oferta_id]
    d.sql("UPDATE comercio SET ficticio = true WHERE id = (SELECT comercio_id FROM oferta WHERE id = %s)",
          uuid.UUID(oferta_id))
    oferta = next(o for o in d.operacion("GET", "/catalogo").json()["ofertas"] if o["id"] == oferta_id)
    assert oferta["editable"] is True
    # C3: un total confirmado no cambia con el precio nuevo
    familia, pedido = pedido_confirmado(d.e)
    total = d.sql("SELECT total FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))[0][0]
    ruta = f"/ofertas/{oferta_id}"
    assert d.operacion("PATCH", ruta, {"precio": 15990}).status_code == 428
    assert d.operacion("PATCH", ruta, {"precio": 15990}, **{"If-Match": '"o1"'}).status_code == 412
    assert d.operacion("PATCH", ruta, {"precio": 0}, **{"If-Match": oferta["version"]}).status_code == 422
    r = d.operacion("PATCH", ruta, {"precio": 15990}, **{"If-Match": oferta["version"]})
    assert r.status_code == 200, r.text
    assert r.json()["precio"] == 15990 and r.headers["etag"] != oferta["version"]
    assert d.sql("SELECT total FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))[0][0] == total
    assert d.sql("SELECT precio_unitario FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))[0][0] == (
        PRECIO_PANAL)
    assert pagar(d.e, familia, pedido).status_code in (200, 201)
    assert d.sql("SELECT t.monto FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id"
                 " WHERE c.pedido_id = %s AND t.tipo = 'venta'", uuid.UUID(pedido["id"])) == [(total,)]
    assert d.sql("SELECT count(*) FROM auditoria WHERE accion = 'catalogo.oferta_cambiar' AND entidad_id = %s"
                 " AND grupo_id IS NULL", uuid.UUID(oferta_id)) == [(1,)]
    # D-81-7: un comercio real no se edita, ni por la API ni en la base
    d.sql("UPDATE comercio SET ficticio = false WHERE id = (SELECT comercio_id FROM oferta WHERE id = %s)",
          uuid.UUID(oferta_id))
    version = r.headers["etag"]
    r = d.operacion("PATCH", ruta, {"stock": 3}, **{"If-Match": version})
    assert r.status_code == 409 and r.json()["type"] == "/errores/comercio-real"
    d.sql("UPDATE oferta SET precio = %s WHERE id = %s", PRECIO_PANAL, uuid.UUID(oferta_id))


@pytest.mark.rf("R3")
def test_el_retracto_trae_sus_productos_y_el_rechazo_exige_motivo(despacho: Despacho) -> None:
    d = despacho
    familia, pedido, _ = _entregado(d)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                       {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 201, r.text
    retracto = r.json()["id"]
    vista = d.operacion("GET", f"/retractos/{retracto}").json()
    assert vista["referencia"] and [(x["cantidad"], x["monto"]) for x in vista["lineas"]] == [(1, PRECIO_PANAL)]
    assert retracto in [x["id"] for x in d.operacion("GET", "/retractos").json()["retractos"]]
    ruta = f"/retractos/{retracto}/resolver"
    assert d.operacion("POST", ruta, {"decision": "rechazar"}).status_code == 422
    assert d.operacion("POST", ruta, {"decision": "devolver", "motivo": "sello_abierto"}).status_code == 422
    r = d.operacion("POST", ruta, {"decision": "rechazar", "motivo": "producto_no_recibido"})
    assert r.status_code == 200 and r.json()["motivo_rechazo"] == "producto_no_recibido"
    assert r.json()["resuelto_en"] is not None
    assert d.operacion("GET", f"/retractos/{uuid.uuid4()}").status_code == 404


@pytest.mark.rf("R3")
def test_la_lista_de_retractos_filtra_por_estado_y_por_omision_trae_los_por_resolver(despacho: Despacho) -> None:
    """MATU-81: los chips «Por resolver» (solicitado), «Devueltos» y «Sin devolución» (rechazado)."""
    d = despacho
    familia, pedido, _ = _entregado(d)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                       {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 201, r.text
    retracto = r.json()["id"]

    def ids(consulta: str) -> list[str]:
        respuesta = d.operacion("GET", f"/retractos{consulta}")
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.headers["cache-control"] == "no-store" and respuesta.json()["hay_mas"] is False
        return [x["id"] for x in respuesta.json()["retractos"]]

    assert retracto in ids("") and retracto in ids("?estado=solicitado")
    assert retracto not in ids("?estado=rechazado") and retracto not in ids("?estado=devuelto")
    r = d.operacion("POST", f"/retractos/{retracto}/resolver", {"decision": "rechazar", "motivo": "sello_abierto"})
    assert r.status_code == 200, r.text
    assert retracto not in ids("") and retracto not in ids("?estado=devuelto")
    assert retracto in ids("?estado=rechazado") and retracto in ids("?estado=solicitado&estado=rechazado")
    [vista] = [x for x in d.operacion("GET", "/retractos?estado=rechazado").json()["retractos"] if x["id"] == retracto]
    assert vista["estado"] == "rechazado" and vista["motivo_rechazo"] == "sello_abierto" and vista["resuelto_en"]
    # Un estado que no es del retracto: 422, con el campo
    r = d.operacion("GET", "/retractos?estado=vencido")
    assert r.status_code == 422 and r.json()["errores"][0]["campo"] == "estado"


@pytest.mark.rf("R3")
@pytest.mark.rf("Ley-21.719")
def test_c24_la_familia_ve_el_motivo_del_rechazo(despacho: Despacho) -> None:
    """MATU-81 (C24): RetractoVistaFamilia trae motivo_rechazo, null hasta que se rechaza."""
    d = despacho
    familia, pedido, _ = _entregado(d)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                       {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 201 and r.json()["motivo_rechazo"] is None
    retracto = r.json()["id"]
    ruta_familia = f"/v1/pedidos/{pedido['id']}/retractos"
    [antes] = d.e.pedir("GET", ruta_familia, familia.admin, familia).json()["retractos"]
    assert antes["estado"] == "solicitado" and antes["motivo_rechazo"] is None
    d.operacion("POST", f"/retractos/{retracto}/resolver", {"decision": "rechazar", "motivo": "producto_no_recibido"})
    [despues] = d.e.pedir("GET", ruta_familia, familia.admin, familia).json()["retractos"]
    assert despues["estado"] == "rechazado" and despues["motivo_rechazo"] == "producto_no_recibido"
    assert despues["resuelto_en"] is not None


@pytest.mark.rf("RF-37")
@pytest.mark.rf("Ley-21.719")
def test_h2_la_copia_de_los_datos_trae_el_motivo_del_rechazo_en_las_dos_copias(despacho: Despacho) -> None:
    """MATU-81 (H2 del analista): «Datos de» y «Tus datos» traen por qué no se aceptó el retracto; null mientras
    está por resolver."""
    d = despacho
    familia, pedido, _ = _entregado(d)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                       {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 201, r.text
    retracto = r.json()["id"]

    def copias() -> tuple[list[Any], list[Any]]:
        persona = d.e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)
        assert persona.status_code == 200, persona.text
        [p] = persona.json()["pedidos"]
        cuenta = d.como(familia.admin, "GET", "/v1/yo/datos")
        assert cuenta.status_code == 200, cuenta.text
        return ([(x["estado"], x["motivo_rechazo"]) for x in p["retractos"]],
                [(x["estado"], x["motivo_rechazo"]) for x in cuenta.json()["retractos"]])

    assert copias() == ([("solicitado", None)], [("solicitado", None)])
    r = d.operacion("POST", f"/retractos/{retracto}/resolver", {"decision": "rechazar", "motivo": "sello_abierto"})
    assert r.status_code == 200, r.text
    assert copias() == ([("rechazado", "sello_abierto")], [("rechazado", "sello_abierto")])


@pytest.mark.rf("R3")
def test_las_anulaciones_pendientes_dicen_si_estan_en_curso_o_sin_terminar(despacho: Despacho) -> None:
    """MATU-81: AnulacionPendiente.estado distingue «En curso» (iniciada o autorizando) de «Sin terminar» (error)."""
    d = despacho
    familia, pedido, _ = _entregado(d)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                       {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 201, r.text
    d.pasarela.caida = True
    try:
        r = d.operacion("POST", f"/retractos/{r.json()['id']}/resolver", {"decision": "devolver"})
        assert r.status_code == 200, r.text
    finally:
        d.pasarela.caida = False
    [(anulacion,)] = d.sql("SELECT t.id FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id"
                           " WHERE c.pedido_id = %s AND t.tipo = 'anulacion'", uuid.UUID(pedido["id"]))

    def del_pedido() -> list[dict[str, Any]]:
        respuesta = d.operacion("GET", "/cobros/pendientes")
        assert respuesta.status_code == 200, respuesta.text
        return [a for a in respuesta.json()["anulaciones_sin_terminar"] if a["pedido_id"] == pedido["id"]]

    [sin_terminar] = del_pedido()
    assert sin_terminar["estado"] == "sin_terminar" and sin_terminar["intentos"] == 1
    d.sql("UPDATE transaccion_pasarela SET estado = 'iniciada' WHERE id = %s", anulacion)
    [en_curso] = del_pedido()
    assert en_curso["estado"] == "en_curso"
    # Que no quede pendiente para otras pruebas
    d.sql("UPDATE transaccion_pasarela SET estado = 'rechazada' WHERE id = %s", anulacion)
    assert del_pedido() == []


@pytest.mark.rf("R3")
def test_d_81_9_el_retracto_por_correo_va_a_nombre_del_admin_de_ese_correo(despacho: Despacho) -> None:
    d = despacho
    familia, pedido, _ = _entregado(d)
    d.operacion("POST", f"/pedidos/{pedido['id']}/entregado")
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    lineas = [{"linea_id": str(linea[0]), "cantidad": 1}]
    ajeno = f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl"
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/retractos", {"lineas": lineas, "correo_solicitante": ajeno})
    assert r.status_code == 422 and ajeno not in r.text and ajeno not in d.e.iam.texto_log()
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/retractos",
                    {"lineas": lineas, "correo_solicitante": familia.admin.email.upper()})
    assert r.status_code == 201, r.text
    assert d.sql("SELECT solicitado_por FROM retracto WHERE id = %s", uuid.UUID(r.json()["id"])) == [
        (familia.admin.id,)]
    assert familia.admin.email not in d.e.iam.texto_log()


def test_c34_ninguna_ruta_de_operacion_lee_la_persona_ni_su_direccion(despacho: Despacho) -> None:
    d = despacho
    familia, pedido, _ = _entregado(d, faltan=1)
    d.operacion("POST", f"/pedidos/{pedido['id']}/entregado")
    d.token_operador()
    capturadas: list[str] = []

    def escuchar(_cx: Any, _cursor: Any, sentencia: str, *_: Any) -> None:
        capturadas.append(sentencia)

    event.listen(Engine, "before_cursor_execute", escuchar)
    try:
        referencia = d.sql("SELECT referencia FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))[0][0]
        rutas: list[tuple[str, str, Any]] = [
            ("GET", "/pedidos?grupo=todos", None), ("POST", "/pedidos/buscar", {"referencia": referencia}),
            ("GET", f"/pedidos/{pedido['id']}", None), ("GET", f"/pedidos/{pedido['id']}/cobro", None),
            ("GET", "/cobros/pendientes", None), ("GET", "/retractos", None), ("GET", "/incidencias", None),
            ("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": "otro", "descripcion": "Revisión sintética"}),
            ("GET", "/catalogo", None),
        ]
        capturadas.clear()
        for metodo, ruta, cuerpo in rutas:
            r = d.operacion(metodo, ruta, cuerpo)
            assert r.status_code in (200, 201), (ruta, r.text)
    finally:
        event.remove(Engine, "before_cursor_execute", escuchar)
    leidas = [s for s in capturadas if TABLAS_PROHIBIDAS.search(s)]
    assert capturadas and leidas == []
    assert str(familia.persona.id) not in d.e.iam.texto_log()


@pytest.mark.rf("RF-37")
def test_c30_operacion_exige_la_marca_del_segundo_factor_y_12_horas(despacho: Despacho) -> None:
    """Un token de una cuenta de operación sin el claim mfa, o con uno de más de 12 horas: 401 mfa-requerido. Una
    cuenta que no es de operación, aunque traiga la marca: 404."""
    from datetime import timedelta

    from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT

    d = despacho
    assert d.operador is not None
    emisor = EmisorJWT(d.e.iam.clave_jwt)
    ahora = d.e.iam.reloj.ahora()

    def con(token: str) -> Any:
        return d.e.iam.cliente.get("/v1/operacion/pedidos", headers={"Authorization": f"Bearer {token}"})

    sin_marca = con(emisor.emitir(d.operador.id, ahora, ahora + timedelta(minutes=15)))
    assert sin_marca.status_code == 401 and sin_marca.json()["type"] == "/errores/mfa-requerido"
    vieja = con(emisor.emitir(d.operador.id, ahora, ahora + timedelta(minutes=15), None, ahora - timedelta(hours=12)))
    assert vieja.status_code == 401 and vieja.json()["type"] == "/errores/mfa-requerido"
    assert con(emisor.emitir(d.operador.id, ahora, ahora + timedelta(minutes=15), None, ahora)).status_code == 200
    familia, _ = d.pagado()
    ajena = con(emisor.emitir(familia.admin.id, ahora, ahora + timedelta(minutes=15), None, ahora))
    assert ajena.status_code == 404
