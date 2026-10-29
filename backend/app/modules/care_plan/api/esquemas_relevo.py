"""Esquemas del acceso de relevo (MATU-18). Contrato: docs/api/propuestos/relevo.openapi.yaml.

Ningún mensaje de validación repite el valor recibido (app/core/errores.py copia solo campo, mensaje
y tipo). El token y el PIN solo existen en AccesoCreadoVista, que se entrega una vez.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.modules.care_plan.domain.ficha import CampoFicha, tiene_caracteres_de_control
from app.modules.care_plan.domain.relevo import (
    LARGO_MAXIMO_NOMBRE_RELEVO,
    PATRON_CELULAR,
    EstadoAcceso,
    MotivoAcceso,
)


class SolicitudAccesoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_relevo: str
    telefono_relevo: Annotated[str, Field(pattern=PATRON_CELULAR)]
    campos: Annotated[list[CampoFicha], Field(min_length=1, max_length=3)]
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

    @field_validator("campos")
    @classmethod
    def _sin_repetir(cls, valor: list[CampoFicha]) -> list[CampoFicha]:
        if len(set(valor)) != len(valor):
            raise ValueError("un campo no se puede repetir")
        return valor


class AccesoCreadoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    url: str
    pin: str
    campos: list[CampoFicha]
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
    campos: list[CampoFicha]
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


class FichaRelevoVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_pila: str
    nombre_pila_comparte: str
    vence_en: datetime
    campos: dict[CampoFicha, CampoRelevoVista]
