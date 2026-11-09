"""MATU · Semilla del catálogo curado (MATU-59, decisión 170 de docs/api/README.md).

Siembra en la base LOCAL el catálogo de la demo, todo sintético:

- Tres categorías: «Higiene y cuidado personal», «Cuidado de la piel» y «Alimentación» (D3 de Jorge). La bolsa
  colectora va en «Higiene y cuidado personal», sin categoría propia: una para ella nombraría una condición de
  salud (lenguaje.md, sección 3.1).
- Los seis productos de las entrevistas, con los nombres de D3. nombre es el texto de D3 y presentacion dice cómo
  viene (N3 del diseñador), para que la tarjeta no repita lo mismo. Sin marca (D5: ninguna marca real) y sin
  afirmaciones de salud. retracto_pierde_al_abrir según D2: true en pañales, toallitas, protectores y crema;
  false en el suplemento y las bolsas.
- Dos comercios ficticios (D5), con nombres inventados, dirección «Calle de Prueba», teléfono de la serie 5555 y
  un RUT con dígito verificador incorrecto a propósito: no pasa el módulo 11, así que no es el de nadie. Nunca se
  muestra (la API expone solo nombre_fantasia).
- Una oferta por producto en cada comercio, con precios de ejemplo en pesos enteros con IVA y un stock distinto
  en cada uno: hay productos sin stock en un comercio y con stock en el otro, y uno sin stock en ninguno.

Sin convenio: la consulta del catálogo no lo necesita y el convenio sería solo de simulación (D5). Llega con el
pedido (MATU-61) si hace falta.

Escribe como matu_app con app.rol = 'operacion' (las políticas *_operacion de 0001), nunca como dueño ni
superusuario. Es idempotente y reproducible: categoría por nombre, comercio por RUT, producto por un id fijo
(uuid5 de su nombre y presentación) y oferta por (producto, comercio). Correrla otra vez deja los mismos precios
y stock de esta lista.

Desde la raíz del repositorio, con el entorno virtual de backend/ activo:

    python infra/semillas/catalogo_demo.py

Lo corre también infra/semillas/demo.py al final. Se niega a correr con ENTORNO=produccion o si DATABASE_URL no
entra como matu_app, sin mostrar la URL.
"""

import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import obtener_configuracion  # noqa: E402
from app.core.db import fabrica_sesiones, sesion_tenant  # noqa: E402

ROL_ESPERADO = "matu_app"

# Espacio de nombres fijo de los ids de producto de la semilla: el mismo nombre da el mismo id en cada corrida
ESPACIO_IDS = uuid.UUID("5e3c59a0-0059-4a7e-9c00-000000000059")


@dataclass(frozen=True)
class CategoriaSemilla:
    nombre: str
    orden: int


@dataclass(frozen=True)
class ProductoSemilla:
    clave: str
    categoria: str
    nombre: str
    presentacion: str
    unidad: str
    unidades_por_envase: int
    retracto_pierde_al_abrir: bool


@dataclass(frozen=True)
class ComercioSemilla:
    clave: str
    razon_social: str
    nombre_fantasia: str
    rut: str
    direccion: str
    comuna: str
    telefono: str | None


@dataclass(frozen=True)
class OfertaSemilla:
    producto: str
    comercio: str
    precio: int
    stock: int


@dataclass(frozen=True)
class CatalogoSemilla:
    categorias: tuple[CategoriaSemilla, ...]
    productos: tuple[ProductoSemilla, ...]
    comercios: tuple[ComercioSemilla, ...]
    ofertas: tuple[OfertaSemilla, ...]


HIGIENE, PIEL, ALIMENTACION = "Higiene y cuidado personal", "Cuidado de la piel", "Alimentación"

