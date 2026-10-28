"""Esquemas de la API de la ficha de relevo (MATU-12, RF-02).

Calzan con docs/api/propuestos/ficha.openapi.yaml: SolicitudCampo, Ficha, EstadoCampo, Autor y
CampoGuardado, todos con extra="forbid".

- El texto se normaliza antes de validar: ``\r\n`` pasa a ``\n`` y se quitan los espacios de los
  extremos. Después se cuentan los 500 caracteres (tipo string_too_long) y se rechaza cualquier
  carácter de control que no sea el salto de línea.
- Un 422 nunca repite el texto: el mensaje propio es fijo, y el manejador de app/core/errores.py
  no copia ni input ni ctx de Pydantic.
- El autor lleva solo id y nombre, nunca el email (analista normativo, condición 6).
- No llevan las preguntas guía ni los ejemplos de cada campo: son textos de la interfaz y salen de
  docs/lenguaje.md, secciones 5.1 a 5.3 (el contrato los deja fuera a propósito).
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints

from app.modules.care_plan.domain.ficha import LARGO_MAXIMO_CAMPO, normalizar_texto, tiene_caracteres_de_control

CampoFichaVista = Literal["rutina", "manejo_situaciones", "red_apoyo"]
Completitud = Literal[0, 33, 67, 100]


def _normalizar(valor: object) -> object:
    # Solo normaliza texto: un número o un null siguen a la validación de str, que responde 422
    return normalizar_texto(valor) if isinstance(valor, str) else valor


def _sin_caracteres_de_control(valor: str) -> str:
    if tiene_caracteres_de_control(valor):
        raise ValueError("solo admite texto y saltos de línea, sin otros caracteres de control")
    return valor


# StringConstraints va antes que BeforeValidator: así la normalización corre primero y el largo se
# cuenta sobre el texto ya normalizado
TextoFicha = Annotated[
    str,
    StringConstraints(max_length=LARGO_MAXIMO_CAMPO),
    BeforeValidator(_normalizar),
    AfterValidator(_sin_caracteres_de_control),
]


class SolicitudCampo(BaseModel):
    """Cuerpo de PUT /v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}. Un campo extra responde 422."""

    model_config = ConfigDict(extra="forbid")

    texto: TextoFicha


class AutorVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str


class EstadoCampoVista(BaseModel):
    """Un campo: nunca escrito (todo null), vaciado (texto null con etag) o escrito."""

    model_config = ConfigDict(extra="forbid")

    texto: str | None
    etag: str | None
    actualizado_por: AutorVista | None
    actualizado_en: datetime | None


class CamposVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rutina: EstadoCampoVista
    manejo_situaciones: EstadoCampoVista
    red_apoyo: EstadoCampoVista


class FichaVista(BaseModel):
    """Respuesta 200 de GET …/plan/ficha: siempre los tres campos."""

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    completitud: Completitud
    actualizado_en: datetime | None
    campos: CamposVista


class CampoGuardadoVista(BaseModel):
    """Respuesta 200 o 201 de PUT …/plan/ficha/{campo}."""

    model_config = ConfigDict(extra="forbid")

    campo: CampoFichaVista
    texto: str | None
    etag: str
    actualizado_por: AutorVista
    actualizado_en: datetime
    completitud: Completitud
