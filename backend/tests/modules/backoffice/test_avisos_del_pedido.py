"""MATU-76 · Los avisos del pedido a quien pagó, contra PostgreSQL (RF-39; D-76-2 a D-76-5; C1 a C4 y C8).

El pedido se paga y se mueve por la API de MATU-62 y MATU-63 (con la pasarela falsa), y los eventos que quedan en el
outbox se entregan al consumidor del aviso del pedido, que corre como matu_app con app.rol = 'sistema' y el grupo del
pedido. Los enviadores son dobles en memoria. Está en backoffice porque usa sus fixtures del despacho; el consumidor es
de notifications. Solo datos sintéticos.
"""

import json
import logging
import uuid
from datetime import timedelta
from typing import Any

import pytest

from app.core.db import fabrica_sesiones
from app.core.push_piloto import PoliticaPush
from app.modules.notifications.application.avisos_pedido import ConsumidorAvisoPedido
from app.modules.notifications.domain.aviso import ResultadoEnvio
from app.modules.notifications.domain.mensaje import PIE_PEDIDO, PIE_PEDIDO_DINERO
from app.modules.notifications.infrastructure.repositorio_avisos import UnidadAvisosSQL
from app.shared.outbox import EventoTomado, Hecho, Posponer, Reintentar, ResultadoConsumo
from tests.base_datos import requiere_base
from tests.dobles.enviadores_en_memoria import EnviadorCorreoEnMemoria, EnviadorPushEnMemoria
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.backoffice.conftest import Despacho
from tests.modules.backoffice.test_despacho_api import _codigo, _parte, _preparar_todo, _validar
from tests.modules.payments.conftest import pagar, pedido_confirmado, sin_sesion_volver

pytestmark = [requiere_base, pytest.mark.rf("RF-39")]

ORIGEN = "https://matu.example"
TOKEN_PUSH = "https://fcm.googleapis.com/fcm/send/token-sintetico-76-{}"


class Avisos:
    """El consumidor de cada evento del pedido, con enviadores en memoria y su propio reloj."""

    def __init__(self, d: Despacho) -> None:
        self.d = d
        self.correo = EnviadorCorreoEnMemoria()
        self.push = EnviadorPushEnMemoria()
        # Las 10:00 de Santiago del día de la prueba: ya se puede avisar
        self.reloj = RelojFijo(d.e.iam.reloj.ahora() + timedelta(hours=1))

    def consumidor(self, tipo: str) -> ConsumidorAvisoPedido:
        return ConsumidorAvisoPedido(
            tipo=tipo,
            unidad=UnidadAvisosSQL(fabrica_sesiones()),
            correo=self.correo,
            push=self.push,
            reloj=self.reloj,
            origen_web=ORIGEN,
            push_permitido=PoliticaPush(entorno="pruebas").permite,
        )

    def evento(self, pedido: dict[str, Any], tipo: str) -> EventoTomado:
        [(evento_id, grupo_id, payload, intentos)] = self.d.sql(
            "SELECT id, grupo_id, payload, intentos FROM evento_outbox WHERE agregado_id = %s AND tipo = %s",
            uuid.UUID(pedido["id"]),
            tipo,
        )
        return EventoTomado(evento_id, grupo_id, tipo, payload, intentos)

    def consumir(self, pedido: dict[str, Any], tipo: str) -> ResultadoConsumo:
        return self.consumidor(tipo).consumir(self.evento(pedido, tipo))

    def filas(self, pedido: dict[str, Any], tipo: str) -> dict[tuple[uuid.UUID, str], tuple[str, str | None]]:
        evento = self.evento(pedido, tipo)
        return {
            (u, c): (e, err)
            for u, c, e, err, plantilla in self.d.sql(
                "SELECT usuario_id, canal, estado, error, plantilla FROM notificacion WHERE evento_id = %s", evento.id
            )
            if plantilla == "pedido_novedad"
        }

    def dispositivo(self, usuario: UsuarioCreado, n: int) -> None:
        self.d.sql(
            "INSERT INTO dispositivo (id, usuario_id, plataforma, push_token) VALUES (%s, %s, 'web', %s)",
            uuid.uuid4(),
            usuario.id,
            TOKEN_PUSH.format(n),
        )

    def preferencia(self, usuario: UsuarioCreado, canal: str, activo: bool) -> None:
        self.d.sql(
            "INSERT INTO preferencia_notificacion (usuario_id, tipo_evento, canal, activo)"
            " VALUES (%s, 'pedido', %s, %s)"
            " ON CONFLICT (usuario_id, tipo_evento, canal) DO UPDATE SET activo = EXCLUDED.activo",
            usuario.id,
            canal,
            activo,
        )


