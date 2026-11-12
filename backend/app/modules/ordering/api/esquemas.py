"""Esquemas del pedido (MATU-61; contrato docs/api/propuestos/pedido.openapi.yaml, decisiones 188 a 219).

Todos con extra="forbid". Montos en pesos enteros con IVA incluido (C5), sin punto flotante. Nunca grupo_id,
creado_por, el nombre de la persona, la dirección del comercio ni las referencias opacas de los comercios. El
observador recibe un DTO distinto, sin entrega, resumen ni etag (C3).
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ordering.domain.estados import Estado
from app.modules.ordering.domain.pedido import CANTIDAD_MAXIMA, LINEAS_MAXIMAS, Regla
from app.shared.celular import PATRON_CELULAR

Etag = Annotated[str, Field(pattern=r'^"v[0-9]+"$')]
Huella = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Cantidad = Annotated[int, Field(ge=1, le=CANTIDAD_MAXIMA, description="Envases del producto, de 1 a 99")]
Celular = Annotated[
    str,
    Field(
        max_length=20,
        pattern=PATRON_CELULAR,
        description="Celular chileno, con la regla de POST /v1/usuarios; se guarda en E.164",
    ),
]


class ComercioVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre_fantasia: str
    ficticio: bool = Field(description="comercio.ficticio (D9). Con true, la pantalla agrega «(comercio ficticio)»")


class ProductoPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    presentacion: str
    unidad: Literal["unidad", "sobre", "ml", "g"]
    unidades_por_envase: int = Field(gt=0)


class CambioDeLinea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    precio_antes: int | None = Field(gt=0, description="El precio del carrito, si el confirmado es distinto")
    comercio_antes: ComercioVista | None = Field(description="El comercio del carrito, si el producto pasó a otro")


class DevolucionLinea(BaseModel):
    """MATU-62 (decisión 239): la anulación parcial de la línea, a la misma tarjeta. La crea MATU-63. Sin los
    últimos 4."""

    model_config = ConfigDict(extra="forbid")

    monto: int = Field(gt=0, description="Pesos enteros devueltos o por devolver")
    estado: Literal["en_curso", "hecha"]
    hecha_en: datetime | None


class LineaPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    oferta_id: uuid.UUID = Field(
        description=(
            "La oferta del carrito de esta línea, la que se reenvía en PUT …/lineas para conservarla, también si dejó"
            " de estar publicada. Es un id opaco, nunca va a la URL del navegador"
        )
    )
    producto: ProductoPedido
    cantidad: Cantidad
    comercio: ComercioVista
    precio_unitario: int = Field(gt=0, description="Precio exacto en pesos enteros, con IVA incluido")
    subtotal: int = Field(gt=0, description="cantidad × precio_unitario")
    regla_faltante: Regla
    retracto_pierde_al_abrir: bool
    cambio: CambioDeLinea | None
    devolucion: DevolucionLinea | None = Field(
        description="MATU-62: la devolución de esta línea por anulación parcial. null si no se devolvió"
    )


class LineaSalida(BaseModel):
    model_config = ConfigDict(extra="forbid")

    producto: ProductoPedido
    cantidad: Cantidad
    comercio: ComercioVista


class ParteComercio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comercio: ComercioVista
    subtotal_productos: int = Field(ge=0)


class EntregaVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calle: str
    numero: str
    depto: str | None
    comuna: str
    region: str
    referencia: str | None
    telefono_contacto: str = Field(
        max_length=20,
        description="El celular de una cuenta va enmascarado (celular_cuenta); uno escrito, completo en E.164",
    )
    telefono_origen: Literal["celular_cuenta", "escrito"]
    telefono_es_tuyo: bool


class CondicionesVigentes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    huella: Huella
    enlace: Literal["/v1/condiciones-pedido"]


class ResumenAntesDePagar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendedor: Literal["MATU, piloto académico, sin persona jurídica"]
    boleta: Literal["En este piloto no se emite boleta"]
    ventana_entrega: Literal["Entre 24 y 48 horas hábiles"]
    canal_reclamo: str
    condiciones: CondicionesVigentes


class PedidoVista(BaseModel):
    """El pedido de la familia, como un solo pedido (D7). Lo ven admin, cuidador y pagador (C3)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    estado: Estado
    etag: Etag
    precios_de_ejemplo: bool
    lineas: list[LineaPedido] = Field(max_length=LINEAS_MAXIMAS)
    salieron: list[LineaSalida]
    comercios: list[ParteComercio]
    subtotal_productos: int = Field(ge=0)
    costo_envio: int = Field(ge=0, description="Un solo envío por pedido (ADR-027), con IVA incluido")
    total: int | None = Field(gt=0, description="subtotal_productos + costo_envio, con IVA incluido")
    total_confirmado_en: datetime | None
    vence_en: datetime | None
    vigencia_segundos: int | None = Field(ge=0, le=900)
    ventana_entrega: str
    entrega: EntregaVista | None
    resumen: ResumenAntesDePagar | None
    pago_en_curso: bool = Field(
        description=(
            "MATU-62 (decisión 230): hay una venta iniciada vigente o autorizando. Mientras sea true, confirmar,"
            " cambiar, lineas, reglas-faltante y contacto responden 409 pago-en-curso"
        )
    )
    pagado_en: datetime | None = Field(description="MATU-62: cuándo se pagó. El pago se lee en GET …/pago")
    creado_en: datetime
    actualizado_en: datetime


class PedidoVistaObservador(BaseModel):
    """Lo que ve el observador (C3): el carrito sin entrega, sin resumen y sin etag."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    estado: Estado
    precios_de_ejemplo: bool
    lineas: list[LineaPedido]
    salieron: list[LineaSalida]
    comercios: list[ParteComercio]
    subtotal_productos: int = Field(ge=0)
    costo_envio: int = Field(ge=0)
    total: int | None
    total_confirmado_en: datetime | None
    vence_en: datetime | None
    ventana_entrega: str
    creado_en: datetime
    actualizado_en: datetime


class LineaSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oferta_id: uuid.UUID
    cantidad: Cantidad


class SolicitudPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lineas: list[LineaSolicitud] = Field(min_length=1, max_length=LINEAS_MAXIMAS)


class SolicitudLineas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lineas: list[LineaSolicitud] = Field(min_length=0, max_length=LINEAS_MAXIMAS)


class ReglaProducto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    producto_id: uuid.UUID
    accion: Regla


class SolicitudReglasFaltante(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reglas: list[ReglaProducto] = Field(min_length=0, max_length=LINEAS_MAXIMAS)


class SolicitudConfirmar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telefono_contacto: Celular | None = None


class SolicitudContacto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telefono_contacto: Celular


class CondicionesPedidoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    actualizada_en: date
    huella: Huella
    texto: str
