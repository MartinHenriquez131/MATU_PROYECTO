"""El efecto del retiro de ``plan_cuidado`` (MATU-44, decisiones 124, 127 y 128).

Lo registra app.main en care_circle (infrastructure/efectos_retiro.py). Corre en la transacción de la
petición de retiro o de autorización, con su sesión y su registro de auditoría:

- aplicar: corta los accesos de relevo de la persona (cortar_por_retiro), cada uno con relevo.revocar.
- borrar_vencido: al volver a autorizar 90 días o más después del retiro, destruye la clave de la ficha
  aunque la tarea no haya corrido, y registra clave.destruir con actor sistema y sin detalle.
- destruido_en: cuándo se destruyó la clave, para la vista de las autorizaciones.

No lee ni escribe texto de la ficha. Nada se registra en los logs.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.care_plan.application.relevo import cortar_por_retiro
from app.modules.care_plan.infrastructure.repositorio_accesos import RepositorioAccesosSQL
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria


class EfectoRetiroFicha:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._grupo_id = grupo_id
        self._registro = registro
        self._accesos = RepositorioAccesosSQL(sesion, grupo_id, registro)
        self._claves = RepositorioClavesSQL(sesion)

    def aplicar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        return cortar_por_retiro(persona_id, ahora, usuario_id, request_id, self._accesos)

    def borrar_vencido(self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None) -> None:
        clave_id = self._claves.destruir(persona_id, ahora)
        if clave_id is None:
            return
        self._registro.registrar(
            EntradaAuditoria(
                grupo_id=self._grupo_id,
                actor_tipo=ActorTipo.SISTEMA,
                actor_ref=None,
                accion=AccionAuditoria.CLAVE_DESTRUIR,
                entidad=EntidadAuditoria.CLAVE_DATOS,
                entidad_id=clave_id,
                request_id=request_id,
            )
        )

    def destruido_en(self, persona_id: uuid.UUID) -> datetime | None:
        return self._claves.destruida_en(persona_id)
