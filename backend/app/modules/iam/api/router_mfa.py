"""El segundo paso de la entrada de operación (MATU-81, C26 a C32; decisiones 449 a 455).

- ``mfa_requerido``: el 401 mfa-requerido de POST /v1/sesiones, con el desafío de 5 minutos. Sin tokens ni cookie.
- POST /v1/sesiones/mfa: el desafío y las 6 cifras. Con el código correcto responde como POST /v1/sesiones
  (SesionRespuesta con la cookie del refresh, ``tipo_cuenta: operacion`` y ``sesion_vence_en``, 12 horas después).
  Los fallos tienen tres ``type`` distintos (P2 del diseñador): codigo-mfa-incorrecto (401, con
  ``intentos_restantes``), mfa-bloqueado (429, con Retry-After y ``minutos_espera``) y desafio-vencido (401). Un paso ya
  usado: codigo-mfa-usado (401, sin sumar un fallo). Sin Redis, sin PEPPER_LIMITES o sin la KEK: 503.

Cache-Control: no-store lo pone el middleware de /v1/sesiones. Nada de esto se registra en el log.
"""

import logging
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

import redis
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones
from app.core.errores import ErrorMATU
from app.modules.iam.api.dependencias import TipoCuenta, obtener_emisor_tokens, obtener_reloj, obtener_tipo_cuenta
from app.modules.iam.api.esquemas import SesionRespuesta, SolicitudMfa
from app.modules.iam.api.sesion_web import (
    PROBLEMA,
    PepperLimitesDep,
    UnidadDep,
    cookie_refresh,
    fijar_cookie,
    request_id,
)
from app.modules.iam.application import mfa as casos
from app.modules.iam.application.ports import (
    AlmacenMfa,
    CifradorMfa,
    ContadoresNoDisponibles,
    EmisorTokens,
    SecretosMfa,
)
from app.modules.iam.infrastructure.cifrador_mfa import cifrador_de
from app.modules.iam.infrastructure.mfa_redis import AlmacenMfaRedis
from app.modules.iam.infrastructure.repositorio_usuarios import SecretosMfaSQL
from app.shared.puertos import Reloj

log = logging.getLogger("matu.iam")

router = APIRouter(tags=["sesiones"])

_SIN_SERVICIO = "No se puede entrar en este momento. Cita el request_id si lo reportas"
DETALLE_MFA_REQUERIDO = "Escribe el código de 6 cifras de la app de tu teléfono"


@lru_cache
def _redis() -> "redis.Redis":
    return redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=2)


def obtener_almacen_mfa() -> AlmacenMfa:
    """El desafío, los fallos y el último paso en Redis. Las pruebas lo sobreescriben con AlmacenMfaEnMemoria."""
    return AlmacenMfaRedis(_redis())


def obtener_cifrador_mfa() -> CifradorMfa | None:
    """El cifrador con la KEK, o None si la custodia está apagada (503). Las pruebas lo sobreescriben."""
    return cifrador_de(obtener_configuracion())


def obtener_secretos_mfa(
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
) -> SecretosMfa:
    return SecretosMfaSQL(fabrica)


AlmacenMfaDep = Annotated[AlmacenMfa, Depends(obtener_almacen_mfa)]


def mfa_requerido(usuario_id: Any, almacen: AlmacenMfa, reloj: Reloj, request: Request) -> ErrorMATU:
    """El 401 mfa-requerido con su desafío. 503 si Redis no responde (C32)."""
    try:
        desafio, guardado = casos.crear_desafio(usuario_id=usuario_id, almacen=almacen, reloj=reloj)
    except ContadoresNoDisponibles:
        log.error("Redis no responde: la entrada de operación falla cerrada")
        return ErrorMATU(503, detalle=_SIN_SERVICIO)
    request.state.usuario_id = str(usuario_id)
    return ErrorMATU(
        401,
        tipo="mfa-requerido",
        detalle=DETALLE_MFA_REQUERIDO,
        headers={"Cache-Control": "no-store"},
        extension={"desafio": desafio, "desafio_expira_en": _iso(guardado.expira_en)},
    )


def _iso(instante: datetime) -> str:
    return instante.isoformat().replace("+00:00", "Z")


