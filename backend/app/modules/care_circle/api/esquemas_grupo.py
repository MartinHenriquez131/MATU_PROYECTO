"""Esquemas de las invitaciones y los miembros del grupo (MATU-42, contrato invitar-familiar.openapi.yaml).

Todos con extra="forbid": un campo de más en el cuerpo es 422, y en la respuesta nunca aparece algo que el contrato no
declara (C9: sin email, celular ni usuario_id). Los mensajes de validación nunca repiten el valor recibido.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Rol = Literal["admin", "cuidador", "pagador", "observador"]
Token = Annotated[str, StringConstraints(min_length=1, max_length=128)]
Codigo = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")]


class _Cerrado(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Invitaciones ---------------------------------------------------------------------------------------


class SolicitudInvitacion(_Cerrado):
    """Solo el rol (C8). Sin correo, teléfono ni puede_ver_plan (D-42-1 a)."""

    rol: Rol


class InvitacionCreada(_Cerrado):
    """La invitación recién creada (P9). url y codigo salen solo aquí y una sola vez."""

    id: uuid.UUID
    rol: Rol
    url: str = Field(description="`{ORIGEN_WEB}/invitacion#<token>`, con el token de 256 bits en el fragmento (C21)")
    codigo: str = Field(pattern=r"^[0-9]{4}$", description="4 dígitos que se dictan aparte. Se guarda solo su HMAC")
    creada_en: datetime
    expira_en: datetime


class InvitadaPor(_Cerrado):
    nombre: str | None = Field(description="Nombre de pila copiado en la invitación, o null si ya no es miembro activo")
    autor_activo: bool
    eres_tu: bool


class InvitacionVista(_Cerrado):
    """Una invitación sin usar, para quien administra. Nunca el token, el código ni los intentos."""

    id: uuid.UUID
    rol: Rol
    estado: Literal["pendiente", "bloqueada"]
    creada_en: datetime
    expira_en: datetime
    invitada_por: InvitadaPor


class ListaInvitaciones(_Cerrado):
    invitaciones: list[InvitacionVista] = Field(max_length=200)


class SolicitudPresentacionInvitacion(_Cerrado):
    token: Token


class PresentacionInvitacion(_Cerrado):
    """Lo único que se ve antes del código (C1, D-42-4 a, P2)."""

    nombre_pila_invita: str
    rol: Rol
    expira_en: datetime


class SolicitudCanjeInvitacion(_Cerrado):
    token: Token
    codigo: Codigo


class VerificacionInvitacion(_Cerrado):
    """Lo que C2 pide mostrar antes de «Unirme al grupo» (P3). Sin intentos_restantes (decisión 325)."""

    nombre_pila_invita: str
    grupo: str
    personas: list[str] = Field(max_length=20)
    rol: Rol
    expira_en: datetime


class Union(_Cerrado):
    """El grupo al que se unió, para fijar X-Grupo-Id en memoria."""

    grupo_id: uuid.UUID
    membresia_id: uuid.UUID
    grupo: str
    rol: Rol
    puede_ver_plan: bool


# --- Miembros -------------------------------------------------------------------------------------------


class MiembroVista(_Cerrado):
    """Un miembro activo (C9). Nunca el email, el celular ni el usuario_id."""

    id: uuid.UUID = Field(description="El id de la membresía, que usan PATCH y DELETE …/miembros/{membresia_id}")
    nombre: str
    rol: Rol
    puede_ver_plan: bool | None = Field(description="Solo del pagador; null para los demás roles")
    unido_en: datetime
    eres_tu: bool
    etag: str = Field(pattern=r'^"v[0-9]+"$')
    enlaces_vigentes: int | None = Field(
        ge=0, description="Accesos de relevo vigentes que compartió: para quien administra y en la propia fila"
    )


class ListaMiembros(_Cerrado):
    miembros: list[MiembroVista] = Field(min_length=1)


class SolicitudCambioMiembro(_Cerrado):
    """rol, puede_ver_plan o los dos. null en cualquiera es 422."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1})

    rol: Rol | None = None
    puede_ver_plan: bool | None = None

    @model_validator(mode="after")
    def _al_menos_uno_y_sin_null(self) -> "SolicitudCambioMiembro":
        if not self.model_fields_set:
            raise ValueError("trae rol, puede_ver_plan o los dos")
        for campo in sorted(self.model_fields_set):
            if getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser null")
        return self


class ResultadoCambioMiembro(_Cerrado):
    miembro: MiembroVista
    enlaces_cortados: int = Field(ge=0)


class ResultadoSalida(_Cerrado):
    enlaces_cortados: int = Field(ge=0)