@pytest.fixture
def avisos(despacho: Despacho) -> Avisos:
    return Avisos(despacho)


def _familia(d: Despacho) -> FamiliaCreada:
    return d.e.fabrica.familia(miembros=("cuidador", "pagador", "observador"))


def _pagado_por(d: Despacho, familia: FamiliaCreada, usuario: UsuarioCreado) -> dict[str, Any]:
    familia, pedido = pedido_confirmado(d.e, familia)
    respuesta = pagar(d.e, familia, pedido, usuario)
    assert respuesta.status_code == 201, respuesta.text
    token = respuesta.json()["token"]
    d.pasarela.pagar(token)
    assert sin_sesion_volver(d.e, {"token_ws": token}).json()["resultado"] == "aprobado"
    return pedido


def _en_ruta(d: Despacho, pedido: dict[str, Any]) -> None:
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag)
    assert _validar(d, parte, _codigo(d, parte)).json()["resultado"] == "correcto"
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino").status_code == 200


def _entregado(d: Despacho, pedido: dict[str, Any]) -> None:
    _en_ruta(d, pedido)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").json()["estado"] == "entregado"


# --- El evento nuevo (D-76-5) -------------------------------------------------------------------------------------


def test_no_entregado_emite_pedido_no_entregado_y_avisa_a_quien_pago(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    _en_ruta(d, pedido)

    assert d.operacion("POST", f"/pedidos/{pedido['id']}/no-entregado").json()["estado"] == "no_entregado"

    # En la misma transacción que el cambio de estado, solo con el id del pedido
    [(payload, grupo)] = d.sql(
        "SELECT payload, grupo_id FROM evento_outbox WHERE agregado_id = %s AND tipo = 'PedidoNoEntregado'",
        uuid.UUID(pedido["id"]),
    )
    assert payload == {"pedido_id": pedido["id"]} and grupo == familia.grupo.id
    assert isinstance(avisos.consumir(pedido, "PedidoNoEntregado"), Hecho)
    assert avisos.filas(pedido, "PedidoNoEntregado") == {
        (familia.admin.id, "correo"): ("enviada", None),
        (familia.admin.id, "push"): ("omitida", "sin_destino"),
    }
    [enviado] = avisos.correo.enviados
    assert (enviado.destino, enviado.plantilla) == (familia.admin.email, "pedido_novedad")
    assert enviado.mensaje.pie == PIE_PEDIDO
    # Volver a salir desde no_entregado no emite otro
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino").json()["estado"] == "en_ruta"
    assert (
        len(
            d.sql(
                "SELECT 1 FROM evento_outbox WHERE agregado_id = %s AND tipo = 'PedidoNoEntregado'",
                uuid.UUID(pedido["id"]),
            )
        )
        == 1
    )


# --- Solo quien pagó (C4) -----------------------------------------------------------------------------------------


def test_entregado_avisa_solo_al_admin_que_pago_y_no_a_quien_cuida(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    cuidador = familia.miembros["cuidador"].usuario
    avisos.dispositivo(familia.admin, 1)
    avisos.dispositivo(cuidador, 2)
    pedido = _pagado_por(d, familia, familia.admin)
    _entregado(d, pedido)

    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)

    assert avisos.filas(pedido, "PedidoEntregado") == {
        (familia.admin.id, "correo"): ("enviada", None),
        (familia.admin.id, "push"): ("enviada", None),
    }
    assert {x.usuario_id for x in avisos.correo.enviados} == {familia.admin.id}
    assert [x.push_token for x in avisos.push.enviados] == [TOKEN_PUSH.format(1)]
    assert d.sql(
        "SELECT consumidor FROM evento_consumido WHERE evento_id = %s", avisos.evento(pedido, "PedidoEntregado").id
    ) == [("notifications.pedido.PedidoEntregado",)]


def test_pago_el_pagador_y_paso_a_observador_recibe_y_el_admin_no(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    pagador = familia.miembros["pagador"].usuario
    pedido = _pagado_por(d, familia, pagador)
    _entregado(d, pedido)
    d.sql(
        "UPDATE membresia SET rol = 'observador' WHERE usuario_id = %s AND grupo_id = %s", pagador.id, familia.grupo.id
    )

    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)

    assert avisos.filas(pedido, "PedidoEntregado") == {
        (pagador.id, "correo"): ("enviada", None),
        (pagador.id, "push"): ("omitida", "sin_destino"),
    }
    assert [x.destino for x in avisos.correo.enviados] == [pagador.email]


def test_quien_pago_y_salio_del_grupo_se_omite(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    pagador = familia.miembros["pagador"].usuario
    pedido = _pagado_por(d, familia, pagador)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/cancelar-con-devolucion").status_code == 200
    d.sql(
        "UPDATE membresia SET estado = 'retirada' WHERE usuario_id = %s AND grupo_id = %s", pagador.id, familia.grupo.id
    )

    assert isinstance(avisos.consumir(pedido, "PedidoCanceladoConDevolucion"), Hecho)

    # D-76-4: no se le avisa, ni siquiera el correo de su dinero. La devolución va igual a su tarjeta
    assert set(avisos.filas(pedido, "PedidoCanceladoConDevolucion").values()) == {("omitida", "miembro_inactivo")}
    assert avisos.correo.enviados == [] and avisos.push.enviados == []


def test_quien_retiro_la_autorizacion_de_pedidos_recibe(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    _entregado(d, pedido)
    d.sql(
        "UPDATE consentimiento SET revocado_en = now(), revocacion_motivo = 'retiro'"
        " WHERE persona_cuidada_id = %s AND finalidad = 'despacho' AND revocado_en IS NULL",
        familia.persona.id,
    )

    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)

    # C2: un aviso del pedido nunca queda sin_autorizacion
    assert avisos.filas(pedido, "PedidoEntregado")[(familia.admin.id, "correo")] == ("enviada", None)


# --- Idempotencia (C1 y C4) ---------------------------------------------------------------------------------------


def test_un_reintento_no_duplica_y_el_push_que_fallo_se_reintenta(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    avisos.dispositivo(familia.admin, 3)
    pedido = _pagado_por(d, familia, familia.admin)
    _entregado(d, pedido)
    avisos.push.respuesta = ResultadoEnvio.NO_DISPONIBLE

    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Reintentar)
    assert avisos.filas(pedido, "PedidoEntregado")[(familia.admin.id, "push")] == ("fallida", "proveedor_no_disponible")

    avisos.push.respuesta = ResultadoEnvio.ENVIADO
    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)
    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)

    assert len(avisos.correo.enviados) == 1 and len(avisos.push.enviados) == 2
    assert len(avisos.filas(pedido, "PedidoEntregado")) == 2
    assert set(avisos.filas(pedido, "PedidoEntregado").values()) == {("enviada", None)}


