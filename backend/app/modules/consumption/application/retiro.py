"""Lo que hace el consumo cuando se retira su autorización (MATU-44, D5, decisiones 124 y 128).

- Al retirar ``consumo``: las alertas abiertas (pendiente y notificada) de la persona pasan a descartada,
  cada una con alerta.descartar y actor el usuario que retiró, en la transacción del retiro.
- Al volver a autorizar 90 días o más después del retiro: se borran los perfiles de la persona aunque la
  tarea de conservación no haya corrido (decisión 70). Sus alertas y reposiciones caen por ON DELETE CASCADE.

El trabajo diario y los avisos ya revisan la autorización antes de actuar (decisiones 75 y 107): no
cambian.
"""

import uuid
from datetime import datetime
from typing import Protocol

from app.modules.consumption.domain.alerta import EstadoAlerta
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria


class ConsumoDeLaPersona(Protocol):
    """Implementación: RepositorioAlertasSQL y RepositorioPerfilesSQL, por EfectoRetiroConsumo."""

    def abiertas_de_la_persona(self, persona_id: uuid.UUID) -> list[uuid.UUID]:
        """Las alertas pendiente y notificada de la persona, bloqueadas, en un orden fijo."""
        ...

    def cerrar(self, alerta_id: uuid.UUID, estado: EstadoAlerta, ahora: datetime) -> object: ...

    def borrar_perfiles_de_la_persona(self, persona_id: uuid.UUID) -> int: ...


def descartar_por_retiro(
    grupo_id: uuid.UUID,
    persona_id: uuid.UUID,
    ahora: datetime,
    usuario_id: uuid.UUID,
    request_id: str | None,
    consumo: ConsumoDeLaPersona,
    auditoria: RegistroAuditoria,
) -> int:
    """Descarta las alertas abiertas de la persona. Devuelve cuántas."""
    descartadas = 0
    for alerta_id in consumo.abiertas_de_la_persona(persona_id):
        consumo.cerrar(alerta_id, EstadoAlerta.DESCARTADA, ahora)
        auditoria.registrar(
            EntradaAuditoria(
                grupo_id=grupo_id,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.ALERTA_DESCARTAR,
                entidad=EntidadAuditoria.ALERTA_QUIEBRE,
                entidad_id=alerta_id,
                request_id=request_id,
                persona_cuidada_id=persona_id,
            )
        )
        descartadas += 1
    return descartadas
