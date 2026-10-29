"""Contexto de grupo de cada petición (MATU-02, ADR-013, arquitectura, sección 7.7).

sesion_de_grupo es la puerta de toda ruta que trabaja sobre un grupo familiar:

1. usuario_actual (iam) valida el access token. Sin token válido, 401.
2. Lee el grupo de la cabecera X-Grupo-Id.
3. Abre sesion_tenant con app.usuario_id primero y app.grupo_id después.
4. Verifica, dentro de ese contexto, que el usuario es miembro activo del grupo, y lee su rol en él.

Si falta la cabecera, no es un UUID, el grupo no existe o el usuario no es miembro activo, la
respuesta es el mismo 404, nunca 403: no revela si el grupo existe.

Las rutas la usan con el tipo SesionDeGrupo:

    @router.get("/grupos/actual")
    def ver(contexto: SesionDeGrupo) -> ...:
        contexto.sesion.execute(...)
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.modules.care_circle.infrastructure.membresia import membresia_activa
from app.modules.iam.api.dependencias import UsuarioActual, usuario_actual


@dataclass(frozen=True)
class ContextoGrupo:
    """El usuario, el grupo verificado, su rol en él y la sesión con su contexto ya fijado.

    rol es el de su membresía activa (admin, cuidador, pagador u observador). Cada ruta decide con él
    qué puede hacer y qué ve (arquitectura 11.2), y responde 404 cuando el rol no alcanza.
    puede_ver_plan es el permiso explícito del pagador para ver el plan de cuidado (MATU-12).
    """

    usuario_id: uuid.UUID
    grupo_id: uuid.UUID
    sesion: Session
    rol: str
    puede_ver_plan: bool = False


def _grupo_de_cabecera(valor: str | None) -> uuid.UUID:
    if valor is None:
        raise ErrorMATU(404)
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def sesion_de_grupo(
    request: Request,
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
    x_grupo_id: Annotated[str | None, Header(alias="X-Grupo-Id")] = None,
) -> Iterator[ContextoGrupo]:
    """Entrega el contexto de grupo en una transacción que dura lo que la ruta.

    Commit si la ruta termina bien, rollback si lanza. ErrorMATU(404) si no hay grupo válido o el
    usuario no es miembro activo de él.
    """
    grupo_id = _grupo_de_cabecera(x_grupo_id)
    with sesion_tenant(fabrica, usuario_id=usuario.id, grupo_id=grupo_id) as sesion:
        membresia = membresia_activa(sesion, usuario.id, grupo_id)
        if membresia is None:
            # El mismo 404 por omisión que un grupo inexistente o una ruta que no existe
            raise ErrorMATU(404)
        # El log de la petición registra el grupo ya verificado
        request.state.grupo_id = str(grupo_id)
        yield ContextoGrupo(
            usuario_id=usuario.id,
            grupo_id=grupo_id,
            sesion=sesion,
            rol=membresia.rol,
            puede_ver_plan=membresia.puede_ver_plan,
        )


# scope="function": la transacción se cierra (commit o rollback) antes de enviar la respuesta,
# para que un commit fallido no llegue al cliente como un 200
SesionDeGrupo = Annotated[ContextoGrupo, Depends(sesion_de_grupo, scope="function")]
