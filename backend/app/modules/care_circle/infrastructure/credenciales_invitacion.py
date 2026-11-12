"""El token y el código de la invitación, y sus huellas (MATU-42, decisiones 295 y 297, C21).

- Token: ``secrets.token_bytes(32)``, 256 bits, que viaja en base64url en el fragmento del enlace. Se guarda su SHA-256
  sobre los 32 bytes crudos, como el del relevo: ``huella_de_texto`` decodifica el texto y calcula lo mismo.
- Código: 4 dígitos con ``secrets.randbelow``. Se guarda HMAC-SHA-256(PEPPER_PIN, "invitacion:<id>:<código>"), 32
  bytes: el prefijo separa su dominio del PIN del relevo, que usa la misma llave, y el id hace que dos invitaciones con
  el mismo código tengan huellas distintas.

Ninguna clase guarda el token ni el código, y el pepper no aparece en el repr.
"""

import base64
import binascii
import hashlib
import hmac
import secrets
import uuid

LARGO_TOKEN = 32


class CredencialesInvitacionHmac:
    def __init__(self, pepper: bytes) -> None:
        if not pepper:
            raise ValueError("El pepper no puede estar vacío")
        self._pepper = pepper

    def __repr__(self) -> str:
        return "CredencialesInvitacionHmac(pepper=**********)"

    def token(self) -> bytes:
        return secrets.token_bytes(LARGO_TOKEN)

    def codigo(self) -> str:
        return f"{secrets.randbelow(10_000):04d}"

    def huella_token(self, token: bytes) -> bytes:
        return hashlib.sha256(token).digest()

    def huella_codigo(self, invitacion_id: uuid.UUID, codigo: str) -> bytes:
        return hmac.new(self._pepper, f"invitacion:{invitacion_id}:{codigo}".encode("ascii"), hashlib.sha256).digest()


def huella_de_texto(token: str) -> bytes | None:
    """SHA-256 de los 32 bytes crudos del token del enlace. None si el texto no es un token: responde 410
    invitacion-no-disponible, como un token desconocido (C28)."""
    try:
        crudo = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None
    return hashlib.sha256(crudo).digest() if len(crudo) == LARGO_TOKEN else None
