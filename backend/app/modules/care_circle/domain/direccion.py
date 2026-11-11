"""Reglas puras de la dirección de entrega de la persona (MATU-61, D4, C6 y C8; decisiones 189 a 191, 216 y 219).

Sin I/O y sin reloj del sistema.

- La cambian y la vacían admin y cuidador. pagador, observador y quien no es del grupo: 404 (C10). No dependen de
  la autorización de pedidos ``despacho`` (C8): es un dato de la persona.
- Precondición obligatoria, como la ficha (MATU-13): ``If-None-Match: *`` la primera vez, ``If-Match`` con el
  ``etag`` después. Sin ninguna, vacía o ``If-Match: *``: 428. Las dos juntas o ``If-None-Match`` distinto de ``*``:
  422. Desactualizada: 412.
- El etag es ``"v<version>"`` de direccion.version.
"""

from dataclasses import dataclass

ROLES_QUE_CAMBIAN_DIRECCION = frozenset({"admin", "cuidador"})


class FaltaPrecondicion(Exception):
    """428 falta-version."""


class PrecondicionInvalida(Exception):
    """422: las dos cabeceras juntas, o If-None-Match distinto de *."""


class DireccionDesactualizada(Exception):
    """412: If-Match no es el vigente, o If-None-Match: * y ya hay una dirección."""


class SinDireccion(LookupError):
    """Vaciar sin dirección: no hay nada que vaciar (404)."""


@dataclass(frozen=True)
class Precondicion:
    if_match: str | None
    if_none_match: str | None


def puede_cambiar_direccion(rol: str) -> bool:
    return rol in ROLES_QUE_CAMBIAN_DIRECCION


def etag_de(version: int) -> str:
    return f'"v{version}"'


def _limpia(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


def exigir_forma_precondicion(pre: Precondicion) -> None:
    """Para PUT, sin mirar la base: 428 sin precondición y 422 con una mal formada."""
    if_match, if_none_match = _limpia(pre.if_match), _limpia(pre.if_none_match)
    if if_none_match is None and (if_match is None or if_match == "*"):
        raise FaltaPrecondicion()
    if if_match is not None and if_none_match is not None:
        raise PrecondicionInvalida()
    if if_none_match is not None and if_none_match != "*":
        raise PrecondicionInvalida()


def exigir_precondicion_guardar(pre: Precondicion, version_actual: int | None) -> None:
    """Para PUT: la cabecera que corresponde según haya o no dirección. Orden: 428, 422 y 412."""
    exigir_forma_precondicion(pre)
    if_match, if_none_match = _limpia(pre.if_match), _limpia(pre.if_none_match)
    if if_none_match is not None:
        if version_actual is not None:
            raise DireccionDesactualizada()
        return
    if version_actual is None or if_match != etag_de(version_actual):
        raise DireccionDesactualizada()


def exigir_precondicion_vaciar(if_match: str | None, version_actual: int | None) -> None:
    """Para DELETE: If-Match obligatorio. Orden: 428, 404 (sin dirección) y 412."""
    valor = _limpia(if_match)
    if valor is None or valor == "*":
        raise FaltaPrecondicion()
    if version_actual is None:
        raise SinDireccion()
    if valor != etag_de(version_actual):
        raise DireccionDesactualizada()
