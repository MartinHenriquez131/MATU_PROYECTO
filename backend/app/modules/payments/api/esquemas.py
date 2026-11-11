"""Esquemas del pago (MATU-62; contrato docs/api/propuestos/pago.openapi.yaml, decisiones 223 a 247).

Todos con extra="forbid". Montos en pesos enteros con IVA incluido. **Nunca** el buy_order, el session_id, el número
de tarjeta, la respuesta de Transbank ni grupo_id en una vista del pago (decisión 247). La tarjeta, el código de
autorización y el correo, solo para quien pagó (D-62-2). El observador recibe un DTO distinto (decisión 127).
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ordering.api.esquemas import ProductoPedido

Version = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$", max_length=9)]
Huella = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ValorTransbank = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$")]

EstadoVenta = Literal["iniciada", "autorizando", "aprobada", "rechazada", "error"]
EstadoPago = Literal["sin_intento", "pendiente", "aprobado", "no_aprobado", "devuelto_parcial", "anulado"]
ResultadoPago = Literal[
    "aprobado", "aprobado_tardio", "no_aprobado", "abandonado", "tiempo_agotado", "pendiente", "anulado", "en_webpay"
]


# --- pagar ------------------------------------------------------------------------------------------------------


class CondicionesQueSeAceptan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Version
    huella: Huella = Field(description="SHA-256 del texto exacto, desde «## 1. Quién vende» (decisión 221)")


class SolicitudPago(BaseModel):
    """Lo que quien paga aceptó (R5, D6, D-62-16). **No lleva montos**: el monto sale del pedido, y If-Match asegura
    que es el que la pantalla mostró (decisión 226)."""

    model_config = ConfigDict(extra="forbid")

    acepta_condiciones: Literal[True] = Field(
        description="La casilla marcada por quien paga. Con false o sin ella, 422"
    )
    condiciones: CondicionesQueSeAceptan


class InicioPago(BaseModel):
    """La venta abierta (decisiones 228 y 229). Sin datos de tarjeta. La pantalla envía un formulario POST a ``url``
    con el campo token_ws = ``token``; el token nunca va en la URL de la app."""

    model_config = ConfigDict(extra="forbid")

    intento_id: uuid.UUID
    estado: EstadoVenta
    monto: int = Field(gt=0, description="El total confirmado, en pesos enteros con IVA, envío incluido")
    total_confirmado_en: datetime
    url: str | None = Field(description="El action del formulario de Webpay. null si la venta ya no está iniciada")
    token: str | None = Field(max_length=128, description="El valor de token_ws. null con url null")


# --- la vuelta --------------------------------------------------------------------------------------------------


class SolicitudRetorno(BaseModel):
    """Lo que trajo la dirección de la vuelta, con los nombres de Transbank (decisión 232). Al menos uno."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    token_ws: Annotated[ValorTransbank, Field(max_length=128)] | None = None
    tbk_token: Annotated[ValorTransbank, Field(max_length=128)] | None = Field(default=None, alias="TBK_TOKEN")
    tbk_orden_compra: Annotated[ValorTransbank, Field(max_length=26)] | None = Field(
        default=None, alias="TBK_ORDEN_COMPRA"
    )
    tbk_id_sesion: Annotated[ValorTransbank, Field(max_length=61)] | None = Field(default=None, alias="TBK_ID_SESION")

    @model_validator(mode="after")
    def _al_menos_uno(self) -> "SolicitudRetorno":
        if not any((self.token_ws, self.tbk_token, self.tbk_orden_compra, self.tbk_id_sesion)):
            raise ValueError("falta lo que trajo la vuelta de Webpay")
        return self


class ResultadoRetorno(BaseModel):
    """El resultado de la vuelta (decisiones 232 a 234). Sin montos ni tarjeta, con o sin sesión."""

    model_config = ConfigDict(extra="forbid")

    resultado: Literal[
        "aprobado", "aprobado_tardio", "no_aprobado", "abandonado", "tiempo_agotado", "pendiente", "anulado"
    ]
    ya_registrado: bool
    anulacion: Literal["en_curso", "hecha"] | None
    volver_a_preguntar_en: int | None = Field(ge=1)
    grupo_id: uuid.UUID | None = Field(description="Solo con la sesión de un admin, cuidador o pagador del grupo")
    persona_cuidada_id: uuid.UUID | None
    pedido_id: uuid.UUID | None
    pago_de_prueba: bool = Field(
        description="Decisión 248: true si la pasarela no es la de producción (no se movió dinero real, D-62-7)"
    )


