"""El token y el PIN del acceso de relevo, y sus huellas (MATU-18, RF-05).

- Token: ``secrets.token_bytes(32)``, 256 bits. Se guarda su SHA-256 sobre los 32 bytes crudos (no
  sobre el texto base64url): el canje de MATU-19 decodifica el texto del fragmento y calcula lo mismo.
- PIN: 4 dígitos con ``secrets.randbelow``. Se guarda HMAC-SHA-256(PEPPER_PIN, "<acceso_id>:<pin>") en
  hexadecimal. El pepper vive en .env (contrato, notas para implementar): una copia de la base sola no
  basta para recuperar el PIN por fuerza bruta. Ligarlo al acceso hace que dos accesos con el mismo PIN
  tengan huellas distintas. La comparación del canje (MATU-19) va con ``hmac.compare_digest``.

Ninguna clase guarda el token ni el PIN, y el pepper no aparece en el repr.
"""

import hashlib
import hmac
import secrets
import uuid

LARGO_TOKEN = 32


class GeneradorSecrets:
    def token(self) -> bytes:
        return secrets.token_bytes(LARGO_TOKEN)

    def pin(self) -> str:
        return f"{secrets.randbelow(10_000):04d}"


class HuellasHmac:
    def __init__(self, pepper: bytes) -> None:
        self._pepper = pepper

    def __repr__(self) -> str:
        return "HuellasHmac(pepper=**********)"

    def huella_token(self, token: bytes) -> bytes:
        return hashlib.sha256(token).digest()

    def huella_pin(self, acceso_id: uuid.UUID, pin: str) -> str:
        return hmac.new(self._pepper, f"{acceso_id}:{pin}".encode("ascii"), hashlib.sha256).hexdigest()
