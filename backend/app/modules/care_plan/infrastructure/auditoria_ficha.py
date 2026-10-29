"""Auditoría de la ficha: plan.leer y plan.editar sobre el puerto RegistroAuditoria (MATU-14, RF-08).

Los casos de uso (application/ficha.py) llaman al puerto AuditoriaFicha dentro de la transacción de
la petición, después de leer o escribir y antes de devolver el texto. Este adaptador traduce el
EventoFicha a una EntradaAuditoria y la registra con RegistroAuditoria, en la misma sesión: si
registrar falla, la excepción sube, sesion_tenant hace rollback y no hay respuesta con texto.

- Lectura: plan.leer sobre plan_cuidado (entidad_id = plan_id, o null si aún no hay plan).
- Escritura: plan.editar sobre plan_seccion (entidad_id = la sección escrita).

Actor: USUARIO con el usuario_id de la sesión de grupo. Solo identificadores: ni texto, ni ETag, ni
versión, ni IP. El instante lo pone RegistroAuditoriaSql con el puerto Reloj.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_plan.application.ports import EventoFicha
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria

_ID_SECCION = text("SELECT id FROM plan_seccion WHERE plan_id = :plan_id AND tipo = :tipo")


class AuditoriaFichaRegistro:
    def __init__(self, sesion: Session, registro: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._registro = registro

    def _entrada(
        self, evento: EventoFicha, accion: AccionAuditoria, entidad: EntidadAuditoria, entidad_id: uuid.UUID | None
    ) -> EntradaAuditoria:
        return EntradaAuditoria(
            grupo_id=evento.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=evento.usuario_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            request_id=evento.request_id,
        )

    def registrar_lectura(self, evento: EventoFicha) -> None:
        self._registro.registrar(
            self._entrada(evento, AccionAuditoria.PLAN_LEER, EntidadAuditoria.PLAN_CUIDADO, evento.plan_id)
        )

    def registrar_edicion(self, evento: EventoFicha) -> None:
        seccion_id = self._sesion.execute(
            _ID_SECCION, {"plan_id": evento.plan_id, "tipo": evento.campo}
        ).scalar_one()
        self._registro.registrar(
            self._entrada(evento, AccionAuditoria.PLAN_EDITAR, EntidadAuditoria.PLAN_SECCION, seccion_id)
        )
