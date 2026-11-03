"""Rutas de iam: crear una cuenta (MATU-04) e iniciar sesión (MATU-05a, con el cambio de MATU-38).

La renovación, el cierre y los dispositivos están en router_sesiones.py.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones
from app.core.errores import TITULOS, ErrorMATU
from app.modules.iam.api.dependencias import obtener_emisor_tokens, obtener_reloj
from app.modules.iam.api.esquemas import (
    CuentaCreadaRespuesta,
    ProblemaEmailRegistradoVista,
    SesionRespuesta,
    SolicitudRegistro,
    SolicitudSesion,
)
from app.modules.iam.api.sesion_web import (
    PROBLEMA,
    ContadoresDep,
    PepperLimitesDep,
    UnidadDep,
    cookie_refresh,
    fijar_cookie,
    request_id,
)
from app.modules.iam.application.ports import (
    ContadoresNoDisponibles,
    EmisorTokens,
    HasherContrasenas,
    RepositorioUsuarios,
)
from app.modules.iam.application.registro import registrar_usuario
from app.modules.iam.application.sesiones import DemoraActiva, entrar
from app.modules.iam.domain.credenciales import EmailYaRegistrado
from app.modules.iam.domain.sesion import CredencialesInvalidas
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id
from app.modules.iam.infrastructure.repositorio_usuarios import RepositorioUsuariosSQL
from app.shared.puertos import Reloj

log = logging.getLogger("matu.iam")

router = APIRouter(tags=["usuarios"])

_SIN_SERVICIO = "No se puede entrar en este momento. Cita el request_id si lo reportas"


def obtener_pepper_email() -> bytes:
    pepper = obtener_configuracion().pepper_email
    if pepper is None:
        raise RuntimeError("Falta PEPPER_EMAIL. Copia .env.example a .env y complétalo.")
    return pepper.get_secret_value().encode("utf-8")


def obtener_hasher() -> HasherContrasenas:
    return HasherArgon2id()


def obtener_repositorio_usuarios() -> RepositorioUsuarios:
    return RepositorioUsuariosSQL(fabrica_sesiones())


_EJEMPLO_409: dict[str, Any] = {
    "type": "/errores/email-registrado",
    "title": TITULOS[409],
    "status": 409,
    "detail": "Ese email ya tiene una cuenta. Inicia sesión",
    "errores": [],
    "request_id": "9b2f4c1e-0000-4000-8000-0000000000a9",
}


@router.post(
    "/usuarios",
    status_code=status.HTTP_201_CREATED,
    response_model=CuentaCreadaRespuesta,
    description=(
        "Crea una cuenta (MATU-04). Desde MATU-39 pide el celular chileno, obligatorio, que se guarda en"
        " E.164 y nunca se registra en logs ni en la auditoría (decisión 65). Orden: 422 y 409."
    ),
    responses={
        409: {
            "description": "email-registrado: ese email ya tiene una cuenta. El detalle nunca repite el email",
            "content": {
                "application/problem+json": {
                    "schema": ProblemaEmailRegistradoVista.model_json_schema(mode="serialization"),
                    "example": _EJEMPLO_409,
                }
            },
        },
        422: {"description": "Cuerpo inválido, incluido celular_invalido. Nunca repite el valor", **PROBLEMA},
    },
)
def crear_cuenta(
    solicitud: SolicitudRegistro,
    pepper: Annotated[bytes, Depends(obtener_pepper_email)],
    hasher: Annotated[HasherContrasenas, Depends(obtener_hasher)],
    repositorio: Annotated[RepositorioUsuarios, Depends(obtener_repositorio_usuarios)],
) -> CuentaCreadaRespuesta:
    try:
        cuenta = registrar_usuario(
            nombre=solicitud.nombre,
            email=solicitud.email,
            contrasena=solicitud.contrasena,
            telefono=solicitud.telefono,
            pepper=pepper,
            hasher=hasher,
            repositorio=repositorio,
        )
    except EmailYaRegistrado:
        # Riesgo aceptado en el backlog: el 409 revela que el email existe. Se mitiga con el
        # límite por IP de MATU-25. El detalle nunca repite el email.
        raise ErrorMATU(
            409, tipo="email-registrado", detalle="Ese email ya tiene una cuenta. Inicia sesión"
        ) from None
    return CuentaCreadaRespuesta(id=cuenta.id, nombre=cuenta.nombre, email=cuenta.email)


@router.post(
    "/sesiones",
    response_model=SesionRespuesta,
    tags=["sesiones"],
    description=(
        "Inicia sesión (MATU-05a). MATU-38 agrega la cookie `__Secure-matu-refresh` (HttpOnly, Secure,"
        " SameSite=Strict, Path=/v1/sesiones, Max-Age de 30 días), el dispositivo, el claim `did` del"
        " access token y la demora progresiva (429 con Retry-After; sin Redis, 503). Orden: 422, 429 o 503,"
        " 401 y 200. Ver docs/api/propuestos/app-familia.openapi.yaml y las decisiones 47 a 49 y 57."
    ),
    responses={
        200: {"headers": {"Set-Cookie": {"description": "Cookie del refresh", "schema": {"type": "string"}}}},
        401: {"description": "credenciales-invalidas, el mismo exista o no el email", **PROBLEMA},
        422: {"description": "Cuerpo inválido. No cuenta como intento", **PROBLEMA},
        429: {
            "description": "demasiadas-peticiones: la huella de la IP o la del email están en espera",
            "headers": {"Retry-After": {"description": "Segundos, de 1 a 900", "schema": {"type": "integer"}}},
            **PROBLEMA,
        },
        503: {"description": "Redis no responde o falta PEPPER_LIMITES: la entrada falla cerrada", **PROBLEMA},
    },
)
def crear_sesion(
    request: Request,
    solicitud: SolicitudSesion,
    respuesta: Response,
    pepper: Annotated[bytes, Depends(obtener_pepper_email)],
    pepper_limites: PepperLimitesDep,
    hasher: Annotated[HasherContrasenas, Depends(obtener_hasher)],
    repositorio: Annotated[RepositorioUsuarios, Depends(obtener_repositorio_usuarios)],
    contadores: ContadoresDep,
    unidad: UnidadDep,
    emisor: Annotated[EmisorTokens, Depends(obtener_emisor_tokens)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> SesionRespuesta:
    if pepper_limites is None:
        log.error("falta PEPPER_LIMITES: la entrada falla cerrada")
        raise ErrorMATU(503, detalle=_SIN_SERVICIO)
    try:
        sesion = entrar(
            email=solicitud.email,
            contrasena=solicitud.contrasena,
            # La IP del socket. Solo se usa para su huella HMAC: nunca se guarda ni se registra
            ip=request.client.host if request.client else "desconocida",
            agente_usuario=request.headers.get("user-agent"),
            refresh_presentado=cookie_refresh(request),
            pepper=pepper,
            pepper_limites=pepper_limites,
            hasher=hasher,
            repositorio=repositorio,
            contadores=contadores,
            unidad=unidad,
            emisor=emisor,
            reloj=reloj,
            request_id=request_id(request),
        )
    except DemoraActiva as demora:
        raise ErrorMATU(
            429,
            detalle="Espera un rato antes de volver a intentarlo",
            headers={"Retry-After": str(max(1, demora.segundos))},
        ) from None
    except ContadoresNoDisponibles:
        log.error("Redis no responde: la entrada falla cerrada")
        raise ErrorMATU(503, detalle=_SIN_SERVICIO) from None
    except CredencialesInvalidas:
        # El mismo cuerpo si el email no existe, si la contraseña no corresponde o si la cuenta
        # no está activa: la respuesta no revela cuál falló
        raise ErrorMATU(401, tipo="credenciales-invalidas", detalle="Email o contraseña incorrectos") from None
    # Un token no se guarda en cachés intermedias (RFC 6749, sección 5.1). El middleware de
    # /v1/sesiones también lo pone, en los errores
    respuesta.headers["Cache-Control"] = "no-store"
    fijar_cookie(respuesta, sesion.refresh)
    request.state.usuario_id = str(sesion.usuario_id)
    return SesionRespuesta(access_token=sesion.access_token, expira_en=sesion.duracion_segundos)
