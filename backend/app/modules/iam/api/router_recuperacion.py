"""Rutas de MATU-57 (RF-37): recuperar el acceso con un código y verificar el celular.

- POST /v1/recuperacion/codigo responde siempre 202 sin cuerpo, exista o no la cuenta y aunque se
  alcance el límite (decisión 84): todo el trabajo corre después de responder.
- POST /v1/recuperacion/contrasena: un solo error para todo código que no sirve
  (/errores/codigo-invalido, 422), y 429 con Retry-After. No emite tokens.
- /v1/cuenta y /v1/cuenta/celular/*: autenticadas.
- Ni el email, ni el código, ni el celular en la URL, un log o un error. Cache-Control: no-store lo pone
  el middleware de /v1/recuperacion y /v1/cuenta (app/main.py).
"""

import logging
from functools import lru_cache
from typing import Annotated, Any

import redis
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.core.config import RAIZ_REPOSITORIO, obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.iam.api.dependencias import UsuarioActual, obtener_reloj, usuario_actual
from app.modules.iam.api.esquemas import (
    CuentaVista,
    PoliticaAceptadaVista,
    SolicitudCambioContrasena,
    SolicitudCodigoRecuperacion,
    SolicitudVerificarCelular,
)
from app.modules.iam.api.router import obtener_hasher, obtener_pepper_email, obtener_repositorio_usuarios
from app.modules.iam.api.sesion_web import PROBLEMA, ContadoresDep, PepperLimitesDep, UnidadDep, request_id
from app.modules.iam.application.politica import leer_cuenta_y_aceptacion
from app.modules.iam.application.ports import (
    AlmacenCodigos,
    ContadoresEnvio,
    ContadoresNoDisponibles,
    EnviadorCodigos,
    HasherContrasenas,
    RepositorioUsuarios,
)
from app.modules.iam.application.recuperacion import (
    CelularYaVerificado,
    EnvioEnEspera,
    Peppers,
    SinCelular,
    cambiar_contrasena_con_codigo,
    pedir_codigo_celular,
    solicitar_recuperacion,
    verificar_celular,
)
from app.modules.iam.application.sesiones import DemoraActiva
from app.modules.iam.domain.recuperacion import CodigoInvalido, enmascarar_celular
from app.modules.iam.infrastructure.enviador_simulado import EnviadorSimulado
from app.modules.iam.infrastructure.recuperacion_redis import AlmacenCodigosRedis, ContadoresEnvioRedis
from app.shared.puertos import Reloj

log = logging.getLogger("matu.iam")

router = APIRouter()

_SIN_SERVICIO = "No se puede recuperar el acceso en este momento. Cita el request_id si lo reportas"


# --- Dependencias -----------------------------------------------------------------------------------


def obtener_pepper_recuperacion() -> bytes | None:
    pepper = obtener_configuracion().pepper_recuperacion
    return None if pepper is None else pepper.get_secret_value().encode("utf-8")


@lru_cache
def _redis() -> "redis.Redis":
    return redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=2)


def obtener_almacen_codigos() -> AlmacenCodigos:
    return AlmacenCodigosRedis(_redis())


def obtener_contadores_envio() -> ContadoresEnvio:
    return ContadoresEnvioRedis(_redis())


@lru_cache
def _enviador_simulado() -> EnviadorSimulado:
    archivo = obtener_configuracion().registro_envios
    if archivo is not None and not archivo.is_absolute():
        archivo = RAIZ_REPOSITORIO / archivo
    return EnviadorSimulado(archivo)


def obtener_enviador() -> EnviadorCodigos | None:
    """El envío simulado si ENVIADOR_CODIGOS=simulado; si no, None y las rutas que envían responden 503."""
    if obtener_configuracion().enviador_codigos != "simulado":
        return None
    return _enviador_simulado()


