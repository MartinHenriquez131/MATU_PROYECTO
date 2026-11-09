"""Adaptador SQL de RepositorioBorrado (MATU-72, decisiones 149 a 157).

Con la sesión del contexto de grupo: RLS acota persona_cuidada, consentimiento y direccion al grupo, y desde la
migración 0018 solo admin y cuidador modifican la persona (persona_familia_editar con app_retira_autorizacion()).
El filtro por grupo es además explícito. Nunca lee el nombre, la dirección ni nada de la persona: solo
identificadores y fechas. Nada se registra en los logs.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Row, text
from sqlalchemy.orm import Session

from app.modules.care_circle.domain.borrado import NOMBRE_BORRADO, PersonaParaBorrar
from app.modules.care_circle.domain.retiro import FINALIDADES_RETIRABLES, AutorizacionRegistrada
from app.modules.care_circle.infrastructure.repositorio_retiros import registrada_de
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria

# C1, paso 1: la fila de la persona, también si está eliminada (para responder 409 ya-borrada y no 404)
_BLOQUEAR_PERSONA = text(
    "SELECT id, eliminado_en, datos_borrados_en, direccion_entrega_id FROM persona_cuidada"
    " WHERE id = :persona_id AND grupo_id = :grupo_id FOR UPDATE"
)

# C1, paso 2: plan_cuidado, consumo y las demás finalidades al final (domain/borrado.py, orden_de_bloqueo)
_ORDEN = " ".join(f"WHEN '{f}' THEN {i}" for i, f in enumerate(FINALIDADES_RETIRABLES))
_BLOQUEAR_VIGENTES = text(
    "SELECT id, finalidad, calidad_otorgante, otorgado_en, revision_vence_en, revocado_en, revocacion_motivo"
    " FROM consentimiento WHERE grupo_id = :grupo_id AND persona_cuidada_id = :persona_id AND revocado_en IS NULL"
    f" ORDER BY CASE finalidad {_ORDEN} ELSE {len(FINALIDADES_RETIRABLES)} END, id FOR UPDATE"
)

# D5: la fila queda con su id, sin datos y con la marca. El trigger persona_borrada_fija (0018) no deja volver
_ANONIMIZAR = text(
    "UPDATE persona_cuidada SET eliminado_en = :ahora, datos_borrados_en = :ahora, nombre = :fijo,"
    " nombre_pila = :fijo, nivel_apoyo = NULL, direccion_entrega_id = NULL, activa = false"
    " WHERE id = :persona_id AND grupo_id = :grupo_id AND datos_borrados_en IS NULL"
)

# La dirección se borra si ninguna otra persona la usa. pedido no la referencia (capa 3 desacoplable, C12)
_BORRAR_DIRECCION = text(
    "DELETE FROM direccion d WHERE d.id = :direccion_id AND d.grupo_id = :grupo_id"
    " AND NOT EXISTS (SELECT 1 FROM persona_cuidada p WHERE p.direccion_entrega_id = d.id)"
)


class BorradoNoEscrito(RuntimeError):
    """La base no aplicó el borrado de la persona (RLS o la fila ya borrada). Mensaje fijo, sin datos."""


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


def _persona(fila: Row[Any]) -> PersonaParaBorrar:
    return PersonaParaBorrar(
        id=fila.id,
        eliminado_en=_utc(fila.eliminado_en),
        datos_borrados_en=_utc(fila.datos_borrados_en),
        direccion_id=fila.direccion_entrega_id,
    )


class RepositorioBorradoSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, auditoria: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._auditoria = auditoria

    def bloquear_persona(self, persona_id: uuid.UUID) -> PersonaParaBorrar | None:
        fila = self._sesion.execute(_BLOQUEAR_PERSONA, {"persona_id": persona_id, "grupo_id": self._grupo_id}).first()
        return None if fila is None else _persona(fila)

    def bloquear_vigentes(self, persona_id: uuid.UUID) -> list[AutorizacionRegistrada]:
        filas = self._sesion.execute(_BLOQUEAR_VIGENTES, {"persona_id": persona_id, "grupo_id": self._grupo_id}).all()
        return [registrada_de(f) for f in filas]

    def anonimizar(
        self, persona: PersonaParaBorrar, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None
    ) -> None:
        parametros = {"persona_id": persona.id, "grupo_id": self._grupo_id, "ahora": ahora, "fijo": NOMBRE_BORRADO}
        resultado = cast(CursorResult[Any], self._sesion.execute(_ANONIMIZAR, parametros))
        if resultado.rowcount != 1:
            raise BorradoNoEscrito("la persona no se borró")
        if persona.direccion_id is not None:
            self._sesion.execute(_BORRAR_DIRECCION, {"direccion_id": persona.direccion_id, "grupo_id": self._grupo_id})
        # Solo identificadores: sin nombre, sin IP, sin contadores y sin detalle (C4)
        self._auditoria.registrar(
            EntradaAuditoria(
                grupo_id=self._grupo_id,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.PERSONA_BORRAR,
                entidad=EntidadAuditoria.PERSONA_CUIDADA,
                entidad_id=persona.id,
                request_id=request_id,
            )
        )
