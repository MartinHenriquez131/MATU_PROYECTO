"""MATU-114 · El retracto por correo sin que operación lea las membresías (C8 a C11, J1 y J2), contra PostgreSQL.

- C8 y C9: a nombre de quién va lo decide operacion_solicitante_retracto (migración 0031). El 422 solicitante-invalido
  es el mismo cuerpo en los cuatro casos (huella sin cuenta, cuenta de otro grupo, no admin, admin retirado) y con los
  dos campos.
- C11 (J1): 5 correos que no calzan por hora y por cuenta de operación; el sexto intento responde 429 sin buscar el
  correo, aunque sea válido. Sin Redis o sin PEPPER_LIMITES, 503 sin consultar. La clave del límite es la huella de la
  cuenta: ni el correo ni su huella llegan a Redis.
- J2: cada intento fallido queda en la auditoría como operacion.retracto_correo_fallido, con el grupo y la persona del
  pedido y sin el correo.
"""

import uuid
from typing import Any

import pytest

from app.core.limite_ip import obtener_pepper_limites
from app.modules.backoffice.api.router_operacion import DETALLE_SOLICITANTE, LIMITE_CORREO_RETRACTO
from app.shared.limite_ip import huella
from tests.base_datos import requiere_base
from tests.modules.backoffice.conftest import Despacho
from tests.modules.backoffice.test_consola_api import _entregado

pytestmark = [pytest.mark.rf("R3"), pytest.mark.rf("Ley-21.719"), requiere_base]

ACCION = "operacion.retracto_correo_fallido"


def _listo_para_retracto(d: Despacho) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
    familia, pedido, _ = _entregado(d)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    return familia, pedido, [{"linea_id": str(linea[0]), "cantidad": 1}]


def _por_correo(d: Despacho, pedido: dict[str, Any], lineas: list[dict[str, Any]], correo: str) -> Any:
    return d.operacion("POST", f"/pedidos/{pedido['id']}/retractos", {"lineas": lineas, "correo_solicitante": correo})


def _sin_request_id(cuerpo: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cuerpo.items() if k != "request_id"}


def _fallidos(d: Despacho, pedido_id: str) -> list[tuple[Any, ...]]:
    return d.sql("SELECT actor_tipo, actor_ref, grupo_id, persona_cuidada_id, entidad, detalle FROM auditoria"
                 " WHERE accion = %s AND entidad_id = %s ORDER BY ocurrido_en, id", ACCION, uuid.UUID(pedido_id))


