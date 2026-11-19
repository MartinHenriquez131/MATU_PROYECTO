"""MATU-128 · «Lo que pasó con tu pedido» para quien lo pagó, contra PostgreSQL: GET
/v1/pedidos/{pedido_id}/lo-que-paso (C5, R2, R3, E4 y E5) y el filtro de correos y teléfonos de
la consola (R5, C9). Solo datos sintéticos.
"""

import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI

from app.shared.notas_operacion import CustodiaNotas, obtener_custodia_notas
from tests.base_datos import requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.backoffice.conftest import Despacho
from tests.modules.backoffice.test_tus_pedidos_api import _otro_pagado, _pagado_por_el_pagador, _rol

pytestmark = [pytest.mark.rf("RF-20"), pytest.mark.rf("Ley-21.719"), requiere_base]

NOTA = "Nota sintética: la farmacia no tenía una de las bolsas"
RESOLUCION = "Resolución sintética: devolvimos su precio a tu tarjeta"
CAMPOS = {"tipo", "estado", "anotado_en", "resuelto_en", "nota", "resolucion", "nota_disponible"}
DETALLE_503 = "Lo anotado no se puede revisar en este momento. Cita el request_id si lo reportas"


def _ruta(pedido: dict[str, Any]) -> str:
    return f"/v1/pedidos/{pedido['id']}/lo-que-paso"


def _pedir(d: Despacho, familia: FamiliaCreada, usuario: UsuarioCreado, pedido: dict[str, Any]) -> Any:
    return d.e.pedir("GET", _ruta(pedido), usuario, familia)


def _anotar(d: Despacho, pedido: dict[str, Any], nota: str = NOTA, tipo: str = "faltante") -> dict[str, Any]:
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": tipo, "descripcion": nota})
    assert r.status_code == 201, r.text
    return dict(r.json())


def _resolver(d: Despacho, incidencia: dict[str, Any], resolucion: str = RESOLUCION) -> None:
    r = d.operacion("PATCH", f"/incidencias/{incidencia['id']}", {"estado": "resuelta", "resolucion": resolucion},
                    **{"If-Match": f'"i{incidencia["version"]}"'})
    assert r.status_code == 200, r.text


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


