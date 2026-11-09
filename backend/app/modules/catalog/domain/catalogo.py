"""La vista del catálogo (MATU-59, RF-20, decisiones 158 a 165 de docs/api/README.md).

El catálogo es general: no lleva grupo, persona ni nada de quien lo mira, y no se cruza con el consumo
(condición 3 del analista). Se arma desde las ofertas publicadas, una fila por oferta (FilaOferta), con reglas
puras y sin I/O:

- Entra un producto si tiene al menos una oferta publicada de un comercio activo. El precio sale siempre de una
  oferta real (condición 1a): un producto sin oferta no se muestra, y una categoría sin productos tampoco.
- Del comercio solo viaja su nombre de fantasía. Nunca su razón social, RUT, dirección, comuna ni teléfono.
- De la cantidad en stock solo sale si hay, como disponible (decisión 161): no se promete disponibilidad ni se expone el
  inventario del comercio. Lo que hay se confirma antes de pagar.
- Orden estable: categorías por su orden y nombre; productos por nombre, presentación e id; comercios de cada
  producto por nombre de fantasía e id, nunca por precio, para no recomendar el más barato (D6, N4 del diseñador).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

# Las unidades del CHECK de producto.unidad (0001)
Unidad = Literal["unidad", "sobre", "ml", "g"]


class PrecioInvalido(ValueError):
    """Una oferta con precio no positivo. La base lo impide (CHECK oferta_precio_check): si llega, es un error."""


@dataclass(frozen=True)
class FilaOferta:
    """Una oferta publicada con su producto, su categoría y el nombre de fantasía del comercio."""

    categoria_id: uuid.UUID
    categoria_nombre: str
    categoria_orden: int
    producto_id: uuid.UUID
    producto_nombre: str
    presentacion: str
    unidad: Unidad
    unidades_por_envase: int
    retracto_pierde_al_abrir: bool
    oferta_id: uuid.UUID
    comercio_id: uuid.UUID
    nombre_fantasia: str
    precio: int
    stock: int


@dataclass(frozen=True)
class OfertaVista:
    oferta_id: uuid.UUID
    comercio_id: uuid.UUID
    nombre_fantasia: str
    # Pesos enteros con IVA (ADR-027)
    precio: int
    disponible: bool


@dataclass(frozen=True)
class ProductoVista:
    id: uuid.UUID
    nombre: str
    presentacion: str
    unidad: Unidad
    unidades_por_envase: int
    retracto_pierde_al_abrir: bool
    comercios: tuple[OfertaVista, ...]


@dataclass(frozen=True)
class CategoriaVista:
    id: uuid.UUID
    nombre: str
    orden: int
    productos: tuple[ProductoVista, ...]


@dataclass(frozen=True)
class Catalogo:
    # true mientras el adaptador de CatalogoComercio sea simulado (arquitectura 9.4): la pantalla lo rotula
    precios_de_ejemplo: bool
    categorias: tuple[CategoriaVista, ...]


def hay_stock(stock: int) -> bool:
    return stock > 0


def _oferta(fila: FilaOferta) -> OfertaVista:
    if fila.precio <= 0:
        raise PrecioInvalido("una oferta del catálogo tiene precio no positivo")
    return OfertaVista(
        oferta_id=fila.oferta_id,
        comercio_id=fila.comercio_id,
        nombre_fantasia=fila.nombre_fantasia,
        precio=fila.precio,
        disponible=hay_stock(fila.stock),
    )


def armar_catalogo(filas: Iterable[FilaOferta], *, precios_de_ejemplo: bool) -> Catalogo:
    """Agrupa las ofertas por categoría y producto, en el orden de la decisión 162."""
    categorias: dict[uuid.UUID, tuple[int, str]] = {}
    productos: dict[uuid.UUID, FilaOferta] = {}
    ofertas: dict[uuid.UUID, list[OfertaVista]] = {}
    for fila in filas:
        categorias[fila.categoria_id] = (fila.categoria_orden, fila.categoria_nombre)
        productos.setdefault(fila.producto_id, fila)
        ofertas.setdefault(fila.producto_id, []).append(_oferta(fila))

    def producto(fila: FilaOferta) -> ProductoVista:
        comercios = sorted(ofertas[fila.producto_id], key=lambda o: (o.nombre_fantasia, str(o.comercio_id)))
        return ProductoVista(
            id=fila.producto_id,
            nombre=fila.producto_nombre,
            presentacion=fila.presentacion,
            unidad=fila.unidad,
            unidades_por_envase=fila.unidades_por_envase,
            retracto_pierde_al_abrir=fila.retracto_pierde_al_abrir,
            comercios=tuple(comercios),
        )

    vistas: list[CategoriaVista] = []
    for categoria_id, (orden, nombre) in sorted(categorias.items(), key=lambda c: (c[1][0], c[1][1], str(c[0]))):
        suyos = sorted(
            (f for f in productos.values() if f.categoria_id == categoria_id),
            key=lambda f: (f.producto_nombre, f.presentacion, str(f.producto_id)),
        )
        vistas.append(
            CategoriaVista(id=categoria_id, nombre=nombre, orden=orden, productos=tuple(producto(f) for f in suyos))
        )
    return Catalogo(precios_de_ejemplo=precios_de_ejemplo, categorias=tuple(vistas))
