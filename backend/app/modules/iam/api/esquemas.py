"""Esquemas de la API de iam.

Los mensajes de validación propios nunca incluyen el valor recibido: el manejador de 422 copia
el mensaje tal cual (app/core/errores.py), y el valor puede ser una contraseña.
"""

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.modules.iam.domain.credenciales import (
    LARGO_MAXIMO_CONTRASENA,
    LARGO_MAXIMO_EMAIL,
    LARGO_MINIMO_CONTRASENA,
)
from app.modules.iam.domain.dispositivo import LARGO_MAXIMO_NOMBRE, LARGO_MAXIMO_PUSH, push_admitido
from app.shared.celular import normalizar_celular

# Forma básica: algo, una @, un dominio con al menos un punto, sin espacios. La verificación
# real del email llega con el adaptador de correo (sprint 3).
_FORMA_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SolicitudRegistro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(min_length=1, max_length=100)]
    email: Annotated[str, Field(max_length=LARGO_MAXIMO_EMAIL)]
    contrasena: Annotated[str, Field(min_length=LARGO_MINIMO_CONTRASENA, max_length=LARGO_MAXIMO_CONTRASENA)]
    telefono: Annotated[
        str,
        Field(
            max_length=20,
            json_schema_extra={"pattern": r"^(\+?56 ?)?9( ?[0-9]){8}$", "examples": ["+56 9 1234 5678"]},
            description=(
                "Celular chileno, obligatorio (decisión 65): 9 y ocho dígitos, con o sin +56 y con o sin"
                " espacios. Se guarda en E.164 (+569XXXXXXXX). Sirve para recuperar el acceso (MATU-57)."
                " Nunca aparece en logs ni en la auditoría"
            ),
        ),
    ]

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

    @field_validator("telefono")
    @classmethod
    def _celular_chileno(cls, valor: str) -> str:
        normalizado = normalizar_celular(valor.strip())
        if normalizado is None:
            raise PydanticCustomError("celular_invalido", "no es un celular chileno (+56 9 y ocho dígitos)")
        return normalizado


class ProblemaEmailRegistradoVista(BaseModel):
    """409 de POST /v1/usuarios. Solo documenta el OpenAPI: la respuesta la arma app/core/errores.py."""

    type: Literal["/errores/email-registrado"]
    title: str
    status: Literal[409]
    detail: str | None
    errores: list[dict[str, str]]
    request_id: str | None


class CuentaCreadaRespuesta(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str


class SolicitudSesion(BaseModel):
    """Cuerpo de POST /v1/sesiones.

    Sin largo mínimo ni forma de email: un 422 por esas razones distinguiría casos que el login
    responde siempre con el mismo 401. Sí hay tope, para no hashear cuerpos enormes.
    """

    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(max_length=LARGO_MAXIMO_EMAIL)]
    contrasena: Annotated[str, Field(max_length=LARGO_MAXIMO_CONTRASENA)]


class SesionRespuesta(BaseModel):
    """Respuesta de POST /v1/sesiones y de POST /v1/sesiones/renovar. Nunca lleva el refresh."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    # Segundos de vida del access token
    expira_en: int


class DispositivoVista(BaseModel):
    """Un dispositivo propio. Nunca lleva push_token, familia_id, hashes, la IP ni el agente de usuario."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    plataforma: Literal["android", "ios", "web"]
    nombre: Annotated[str, Field(max_length=LARGO_MAXIMO_NOMBRE)]
    creado_en: datetime
    ultimo_uso_en: datetime | None
    actual: bool


class ListaDispositivos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DispositivoVista]


class SolicitudPush(BaseModel):
    """Cuerpo de PUT /v1/dispositivos/actual/push. El valor nunca se repite en un error."""

    model_config = ConfigDict(extra="forbid")

    push_token: Annotated[
        str,
        Field(
            min_length=12,
            max_length=LARGO_MAXIMO_PUSH,
            pattern=r"^https://[^\s]+$",
            json_schema_extra={"format": "uri", "writeOnly": True},
            description=(
                "Endpoint de Web Push del navegador (RFC 8030), solo escritura. https, de hasta 1024"
                " caracteres, con el host en la lista cerrada de servicios de push"
            ),
        ),
    ]

    @field_validator("push_token")
    @classmethod
    def _servicio_admitido(cls, valor: str) -> str:
        if not push_admitido(valor):
            raise PydanticCustomError("push_no_admitido", "el servicio de avisos de este navegador no está admitido")
        return valor
