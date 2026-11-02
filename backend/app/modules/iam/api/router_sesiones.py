"""Rutas de MATU-38 (RF-37): renovar y cerrar la sesión, y los dispositivos.

- Renovar y cerrar no usan el access token: usan la cookie __Secure-matu-refresh y la cabecera fija
  X-MATU-Cliente: web (anti-CSRF). Sin ella, 422 antes de mirar la cookie (decisión 45).
- Todo fallo de la renovación es el mismo 401 sesion-expirada, y borra la cookie.
- Los dispositivos usan el access token (usuario_actual); un dispositivo ajeno es 404, nunca 403.
- Cache-Control: no-store lo pone en toda respuesta el middleware de /v1/sesiones y /v1/dispositivos
  (app/main.py); aquí se repite en las respuestas correctas.
"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.core.errores import ErrorMATU
from app.modules.iam.api.dependencias import UsuarioActual, obtener_emisor_tokens, obtener_reloj, usuario_actual
from app.modules.iam.api.esquemas import DispositivoVista, ListaDispositivos, SesionRespuesta, SolicitudPush
from app.modules.iam.api.sesion_web import (
    BORRAR_COOKIE,
    PROBLEMA,
    UnidadDep,
    borrar_cookie,
    cookie_refresh,
    fijar_cookie,
    request_id,
)
from app.modules.iam.application.ports import EmisorTokens
from app.modules.iam.application.sesiones import (
    DispositivoNoEncontrado,
    SesionRechazada,
    cerrar,
    guardar_push,
    listar_dispositivos,
    renovar,
    sacar_dispositivo,
)
from app.shared.puertos import Reloj

router = APIRouter()

ClienteWeb = Annotated[
    Literal["web"],
    Header(
        alias="X-MATU-Cliente",
        description="Cabecera fija anti-CSRF de las rutas que usan la cookie del refresh. Si falta o trae otro"
        " valor, 422 (decisión 45)",
    ),
]
Usuario = Annotated[UsuarioActual, Depends(usuario_actual)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]

_NO_STORE = {"Cache-Control": {"description": "no-store", "schema": {"type": "string"}}}
_SET_COOKIE = {"Set-Cookie": {"description": "Cookie del refresh", "schema": {"type": "string"}}}
_Respuestas = dict[int | str, dict[str, Any]]
_FALTA_CLIENTE: _Respuestas = {422: {"description": "Falta X-MATU-Cliente: web o trae otro valor", **PROBLEMA}}
_NO_AUTENTICADO: _Respuestas = {401: {"description": "no-autenticado o token-invalido", **PROBLEMA}}
_NO_ENCONTRADO: _Respuestas = {
    404: {"description": "El dispositivo no existe, es de otro usuario o el token no trae did", **PROBLEMA}
}


def _sesion_expirada() -> ErrorMATU:
    return ErrorMATU(
        401,
        tipo="sesion-expirada",
        detalle="Vuelve a entrar con tu email y tu contraseña",
        headers={"Set-Cookie": BORRAR_COOKIE, "Cache-Control": "no-store"},
    )


def _no_encontrado() -> ErrorMATU:
    return ErrorMATU(404, headers={"Cache-Control": "no-store"})


@router.post(
    "/sesiones/renovar",
    response_model=SesionRespuesta,
    tags=["sesiones"],
    description=(
        "Rota el refresh de la cookie `__Secure-matu-refresh` (ventana deslizante de 30 días, decisión 57) y"
        " entrega un access token nuevo de 15 minutos. Un refresh ya usado revoca toda su familia"
        " (`reutilizacion`). Todo fallo es el mismo 401 `sesion-expirada`, que borra la cookie."
    ),
    responses={200: {"headers": {**_NO_STORE, **_SET_COOKIE}}, 401: {"description": "sesion-expirada",
               "headers": _SET_COOKIE, **PROBLEMA}, **_FALTA_CLIENTE},
)
def renovar_sesion(
    request: Request,
    respuesta: Response,
    _cliente: ClienteWeb,
    unidad: UnidadDep,
    emisor: Annotated[EmisorTokens, Depends(obtener_emisor_tokens)],
    reloj: RelojDep,
) -> SesionRespuesta:
    try:
        sesion = renovar(
            refresh_presentado=cookie_refresh(request),
            unidad=unidad,
            emisor=emisor,
            reloj=reloj,
            request_id=request_id(request),
        )
    except SesionRechazada:
        raise _sesion_expirada() from None
    request.state.usuario_id = str(sesion.usuario_id)
    respuesta.headers["Cache-Control"] = "no-store"
    fijar_cookie(respuesta, sesion.refresh)
    return SesionRespuesta(access_token=sesion.access_token, expira_en=sesion.duracion_segundos)


@router.post(
    "/sesiones/cerrar",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["sesiones"],
    description=(
        "Revoca la familia de la cookie (`logout`), el dispositivo y su endpoint de push (decisión 47)."
        " Idempotente: sin cookie o con una que no sirve, también 204. Siempre borra la cookie. Un access"
        " token ya emitido sigue valiendo hasta sus 15 minutos."
    ),
    responses={204: {"headers": {**_NO_STORE, **_SET_COOKIE}}, **_FALTA_CLIENTE},
)
def cerrar_sesion(request: Request, _cliente: ClienteWeb, unidad: UnidadDep, reloj: RelojDep) -> Response:
    cerrar(refresh_presentado=cookie_refresh(request), unidad=unidad, reloj=reloj, request_id=request_id(request))
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    respuesta.headers["Cache-Control"] = "no-store"
    borrar_cookie(respuesta)
    return respuesta


@router.get(
    "/dispositivos",
    response_model=ListaDispositivos,
    tags=["dispositivos"],
    description=(
        "Los dispositivos propios no revocados: primero el actual (claim `did`) y después por último uso."
        " Nunca devuelve `push_token`."
    ),
    responses={200: {"headers": _NO_STORE}, **_NO_AUTENTICADO},
)
def ver_dispositivos(request: Request, respuesta: Response, usuario: Usuario, unidad: UnidadDep) -> ListaDispositivos:
    dispositivos = listar_dispositivos(usuario_id=usuario.id, unidad=unidad)
    # sorted es estable: el actual va primero y el resto conserva el orden por último uso
    ordenados = sorted(dispositivos, key=lambda d: d.id != usuario.dispositivo_id)
    respuesta.headers["Cache-Control"] = "no-store"
    return ListaDispositivos(
        items=[
            DispositivoVista(
                id=d.id,
                plataforma=d.plataforma,  # type: ignore[arg-type]
                nombre=d.nombre,
                creado_en=d.creado_en,
                ultimo_uso_en=d.ultimo_uso_en,
                actual=d.id == usuario.dispositivo_id,
            )
            for d in ordenados
        ]
    )


@router.delete(
    "/dispositivos/{dispositivo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["dispositivos"],
    description=(
        "Revoca las sesiones del dispositivo (`dispositivo`), el dispositivo y su endpoint de push, en una"
        " transacción. Ajeno, inexistente o con un id que no es UUID: 404. Ya revocado: 204. Si es el actual,"
        " borra además la cookie del refresh."
    ),
    responses={204: {"headers": _NO_STORE}, **_NO_AUTENTICADO, **_NO_ENCONTRADO},
)
def sacar(request: Request, dispositivo_id: str, usuario: Usuario, unidad: UnidadDep, reloj: RelojDep) -> Response:
    try:
        objetivo = uuid.UUID(dispositivo_id)
    except ValueError:
        raise _no_encontrado() from None
    try:
        sacar_dispositivo(
            usuario_id=usuario.id, dispositivo_id=objetivo, unidad=unidad, reloj=reloj, request_id=request_id(request)
        )
    except DispositivoNoEncontrado:
        raise _no_encontrado() from None
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    respuesta.headers["Cache-Control"] = "no-store"
    if objetivo == usuario.dispositivo_id:
        borrar_cookie(respuesta)
    return respuesta


def exigir_dispositivo_actual(usuario: Usuario, unidad: UnidadDep) -> None:
    """El 404 del dispositivo actual antes del 422 del cuerpo (orden del contrato: 401, 404, 422).

    FastAPI resuelve las dependencias antes de informar los errores del cuerpo."""
    if usuario.dispositivo_id is None or all(
        d.id != usuario.dispositivo_id for d in listar_dispositivos(usuario_id=usuario.id, unidad=unidad)
    ):
        raise _no_encontrado()


@router.put(
    "/dispositivos/actual/push",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["dispositivos"],
    description=(
        "Guarda el endpoint de Web Push del dispositivo del claim `did`. Solo se escribe: nunca aparece en una"
        " respuesta, un error, un log ni la auditoría. El envío es de MATU-41. Orden: 401, 404, 422 y 204."
    ),
    responses={
        204: {"headers": _NO_STORE},
        **_NO_AUTENTICADO,
        **_NO_ENCONTRADO,
        422: {"description": "push_token inválido o de un servicio no admitido (push_no_admitido)", **PROBLEMA},
    },
)
def guardar_push_actual(
    request: Request,
    usuario: Usuario,
    unidad: UnidadDep,
    _actual: Annotated[None, Depends(exigir_dispositivo_actual)],
    solicitud: SolicitudPush,
) -> Response:
    return _push(request, usuario, unidad, solicitud.push_token)


@router.delete(
    "/dispositivos/actual/push",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["dispositivos"],
    description="Pone `push_token = NULL` en el dispositivo del claim `did`. Idempotente.",
    responses={204: {"headers": _NO_STORE}, **_NO_AUTENTICADO, **_NO_ENCONTRADO},
)
def borrar_push_actual(request: Request, usuario: Usuario, unidad: UnidadDep) -> Response:
    return _push(request, usuario, unidad, None)


def _push(request: Request, usuario: UsuarioActual, unidad: UnidadDep, push_token: str | None) -> Response:
    request.state.usuario_id = str(usuario.id)
    try:
        guardar_push(
            usuario_id=usuario.id,
            dispositivo_id=usuario.dispositivo_id,
            push_token=push_token,
            unidad=unidad,
            request_id=request_id(request),
        )
    except DispositivoNoEncontrado:
        raise _no_encontrado() from None
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta
