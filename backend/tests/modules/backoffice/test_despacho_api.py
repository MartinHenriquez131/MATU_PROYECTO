"""MATU-63 · El despacho de punta a punta contra PostgreSQL: el comercio prepara su parte, operación genera el código,
el comercio lo valida, operación entrega, y la familia se retracta; con los caminos de error del código (no es, usado,
vencido, bloqueado), la parte de otro comercio (404), la cancelación después de pagar (R15) y el faltante que se
devuelve el mismo día (D-63-8). Logs sin el código, el token ni el PIN.
"""

import re
import uuid
from datetime import timedelta
from typing import Any

import pytest

from app.modules.fulfillment.domain.despacho import VIDA_CODIGO
from tests.base_datos import requiere_base
from tests.modules.backoffice.conftest import Despacho
from tests.modules.ordering.conftest import COSTO_ENVIO

pytestmark = [pytest.mark.rf("RF-26"), requiere_base]

PRECIO_PANAL = 12990


def _parte(d: Despacho, pedido: dict[str, Any], comercio: str = "uno") -> tuple[str, str]:
    parte = d.parte_de(pedido["id"])
    vista = d.comercio(comercio, "GET", f"/partes/{parte}")
    assert vista.status_code == 200, vista.text
    return parte, vista.headers["ETag"]


def _preparar_todo(d: Despacho, parte: str, etag: str, faltan: int = 0) -> dict[str, Any]:
    r = d.comercio("uno", "POST", f"/partes/{parte}/preparar", **{"If-Match": etag})
    assert r.status_code == 200, r.text
    [linea] = r.json()["lineas"]
    marca = {"estado": "faltante", "unidades_faltantes": faltan} if faltan else {"estado": "preparada"}
    r = d.comercio("uno", "PUT", f"/partes/{parte}/lineas/{linea['id']}", marca, **{"If-Match": r.headers["ETag"]})
    assert r.status_code == 200, r.text
    r = d.comercio("uno", "POST", f"/partes/{parte}/listo", **{"If-Match": r.headers["ETag"]})
    assert r.status_code == 200, r.text
    return r.json()


def _codigo(d: Despacho, parte: str) -> str:
    r = d.operacion("POST", f"/partes/{parte}/codigo")
    assert r.status_code == 201, r.text
    assert r.headers["cache-control"] == "no-store"
    return str(r.json()["codigo"])


def _validar(d: Despacho, parte: str, codigo: str, comercio: str = "uno") -> Any:
    return d.comercio(comercio, "POST", f"/partes/{parte}/validar-codigo", {"codigo": codigo})


