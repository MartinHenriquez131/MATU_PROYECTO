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
    # MATU-81 (P4 del diseñador): lo que muestra la fila de la lista
    pagado_en: datetime
    total_confirmado: Annotated[int, Field(ge=0, description="Pesos enteros, con IVA incluido")]
    numero_partes: int
    incidencia_abierta: bool
    devolucion_sin_terminar: bool


class ListaPedidosOperacion(BaseModel):
    pedidos: list[PedidoOperacion]
    # MATU-81: la lista trae hasta 200 pedidos, del pago más reciente al más antiguo
    hay_mas: bool = False


class RetractoVista(BaseModel):
    id: uuid.UUID
    pedido_id: uuid.UUID
    estado: Literal["solicitado", "devuelto", "rechazado"]
    solicitado_en: datetime
    plazo_hasta: datetime
    incluye_envio: bool
    monto: int
    origen: Literal["app", "correo"] = "app"


class ListaRetractos(BaseModel):
    retractos: list[RetractoVista]


class LineaRetractoOperacion(_Estricto):
    linea_id: uuid.UUID
    producto: str
    presentacion: str
    cantidad: int
    monto: Annotated[int, Field(ge=0, description="cantidad × precio pagado, en pesos enteros con IVA")]


class RetractoOperacion(RetractoVista):
    """MATU-81 (C23, P6): el retracto en la consola, con la referencia del pedido, sus productos y, si se rechazó, el
    motivo."""

    model_config = ConfigDict(extra="forbid")

    referencia: str | None
    lineas: list[LineaRetractoOperacion]
    motivo_rechazo: Literal["sello_abierto", "producto_no_recibido"] | None


class ListaRetractosOperacion(BaseModel):
    retractos: list[RetractoOperacion]


class SolicitudResolverRetracto(_Estricto):
    decision: Literal["devolver", "rechazar"]
    # MATU-81 (C24, P5): rechazar exige el motivo, de una lista cerrada que la familia ve. producto_no_recibido: MATU
    # no recibió el producto de vuelta
    motivo: Literal["sello_abierto", "producto_no_recibido"] | None = None


class EstadoPedidoVista(BaseModel):
    pedido_id: uuid.UUID
    estado: str


# --- Familia (R15 y R3, pantallas en MATU-92) ---------------------------------------------------------------------


class LineaRetracto(_Estricto):
    linea_id: uuid.UUID
    cantidad: Annotated[int, Field(ge=1, le=9999)]


class SolicitudRetracto(_Estricto):
    lineas: Annotated[list[LineaRetracto], Field(min_length=1, max_length=100)]


class SolicitudRetractoPorCorreo(SolicitudRetracto):
    """H2: el retracto que la familia pidió por correo. Sin valor, va a nombre de quien pagó. MATU-81 (D-81-9, C25):
    ``correo_solicitante`` es el correo de quien escribió; el servidor lo busca entre los admins activos del grupo y
    responde 422 si no está. Nunca lista a nadie ni lo escribe en los logs. ``solicitado_por`` (el id) se mantiene
    por compatibilidad; no se mandan los dos."""

    solicitado_por: uuid.UUID | None = None
    correo_solicitante: Annotated[str | None, Field(min_length=3, max_length=254)] = None


class RetractosDelPedido(BaseModel):
    """GET /v1/pedidos/{id}/retractos: hasta cuándo se puede pedir (la fecha exacta que muestra la pantalla) y los
    retractos pedidos."""

    plazo_hasta: datetime
    retractos: list[RetractoVista]
