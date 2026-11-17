"""Esquemas de la vista del comercio, de operación y de la familia después de pagar (MATU-63, decisiones 407 en
adelante).

La proyección del comercio (D-63-1, R6 y R7) no lleva pedido_id, grupo, persona, quién creó el pedido, condiciones,
la referencia corta de la familia, montos, precios del pedido, devoluciones, transiciones, la entrega, el código ni su
hash. tests/modules/backoffice/test_contrato_comercio.py lo verifica sobre el OpenAPI.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ordering.api.esquemas import ProductoPedido

EstadoParteApi = Literal["enviada", "preparando", "lista", "retirada", "cancelada"]
EstadoCodigoApi = Literal["sin_codigo", "vigente", "usado", "bloqueado", "vencido"]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Comercio ---------------------------------------------------------------------------------------------------


class ComercioDeLaCuenta(BaseModel):
    """GET /v1/comercio: la barra de la consola, el rótulo del piloto y el contacto de «Avisa a MATU» (O2)."""

    nombre_fantasia: str
    ficticio: bool
    contacto: str | None = Field(
        description="El correo de contacto de MATU (CORREO_PRIVACIDAD), o null si no está configurado"
    )


class ParteResumen(BaseModel):
    id: uuid.UUID
    referencia: Annotated[str, Field(description="Seis caracteres sin 0, O, 1, I ni L, aleatoria por parte (O6)")]
    estado: EstadoParteApi
    enviado_en: datetime
    preparar_antes_de: datetime
    estado_codigo: EstadoCodigoApi
    numero_lineas: int
    retirada_en: datetime | None
    cancelada_en: datetime | None
    motivo_cancelacion: Annotated[
        Literal["producto_faltante", "cancelada_por_familia"] | None,
        Field(description="Solo en cancelada: no tenía ninguno (O3) o la familia canceló antes de preparar (R15)"),
    ]


class ListaPartes(BaseModel):
    """GET /v1/comercio/partes: las abiertas y las cerradas hoy (fecha de Chile)."""

    partes: list[ParteResumen]


class ProductoLinea(BaseModel):
    nombre: str
    presentacion: str


class LineaComercioVista(BaseModel):
    id: uuid.UUID
    producto: ProductoLinea
    cantidad: int
    estado_linea: Literal["pendiente", "preparada", "faltante", "devuelta"]
    unidades_faltantes: int


class ParteVista(ParteResumen):
    """GET /v1/comercio/partes/{id}, con ETag. Las acciones devuelven la parte como queda."""

    lineas: list[LineaComercioVista]


class SolicitudMarca(_Estricto):
    estado: Literal["preparada", "faltante"]
    unidades_faltantes: Annotated[
        int | None,
        Field(ge=1, le=9999, description="Solo con faltante: cuántos faltan. Sin valor, faltan todos"),
    ] = None


class SolicitudCodigo(_Estricto):
    codigo: Annotated[str, Field(pattern=r"^[0-9]{6}$", description="Las 6 cifras, solo en el cuerpo (D-63-4)")]


class ResultadoCodigoVista(BaseModel):
    resultado: Literal["correcto", "no_es", "bloqueado", "vencido", "usado", "cancelada", "sin_codigo"]
    intentos_restantes: int
    parte: ParteVista


class ProductoDelComercio(BaseModel):
    oferta_id: uuid.UUID
    nombre: str
    presentacion: str
    precio: int
    stock: int
    apartado: int
    disponibles: Annotated[int, Field(description="stock − apartado, nunca bajo 0 (O5)")]
    disponible: Annotated[bool, Field(description="Si lo ofrece en MATU")]
    etag: Annotated[str, Field(description="Para el If-Match de PATCH /v1/comercio/productos/{oferta_id}")]


class ListaProductos(BaseModel):
    productos: list[ProductoDelComercio]


class SolicitudProducto(_Estricto):
    stock: Annotated[int | None, Field(ge=0, le=9999)] = None
    disponible: bool | None = None


# --- Operación (D-63-5, D-63-6) ------------------------------------------------------------------------------------


class CodigoGenerado(BaseModel):
    """El código se muestra **una sola vez**: no se guarda en claro ni se puede volver a leer (D-63-5)."""

    parte_id: uuid.UUID
    codigo: str
    expira_en: datetime


class ParteOperacion(BaseModel):
    id: uuid.UUID
    comercio: str
    referencia: str
    estado: EstadoParteApi
    estado_codigo: EstadoCodigoApi


class PedidoOperacion(BaseModel):
    id: uuid.UUID
    estado: str
    referencia: str | None
    entregado_en: datetime | None
    partes: list[ParteOperacion]


class ListaPedidosOperacion(BaseModel):
    pedidos: list[PedidoOperacion]


class LineaDelRetracto(_Estricto):
    """MATU-92 (ruta 4): un producto del retracto, con lo que se devuelve a precio pagado."""

    linea_id: uuid.UUID
    producto: ProductoPedido
    cantidad: Annotated[int, Field(ge=1)]
    monto: Annotated[int, Field(gt=0, description="cantidad × precio pagado, en pesos enteros")]


class RetractoVista(_Estricto):
    id: uuid.UUID
    pedido_id: uuid.UUID
    estado: Literal["solicitado", "devuelto", "rechazado"]
    solicitado_en: datetime
    plazo_hasta: datetime
    incluye_envio: bool
    monto: Annotated[int, Field(gt=0, description="Los productos a precio pagado, más el envío si lo incluye")]
    origen: Annotated[
        Literal["app", "correo"], Field(description="correo: lo pidió la familia por correo y lo registró operación")
    ]
    lineas: list[LineaDelRetracto]
    resuelto_en: Annotated[datetime | None, Field(description="Cuándo se devolvió o no se aceptó; null si sigue")]


class ListaRetractos(BaseModel):
    retractos: list[RetractoVista]


class SolicitudResolverRetracto(_Estricto):
    decision: Literal["devolver", "rechazar"]


class EstadoPedidoVista(_Estricto):
    pedido_id: uuid.UUID
    estado: str


# --- Familia (R15 y R3, pantallas en MATU-92) ---------------------------------------------------------------------


class LineaRetracto(_Estricto):
    linea_id: uuid.UUID
    cantidad: Annotated[int, Field(ge=1, le=9999)]


class SolicitudRetracto(_Estricto):
    lineas: Annotated[list[LineaRetracto], Field(min_length=1, max_length=100)]


class SolicitudRetractoPorCorreo(SolicitudRetracto):
    """H2: el retracto que la familia pidió por correo. ``solicitado_por``: la cuenta que pagó o el admin del grupo;
    sin valor, quien pagó."""

    solicitado_por: uuid.UUID | None = None


class RetractoVistaFamilia(RetractoVista):
    """El retracto para la familia (MATU-92, C18): quién lo pidió solo como es_tuyo, nunca su nombre ni su id."""

    es_tuyo: bool


MotivoNoCancelarApi = Literal["rol", "ya_se_prepara", "cancelado"]
MotivoNoArrepentirseApi = Literal["rol", "sin_entregar", "plazo_app_vencido", "plazo_vencido", "nada_disponible"]
_DESCRIPCION_CANCELAR = (
    "null si puede_cancelar. rol: solo el admin cancela; ya_se_prepara: un comercio ya empezó (o el pedido ya salió);"
    " cancelado: el pedido ya se canceló"
)
_DESCRIPCION_ARREPENTIRSE = (
    "null si puede_arrepentirse. sin_entregar; plazo_app_vencido: pasaron los 10 días hábiles y queda el correo hasta"
    " plazo_correo_hasta (C22); plazo_vencido: pasaron también los 90 días; rol: pueden el admin y quien pagó;"
    " nada_disponible: ya se pidió devolver todo lo entregado"
)


class LineaParaRetracto(_Estricto):
    """MATU-92 (ruta 3): lo que se puede devolver de una línea entregada."""

    linea_id: uuid.UUID
    producto: ProductoPedido
    entregadas: Annotated[int, Field(ge=0, description="cantidad − unidades_faltantes")]
    ya_pedidas: Annotated[int, Field(ge=0, description="En retractos anteriores, también los no aceptados (H3 y H8)")]
    disponibles: Annotated[int, Field(ge=0, description="entregadas − ya_pedidas: el máximo de un retracto nuevo")]
    precio_pagado: Annotated[int, Field(gt=0, description="El precio unitario pagado, en pesos enteros (C9)")]
    retracto_pierde_al_abrir: bool


class RetractosDelPedido(_Estricto):
    """GET /v1/pedidos/{id}/retractos: hasta cuándo se puede pedir (la fecha exacta que muestra la pantalla), lo que
    se puede devolver y los retractos pedidos (MATU-92)."""

    plazo_hasta: Annotated[datetime, Field(description="Fin del décimo día hábil desde la entrega, en hora de Chile")]
    plazo_correo_hasta: Annotated[datetime, Field(description="90 días desde la entrega: hasta aquí, por correo (C22)")]
    puede_arrepentirse: bool
    arrepentirse_motivo: Annotated[MotivoNoArrepentirseApi | None, Field(description=_DESCRIPCION_ARREPENTIRSE)]
    condiciones_version: Annotated[str | None, Field(description="La versión de las condiciones aceptada al pagar")]
    costo_envio: Annotated[int, Field(ge=0, description="El envío pagado, en pesos enteros")]
    incluye_envio_si_todo: Annotated[
        bool, Field(description="Si devolver ahora todo lo disponible devuelve también el envío (D-63-10)")
    ]
    lineas: list[LineaParaRetracto]
    retractos: list[RetractoVistaFamilia]


# --- Tus pedidos (MATU-92, rutas 1 y 2) --------------------------------------------------------------------------

EstadoFamiliaApi = Literal[
    "pagado", "enviado_a_comercio", "preparando", "listo_retiro", "en_ruta", "entregado", "no_entregado",
    "reprogramado", "cancelado_con_devolucion",
]
_DESCRIPCION_ESTADO = (
    "El estado para la familia (lenguaje.md 38): listo_retiro agrupa listo_retiro, asignado, sin_repartidor y"
    " retirado; entregado agrupa entregado y cerrado"
)
Referencia = Annotated[str, Field(pattern=r"^[0-9]{4,6}$")]


class ProductoDeLaFila(_Estricto):
    producto: ProductoPedido
    cantidad: Annotated[int, Field(ge=1)]


class ResumenProductos(_Estricto):
    """O5 del diseño: «{primero} y {otros} productos más»."""

    primero: str
    otros: Annotated[int, Field(ge=0)]


class PedidoPagadoFila(_Estricto):
    """Una fila de «Tus pedidos» para admin, cuidador y pagador (C5)."""

    pedido_id: uuid.UUID
    referencia: Referencia
    pagado_en: datetime
    estado: Annotated[EstadoFamiliaApi, Field(description=_DESCRIPCION_ESTADO)]
    entregado_en: datetime | None
    cancelado_en: datetime | None
    productos: list[ProductoDeLaFila]
    resumen_productos: ResumenProductos | None
    productos_borrados: Annotated[bool, Field(description="C28: ya no se guardan los productos del pedido")]
    total: Annotated[int, Field(gt=0, description="El total pagado, envío incluido, en pesos enteros")]
    devuelto: Annotated[int, Field(ge=0, description="Lo devuelto a la tarjeta con anulaciones hechas")]
    devuelto_todo: Annotated[bool, Field(description="devuelto = total: «Devolvimos», y no «Estamos devolviendo»")]
    puede_cancelar: bool
    cancelar_motivo: Annotated[MotivoNoCancelarApi | None, Field(description=_DESCRIPCION_CANCELAR)]
    puede_arrepentirse: bool
    arrepentirse_motivo: Annotated[MotivoNoArrepentirseApi | None, Field(description=_DESCRIPCION_ARREPENTIRSE)]
    plazo_hasta: Annotated[
        datetime | None,
        Field(description="Fin del décimo día hábil desde la entrega, en hora de Chile. null sin entrega"),
    ]
    plazo_correo_hasta: Annotated[datetime | None, Field(description="90 días desde la entrega. null sin entrega")]


class PedidoPagadoFilaObservador(_Estricto):
    """Lo que ve el observador (D-92-1 a, C3; MATU-113, decisión 472): la fecha del pago, el estado de familia, la
    fecha de entrega y los productos. Sin referencia, montos, comprobante, código ni acciones."""

    pedido_id: uuid.UUID
    pagado_en: datetime
    estado: Annotated[EstadoFamiliaApi, Field(description=_DESCRIPCION_ESTADO)]
    entregado_en: datetime | None
    productos: list[ProductoDeLaFila]
    resumen_productos: ResumenProductos | None
    productos_borrados: bool


class ListaPedidosPagados(_Estricto):
    items: list[PedidoPagadoFila]
    siguiente_cursor: str | None


class ListaPedidosPagadosObservador(_Estricto):
    items: list[PedidoPagadoFilaObservador]
    siguiente_cursor: str | None


class ComercioDeLaParte(_Estricto):
    nombre_fantasia: Annotated[str | None, Field(description="null si el comercio ya no está activo")]
    ficticio: Annotated[bool, Field(description="Con true, la pantalla agrega «(comercio ficticio)»")]


class LineaDeLaParte(_Estricto):
    linea_id: uuid.UUID
    producto: ProductoPedido
    cantidad: Annotated[int, Field(ge=1)]
    unidades_faltantes: Annotated[int, Field(ge=0, description="Las que el comercio no tenía")]


class ParteDelPedido(_Estricto):
    """Una parte del pedido por comercio (C16): su estado, que la pantalla dice con los textos de la familia."""

    comercio: ComercioDeLaParte
    estado: EstadoParteApi
    cancelada_por: Annotated[
        Literal["faltante", "pedido"] | None,
        Field(description="Solo con cancelada: el comercio no tenía nada (faltante) o se canceló el pedido"),
    ]
    lineas: list[LineaDeLaParte]


class SeguimientoPedido(_Estricto):
    """GET /v1/pedidos/{id}/seguimiento (ruta 2): cómo va el pedido pagado, por comercio. Sin la referencia de la
    parte, el código de retiro ni nada del encargado (C15). El comprobante es GET …/pago (C14)."""

    pedido_id: uuid.UUID
    referencia: Referencia
    pagado_en: datetime
    estado: Annotated[EstadoFamiliaApi, Field(description=_DESCRIPCION_ESTADO)]
    entregado_en: datetime | None
    cancelado_en: datetime | None
    partes: list[ParteDelPedido]
    productos_borrados: bool
    total: Annotated[int, Field(gt=0)]
    devuelto: Annotated[int, Field(ge=0)]
    devuelto_todo: bool
    puede_cancelar: bool
    cancelar_motivo: Annotated[MotivoNoCancelarApi | None, Field(description=_DESCRIPCION_CANCELAR)]
    puede_arrepentirse: bool
    arrepentirse_motivo: Annotated[MotivoNoArrepentirseApi | None, Field(description=_DESCRIPCION_ARREPENTIRSE)]
    plazo_hasta: datetime | None
    plazo_correo_hasta: datetime | None
