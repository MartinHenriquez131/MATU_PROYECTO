"""Adaptador SQL de RepositorioRetiros (MATU-44, decisiones 123 a 127).

Con la sesión del contexto de grupo: RLS acota consentimiento al grupo, y desde la migración 0016 solo
admin y cuidador lo actualizan (consentimiento_familia_revocar con app_retira_autorizacion()). El filtro
por grupo es además explícito. Solo lee columnas que no son sensibles: ni la referencia al documento, ni
la evidencia, ni quién la dio. Nada se registra en los logs.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.modules.care_circle.domain.retiro import MOTIVO_RETIRO, AutorizacionRegistrada
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria

_COLUMNAS = "SELECT id, finalidad, calidad_otorgante, otorgado_en, revision_vence_en, revocado_en FROM consentimiento"
_DE_LA_PERSONA = " WHERE grupo_id = :grupo_id AND persona_cuidada_id = :persona_id AND finalidad = :finalidad"

# Condición 7 del analista: el retiro bloquea la fila; compartir la lee con FOR SHARE y espera
_BLOQUEAR_VIGENTE = text(_COLUMNAS + _DE_LA_PERSONA + " AND revocado_en IS NULL FOR UPDATE")

# La no revocada primero (NULLS FIRST) y, si no hay, la de revocación más reciente
_ULTIMA = text(_COLUMNAS + _DE_LA_PERSONA + " ORDER BY revocado_en DESC NULLS FIRST, otorgado_en DESC LIMIT 1")

_RETIRO_ANTERIOR = text(
    _COLUMNAS + _DE_LA_PERSONA + " AND revocacion_motivo = 'retiro' AND revocado_en <= :antes_de"
    " ORDER BY revocado_en DESC LIMIT 1"
)

_RETIRAR = text(
    "UPDATE consentimiento SET revocado_en = :ahora, revocacion_motivo = :motivo"
    " WHERE id = :id AND grupo_id = :grupo_id AND revocado_en IS NULL"
)


class RetiroNoEscrito(RuntimeError):
    """La base no aplicó la revocación (RLS o la fila ya revocada). Mensaje fijo, sin datos."""


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


def _registrada(fila: Row[Any]) -> AutorizacionRegistrada:
    return AutorizacionRegistrada(
        id=fila.id,
        finalidad=fila.finalidad,
        calidad_otorgante=fila.calidad_otorgante,
        otorgado_en=fila.otorgado_en.astimezone(UTC),
        revision_vence_en=_utc(fila.revision_vence_en),
        revocado_en=_utc(fila.revocado_en),
    )


class RepositorioRetirosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, auditoria: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._auditoria = auditoria

    def _parametros(self, persona_id: uuid.UUID, finalidad: str) -> dict[str, Any]:
        return {"grupo_id": self._grupo_id, "persona_id": persona_id, "finalidad": finalidad}

    def bloquear_vigente(self, persona_id: uuid.UUID, finalidad: str) -> AutorizacionRegistrada | None:
        fila = self._sesion.execute(_BLOQUEAR_VIGENTE, self._parametros(persona_id, finalidad)).first()
        return None if fila is None else _registrada(fila)

    def ultima(self, persona_id: uuid.UUID, finalidad: str) -> AutorizacionRegistrada | None:
        fila = self._sesion.execute(_ULTIMA, self._parametros(persona_id, finalidad)).first()
        return None if fila is None else _registrada(fila)

    def retiro_anterior(
        self, persona_id: uuid.UUID, finalidad: str, antes_de: datetime
    ) -> AutorizacionRegistrada | None:
        fila = self._sesion.execute(
            _RETIRO_ANTERIOR, {**self._parametros(persona_id, finalidad), "antes_de": antes_de}
        ).first()
        return None if fila is None else _registrada(fila)

    def retirar(
        self, consentimiento_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None
    ) -> None:
        resultado = self._sesion.execute(
            _RETIRAR, {"id": consentimiento_id, "grupo_id": self._grupo_id, "ahora": ahora, "motivo": MOTIVO_RETIRO}
        )
        if getattr(resultado, "rowcount", 0) != 1:
            raise RetiroNoEscrito("la autorización no se retiró")
        # Solo identificadores: sin nombre, sin IP y sin detalle (condición 4 del analista)
        self._auditoria.registrar(
            EntradaAuditoria(
                grupo_id=self._grupo_id,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.CONSENTIMIENTO_REVOCAR,
                entidad=EntidadAuditoria.CONSENTIMIENTO,
                entidad_id=consentimiento_id,
                request_id=request_id,
            )
        )
