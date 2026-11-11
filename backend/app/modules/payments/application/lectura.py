"""GET /v1/pedidos/{pedido_id}/pago y GET /v1/personas-cuidadas/{persona_id}/pedido-pagado (decisiones 236 a 239;
D-62-2, D-62-3 y D-62-7).

- admin, cuidador y pagador: el estado del pago, si hay un pago en curso, el último intento, las devoluciones y, si se
  pagó, el comprobante. La tarjeta, el código de autorización y el correo **solo para quien pagó** (D-62-2).
- observador: solo si está pagado (DTO distinto, decisión 127). No lee el cargo (RLS, migración 0024).
- Nunca el buy_order, el session_id, el token ni la respuesta de Transbank. No pide despacho y no se audita.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.modules.ordering.domain.pedido import PILOTO
from app.modules.payments.application.cobro import EstadoAnulacion
from app.modules.payments.application.ports import CondicionesAceptadas, LineaPagada, PedidoCobro, RepositorioPagos
from app.modules.payments.domain.cargo import EstadoCargo
from app.modules.payments.domain.venta import (
    Anulacion,
    EstadoVenta,
    ResultadoPago,
    TipoTarjeta,
    Venta,
    en_curso,
    resultado_de,
)

ROLES_QUE_VEN_EL_PAGO = frozenset({"admin", "cuidador", "pagador"})
ROLES_QUE_LEEN = ROLES_QUE_VEN_EL_PAGO | {"observador"}

# EstadoPago desde cargo.estado (decisión 236)
ESTADO_PAGO: dict[EstadoCargo | None, str] = {
    None: "sin_intento",
    EstadoCargo.PENDIENTE: "pendiente",
    EstadoCargo.PAGADO: "aprobado",
    EstadoCargo.RECHAZADO: "no_aprobado",
    EstadoCargo.DEVUELTO_PARCIAL: "devuelto_parcial",
    EstadoCargo.ANULADO: "anulado",
}
CON_COMPROBANTE = frozenset({"aprobado", "devuelto_parcial", "anulado"})

ENLACE_CONDICIONES = "/v1/condiciones-pedido?version={version}"

# D-62-3 y P-62-5: en el piloto el comprobante no se envía por correo. Mientras sea False, Comprobante.correo va en
# null (decisión 249, observación 4 del cierre del analista): no se muestra un destino al que nada se envía
CORREO_COMPROBANTE_ACTIVO = False


@dataclass(frozen=True)
class Intento:
    id: uuid.UUID
    resultado: ResultadoPago
    iniciado_en: datetime
    cerrado_en: datetime | None
    es_tuyo: bool


@dataclass(frozen=True)
class Devolucion:
    motivo: str
    monto: int
    producto: LineaPagada | None
    estado: EstadoAnulacion
    solicitada_en: datetime
    hecha_en: datetime | None
    ultimos4: str | None


@dataclass(frozen=True)
class Tarjeta:
    tipo: TipoTarjeta
    ultimos4: str
    cuotas: int


@dataclass(frozen=True)
class Correo:
    destino: str
    enviado: bool


@dataclass(frozen=True)
class Comprobante:
    referencia: str
    pagado_en: datetime
    lineas: tuple[LineaPagada, ...]
    subtotal_productos: int
    costo_envio: int
    total: int
    pagaste_tu: bool
    tarjeta: Tarjeta | None
    codigo_autorizacion: str | None
    vendedor: str
    ventana_entrega: str
    canal_reclamo: str
    condiciones: CondicionesAceptadas
    enlace_condiciones: str
    tardio: bool
    devoluciones: tuple[Devolucion, ...]
    precios_de_ejemplo: bool
    pago_de_prueba: bool
    correo: Correo | None


@dataclass(frozen=True)
class EstadoDelPago:
    pedido_id: uuid.UUID
    estado: str
    pago_en_curso: bool
    intento: Intento | None
    comprobante: Comprobante | None
    devoluciones: tuple[Devolucion, ...]
    # Decisión 248: el sello «Pago de prueba» también sin comprobante (un pago anulado, diseño 7.9)
    pago_de_prueba: bool = True


@dataclass(frozen=True)
class PagoObservador:
    pedido_id: uuid.UUID
    estado: str


def _devoluciones(
    anulaciones: list[Anulacion],
    ventas: dict[uuid.UUID, Venta],
    lineas: dict[uuid.UUID, LineaPagada],
    lector: uuid.UUID,
) -> tuple[Devolucion, ...]:
    resultado: list[Devolucion] = []
    for a in sorted(anulaciones, key=lambda x: (x.solicitada_en, str(x.id))):
        venta = ventas.get(a.venta_id)
        es_quien_pago = venta is not None and venta.usuario_id == lector
        resultado.append(
            Devolucion(
                motivo=a.motivo.value,
                monto=a.monto,
                producto=None if a.pedido_linea_id is None else lineas.get(a.pedido_linea_id),
                estado=EstadoAnulacion.HECHA if a.hecha else EstadoAnulacion.EN_CURSO,
                solicitada_en=a.solicitada_en,
                hecha_en=a.hecha_en,
                ultimos4=venta.ultimos4 if es_quien_pago and venta is not None else None,
            )
        )
    return tuple(resultado)


def estado_del_pago(
    repositorio: RepositorioPagos,
    pedido: PedidoCobro,
    lector: uuid.UUID,
    correo_de_quien_lee: str | None,
    ahora: datetime,
    vida: timedelta,
    *,
    precios_de_ejemplo: bool,
    pago_de_prueba: bool,
) -> EstadoDelPago:
    cargo = repositorio.cargo_de(pedido.id)
    ventas = repositorio.ventas(cargo.id) if cargo is not None else []
    anulaciones = repositorio.anulaciones(cargo.id) if cargo is not None else []
    lineas = {x.id: x for x in repositorio.lineas_pagadas(pedido.id)} if anulaciones or pedido.pagado_en else {}
    por_id = {v.id: v for v in ventas}
    devoluciones = _devoluciones(anulaciones, por_id, lineas, lector)

    intentos = [v for v in ventas if v.estado is not EstadoVenta.ERROR]
    ultima = max(intentos, key=lambda v: (v.creado_en, str(v.id)), default=None)
    intento = None
    if ultima is not None:
        resultado = resultado_de(ultima)
        assert resultado is not None
        intento = Intento(
            id=ultima.id,
            resultado=resultado,
            iniciado_en=ultima.creado_en,
            cerrado_en=ultima.cerrada_en if ultima.estado in (EstadoVenta.APROBADA, EstadoVenta.RECHAZADA) else None,
            es_tuyo=ultima.usuario_id == lector,
        )

    estado = ESTADO_PAGO[None if cargo is None else cargo.estado]
    comprobante = None
    pagadora = next(
        (v for v in ventas if v.estado is EstadoVenta.APROBADA and not v.anulada_por_pago_tardio), None
    )
    condiciones = repositorio.condiciones_aceptadas(pedido.id)
    if (
        estado in CON_COMPROBANTE
        and pedido.pagado_en is not None
        and pagadora is not None
        and condiciones is not None
        and pedido.referencia is not None
    ):
        pagaste_tu = pagadora.usuario_id == lector
        quedan = tuple(x for x in lineas.values() if not x.salio)
        comprobante = Comprobante(
            referencia=pedido.referencia,
            pagado_en=pedido.pagado_en,
            lineas=quedan,
            subtotal_productos=pedido.subtotal_productos,
            costo_envio=pedido.costo_envio,
            total=pedido.total,
            pagaste_tu=pagaste_tu,
            tarjeta=(
                Tarjeta(pagadora.tipo_tarjeta, pagadora.ultimos4, pagadora.cuotas or 0)
                if pagaste_tu and pagadora.tipo_tarjeta is not None and pagadora.ultimos4 is not None
                else None
            ),
            codigo_autorizacion=pagadora.codigo_autorizacion if pagaste_tu else None,
            vendedor=PILOTO.vendedor,
            ventana_entrega=PILOTO.ventana_entrega,
            canal_reclamo=PILOTO.canal_reclamo,
            condiciones=condiciones,
            enlace_condiciones=ENLACE_CONDICIONES.format(version=condiciones.version),
            tardio=pagadora.tardia,
            devoluciones=devoluciones,
            precios_de_ejemplo=precios_de_ejemplo,
            pago_de_prueba=pago_de_prueba,
            # D-62-3 (P-62-5) y decisión 249: en el piloto el comprobante no se envía, y correo va en null
            correo=Correo(destino=correo_de_quien_lee, enviado=True)
            if CORREO_COMPROBANTE_ACTIVO and pagaste_tu and correo_de_quien_lee is not None
            else None,
        )
    return EstadoDelPago(
        pedido_id=pedido.id,
        estado=estado,
        pago_en_curso=any(en_curso(v, ahora, vida) for v in ventas),
        intento=intento,
        comprobante=comprobante,
        devoluciones=devoluciones,
        pago_de_prueba=pago_de_prueba,
    )


def vista_observador(pedido: PedidoCobro) -> PagoObservador:
    return PagoObservador(pedido_id=pedido.id, estado="pagado" if pedido.pagado_en is not None else "sin_pagar")