@router.post(
    "/sesiones/mfa",
    response_model=SesionRespuesta,
    description=(
        "MATU-81 (C29): el segundo paso de la entrada de una cuenta de operación. Recibe el `desafio` del 401"
        " mfa-requerido de POST /v1/sesiones y las 6 cifras de la app del teléfono (TOTP, RFC 6238, ventana de ±1"
        " paso). Con el código correcto, la misma respuesta y la misma cookie que POST /v1/sesiones, con"
        " `tipo_cuenta: operacion` y `sesion_vence_en` (12 horas, sin ventana deslizante: C31). El desafío sirve una"
        " vez. Se audita `sesion.mfa_correcto` o `sesion.mfa_fallido`, sin grupo ni código. Orden: 422, 503, 401"
        " desafio-vencido, 429 mfa-bloqueado, 401 codigo-mfa-incorrecto o codigo-mfa-usado, 200."
    ),
    responses={
        200: {"headers": {"Set-Cookie": {"description": "Cookie del refresh", "schema": {"type": "string"}}}},
        401: {
            "description": (
                "desafio-vencido: el desafío no existe, venció (5 minutos) o ya se usó; se vuelve a la contraseña."
                " codigo-mfa-incorrecto: el código no coincide; trae `intentos_restantes` (de 5 por cuenta en 15"
                " minutos). codigo-mfa-usado: ese código ya abrió una sesión; se espera el siguiente (30 segundos)"
            ),
            **PROBLEMA,
        },
        422: {
            "description": "Cuerpo inválido: el desafío no tiene 43 caracteres o el código no son 6 cifras",
            **PROBLEMA,
        },
        429: {
            "description": "mfa-bloqueado: 5 códigos fallidos de la cuenta. Trae `minutos_espera` y Retry-After",
            "headers": {"Retry-After": {"description": "Segundos", "schema": {"type": "integer"}}},
            **PROBLEMA,
        },
        503: {"description": "Redis no responde, falta PEPPER_LIMITES o la KEK: falla cerrada", **PROBLEMA},
    },
)
def verificar_mfa(  # noqa: PLR0913 - las dependencias de la entrada
    request: Request,
    solicitud: SolicitudMfa,
    respuesta: Response,
    pepper_limites: PepperLimitesDep,
    almacen: AlmacenMfaDep,
    cifrador: Annotated[CifradorMfa | None, Depends(obtener_cifrador_mfa)],
    secretos: Annotated[SecretosMfa, Depends(obtener_secretos_mfa)],
    unidad: UnidadDep,
    emisor: Annotated[EmisorTokens, Depends(obtener_emisor_tokens)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    tipo_cuenta: Annotated[TipoCuenta, Depends(obtener_tipo_cuenta)],
) -> SesionRespuesta:
    if pepper_limites is None or cifrador is None:
        log.error("falta PEPPER_LIMITES o la KEK: la entrada de operación falla cerrada")
        raise ErrorMATU(503, detalle=_SIN_SERVICIO)
    try:
        sesion = casos.verificar(
            desafio=solicitud.desafio,
            codigo=solicitud.codigo,
            agente_usuario=request.headers.get("user-agent"),
            refresh_presentado=cookie_refresh(request),
            pepper_limites=pepper_limites,
            almacen=almacen,
            cifrador=cifrador,
            secretos=secretos,
            unidad=unidad,
            emisor=emisor,
            reloj=reloj,
            request_id=request_id(request),
        )
    except ContadoresNoDisponibles:
        log.error("Redis no responde: la entrada de operación falla cerrada")
        raise ErrorMATU(503, detalle=_SIN_SERVICIO) from None
    except casos.DesafioVencido:
        raise ErrorMATU(
            401,
            tipo="desafio-vencido",
            detalle="Pasaron más de 5 minutos. Vuelve a escribir tu contraseña para pedir otro código",
        ) from None
    except casos.MfaAgotado as agotado:
        segundos = max(1, agotado.segundos)
        raise ErrorMATU(
            429,
            tipo="mfa-bloqueado",
            detalle="Hubo 5 códigos que no coinciden. Espera antes de volver a intentarlo",
            headers={"Retry-After": str(segundos)},
            extension={"minutos_espera": max(1, -(-segundos // 60))},
        ) from None
    except casos.CodigoIncorrecto as incorrecto:
        raise ErrorMATU(
            401,
            tipo="codigo-mfa-incorrecto",
            detalle="El código no coincide. Revisa la app de tu teléfono",
            extension={"intentos_restantes": incorrecto.restantes},
        ) from None
    except casos.CodigoUsado:
        raise ErrorMATU(
            401, tipo="codigo-mfa-usado", detalle="Ese código ya se usó. Espera el siguiente en tu teléfono"
        ) from None
    respuesta.headers["Cache-Control"] = "no-store"
    fijar_cookie(respuesta, sesion.refresh)
    request.state.usuario_id = str(sesion.usuario_id)
    return SesionRespuesta(
        access_token=sesion.access_token,
        expira_en=sesion.duracion_segundos,
        tipo_cuenta=tipo_cuenta(sesion.usuario_id),  # type: ignore[arg-type]
        sesion_vence_en=sesion.vence_en,
    )
