"""La proyección del pedido según el rol (C3; decisiones 198, 202 a 205): PedidoVista o PedidoVistaObservador.

El celular de una cuenta va enmascarado, como en GET /v1/cuenta; uno escrito va completo, para que quien lo escribió
lo revise (decisión 203). El resumen solo con el total confirmado vigente (C1). La entrega solo para admin, cuidador
y pagador, y solo mientras exista su copia (con el total confirmado o vencido).
"""

from datetime import UTC, datetime

from app.modules.iam.domain.recuperacion import enmascarar_celular
from app.modules.ordering.api.esquemas import (
    CambioDeLinea,
    ComercioVista,
    CondicionesVigentes,
    EntregaVista,
    LineaPedido,
    LineaSalida,
    ParteComercio,
    PedidoVista,
    PedidoVistaObservador,
    ProductoPedido,
    ResumenAntesDePagar,
)
from app.modules.ordering.application.pedidos import ORIGEN_CELULAR_CUENTA
from app.modules.ordering.domain.estados import Estado, estado_visible, vigencia_segundos
from app.modules.ordering.domain.pedido import (
    PILOTO,
    Comercio,
    Linea,
    Pedido,
    Producto,
    cambio_de,
    partes_por_comercio,
    ve_entrega,
)
from app.modules.ordering.infrastructure.condiciones import ENLACE, Condiciones

CON_ENTREGA = frozenset({Estado.TOTAL_CONFIRMADO, Estado.VENCIDO})


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


def _comercio(c: Comercio) -> ComercioVista:
    return ComercioVista(id=c.id, nombre_fantasia=c.nombre_fantasia, ficticio=c.ficticio)


def _producto(p: Producto) -> ProductoPedido:
    return ProductoPedido(
        id=p.id,
        nombre=p.nombre,
        presentacion=p.presentacion,
        unidad=p.unidad,  # type: ignore[arg-type]
        unidades_por_envase=p.unidades_por_envase,
    )


def _linea(linea: Linea, confirmado: bool) -> LineaPedido:
    cambio = cambio_de(linea, confirmado)
    return LineaPedido(
        id=linea.id,
        producto=_producto(linea.producto),
        cantidad=linea.cantidad,
        comercio=_comercio(linea.comercio),
        precio_unitario=linea.precio_unitario,
        subtotal=linea.subtotal,
        regla_faltante=linea.regla,
        retracto_pierde_al_abrir=linea.retracto_pierde_al_abrir,
        cambio=None
        if cambio is None
        else CambioDeLinea(
            precio_antes=cambio.precio_antes,
            comercio_antes=None if cambio.comercio_antes is None else _comercio(cambio.comercio_antes),
        ),
    )


def _comunes(pedido: Pedido, ahora: datetime, costo_envio_vigente: int, precios_de_ejemplo: bool) -> dict[str, object]:
    estado = estado_visible(pedido.estado, pedido.total_vence_en, ahora)
    confirmado = pedido.confirmado
    lineas = pedido.lineas_que_quedan() if confirmado else pedido.lineas
    return {
        "id": pedido.id,
        "persona_cuidada_id": pedido.persona_id,
        "estado": estado,
        "precios_de_ejemplo": precios_de_ejemplo,
        "lineas": [_linea(linea, confirmado) for linea in lineas],
        "salieron": [
            LineaSalida(producto=_producto(x.producto), cantidad=x.cantidad, comercio=_comercio(x.comercio_carrito))
            for x in pedido.salieron()
        ],
        "comercios": [
            ParteComercio(comercio=_comercio(p.comercio), subtotal_productos=p.subtotal_productos)
            for p in partes_por_comercio(lineas)
        ],
        "subtotal_productos": pedido.subtotal_productos,
        # En borrador, el envío vigente, para informar antes de confirmar (C5)
        "costo_envio": pedido.costo_envio if confirmado else costo_envio_vigente,
        "total": pedido.total,
        "total_confirmado_en": _utc(pedido.total_confirmado_en),
        "vence_en": _utc(pedido.total_vence_en),
        "ventana_entrega": PILOTO.ventana_entrega,
        "creado_en": _utc(pedido.creado_en),
        "actualizado_en": _utc(pedido.actualizado_en),
    }


def vista_pedido(
    pedido: Pedido,
    *,
    rol: str,
    ahora: datetime,
    costo_envio_vigente: int,
    precios_de_ejemplo: bool,
    condiciones: Condiciones,
    celular_de_quien_lee: str | None,
) -> PedidoVista | PedidoVistaObservador:
    comunes = _comunes(pedido, ahora, costo_envio_vigente, precios_de_ejemplo)
    if not ve_entrega(rol):
        return PedidoVistaObservador.model_validate(comunes)
    estado = comunes["estado"]
    entrega = None
    if pedido.entrega is not None and estado in CON_ENTREGA:
        e = pedido.entrega
        de_cuenta = e.telefono_origen == ORIGEN_CELULAR_CUENTA
        entrega = EntregaVista(
            calle=e.calle,
            numero=e.numero,
            depto=e.depto,
            comuna=e.comuna,
            region=e.region,
            referencia=e.referencia,
            telefono_contacto=(enmascarar_celular(e.telefono) or "") if de_cuenta else e.telefono,
            telefono_origen="celular_cuenta" if de_cuenta else "escrito",
            telefono_es_tuyo=celular_de_quien_lee is not None and celular_de_quien_lee == e.telefono,
        )
    resumen = None
    if estado is Estado.TOTAL_CONFIRMADO:
        resumen = ResumenAntesDePagar(
            vendedor="MATU, piloto académico, sin persona jurídica",
            boleta="En este piloto no se emite boleta",
            ventana_entrega="Entre 24 y 48 horas hábiles",
            canal_reclamo=PILOTO.canal_reclamo,
            condiciones=CondicionesVigentes(version=condiciones.version, huella=condiciones.huella, enlace=ENLACE),
        )
    return PedidoVista.model_validate(
        {
            **comunes,
            "etag": pedido.etag,
            "vigencia_segundos": vigencia_segundos(estado, pedido.total_vence_en, ahora),  # type: ignore[arg-type]
            "entrega": entrega,
            "resumen": resumen,
        }
    )
