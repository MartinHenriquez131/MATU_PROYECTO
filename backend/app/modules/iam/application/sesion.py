"""Casos de uso: iniciar sesión y validar un access token (MATU-05a, RF-37)."""

import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.iam.application.ports import (
    ClaimsAcceso,
    CredencialGuardada,
    EmisorTokens,
    HasherContrasenas,
    RepositorioUsuarios,
)
from app.modules.iam.domain.credenciales import indice_email, normalizar_email
from app.modules.iam.domain.mfa import vence_la_sesion
from app.modules.iam.domain.sesion import (
    DURACION_ACCESO,
    CredencialesInvalidas,
    TokenInvalido,
    esta_vigente,
    puede_iniciar_sesion,
    vencimiento,
)
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class SesionIniciada:
    usuario_id: uuid.UUID
    access_token: str
    expira_en: datetime
    duracion_segundos: int


# Hash de relleno por tipo de hasher, generado la primera vez que se necesita. Se verifica contra
# él cuando el email no tiene cuenta, para que el tiempo de respuesta no delate si existe.
_hashes_relleno: dict[type, str] = {}
_candado_relleno = threading.Lock()


def _hash_relleno(hasher: HasherContrasenas) -> str:
    tipo = type(hasher)
    with _candado_relleno:
        if tipo not in _hashes_relleno:
            # Una contraseña al azar que nadie conoce: verificar contra ella siempre falla
            _hashes_relleno[tipo] = hasher.hashear(secrets.token_urlsafe(32))
        return _hashes_relleno[tipo]


def iniciar_sesion(
    *,
    email: str,
    contrasena: str,
    pepper: bytes,
    hasher: HasherContrasenas,
    repositorio: RepositorioUsuarios,
    emisor: EmisorTokens,
    reloj: Reloj,
) -> SesionIniciada:
    """Verifica las credenciales y emite un access token de 15 minutos.

    Lanza CredencialesInvalidas, siempre igual, si el email no tiene cuenta, si la contraseña no
    corresponde o si la cuenta no está activa. En los tres casos se verifica un hash de Argon2id,
    para que el tiempo de respuesta tampoco distinga los casos.
    """
    usuario_id = verificar_credenciales(
        email=email, contrasena=contrasena, pepper=pepper, hasher=hasher, repositorio=repositorio
    )
    return emitir_acceso(usuario_id, emisor, reloj)


def verificar_credenciales(
    *, email: str, contrasena: str, pepper: bytes, hasher: HasherContrasenas, repositorio: RepositorioUsuarios
) -> uuid.UUID:
    """Devuelve el id de la cuenta si el email y la contraseña corresponden y la cuenta está activa.

    Lanza CredencialesInvalidas, siempre igual, en los demás casos, después de verificar un hash.
    """
    return verificar_cuenta(
        email=email, contrasena=contrasena, pepper=pepper, hasher=hasher, repositorio=repositorio
    ).usuario_id


def verificar_cuenta(
    *, email: str, contrasena: str, pepper: bytes, hasher: HasherContrasenas, repositorio: RepositorioUsuarios
) -> CredencialGuardada:
    """Como verificar_credenciales, y entrega además si la cuenta es de operación (MATU-81)."""
    credencial = repositorio.buscar_credencial(indice_email(pepper, normalizar_email(email)))
    if credencial is None:
        hasher.verificar(_hash_relleno(hasher), contrasena)
        raise CredencialesInvalidas()

    contrasena_correcta = hasher.verificar(credencial.password_hash, contrasena)
    if not contrasena_correcta or not puede_iniciar_sesion(credencial.estado):
        raise CredencialesInvalidas()
    return credencial


def emitir_acceso(
    usuario_id: uuid.UUID,
    emisor: EmisorTokens,
    reloj: Reloj,
    dispositivo_id: uuid.UUID | None = None,
    mfa_en: datetime | None = None,
) -> SesionIniciada:
    """Emite un access token de 15 minutos, con el claim did si llega el dispositivo (MATU-38). Con el segundo factor
    (MATU-81), lleva el claim mfa y no vive más allá de las 12 horas de la sesión de operación (C31)."""
    emitido_en = reloj.ahora()
    expira_en = vencimiento(emitido_en)
    if mfa_en is not None:
        expira_en = min(expira_en, vence_la_sesion(mfa_en))
    duracion = int((expira_en - emitido_en).total_seconds())
    return SesionIniciada(
        usuario_id=usuario_id,
        access_token=emisor.emitir(usuario_id, emitido_en, expira_en, dispositivo_id, mfa_en)
        if mfa_en is not None
        else emisor.emitir(usuario_id, emitido_en, expira_en, dispositivo_id),
        expira_en=expira_en,
        duracion_segundos=duracion if mfa_en is not None else int(DURACION_ACCESO.total_seconds()),
    )


def leer_acceso(token: str, emisor: EmisorTokens, reloj: Reloj) -> ClaimsAcceso:
    """Los claims de un token vigente. Lanza TokenInvalido si no sirve o ya venció."""
    claims = emisor.leer(token)
    if not esta_vigente(claims.exp, reloj.ahora()):
        raise TokenInvalido()
    return claims


def validar_acceso(token: str, emisor: EmisorTokens, reloj: Reloj) -> uuid.UUID:
    """Devuelve el id del usuario del token. Lanza TokenInvalido si no sirve o ya venció."""
    return leer_acceso(token, emisor, reloj).sub