def test_de_pagado_a_entregado_y_el_retracto(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    parte, etag = _parte(d, pedido)

    # La proyección del comercio (D-63-1): la referencia que se dicta, sin nada de la familia
    lista = d.comercio("uno", "GET", "/partes").json()["partes"]
    [resumen] = [p for p in lista if p["id"] == parte]
    assert re.fullmatch(r"[2-9A-HJKMNP-Z]{6}", resumen["referencia"])
    assert (resumen["estado"], resumen["estado_codigo"], resumen["numero_lineas"]) == ("enviada", "sin_codigo", 1)
    assert resumen["motivo_cancelacion"] is None
    assert d.comercio("uno", "GET", "").json()["nombre_fantasia"]

    # Preparar, marcar y «Listo»: el pedido sigue a la parte, con el comercio como actor (D-63-12)
    lista = _preparar_todo(d, parte, etag)
    assert lista["estado"] == "lista"
    assert d.estado_pedido(pedido["id"]) == "listo_retiro"
    transiciones = d.sql(
        "SELECT hacia, actor_tipo, actor_ref FROM pedido_transicion WHERE pedido_id = %s ORDER BY id",
        uuid.UUID(pedido["id"]),
    )
    comercio_uno = d.e.catalogo.comercios["uno"]
    assert [t[0] for t in transiciones][-3:] == ["enviado_a_comercio", "preparando", "listo_retiro"]
    assert transiciones[-1][1:] == ("comercio", comercio_uno)
    # Lo preparado salió del stock y nada quedó apartado (O5)
    [producto] = [p for p in d.comercio("uno", "GET", "/productos").json()["productos"]
                  if p["oferta_id"] == d.e.oferta("panal", "uno")]
    assert producto["apartado"] == 0

    # Operación genera el código y el comercio lo valida
    codigo = _codigo(d, parte)
    malo = f"{(int(codigo) + 1) % 1_000_000:06d}"
    r = _validar(d, parte, malo)
    assert (r.json()["resultado"], r.json()["intentos_restantes"]) == ("no_es", 4)
    r = _validar(d, parte, codigo)
    assert r.status_code == 200 and r.json()["resultado"] == "correcto"
    assert r.json()["parte"]["estado"] == "retirada" and r.json()["parte"]["estado_codigo"] == "usado"
    assert d.estado_pedido(pedido["id"]) == "retirado"
    # Usado: no sirve otra vez
    assert _validar(d, parte, codigo).json()["resultado"] == "usado"
    # La base guarda solo la huella, y ni el código ni la huella
    assert d.sql("SELECT codigo_hash FROM pedido_comercio WHERE id = %s", uuid.UUID(parte)) == [(None,)]

    # En camino y entregado: entregado_en y lo que MATU le debe al comercio (RF-31)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino").json()["estado"] == "en_ruta"
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").json()["estado"] == "entregado"
    assert d.sql(
        "SELECT monto_autorizado, monto_boleta, estado FROM consumo_comercio WHERE pedido_comercio_id = %s",
        uuid.UUID(parte),
    ) == [(2 * PRECIO_PANAL, None, "pendiente")]

    # R3: la familia se arrepiente de un pañal; operación lo recibe y devuelve a la misma tarjeta
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    ver = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia)
    assert ver.status_code == 200 and ver.json()["retractos"] == []
    r = d.e.pedir("POST", f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                  {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 201, r.text
    # Las condiciones 0.2 devuelven también el envío (D-63-10, a)
    assert (r.json()["monto"], r.json()["incluye_envio"]) == (PRECIO_PANAL + COSTO_ENVIO, True)
    resuelto = d.operacion("POST", f"/retractos/{r.json()['id']}/resolver", {"decision": "devolver"})
    assert resuelto.status_code == 200, resuelto.text
    assert resuelto.json()["estado"] == "devuelto"
    total = 2 * PRECIO_PANAL + COSTO_ENVIO
    assert d.cargo(pedido["id"]) == ("devuelto_parcial", total, PRECIO_PANAL + COSTO_ENVIO)
    assert d.sql(
        "SELECT estado_linea, monto_devuelto FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"])
    ) == [("preparada", PRECIO_PANAL)]
    # Resuelto, no se resuelve otra vez
    assert d.operacion("POST", f"/retractos/{r.json()['id']}/resolver", {"decision": "devolver"}).status_code == 409
    # La misma línea no se pide otra vez
    otra = d.e.pedir("POST", f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                     {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert otra.status_code == 422

    # Logs: ni el código, ni el token, ni la referencia
    logs = d.e.iam.salida_logs.getvalue()
    assert codigo not in logs and malo not in logs


def test_el_faltante_se_devuelve_el_mismo_dia_por_unidades(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    # O4: marcar no mueve dinero; recién «Listo»
    lista = _preparar_todo(d, parte, etag, faltan=1)
    assert lista["estado"] == "lista" and lista["lineas"][0]["unidades_faltantes"] == 1
    total = 2 * PRECIO_PANAL + COSTO_ENVIO
    assert d.cargo(pedido["id"]) == ("devuelto_parcial", total, PRECIO_PANAL)
    assert d.sql(
        "SELECT t.motivo_anulacion, t.monto FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id"
        " WHERE c.pedido_id = %s AND t.tipo = 'anulacion'", uuid.UUID(pedido["id"]),
    ) == [("producto_no_entregado", PRECIO_PANAL)]
    # La tarea del despacho no lo devuelve dos veces
    from app.core.db import obtener_fabrica_sesiones
    from app.modules.backoffice.application.despacho import llevar
    from app.modules.backoffice.infrastructure.sistema import AbrirDespachoSQL

    grupo = d.sql("SELECT grupo_id FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))[0][0]
    with AbrirDespachoSQL(obtener_fabrica_sesiones(), d.e.iam.reloj)(grupo) as (u, _):
        assert llevar(u, d.pasarela, uuid.UUID(pedido["id"]), d.e.iam.reloj.ahora()) == []
    assert d.cargo(pedido["id"]) == ("devuelto_parcial", total, PRECIO_PANAL)


@pytest.mark.rf("RF-25")
def test_si_no_hay_ninguno_se_devuelve_todo_con_el_envio(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    cancelada = _preparar_todo(d, parte, etag, faltan=2)
    assert (cancelada["estado"], cancelada["motivo_cancelacion"]) == ("cancelada", "producto_faltante")
    assert d.estado_pedido(pedido["id"]) == "cancelado_con_devolucion"
    total = 2 * PRECIO_PANAL + COSTO_ENVIO
    assert d.cargo(pedido["id"]) == ("anulado", total, total)
    assert d.pasarela.cobrado(d.sql(
        "SELECT t.token FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id"
        " WHERE c.pedido_id = %s AND t.tipo = 'venta'", uuid.UUID(pedido["id"]))[0][0]) == 0


def test_el_codigo_vence_y_se_bloquea(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag)
    # Sin código todavía
    assert _validar(d, parte, "000000").json()["resultado"] == "sin_codigo"
    codigo = _codigo(d, parte)
    malos = [f"{(int(codigo) + i) % 1_000_000:06d}" for i in range(1, 6)]
    resultados = [_validar(d, parte, m).json() for m in malos]
    assert [(r["resultado"], r["intentos_restantes"]) for r in resultados] == [
        ("no_es", 4), ("no_es", 3), ("no_es", 2), ("no_es", 1), ("bloqueado", 0)]
    # Bloqueado: ni el correcto sirve
    assert _validar(d, parte, codigo).json()["resultado"] == "bloqueado"
    assert d.sql("SELECT codigo_hash IS NULL, codigo_bloqueado_en IS NOT NULL FROM pedido_comercio WHERE id = %s",
                 uuid.UUID(parte)) == [(True, True)]
    # Operación lo regenera; vence a los 90 minutos
    codigo = _codigo(d, parte)
    d.e.avanzar(VIDA_CODIGO + timedelta(seconds=1))
    assert _validar(d, parte, codigo).json()["resultado"] == "vencido"
    assert d.comercio("uno", "GET", f"/partes/{parte}").json()["estado_codigo"] == "vencido"
    # Auditoría del comercio: sin grupo ni persona, con la cuenta del encargado
    filas = d.sql("SELECT DISTINCT accion, grupo_id, persona_cuidada_id, actor_tipo FROM auditoria"
                  " WHERE entidad_id = %s AND actor_tipo = 'comercio'", uuid.UUID(parte))
    assert {f[0] for f in filas} >= {"comercio.preparar", "comercio.codigo_incorrecto", "comercio.codigo_bloqueo"}
    assert all(f[1] is None and f[2] is None for f in filas)


def test_el_codigo_no_va_en_la_url_y_un_codigo_mal_formado_es_422(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    parte, _ = _parte(d, pedido)
    r = _validar(d, parte, "12ab56")
    assert r.status_code == 422 and "12ab56" not in r.text


def test_la_parte_de_otro_comercio_es_404(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    for metodo, ruta in (("GET", f"/partes/{parte}"), ("POST", f"/partes/{parte}/preparar"),
                         ("POST", f"/partes/{parte}/listo")):
        assert d.comercio("dos", metodo, ruta).status_code == 404
    assert _validar(d, parte, "123456", comercio="dos").status_code == 404
    assert parte not in [p["id"] for p in d.comercio("dos", "GET", "/partes").json()["partes"]]


def test_una_cuenta_que_no_es_de_comercio_ni_de_operacion_recibe_404(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    assert d.como(familia.admin, "GET", "/v1/comercio/partes").status_code == 404
    assert d.como(familia.admin, "GET", "/v1/operacion/pedidos").status_code == 404
    # El tipo de cuenta al entrar (O1)
    assert d.e.iam.iniciar_sesion(email=familia.admin.email, contrasena=familia.admin.contrasena).json()[
        "tipo_cuenta"] == "familia"
    encargado = d.encargados["uno"]
    assert d.e.iam.iniciar_sesion(email=encargado.email, contrasena=encargado.contrasena).json()[
        "tipo_cuenta"] == "comercio"


def test_comercio_inactivo_es_403(despacho: Despacho) -> None:
    d = despacho
    d.sql("UPDATE usuario_comercio SET activo = false WHERE usuario_id = %s", d.encargados["uno"].id)
    r = d.comercio("uno", "GET", "/partes")
    assert r.status_code == 403 and r.json()["type"] == "/errores/comercio-inactivo"


def test_una_version_vieja_es_412_y_un_estado_que_no_calza_es_409(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    assert d.comercio("uno", "POST", f"/partes/{parte}/listo", **{"If-Match": etag}).status_code == 409
    assert d.comercio("uno", "POST", f"/partes/{parte}/preparar", **{"If-Match": '"v99"'}).status_code == 412


@pytest.mark.rf("R15")
def test_r15_cancela_con_devolucion_antes_de_que_preparen_y_no_despues(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    # Solo el admin
    cuidador = d.e.usuario(familia, "cuidador") if "cuidador" in familia.miembros else None
    if cuidador is not None:
        assert d.e.pedir("POST", f"/v1/pedidos/{pedido['id']}/cancelar-con-devolucion", cuidador,
                         familia).status_code == 404
    r = d.e.pedir("POST", f"/v1/pedidos/{pedido['id']}/cancelar-con-devolucion", familia.admin, familia)
    assert r.status_code == 200, r.text
    total = 2 * PRECIO_PANAL + COSTO_ENVIO
    assert d.estado_pedido(pedido["id"]) == "cancelado_con_devolucion"
    assert d.cargo(pedido["id"]) == ("anulado", total, total)
    parte = d.parte_de(pedido["id"])
    vista = d.comercio("uno", "GET", f"/partes/{parte}").json()
    assert (vista["estado"], vista["motivo_cancelacion"]) == ("cancelada", "cancelada_por_familia")
    [resumen] = [p for p in d.comercio("uno", "GET", "/partes").json()["partes"] if p["id"] == parte]
    assert resumen["motivo_cancelacion"] == "cancelada_por_familia"
    assert d.comercio("uno", "POST", f"/partes/{parte}/preparar").status_code == 409

    # Con el comercio preparando, ya no
    familia2, pedido2 = d.pagado()
    parte2, etag2 = _parte(d, pedido2)
    assert d.comercio("uno", "POST", f"/partes/{parte2}/preparar", **{"If-Match": etag2}).status_code == 200
    r = d.e.pedir("POST", f"/v1/pedidos/{pedido2['id']}/cancelar-con-devolucion", familia2.admin, familia2)
    assert r.status_code == 409 and r.json()["type"] == "/errores/ya-se-prepara"


def test_el_retracto_fuera_de_plazo_es_409(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag)
    assert _validar(d, parte, _codigo(d, parte)).json()["resultado"] == "correcto"
    d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino")
    d.operacion("POST", f"/pedidos/{pedido['id']}/entregado")
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    d.e.avanzar(timedelta(days=15))
    r = d.e.pedir("POST", f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                  {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 409 and r.json()["type"] == "/errores/fuera-de-plazo"
    # Un pedido no entregado no tiene retracto
    familia2, pedido2 = d.pagado()
    assert d.e.pedir("GET", f"/v1/pedidos/{pedido2['id']}/retractos", familia2.admin, familia2).status_code == 404


def test_operacion_no_salta_estados(despacho: Despacho) -> None:
    d = despacho
    _, pedido = d.pagado()
    r = d.operacion("POST", f"/pedidos/{pedido['id']}/entregado")
    assert r.status_code == 409 and r.json()["type"] == "/errores/estado-pedido"
    parte = d.parte_de(pedido["id"])
    assert d.operacion("POST", f"/partes/{parte}/codigo").status_code == 409


def test_la_tarea_despacho_lleva_el_pedido_pagado_con_matu_scheduler(despacho: Despacho) -> None:
    """python -m app.tareas despacho: despacho_pendiente (matu_scheduler, solo ids) y cada pedido con el sistema."""
    from app.core.config import obtener_configuracion
    from app.core.db import obtener_fabrica_sesiones
    from app.modules.backoffice.infrastructure import tarea_despacho
    from tests.base_datos import fabrica_scheduler

    d = despacho
    _, pedido = d.pagado()
    assert d.estado_pedido(pedido["id"]) == "pagado"
    resultado = tarea_despacho.ejecutar(
        obtener_configuracion(), obtener_fabrica_sesiones(), fabrica_scheduler(), d.e.iam.reloj, d.pasarela
    )
    assert resultado.fallidos == 0 and resultado.avanzados >= 1
    assert d.estado_pedido(pedido["id"]) == "enviado_a_comercio"


@pytest.mark.rf("RF-26")
def test_operacion_genera_el_codigo_desde_la_consola_y_vence_solo(despacho: Despacho, monkeypatch: Any) -> None:
    """D-63-5 (decisión 426): python -m app.tareas codigo-retiro <parte> con matu_scheduler. El código sale una vez por
    la consola, nunca por el log, y la auditoría lo registra sin el código. D-63-13: la tarea despacho vacía la huella
    del código vencido."""
    import io

    from pydantic import SecretStr

    from app import tareas
    from app.core.config import obtener_configuracion
    from app.core.db import obtener_fabrica_sesiones
    from app.modules.backoffice.infrastructure import tarea_despacho
    from tests.base_datos import fabrica_scheduler
    from tests.modules.backoffice.conftest import SECRETO_CODIGO

    d = despacho
    _, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag)
    config = obtener_configuracion().model_copy(update={"codigo_retiro_secreto": SecretStr(SECRETO_CODIGO.decode())})
    monkeypatch.setattr(tareas, "fabrica_de_rol", lambda url, rol: fabrica_scheduler())
    logs, consola = io.StringIO(), io.StringIO()
    assert tareas.codigo_retiro(parte, stream=logs, consola=consola, reloj=d.e.iam.reloj, config=config) == 0
    [codigo] = re.findall(r"\b[0-9]{6}\b", consola.getvalue())
    assert codigo not in logs.getvalue() and "codigo_retiro" in logs.getvalue()
    assert d.sql("SELECT accion, actor_tipo, actor_ref, persona_cuidada_id IS NOT NULL FROM auditoria"
                 " WHERE entidad_id = %s AND accion = 'codigo_retiro.generar'", uuid.UUID(parte)) == [
        ("codigo_retiro.generar", "operacion", None, True)]
    # Una parte que no existe, o un id que no es: falla sin escribir nada
    assert tareas.codigo_retiro(str(uuid.uuid4()), stream=logs, consola=io.StringIO(), reloj=d.e.iam.reloj,
                                config=config) == 1
    assert tareas.codigo_retiro("no-es-un-id", stream=logs) == 2
    # Sin el secreto, tampoco
    sin_secreto = obtener_configuracion().model_copy(update={"codigo_retiro_secreto": None})
    assert tareas.codigo_retiro(parte, stream=logs, consola=io.StringIO(), reloj=d.e.iam.reloj,
                                config=sin_secreto) == 1
    assert "CODIGO_RETIRO_SECRETO" in logs.getvalue()

    # Vence a los 90 minutos: la tarea despacho vacía su huella sin que nadie lo pruebe
    d.e.avanzar(VIDA_CODIGO + timedelta(seconds=1))
    resultado = tarea_despacho.ejecutar(
        obtener_configuracion(), obtener_fabrica_sesiones(), fabrica_scheduler(), d.e.iam.reloj, d.pasarela
    )
    assert resultado.codigos_vencidos >= 1
    assert d.sql("SELECT codigo_hash FROM pedido_comercio WHERE id = %s", uuid.UUID(parte)) == [(None,)]
    assert _validar(d, parte, codigo).json()["resultado"] == "vencido"


@pytest.mark.rf("RF-37")
def test_la_copia_de_los_datos_trae_las_partes_los_faltantes_y_el_retracto(despacho: Despacho) -> None:
    """MATU-54 con MATU-63: «Datos de» suma las partes (sin su referencia), las unidades faltantes, las devoluciones y
    los retractos; «Tus datos» de quien pidió el retracto, sus retractos."""
    d = despacho
    familia, pedido = d.pagado()
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag, faltan=1)
    assert _validar(d, parte, _codigo(d, parte)).json()["resultado"] == "correcto"
    d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino")
    d.operacion("POST", f"/pedidos/{pedido['id']}/entregado")
    [linea] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    r = d.e.pedir("POST", f"/v1/pedidos/{pedido['id']}/retractos", familia.admin, familia,
                  {"lineas": [{"linea_id": str(linea[0]), "cantidad": 1}]})
    assert r.status_code == 201, r.text
    referencia_parte = d.sql("SELECT referencia FROM pedido_comercio WHERE id = %s", uuid.UUID(parte))[0][0]

    copia = d.e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)
    assert copia.status_code == 200, copia.text
    [p] = [x for x in copia.json()["pedidos"] if x["estado"] == "entregado"]
    assert [(x["estado"], x["unidades_faltantes"]) for x in p["lineas"]] == [("faltante", 1)]
    assert [x["estado"] for x in p["partes"]] == ["retirada"] and p["entregado_en"] is not None
    assert [x["motivo"] for x in p["pago"]["devoluciones"]] == ["producto_no_entregado"]
    assert [(x["estado"], x["lineas"][0]["cantidad"]) for x in p["retractos"]] == [("solicitado", 1)]
    assert referencia_parte not in copia.text
    tipos = {h["tipo"] for h in copia.json()["historial"]["hechos"]}
    assert {"pedido_entregado", "pidio_un_retracto", "codigo_de_retiro_generado", "devolucion_a_la_tarjeta"} <= tipos

    cuenta = d.como(familia.admin, "GET", "/v1/yo/datos")
    assert cuenta.status_code == 200, cuenta.text
    assert [x["estado"] for x in cuenta.json()["retractos"]] == ["solicitado"]
