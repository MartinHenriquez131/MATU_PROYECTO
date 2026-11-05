"""Esquemas del acceso de relevo (MATU-18). Contrato: docs/api/propuestos/relevo.openapi.yaml.

Ningún mensaje de validación repite el valor recibido (app/core/errores.py copia solo campo, mensaje
y tipo). El token y el PIN solo existen en AccesoCreadoVista, que se entrega una vez.

MATU-50 (ficha-ampliada.openapi.yaml): al compartir, los tres campos base van siempre y
``secciones_adicionales`` elige las secciones complementarias (0 a 6, sin repetir, por defecto ninguna).
``campos`` queda deprecado: si viene, debe traer los tres campos base (422 ``campos_base_obligatorios``).
El relevo recibe ``secciones`` y cada apertura de la auditoría, los tipos mostrados.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.modules.care_plan.domain.aperturas import TipoApertura
from app.modules.care_plan.domain.ficha import CAMPOS_FICHA, CampoFicha, tiene_caracteres_de_control
from app.modules.care_plan.domain.relevo import (
    LARGO_MAXIMO_NOMBRE_RELEVO,
    PATRON_CELULAR,
    EstadoAcceso,
    MotivoAcceso,
)
from app.modules.care_plan.domain.secciones import SECCIONES_COMPLEMENTARIAS, SeccionComplementaria

_MENSAJE_CAMPOS = "si viene, debe traer los tres campos base; los tres van siempre"


class SolicitudAccesoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_relevo: str
    telefono_relevo: Annotated[str, Field(pattern=PATRON_CELULAR)]
    # MATU-50: deprecado. Los tres campos base van siempre; si viene, debe traer los tres (o 422)
    campos: Annotated[
        list[CampoFicha] | None,
        Field(
            deprecated=True,
            description="Deprecado. Si viene, debe tener los tres campos base; si no, 422 campos_base_obligatorios",
            json_schema_extra={"minItems": 3, "maxItems": 3, "uniqueItems": True},
        ),
    ] = None
    # MATU-50: las secciones complementarias que también ve el relevo. remedios solo si viene (ADR-028)
    secciones_adicionales: Annotated[
        list[SeccionComplementaria],
        Field(
            max_length=len(SECCIONES_COMPLEMENTARIAS),
            json_schema_extra={"uniqueItems": True},
            description=(
                "Secciones complementarias que también ve el relevo, sin repetir. Cada una debe estar agregada"
                " (si no, 422 seccion_no_agregada). El servidor nunca agrega una por su cuenta"
            ),
        ),
    ] = Field(default_factory=list)
    expira_en: AwareDatetime | None = None
    motivo: MotivoAcceso
    # Decisión 34: quien comparte declara que le avisó al relevo qué datos guarda MATU. Obligatorio y true
    relevo_informado: bool

    @field_validator("relevo_informado")
    @classmethod
    def _aviso_declarado(cls, valor: bool) -> bool:
        if valor is not True:
            raise ValueError("hay que declarar que se le avisó al relevo")
        return valor

    @field_validator("nombre_relevo")
    @classmethod
    def _una_linea(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio or tiene_caracteres_de_control(limpio) or "\n" in limpio:
            raise ValueError("debe ser una línea con texto")
        if len(limpio) > LARGO_MAXIMO_NOMBRE_RELEVO:
            raise ValueError("admite hasta 60 caracteres")
        return limpio

    @field_validator("campos", mode="before")
    @classmethod
    def _campos_no_nulo(cls, valor: object) -> object:
        # Omitir campos es la forma nueva; un null explícito no equivale a omitirlo
        if valor is None:
            raise PydanticCustomError("campos_base_obligatorios", _MENSAJE_CAMPOS)
        return valor

    @field_validator("campos")
    @classmethod
    def _los_tres_campos(cls, valor: list[CampoFicha] | None) -> list[CampoFicha] | None:
        if valor is not None and (len(valor) != len(CAMPOS_FICHA) or set(valor) != set(CAMPOS_FICHA)):
            raise PydanticCustomError("campos_base_obligatorios", _MENSAJE_CAMPOS)
        return valor

    @field_validator("secciones_adicionales")
    @classmethod
    def _sin_repetir(cls, valor: list[SeccionComplementaria]) -> list[SeccionComplementaria]:
        if len(set(valor)) != len(valor):
            raise PydanticCustomError("duplicado", "una sección no se puede repetir")
        return valor


class AccesoCreadoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    url: str
    pin: str
    # Siempre los tres campos base (MATU-50)
    campos: list[CampoFicha]
    secciones_adicionales: list[SeccionComplementaria]
    expira_en: datetime
    nombre_relevo: str
    nombre_pila_persona: str


class AutorAccesoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str


class AccesoResumenVista(BaseModel):
    """telefono_relevo solo para admin y cuidador: para el pagador la propiedad no viene (decisión 31).
    otorgado_por.nombre es el nombre de pila de quien compartió, nunca el completo (decisión 35)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre_relevo: str
    telefono_relevo: str | None = None
    # Los campos base del acceso: siempre los tres desde MATU-50; uno, dos o tres en los anteriores
    campos: list[CampoFicha]
    # Las secciones compartidas, [] en los accesos anteriores a MATU-50
    secciones_adicionales: list[SeccionComplementaria]
    motivo: MotivoAcceso
    estado: EstadoAcceso
    creado_en: datetime
    expira_en: datetime
    revocado_en: datetime | None
    usos: int
    ultimo_uso_en: datetime | None
    otorgado_por: AutorAccesoVista | None


class ListaAccesosVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AccesoResumenVista]
    siguiente_cursor: str | None


# --- Ver quién abrió la ficha (MATU-45) -------------------------------------------------------------------


class AccesoDeAperturaVista(BaseModel):
    """El acceso de una apertura: su id y el nombre que le puso la familia. Nunca el teléfono."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre_relevo: str


class AperturaVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocurrido_en: datetime
    tipo: TipoApertura
    acceso: AccesoDeAperturaVista
    # MATU-50: solo en tipo apertura, los tipos de las secciones mostradas. Nunca texto
    secciones: Annotated[
        list[SeccionComplementaria],
        Field(description="Solo en `tipo: apertura`. Tipos mostrados, sin texto"),
    ] = Field(default_factory=list)


class ListaAperturasVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AperturaVista]
    siguiente_cursor: str | None


# --- Abrir la ficha como relevo (MATU-19) ---------------------------------------------------------------


class SolicitudPresentacionVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No se valida la forma: un token desconocido o cortado responde 410, no 422
    token: Annotated[str, Field(min_length=1, max_length=128)]


class SolicitudCanjeVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: Annotated[str, Field(min_length=1, max_length=128)]
    pin: Annotated[str, Field(pattern=r"^[0-9]{4}$")]


class PresentacionVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_pila_comparte: str
    nombre_pila: str


class CampoRelevoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str | None


class SeccionRelevoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: SeccionComplementaria
    texto: str


class FichaRelevoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_pila: str
    nombre_pila_comparte: str
    vence_en: datetime
    campos: dict[CampoFicha, CampoRelevoVista]
    # MATU-50: solo las secciones compartidas que siguen agregadas y nacieron antes del acceso, en el orden
    # de ADR-028 (quien_es, preferencias, alimentacion, movilidad, comunicacion, remedios)
    secciones: list[SeccionRelevoVista]
