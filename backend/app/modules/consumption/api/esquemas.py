"""Esquemas de la API del consumo (MATU-36, MATU-37 y MATU-60). Contrato: docs/api/openapi.json.

- Los cuerpos usan extra="forbid": stock_medido_en, grupo_id, producto_id en la edición, activo o
  cualquier otro campo extra responden 422.
- nombre_libre: 1 a 60 caracteres después de quitar los espacios de los extremos, una línea, sin
  caracteres de control. El 422 nunca repite el valor (app/core/errores.py no copia input ni ctx).
- Las respuestas no llevan grupo_id ni precios.
- unidades_por_envase (MATU-60, decisión 121): opcional, de 1 a 10.000. En el PATCH es el único campo que
  admite null, que lo borra.
- La lista de insumos (MATU-60, decisión 118) trae solo {fecha, items}, sin la persona, la ficha, la tasa,
  el stock, la alerta ni el etag.
"""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.consumption.domain.alerta import CANTIDAD_MAXIMA, ENVASES_MAXIMO, EstadoAlerta
from app.modules.consumption.domain.perfil import (
    DIAS_AVISO_MAXIMO,
    DIAS_AVISO_POR_OMISION,
    LARGO_MAXIMO_NOMBRE_LIBRE,
    STOCK_MAXIMO,
    TASA_DIAS_MAXIMA,
    TASA_UNIDADES_MAXIMA,
    UNIDADES_POR_ENVASE_MAXIMO,
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
UnidadesPorEnvase = Annotated[
    int,
    Field(
        ge=1,
        le=UNIDADES_POR_ENVASE_MAXIMO,
        description=(
            "Cuántas unidades trae cada envase, en la unidad del insumo (unidades, sobres, ml o g). Opcional."
            " Lo usa solo la lista de insumos para sugerir envases enteros (decisión 121)"
        ),
    ),
]


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
    unidades_por_envase: UnidadesPorEnvase | None = None


class SolicitudEdicionPerfil(BaseModel):
    """Edición parcial. Al menos un campo; null no se admite (422 null_no_admitido), salvo en
    unidades_por_envase, donde null lo borra (decisión 121)."""

    model_config = ConfigDict(extra="forbid")

    nombre_libre: NombreLibre | None = None
    tasa_unidades: TasaUnidades | None = None
    tasa_dias: TasaDias | None = None
    stock_unidades: Stock | None = None
    dias_aviso: DiasAviso | None = None
    unidades_por_envase: UnidadesPorEnvase | None = None


class ProductoResumen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    presentacion: str


class AutorPerfilVista(BaseModel):
    """Quién guardó el perfil por última vez: su id y su nombre de pila, nunca el email."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str | None = Field(
        description="null si esa persona ya no es miembro activo del grupo o eliminó su cuenta (decisión 309)"
    )
    autor_activo: bool = Field(description="false si ya no está en el grupo: «Alguien que ya no está en el grupo»")


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
    unidades_por_envase: int | None = Field(
        description="Unidades por envase, en la unidad del insumo. null si no se anotó (decisión 121)"
    )
    fecha_quiebre_estimada: date = Field(
        description="Es una estimación con lo que anotó la familia, no una promesa: stock_medido_en + días de cobertura"
    )
    dias_restantes: int = Field(description="fecha_quiebre_estimada menos hoy (America/Santiago). Negativo: ya pasó")
    activo: bool
    actualizado_por: AutorPerfilVista | None = Field(
        description=(
            "Quién guardó la última vez, con su nombre de pila (decisión 73). Si ya no está en el grupo, nombre null y"
            " autor_activo false (decisión 309). null solo sin autor"
        )
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


class _LoComprado(BaseModel):
    """Lo comprado, compartido por «Ya lo resolví» y «Compré» (decisiones 137 y 147): envases o cantidad, a lo
    más uno. La regla completa (uno solo, envases solo con unidades_por_envase) es cantidad_comprada del
    dominio; aquí van los topes del cuerpo. Sin fecha: ocurrida_en lo fija el servidor con el Reloj."""

    model_config = ConfigDict(extra="forbid")

    envases: int | None = Field(
        default=None,
        ge=1,
        le=ENVASES_MAXIMO,
        description=(
            "Cuántos envases se compraron, de 1 a 99. Solo si el perfil tiene unidades_por_envase (si no, 422"
            " sin_unidades_por_envase). Lo comprado es envases × unidades_por_envase y puede pasar de 10.000"
        ),
    )
    cantidad: int | None = Field(
        default=None,
        ge=1,
        le=CANTIDAD_MAXIMA,
        description="Cuánto se compró en la unidad del insumo (unidades, sobres, ml o g), de 1 a 10.000",
    )


class SolicitudResolver(_LoComprado):
    """Cuerpo opcional de «Ya lo resolví» (decisiones 76, 79 y 147). Sin envases ni cantidad (u omitido o
    null): la alerta pasa a descartada. Con uno de los dos: se suma a lo que MATU estima que queda hoy, se anota
    la compra (`reposicion`) y la alerta pasa a resuelta. Los dos: 422 envases_o_cantidad."""


# --- MATU-51: «Compré» y «Me quedan N» ------------------------------------------------------------------


class SolicitudReposicion(_LoComprado):
    """Cuerpo de «Compré» (decisión 137): exactamente uno de envases y cantidad (si no, 422 envases_o_cantidad).
    Siempre pide la cantidad: el valor por omisión de 1 envase lo pone la pantalla."""


class SolicitudRecuento(BaseModel):
    """Cuerpo de «Me quedan N» (decisión 139): el stock contado hoy, de 0 a 100.000."""

    model_config = ConfigDict(extra="forbid")

    stock_unidades: Stock = Field(description="Cuánto queda hoy, en la unidad del insumo. De 0 a 100.000")


# --- MATU-60: lista de insumos ---------------------------------------------------------------------------

UNIDADES_SUGERIDAS_MAXIMO = 300_000


class LineaListaInsumos(BaseModel):
    """Una línea de la lista (decisión 118). Sin la tasa, el stock, la fecha estimada, precios, comercios, la
    alerta ni el etag. El nombre puede decir algo de la salud de la persona: nunca va a logs ni errores."""

    model_config = ConfigDict(extra="forbid")

    perfil_id: uuid.UUID = Field(description="El perfil de consumo de esta línea (PerfilConsumoVista.id)")
    nombre: str = Field(
        min_length=1,
        description="producto.nombre si el perfil es de un producto, o nombre_libre si no. Nunca la presentación",
    )
    unidad: UnidadConsumo
    dias_restantes: int = Field(
        description=(
            "fecha_quiebre_estimada menos fecha, en días, como en PerfilConsumoVista. Solo para la pantalla: el"
            " texto que se imprime o se comparte no lo lleva (ADR-031, punto 4)"
        )
    )
    unidades_sugeridas: int = Field(
        ge=1,
        le=UNIDADES_SUGERIDAS_MAXIMO,
        description=(
            "Lo que falta para 30 días, en la unidad del insumo: max(1, techo(30 × tasa_unidades / tasa_dias)"
            " - lo que MATU estima que queda hoy) (decisiones 119 y 120)"
        ),
    )
    unidades_por_envase: int | None = Field(
        ge=1,
        le=UNIDADES_POR_ENVASE_MAXIMO,
        description="El del perfil, nunca el del catálogo (decisión 121). null si no se anotó",
    )
    envases_sugeridos: int | None = Field(
        ge=1,
        le=UNIDADES_SUGERIDAS_MAXIMO,
        description="techo(unidades_sugeridas / unidades_por_envase), o null si el perfil no tiene unidades_por_envase",
    )
    producto_id: uuid.UUID | None = Field(
        description=(
            "MATU-61 (decisión 215): el producto del catálogo del perfil, o null si el insumo se anotó con"
            " nombre_libre. «Pedir estos productos» pasa al pedido solo las líneas con producto"
        )
    )


class ListaInsumos(BaseModel):
    """La lista de insumos de hoy (decisión 118): sin el nombre de la persona, el grupo, la ficha ni acciones."""

    model_config = ConfigDict(extra="forbid")

    fecha: date = Field(description="Hoy en America/Santiago según el Reloj de la API, el mismo de dias_restantes")
    items: list[LineaListaInsumos] = Field(
        description="En el orden de la decisión 117. Vacía si ningún insumo de «Se acaban pronto» está avisando"
    )
