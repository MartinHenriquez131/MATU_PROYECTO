"""Esquemas de la API de personas cuidadas (MATU-07, RF-01).

- El cuerpo del alta y la dirección anidada usan extra="forbid": un campo que no está aquí, por
  ejemplo un diagnóstico, una versión de la política o coordenadas, responde 422.
- No hay campo de diagnóstico (arquitectura 11.3) ni de versión de la política: la fija el servidor.
- Los mensajes de validación propios nunca incluyen el valor recibido, y el manejador de 422 no
  copia ni input ni ctx (app/core/errores.py).
- Cada vista de lectura es un DTO distinto por rol (arquitectura 11.1 y 11.2), con extra="forbid"
  para que una respuesta nunca calce con una vista más amplia que la del rol.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.modules.care_circle.domain.personas import (
    LARGO_MAXIMO_NOMBRE,
    LARGO_MAXIMO_NOMBRE_PILA,
    LARGO_MAXIMO_REFERENCIA,
    CalidadOtorgante,
)

NivelApoyo = Literal["autovalente_con_supervision", "apoyo_parcial", "apoyo_total"]


def _sin_caracteres_de_control(valor: str) -> str:
    if any(ord(c) < 32 or 127 <= ord(c) < 160 for c in valor):
        raise ValueError("solo admite texto, sin saltos de línea ni caracteres de control")
    return valor


# Todos los textos son de una línea, sin espacios en los extremos y con un largo máximo
Nombre = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_NOMBRE),
    AfterValidator(_sin_caracteres_de_control),
]
NombrePila = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=LARGO_MAXIMO_NOMBRE_PILA),
    AfterValidator(_sin_caracteres_de_control),
]
# Vacía se acepta aquí y cuenta como ausente: la regla de la calidad decide si responde 422
ReferenciaDocumento = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=LARGO_MAXIMO_REFERENCIA),
    AfterValidator(_sin_caracteres_de_control),
]
Texto20 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
                    AfterValidator(_sin_caracteres_de_control)]
Texto40 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40),
                    AfterValidator(_sin_caracteres_de_control)]
Texto60 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
                    AfterValidator(_sin_caracteres_de_control)]
Texto120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
                     AfterValidator(_sin_caracteres_de_control)]
Texto200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
                     AfterValidator(_sin_caracteres_de_control)]


class DireccionNueva(BaseModel):
    """Dirección de entrega opcional del alta. Sin lat ni lng: un campo extra responde 422."""

    model_config = ConfigDict(extra="forbid")

    etiqueta: Texto40 = "Casa"
    calle: Texto120
    numero: Texto20
    depto: Texto20 | None = None
    comuna: Texto60
    region: Texto60 = "Metropolitana"
    referencia: Texto200 | None = None


class AvisoMostradoEntrada(BaseModel):
    """El aviso que se mostró al elegir la calidad: solo su identificador y su versión."""

    model_config = ConfigDict(extra="forbid")

    id: Texto60
    version: Texto20


class SolicitudPersona(BaseModel):
    """Cuerpo de POST /v1/grupos/{grupo_id}/personas-cuidadas."""

    model_config = ConfigDict(extra="forbid")

    nombre: Nombre
    nombre_pila: NombrePila
    nivel_apoyo: NivelApoyo
    calidad_otorgante: CalidadOtorgante
    referencia_documento: ReferenciaDocumento | None = None
    aviso: AvisoMostradoEntrada | None = None
    direccion: DireccionNueva | None = None


# --- Respuestas ------------------------------------------------------------------------------------


class DireccionVista(BaseModel):
    model_config = ConfigDict(extra="forbid")

    etiqueta: str
    calle: str
    numero: str
    depto: str | None
    comuna: str
    region: str
    referencia: str | None


class ConsentimientoVista(BaseModel):
    """El consentimiento vigente para plan_cuidado. Sin la referencia al documento ni la evidencia."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    calidad_otorgante: CalidadOtorgante
    finalidad: str
    version_politica: str
    otorgado_en: datetime
    revision_vence_en: datetime | None


class AvisoVista(BaseModel):
    """El aviso canónico que se mostró, con su texto completo y su huella."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    titulo: str
    parrafos: list[str]
    sha256: str


class PersonaCreada(BaseModel):
    """Respuesta 201 del alta. ``aviso`` es el texto del aviso de limitación para un cuidador de
    hecho, y null para las demás calidades."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    nombre_pila: str
    nivel_apoyo: NivelApoyo
    direccion: DireccionVista | None
    consentimiento: ConsentimientoVista
    aviso: AvisoVista | None


class PersonaVistaCompleta(BaseModel):
    """Lo que ven admin y cuidador."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    nombre_pila: str
    nivel_apoyo: NivelApoyo
    direccion: DireccionVista | None
    consentimiento: ConsentimientoVista | None


class PersonaVistaPagador(BaseModel):
    """Lo que ve el pagador: nombre y dirección."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    direccion: DireccionVista | None


class PersonaVistaObservador(BaseModel):
    """Lo que ve el observador: el nombre."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
