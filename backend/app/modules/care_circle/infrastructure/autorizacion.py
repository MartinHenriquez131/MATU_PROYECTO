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

# MATU-44, condición 7 del analista: compartir lee la autorización con FOR SHARE. Si un retiro la tiene
# bloqueada (FOR UPDATE), espera a que termine y, al reevaluar, ya no la encuentra: responde 403. FOR SHARE
# no se puede aplicar al lado opcional de un LEFT JOIN, por eso es una consulta aparte
_AUTORIZACION_BLOQUEADA = text(
    "SELECT calidad_otorgante, revision_vence_en FROM consentimiento"
    " WHERE persona_cuidada_id = :persona_id AND grupo_id = :grupo_id AND finalidad = :finalidad"
    " AND revocado_en IS NULL FOR SHARE"
)


@dataclass(frozen=True)
class PersonaDelGrupo:
    id: uuid.UUID
    # None si la persona no tiene un consentimiento no revocado para plan_cuidado
    autorizacion: AutorizacionGuardada | None


def persona_con_autorizacion(
    sesion: Session,
    grupo_id: uuid.UUID,
    persona_id: uuid.UUID,
    finalidad: str = FINALIDAD_PLAN_CUIDADO,
    *,
    bloquear: bool = False,
) -> PersonaDelGrupo | None:
    """La persona del grupo con su consentimiento no revocado para ``finalidad`` (plan_cuidado por
    omisión; consumo en MATU-36), o None si no existe en el grupo (inexistente, eliminada o de otro
    grupo: el mismo None).

    ``bloquear`` (MATU-44): lee el consentimiento con FOR SHARE hasta el fin de la transacción, para que un
    retiro simultáneo espere o haga esperar (compartir la ficha)."""
    parametros = {"persona_id": persona_id, "grupo_id": grupo_id, "finalidad": finalidad}
    fila = sesion.execute(_PERSONA_Y_CONSENTIMIENTO, parametros).first()
    if fila is None:
        return None
    if bloquear:
        bloqueada = sesion.execute(_AUTORIZACION_BLOQUEADA, parametros).first()
        autorizada = None if bloqueada is None else AutorizacionGuardada(
            calidad_otorgante=bloqueada.calidad_otorgante, revision_vence_en=bloqueada.revision_vence_en
        )
        return PersonaDelGrupo(id=fila.id, autorizacion=autorizada)
    autorizacion = (
        None
        if fila.calidad_otorgante is None
        else AutorizacionGuardada(calidad_otorgante=fila.calidad_otorgante, revision_vence_en=fila.revision_vence_en)
    )
    return PersonaDelGrupo(id=fila.id, autorizacion=autorizacion)
