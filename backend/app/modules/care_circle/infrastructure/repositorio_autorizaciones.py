"""Adaptador SQL de RepositorioAutorizaciones (MATU-36, decisión 37).

Con la sesión del contexto de grupo: RLS (consentimiento_familia_*) acota todo al grupo. El INSERT
no usa RETURNING. Un choque con consentimiento_vigente_uq (dos peticiones a la vez) se traduce a
AutorizacionVigente dentro de un SAVEPOINT; el mensaje de la base no se registra.

MATU-72 (C8): antes de guardar toma la fila de la persona con FOR SHARE y exige eliminado_en nulo, para que una
autorización nunca se cuele en un borrado simultáneo, que la bloquea con FOR UPDATE.
"""

import json
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.care_circle.application.autorizaciones import AutorizacionVigente, NuevaAutorizacion
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria

_BLOQUEAR_PERSONA = text(
    "SELECT 1 FROM persona_cuidada WHERE id = :persona_id AND grupo_id = :grupo_id AND eliminado_en IS NULL"
    " FOR SHARE"
)

_HAY_VIGENTE = text(
    "SELECT 1 FROM consentimiento WHERE grupo_id = :grupo_id AND persona_cuidada_id = :persona_id"
    " AND finalidad = :finalidad AND revocado_en IS NULL"
)

_INSERTAR = text(
    "INSERT INTO consentimiento (id, grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
    " version_politica, evidencia, referencia_documento, otorgado_en, revision_vence_en)"
    " VALUES (:id, :grupo_id, :persona_id, :usuario_id, :calidad_otorgante, :finalidad,"
    " :version_politica, CAST(:evidencia AS jsonb), :referencia_documento, :otorgado_en, :revision_vence_en)"
)


class RepositorioAutorizacionesSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, auditoria: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._auditoria = auditoria

    def bloquear_persona(self, persona_id: uuid.UUID) -> bool:
        fila = self._sesion.execute(_BLOQUEAR_PERSONA, {"persona_id": persona_id, "grupo_id": self._grupo_id}).first()
        return fila is not None

    def hay_vigente(self, persona_id: uuid.UUID, finalidad: str) -> bool:
        fila = self._sesion.execute(
            _HAY_VIGENTE, {"grupo_id": self._grupo_id, "persona_id": persona_id, "finalidad": finalidad}
        ).first()
        return fila is not None

    def guardar(self, autorizacion: NuevaAutorizacion) -> None:
        try:
            with self._sesion.begin_nested():
                self._sesion.execute(
                    _INSERTAR,
                    {
                        "id": autorizacion.id,
                        "grupo_id": autorizacion.grupo_id,
                        "persona_id": autorizacion.persona_id,
                        "usuario_id": autorizacion.usuario_id,
                        "calidad_otorgante": autorizacion.calidad_otorgante,
                        "finalidad": autorizacion.finalidad,
                        "version_politica": autorizacion.version_politica,
                        "evidencia": json.dumps(autorizacion.evidencia, ensure_ascii=False, sort_keys=True),
                        "referencia_documento": autorizacion.referencia_documento,
                        "otorgado_en": autorizacion.otorgado_en,
                        "revision_vence_en": autorizacion.revision_vence_en,
                    },
                )
        except IntegrityError:
            raise AutorizacionVigente() from None
        # Sin la referencia al documento ni la evidencia: solo identificadores
        self._auditoria.registrar(
            EntradaAuditoria(
                grupo_id=autorizacion.grupo_id,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=autorizacion.usuario_id,
                accion=AccionAuditoria.CONSENTIMIENTO_OTORGAR,
                entidad=EntidadAuditoria.CONSENTIMIENTO,
                entidad_id=autorizacion.id,
                request_id=autorizacion.request_id,
            )
        )
