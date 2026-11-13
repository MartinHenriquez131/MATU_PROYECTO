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


class RetractoVista(BaseModel):
    id: uuid.UUID
    pedido_id: uuid.UUID
    estado: Literal["solicitado", "devuelto", "rechazado"]
    solicitado_en: datetime
    plazo_hasta: datetime
    incluye_envio: bool
    monto: int


class ListaRetractos(BaseModel):
    retractos: list[RetractoVista]


class SolicitudResolverRetracto(_Estricto):
    decision: Literal["devolver", "rechazar"]


class EstadoPedidoVista(BaseModel):
    pedido_id: uuid.UUID
    estado: str


# --- Familia (R15 y R3, pantallas en MATU-92) ---------------------------------------------------------------------


class LineaRetracto(_Estricto):
    linea_id: uuid.UUID
    cantidad: Annotated[int, Field(ge=1, le=9999)]


class SolicitudRetracto(_Estricto):
    lineas: Annotated[list[LineaRetracto], Field(min_length=1, max_length=100)]


class RetractosDelPedido(BaseModel):
    """GET /v1/pedidos/{id}/retractos: hasta cuándo se puede pedir (la fecha exacta que muestra la pantalla) y los
    retractos pedidos."""

    plazo_hasta: datetime
    retractos: list[RetractoVista]
