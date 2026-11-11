"""MATU-62 · Los nueve casos de la arquitectura 12.4 y las reglas de D-62-4, con la PasarelaFalsa. Sin base.

Los casos de uso (pagar, la vuelta, la conciliación y las devoluciones) corren contra el pago en memoria
(tests/dobles/pagos_en_memoria.py), que repite las restricciones de la base que importan al flujo. Las mismas reglas
en la base las prueban test_pago_api.py, test_aislamiento.py y test_migraciones.py.

Los montos son sintéticos y como los de la prueba en integración: $57.460 = 2 × $17.990 + 2 × $8.745 + $3.990.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.ordering.application.pedidos import Actor, VersionDesactualizada
from app.modules.ordering.domain.estados import TransicionInvalida
from app.modules.payments.application import devoluciones
from app.modules.payments.application.cobro import EstadoAnulacion
from app.modules.payments.application.conciliacion import ResultadoConciliacion, conciliar
from app.modules.payments.application.pagar import (
    Aceptacion,
    CondicionesCambiaron,
    Inicio,
    PagoEnCurso,
    PagoNoIniciado,
    SinPasarela,
    pagar,
    repetir,
)
from app.modules.payments.application.ports import PasarelaNoDisponible
from app.modules.payments.application.retorno import ResultadoVuelta, VentaDesconocida, Vuelta, procesar
from app.modules.payments.domain.cargo import DevolucionInvalida, EstadoCargo, EstadoParticipacion
from app.modules.payments.domain.venta import (
    EstadoVenta,
    MotivoAnulacion,
    MotivoCierre,
    RespuestaAnulacion,
    ResultadoPago,
    TipoTarjeta,
)
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from app.shared.auditoria import AccionAuditoria
from tests.dobles.pagos_en_memoria import BasePagos, PedidoMem, RepositorioPagosEnMemoria, SistemaEnMemoria
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-25")

AHORA = datetime(2026, 11, 12, 14, 2, 11, tzinfo=UTC)
VIDA = timedelta(minutes=10)
VIGENTES = Aceptacion("0.2", "a" * 64)
RETURN_URL = "https://localhost/insumos/pedido/pago"
TOTAL = 57460


@dataclass
class Escena:
    pasarela: PasarelaFalsa = field(default_factory=PasarelaFalsa)
    base: BasePagos = field(default_factory=BasePagos)
    reloj: RelojFijo = field(default_factory=lambda: RelojFijo(AHORA))
    admin: uuid.UUID = field(default_factory=uuid.uuid4)
    pedido: PedidoMem | None = None

    def __post_init__(self) -> None:
        self.sistema = SistemaEnMemoria(self.base)
        self.pedido = self.base.nuevo_pedido(AHORA)

    @property
    def p(self) -> PedidoMem:
        assert self.pedido is not None
        return self.pedido

    def registro(self) -> RegistroAuditoriaEnMemoria:
        return self.base.registros.setdefault(self.p.grupo_id, RegistroAuditoriaEnMemoria())

    def pagar(
        self,
        *,
        usuario: uuid.UUID | None = None,
        if_match: str | None = None,
        aceptacion: Aceptacion = VIGENTES,
        pasarela: PasarelaFalsa | None | bool = True,
    ) -> Inicio:
        quien = usuario or self.admin
        actor = Actor(usuario_id=quien, grupo_id=self.p.grupo_id, rol="admin")
        return pagar(
            actor,
            self.p.a_pedido(),
            if_match or f'"v{self.p.version}"',
            aceptacion,
            VIGENTES,
            self.reloj.ahora(),
            VIDA,
            RETURN_URL,
            RepositorioPagosEnMemoria(self.base, self.p.grupo_id, quien),
            self.pasarela if pasarela is True else (pasarela or None),
            self.registro(),
        )

    def volver(self, **campos: str) -> ResultadoVuelta:
        """Con los nombres de Transbank, como los trae la dirección."""
        vuelta = Vuelta(
            token_ws=campos.get("token_ws"),
            tbk_token=campos.get("TBK_TOKEN"),
            tbk_orden_compra=campos.get("TBK_ORDEN_COMPRA"),
            tbk_id_sesion=campos.get("TBK_ID_SESION"),
        )
        return procesar(vuelta, self.sistema.resolver, self.sistema.abrir, self.pasarela, self.reloj.ahora(), VIDA)

    def conciliar(self) -> ResultadoConciliacion:
        return conciliar(self.sistema.listar, self.sistema.abrir, self.pasarela, self.reloj.ahora(), VIDA)

    def cargo(self):  # type: ignore[no-untyped-def]
        return next(c for c in self.base.cargos.values() if c.pedido_id == self.p.id)

    def ventas(self):  # type: ignore[no-untyped-def]
        return [v for v in self.base.ventas.values() if v.cargo_id == self.cargo().id]

    def unidad(self):  # type: ignore[no-untyped-def]
        return self.sistema.abrir(self.p.grupo_id)

    def acciones(self) -> list[AccionAuditoria]:
        return [e.accion for e in self.registro().entradas]

    def pagado(self, *, debito: bool = False) -> str:
        """Pagar, pasar por Webpay y volver: el pedido queda pagado. Devuelve el token."""
        token = self.pagar().token
        assert token is not None
        self.pasarela.pagar(token, debito=debito, ultimos4="7763" if debito else "2032")
        assert self.volver(token_ws=token).resultado is ResultadoPago.APROBADO
        return token


# --- Caso 1 y 2: venta normal con crédito y con débito por el total confirmado ------------------------------------


@pytest.mark.parametrize("debito", [False, True], ids=["caso-1-credito", "caso-2-debito"])
def test_caso_1_y_2_cobra_una_vez_el_total_exacto_con_credito_y_con_debito(debito: bool) -> None:
    escena = Escena()
    inicio = escena.pagar()
    assert inicio.url is not None and inicio.token is not None
    assert inicio.venta.monto == TOTAL == escena.p.total
    assert inicio.venta.total_confirmado_en == escena.p.total_confirmado_en
    escena.pasarela.pagar(inicio.token, debito=debito)

    vuelta = escena.volver(token_ws=inicio.token)

    assert (vuelta.resultado, vuelta.ya_registrado, vuelta.anulacion) == (ResultadoPago.APROBADO, False, None)
    assert escena.p.estado == "pagado" and escena.p.pagado_en == AHORA
    assert escena.p.referencia is not None and 4 <= len(escena.p.referencia) <= 6
    cargo = escena.cargo()
    assert (cargo.estado, cargo.monto_cobrado, cargo.monto_devuelto) == (EstadoCargo.PAGADO, TOTAL, 0)
    [participacion] = escena.base.participaciones.values()
    assert (participacion.estado, participacion.monto_cobrado) == (EstadoParticipacion.PAGADA, TOTAL)
    [venta] = escena.ventas()
    assert venta.tipo_tarjeta is (TipoTarjeta.DEBITO if debito else TipoTarjeta.CREDITO)
    assert escena.pasarela.cobrado(inicio.token) == TOTAL
    assert ("PedidoPagado", escena.p.id) in escena.base.eventos
    assert (escena.p.id, "total_confirmado", "pagado", "pago_aprobado", AHORA) in escena.base.transiciones
    assert escena.acciones() == [AccionAuditoria.PAGO_INICIAR, AccionAuditoria.PAGO_APROBAR]
    # Las condiciones que aceptó quien tocó «Pagar», con su versión y su huella
    assert escena.p.condiciones is not None
    assert (escena.p.condiciones.version, escena.p.condiciones.aceptadas_por) == ("0.2", escena.admin)


def test_caso_2_ninguna_rama_distingue_el_medio() -> None:
    credito, debito = Escena(), Escena()
    credito.pagado()
    debito.pagado(debito=True)
    for escena in (credito, debito):
        cargo = escena.cargo()
        assert (escena.p.estado, cargo.estado, cargo.monto_cobrado) == ("pagado", EstadoCargo.PAGADO, TOTAL)
        assert escena.base.transiciones[-1][1:4] == ("total_confirmado", "pagado", "pago_aprobado")


# --- Caso 3: anulación parcial de una línea no entregada ------------------------------------------------------------


@pytest.mark.parametrize("debito", [False, True], ids=["credito", "debito"])
def test_caso_3_anulacion_parcial_de_una_linea_a_la_misma_tarjeta(debito: bool) -> None:
    escena = Escena()
    token = escena.pagado(debito=debito)
    linea = escena.p.lineas[1]  # 2 × $8.745

    with escena.unidad() as unidad:
        estado = devoluciones.devolver_linea(unidad, escena.pasarela, escena.p.id, linea.id, escena.reloj.ahora())

    assert estado is EstadoAnulacion.HECHA
    cargo = escena.cargo()
    assert (cargo.estado, cargo.monto_devuelto) == (EstadoCargo.DEVUELTO_PARCIAL, linea.subtotal)
    # Lo cobrado menos lo devuelto calza al peso con lo que dice Transbank
    assert cargo.monto_cobrado - cargo.monto_devuelto == escena.pasarela.cobrado(token) == TOTAL - 17490
    assert escena.pasarela.consultar(token).status == "PARTIALLY_NULLIFIED"
    assert escena.p.lineas[1].monto_devuelto == linea.subtotal
    [anulacion] = escena.base.anulaciones.values()
    assert (anulacion.motivo, anulacion.pedido_linea_id) == (MotivoAnulacion.PRODUCTO_NO_ENTREGADO, linea.id)


# --- Caso 4: no se entrega nada, o se cancela antes de preparar -----------------------------------------------------


def test_caso_4_se_devuelve_el_total_envio_incluido() -> None:
    escena = Escena()
    token = escena.pagado()
    with escena.unidad() as unidad:
        assert devoluciones.devolver_todo(unidad, escena.pasarela, escena.p.id, AHORA) is EstadoAnulacion.HECHA
    cargo = escena.cargo()
    assert (cargo.estado, cargo.monto_devuelto) == (EstadoCargo.ANULADO, TOTAL)
    assert escena.pasarela.cobrado(token) == 0
    [anulacion] = escena.base.anulaciones.values()
    assert anulacion.motivo is MotivoAnulacion.CANCELACION and anulacion.monto == TOTAL


# --- Caso 5: el retorno llega dos veces ----------------------------------------------------------------------------


def test_caso_5_retorno_repetido_un_solo_cobro_y_un_solo_cargo() -> None:
    escena = Escena()
    token = escena.pagado()
    llamadas = list(escena.pasarela.llamadas)

    repetida = escena.volver(token_ws=token)

    assert (repetida.resultado, repetida.ya_registrado) == (ResultadoPago.APROBADO, True)
    assert escena.pasarela.llamadas == llamadas  # no llama a Transbank
    assert escena.pasarela.cobrado(token) == TOTAL
    assert len(escena.base.cargos) == 1 and len(escena.ventas()) == 1
    assert escena.acciones().count(AccionAuditoria.PAGO_APROBAR) == 1


def test_caso_5_el_segundo_commit_de_transbank_no_falla_y_no_paga_dos_veces() -> None:
    """La idempotencia es de MATU: aunque se llegue a llamar dos veces al commit (la venta quedó autorizando), la
    PasarelaFalsa devuelve la misma transacción y el pedido se paga una sola vez."""
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    escena.pasarela.caida = True
    assert escena.volver(token_ws=token).resultado is ResultadoPago.PENDIENTE
    escena.pasarela.caida = False
    escena.pasarela.confirmar(token)  # el commit sí llegó a Transbank antes de la caída
    escena.reloj.avanzar(timedelta(seconds=10))
    assert escena.volver(token_ws=token).resultado is ResultadoPago.APROBADO
    assert escena.pasarela.cobrado(token) == TOTAL and escena.cargo().monto_cobrado == TOTAL


# --- Caso 6: el retorno nunca llega --------------------------------------------------------------------------------


def test_caso_6_la_conciliacion_cierra_en_menos_de_15_minutos() -> None:
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)  # pagó y cerró el navegador
    escena.reloj.avanzar(timedelta(minutes=5))
    assert escena.conciliar().revisadas == 0  # todavía dentro de la vida de la venta
    escena.reloj.avanzar(timedelta(minutes=5))

    resultado = escena.conciliar()

    assert (resultado.revisadas, resultado.cerradas) == (1, 1)
    assert escena.p.estado == "pagado" and escena.p.pagado_en - AHORA < timedelta(minutes=15)  # type: ignore[operator]
    assert escena.pasarela.cobrado(token) == TOTAL


def test_caso_6_sin_pago_la_conciliacion_cierra_sin_cobro_por_formulario_vencido() -> None:
    escena = Escena()
    escena.pagar()
    escena.reloj.avanzar(VIDA)
    assert escena.conciliar().cerradas == 1
    [venta] = escena.ventas()
    assert (venta.estado, venta.motivo_cierre) == (EstadoVenta.RECHAZADA, MotivoCierre.FORMULARIO_VENCIDO)
    assert escena.cargo().estado is EstadoCargo.RECHAZADO and escena.p.pagado_en is None


# --- Caso 7: la pasarela no responde durante 20 minutos ------------------------------------------------------------


def test_caso_7_reintentos_sin_doble_cobro_y_alerta_a_operacion(caplog: pytest.LogCaptureFixture) -> None:
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    escena.pasarela.caida = True
    assert escena.volver(token_ws=token).resultado is ResultadoPago.PENDIENTE
    with caplog.at_level(logging.WARNING, logger="matu.payments"):
        for _ in range(4):  # cada 5 minutos, 20 minutos
            escena.reloj.avanzar(timedelta(minutes=5))
            assert escena.conciliar().pendientes == 1
    alertas = [r for r in caplog.records if getattr(r, "evento", None) == "pago_sin_respuesta"]
    assert alertas, "sin alerta a operación"
    assert all(token not in r.getMessage() for r in caplog.records)
    [venta] = escena.ventas()
    assert venta.estado is EstadoVenta.AUTORIZANDO and escena.p.pagado_en is None

    escena.pasarela.caida = False
    escena.reloj.avanzar(timedelta(minutes=5))
    assert escena.conciliar().cerradas == 1
    assert escena.pasarela.cobrado(token) == TOTAL and escena.cargo().monto_cobrado == TOTAL
    # El total venció mientras Webpay no respondía, y el mismo total se respeta (D-62-4, regla 2)
    assert escena.p.estado == "pagado"


# --- Caso 8: el total vencido no se cobra ---------------------------------------------------------------------------


def test_caso_8_total_vencido_409_sin_llamar_a_la_pasarela_y_el_pedido_no_cambia() -> None:
    """D-62-15 y decisión 225 (manda la arquitectura 8.1): estado-pedido con vencido; el pedido no vuelve a borrador."""
    escena = Escena()
    escena.reloj.avanzar(timedelta(minutes=15))
    with pytest.raises(TransicionInvalida) as error:
        escena.pagar()
    assert error.value.estado.value == "vencido"
    assert escena.pasarela.llamadas == [] and escena.base.ventas == {} and escena.base.cargos == {}
    assert escena.p.estado == "total_confirmado" and escena.p.condiciones is None


# --- Caso 9: devolución repetida o mayor que lo cobrado ------------------------------------------------------------


def test_caso_9_una_linea_se_devuelve_una_sola_vez_y_nunca_mas_que_lo_cobrado() -> None:
    escena = Escena()
    token = escena.pagado()
    linea = escena.p.lineas[0]
    with escena.unidad() as unidad:
        devoluciones.devolver_linea(unidad, escena.pasarela, escena.p.id, linea.id, AHORA)
        with pytest.raises(DevolucionInvalida):
            devoluciones.devolver_linea(unidad, escena.pasarela, escena.p.id, linea.id, AHORA)
        assert devoluciones.devolver_todo(unidad, escena.pasarela, escena.p.id, AHORA) is EstadoAnulacion.HECHA
        with pytest.raises(DevolucionInvalida):
            devoluciones.devolver_todo(unidad, escena.pasarela, escena.p.id, AHORA)
        with pytest.raises(DevolucionInvalida):
            devoluciones.devolver_linea(unidad, escena.pasarela, escena.p.id, escena.p.lineas[1].id, AHORA)
    cargo = escena.cargo()
    assert cargo.monto_devuelto == cargo.monto_cobrado == TOTAL and cargo.estado is EstadoCargo.ANULADO
    assert sum(escena.pasarela.transacciones[token].anulaciones) == TOTAL


# --- D-62-4: pago en curso, pago tardío y total reemplazado ---------------------------------------------------------


def test_regla_1_un_solo_pago_en_curso_y_despues_de_su_vida_otro_intento_reutiliza_el_cargo() -> None:
    escena = Escena()
    primero = escena.pagar()
    with pytest.raises(PagoEnCurso):
        escena.pagar()
    escena.reloj.avanzar(VIDA)
    segundo = escena.pagar()
    assert segundo.venta.id != primero.venta.id and len(escena.base.cargos) == 1


def test_regla_2_el_pago_tardio_del_mismo_total_se_respeta() -> None:
    escena = Escena()
    escena.reloj.avanzar(timedelta(minutes=14))
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    escena.reloj.avanzar(timedelta(minutes=3))  # vuelve con el total ya vencido

    vuelta = escena.volver(token_ws=token)

    assert vuelta.resultado is ResultadoPago.APROBADO_TARDIO
    assert escena.p.estado == "pagado"
    vence = AHORA + timedelta(minutes=15)
    assert (escena.p.id, "total_confirmado", "vencido", "total_vencio", vence) in escena.base.transiciones
    assert escena.base.transiciones[-1][1:4] == ("vencido", "pagado", "pago_aprobado")
    assert escena.pasarela.cobrado(token) == TOTAL


@pytest.mark.parametrize("cambio", ["cancelado", "reconfirmado", "borrador"])
def test_regla_3_el_pago_de_un_total_que_ya_no_es_el_del_pedido_se_anula_completo(cambio: str) -> None:
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    # Mientras pagaba: se canceló (o se retiró despacho, o se borró la persona), o pasó la vida de la venta y se volvió
    # a confirmar otro total, o se volvió al carrito
    escena.reloj.avanzar(VIDA)
    if cambio == "cancelado":
        escena.p.estado = "cancelado"
    elif cambio == "reconfirmado":
        escena.base.volver_a_confirmar(escena.p, escena.reloj.ahora())
    else:
        escena.p.estado, escena.p.total_confirmado_en, escena.p.total_vence_en = "borrador", None, None

    vuelta = escena.volver(token_ws=token)

    assert (vuelta.resultado, vuelta.anulacion) == (ResultadoPago.ANULADO, EstadoAnulacion.HECHA)
    assert escena.p.pagado_en is None and escena.p.estado != "pagado"  # el pedido no cambia
    assert escena.pasarela.cobrado(token) == 0  # anulado completo, a la misma tarjeta
    [venta] = escena.ventas()
    assert venta.estado is EstadoVenta.APROBADA and venta.anulacion_total
    [anulacion] = escena.base.anulaciones.values()
    assert (anulacion.motivo, anulacion.monto, anulacion.estado) == (
        MotivoAnulacion.PAGO_TARDIO,
        TOTAL,
        EstadoVenta.APROBADA,
    )
    # El cargo no cuenta la anulación del pago tardío: queda rechazado, sin cobro ni devolución
    cargo = escena.cargo()
    assert (cargo.estado, cargo.monto_cobrado, cargo.monto_devuelto) == (EstadoCargo.RECHAZADO, 0, 0)
    assert ("PagoAnulado", escena.p.id) in escena.base.eventos
    assert AccionAuditoria.PAGO_ANULAR in escena.acciones()
    # Repetido, sigue anulado y no vuelve a anular
    repetida = escena.volver(token_ws=token)
    assert (repetida.resultado, repetida.ya_registrado, repetida.anulacion) == (
        ResultadoPago.ANULADO,
        True,
        EstadoAnulacion.HECHA,
    )
    assert len(escena.pasarela.transacciones[token].anulaciones) == 1


def test_regla_3_si_ya_lo_pago_otra_venta_la_segunda_se_anula_y_el_pedido_queda_pagado_una_vez() -> None:
    escena = Escena()
    primera = escena.pagar().token
    assert primera is not None
    escena.pasarela.pagar(primera)  # pagó y no volvió
    escena.reloj.avanzar(VIDA)  # la primera ya no está en curso: un segundo intento
    segunda = escena.pagar().token
    assert segunda is not None
    escena.pasarela.pagar(segunda)
    assert escena.volver(token_ws=segunda).resultado is ResultadoPago.APROBADO
    assert escena.conciliar().cerradas == 1  # la primera llega tarde

    assert escena.pasarela.cobrado(primera) + escena.pasarela.cobrado(segunda) == TOTAL
    assert escena.cargo().monto_cobrado == TOTAL
    assert sum(1 for v in escena.ventas() if v.estado is EstadoVenta.APROBADA and not v.anulacion_total) == 1


def test_la_anulacion_que_falla_se_reintenta_sin_devolver_dos_veces() -> None:
    """D-62-6: si refund se hizo pero la respuesta se perdió, la conciliación pregunta el status y no repite."""

    class PierdeLaRespuesta(PasarelaFalsa):
        perder = True

        def anular(self, token: str, monto: int) -> RespuestaAnulacion:
            respuesta = super().anular(token, monto)
            if self.perder:
                self.perder = False
                raise PasarelaNoDisponible()
            return respuesta

    escena = Escena(pasarela=PierdeLaRespuesta())
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    escena.p.estado = "cancelado"
    vuelta = escena.volver(token_ws=token)
    assert (vuelta.resultado, vuelta.anulacion) == (ResultadoPago.ANULADO, EstadoAnulacion.EN_CURSO)

    escena.reloj.avanzar(timedelta(minutes=5))
    assert escena.conciliar().anulaciones_hechas == 1

    assert escena.pasarela.transacciones[token].anulaciones == [TOTAL]  # una sola anulación en Transbank
    [anulacion] = escena.base.anulaciones.values()
    assert anulacion.estado is EstadoVenta.APROBADA


# --- La vuelta: salió, se acabó el tiempo, desconocida --------------------------------------------------------------


def test_salio_de_webpay_sin_commit_y_el_reintento_reutiliza_el_cargo() -> None:
    escena = Escena()
    venta = escena.pagar().venta
    assert venta.token is not None
    sesion = venta.session_id or ""
    vuelta = escena.volver(TBK_TOKEN=venta.token, TBK_ORDEN_COMPRA=venta.buy_order, TBK_ID_SESION=sesion)

    assert vuelta.resultado is ResultadoPago.ABANDONADO
    assert "commit" not in escena.pasarela.llamadas
    assert escena.cargo().estado is EstadoCargo.RECHAZADO
    otro = escena.pagar()  # rechazado → pendiente (D-62-11)
    assert escena.cargo().estado is EstadoCargo.PENDIENTE and otro.venta.cargo_id == venta.cargo_id


def test_se_acabo_el_tiempo_del_formulario() -> None:
    escena = Escena()
    venta = escena.pagar().venta
    vuelta = escena.volver(TBK_ORDEN_COMPRA=venta.buy_order, TBK_ID_SESION=venta.session_id or "")
    assert vuelta.resultado is ResultadoPago.TIEMPO_AGOTADO
    [cerrada] = escena.ventas()
    assert cerrada.motivo_cierre is MotivoCierre.FORMULARIO_VENCIDO


@pytest.mark.parametrize(
    "campos",
    [
        {"token_ws": "no-es-de-matu"},
        {"TBK_ORDEN_COMPRA": "no-es-de-matu", "TBK_ID_SESION": "tampoco"},
        {"TBK_ORDEN_COMPRA": "solo-la-orden"},
    ],
)
def test_lo_que_no_es_de_matu_es_desconocido_sin_llamar_a_transbank(campos: dict[str, str]) -> None:
    escena = Escena()
    escena.pagar()
    llamadas = list(escena.pasarela.llamadas)
    with pytest.raises(VentaDesconocida):
        escena.volver(**campos)
    assert escena.pasarela.llamadas == llamadas


def test_la_orden_sola_o_con_otra_sesion_no_encuentra_la_venta() -> None:
    escena = Escena()
    venta = escena.pagar().venta
    with pytest.raises(VentaDesconocida):
        escena.volver(TBK_ORDEN_COMPRA=venta.buy_order, TBK_ID_SESION="otra-sesion")


# --- pagar: 412, condiciones, 503 e idempotencia --------------------------------------------------------------------


def test_412_si_otra_persona_cambio_el_pedido_y_no_se_cobra() -> None:
    escena = Escena()
    with pytest.raises(VersionDesactualizada):
        escena.pagar(if_match='"v1"')
    assert escena.pasarela.llamadas == [] and escena.base.ventas == {}


def test_condiciones_cambiaron_si_la_version_o_la_huella_no_son_las_publicadas() -> None:
    escena = Escena()
    for aceptacion in (Aceptacion("0.1", "a" * 64), Aceptacion("0.2", "b" * 64)):
        with pytest.raises(CondicionesCambiaron) as error:
            escena.pagar(aceptacion=aceptacion)
        assert error.value.version_vigente == "0.2"
    assert escena.pasarela.llamadas == [] and escena.p.condiciones is None


def test_503_si_webpay_no_responde_la_venta_queda_en_error_y_no_es_un_pago_en_curso() -> None:
    escena = Escena()
    escena.pasarela.caida = True
    with pytest.raises(PagoNoIniciado):
        escena.pagar()
    [venta] = escena.base.ventas.values()
    assert venta.estado is EstadoVenta.ERROR and venta.token is None
    assert escena.cargo().estado is EstadoCargo.PENDIENTE and escena.cargo().monto_cobrado == 0
    escena.pasarela.caida = False
    assert escena.pagar().venta.estado is EstadoVenta.INICIADA  # no bloquea un intento nuevo


def test_sin_pasarela_configurada_no_se_escribe_nada() -> None:
    escena = Escena()
    with pytest.raises(SinPasarela):
        escena.pagar(pasarela=None)
    assert escena.base.cargos == {} and escena.p.condiciones is None


def test_la_misma_clave_devuelve_la_venta_como_esta_ahora() -> None:
    """Decisión 229: iniciada y vigente, la misma url y el mismo token; terminada, los dos en None."""
    escena = Escena()
    inicio = escena.pagar()
    otra = repetir(inicio.venta, escena.pasarela, escena.reloj.ahora(), VIDA)
    assert (otra.url, otra.token) == (inicio.url, inicio.token)
    assert inicio.token is not None
    escena.pasarela.pagar(inicio.token)
    escena.volver(token_ws=inicio.token)
    venta = escena.base.ventas[inicio.venta.id]
    assert (repetir(venta, escena.pasarela, escena.reloj.ahora(), VIDA).url, venta.estado) == (
        None,
        EstadoVenta.APROBADA,
    )
