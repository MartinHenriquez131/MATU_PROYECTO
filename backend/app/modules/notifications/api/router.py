"""Rutas de la preferencia propia de avisos (MATU-41, decisión 111): GET y PUT /v1/yo/avisos.

- Solo del usuario autenticado: no reciben un usuario_id. Corren en sesion_de_usuario (solo
  app.usuario_id), y RLS (preferencia_propia) no deja leer ni escribir la preferencia de otra persona.
- Sin pantalla en esta historia: la pantalla es de MATU-55.
- Cache-Control: no-store lo pone el middleware de /v1/yo (app/main.py); aquí se repite.
- MATU-55 (decisión 259): el PUT audita avisos.preferencia, sin los valores, solo si la preferencia cambió.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.modules.iam.api.dependencias import SesionDeUsuario, UsuarioActual, obtener_reloj, usuario_actual
from app.modules.iam.api.sesion_web import PROBLEMA, request_id
from app.modules.notifications.api.esquemas import PreferenciaAvisosVista
from app.modules.notifications.application.preferencias import (
    PreferenciaAvisos,
    guardar_preferencia,
    leer_preferencia,
)
from app.modules.notifications.infrastructure.repositorio_preferencias import RepositorioPreferenciasSQL
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import Reloj

router = APIRouter()

Usuario = Annotated[UsuarioActual, Depends(usuario_actual)]

_NO_STORE = {"Cache-Control": {"description": "no-store", "schema": {"type": "string"}}}
_Respuestas = dict[int | str, dict[str, Any]]
_401: _Respuestas = {401: {"description": "no-autenticado o token-invalido", **PROBLEMA}}


def _vista(preferencia: PreferenciaAvisos, respuesta: Response) -> PreferenciaAvisosVista:
    respuesta.headers["Cache-Control"] = "no-store"
    return PreferenciaAvisosVista(correo=preferencia.correo, push=preferencia.push)


@router.get(
    "/yo/avisos",
    response_model=PreferenciaAvisosVista,
    tags=["avisos"],
    operation_id="leerPreferenciaAvisos",
    description=(
        "Si la persona recibe por correo y por push los avisos de un insumo que se está acabando (MATU-41)."
        " Es suya, no del grupo, y vale para todos sus grupos. Sin preferencia guardada, lo que corresponde a"
        " sus roles: activo si es admin o cuidador en algún grupo, e inactivo si solo es pagador u"
        " observador (decisión 78). Orden: 401 y 200."
    ),
    responses={200: {"headers": _NO_STORE}, **_401},
)
def leer_avisos(respuesta: Response, usuario: Usuario, sesion: SesionDeUsuario) -> PreferenciaAvisosVista:
    return _vista(leer_preferencia(RepositorioPreferenciasSQL(sesion), usuario.id), respuesta)


@router.put(
    "/yo/avisos",
    response_model=PreferenciaAvisosVista,
    tags=["avisos"],
    operation_id="guardarPreferenciaAvisos",
    description=(
        "Elige los canales de los avisos de un insumo que se está acabando (MATU-41). La elección es de la persona"
        " y vale para todos sus grupos. Trae los dos canales, pero solo guarda el que difiere de lo que muestra el"
        " GET, o el que ya estaba guardado: un canal sin elegir sigue, en cada grupo, el valor por omisión del rol"
        " (decisión 111). El pagador y el observador lo usan para activarlos; el admin y el cuidador, para"
        " apagarlos. Apagar el correo no cambia el push, y al revés: nunca se busca otro canal. Devuelve lo mismo"
        " que el GET. Registra `avisos.preferencia` en la auditoría de la cuenta, sin los valores, solo si lo que"
        " devuelve el GET cambió (MATU-55, decisión 259). Orden: 401, 422 y 200."
    ),
    responses={200: {"headers": _NO_STORE}, **_401, 422: {"description": "Cuerpo inválido", **PROBLEMA}},
)
def guardar_avisos(
    request: Request,
    solicitud: PreferenciaAvisosVista,
    respuesta: Response,
    usuario: Usuario,
    sesion: SesionDeUsuario,
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> PreferenciaAvisosVista:
    preferencia = PreferenciaAvisos(correo=solicitud.correo, push=solicitud.push)
    guardada = guardar_preferencia(
        RepositorioPreferenciasSQL(sesion),
        usuario.id,
        preferencia,
        RegistroAuditoriaSql(sesion, reloj),
        request_id(request),
    )
    return _vista(guardada, respuesta)
