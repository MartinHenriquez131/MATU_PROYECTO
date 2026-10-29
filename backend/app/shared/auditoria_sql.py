"""Adaptador SQL del puerto RegistroAuditoria (MATU-14, RF-08).

Escribe en ``auditoria`` con la sesión de la transacción en curso, la que abrió sesion_tenant para
la petición (arquitectura, sección 7.7). No abre su propia sesión, no fija contexto y no hace commit:
la fila de auditoría se confirma o se deshace junto con la acción que registra.

RLS decide si la fila entra: auditoria_insertar la acepta solo en el grupo de app.grupo_id, y
auditoria_relevo solo en el grupo del acceso de relevo de app.acceso_relevo_id. Una entrada de otra
familia falla, la excepción sube y sesion_tenant hace rollback de todo.

Nunca escribe la columna ``ip`` (decisión 27 del contrato de MATU-09), ni usa ``now()`` de la base:
el instante sale del puerto Reloj. No registra nada en los logs: ni los valores de la fila ni el
error de la base, que puede traerlos.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.shared.auditoria import EntradaAuditoria
from app.shared.puertos import Reloj

# Sin RETURNING: matu_app solo ve la auditoría de su grupo, y el id lo genera la base
_INSERTAR = text(
    "INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, motivo, request_id,"
    " ocurrido_en)"
    " VALUES (:grupo_id, :actor_tipo, :actor_ref, :accion, :entidad, :entidad_id, :motivo, :request_id,"
    " :ocurrido_en)"
)


class RegistroAuditoriaSql:
    """Registra en la transacción de la petición.

    El caso de uso arma la EntradaAuditoria con el actor del contexto autenticado, nunca con un dato
    del cuerpo de la petición:

    - Un miembro de la familia: actor_tipo USUARIO y actor_ref = el usuario_id de usuario_actual,
      el mismo que sesion_de_grupo fijó en app.usuario_id.
    - El relevo: actor_tipo RELEVO y actor_ref = el id del acceso de relevo canjeado, el mismo que
      fijó en app.acceso_relevo_id.
    """

    def __init__(self, sesion: Session, reloj: Reloj) -> None:
        self._sesion = sesion
        self._reloj = reloj

    def registrar(self, entrada: EntradaAuditoria) -> None:
        self._sesion.execute(
            _INSERTAR,
            {
                "grupo_id": entrada.grupo_id,
                "actor_tipo": entrada.actor_tipo.value,
                "actor_ref": entrada.actor_ref,
                "accion": entrada.accion.value,
                "entidad": entrada.entidad.value,
                "entidad_id": entrada.entidad_id,
                "motivo": None if entrada.motivo is None else entrada.motivo.value,
                "request_id": entrada.request_id,
                "ocurrido_en": self._reloj.ahora(),
            },
        )
