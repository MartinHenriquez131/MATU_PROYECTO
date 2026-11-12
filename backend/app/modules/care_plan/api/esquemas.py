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
- Secciones complementarias (MATU-50, ficha-ampliada.openapi.yaml): SolicitudSeccion, EstadoSeccionVista
  y SeccionGuardadaVista. El esquema solo rechaza lo que no es texto y los caracteres de control (como
  en los campos base); el vacío (``vacio``) y el máximo por sección (``largo_maximo``: 500, 800 en
  remedios) los decide domain/secciones.py, porque el máximo depende de la ruta. El OpenAPI declara
  minLength 1 y maxLength 800, el mayor, como el contrato.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from app.modules.care_plan.domain.ficha import LARGO_MAXIMO_CAMPO, normalizar_texto, tiene_caracteres_de_control
from app.modules.care_plan.domain.secciones import LARGO_MAXIMO_REMEDIOS, SeccionComplementaria

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


# Sin StringConstraints: el vacío y el máximo dependen de la sección y los responde la ruta con su tipo
TextoSeccion = Annotated[
    str,
    BeforeValidator(_normalizar),
    AfterValidator(_sin_caracteres_de_control),
    Field(
        json_schema_extra={"minLength": 1, "maxLength": LARGO_MAXIMO_REMEDIOS},
        description=(
            "Texto libre, con saltos de línea. Máximo 500 caracteres, 800 en `remedios`, contados después de"
            " quitar los espacios de los extremos. Vacío o solo espacios responde 422 `vacio`"
        ),
    ),
]


class SolicitudCampo(BaseModel):
    """Cuerpo de PUT /v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}. Un campo extra responde 422."""

    model_config = ConfigDict(extra="forbid")

    texto: TextoFicha


class AutorVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str | None = Field(
        description="null si esa persona ya no es miembro activo del grupo o eliminó su cuenta (decisión 309)"
    )
    autor_activo: bool = Field(description="false si ya no está en el grupo: «Alguien que ya no está en el grupo»")


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


class EstadoSeccionVista(BaseModel):
    """Una sección complementaria agregada (MATU-50). No hay estado "vacío": una sección que no está no viene."""

    model_config = ConfigDict(extra="forbid")

    texto: str
    etag: str
    actualizado_por: AutorVista | None
    actualizado_en: datetime


class FichaVista(BaseModel):
    """Respuesta 200 de GET …/plan/ficha: siempre los tres campos, y solo las secciones agregadas."""

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    completitud: Completitud
    actualizado_en: datetime | None
    campos: CamposVista
    secciones: Annotated[
        dict[SeccionComplementaria, EstadoSeccionVista],
        Field(description="Solo las secciones complementarias agregadas (MATU-50). Las que no están no vienen"),
    ]


class CampoGuardadoVista(BaseModel):
    """Respuesta 200 o 201 de PUT …/plan/ficha/{campo}."""

    model_config = ConfigDict(extra="forbid")

    campo: CampoFichaVista
    texto: str | None
    etag: str
    actualizado_por: AutorVista
    actualizado_en: datetime
    completitud: Completitud


class SolicitudSeccion(BaseModel):
    """Cuerpo de PUT …/plan/secciones/{seccion} (MATU-50). Un campo extra responde 422."""

    model_config = ConfigDict(extra="forbid")

    texto: TextoSeccion


class SeccionGuardadaVista(BaseModel):
    """Respuesta 200 o 201 de PUT …/plan/secciones/{seccion}. Sin completitud: las secciones no cuentan."""

    model_config = ConfigDict(extra="forbid")

    seccion: SeccionComplementaria
    texto: str
    etag: str
    actualizado_por: AutorVista
    actualizado_en: datetime


# --- Problemas RFC 7807 de la escritura (MATU-13). Solo documentan el OpenAPI: la respuesta la arma
# app/core/errores.py. Sin modelos anidados nuevos, para que el esquema vaya en línea en el contrato.


class _ProblemaVista(BaseModel):
    detail: str | None
    errores: list[dict[str, str]]
    request_id: str | None


class ProblemaVersionVista(_ProblemaVista):
    """412: If-Match desactualizado o sobre un campo nunca escrito, o If-None-Match: * sobre uno que existe."""

    type: Literal["/errores/version-desactualizada"]
    title: str
    status: Literal[412]
    campo: CampoFichaVista
    # El contenido vigente del campo, descifrado. etag null: el campo nunca se escribió
    actual: EstadoCampoVista


class ProblemaFaltaVersionVista(_ProblemaVista):
    """428: sin If-Match ni If-None-Match, o con If-Match vacío o ``*``."""

    type: Literal["/errores/falta-version"]
    title: str
    status: Literal[428]


class ProblemaVersionSeccionVista(_ProblemaVista):
    """412 de una sección (MATU-50): otra persona se adelantó, o la sección no está (``actual`` null)."""

    type: Literal["/errores/version-desactualizada"]
    title: str
    status: Literal[412]
    # La sección vigente, descifrada, o null si no está (nunca agregada o ya quitada)
    actual: EstadoSeccionVista | None
