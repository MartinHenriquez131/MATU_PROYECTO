"""Rutas públicas del relevo, sin cuenta (MATU-19, RF-06). Contrato: docs/api/propuestos/relevo.openapi.yaml.

    POST /v1/relevo/presentacion   token → los dos nombres de pila (decisión 28)
    POST /v1/relevo/canje          token y PIN → 204 con la cookie __Secure-matu-relevo
    GET  /v1/relevo/ficha          cookie → solo los campos habilitados

Cada petición usa dos transacciones:

1. Sin contexto, solo indice_token (sin RLS): el estado por revocado_en y expira_en (decisión 23).
2. sesion_tenant(acceso_relevo_id=…, rol='relevo'): nunca app.grupo_id ni el rol 'sistema' (C1).

Los casos de uso que lanzan lo hacen antes de escribir. El PIN incorrecto y el bloqueo vuelven como
resultado: la transacción confirma el contador y la auditoría y recién después se responde 401 o 423
(C6). El token, el PIN y el id de sesión nunca van a un log, a un error ni a una cabecera que no sea
la cookie. Las cabeceras no-store, no-referrer y noindex las pone app/core/cabeceras.py (C11).
"""

import base64
import binascii
import hashlib
import logging
import uuid
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any

import redis
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.modules.care_plan.api.dependencias import obtener_custodia, obtener_pepper_pin
from app.modules.care_plan.api.esquemas_relevo import (
    CampoRelevoVista,
    FichaRelevoVista,
    PresentacionVista,
    SolicitudCanjeVista,
    SolicitudPresentacionVista,
)
from app.modules.care_plan.application.canje_relevo import (
    AccesoBloqueadoAhora,
    CanjeAceptado,
    PinIncorrecto,
    PinNoVerificable,
    RelevoBloqueado,
    RelevoNoDisponible,
    TipoNoDisponible,
    abrir_sesion,
    canjear,
    presentar,
    verificar_indice,
)
from app.modules.care_plan.application.ficha_relevo import PlanDelRelevoNoDisponible, leer_ficha_relevo
from app.modules.care_plan.application.ports import (
    CustodiaClaves,
    EntradaIndice,
    SesionesNoDisponibles,
    SesionesRelevo,
)
from app.modules.care_plan.domain.cifrado import ErrorCifrado
from app.modules.care_plan.domain.ficha import CampoFicha
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from app.modules.care_plan.infrastructure.credenciales_relevo import LARGO_TOKEN, HuellasHmac
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from app.modules.care_plan.infrastructure.repositorio_relevo import (
    IndiceTokensSQL,
    RepositorioAccesoRelevoSQL,
    SeccionesRelevoSQL,
)
from app.modules.care_plan.infrastructure.sesiones_relevo_redis import SesionesRelevoRedis
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import RegistroAuditoria, Reloj

log = logging.getLogger("matu.care_plan.relevo")

router = APIRouter(prefix="/relevo", tags=["relevo"])

COOKIE = "__Secure-matu-relevo"
RUTA_COOKIE = "/v1/relevo"
_ATRIBUTOS = f"Path={RUTA_COOKIE}; HttpOnly; Secure; SameSite=Strict"
BORRAR_COOKIE = f"{COOKIE}=; Max-Age=0; {_ATRIBUTOS}"

_TEXTOS: dict[TipoNoDisponible, str] = {
    TipoNoDisponible.NO_DISPONIBLE: "Este enlace no sirve. Pídele a quien te envió el enlace uno nuevo",
    TipoNoDisponible.VENCIDO: "Este enlace venció. Pídele a quien te envió el enlace uno nuevo",
    TipoNoDisponible.REVOCADO: (
        "Quien te compartió la ficha cortó este enlace. Pídele a quien te envió el enlace uno nuevo"
    ),
    # Decisión 33: no revela el motivo (consentimiento retirado o revisión anual vencida)
    TipoNoDisponible.PAUSADO: "Por ahora no puedes abrir esta ficha. Habla con quien te envió el enlace",
}

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES_ANTES_DEL_PIN: dict[int | str, dict[str, Any]] = {
    410: {"description": "relevo-no-disponible, relevo-vencido, relevo-revocado o relevo-pausado", **_PROBLEMA},
    422: {"description": "Cuerpo inválido. No cuenta como intento", **_PROBLEMA},
    423: {"description": "Bloqueado por 5 PIN incorrectos", **_PROBLEMA},
}


# --- Dependencias --------------------------------------------------------------------------------------


@lru_cache
def _sesiones_redis() -> SesionesRelevo:
    return SesionesRelevoRedis(redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=2))


