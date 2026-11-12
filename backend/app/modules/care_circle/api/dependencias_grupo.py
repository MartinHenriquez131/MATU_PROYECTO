"""Dependencias de las rutas de invitaciones y miembros (MATU-42).

- grupo_del_path: el contexto de grupo, si el grupo del path es el de X-Grupo-Id (como …/personas-cuidadas).
- actor_admin: 404 si el rol no es admin, antes de mirar el cuerpo y las cabeceras.
- puertos_del_grupo: los repositorios sobre la sesión del grupo y el registro de auditoría con el Reloj.
- obtener_pepper_codigo: PEPPER_PIN, la llave del HMAC del código (decisión 297). Las pruebas la sobreescriben.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo
from app.modules.care_circle.api.router_personas import ContextoDelGrupo
from app.modules.care_circle.application.invitaciones import Actor
from app.modules.care_circle.application.miembros import Puertos
from app.modules.care_circle.domain.miembros import ROL_ADMIN
from app.modules.care_circle.infrastructure.enlaces_relevo import enlaces_de
from app.modules.care_circle.infrastructure.repositorio_invitaciones import RepositorioInvitacionesSQL
from app.modules.care_circle.infrastructure.repositorio_miembros import RepositorioMiembrosSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import Reloj


def obtener_pepper_codigo() -> bytes | None:
    """PEPPER_PIN, o None si falta: crear, verificar y aceptar responden 503."""
    pepper = obtener_configuracion().pepper_pin
    return None if pepper is None else pepper.get_secret_value().encode("utf-8")


def actor_del_grupo(request: Request, contexto: ContextoDelGrupo) -> Actor:
    return Actor(
        usuario_id=contexto.usuario_id,
        grupo_id=contexto.grupo_id,
        rol=contexto.rol,
        request_id=getattr(request.state, "request_id", None),
    )


def actor_admin(actor: Annotated[Actor, Depends(actor_del_grupo)]) -> Actor:
    """Solo admin. Los demás roles reciben el mismo 404 que un grupo ajeno (decisión 292)."""
    if actor.rol != ROL_ADMIN:
        raise ErrorMATU(404)
    return actor


def puertos_del_grupo(
    contexto: ContextoDelGrupo, reloj: Annotated[Reloj, Depends(obtener_reloj)]
) -> Puertos:
    return _puertos(contexto, reloj)


def _puertos(contexto: ContextoGrupo, reloj: Reloj) -> Puertos:
    registro = RegistroAuditoriaSql(contexto.sesion, reloj)
    return Puertos(
        miembros=RepositorioMiembrosSQL(contexto.sesion, contexto.grupo_id, registro),
        enlaces=enlaces_de(contexto.sesion, contexto.grupo_id, registro),
        invitaciones=RepositorioInvitacionesSQL(contexto.sesion, contexto.grupo_id, registro),
        reloj=reloj,
    )


ActorDelGrupo = Annotated[Actor, Depends(actor_del_grupo)]
ActorAdmin = Annotated[Actor, Depends(actor_admin)]
PuertosDelGrupo = Annotated[Puertos, Depends(puertos_del_grupo)]
PepperCodigo = Annotated[bytes | None, Depends(obtener_pepper_codigo)]
