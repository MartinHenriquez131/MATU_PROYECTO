"""Esquemas de la API del consumo (MATU-36). Contrato: docs/api/openapi.json.

- Los cuerpos usan extra="forbid": stock_medido_en, grupo_id, producto_id en la edición, activo o
  cualquier otro campo extra responden 422.
- nombre_libre: 1 a 60 caracteres después de quitar los espacios de los extremos, una línea, sin
  caracteres de control. El 422 nunca repite el valor (app/core/errores.py no copia input ni ctx).
- Las respuestas no llevan grupo_id ni precios.
"""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.consumption.domain.alerta import CANTIDAD_MAXIMA, EstadoAlerta
from app.modules.consumption.domain.perfil import (
    DIAS_AVISO_MAXIMO,
    DIAS_AVISO_POR_OMISION,
    LARGO_MAXIMO_NOMBRE_LIBRE,
    STOCK_MAXIMO,
    TASA_DIAS_MAXIMA,
    TASA_UNIDADES_MAXIMA,
    UnidadConsumo,
    nombre_libre_valido,
)

NombreLibre = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_NOMBRE_LIBRE),
    AfterValidator(nombre_libre_valido),
    Field(
        description=(
            "Nombre del producto tal como se vende. No es para remedios ni para explicar para qué se usa."
            " De 1 a 60 caracteres, una línea, sin caracteres de control"
        )
    ),
]
TasaUnidades = Annotated[int, Field(ge=1, le=TASA_UNIDADES_MAXIMA)]
TasaDias = Annotated[int, Field(ge=1, le=TASA_DIAS_MAXIMA)]
Stock = Annotated[int, Field(ge=0, le=STOCK_MAXIMO)]
DiasAviso = Annotated[int, Field(ge=0, le=DIAS_AVISO_MAXIMO)]


class SolicitudPerfil(BaseModel):
    """Cuerpo de la creación. producto_id o nombre_libre, exactamente uno (si no, 422 producto_o_nombre)."""

    model_config = ConfigDict(extra="forbid")

    producto_id: uuid.UUID | None = None
    nombre_libre: NombreLibre | None = None
    unidad: UnidadConsumo | None = None
    tasa_unidades: TasaUnidades
    tasa_dias: TasaDias = 1
    stock_unidades: Stock
    dias_aviso: DiasAviso = DIAS_AVISO_POR_OMISION


class SolicitudEdicionPerfil(BaseModel):
    """Edición parcial. Al menos un campo; null no se admite (422 null_no_admitido)."""

    model_config = ConfigDict(extra="forbid")

    nombre_libre: NombreLibre | None = None
    tasa_unidades: TasaUnidades | None = None
    tasa_dias: TasaDias | None = None
    stock_unidades: Stock | None = None
    dias_aviso: DiasAviso | None = None


class ProductoResumen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    presentacion: str


class AutorPerfilVista(BaseModel):
    """Quién guardó el perfil por última vez: su id y su nombre de pila, nunca el email."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str


class PerfilConsumoVista(BaseModel):
    """Un perfil. Exactamente uno de producto y nombre_libre no es null. Sin grupo_id ni precios."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    producto: ProductoResumen | None
    nombre_libre: str | None
    unidad: UnidadConsumo
    tasa_unidades: int
    tasa_dias: int
    stock_unidades: int
    stock_medido_en: date
    dias_aviso: int
    fecha_quiebre_estimada: date = Field(
        description="Es una estimación con lo que anotó la familia, no una promesa: stock_medido_en + días de cobertura"
    )
    dias_restantes: int = Field(description="fecha_quiebre_estimada menos hoy (America/Santiago). Negativo: ya pasó")
    activo: bool
    actualizado_por: AutorPerfilVista | None = Field(
        description="Quién guardó la última vez, con su nombre de pila (decisión 73). null si la cuenta ya no está"
    )
    etag: str = Field(pattern=r'^"v[1-9][0-9]*"$')


class ListaPerfiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PerfilConsumoVista]
    siguiente_cursor: str | None


class ProblemaVersionPerfilVista(BaseModel):
    """412: el perfil actual en ``actual``, con quién lo guardó."""

    type: str
    title: str
    status: int
    detail: str | None
    errores: list[dict[str, str]]
    request_id: str | None
    actual: PerfilConsumoVista


# --- MATU-37: se acaban pronto y alertas -----------------------------------------------------------------


class InsumoPorAcabarseVista(PerfilConsumoVista):
    """Un insumo en su ventana de aviso, con lo que la pantalla necesita para el bloque «Se acaban pronto»."""

    avisando: bool = Field(
        description=(
            "true si dias_restantes <= dias_aviso y no hay una alerta resuelta ni descartada para la"
            " fecha_quiebre_estimada actual (decisión 74). Después de «Ya lo resolví» pasa a false"
        )
    )
    alerta_id: uuid.UUID | None = Field(
        description=(
            "La alerta de la fecha estimada actual, en cualquier estado. null si el trabajo diario aún no la creó"
        )
    )


class ListaPorAcabarse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InsumoPorAcabarseVista]


class AlertaVista(BaseModel):
    """Una alerta. Solo identificadores, fechas y estado: el nombre del insumo sale del perfil."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    perfil_id: uuid.UUID
    fecha_prevista: date = Field(description="La fecha estimada del perfil cuando se creó la alerta")
    estado: EstadoAlerta
    creada_en: datetime
    notificada_en: datetime | None
    cerrada_en: datetime | None


class ListaAlertas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AlertaVista]
    siguiente_cursor: str | None


class SolicitudResolver(BaseModel):
    """Cuerpo opcional de «Ya lo resolví» (decisiones 76 y 79). Sin cantidad (u omitido o null): la alerta
    pasa a descartada. Con cantidad: se suma a lo que MATU estima que queda hoy, se anota la reposición y la
    alerta pasa a resuelta."""

    model_config = ConfigDict(extra="forbid")

    cantidad: int | None = Field(
        default=None,
        ge=1,
        le=CANTIDAD_MAXIMA,
        description="Cuánto se compró, en la unidad del insumo (no en envases). De 1 a 9999",
    )
