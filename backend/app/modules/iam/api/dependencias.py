"""Dependencias de FastAPI para la sesión: el reloj, el emisor de tokens y el usuario actual.

usuario_actual es la puerta de toda ruta autenticada. MATU-02 y MATU-06 la importan desde aquí.
Valida firma, algoritmo y vencimiento del access token en cada petición, y nunca registra el token.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.iam.application.ports import EmisorTokens
from app.modules.iam.application.sesion import validar_acceso
from app.modules.iam.domain.sesion import TokenInvalido
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

# auto_error=False: sin cabecera, o con un esquema distinto de Bearer, entrega None y la respuesta
# la arma usuario_actual como problema RFC 7807 en vez del 403 de FastAPI
_esquema_bearer = HTTPBearer(auto_error=False)

_CABECERA_BEARER = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class UsuarioActual:
    id: uuid.UUID


def obtener_clave_jwt() -> bytes:
    clave = obtener_configuracion().jwt_clave
    if clave is None:
        raise RuntimeError("Falta JWT_CLAVE. Copia .env.example a .env y complétalo.")
    return clave.get_secret_value().encode("utf-8")


def obtener_emisor_tokens(clave: Annotated[bytes, Depends(obtener_clave_jwt)]) -> EmisorTokens:
    return EmisorJWT(clave)


def obtener_reloj() -> Reloj:
    return RelojSistema()


def usuario_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_esquema_bearer)],
    emisor: Annotated[EmisorTokens, Depends(obtener_emisor_tokens)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> UsuarioActual:
    if credenciales is None:
        raise ErrorMATU(401, detalle="Inicia sesión para continuar", headers=_CABECERA_BEARER)
    try:
        return UsuarioActual(id=validar_acceso(credenciales.credentials, emisor, reloj))
    except TokenInvalido:
        raise ErrorMATU(
            401, tipo="token-invalido", detalle="Inicia sesión de nuevo", headers=_CABECERA_BEARER
        ) from None