def test_quien_pago_ve_lo_que_paso_aunque_pase_a_se_informa(despacho: Despacho) -> None:
    """C5 y A1/A2 por la API: el pagador que pagó el pedido recibe lo anotado y cómo se resolvió, descifrado, con los
    siete campos y sin quién lo anotó; después de pasar a «Se informa», lo mismo. Cache-Control: no-store, y el texto
    nunca va al log."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    incidencia = _anotar(d, pedido)
    _resolver(d, incidencia)
    pagador = _rol(d, familia, "pagador")
    auditadas = d.sql("SELECT count(*) FROM auditoria WHERE grupo_id = %s", familia.grupo.id)

    for rol in ("pagador", "observador"):
        d.sql("UPDATE membresia SET rol = %s WHERE usuario_id = %s AND grupo_id = %s", rol, pagador.id,
              familia.grupo.id)
        r = _pedir(d, familia, pagador, pedido)
        assert r.status_code == 200, (rol, r.text)
        assert r.headers["cache-control"] == "no-store"
        assert set(r.json()) == {"lo_que_paso"}
        [cosa] = r.json()["lo_que_paso"]
        assert set(cosa) == CAMPOS
        assert (cosa["tipo"], cosa["estado"], cosa["nota"], cosa["resolucion"], cosa["nota_disponible"]) == (
            "faltante", "resuelta", NOTA, RESOLUCION, True)
        assert cosa["anotado_en"] and cosa["resuelto_en"]
        # Nunca el id de la incidencia, quién del equipo la anotó ni a quién se asignó
        assert incidencia["id"] not in r.text
        assert d.operador is not None and str(d.operador.id) not in r.text
        for nunca in ("incidencia", "incidente", "creada_por", "asignada", "version"):
            assert nunca not in r.text, nunca
    assert NOTA not in d.e.iam.texto_log() and RESOLUCION not in d.e.iam.texto_log()
    # C7: la lectura no se audita
    assert d.sql("SELECT count(*) FROM auditoria WHERE grupo_id = %s", familia.grupo.id) == auditadas


@pytest.mark.rf("RNF-07")
def test_404_a_quien_no_pago_ese_pedido_nunca_403(despacho: Despacho) -> None:
    """C5 y A3 a A6 por la API: el admin y el cuidador (que siguen viendo lo anotado en «Datos de»), quien se informa
    sin pagar, quien pagó otro pedido del grupo, otro grupo (con su X-Grupo-Id o con el de A), un id que no es UUID
    y quien pagó y salió del grupo: 404 RFC 7807, sin la nota."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    _anotar(d, pedido)
    pagador = _rol(d, familia, "pagador")
    assert _pedir(d, familia, pagador, pedido).status_code == 200

    def _es_404(r: Any, caso: str) -> None:
        assert r.status_code == 404, (caso, r.status_code, r.text)
        assert r.headers["content-type"].startswith("application/problem+json"), caso
        assert NOTA not in r.text and r.headers["cache-control"] == "no-store", caso

    for rol in ("admin", "cuidador", "observador"):
        _es_404(_pedir(d, familia, _rol(d, familia, rol), pedido), rol)
    # El admin lo sigue viendo en la copia de los datos de la persona («Datos de»)
    copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)
    assert copia.status_code == 200 and NOTA in copia.text
    # A3: otro pedido del grupo, que pagó el admin
    d.e.avanzar(timedelta(minutes=1))
    ajeno = _otro_pagado(d, familia)
    _anotar(d, ajeno)
    _es_404(_pedir(d, familia, pagador, ajeno), "otro pedido")
    assert _pedir(d, familia, familia.admin, ajeno).status_code == 200
    # A5: otro grupo, con su X-Grupo-Id o con el de A (del que no es miembro)
    otra = d.e.fabrica.familia()
    _es_404(d.e.pedir("GET", _ruta(pedido), otra.admin, otra), "otro grupo, su cabecera")
    _es_404(d.e.pedir("GET", _ruta(pedido), otra.admin, familia), "otro grupo, la cabecera de A")
    # Quien pagó, con el X-Grupo-Id de otro grupo: no es miembro
    _es_404(d.e.pedir("GET", _ruta(pedido), pagador, otra), "quien pagó con la cabecera de B")
    _es_404(d.e.pedir("GET", "/v1/pedidos/no-es-uuid/lo-que-paso", pagador, familia), "pedido sin UUID")
    # A6: quien pagó y salió del grupo
    d.sql("UPDATE membresia SET estado = 'retirada' WHERE usuario_id = %s AND grupo_id = %s", pagador.id,
          familia.grupo.id)
    _es_404(_pedir(d, familia, pagador, pedido), "salió del grupo")


def test_e4_sin_nada_anotado_responde_lista_vacia_aunque_falte_la_kek(despacho: Despacho) -> None:
    """E4: sin nada anotado no hay nada que abrir: 200 con la lista vacía, con la KEK y sin ella."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    pagador = _rol(d, familia, "pagador")
    for custodia in (None, CustodiaNotas(secrets.token_bytes(32), 1)):
        with _con_custodia(d, custodia):
            r = _pedir(d, familia, pagador, pedido)
        assert r.status_code == 200, r.text
        assert r.json() == {"lo_que_paso": []}
    assert _pedir(d, familia, pagador, pedido).json() == {"lo_que_paso": []}


@pytest.mark.parametrize("sin", ["kek", "otra_kek"])
def test_sin_la_kek_con_algo_anotado_responde_503_y_el_detalle_sigue(despacho: Despacho, sin: str) -> None:
    """R2 y E4: con algo que descifrar y sin la KEK (o con otra), 503 RFC 7807 con mensaje fijo, sin la nota y nunca
    como «no disponible». El detalle del pedido sigue respondiendo 200. Con la KEK de vuelta, la nota se lee."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    _anotar(d, pedido)
    pagador = _rol(d, familia, "pagador")
    custodia = None if sin == "kek" else CustodiaNotas(secrets.token_bytes(32), 1)
    with _con_custodia(d, custodia):
        r = _pedir(d, familia, pagador, pedido)
        assert r.status_code == 503, r.text
        assert r.headers["content-type"].startswith("application/problem+json")
        assert (r.json()["status"], r.json()["detail"]) == (503, DETALLE_503)
        assert NOTA not in r.text and "nota_disponible" not in r.text
        assert r.headers["cache-control"] == "no-store"
        detalle = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/seguimiento", pagador, familia)
        assert detalle.status_code == 200, detalle.text
    [cosa] = _pedir(d, familia, pagador, pedido).json()["lo_que_paso"]
    assert (cosa["nota"], cosa["nota_disponible"]) == (NOTA, True)
    assert NOTA not in d.e.iam.texto_log()


