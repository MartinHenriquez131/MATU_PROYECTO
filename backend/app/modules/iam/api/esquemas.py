"""Esquemas de la API de iam.

Los mensajes de validación propios nunca incluyen el valor recibido: el manejador de 422 copia
el mensaje tal cual (app/core/errores.py), y el valor puede ser una contraseña.
"""

import re
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.iam.domain.credenciales import (
    LARGO_MAXIMO_CONTRASENA,
    LARGO_MAXIMO_EMAIL,
    LARGO_MINIMO_CONTRASENA,
)

# Forma básica: algo, una @, un dominio con al menos un punto, sin espacios. La verificación
# real del email llega con el adaptador de correo (sprint 3).
_FORMA_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SolicitudRegistro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str, Field(max_length=LARGO_MAXIMO_EMAIL)]
    contrasena: Annotated[str, Field(min_length=LARGO_MINIMO_CONTRASENA, max_length=LARGO_MAXIMO_CONTRASENA)]

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("el nombre no puede estar vacío")
        return valor

    @field_validator("email")
    @classmethod
    def _forma_de_email(cls, valor: str) -> str:
        if not _FORMA_EMAIL.match(valor.strip()):
            raise ValueError("no tiene la forma de un email")
        return valor


class CuentaCreadaRespuesta(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str
