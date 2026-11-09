"""Fixtures del catálogo (MATU-59): la API con el router del catálogo montado y un catálogo sintético.

El router es capa 3 y crear_app lo monta solo con CAPA3_HABILITADA. Aquí se agrega con rutas_de_prueba, igual que
lo haría incluir_capa_3, para no depender de la variable. El catálogo se siembra como superusuario con nombres y
RUT únicos por prueba y se borra al terminar: la base puede tener otro catálogo (la semilla de la demo), así que
las pruebas miran solo sus propias categorías.
"""

import secrets
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI

from app.modules.catalog.api.router import router as router_catalogo
from tests.base_datos import DSN
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.conftest import EntornoIam
from tests.rut_ficticio import rut_ficticio


@pytest.fixture
def rutas_de_prueba() -> Callable[[FastAPI], None]:
    return lambda app: app.include_router(router_catalogo, prefix="/v1")


@dataclass
class CatalogoSintetico:
    sufijo: str
    categorias: dict[str, uuid.UUID] = field(default_factory=dict)
    productos: dict[str, uuid.UUID] = field(default_factory=dict)
    comercios: dict[str, uuid.UUID] = field(default_factory=dict)
    ofertas: dict[tuple[str, str], uuid.UUID] = field(default_factory=dict)
    # Lo que nunca debe salir en la respuesta
    privados: list[str] = field(default_factory=list)


def _insertar(cx: psycopg.Connection, sql: str, parametros: tuple[Any, ...]) -> uuid.UUID:
    fila = cx.execute(sql, parametros).fetchone()
    assert fila is not None
    return uuid.UUID(str(fila[0]))


def _sembrar(cx: psycopg.Connection, catalogo: CatalogoSintetico) -> None:
    s = catalogo.sufijo
    for clave, orden, activa in (("higiene", 1, True), ("piel", 2, True), ("inactiva", 0, False)):
        catalogo.categorias[clave] = _insertar(
            cx,
            "INSERT INTO categoria_cuidado (nombre, orden, activa) VALUES (%s, %s, %s) RETURNING id",
            (f"Categoría {clave} {s}", orden, activa),
        )
    productos = (
        # clave, categoría, retracto, activo, requiere receta
        ("panal", "higiene", True, True, False),
        ("bolsa", "higiene", False, True, False),
        ("crema", "piel", True, True, False),
        ("no_publicado", "higiene", True, True, False),
        ("solo_suspendido", "higiene", True, True, False),
        ("sin_ofertas", "higiene", True, True, False),
        ("inactivo", "higiene", True, False, False),
        ("de_inactiva", "inactiva", True, True, False),
        ("con_receta", "higiene", True, True, True),
    )
    for clave, categoria, retracto, activo, receta in productos:
        catalogo.productos[clave] = _insertar(
            cx,
            "INSERT INTO producto (categoria_id, nombre, marca, presentacion, unidad, unidades_por_envase,"
            " retracto_pierde_al_abrir, activo, requiere_receta)"
            " VALUES (%s, %s, 'Marca de ejemplo', %s, 'unidad', 30, %s, %s, %s) RETURNING id",
            (catalogo.categorias[categoria], f"Producto {clave} {s}", "Paquete de 30 unidades", retracto, activo,
             receta),
        )
    comercios = (("uno", "Almacén El Ejemplo", "activo"), ("dos", "Bodega La Muestra", "activo"),
                 ("suspendido", "Comercio Suspendido", "suspendido"))
    for i, (clave, fantasia, estado) in enumerate(comercios):
        razon, rut = f"Razón social secreta {clave} {s}", rut_ficticio(f"7{5 + i}{s}")
        direccion, telefono = f"Calle de Prueba {i} {s}", f"+56 2 5555 0{s[:3]}"
        catalogo.comercios[clave] = _insertar(
            cx,
            "INSERT INTO comercio (razon_social, nombre_fantasia, rut, direccion, comuna, telefono, estado)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (razon, f"{fantasia} {s}", rut, direccion, f"Comuna {s}", telefono, estado),
        )
        catalogo.privados += [razon, rut, direccion, telefono, f"Comuna {s}"]
    ofertas = (
        ("panal", "uno", 12990, 24, True),
        ("panal", "dos", 9990, 0, True),
        ("bolsa", "uno", 15990, 0, True),
        ("bolsa", "dos", 16490, 0, True),
        ("crema", "dos", 7290, 10, True),
        ("no_publicado", "uno", 1990, 5, False),
        ("solo_suspendido", "suspendido", 2990, 5, True),
        ("inactivo", "uno", 3990, 5, True),
        ("de_inactiva", "uno", 4990, 5, True),
        # Publicado, con stock y de un comercio activo, pero requiere receta (decisión 171)
        ("con_receta", "uno", 5990, 5, True),
    )
    for producto, comercio, precio, stock, disponible in ofertas:
        catalogo.ofertas[(producto, comercio)] = _insertar(
            cx,
            "INSERT INTO oferta (producto_id, comercio_id, precio, stock, disponible) VALUES (%s, %s, %s, %s, %s)"
            " RETURNING id",
            (catalogo.productos[producto], catalogo.comercios[comercio], precio, stock, disponible),
        )


def _borrar(cx: psycopg.Connection, catalogo: CatalogoSintetico) -> None:
    cx.execute("DELETE FROM oferta WHERE id = ANY(%s)", (list(catalogo.ofertas.values()),))
    cx.execute("DELETE FROM producto WHERE id = ANY(%s)", (list(catalogo.productos.values()),))
    cx.execute("DELETE FROM comercio WHERE id = ANY(%s)", (list(catalogo.comercios.values()),))
    cx.execute("DELETE FROM categoria_cuidado WHERE id = ANY(%s)", (list(catalogo.categorias.values()),))


@pytest.fixture
def catalogo_sintetico() -> Iterator[CatalogoSintetico]:
    catalogo = CatalogoSintetico(sufijo=f"{secrets.randbelow(10**6):06d}")
    with psycopg.connect(DSN, autocommit=True) as cx:
        try:
            _sembrar(cx, catalogo)
            yield catalogo
        finally:
            _borrar(cx, catalogo)


@dataclass
class EntornoCatalogo:
    iam: EntornoIam
    fabrica: Fabrica
    tokens: dict[uuid.UUID, str] = field(default_factory=dict)

    def token(self, usuario: UsuarioCreado) -> str:
        if usuario.id not in self.tokens:
            assert usuario.contrasena is not None
            respuesta = self.iam.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
            assert respuesta.status_code == 200, respuesta.text
            self.tokens[usuario.id] = respuesta.json()["access_token"]
        return self.tokens[usuario.id]

    def ver(self, usuario: UsuarioCreado | None = None, **cabeceras: str) -> Any:
        if usuario is not None:
            cabeceras["Authorization"] = f"Bearer {self.token(usuario)}"
        return self.iam.cliente.get("/v1/catalogo", headers=cabeceras)

    def familia(self) -> FamiliaCreada:
        return self.fabrica.familia()


@pytest.fixture
def entorno_catalogo(entorno_iam: EntornoIam) -> Iterator[EntornoCatalogo]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    try:
        yield EntornoCatalogo(iam=entorno_iam, fabrica=fabrica)
    finally:
        fabrica.limpiar()
