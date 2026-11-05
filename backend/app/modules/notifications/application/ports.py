"""Puertos del módulo notifications (MATU-41, ADR-021).

- EnviadorCorreo y EnviadorPush: el envío real lo hará un proveedor que aún no se elige. En el semestre
  solo existen los adaptadores simulados (infrastructure/enviadores_simulados.py, decisión 112).
- UnidadAvisos y RepositorioAvisos: lo que el consumidor lee y escribe, en una transacción con app.rol =
  'sistema' y el grupo del evento (sin saltarse RLS).
- RepositorioPreferencias: la preferencia propia de GET y PUT /v1/yo/avisos (política preferencia_propia).

Ningún dato de destino (email, push_token) ni texto aparece en un ``repr``.
"""

import uuid
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.modules.care_circle.domain.personas import AutorizacionGuardada
from app.modules.notifications.domain.aviso import Canal, CodigoAviso, EstadoNotificacion, ResultadoEnvio
from app.modules.notifications.domain.mensaje import MensajeCorreo


@dataclass(frozen=True)
class EnvioCorreo:
    notificacion_id: uuid.UUID
    usuario_id: uuid.UUID
    plantilla: str
    destino: str = field(repr=False)
    mensaje: MensajeCorreo = field(repr=False)


@dataclass(frozen=True)
class EnvioPush:
    """Un push sin contenido (decisión 50, RFC 8030 con VAPID): no lleva texto. El service worker muestra el
    texto fijo. ``plantilla`` es solo el nombre de la plantilla, para el registro."""

    notificacion_id: uuid.UUID
    usuario_id: uuid.UUID
    plantilla: str
    push_token: str = field(repr=False)


class EnviadorCorreo(Protocol):
    """Envía un correo. Devuelve el resultado ya traducido; nunca lanza con la respuesta del proveedor."""

    def enviar(self, envio: EnvioCorreo) -> ResultadoEnvio: ...


class EnviadorPush(Protocol):
    """Envía un push sin contenido a un dispositivo (decisión 50). EXPIRADO cuando el servicio responde 404 o
    410."""

    def enviar(self, envio: EnvioPush) -> ResultadoEnvio: ...


@dataclass(frozen=True)
class MiembroAviso:
    usuario_id: uuid.UUID
    rol: str
    activo: bool  # membresía activa y usuario activo (sin eliminar)
    # La preferencia guardada por canal para quiebre_proximo, o None si no hay fila
    preferencias: Mapping[Canal, bool | None]


@dataclass(frozen=True)
class NotificacionLeida:
    id: uuid.UUID
    usuario_id: uuid.UUID
    canal: Canal
    estado: EstadoNotificacion
    codigo: CodigoAviso | None


@dataclass(frozen=True)
class ContextoAlerta:
    alerta_abierta: bool  # pendiente o notificada, con su perfil
    autorizacion: AutorizacionGuardada | None  # el consentimiento no revocado para consumo


@dataclass(frozen=True)
class DestinoPush:
    dispositivo_id: uuid.UUID
    push_token: str = field(repr=False)


class RepositorioAvisos(Protocol):
    def ya_consumido(self, evento_id: int, consumidor: str) -> bool: ...

    def marcar_consumido(self, evento_id: int, consumidor: str, ahora: datetime) -> None: ...

    def miembros(self) -> list[MiembroAviso]:
        """Los miembros del grupo, con su estado y sus preferencias para quiebre_proximo."""
        ...

    def miembro(self, usuario_id: uuid.UUID) -> MiembroAviso | None: ...

    def crear(self, evento_id: int, filas: Sequence[tuple[uuid.UUID, Canal]], plantilla: str, ahora: datetime) -> None:
        """Inserta las filas pendientes que no existan (notificacion_uq): un reintento no duplica."""
        ...

    def notificaciones(self, evento_id: int) -> list[NotificacionLeida]: ...

    def bloquear(self, notificacion_id: uuid.UUID) -> NotificacionLeida | None:
        """Relee la fila con FOR UPDATE: dos publicadores nunca envían la misma."""
        ...

    def contexto(self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, persona_id: uuid.UUID) -> ContextoAlerta: ...

    def correo(self, usuario_id: uuid.UUID) -> str | None: ...

    def destinos_push(self, usuario_id: uuid.UUID) -> list[DestinoPush]:
        """Los dispositivos no revocados con push_token."""
        ...

    def actualizar(
        self,
        notificacion_id: uuid.UUID,
        estado: EstadoNotificacion,
        codigo: CodigoAviso | None,
        enviada_en: datetime | None,
    ) -> None: ...

    def expirar_push(self, dispositivo_id: uuid.UUID) -> None:
        """push_token = NULL en ese dispositivo (push 404 o 410)."""
        ...

    def marcar_alerta_notificada(self, alerta_id: uuid.UUID, ahora: datetime) -> None:
        """pendiente -> notificada (solo 'sistema'). Si ya no está pendiente, no hace nada."""
        ...


class UnidadAvisos(Protocol):
    def abrir(self, grupo_id: uuid.UUID) -> AbstractContextManager[RepositorioAvisos]:
        """Una transacción con app.rol = 'sistema' y app.grupo_id: commit al salir bien, rollback si lanza."""
        ...


class RepositorioPreferencias(Protocol):
    """En la sesión del propio usuario (solo app.usuario_id): RLS preferencia_propia y membresia_propia."""

    def guardadas(self, usuario_id: uuid.UUID, tipo_evento: str) -> dict[Canal, bool]: ...

    def roles_activos(self, usuario_id: uuid.UUID) -> set[str]: ...

    def guardar(self, usuario_id: uuid.UUID, tipo_evento: str, valores: Mapping[Canal, bool]) -> None:
        """Inserta o actualiza solo los canales de ``valores``: los demás quedan como estaban."""
        ...
