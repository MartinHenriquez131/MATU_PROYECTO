"""La consulta de stock que MATU envía al comercio por el puerto CatalogoComercio (MATU-59, decisión 168).

Condiciones 4.1 a 4.7 del analista (arquitectura 9.5 y 12.5): la consulta lleva **exactamente** sus líneas
(producto y cantidad) y una referencia opaca. Nada de la familia, de la persona cuidada, de quien pide ni de la
dirección o la comuna, y ningún dato de la sesión (token, cookie, IP, User-Agent ni request_id).

La referencia es aleatoria (secrets, 128 bits), nueva en cada consulta: nunca sale de grupo_id ni de pedido_id,
no es correlativa y no lleva fecha. Cuando exista el pedido (MATU-61), será nueva por pedido.

secrets no lee el reloj ni hace I/O: la regla sigue siendo pura.
"""

import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

# 16 bytes aleatorios en base64 url: 22 caracteres
BYTES_REFERENCIA = 16
CANTIDAD_MAXIMA = 10_000
LINEAS_MAXIMAS = 100


class ConsultaInvalida(ValueError):
    """Una consulta sin líneas, con un producto repetido o con una cantidad fuera de rango."""


@dataclass(frozen=True)
class LineaConsulta:
    producto_id: uuid.UUID
    cantidad: int


@dataclass(frozen=True)
class ConsultaStock:
    """Lo único que sale de MATU hacia el comercio. Inmutable, y sin otros campos (condición 4.1)."""

    lineas: tuple[LineaConsulta, ...]
    referencia: str


@dataclass(frozen=True)
class LineaDisponible:
    producto_id: uuid.UUID
    # Cuánto de lo pedido tiene el comercio: de 0 a la cantidad de la línea
    disponible: int


@dataclass(frozen=True)
class RespuestaStock:
    referencia: str
    lineas: tuple[LineaDisponible, ...]


def referencia_nueva() -> str:
    return secrets.token_urlsafe(BYTES_REFERENCIA)


def nueva_consulta(lineas: Iterable[tuple[uuid.UUID, int]]) -> ConsultaStock:
    """Una consulta con sus líneas validadas y una referencia nueva."""
    validas: list[LineaConsulta] = []
    vistos: set[uuid.UUID] = set()
    for producto_id, cantidad in lineas:
        if producto_id in vistos:
            raise ConsultaInvalida("un producto va una sola vez por consulta")
        if isinstance(cantidad, bool) or not 1 <= cantidad <= CANTIDAD_MAXIMA:
            raise ConsultaInvalida(f"la cantidad va de 1 a {CANTIDAD_MAXIMA}")
        vistos.add(producto_id)
        validas.append(LineaConsulta(producto_id=producto_id, cantidad=cantidad))
    if not 1 <= len(validas) <= LINEAS_MAXIMAS:
        raise ConsultaInvalida(f"la consulta lleva de 1 a {LINEAS_MAXIMAS} líneas")
    return ConsultaStock(lineas=tuple(validas), referencia=referencia_nueva())