def obtener_sesiones_relevo() -> SesionesRelevo:
    """Las sesiones de relevo en Redis. Las pruebas la sobreescriben con SesionesRelevoEnMemoria."""
    return _sesiones_redis()


FabricaRegistro = Callable[[Session], RegistroAuditoria]


def obtener_fabrica_registro(reloj: Annotated[Reloj, Depends(obtener_reloj)]) -> FabricaRegistro:
    """El registro de auditoría sobre la sesión de relevo. Las pruebas lo sobreescriben para hacerlo fallar."""
    return lambda sesion: RegistroAuditoriaSql(sesion, reloj)


Fabrica = Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
SesionesDep = Annotated[SesionesRelevo, Depends(obtener_sesiones_relevo)]
RegistroDep = Annotated[FabricaRegistro, Depends(obtener_fabrica_registro)]


# --- Errores -------------------------------------------------------------------------------------------


def _no_disponible(tipo: TipoNoDisponible, headers: dict[str, str] | None = None) -> ErrorMATU:
    return ErrorMATU(410, tipo=tipo.value, detalle=_TEXTOS[tipo], headers=headers)


def _bloqueado(headers: dict[str, str] | None = None) -> ErrorMATU:
    return ErrorMATU(
        423,
        tipo="relevo-bloqueado",
        detalle="El enlace se bloqueó por PIN incorrecto. Pídele a quien te envió el enlace uno nuevo",
        headers=headers,
    )


def _sin_servicio() -> ErrorMATU:
    return ErrorMATU(503, detalle="La ficha no está disponible en este momento. Cita el request_id si lo reportas")


def _sin_sesion() -> ErrorMATU:
    return ErrorMATU(401, tipo="sin-sesion-relevo", detalle="Abre de nuevo el enlace y escribe el PIN")


# --- Paso 1: indice_token ------------------------------------------------------------------------------


def _huella_token(token: str) -> bytes | None:
    """SHA-256 de los 32 bytes crudos del token (notas para implementar). None si no es un token."""
    try:
        crudo = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None
    return hashlib.sha256(crudo).digest() if len(crudo) == LARGO_TOKEN else None


def _acceso_por_token(fabrica: sessionmaker[Session], token: str, reloj: Reloj) -> uuid.UUID:
    huella = _huella_token(token)
    entrada: EntradaIndice | None = None
    if huella is not None:
        with sesion_tenant(fabrica) as sesion:
            entrada = IndiceTokensSQL(sesion).por_token(huella)
    try:
        return verificar_indice(entrada, reloj.ahora())
    except RelevoNoDisponible as error:
        raise _no_disponible(error.tipo) from None


# --- Rutas ---------------------------------------------------------------------------------------------


@router.post("/presentacion", response_model=PresentacionVista, responses=_ERRORES_ANTES_DEL_PIN)
def presentar_relevo(
    request: Request,
    solicitud: SolicitudPresentacionVista,
    fabrica: Fabrica,
    reloj: RelojDep,
    registro: RegistroDep,
) -> PresentacionVista:
    acceso_id = _acceso_por_token(fabrica, solicitud.token, reloj)
    try:
        with sesion_tenant(fabrica, acceso_relevo_id=acceso_id, rol="relevo") as sesion:
            vista = presentar(
                RepositorioAccesoRelevoSQL(sesion), registro(sesion), reloj, getattr(request.state, "request_id", None)
            )
    except RelevoNoDisponible as error:
        raise _no_disponible(error.tipo) from None
    except RelevoBloqueado:
        raise _bloqueado() from None
    return PresentacionVista(nombre_pila_comparte=vista.nombre_pila_comparte, nombre_pila=vista.nombre_pila)


