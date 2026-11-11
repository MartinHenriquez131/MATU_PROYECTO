"""La Idempotency-Key de los POST de pedidos (arquitectura 9.1; decisión 195; D5).

- Obligatoria en crear, confirmar, cambiar y cancelar: sin ella, 428 falta-idempotencia. De 16 a 64 caracteres
  [A-Za-z0-9_-]; otro formato, 422.
- Vale 24 horas por grupo y ruta. La misma clave con el mismo cuerpo, de la misma cuenta, devuelve el mismo código y
  el pedido tal como está ahora: se guarda solo el estado HTTP y el id del pedido (D5), nunca el cuerpo.
- La misma clave con otro cuerpo o de otra cuenta del grupo: 422 idempotencia-reutilizada. Mientras la primera no
  termina: 409 idempotencia-en-curso.
- La huella de la petición es la SHA-256 de la ruta y el cuerpo canónico: nunca se guarda el cuerpo, y la clave no
  va a los logs.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

FORMA_CLAVE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
VIGENCIA_CLAVE = timedelta(hours=24)


class ClaveInvalida(ValueError):
    """La clave no tiene la forma pedida (422 en Idempotency-Key)."""


def exigir_forma(clave: str) -> str:
    if not FORMA_CLAVE.match(clave):
        raise ClaveInvalida("la clave va de 16 a 64 caracteres A-Z, a-z, 0-9, _ y -")
    return clave


def huella_peticion(endpoint: str, cuerpo: Any) -> bytes:
    """SHA-256 de la ruta y el cuerpo en JSON canónico (claves ordenadas, sin espacios)."""
    canonico = json.dumps(cuerpo, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(f"{endpoint}\n{canonico}".encode()).digest()


def expira_en(ahora: datetime) -> datetime:
    return ahora + VIGENCIA_CLAVE


@dataclass(frozen=True)
class Registro:
    """Una fila de idempotencia: quién la usó, con qué petición, y cómo terminó (None si no terminó)."""

    usuario_id: uuid.UUID
    huella: bytes
    estado_http: int | None
    pedido_id: uuid.UUID | None
    expira_en: datetime


class Decision(StrEnum):
    NUEVA = "nueva"
    REPETIDA = "repetida"
    EN_CURSO = "en_curso"
    REUTILIZADA = "reutilizada"


def decidir(existente: Registro | None, usuario_id: uuid.UUID, huella: bytes, ahora: datetime) -> Decision:
    """Qué hacer con una petición según la fila que ya había con la misma clave."""
    if existente is None:
        return Decision.NUEVA
    if existente.usuario_id != usuario_id:
        return Decision.REUTILIZADA
    if existente.expira_en <= ahora:
        return Decision.NUEVA
    if existente.huella != huella:
        return Decision.REUTILIZADA
    if existente.estado_http is None:
        return Decision.EN_CURSO
    return Decision.REPETIDA
