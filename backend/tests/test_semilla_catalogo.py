"""MATU-59 · La semilla del catálogo (infra/semillas/catalogo_demo.py): los datos de D2, D3 y D5, idempotente,
como matu_app con app.rol = 'operacion', y legible por GET /v1/catalogo.

Las pruebas sin base revisan los datos de la semilla. Las que tocan la base siembran una copia con nombres y RUT
únicos, para no pisar una semilla de verdad en la base local, y la borran al terminar como superusuario.
"""

import importlib.util
import re
import sys
import uuid
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import psycopg
import pytest

from app.core.db import fabrica_sesiones
from app.modules.catalog.application.catalogo import leer_catalogo
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado
from app.modules.catalog.infrastructure.repositorio_catalogo import RepositorioCatalogoSQL
from tests.base_datos import DSN, requiere_base
from tests.rut_ficticio import modulo_11, rut_ficticio

RUTA_SEMILLA = Path(__file__).resolve().parents[2] / "infra" / "semillas" / "catalogo_demo.py"

pytestmark = pytest.mark.rf("RF-20")


def _cargar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("semilla_catalogo_demo", RUTA_SEMILLA)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


semilla = _cargar()
CATALOGO = semilla.CATALOGO

NOMBRES_D3 = {
    "Pañal adulto M x30", "Toallitas húmedas x80", "Protectores diarios x20", "Crema protectora de la piel 100 g",
    "Suplemento nutricional en polvo 400 g", "Bolsa colectora x10",
}
# lenguaje.md 3.2 y D3: sin términos clínicos ni afirmaciones de salud
PROHIBIDOS = ("escara", "úlcera", "ulcera", "antiescara", "ostom", "incontinencia", "previene", "cura", "diabét")


# --- Los datos, sin base ---------------------------------------------------------------------------------


def test_los_seis_productos_de_d3_en_sus_categorias() -> None:
    assert {p.nombre for p in CATALOGO.productos} == NOMBRES_D3
    assert [(c.nombre, c.orden) for c in CATALOGO.categorias] == [
        ("Higiene y cuidado personal", 1), ("Cuidado de la piel", 2), ("Alimentación", 3),
    ]
    categoria = {p.nombre: p.categoria for p in CATALOGO.productos}
    assert categoria["Crema protectora de la piel 100 g"] == "Cuidado de la piel"
    assert categoria["Suplemento nutricional en polvo 400 g"] == "Alimentación"
    assert {n for n, c in categoria.items() if c == "Higiene y cuidado personal"} == {
        "Pañal adulto M x30", "Toallitas húmedas x80", "Protectores diarios x20", "Bolsa colectora x10",
    }
    # D3 de Jorge (08-11): la bolsa colectora va en «Higiene y cuidado personal», sin categoría propia, porque esa
    # categoría nombraría una condición de salud (lenguaje.md, sección 3.1)
    assert categoria["Bolsa colectora x10"] == "Higiene y cuidado personal"
    assert not any("colectora" in c.nombre.lower() or "ostom" in c.nombre.lower() for c in CATALOGO.categorias)


def test_nombre_y_presentacion_no_se_repiten_ni_usan_terminos_prohibidos() -> None:
    for producto in CATALOGO.productos:
        assert producto.presentacion != producto.nombre
        assert producto.presentacion not in producto.nombre
        texto = f"{producto.nombre} {producto.presentacion}".lower()
        assert not any(p in texto for p in PROHIBIDOS), producto.nombre


def test_retracto_segun_d2() -> None:
    retracto = {p.nombre: p.retracto_pierde_al_abrir for p in CATALOGO.productos}

    assert {n for n, pierde in retracto.items() if not pierde} == {
        "Suplemento nutricional en polvo 400 g", "Bolsa colectora x10",
    }


def test_los_rut_de_prueba_nunca_pasan_el_modulo_11() -> None:
    # Dos RUT válidos conocidos: el cálculo es el del módulo 11
    assert modulo_11("76123456") == "0"
    assert modulo_11("11111111") == "1"
    # El dígito forzado nunca es el correcto, también cuando el correcto es K o 0
    correctos = set()
    for n in range(70_000_000, 70_000_400):
        numero = str(n)
        correctos.add(modulo_11(numero))
        rut = rut_ficticio(numero)
        cuerpo, dv = rut.split("-")
        assert cuerpo.replace(".", "") == numero and re.fullmatch(r"\d{2}\.\d{3}\.\d{3}", cuerpo), rut
        assert dv != modulo_11(numero), rut
    assert correctos == set("0123456789K")


def test_comercios_ficticios_con_rut_que_no_pasa_el_modulo_11() -> None:
    assert len(CATALOGO.comercios) == 2
    for comercio in CATALOGO.comercios:
        numero, dv = comercio.rut.replace(".", "").split("-")
        assert modulo_11(numero) != dv, comercio.rut
        assert "(ficticio)" in comercio.razon_social
        assert comercio.direccion.startswith("Calle de Prueba")
        assert comercio.telefono is None or "5555" in comercio.telefono
        assert "Aromos" not in comercio.nombre_fantasia


