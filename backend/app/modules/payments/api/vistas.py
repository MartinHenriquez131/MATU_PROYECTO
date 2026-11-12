"""De lo que arma application/lectura.py a los esquemas del contrato (decisiones 236 a 239). Instantes en UTC."""

from datetime import UTC, datetime

from app.modules.ordering.api.esquemas import ProductoPedido
from app.modules.payments.api.esquemas import (
    Comprobante,
    CondicionesComprobante,
    CorreoComprobante,
    Devolucion,
    IntentoPago,
    LineaComprobante,
    PagoVista,
    PagoVistaObservador,
    Tarjeta,
)
from app.modules.payments.application import lectura
from app.modules.payments.application.ports import LineaPagada


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


def _producto(linea: LineaPagada) -> ProductoPedido:
    return ProductoPedido(
        id=linea.producto_id,
        nombre=linea.nombre,
        presentacion=linea.presentacion,
        unidad=linea.unidad,  # type: ignore[arg-type]
        unidades_por_envase=linea.unidades_por_envase,
    )


def _devolucion(d: lectura.Devolucion) -> Devolucion:
    return Devolucion(
        motivo=d.motivo,  # type: ignore[arg-type]
        monto=d.monto,
        producto=None if d.producto is None else _producto(d.producto),
        estado=d.estado.value,
        solicitada_en=_utc(d.solicitada_en),  # type: ignore[arg-type]
        hecha_en=_utc(d.hecha_en),
        ultimos4=d.ultimos4,
    )


def _comprobante(c: lectura.Comprobante) -> Comprobante:
    return Comprobante(
        referencia=c.referencia,
        pagado_en=_utc(c.pagado_en),  # type: ignore[arg-type]
        lineas=[
            LineaComprobante(
                producto=_producto(x), cantidad=x.cantidad, precio_unitario=x.precio_unitario, subtotal=x.subtotal
            )
            for x in c.lineas
        ],
        subtotal_productos=c.subtotal_productos,
        costo_envio=c.costo_envio,
        total=c.total,
        pagaste_tu=c.pagaste_tu,
        tarjeta=None
        if c.tarjeta is None
        else Tarjeta(tipo=c.tarjeta.tipo.value, ultimos4=c.tarjeta.ultimos4, cuotas=c.tarjeta.cuotas),
        codigo_autorizacion=c.codigo_autorizacion,
        vendedor=c.vendedor,  # type: ignore[arg-type]
        ventana_entrega=c.ventana_entrega,
        canal_reclamo=c.canal_reclamo,
        condiciones=CondicionesComprobante(
            version=c.condiciones.version,
            aceptadas_en=_utc(c.condiciones.aceptadas_en),  # type: ignore[arg-type]
            huella=c.condiciones.huella,
            enlace=c.enlace_condiciones,
        ),
        tardio=c.tardio,
        devoluciones=[_devolucion(d) for d in c.devoluciones],
        precios_de_ejemplo=c.precios_de_ejemplo,
        pago_de_prueba=c.pago_de_prueba,
        correo=None if c.correo is None else CorreoComprobante(destino=c.correo.destino, enviado=c.correo.enviado),
    )


def vista_pago(estado: lectura.EstadoDelPago) -> PagoVista:
    intento = estado.intento
    return PagoVista(
        pedido_id=estado.pedido_id,
        estado=estado.estado,  # type: ignore[arg-type]
        pago_en_curso=estado.pago_en_curso,
        intento=None
        if intento is None
        else IntentoPago(
            id=intento.id,
            resultado=intento.resultado.value,
            iniciado_en=_utc(intento.iniciado_en),  # type: ignore[arg-type]
            cerrado_en=_utc(intento.cerrado_en),
            es_tuyo=intento.es_tuyo,
        ),
        comprobante=None if estado.comprobante is None else _comprobante(estado.comprobante),
        devoluciones=[_devolucion(d) for d in estado.devoluciones],
        pago_de_prueba=estado.pago_de_prueba,
    )


def vista_observador(observador: lectura.PagoObservador) -> PagoVistaObservador:
    return PagoVistaObservador(pedido_id=observador.pedido_id, estado=observador.estado)  # type: ignore[arg-type]
