"""Adaptador del puerto EmisorTokens con PyJWT.

El algoritmo es fijo, HS256, y se pasa explícito al verificar: un token con otro alg en su
cabecera (none, RS256 con la clave como clave pública, …) se rechaza antes de mirar la firma.
El vencimiento no lo decide PyJWT con la hora del sistema, sino validar_acceso con el Reloj.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import jwt

from app.modules.iam.application.ports import ClaimsAcceso
from app.modules.iam.domain.sesion import TokenInvalido

ALGORITMO = "HS256"
CLAIMS_OBLIGATORIOS = ["sub", "iat", "exp"]


def _instante(valor: Any) -> datetime:
    # bool es subclase de int: true no es una fecha
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        raise ValueError("el claim no es un instante numérico")
    return datetime.fromtimestamp(valor, UTC)


class EmisorJWT:
    def __init__(self, clave: bytes) -> None:
        if not clave:
            raise ValueError("La clave del JWT no puede estar vacía")
        self._clave = clave

    def emitir(self, usuario_id: uuid.UUID, emitido_en: datetime, expira_en: datetime) -> str:
        claims = {
            "sub": str(usuario_id),
            "iat": int(emitido_en.timestamp()),
            "exp": int(expira_en.timestamp()),
        }
        return jwt.encode(claims, self._clave, algorithm=ALGORITMO)

    def leer(self, token: str) -> ClaimsAcceso:
        try:
            claims = jwt.decode(
                token,
                self._clave,
                algorithms=[ALGORITMO],
                options={"require": CLAIMS_OBLIGATORIOS, "verify_exp": False, "verify_iat": False},
            )
            sub = claims["sub"]
            if not isinstance(sub, str):
                raise ValueError("sub no es texto")
            return ClaimsAcceso(sub=uuid.UUID(sub), iat=_instante(claims["iat"]), exp=_instante(claims["exp"]))
        except (jwt.PyJWTError, ValueError, OverflowError, OSError):
            # Sin encadenar ni copiar el mensaje: no hace falta saber por qué falló, y el token no
            # debe llegar a ninguna traza
            raise TokenInvalido() from None
