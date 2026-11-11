"""MATU-59 · Cómo se arma la vista del catálogo (decisiones 160 a 162). Sin base."""

import dataclasses
import uuid

import pytest

from app.modules.catalog.application.catalogo import leer_catalogo
from app.modules.catalog.domain.catalogo import (
    Catalogo,
    CategoriaVista,
    FilaOferta,
    OfertaVista,
    PrecioInvalido,
    ProductoVista,
    armar_catalogo,
)
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado

pytestmark = pytest.mark.rf("RF-20")

HIGIENE, ALIMENTACION = uuid.UUID(int=0xC1), uuid.UUID(int=0xC2)
PANAL, TOALLITAS, SUPLEMENTO = uuid.UUID(int=0xF1), uuid.UUID(int=0xF2), uuid.UUID(int=0xF3)
UNO, DOS = uuid.UUID(int=0xA1), uuid.UUID(int=0xA2)


def _fila(categoria: uuid.UUID, producto: uuid.UUID, comercio: uuid.UUID, precio: int, stock: int) -> FilaOferta:
    nombres = {PANAL: "Pañal adulto M x30", TOALLITAS: "Toallitas húmedas x80", SUPLEMENTO: "Suplemento x400"}
    return FilaOferta(
        categoria_id=categoria,
        categoria_nombre="Higiene y cuidado personal" if categoria == HIGIENE else "Alimentación",
        categoria_orden=1 if categoria == HIGIENE else 3,
        producto_id=producto,
        producto_nombre=nombres[producto],
        presentacion="Paquete",
        unidad="unidad",
        unidades_por_envase=30,
        retracto_pierde_al_abrir=producto != SUPLEMENTO,
        oferta_id=uuid.uuid5(producto, str(comercio)),
        comercio_id=comercio,
        nombre_fantasia="Almacén El Ejemplo" if comercio == UNO else "Bodega La Muestra",
        precio=precio,
        stock=stock,
    )


FILAS = [
    _fila(ALIMENTACION, SUPLEMENTO, UNO, 18990, 8),
    _fila(HIGIENE, TOALLITAS, DOS, 4290, 30),
    # Bodega La Muestra es más barata y aun así va después de Almacén El Ejemplo: el orden no recomienda
    _fila(HIGIENE, PANAL, DOS, 9990, 0),
    _fila(HIGIENE, PANAL, UNO, 12990, 24),
    _fila(HIGIENE, TOALLITAS, UNO, 4590, 0),
]


def test_agrupa_por_categoria_en_su_orden_y_productos_por_nombre() -> None:
    catalogo = armar_catalogo(FILAS, precios_de_ejemplo=True)

    assert [(c.nombre, c.orden) for c in catalogo.categorias] == [
        ("Higiene y cuidado personal", 1),
        ("Alimentación", 3),
    ]
    assert [p.nombre for p in catalogo.categorias[0].productos] == ["Pañal adulto M x30", "Toallitas húmedas x80"]
    assert catalogo.precios_de_ejemplo is True


def test_cada_comercio_con_su_precio_por_nombre_de_fantasia_nunca_por_precio() -> None:
    panal = armar_catalogo(FILAS, precios_de_ejemplo=True).categorias[0].productos[0]

    assert [(o.nombre_fantasia, o.precio, o.disponible) for o in panal.comercios] == [
        ("Almacén El Ejemplo", 12990, True),
        ("Bodega La Muestra", 9990, False),
    ]


def test_el_stock_sale_solo_como_disponible() -> None:
    catalogo = armar_catalogo(FILAS, precios_de_ejemplo=True)
    ofertas = [o for c in catalogo.categorias for p in c.productos for o in p.comercios]

    assert [f.name for f in dataclasses.fields(OfertaVista)] == [
        "oferta_id", "comercio_id", "nombre_fantasia", "precio", "disponible", "ficticio",
    ]
    assert {o.disponible for o in ofertas} == {True, False}


def test_la_vista_no_trae_datos_del_comercio_ni_marca() -> None:
    campos = {
        f.name
        for clase in (Catalogo, CategoriaVista, ProductoVista, OfertaVista)
        for f in dataclasses.fields(clase)
    }
    assert campos.isdisjoint({"marca", "razon_social", "rut", "direccion", "telefono", "comuna", "stock"})


def test_sin_ofertas_no_hay_productos_ni_categorias() -> None:
    assert armar_catalogo([], precios_de_ejemplo=False) == Catalogo(precios_de_ejemplo=False, categorias=())


def test_el_retracto_viene_del_producto() -> None:
    catalogo = armar_catalogo(FILAS, precios_de_ejemplo=True)
    retracto = {p.nombre: p.retracto_pierde_al_abrir for c in catalogo.categorias for p in c.productos}

    assert retracto == {"Pañal adulto M x30": True, "Toallitas húmedas x80": True, "Suplemento x400": False}


@pytest.mark.parametrize("precio", [0, -1])
def test_un_precio_no_positivo_es_un_error(precio: int) -> None:
    with pytest.raises(PrecioInvalido):
        armar_catalogo([_fila(HIGIENE, PANAL, UNO, precio, 1)], precios_de_ejemplo=True)


def test_leer_catalogo_marca_los_precios_de_ejemplo_del_adaptador() -> None:
    class Repositorio:
        def ofertas_publicadas(self) -> list[FilaOferta]:
            return FILAS

    catalogo = leer_catalogo(Repositorio(), CatalogoComercioSimulado())

    assert catalogo.precios_de_ejemplo is True
    assert len(catalogo.categorias) == 2
