"""La persona cuidada del grupo y su consentimiento para plan_cuidado (MATU-12, RF-02).

La usa la ficha de relevo (care_plan) antes de leer o escribir nada del plan: si la persona no es del
grupo, 404; si no hay autorización vigente, 403. Corre con la sesión del contexto de grupo
(sesion_de_grupo): RLS acota persona_cuidada y consentimiento al grupo. Solo lee columnas que no son
sensibles: ni el nombre, ni la referencia al documento, ni la evidencia.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_circle.domain.personas import FINALIDAD_PLAN_CUIDADO, AutorizacionGuardada

# El filtro por grupo es explícito además de RLS. Un solo consentimiento no revocado por persona y
# finalidad (índice consentimiento_vigente_uq)
_PERSONA_Y_CONSENTIMIENTO = text(
    "SELECT p.id, c.calidad_otorgante, c.revision_vence_en"
    " FROM persona_cuidada p"
    " LEFT JOIN consentimiento c ON c.persona_cuidada_id = p.id AND c.grupo_id = p.grupo_id"
    " AND c.finalidad = :finalidad AND c.revocado_en IS NULL"
    " WHERE p.id = :persona_id AND p.grupo_id = :grupo_id AND p.eliminado_en IS NULL"
)


@dataclass(frozen=True)
class PersonaDelGrupo:
    id: uuid.UUID
    # None si la persona no tiene un consentimiento no revocado para plan_cuidado
    autorizacion: AutorizacionGuardada | None


def persona_con_autorizacion(sesion: Session, grupo_id: uuid.UUID, persona_id: uuid.UUID) -> PersonaDelGrupo | None:
    """La persona del grupo con su consentimiento para plan_cuidado, o None si no existe en el grupo
    (inexistente, eliminada o de otro grupo: el mismo None)."""
    fila = sesion.execute(
        _PERSONA_Y_CONSENTIMIENTO,
        {"persona_id": persona_id, "grupo_id": grupo_id, "finalidad": FINALIDAD_PLAN_CUIDADO},
    ).first()
    if fila is None:
        return None
    autorizacion = (
        None
        if fila.calidad_otorgante is None
        else AutorizacionGuardada(calidad_otorgante=fila.calidad_otorgante, revision_vence_en=fila.revision_vence_en)
    )
    return PersonaDelGrupo(id=fila.id, autorizacion=autorizacion)
