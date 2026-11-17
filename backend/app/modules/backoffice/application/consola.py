"""Las reglas de la consola de operación que no son SQL (MATU-81).

- ``acciones``: lo que operación puede hacer con un pedido en su estado, con lo que devolvería a la misma tarjeta (P3
  del diseñador, C22). La pantalla no copia la máquina de estados ni calcula montos.
- ``estados_del_filtro``: los grupos de estados de la lista (P4).
- ``nuevo_estado_incidencia``: las reglas del PATCH de una incidencia (C13): una resuelta no cambia, y resolver exige
  la resolución.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.modules.fulfillment.domain.despacho import (
    EN_CAMINO_DESDE,
    ENTREGADO_DESDE,
    NO_ENTREGADO_DESDE,
    EstadoParte,
    LineaDespacho,
    cancelable_despues_de_pagar,
)

# P4: los grupos de la lista. «con_problema» suma los pedidos con una incidencia abierta o una devolución sin terminar
FILTROS: dict[str, tuple[str, ...]] = {
    "por_atender": ("pagado", "enviado_a_comercio", "preparando", "listo_retiro", "retirado", "reprogramado"),
    "en_camino": ("en_ruta",),
    "con_problema": ("no_entregado", "sin_repartidor"),
    "cerrados": ("entregado", "cerrado"),
    "cancelados": ("cancelado_con_devolucion", "cancelado"),
}
FILTRO_POR_OMISION = "por_atender"


@dataclass(frozen=True)
class Filtro:
    estados: tuple[str, ...]
    todos: bool
    con_problema: bool


def estados_del_filtro(grupo: str | None, estados: Iterable[str]) -> Filtro:
    """``grupo`` (uno de FILTROS o «todos») y ``estado`` repetido se suman. Sin ninguno, «por_atender»."""
    pedidos = tuple(estados)
    if grupo is None and not pedidos:
        grupo = FILTRO_POR_OMISION
    if grupo == "todos":
        return Filtro((), True, False)
    del_grupo = FILTROS.get(grupo, ()) if grupo is not None else ()
    return Filtro(tuple(dict.fromkeys((*del_grupo, *pedidos))), False, grupo == "con_problema")


@dataclass(frozen=True)
class Accion:
    accion: str
    monto_a_devolver: int


def faltante_por_devolver(lineas: Sequence[LineaDespacho]) -> int:
    """Lo que falta devolver por los productos que faltaron (D-63-8): unidades × precio, menos lo ya devuelto."""
    return sum(max(0, linea.monto_faltante - linea.monto_devuelto) for linea in lineas)


def acciones(
    estado: str, partes: Sequence[EstadoParte], lineas: Sequence[LineaDespacho], cobrado: int, devuelto: int
) -> list[Accion]:
    """Las acciones de router_operacion (D-63-6, H1 y H2) que el estado permite, en el orden de la pantalla."""
    disponibles: list[Accion] = []
    if estado in EN_CAMINO_DESDE or estado == "no_entregado":
        disponibles.append(Accion("en_camino", 0))
    if estado in ENTREGADO_DESDE:
        disponibles.append(Accion("entregado", faltante_por_devolver(lineas)))
    if estado in NO_ENTREGADO_DESDE:
        disponibles.append(Accion("no_entregado", 0))
    if estado == "no_entregado" or cancelable_despues_de_pagar(estado, partes):
        disponibles.append(Accion("cancelar_con_devolucion", max(0, cobrado - devuelto)))
    return disponibles


class IncidenciaResuelta(Exception):
    """Una incidencia resuelta ya no cambia (409)."""


class FaltaResolucion(Exception):
    """Resolver exige la resolución (422)."""


@dataclass(frozen=True)
class CambioIncidencia:
    estado: str
    resolucion: str | None
    resuelta_en: datetime | None
    resuelve: bool


def nuevo_estado_incidencia(
    actual: str, resolucion_actual: str | None, estado: str | None, resolucion: str | None, ahora: datetime
) -> CambioIncidencia:
    if actual == "resuelta":
        raise IncidenciaResuelta()
    destino = estado or actual
    texto = resolucion if resolucion is not None else resolucion_actual
    if destino == "resuelta" and texto is None:
        raise FaltaResolucion()
    return CambioIncidencia(
        estado=destino,
        resolucion=texto,
        resuelta_en=ahora if destino == "resuelta" else None,
        resuelve=destino == "resuelta",
    )