PepperRecuperacionDep = Annotated[bytes | None, Depends(obtener_pepper_recuperacion)]
AlmacenDep = Annotated[AlmacenCodigos, Depends(obtener_almacen_codigos)]
EnviosDep = Annotated[ContadoresEnvio, Depends(obtener_contadores_envio)]
EnviadorDep = Annotated[EnviadorCodigos | None, Depends(obtener_enviador)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
Usuario = Annotated[UsuarioActual, Depends(usuario_actual)]


def _peppers(email: bytes, limites: bytes | None, recuperacion: bytes | None) -> Peppers:
    if limites is None or recuperacion is None:
        log.error("falta PEPPER_LIMITES o PEPPER_RECUPERACION: la recuperacion falla cerrada")
        raise ErrorMATU(503, detalle=_SIN_SERVICIO)
    return Peppers(email=email, limites=limites, recuperacion=recuperacion)


def _con_enviador(enviador: EnviadorCodigos | None) -> EnviadorCodigos:
    if enviador is None:
        log.error("falta ENVIADOR_CODIGOS: la recuperacion falla cerrada")
        raise ErrorMATU(503, detalle=_SIN_SERVICIO)
    return enviador


def _ip(request: Request) -> str:
    # La IP que fijó MiddlewareProxy (app/core/proxy.py). Solo para su huella HMAC: nunca se guarda ni se
    # registra
    return request.client.host if request.client else "desconocida"


def _codigo_invalido() -> ErrorMATU:
    return ErrorMATU(422, tipo="codigo-invalido", detalle="El código no sirve. Revisa los números o pide otro")


def _espera(segundos: int) -> ErrorMATU:
    return ErrorMATU(
        429,
        detalle="Espera un rato antes de volver a intentarlo",
        headers={"Retry-After": str(max(1, segundos))},
    )


def _sin_servicio() -> ErrorMATU:
    log.error("Redis no responde: la recuperacion falla cerrada")
    return ErrorMATU(503, detalle=_SIN_SERVICIO)


_Respuestas = dict[int | str, dict[str, Any]]
_NO_STORE = {"Cache-Control": {"description": "no-store", "schema": {"type": "string"}}}
_RETRY_AFTER = {"Retry-After": {"description": "Segundos de espera", "schema": {"type": "integer"}}}
_429: _Respuestas = {429: {"description": "demasiadas-peticiones", "headers": _RETRY_AFTER, **PROBLEMA}}
_503: _Respuestas = {
    503: {"description": "Falta un pepper o el envío, o Redis no responde: falla cerrada", **PROBLEMA}
}
_401: _Respuestas = {401: {"description": "no-autenticado o token-invalido", **PROBLEMA}}


# --- Recuperar el acceso ----------------------------------------------------------------------------


def _solicitar_en_segundo_plano(**argumentos: Any) -> None:
    try:
        solicitar_recuperacion(**argumentos)
    except Exception:
        # Sin la excepción: puede traer valores de la base o de Redis
        log.error("no se pudo procesar una solicitud de recuperacion", extra={"evento": "recuperacion.fallida"})


@router.post(
    "/recuperacion/codigo",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    tags=["recuperacion"],
    description=(
        "Pide un código para recuperar el acceso (MATU-57). Recibe solo el email. Responde siempre 202 sin"
        " cuerpo, exista o no la cuenta y aunque se haya alcanzado el límite (decisión 84): el envío corre"
        " después de responder. El código va al celular verificado o, si no hay, al correo; con"
        " `canal: \"correo\"`, al correo. Pedir otro invalida el anterior. Orden: 422, 503 y 202."
    ),
    responses={202: {"headers": _NO_STORE}, 422: {"description": "Cuerpo inválido", **PROBLEMA}, **_503},
)
def pedir_codigo_recuperacion(
    request: Request,
    solicitud: SolicitudCodigoRecuperacion,
    tareas: BackgroundTasks,
    pepper_email: Annotated[bytes, Depends(obtener_pepper_email)],
    pepper_limites: PepperLimitesDep,
    pepper_recuperacion: PepperRecuperacionDep,
    repositorio: Annotated[RepositorioUsuarios, Depends(obtener_repositorio_usuarios)],
    unidad: UnidadDep,
    almacen: AlmacenDep,
    envios: EnviosDep,
    enviador: EnviadorDep,
    reloj: RelojDep,
) -> Response:
    peppers = _peppers(pepper_email, pepper_limites, pepper_recuperacion)
    tareas.add_task(
        _solicitar_en_segundo_plano,
        email=solicitud.email,
        solo_correo=solicitud.canal == "correo",
        ip=_ip(request),
        peppers=peppers,
        repositorio=repositorio,
        unidad=unidad,
        almacen=almacen,
        envios=envios,
        enviador=_con_enviador(enviador),
        reloj=reloj,
        request_id=request_id(request),
    )
    return Response(status_code=status.HTTP_202_ACCEPTED, headers={"Cache-Control": "no-store"})


@router.post(
    "/recuperacion/contrasena",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["recuperacion"],
    description=(
        "Cambia la contraseña con el código (MATU-57). Un código incorrecto, vencido, ya usado, con los 5"
        " intentos agotados o de un email sin cuenta responde el mismo 422 `codigo-invalido`. Al cambiarla"
        " revoca todas las sesiones (`cambio_clave`), invalida los códigos pendientes y avisa por el otro"
        " canal. No emite tokens: la persona vuelve a entrar. Orden: 422 del cuerpo, 503, 429, 422"
        " codigo-invalido y 204."
    ),
    responses={
        204: {"headers": _NO_STORE},
        422: {"description": "Cuerpo inválido (validacion) o codigo-invalido. Nunca repite valores", **PROBLEMA},
        **_429,
        **_503,
    },
)
def cambiar_contrasena(
    request: Request,
    solicitud: SolicitudCambioContrasena,
    pepper_email: Annotated[bytes, Depends(obtener_pepper_email)],
    pepper_limites: PepperLimitesDep,
    pepper_recuperacion: PepperRecuperacionDep,
    hasher: Annotated[HasherContrasenas, Depends(obtener_hasher)],
    repositorio: Annotated[RepositorioUsuarios, Depends(obtener_repositorio_usuarios)],
    unidad: UnidadDep,
    almacen: AlmacenDep,
    contadores: ContadoresDep,
    enviador: EnviadorDep,
    reloj: RelojDep,
) -> Response:
    peppers = _peppers(pepper_email, pepper_limites, pepper_recuperacion)
    try:
        cambiar_contrasena_con_codigo(
            email=solicitud.email,
            codigo=solicitud.codigo,
            contrasena_nueva=solicitud.contrasena_nueva,
            ip=_ip(request),
            peppers=peppers,
            hasher=hasher,
            repositorio=repositorio,
            unidad=unidad,
            almacen=almacen,
            contadores=contadores,
            enviador=_con_enviador(enviador),
            reloj=reloj,
            request_id=request_id(request),
        )
    except DemoraActiva as demora:
        raise _espera(demora.segundos) from None
    except ContadoresNoDisponibles:
        raise _sin_servicio() from None
    except CodigoInvalido:
        raise _codigo_invalido() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


# --- La cuenta y su celular -------------------------------------------------------------------------


@router.get(
    "/cuenta",
    response_model=CuentaVista,
    tags=["cuenta"],
    description=(
        "La cuenta propia, con el celular enmascarado y si está verificado (MATU-57). Desde MATU-75, también la"
        " última política de privacidad que aceptó (politica_aceptada), o null si la cuenta no tiene registro"
        " (decisión 179)."
    ),
    responses={200: {"headers": _NO_STORE}, **_401},
)
def ver_cuenta(respuesta: Response, usuario: Usuario, unidad: UnidadDep) -> CuentaVista:
    datos, aceptacion = leer_cuenta_y_aceptacion(usuario_id=usuario.id, unidad=unidad)
    respuesta.headers["Cache-Control"] = "no-store"
    return CuentaVista(
        id=datos.id,
        nombre=datos.nombre,
        email=datos.email,
        celular_enmascarado=enmascarar_celular(datos.telefono),
        celular_verificado=datos.telefono is not None and datos.celular_verificado_en is not None,
        celular_canal=datos.celular_canal,  # type: ignore[arg-type]
        politica_aceptada=None
        if aceptacion is None
        else PoliticaAceptadaVista(
            version=aceptacion.version, huella=aceptacion.huella, aceptada_en=aceptacion.aceptada_en
        ),
    )


@router.post(
    "/cuenta/celular/codigo",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    tags=["cuenta"],
    description=(
        "Envía un código al celular de la cuenta para verificarlo (MATU-57). 60 s entre envíos, 3 por hora y"
        " 10 al día por cuenta y por número. Pedir otro invalida el anterior. Orden: 401, 503, 409, 429 y 202."
    ),
    responses={
        202: {"headers": _NO_STORE},
        **_401,
        409: {"description": "celular-verificado (ya lo está) o sin-celular (la cuenta no tiene)", **PROBLEMA},
        **_429,
        **_503,
    },
)
def pedir_codigo_del_celular(
    request: Request,
    usuario: Usuario,
    pepper_email: Annotated[bytes, Depends(obtener_pepper_email)],
    pepper_limites: PepperLimitesDep,
    pepper_recuperacion: PepperRecuperacionDep,
    unidad: UnidadDep,
    almacen: AlmacenDep,
    envios: EnviosDep,
    enviador: EnviadorDep,
    reloj: RelojDep,
) -> Response:
    peppers = _peppers(pepper_email, pepper_limites, pepper_recuperacion)
    try:
        pedir_codigo_celular(
            usuario_id=usuario.id,
            peppers=peppers,
            unidad=unidad,
            almacen=almacen,
            envios=envios,
            enviador=_con_enviador(enviador),
            reloj=reloj,
            request_id=request_id(request),
        )
    except CelularYaVerificado:
        raise ErrorMATU(409, tipo="celular-verificado", detalle="Tu celular ya está confirmado") from None
    except SinCelular:
        raise ErrorMATU(409, tipo="sin-celular", detalle="Tu cuenta no tiene celular") from None
    except EnvioEnEspera as espera:
        raise _espera(espera.segundos) from None
    except ContadoresNoDisponibles:
        raise _sin_servicio() from None
    return Response(status_code=status.HTTP_202_ACCEPTED, headers={"Cache-Control": "no-store"})


@router.post(
    "/cuenta/celular/verificar",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["cuenta"],
    description=(
        "Confirma el celular con el código (MATU-57). Todo código que no sirve responde el mismo 422"
        " `codigo-invalido`. Desde aquí, la recuperación va al celular. Orden: 401, 422 del cuerpo, 503, 429,"
        " 422 codigo-invalido y 204."
    ),
    responses={
        204: {"headers": _NO_STORE},
        **_401,
        422: {"description": "Cuerpo inválido (validacion) o codigo-invalido. Nunca repite valores", **PROBLEMA},
        **_429,
        **_503,
    },
)
def confirmar_celular(
    request: Request,
    solicitud: SolicitudVerificarCelular,
    usuario: Usuario,
    pepper_email: Annotated[bytes, Depends(obtener_pepper_email)],
    pepper_limites: PepperLimitesDep,
    pepper_recuperacion: PepperRecuperacionDep,
    unidad: UnidadDep,
    almacen: AlmacenDep,
    contadores: ContadoresDep,
    reloj: RelojDep,
) -> Response:
    peppers = _peppers(pepper_email, pepper_limites, pepper_recuperacion)
    try:
        verificar_celular(
            usuario_id=usuario.id,
            codigo=solicitud.codigo,
            canal_preferido=solicitud.canal,
            peppers=peppers,
            unidad=unidad,
            almacen=almacen,
            contadores=contadores,
            reloj=reloj,
            request_id=request_id(request),
        )
    except DemoraActiva as demora:
        raise _espera(demora.segundos) from None
    except ContadoresNoDisponibles:
        raise _sin_servicio() from None
    except CodigoInvalido:
        raise _codigo_invalido() from None
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})
