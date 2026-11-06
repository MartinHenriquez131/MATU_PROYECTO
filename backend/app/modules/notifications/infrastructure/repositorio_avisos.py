"""Los puertos UnidadAvisos y RepositorioAvisos sobre PostgreSQL (MATU-41, migración 0014).

Cada transacción se abre con sesion_tenant, app.rol = 'sistema' y el grupo del evento, como el trabajo
diario: nunca un rol que se salte RLS.

- membresia, usuario (usuario_comiembro), consentimiento, perfil_consumo y alerta_quiebre: las políticas
  que ya existen para el grupo del contexto.
- preferencia_notificacion: preferencia_sistema (solo lectura).
- notificacion: notificacion_sistema (las filas del grupo del contexto).
- dispositivo: dispositivo_sistema_leer y dispositivo_sistema_expirar (0014), solo de miembros activos del
  grupo, y el sistema solo puede borrar el push_token.
- evento_consumido: tabla de infraestructura sin RLS; matu_app lee e inserta.

Nada de lo que se lee aquí (email, push_token) sale en un log, una excepción o un ``repr``.
"""

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.care_circle.domain.personas import FINALIDAD_CONSUMO, AutorizacionGuardada
from app.modules.notifications.application.ports import (
    ContextoAlerta,
    DestinoPush,
    MiembroAviso,
    NotificacionLeida,
    RepositorioAvisos,
)
from app.modules.notifications.domain.aviso import TIPO_EVENTO_QUIEBRE, Canal, CodigoAviso, EstadoNotificacion

_MIEMBROS = (
    "SELECT m.usuario_id, m.rol,"
    " (m.estado = 'activa' AND u.estado = 'activo' AND u.eliminado_en IS NULL) AS activo,"
    " (SELECT p.activo FROM preferencia_notificacion p WHERE p.usuario_id = m.usuario_id"
    "  AND p.tipo_evento = :tipo AND p.canal = 'correo') AS correo,"
    " (SELECT p.activo FROM preferencia_notificacion p WHERE p.usuario_id = m.usuario_id"
    "  AND p.tipo_evento = :tipo AND p.canal = 'push') AS push"
    " FROM membresia m JOIN usuario u ON u.id = m.usuario_id"
    " WHERE m.grupo_id = :grupo"
)
_TODOS = text(_MIEMBROS + " ORDER BY m.usuario_id")
_UNO = text(_MIEMBROS + " AND m.usuario_id = :usuario")

_YA_CONSUMIDO = text("SELECT 1 FROM evento_consumido WHERE evento_id = :evento AND consumidor = :consumidor")
_CONSUMIDO = text(
    "INSERT INTO evento_consumido (evento_id, consumidor, consumido_en) VALUES (:evento, :consumidor, :ahora)"
    " ON CONFLICT DO NOTHING"
)
_CREAR = text(
    "INSERT INTO notificacion (id, usuario_id, grupo_id, evento_id, canal, plantilla, estado, creada_en)"
    " VALUES (:id, :usuario, :grupo, :evento, :canal, :plantilla, 'pendiente', :ahora)"
    " ON CONFLICT ON CONSTRAINT notificacion_uq DO NOTHING"
)
_NOTIFICACIONES = text(
    "SELECT id, usuario_id, canal, estado, error FROM notificacion"
    " WHERE evento_id = :evento AND grupo_id = :grupo ORDER BY usuario_id, canal"
)
_BLOQUEAR = text(
    "SELECT id, usuario_id, canal, estado, error FROM notificacion WHERE id = :id AND grupo_id = :grupo FOR UPDATE"
)
# Un solo consentimiento no revocado por persona y finalidad (consentimiento_vigente_uq)
_CONTEXTO = text(
    "SELECT EXISTS (SELECT 1 FROM alerta_quiebre a JOIN perfil_consumo p ON p.id = a.perfil_id"
    "   WHERE a.id = :alerta AND a.perfil_id = :perfil AND p.grupo_id = :grupo"
    "   AND p.persona_cuidada_id = :persona AND a.estado IN ('pendiente', 'notificada')) AS abierta,"
    " c.calidad_otorgante, c.revision_vence_en"
    " FROM (SELECT 1) AS uno"
    " LEFT JOIN consentimiento c ON c.persona_cuidada_id = :persona AND c.grupo_id = :grupo"
    " AND c.finalidad = :finalidad AND c.revocado_en IS NULL"
)
_CORREO = text("SELECT email FROM usuario WHERE id = :usuario")
_PUSH = text(
    "SELECT id, push_token FROM dispositivo WHERE usuario_id = :usuario AND revocado_en IS NULL"
    " AND push_token IS NOT NULL ORDER BY creado_en, id"
)
_ACTUALIZAR = text(
    "UPDATE notificacion SET estado = :estado, error = :error, enviada_en = :enviada_en"
    " WHERE id = :id AND grupo_id = :grupo"
)
_EXPIRAR = text("UPDATE dispositivo SET push_token = NULL WHERE id = :id")
_NOTIFICADA = text(
    "UPDATE alerta_quiebre SET estado = 'notificada', notificada_en = :ahora WHERE id = :id AND estado = 'pendiente'"
)