def test_e5_en_el_orden_en_que_se_anoto_y_con_la_clave_destruida_no_disponible(despacho: Despacho) -> None:
    """E5: las cosas anotadas van por anotado_en, de la más antigua a la más reciente. Con la clave de las notas
    destruida (el borrado criptográfico de la persona, decisión 471), la nota y la resolución vienen null y
    nota_disponible en false, sin error."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    primera = _anotar(d, pedido, "Primera nota sintética", "faltante")
    _resolver(d, primera)
    d.e.avanzar(timedelta(minutes=5))
    _anotar(d, pedido, "Segunda nota sintética", "entrega_fallida")
    pagador = _rol(d, familia, "pagador")
    cosas = _pedir(d, familia, pagador, pedido).json()["lo_que_paso"]
    assert [(x["tipo"], x["estado"], x["nota"]) for x in cosas] == [
        ("faltante", "resuelta", "Primera nota sintética"), ("entrega_fallida", "abierta", "Segunda nota sintética")]
    assert cosas[0]["anotado_en"] < cosas[1]["anotado_en"]
    assert cosas[1]["resuelto_en"] is None and cosas[1]["resolucion"] is None

    d.sql("UPDATE clave_notas SET dek_cifrada_con_kek = NULL, destruida_en = now() WHERE persona_cuidada_id = %s"
          " AND destruida_en IS NULL", familia.persona.id)
    r = _pedir(d, familia, pagador, pedido)
    assert r.status_code == 200, r.text
    assert [(x["nota"], x["resolucion"], x["nota_disponible"]) for x in r.json()["lo_que_paso"]] == [
        (None, None, False), (None, None, False)]
    assert "Primera nota" not in r.text


@pytest.mark.parametrize("texto", [
    "Escribir a contacto.familia@correo.ejemplo para coordinar",
    "Llamar al +56 9 1234 5678 antes de entregar",
    "La vecina dejó su número 9 8765 4321",
    "Fijo de la farmacia: (2) 2345 6789",
])
def test_r5_la_nota_con_forma_de_correo_o_telefono_responde_422_y_no_se_guarda(despacho: Despacho, texto: str) -> None:
    """R5 (C9): la consola rechaza una nota o una resolución con forma de correo o de teléfono chileno, con 422
    nota-con-contacto y un mensaje fijo que no repite el texto, sin guardar nada. El texto no va al log."""
    d = despacho
    _, pedido = d.pagado()
    antes = d.sql("SELECT count(*) FROM incidencia WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/incidencias", {"tipo": "otro", "descripcion": texto})
    assert r.status_code == 422, r.text
    assert r.json()["type"] == "/errores/nota-con-contacto"
    assert r.json()["detail"] == "La nota no puede llevar correos ni teléfonos"
    assert [e["campo"] for e in r.json()["errores"]] == ["descripcion"]
    assert texto not in r.text
    assert d.sql("SELECT count(*) FROM incidencia WHERE pedido_id = %s", uuid.UUID(pedido["id"])) == antes
    # La resolución, igual: la incidencia no cambia
    incidencia = _anotar(d, pedido, "Nota sintética sin datos de contacto")
    r = d.operacion("PATCH", f"/incidencias/{incidencia['id']}", {"estado": "resuelta", "resolucion": texto},
                    **{"If-Match": f'"i{incidencia["version"]}"'})
    assert r.status_code == 422, r.text
    assert r.json()["type"] == "/errores/nota-con-contacto" and texto not in r.text
    assert [e["campo"] for e in r.json()["errores"]] == ["resolucion"]
    assert d.sql("SELECT estado, version FROM incidencia WHERE id = %s", uuid.UUID(incidencia["id"])) == [
        ("abierta", 1)]
    assert texto not in d.e.iam.texto_log()


def test_r5_montos_fechas_y_cantidades_si_se_anotan(despacho: Despacho) -> None:
    """R5 sin falsos positivos en lo de todos los días: un monto con puntos, una fecha, la referencia y cantidades."""
    d = despacho
    _, pedido = d.pagado()
    nota = "Faltaron 2 de 10 unidades el 19/11/2026; se devolvieron $25.980 del pedido 4790 a las 14:30"
    assert _anotar(d, pedido, nota)["descripcion"] == nota