def test_antes_de_las_9_se_pospone(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    _entregado(d, pedido)
    temprano = avisos.consumidor("PedidoEntregado")
    temprano._reloj = RelojFijo(d.e.iam.reloj.ahora() - timedelta(hours=4))  # 05:00 en Santiago

    assert isinstance(temprano.consumir(avisos.evento(pedido, "PedidoEntregado")), Posponer)
    assert avisos.filas(pedido, "PedidoEntregado") == {}


# --- El correo de dinero no se apaga (D-76-3, C4 y C7) ------------------------------------------------------------


def test_el_correo_de_dinero_llega_con_el_correo_apagado_y_el_push_no(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    avisos.dispositivo(familia.admin, 4)
    avisos.preferencia(familia.admin, "correo", False)
    avisos.preferencia(familia.admin, "push", False)
    pedido = _pagado_por(d, familia, familia.admin)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/cancelar-con-devolucion").status_code == 200

    assert isinstance(avisos.consumir(pedido, "PedidoCanceladoConDevolucion"), Hecho)

    assert avisos.filas(pedido, "PedidoCanceladoConDevolucion") == {(familia.admin.id, "correo"): ("enviada", None)}
    [enviado] = avisos.correo.enviados
    assert enviado.mensaje.pie == PIE_PEDIDO_DINERO
    assert avisos.push.enviados == []


def test_el_correo_de_entregado_sigue_la_preferencia(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    avisos.preferencia(familia.admin, "correo", False)
    pedido = _pagado_por(d, familia, familia.admin)
    _entregado(d, pedido)

    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)

    # Sin push_token, el push queda sin destino; el correo apagado no tiene fila
    assert avisos.filas(pedido, "PedidoEntregado") == {(familia.admin.id, "push"): ("omitida", "sin_destino")}
    assert avisos.correo.enviados == []


def test_el_correo_apagado_entre_la_creacion_y_el_envio_no_sale(despacho: Despacho, avisos: Avisos) -> None:
    """C2: el canal se revisa de nuevo en cada intento."""
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    _en_ruta(d, pedido)
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/no-entregado").status_code == 200
    avisos.correo.respuestas = [ResultadoEnvio.NO_DISPONIBLE]
    assert isinstance(avisos.consumir(pedido, "PedidoNoEntregado"), Reintentar)
    avisos.preferencia(familia.admin, "correo", False)

    assert isinstance(avisos.consumir(pedido, "PedidoNoEntregado"), Hecho)

    assert avisos.filas(pedido, "PedidoNoEntregado")[(familia.admin.id, "correo")] == ("omitida", "sin_destino")
    assert len(avisos.correo.enviados) == 1  # solo el intento que no llegó


def test_producto_faltante_avisa_con_el_correo_de_dinero(despacho: Despacho, avisos: Avisos) -> None:
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag, faltan=1)

    assert isinstance(avisos.consumir(pedido, "ProductoFaltante"), Hecho)

    assert avisos.filas(pedido, "ProductoFaltante")[(familia.admin.id, "correo")] == ("enviada", None)
    assert avisos.correo.enviados[0].mensaje.pie == PIE_PEDIDO_DINERO


def test_pago_anulado_avisa_a_quien_pago_aunque_el_cargo_se_cierre_sin_cobro(
    despacho: Despacho, avisos: Avisos
) -> None:
    """La venta del pago tardío queda aprobada (y anulada entera): esa cuenta es quien pagó. El evento se siembra con
    el formato con que lo emite payments (solo el id del pedido)."""
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    d.sql(
        "INSERT INTO evento_outbox (grupo_id, tipo, agregado_tipo, agregado_id, payload)"
        " VALUES (%s, 'PagoAnulado', 'pedido', %s, %s)",
        familia.grupo.id,
        uuid.UUID(pedido["id"]),
        json.dumps({"pedido_id": pedido["id"]}),
    )

    assert isinstance(avisos.consumir(pedido, "PagoAnulado"), Hecho)

    assert avisos.filas(pedido, "PagoAnulado")[(familia.admin.id, "correo")] == ("enviada", None)
    assert avisos.correo.enviados[0].mensaje.pie == PIE_PEDIDO_DINERO


def test_pedido_pagado_no_tiene_consumidor_de_aviso() -> None:
    with pytest.raises(ValueError):
        ConsumidorAvisoPedido(
            tipo="PedidoPagado",
            unidad=None,  # type: ignore[arg-type]
            correo=None,  # type: ignore[arg-type]
            push=None,  # type: ignore[arg-type]
            reloj=None,  # type: ignore[arg-type]
            origen_web=ORIGEN,
            push_permitido=lambda _: True,
        )


# --- Lo que no se guarda ni se registra (C6 y C8) -----------------------------------------------------------------


def test_ni_la_fila_ni_el_log_llevan_el_destino_ni_el_pedido(
    despacho: Despacho, avisos: Avisos, caplog: pytest.LogCaptureFixture
) -> None:
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    _entregado(d, pedido)

    with caplog.at_level(logging.INFO, logger="matu.notifications"):
        assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)

    [(fila,)] = d.sql(
        "SELECT to_jsonb(n) FROM notificacion n WHERE usuario_id = %s AND plantilla = 'pedido_novedad'"
        " AND canal = 'correo'",
        familia.admin.id,
    )
    texto = json.dumps(fila)
    assert familia.admin.email not in texto and pedido["id"] not in texto
    registros = [r for r in caplog.records if r.name.startswith("matu.notifications")]
    assert registros
    for r in registros:
        extra = json.dumps({k: str(v) for k, v in r.__dict__.items()}, ensure_ascii=False)
        assert familia.admin.email not in extra and pedido["id"] not in extra and "novedad" not in extra