def _miembro(fila: Any) -> MiembroAviso:
    return MiembroAviso(
        usuario_id=fila.usuario_id,
        rol=fila.rol,
        activo=bool(fila.activo),
        preferencias={Canal.CORREO: fila.correo, Canal.PUSH: fila.push},
    )


def _notificacion(fila: Any) -> NotificacionLeida:
    return NotificacionLeida(
        id=fila.id,
        usuario_id=fila.usuario_id,
        canal=Canal(fila.canal),
        estado=EstadoNotificacion(fila.estado),
        codigo=CodigoAviso(fila.error) if fila.error else None,
    )


class RepositorioAvisosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def __repr__(self) -> str:
        return "RepositorioAvisosSQL()"

    def ya_consumido(self, evento_id: int, consumidor: str) -> bool:
        return self._sesion.execute(_YA_CONSUMIDO, {"evento": evento_id, "consumidor": consumidor}).first() is not None

    def marcar_consumido(self, evento_id: int, consumidor: str, ahora: datetime) -> None:
        self._sesion.execute(_CONSUMIDO, {"evento": evento_id, "consumidor": consumidor, "ahora": ahora})

    def miembros(self) -> list[MiembroAviso]:
        filas = self._sesion.execute(_TODOS, {"grupo": self._grupo_id, "tipo": TIPO_EVENTO_QUIEBRE}).all()
        return [_miembro(f) for f in filas]

    def miembro(self, usuario_id: uuid.UUID) -> MiembroAviso | None:
        fila = self._sesion.execute(
            _UNO, {"grupo": self._grupo_id, "tipo": TIPO_EVENTO_QUIEBRE, "usuario": usuario_id}
        ).first()
        return None if fila is None else _miembro(fila)

    def crear(self, evento_id: int, filas: Sequence[tuple[uuid.UUID, Canal]], plantilla: str, ahora: datetime) -> None:
        if not filas:
            return
        self._sesion.execute(
            _CREAR,
            [
                {
                    "id": uuid.uuid4(),
                    "usuario": usuario_id,
                    "grupo": self._grupo_id,
                    "evento": evento_id,
                    "canal": canal.value,
                    "plantilla": plantilla,
                    "ahora": ahora,
                }
                for usuario_id, canal in filas
            ],
        )

    def notificaciones(self, evento_id: int) -> list[NotificacionLeida]:
        filas = self._sesion.execute(_NOTIFICACIONES, {"evento": evento_id, "grupo": self._grupo_id}).all()
        return [_notificacion(f) for f in filas]

    def bloquear(self, notificacion_id: uuid.UUID) -> NotificacionLeida | None:
        fila = self._sesion.execute(_BLOQUEAR, {"id": notificacion_id, "grupo": self._grupo_id}).first()
        return None if fila is None else _notificacion(fila)

    def contexto(self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, persona_id: uuid.UUID) -> ContextoAlerta:
        fila = self._sesion.execute(
            _CONTEXTO,
            {
                "alerta": alerta_id,
                "perfil": perfil_id,
                "persona": persona_id,
                "grupo": self._grupo_id,
                "finalidad": FINALIDAD_CONSUMO,
            },
        ).one()
        autorizacion = None
        if fila.calidad_otorgante is not None:
            autorizacion = AutorizacionGuardada(
                calidad_otorgante=fila.calidad_otorgante, revision_vence_en=fila.revision_vence_en
            )
        return ContextoAlerta(alerta_abierta=bool(fila.abierta), autorizacion=autorizacion)

    def correo(self, usuario_id: uuid.UUID) -> str | None:
        valor = self._sesion.execute(_CORREO, {"usuario": usuario_id}).scalar()
        return None if valor is None else str(valor)

    def destinos_push(self, usuario_id: uuid.UUID) -> list[DestinoPush]:
        filas = self._sesion.execute(_PUSH, {"usuario": usuario_id}).all()
        return [DestinoPush(dispositivo_id=f.id, push_token=f.push_token) for f in filas]

    def actualizar(
        self,
        notificacion_id: uuid.UUID,
        estado: EstadoNotificacion,
        codigo: CodigoAviso | None,
        enviada_en: datetime | None,
    ) -> None:
        self._sesion.execute(
            _ACTUALIZAR,
            {
                "id": notificacion_id,
                "grupo": self._grupo_id,
                "estado": estado.value,
                "error": codigo.value if codigo else None,
                "enviada_en": enviada_en,
            },
        )

    def expirar_push(self, dispositivo_id: uuid.UUID) -> None:
        self._sesion.execute(_EXPIRAR, {"id": dispositivo_id})

    def marcar_alerta_notificada(self, alerta_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(_NOTIFICADA, {"id": alerta_id, "ahora": ahora})


class UnidadAvisosSQL:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def __repr__(self) -> str:
        return "UnidadAvisosSQL()"

    @contextmanager
    def abrir(self, grupo_id: uuid.UUID) -> Iterator[RepositorioAvisos]:
        with sesion_tenant(self._fabrica, grupo_id=grupo_id, rol="sistema") as sesion:
            yield RepositorioAvisosSQL(sesion, grupo_id)
