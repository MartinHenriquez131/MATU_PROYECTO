"""Adaptador SQL del puerto RepositorioAperturas (MATU-45, RF-08).

Con la sesión del contexto de grupo (sesion_de_grupo). RLS: auditoria_aperturas_relevo (0010) muestra
las filas de los relevos del grupo a quien puede ver el plan, y acceso_familia los accesos del grupo. El
filtro por grupo es explícito además de RLS.

Lee solo el id, el instante y la acción de auditoria, y el id y el nombre del acceso. Nunca la IP, el
request_id, el teléfono, el token ni el PIN. Desde MATU-50 lee también detalle -> 'secciones' (los tipos
de las secciones mostradas en relevo.abrir), que nunca lleva texto (CHECK auditoria_detalle_acotado).
"""

import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import Session

from app.modules.care_plan.application.ports import FilaApertura, PosicionApertura

_LISTAR = text(
    "SELECT a.id, a.ocurrido_en, a.accion, r.id AS acceso_id, r.otorgado_a_nombre AS nombre_relevo,"
    " a.detalle -> 'secciones' AS secciones"
    " FROM auditoria a JOIN acceso_relevo r ON r.id = a.actor_ref"
    " WHERE r.plan_id = :plan_id AND r.grupo_id = :grupo_id AND a.grupo_id = :grupo_id"
    " AND a.actor_tipo = 'relevo' AND a.accion = ANY(:acciones)"
    " AND (CAST(:despues_en AS timestamptz) IS NULL"
    "      OR (a.ocurrido_en, a.id) < (CAST(:despues_en AS timestamptz), CAST(:despues_id AS bigint)))"
    " ORDER BY a.ocurrido_en DESC, a.id DESC LIMIT :limite"
).bindparams(bindparam("acciones", type_=ARRAY(TEXT)))


def _tipos(valor: Any) -> tuple[str, ...]:
    # psycopg entrega el jsonb ya decodificado: una lista de textos, o None si la fila no lo trae
    if not isinstance(valor, list):
        return ()
    return tuple(t for t in valor if isinstance(t, str))


class RepositorioAperturasSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def listar(
        self, plan_id: uuid.UUID, acciones: tuple[str, ...], despues_de: PosicionApertura | None, limite: int
    ) -> list[FilaApertura]:
        filas = self._sesion.execute(
            _LISTAR,
            {
                "plan_id": plan_id,
                "grupo_id": self._grupo_id,
                "acciones": list(acciones),
                "despues_en": None if despues_de is None else despues_de.ocurrido_en,
                "despues_id": None if despues_de is None else despues_de.id,
                "limite": limite,
            },
        ).all()
        return [
            FilaApertura(
                id=int(f.id),
                ocurrido_en=f.ocurrido_en.astimezone(UTC),
                accion=f.accion,
                acceso_id=f.acceso_id,
                nombre_relevo=f.nombre_relevo,
                secciones=_tipos(f.secciones),
            )
            for f in filas
        ]