@router.post(
    "/canje",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        **_ERRORES_ANTES_DEL_PIN,
        401: {"description": "PIN incorrecto, del 1.º al 4.º intento", **_PROBLEMA},
        503: {"description": "Falta PEPPER_PIN o Redis no responde: falla cerrado", **_PROBLEMA},
    },
)
def canjear_relevo(
    request: Request,
    solicitud: SolicitudCanjeVista,
    fabrica: Fabrica,
    reloj: RelojDep,
    registro: RegistroDep,
    sesiones: SesionesDep,
    pepper: Annotated[bytes | None, Depends(obtener_pepper_pin)],
) -> Response:
    acceso_id = _acceso_por_token(fabrica, solicitud.token, reloj)
    huellas = None if pepper is None else HuellasHmac(pepper)
    try:
        with sesion_tenant(fabrica, acceso_relevo_id=acceso_id, rol="relevo") as sesion:
            resultado = canjear(
                solicitud.pin, RepositorioAccesoRelevoSQL(sesion), huellas, registro(sesion), reloj,
                getattr(request.state, "request_id", None),
            )
    except RelevoNoDisponible as error:
        raise _no_disponible(error.tipo) from None
    except RelevoBloqueado:
        raise _bloqueado() from None
    except PinNoVerificable:
        log.error("el canje no pudo verificar el PIN")
        raise _sin_servicio() from None
    # La transacción ya confirmó el contador y la auditoría (C6)
    if isinstance(resultado, AccesoBloqueadoAhora):
        raise _bloqueado()
    if isinstance(resultado, PinIncorrecto):
        raise ErrorMATU(
            401,
            tipo="pin-incorrecto",
            titulo="PIN incorrecto",
            detalle=f"El PIN no coincide. Te quedan {resultado.restantes} intentos",
            extension={"intentos_restantes": resultado.restantes},
        )
    assert isinstance(resultado, CanjeAceptado)
    # Después del commit (P3): si Redis falla, el canje quedó auditado pero sin sesión, y responde 503
    try:
        creada = abrir_sesion(resultado, sesiones)
    except SesionesNoDisponibles:
        log.error("el canje no pudo crear la sesión")
        raise _sin_servicio() from None
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    respuesta.headers["Set-Cookie"] = f"{COOKIE}={creada.sesion_id}; Max-Age={creada.max_age}; {_ATRIBUTOS}"
    return respuesta


@router.get(
    "/ficha",
    response_model=FichaRelevoVista,
    responses={
        401: {"description": "Sin cookie, o cookie sin sesión en Redis", **_PROBLEMA},
        410: {"description": "relevo-vencido, relevo-revocado o relevo-pausado. Borra la cookie", **_PROBLEMA},
        423: {"description": "Bloqueado después del canje. Borra la cookie", **_PROBLEMA},
        503: {"description": "Redis o la custodia de la clave no responden", **_PROBLEMA},
    },
)
def leer_ficha_como_relevo(
    request: Request,
    fabrica: Fabrica,
    reloj: RelojDep,
    registro: RegistroDep,
    sesiones: SesionesDep,
    custodia: Annotated[CustodiaClaves | None, Depends(obtener_custodia)],
) -> FichaRelevoVista:
    sesion_id = request.cookies.get(COOKIE)
    if not sesion_id or len(sesion_id) > 128:
        raise _sin_sesion()
    try:
        acceso_id = sesiones.acceso_de(sesion_id)
    except SesionesNoDisponibles:
        raise _sin_servicio() from None
    if acceso_id is None:
        raise _sin_sesion()

    def cortar(error: ErrorMATU) -> ErrorMATU:
        # 410 y 423 descartan la sesión y borran la cookie (C11)
        try:
            sesiones.descartar(sesion_id)
        except SesionesNoDisponibles:
            log.error("no se pudo descartar una sesión de relevo")
        error.headers = {**(error.headers or {}), "Set-Cookie": BORRAR_COOKIE}
        return error

    with sesion_tenant(fabrica) as sesion:
        entrada = IndiceTokensSQL(sesion).por_acceso(acceso_id)
    try:
        verificar_indice(entrada, reloj.ahora())
    except RelevoNoDisponible as error:
        # Sin entrada en indice_token, el acceso ya se purgó tras vencer: la ficha no usa no-disponible
        tipo = TipoNoDisponible.VENCIDO if error.tipo is TipoNoDisponible.NO_DISPONIBLE else error.tipo
        raise cortar(_no_disponible(tipo)) from None
    if custodia is None:
        raise _sin_servicio()

    try:
        with sesion_tenant(fabrica, acceso_relevo_id=acceso_id, rol="relevo") as sesion:
            ficha = leer_ficha_relevo(
                RepositorioAccesoRelevoSQL(sesion),
                SeccionesRelevoSQL(sesion),
                CifradorAesGcm(custodia, RepositorioClavesSQL(sesion)),
                registro(sesion),
                reloj,
                getattr(request.state, "request_id", None),
            )
    except RelevoNoDisponible as error:
        raise cortar(_no_disponible(error.tipo)) from None
    except RelevoBloqueado:
        raise cortar(_bloqueado()) from None
    except (ErrorCifrado, PlanDelRelevoNoDisponible):
        log.error("no se pudo leer la ficha del relevo")
        raise _sin_servicio() from None
    return FichaRelevoVista(
        nombre_pila=ficha.nombre_pila,
        nombre_pila_comparte=ficha.nombre_pila_comparte,
        vence_en=ficha.vence_en,
        campos={CampoFicha(c): CampoRelevoVista(texto=t) for c, t in ficha.campos.items()},
    )
