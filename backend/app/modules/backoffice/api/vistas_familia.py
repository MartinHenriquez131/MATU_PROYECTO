"""De lo que arma backoffice/application/pedidos_familia.py, y del retracto, a los esquemas del contrato (MATU-92).

Instantes en UTC. Ninguna vista trae ``codigo_*``, la referencia opaca de la parte, quién pidió un retracto (solo
``es_tuyo``) ni nada de la cuenta del encargado (C15, C18). Los montos, solo en las vistas de quien ve el pago (C5).
"""

import base64
import binascii
import uuid
from datetime import UTC, datetime

from app.core.errores import ErrorMATU
from app.modules.backoffice.api.esquemas import (
    ComercioDeLaParte,
    LineaDeLaParte,
    LineaDelRetracto,
    LineaParaRetracto,
    ParteDelPedido,
    PedidoPagadoFila,
    PedidoPagadoFilaObservador,
    PedidoPagadoFilaPagaste,
    ProductoDeLaFila,
    ResumenProductos,
    RetractoVistaFamilia,
    SeguimientoPedido,
    SeguimientoPedidoPagaste,
)
from app.modules.backoffice.application.pedidos_familia import LineaLeida, PedidoDeLaFamilia
from app.modules.ordering.api.esquemas import ProductoPedido
from app.modules.payments.application.ports import Unidad
from app.modules.payments.application.retractos import RepositorioRetractos, Retracto, monto_de


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


def _producto(x: LineaLeida) -> ProductoPedido:
    return ProductoPedido(
        id=x.producto_id,
        nombre=x.nombre,
        presentacion=x.presentacion,
        unidad=x.unidad,  # type: ignore[arg-type]
        unidades_por_envase=x.unidades_por_envase,
    )


def _productos(p: PedidoDeLaFamilia) -> dict[str, object]:
    lineas = p.lineas
    return {
        "productos": [ProductoDeLaFila(producto=_producto(x), cantidad=x.cantidad) for x in lineas],
        "resumen_productos": None if not lineas else ResumenProductos(primero=lineas[0].nombre, otros=len(lineas) - 1),
        "productos_borrados": p.productos_borrados,
    }


def _con_pago(p: PedidoDeLaFamilia) -> dict[str, object]:
    c, a = p.cabecera, p.acciones
    assert a is not None and p.devuelto is not None and c.referencia is not None
    return {
        "pedido_id": c.id,
        "referencia": c.referencia,
        "pagado_en": _utc(c.pagado_en),
        "estado": p.estado.value,
        "entregado_en": _utc(c.entregado_en),
        "cancelado_en": _utc(c.cancelado_en),
        "total": c.total,
        "devuelto": p.devuelto,
        "devuelto_todo": p.devuelto >= c.total,
        "puede_cancelar": a.puede_cancelar,
        "cancelar_motivo": None if a.motivo_cancelar is None else a.motivo_cancelar.value,
        "puede_arrepentirse": a.puede_arrepentirse,
        "arrepentirse_motivo": None if a.motivo_arrepentirse is None else a.motivo_arrepentirse.value,
        "plazo_hasta": _utc(a.plazo_hasta),
        "plazo_correo_hasta": _utc(a.plazo_correo_hasta),
    }


def fila(p: PedidoDeLaFamilia) -> PedidoPagadoFila:
    return PedidoPagadoFila.model_validate({**_con_pago(p), **_productos(p)})


def fila_pagaste(p: PedidoDeLaFamilia) -> PedidoPagadoFilaPagaste:
    """MATU-116 (C5): la forma de «Paga»; el esquema exige puede_cancelar en false (el rol nunca alcanza)."""
    return PedidoPagadoFilaPagaste.model_validate({"vista": "pagaste", **_con_pago(p), **_productos(p)})


def fila_observador(p: PedidoDeLaFamilia) -> PedidoPagadoFilaObservador:
    return PedidoPagadoFilaObservador.model_validate(
        {
            "vista": "se_informa",
            "pedido_id": p.cabecera.id,
            "pagado_en": _utc(p.cabecera.pagado_en),
            # MATU-113 (decisión 472): el estado real de familia, ya no siempre «pagado»
            "estado": p.estado.value,
            "entregado_en": _utc(p.cabecera.entregado_en),
            **_productos(p),
        }
    )