# --- el pago y el comprobante -----------------------------------------------------------------------------------


class Tarjeta(BaseModel):
    """Lo que Transbank devuelve y MATU guarda (R14). Solo la ve quien pagó (D-62-2)."""

    model_config = ConfigDict(extra="forbid")

    tipo: Literal["credito", "debito", "prepago"]
    ultimos4: str = Field(pattern=r"^[0-9]{4}$")
    cuotas: int = Field(ge=0, le=48, description="0 o 1: sin cuotas. Las cuotas las reparte el banco")


class IntentoPago(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    resultado: ResultadoPago
    iniciado_en: datetime
    cerrado_en: datetime | None
    es_tuyo: bool


class Devolucion(BaseModel):
    """Una anulación a la misma tarjeta (decisión 239). Las en_curso no restan del total pagado."""

    model_config = ConfigDict(extra="forbid")

    motivo: Literal["pago_tardio", "producto_no_entregado", "cancelacion"]
    monto: int = Field(gt=0)
    producto: ProductoPedido | None
    estado: Literal["en_curso", "hecha"]
    solicitada_en: datetime
    hecha_en: datetime | None
    ultimos4: str | None = Field(pattern=r"^[0-9]{4}$", description="Solo para quien pagó (D-62-2)")


class LineaComprobante(BaseModel):
    model_config = ConfigDict(extra="forbid")

    producto: ProductoPedido
    cantidad: int = Field(ge=1, le=99)
    precio_unitario: int = Field(gt=0)
    subtotal: int = Field(gt=0)


class CondicionesComprobante(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Version
    aceptadas_en: datetime
    huella: Huella
    enlace: str = Field(
        pattern=r"^/v1/condiciones-pedido\?version=[0-9]+\.[0-9]+$",
        description="La versión aceptada, no la vigente (decisión 240)",
    )


class CorreoComprobante(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destino: str = Field(description="El correo de la cuenta de quien pagó")
    enviado: bool = Field(description="false en el piloto: el comprobante no se envía por correo (D-62-3)")


class Comprobante(BaseModel):
    """La confirmación escrita del pago (R4, decisión 238). **No es una boleta.**"""

    model_config = ConfigDict(extra="forbid")

    referencia: str = Field(pattern=r"^[0-9]{4,6}$")
    pagado_en: datetime
    lineas: list[LineaComprobante]
    subtotal_productos: int = Field(gt=0)
    costo_envio: int = Field(ge=0)
    total: int = Field(gt=0)
    pagaste_tu: bool
    tarjeta: Tarjeta | None
    codigo_autorizacion: str | None = Field(max_length=6)
    vendedor: Literal["MATU, piloto académico, sin persona jurídica"]
    ventana_entrega: str
    canal_reclamo: str
    condiciones: CondicionesComprobante
    tardio: bool
    devoluciones: list[Devolucion]
    precios_de_ejemplo: bool
    pago_de_prueba: bool
    correo: CorreoComprobante | None


class PagoVista(BaseModel):
    """El pago del pedido para admin, cuidador y pagador (decisión 236)."""

    model_config = ConfigDict(extra="forbid")

    pedido_id: uuid.UUID
    estado: EstadoPago
    pago_en_curso: bool
    intento: IntentoPago | None
    comprobante: Comprobante | None
    devoluciones: list[Devolucion]
    pago_de_prueba: bool = Field(
        description=(
            "Decisión 248: true si la pasarela no es la de producción. Está aunque no haya comprobante, para el sello"
            " de un pago anulado (diseño 7.9)"
        )
    )


class PagoVistaObservador(BaseModel):
    """Lo que ve el observador: solo si está pagado (D-62-2, decisión 127)."""

    model_config = ConfigDict(extra="forbid")

    pedido_id: uuid.UUID
    estado: Literal["pagado", "sin_pagar"]
