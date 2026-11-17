"""Esquemas de la consola de operación (MATU-81, rutas 1 a 9 de la revisión previa; decisiones 449 en adelante).

C5: ninguna vista trae datos de la persona cuidada (nombre, nivel de apoyo, dirección, teléfono, persona_cuidada_id),
del grupo (grupo_id, nombre) ni de la cuenta de la familia (usuario_id, nombre o correo de quien pidió o pagó). Todas
llevan ``extra="forbid"`` y tests/modules/backoffice/test_contrato_operacion.py recorre sus esquemas en el OpenAPI.
C18: la conciliación no trae el token, el session_id, payload_respuesta, la tarjeta, las cuotas ni el código de
autorización. Dinero en pesos enteros, con IVA incluido.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.backoffice.api.esquemas import EstadoCodigoApi, EstadoParteApi

EstadoPedidoPagado = Literal[
    "pagado", "enviado_a_comercio", "preparando", "listo_retiro", "asignado", "sin_repartidor", "retirado", "en_ruta",
    "entregado", "no_entregado", "reprogramado", "cerrado", "cancelado", "cancelado_con_devolucion",
]
TipoIncidencia = Literal[
    "faltante", "entrega_fallida", "reclamo_familia", "cobro_sin_respuesta", "devolucion_pendiente", "otro"
]
EstadoIncidencia = Literal["abierta", "en_gestion", "resuelta"]
AccionPedido = Literal["en_camino", "entregado", "no_entregado", "cancelar_con_devolucion"]
MotivoAnulacionApi = Literal["pago_tardio", "producto_no_entregado", "cancelacion", "retracto"]
Pesos = Annotated[int, Field(ge=0, description="Pesos enteros, con IVA incluido")]
_TEXTO_NOTA = (
    "Hasta 500 caracteres. No escribas nombres, datos de salud ni la dirección. La familia puede leer esta nota"
)


class _Vista(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Pedidos (rutas 1 y 2) ------------------------------------------------------------------------------------------


class ComercioOperacion(_Vista):
    nombre_fantasia: str
    ficticio: bool


class PedidoFila(_Vista):
    """Una fila de la lista de pedidos (P4 del diseñador)."""

    id: uuid.UUID
    referencia: str | None
    estado: EstadoPedidoPagado
    pagado_en: datetime
    total_confirmado: Pesos
    numero_partes: int
    incidencia_abierta: bool
    devolucion_sin_terminar: bool


class ListaPedidosConsola(_Vista):
    pedidos: list[PedidoFila]
    hay_mas: Annotated[bool, Field(description="La lista trae hasta 200 pedidos, del pago más reciente al más antiguo")]


class SolicitudBuscarPedido(_Vista):
    """C7: la referencia va solo en el cuerpo, nunca en la URL, los logs, los errores ni la auditoría."""

    referencia: Annotated[str, Field(min_length=1, max_length=64, description="La del pedido o la de una parte")]


class ParteDetalle(_Vista):
    id: uuid.UUID
    referencia: str
    comercio: ComercioOperacion
    estado: EstadoParteApi
    estado_codigo: EstadoCodigoApi
    codigo_expira_en: datetime | None
    enviado_en: datetime | None
    preparando_en: datetime | None
    lista_en: datetime | None
    retirada_en: datetime | None
    cancelada_en: datetime | None
    motivo_cancelacion: Literal["producto_faltante", "familia_cancela"] | None


class LineaDetalle(_Vista):
    id: uuid.UUID
    parte_id: uuid.UUID | None
    producto: str
    presentacion: str
    cantidad: int
    precio_unitario: Annotated[Pesos, Field(description="El precio pagado, con IVA incluido")]
    subtotal: Pesos
    estado_linea: Literal["pendiente", "sin_stock", "preparada", "faltante", "devuelta", "eliminada"]
    unidades_faltantes: int
    monto_devuelto: Pesos
    devolucion: Literal["sin_devolucion", "en_curso", "hecha"]


class EventoLineaTiempo(_Vista):
    """C6: el actor es familia, comercio (con su nombre de fantasía), operacion o sistema. Nunca la cuenta de la
    familia. ``tipo``: estado (una transición del pedido), parte, cobro, anulacion, retracto o incidencia."""

    en: datetime
    tipo: Literal["estado", "parte", "cobro", "anulacion", "retracto", "incidencia"]
    actor_tipo: Literal["familia", "comercio", "operacion", "sistema"]
    comercio: str | None
    desde: str | None
    hacia: str | None
    motivo: str | None
    monto: Pesos | None


class AccionDisponible(_Vista):
    """P3: lo que se puede hacer ahora, con lo que devolvería a la misma tarjeta. La pantalla nunca calcula montos."""

    accion: AccionPedido
    monto_a_devolver: Pesos


class PedidoDetalle(_Vista):
    """GET /v1/operacion/pedidos/{id}. Se audita como operacion.pedido_ver (D-81-5)."""

    id: uuid.UUID
    referencia: str | None
    estado: EstadoPedidoPagado
    pagado_en: datetime
    entregado_en: datetime | None
    subtotal_productos: Pesos
    costo_envio: Pesos
    total_confirmado: Pesos
    partes: list[ParteDetalle]
    lineas: list[LineaDetalle]
    linea_de_tiempo: list[EventoLineaTiempo]
    acciones: list[AccionDisponible]
    retracto_plazo_hasta: Annotated[
        datetime | None, Field(description="Hasta cuándo se registra un retracto por correo (90 días desde la entrega)")
    ]


# --- Conciliación (rutas 3 y 4) -----------------------------------------------------------------------------------


class AnulacionVista(_Vista):
    id: uuid.UUID
    motivo: MotivoAnulacionApi
    monto: Pesos
    estado: Literal["en_curso", "hecha", "rechazada"]
    producto: str | None
    en: datetime


class VentaVista(_Vista):
    """D-81-8: buy_order sí (para buscar en el portal de Transbank); nunca va en la URL ni en los logs."""

    buy_order: str
    monto: Pesos
    estado: Literal["iniciada", "autorizando", "aprobada", "rechazada", "error"]
    creada_en: datetime
    respondida_en: datetime | None


class CobroPedido(_Vista):
    """GET /v1/operacion/pedidos/{id}/cobro. Se audita como operacion.pedido_ver (D-81-5)."""

    pedido_id: uuid.UUID
    referencia: str | None
    total_confirmado: Pesos
    cobrado: Pesos
    devuelto: Pesos
    queda_cobrado: Pesos
    estado_cargo: Literal["sin_cargo", "pendiente", "pagado", "rechazado", "devuelto_parcial", "anulado"]
    ventas: list[VentaVista]
    anulaciones: list[AnulacionVista]
    calza: Annotated[bool, Field(description="Lo cobrado no supera el total y no hay devoluciones sin terminar")]


class VentaPendiente(_Vista):
    pedido_id: uuid.UUID
    referencia: str | None
    buy_order: str
    monto: Pesos
    creada_en: datetime


class AnulacionPendiente(_Vista):
    pedido_id: uuid.UUID
    referencia: str | None
    motivo: MotivoAnulacionApi
    monto: Pesos
    creada_en: datetime
    intentos: int


class CobrosPendientes(_Vista):
    """GET /v1/operacion/cobros/pendientes: ventas sin respuesta por más de 15 minutos y anulaciones sin terminar."""

    ventas_sin_respuesta: list[VentaPendiente]
    anulaciones_sin_terminar: list[AnulacionPendiente]


# --- Retractos (rutas 5 y 9) --------------------------------------------------------------------------------------


class LineaRetractoVista(_Vista):
    linea_id: uuid.UUID
    producto: str
    presentacion: str
    cantidad: int
    monto: Pesos


# --- Incidencias (ruta 6) -----------------------------------------------------------------------------------------


class IncidenciaVista(_Vista):
    id: uuid.UUID
    pedido_id: uuid.UUID
    referencia: str | None
    tipo: TipoIncidencia
    estado: EstadoIncidencia
    descripcion: str
    resolucion: str | None
    creada_en: datetime
    resuelta_en: datetime | None
    asignada: bool
    asignada_a_mi: bool
    version: Annotated[int, Field(description="El ETag de la fila, para el If-Match del PATCH sin otro GET")]


class ListaIncidencias(_Vista):
    incidencias: list[IncidenciaVista]


class SolicitudIncidencia(_Vista):
    tipo: TipoIncidencia
    descripcion: Annotated[str, Field(min_length=1, max_length=500, description=_TEXTO_NOTA)]
    asignarme: bool = False


class SolicitudEditarIncidencia(_Vista):
    """Solo cambian el estado, a quién está asignada y la resolución (C13). «resuelta» exige ``resolucion``."""

    estado: EstadoIncidencia | None = None
    resolucion: Annotated[str | None, Field(min_length=1, max_length=500, description=_TEXTO_NOTA)] = None
    asignacion: Literal["a_mi", "sin_asignar"] | None = None


# --- Catálogo (ruta 7) --------------------------------------------------------------------------------------------


class OfertaConsola(_Vista):
    id: uuid.UUID
    comercio: ComercioOperacion
    producto: str
    presentacion: str
    precio: Annotated[int, Field(gt=0, description="Pesos enteros, con IVA incluido")]
    stock: int
    disponible: bool
    editable: Annotated[bool, Field(description="Solo las ofertas de los comercios ficticios (D-81-7)")]
    version: Annotated[str, Field(description="El ETag de la oferta, para el If-Match del PATCH")]


class CatalogoConsola(_Vista):
    ofertas: list[OfertaConsola]


class SolicitudOferta(_Vista):
    precio: Annotated[int | None, Field(gt=0, le=9_999_999, description="Pesos enteros con IVA incluido")] = None
    stock: Annotated[int | None, Field(ge=0, le=9999)] = None
    disponible: bool | None = None