CATALOGO = CatalogoSemilla(
    categorias=(CategoriaSemilla(HIGIENE, 1), CategoriaSemilla(PIEL, 2), CategoriaSemilla(ALIMENTACION, 3)),
    productos=(
        ProductoSemilla("panal", HIGIENE, "Pañal adulto M x30", "Paquete de 30 unidades", "unidad", 30, True),
        ProductoSemilla("toallitas", HIGIENE, "Toallitas húmedas x80", "Paquete de 80 unidades", "unidad", 80, True),
        ProductoSemilla("protectores", HIGIENE, "Protectores diarios x20", "Caja de 20 unidades", "unidad", 20, True),
        ProductoSemilla("bolsa", HIGIENE, "Bolsa colectora x10", "Caja de 10 unidades", "unidad", 10, False),
        ProductoSemilla("crema", PIEL, "Crema protectora de la piel 100 g", "Pote de 100 g", "g", 100, True),
        ProductoSemilla(
            "suplemento", ALIMENTACION, "Suplemento nutricional en polvo 400 g", "Tarro de 400 g", "g", 400, False
        ),
    ),
    comercios=(
        # RUT con dígito verificador incorrecto a propósito: el de 77.777.701 es 7, no 8. No pasa el módulo 11
        ComercioSemilla(
            "uno", "Comercio de Prueba Uno (ficticio)", "Almacén El Ejemplo", "77.777.701-8",
            "Calle de Prueba 100", "Ñuñoa", "+56 2 5555 0101",
        ),
        # Igual: el dígito verificador de 77.777.702 es 5, no 6
        ComercioSemilla(
            "dos", "Comercio de Prueba Dos (ficticio)", "Bodega La Muestra", "77.777.702-6",
            "Calle de Prueba 200", "La Reina", "+56 2 5555 0102",
        ),
    ),
    ofertas=(
        OfertaSemilla("panal", "uno", 12990, 24),
        OfertaSemilla("panal", "dos", 13490, 0),
        OfertaSemilla("toallitas", "uno", 4590, 0),
        OfertaSemilla("toallitas", "dos", 4290, 30),
        OfertaSemilla("protectores", "uno", 3290, 12),
        OfertaSemilla("protectores", "dos", 3490, 6),
        OfertaSemilla("bolsa", "uno", 15990, 0),
        OfertaSemilla("bolsa", "dos", 16490, 0),
        OfertaSemilla("crema", "uno", 6990, 0),
        OfertaSemilla("crema", "dos", 7290, 10),
        OfertaSemilla("suplemento", "uno", 18990, 8),
        OfertaSemilla("suplemento", "dos", 17990, 4),
    ),
)


@dataclass(frozen=True)
class CatalogoSembrado:
    categorias: dict[str, uuid.UUID]
    productos: dict[str, uuid.UUID]
    comercios: dict[str, uuid.UUID]
    ofertas: dict[tuple[str, str], uuid.UUID]


def id_producto(producto: ProductoSemilla) -> uuid.UUID:
    return uuid.uuid5(ESPACIO_IDS, f"producto:{producto.nombre}:{producto.presentacion}")


_CATEGORIA = text(
    "INSERT INTO categoria_cuidado (nombre, orden, activa) VALUES (:nombre, :orden, true)"
    " ON CONFLICT (nombre) DO UPDATE SET orden = EXCLUDED.orden, activa = true RETURNING id"
)
_PRODUCTO = text(
    "INSERT INTO producto (id, categoria_id, nombre, marca, presentacion, unidad, unidades_por_envase,"
    " retracto_pierde_al_abrir, activo)"
    " VALUES (:id, :categoria_id, :nombre, NULL, :presentacion, :unidad, :unidades_por_envase, :retracto, true)"
    " ON CONFLICT (id) DO UPDATE SET categoria_id = EXCLUDED.categoria_id, nombre = EXCLUDED.nombre, marca = NULL,"
    " presentacion = EXCLUDED.presentacion, unidad = EXCLUDED.unidad,"
    " unidades_por_envase = EXCLUDED.unidades_por_envase,"
    " retracto_pierde_al_abrir = EXCLUDED.retracto_pierde_al_abrir, activo = true RETURNING id"
)
_COMERCIO = text(
    "INSERT INTO comercio (razon_social, nombre_fantasia, rut, direccion, comuna, telefono, estado)"
    " VALUES (:razon_social, :nombre_fantasia, :rut, :direccion, :comuna, :telefono, 'activo')"
    " ON CONFLICT (rut) DO UPDATE SET razon_social = EXCLUDED.razon_social,"
    " nombre_fantasia = EXCLUDED.nombre_fantasia, direccion = EXCLUDED.direccion, comuna = EXCLUDED.comuna,"
    " telefono = EXCLUDED.telefono, estado = 'activo' RETURNING id"
)
_OFERTA = text(
    "INSERT INTO oferta (producto_id, comercio_id, precio, stock, disponible)"
    " VALUES (:producto_id, :comercio_id, :precio, :stock, true)"
    " ON CONFLICT ON CONSTRAINT oferta_uq DO UPDATE SET precio = EXCLUDED.precio, stock = EXCLUDED.stock,"
    " disponible = true, actualizado_en = now() RETURNING id"
)