def test_tus_datos_muestra_el_aviso_del_pedido_y_datos_de_la_persona_no(despacho: Despacho, avisos: Avisos) -> None:
    """C11 y C12: el aviso es de la cuenta que pagó. Sale en su copia («Tus datos») con el tipo «pedido», y no en la
    copia de los datos de la persona cuidada."""
    d = despacho
    familia = _familia(d)
    pedido = _pagado_por(d, familia, familia.admin)
    _entregado(d, pedido)
    assert isinstance(avisos.consumir(pedido, "PedidoEntregado"), Hecho)

    cuenta = d.como(familia.admin, "GET", "/v1/yo/datos")
    assert cuenta.status_code == 200, cuenta.text
    tipos = {(a["tipo"], a["canal"]) for a in cuenta.json()["avisos_enviados"]}
    assert tipos == {("pedido", "correo"), ("pedido", "push")}
    persona = d.como(
        familia.admin,
        "GET",
        f"/v1/personas-cuidadas/{familia.persona.id}/datos",
        **{"X-Grupo-Id": str(familia.grupo.id)},
    )
    assert persona.status_code == 200, persona.text
    assert "pedido_novedad" not in persona.text and "avisos_enviados" not in persona.text
    assert persona.json()["insumos"]["avisos"] in ([], None)