def test_precios_enteros_y_stock_distinto_en_cada_comercio() -> None:
    assert {(o.producto, o.comercio) for o in CATALOGO.ofertas} == {
        (p.clave, c.clave) for p in CATALOGO.productos for c in CATALOGO.comercios
    }
    for oferta in CATALOGO.ofertas:
        assert isinstance(oferta.precio, int) and oferta.precio > 0
        assert isinstance(oferta.stock, int) and oferta.stock >= 0
    stock: dict[str, dict[str, int]] = {}
    for oferta in CATALOGO.ofertas:
        stock.setdefault(oferta.producto, {})[oferta.comercio] = oferta.stock
    # Al menos uno sin stock en un comercio y con stock en el otro, y uno sin stock en ninguno
    assert any(min(s.values()) == 0 < max(s.values()) for s in stock.values())
    assert any(max(s.values()) == 0 for s in stock.values())


# --- En la base ---------------------------------------------------------------------------------------------


def _unica() -> Any:
    sufijo = uuid.uuid4().hex[:6]
    digitos = str(int(sufijo, 16) % 10**6).zfill(6)
    categorias = tuple(replace(c, nombre=f"{c.nombre} {sufijo}") for c in CATALOGO.categorias)
    productos = tuple(
        replace(p, nombre=f"{p.nombre} {sufijo}", categoria=f"{p.categoria} {sufijo}") for p in CATALOGO.productos
    )
    comercios = tuple(
        replace(c, nombre_fantasia=f"{c.nombre_fantasia} {sufijo}", rut=rut_ficticio(f"7{i}{digitos}"))
        for i, c in enumerate(CATALOGO.comercios)
    )
    return replace(CATALOGO, categorias=categorias, productos=productos, comercios=comercios)


@pytest.fixture
def copia() -> Iterator[tuple[Any, list[Any]]]:
    sembrados: list[Any] = []
    yield _unica(), sembrados
    with psycopg.connect(DSN, autocommit=True) as cx:
        for s in sembrados:
            cx.execute("DELETE FROM oferta WHERE id = ANY(%s)", (list(s.ofertas.values()),))
            cx.execute("DELETE FROM producto WHERE id = ANY(%s)", (list(s.productos.values()),))
            cx.execute("DELETE FROM comercio WHERE id = ANY(%s)", (list(s.comercios.values()),))
            cx.execute("DELETE FROM categoria_cuidado WHERE id = ANY(%s)", (list(s.categorias.values()),))


@requiere_base
def test_siembra_y_es_idempotente(copia: tuple[Any, list[Any]]) -> None:
    catalogo, sembrados = copia
    primero = semilla.sembrar_catalogo(fabrica_sesiones(), catalogo)
    sembrados.append(primero)
    # Alguien cambió el stock entretanto: la semilla lo devuelve a su valor
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE oferta SET stock = 999 WHERE id = ANY(%s)", (list(primero.ofertas.values()),))

    segundo = semilla.sembrar_catalogo(fabrica_sesiones(), catalogo)

    assert segundo == primero
    with psycopg.connect(DSN) as cx:
        assert cx.execute("SELECT count(*) FROM oferta WHERE id = ANY(%s)",
                          (list(primero.ofertas.values()),)).fetchone() == (12,)
        filas = cx.execute(
            "SELECT p.nombre, o.precio, o.stock, p.marca, p.retracto_pierde_al_abrir FROM oferta o"
            " JOIN producto p ON p.id = o.producto_id WHERE o.id = ANY(%s)", (list(primero.ofertas.values()),)
        ).fetchall()
    assert {f[2] for f in filas} != {999}
    assert {f[3] for f in filas} == {None}
    assert sorted((f[1], f[2]) for f in filas) == sorted((o.precio, o.stock) for o in CATALOGO.ofertas)


@requiere_base
def test_lo_sembrado_se_lee_desde_el_catalogo(copia: tuple[Any, list[Any]]) -> None:
    from app.core.db import sesion_tenant

    catalogo, sembrados = copia
    sembrado = semilla.sembrar_catalogo(fabrica_sesiones(), catalogo)
    sembrados.append(sembrado)

    with sesion_tenant(fabrica_sesiones(), usuario_id=uuid.uuid4()) as sesion:
        vista = leer_catalogo(RepositorioCatalogoSQL(sesion), CatalogoComercioSimulado())

    mias = [c for c in vista.categorias if c.id in set(sembrado.categorias.values())]
    assert [re.sub(r" \w{6}$", "", c.nombre) for c in mias] == [
        "Higiene y cuidado personal", "Cuidado de la piel", "Alimentación",
    ]
    assert sum(len(p.comercios) for c in mias for p in c.productos) == 12
    assert any(not o.disponible for c in mias for p in c.productos for o in p.comercios)