def sembrar_catalogo(fabrica: sessionmaker[Session], catalogo: CatalogoSemilla = CATALOGO) -> CatalogoSembrado:
    """Siembra el catálogo en una sola transacción, como matu_app con app.rol = 'operacion'."""
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        categorias = {
            c.nombre: sesion.execute(_CATEGORIA, {"nombre": c.nombre, "orden": c.orden}).scalar_one()
            for c in catalogo.categorias
        }
        productos = {
            p.clave: sesion.execute(
                _PRODUCTO,
                {
                    "id": id_producto(p),
                    "categoria_id": categorias[p.categoria],
                    "nombre": p.nombre,
                    "presentacion": p.presentacion,
                    "unidad": p.unidad,
                    "unidades_por_envase": p.unidades_por_envase,
                    "retracto": p.retracto_pierde_al_abrir,
                },
            ).scalar_one()
            for p in catalogo.productos
        }
        comercios = {
            c.clave: sesion.execute(
                _COMERCIO,
                {
                    "razon_social": c.razon_social,
                    "nombre_fantasia": c.nombre_fantasia,
                    "rut": c.rut,
                    "direccion": c.direccion,
                    "comuna": c.comuna,
                    "telefono": c.telefono,
                },
            ).scalar_one()
            for c in catalogo.comercios
        }
        ofertas = {
            (o.producto, o.comercio): sesion.execute(
                _OFERTA,
                {
                    "producto_id": productos[o.producto],
                    "comercio_id": comercios[o.comercio],
                    "precio": o.precio,
                    "stock": o.stock,
                },
            ).scalar_one()
            for o in catalogo.ofertas
        }
    return CatalogoSembrado(categorias=categorias, productos=productos, comercios=comercios, ofertas=ofertas)


def rol_de_la_conexion(fabrica: sessionmaker[Session]) -> str:
    with fabrica() as sesion:
        return str(sesion.execute(text("SELECT current_user")).scalar_one())


def main() -> int:
    configuracion = obtener_configuracion()
    if configuracion.entorno == "produccion":
        print("La semilla del catálogo no corre con ENTORNO=produccion.", file=sys.stderr)
        return 2
    fabrica = fabrica_sesiones()
    try:
        rol = rol_de_la_conexion(fabrica)
    except SQLAlchemyError:
        print("No se pudo conectar a la base con DATABASE_URL. Revisa que esté levantada y migrada.", file=sys.stderr)
        return 1
    if rol != ROL_ESPERADO:
        print(
            f"La semilla solo corre conectada como {ROL_ESPERADO}, y DATABASE_URL entra como otro rol.",
            file=sys.stderr,
        )
        return 2
    sembrado = sembrar_catalogo(fabrica)
    print(
        f"Catálogo de demostración en la base local (ENTORNO={configuracion.entorno}): "
        f"{len(sembrado.categorias)} categorías, {len(sembrado.productos)} productos, "
        f"{len(sembrado.comercios)} comercios ficticios y {len(sembrado.ofertas)} ofertas con precios de ejemplo."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
