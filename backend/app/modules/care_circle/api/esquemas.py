"""Esquemas de la API de care_circle.

Los mensajes de validación propios nunca incluyen el valor recibido: el manejador de 422 copia
el mensaje tal cual (app/core/errores.py).
"""

import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.care_circle.domain.grupos import normalizar_nombre


class SolicitudGrupo(BaseModel):
    """Cuerpo de POST /v1/grupos."""

    model_config = ConfigDict(extra="forbid")

    nombre: str

    @field_validator("nombre")
    @classmethod
    def _nombre_valido(cls, valor: str) -> str:
        # NombreGrupoInvalido es un ValueError con un mensaje fijo, sin el nombre
        return normalizar_nombre(valor)


class GrupoRespuesta(BaseModel):
    id: uuid.UUID
    nombre: str
    rol: str