def test_c9_el_mismo_422_en_los_cuatro_casos_y_cada_uno_se_audita_sin_el_correo(despacho: Despacho) -> None:
    d = despacho
    familia, pedido, lineas = _listo_para_retracto(d)
    # El admin activo del grupo puede (antes de los intentos fallidos, que llegan al tope)
    r = _por_correo(d, pedido, lineas, familia.admin.email)
    assert r.status_code == 201, r.text
    assert d.sql("SELECT solicitado_por FROM retracto WHERE id = %s", uuid.UUID(r.json()["id"])) == [
        (familia.admin.id,)]
    otra = d.e.fabrica.familia()
    no_admin = familia.miembros["cuidador"].usuario
    retirado = d.e.fabrica.miembro(familia.grupo, "admin")
    d.sql("UPDATE membresia SET estado = 'retirada', retirado_en = now() WHERE id = %s", retirado.membresia.id)
    correos = [f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl", otra.admin.email, no_admin.email, retirado.usuario.email]
    cuerpos = []
    for correo in correos:
        r = _por_correo(d, pedido, lineas, correo)
        assert r.status_code == 422, r.text
        assert correo not in r.text and correo.lower() not in d.e.iam.texto_log().lower()
        cuerpos.append(_sin_request_id(r.json()))
    # Con los dos campos, también. N1: sin contar el intento ni auditarlo, aunque el correo sea del admin
    contador = d.e.iam.limite_ip
    assert contador is not None
    antes = dict(contador.datos)
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/retractos",
                    {"lineas": lineas, "correo_solicitante": familia.admin.email, "solicitado_por": str(otra.admin.id)})
    assert r.status_code == 422
    cuerpos.append(_sin_request_id(r.json()))
    assert contador.datos == antes
    assert all(c == cuerpos[0] for c in cuerpos), cuerpos
    assert cuerpos[0]["type"].endswith("solicitante-invalido") and cuerpos[0]["detail"] == DETALLE_SOLICITANTE
    assert "errores" not in cuerpos[0] or not cuerpos[0]["errores"]
    # J2: cada correo que no calzó (los cuatro) con el grupo y la persona del pedido, sin el correo ni su huella
    filas = _fallidos(d, pedido["id"])
    assert len(filas) == 4
    assert {f[:5] for f in filas} == {("operacion", d.operador.id, familia.grupo.id, familia.persona.id,  # type: ignore[union-attr]
                                       "pedido")}
    assert all(f[5] is None for f in filas)
    # Un solicitado_por que no es quien pagó ni admin: el mismo 422, sin auditar (no es un correo)
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/retractos",
                    {"lineas": lineas, "solicitado_por": str(no_admin.id)})
    assert r.status_code == 422 and _sin_request_id(r.json()) == cuerpos[0]
    assert len(_fallidos(d, pedido["id"])) == 4
    # J2: la familia lo ve en el historial de «Datos de» la persona, con la referencia del pedido y sin el correo ni
    # quién del equipo
    copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)
    assert copia.status_code == 200, copia.text
    [referencia] = d.sql("SELECT referencia FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))[0]
    hechos = [h for h in copia.json()["historial"]["hechos"] if h["tipo"] == "matu_intento_un_retracto_por_correo"]
    assert len(hechos) == 4
    assert all(h["referencia"] == referencia and h["quien"] == {"tipo": "matu", "nombre": None, "activo": None}
               for h in hechos)
    for correo in correos:
        assert correo not in copia.text and correo.lower() not in copia.text.lower()
    assert str(d.operador.id) not in copia.text  # type: ignore[union-attr]


def test_c8_sin_correo_va_a_nombre_de_quien_pago(despacho: Despacho) -> None:
    d = despacho
    familia, pedido, lineas = _listo_para_retracto(d)
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/retractos", {"lineas": lineas})
    assert r.status_code == 201, r.text
    assert d.sql("SELECT solicitado_por FROM retracto WHERE id = %s", uuid.UUID(r.json()["id"])) == [
        (familia.admin.id,)]
    assert "solicitado_por" not in r.json()


def test_c11_al_sexto_intento_429_sin_buscar_el_correo_aunque_sea_valido(despacho: Despacho) -> None:
    d = despacho
    familia, pedido, lineas = _listo_para_retracto(d)
    for _ in range(LIMITE_CORREO_RETRACTO.maximo):
        assert _por_correo(d, pedido, lineas, f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl").status_code == 422
    r = _por_correo(d, pedido, lineas, familia.admin.email)
    assert r.status_code == 429, r.text
    cuerpo = r.json()
    assert cuerpo["type"].endswith("demasiados-intentos") and 1 <= int(r.headers["retry-after"]) <= 3600
    assert familia.admin.email not in r.text and "admin" not in cuerpo["detail"].lower()
    # Un correo inválido en el sexto intento recibe la misma respuesta: no dice si el último era válido
    otro = _por_correo(d, pedido, lineas, f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl")
    assert otro.status_code == 429 and _sin_request_id(otro.json()) == _sin_request_id(cuerpo)
    # El 429 no se audita ni crea el retracto
    assert len(_fallidos(d, pedido["id"])) == LIMITE_CORREO_RETRACTO.maximo
    assert d.sql("SELECT count(*) FROM retracto WHERE pedido_id = %s", uuid.UUID(pedido["id"])) == [(0,)]
    # Sin correo (a nombre de quien pagó), el límite no aplica
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/retractos", {"lineas": lineas}).status_code == 201


def test_c11_la_clave_del_limite_es_la_huella_de_la_cuenta_y_la_ventana_se_abre_en_una_hora(
    despacho: Despacho,
) -> None:
    d = despacho
    familia, pedido, lineas = _listo_para_retracto(d)
    correo = f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl"
    assert _por_correo(d, pedido, lineas, correo).status_code == 422
    contador = d.e.iam.limite_ip
    assert contador is not None
    [clave] = [c for c in contador.datos if f":{LIMITE_CORREO_RETRACTO.prefijo}:" in c]
    pepper = d.e.iam.cliente.app.dependency_overrides[obtener_pepper_limites]()  # type: ignore[attr-defined]
    assert clave.endswith(huella(pepper, LIMITE_CORREO_RETRACTO.prefijo, str(d.operador.id)))  # type: ignore[union-attr]
    assert correo not in clave and str(d.operador.id) not in clave  # type: ignore[union-attr]
    for _ in range(LIMITE_CORREO_RETRACTO.maximo - 1):
        _por_correo(d, pedido, lineas, correo)
    assert _por_correo(d, pedido, lineas, familia.admin.email).status_code == 429
    d.e.avanzar(LIMITE_CORREO_RETRACTO.ventana)
    assert _por_correo(d, pedido, lineas, familia.admin.email).status_code == 201


@pytest.mark.parametrize("falta", ["redis", "pepper"])
def test_c11_sin_redis_o_sin_pepper_503_sin_consultar(despacho: Despacho, falta: str) -> None:
    d = despacho
    familia, pedido, lineas = _listo_para_retracto(d)
    d.token_operador()
    contador = d.e.iam.limite_ip
    assert contador is not None
    app: Any = d.e.iam.cliente.app
    anterior = app.dependency_overrides[obtener_pepper_limites]
    if falta == "redis":
        contador.caido = True
    else:
        app.dependency_overrides[obtener_pepper_limites] = lambda: None
    try:
        r = _por_correo(d, pedido, lineas, familia.admin.email)
    finally:
        contador.caido = False
        app.dependency_overrides[obtener_pepper_limites] = anterior
    assert r.status_code == 503, r.text
    assert familia.admin.email not in r.text
    assert d.sql("SELECT count(*) FROM retracto WHERE pedido_id = %s", uuid.UUID(pedido["id"])) == [(0,)]
    assert _fallidos(d, pedido["id"]) == []


def test_c11_el_correo_que_calza_no_gasta_un_intento(despacho: Despacho) -> None:
    """La reserva de un correo válido se devuelve: 4 que no calzan, uno que sí y otro que no siguen dentro del límite;
    el siguiente ya pasa de 5."""
    d = despacho
    familia, pedido, lineas = _listo_para_retracto(d)
    for _ in range(LIMITE_CORREO_RETRACTO.maximo - 1):
        assert _por_correo(d, pedido, lineas, f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl").status_code == 422
    assert _por_correo(d, pedido, lineas, familia.admin.email).status_code == 201
    assert _por_correo(d, pedido, lineas, f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl").status_code == 422
    assert _por_correo(d, pedido, lineas, familia.admin.email).status_code == 429
    assert len(_fallidos(d, pedido["id"])) == LIMITE_CORREO_RETRACTO.maximo