def _partes(p: PedidoDeLaFamilia) -> list[ParteDelPedido]:
    return [
        ParteDelPedido(
            comercio=ComercioDeLaParte(nombre_fantasia=x.nombre_fantasia, ficticio=x.ficticio),
            estado=x.estado,  # type: ignore[arg-type]
            cancelada_por=None if x.cancelada_por is None else x.cancelada_por.value,
            lineas=[
                LineaDeLaParte(
                    linea_id=y.id, producto=_producto(y), cantidad=y.cantidad, unidades_faltantes=y.unidades_faltantes
                )
                for y in x.lineas
            ],
        )
        for x in p.partes
    ]


def seguimiento(p: PedidoDeLaFamilia) -> SeguimientoPedido | SeguimientoPedidoPagaste:
    """MATU-116 (C5): para el observador que pagó, la forma de «Paga» con puede_cancelar siempre en false."""
    if p.pagaste:
        return SeguimientoPedidoPagaste.model_validate(
            {**_con_pago(p), "partes": _partes(p), "productos_borrados": p.productos_borrados}
        )
    return SeguimientoPedido.model_validate(
        {**_con_pago(p), "partes": _partes(p), "productos_borrados": p.productos_borrados}
    )


def linea_para_retracto(x: LineaLeida, ya_pedidas: int, disponibles: int) -> LineaParaRetracto:
    return LineaParaRetracto(
        linea_id=x.id,
        producto=_producto(x),
        entregadas=x.entregadas,
        ya_pedidas=ya_pedidas,
        disponibles=disponibles,
        precio_pagado=x.precio_unitario,
        retracto_pierde_al_abrir=x.retracto_pierde_al_abrir,
    )


def _datos_retracto(unidad: Unidad, retractos: RepositorioRetractos, r: Retracto) -> dict[str, object]:
    pagadas = {x.id: x for x in unidad.repositorio.lineas_pagadas(r.pedido_id)}
    lineas = []
    for linea_id, cantidad in sorted(retractos.lineas_de(r.id).items(), key=lambda par: str(par[0])):
        x = pagadas[linea_id]
        lineas.append(
            LineaDelRetracto(
                linea_id=linea_id,
                producto=ProductoPedido(
                    id=x.producto_id,
                    nombre=x.nombre,
                    presentacion=x.presentacion,
                    unidad=x.unidad,  # type: ignore[arg-type]
                    unidades_por_envase=x.unidades_por_envase,
                ),
                cantidad=cantidad,
                monto=cantidad * x.precio_unitario,
            )
        )
    return {
        "id": r.id,
        "pedido_id": r.pedido_id,
        "estado": r.estado,
        "solicitado_en": _utc(r.solicitado_en),
        "plazo_hasta": _utc(r.plazo_hasta),
        "incluye_envio": r.incluye_envio,
        "monto": monto_de(unidad, retractos, r),
        "origen": r.origen,
        "lineas": lineas,
        "resuelto_en": _utc(r.resuelto_en),
    }


def retracto_familia(
    unidad: Unidad, retractos: RepositorioRetractos, r: Retracto, usuario_id: uuid.UUID
) -> RetractoVistaFamilia:
    return RetractoVistaFamilia.model_validate(
        {
            **_datos_retracto(unidad, retractos, r),
            "es_tuyo": r.solicitado_por == usuario_id,
            "motivo_rechazo": r.motivo_rechazo,
        }
    )


# --- El cursor de la lista: base64url de "<pagado_en ISO>|<id>", como el de los accesos de relevo -----------------


def codificar_cursor(posicion: tuple[datetime, uuid.UUID]) -> str:
    crudo = f"{posicion[0].astimezone(UTC).isoformat()}|{posicion[1]}".encode("ascii")
    return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode("ascii")


def decodificar_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        crudo = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
        instante, identificador = crudo.split("|")
        pagado_en = datetime.fromisoformat(instante)
        if pagado_en.tzinfo is None:
            raise ValueError
        return pagado_en, uuid.UUID(identificador)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": "cursor", "mensaje": "El cursor no es válido", "tipo": "cursor_invalido"}],
        ) from None
