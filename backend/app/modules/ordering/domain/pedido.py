"""Reglas puras del pedido sin pagar (MATU-61, RF-21, ADR-027; decisiones 194 a 209 y C1 a C9 de Jorge).

- Roles (C3): admin y cuidador arman, ajustan, confirman y cancelan sin pagar; pagador y observador solo leen, y el
  observador no ve la entrega ni el resumen.
- El carrito: cada línea guarda la oferta y el precio del carrito (C15). Un producto va una sola vez. Las cantidades
  van de 1 a 99 envases y el carrito de 0 a 100 líneas (1 a 100 al crearlo).
- Confirmar (C5): cada línea queda en el comercio del carrito si lo tiene. Si no, con ``otro_comercio`` se busca el
  mismo producto en otro comercio que lo tenga, el de menor precio (empate por nombre de fantasía e id); con
  ``quitar``, o si nadie lo tiene, la línea sale. **Nunca otra marca ni otro producto**: solo ofertas del mismo
  producto. Lo que cambió de precio o de comercio contra el carrito se marca.
- Montos (ADR-027, C5): pesos enteros con IVA incluido, sin un IVA que se sume. ``total = subtotal + un envío``, y el
  subtotal es la suma exacta de cantidad × precio de las líneas que quedan.
"""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from app.modules.ordering.domain.estados import VIGENCIA_TOTAL, Estado

ROLES_QUE_ESCRIBEN = frozenset({"admin", "cuidador"})
ROLES_QUE_LEEN = frozenset({"admin", "cuidador", "pagador", "observador"})
ROLES_QUE_VEN_ENTREGA = frozenset({"admin", "cuidador", "pagador"})

CANTIDAD_MAXIMA = 99
LINEAS_MAXIMAS = 100

ESTADO_LINEA_PENDIENTE = "pendiente"
ESTADO_LINEA_SALIO = "sin_stock"


class Regla(StrEnum):
    """RF-21: qué hacer si falta un producto. Nunca otra marca: no existe otra acción."""

    OTRO_COMERCIO = "otro_comercio"
    QUITAR = "quitar"


REGLA_POR_OMISION = Regla.OTRO_COMERCIO


def puede_escribir(rol: str) -> bool:
    return rol in ROLES_QUE_ESCRIBEN


def puede_leer(rol: str) -> bool:
    return rol in ROLES_QUE_LEEN


def ve_entrega(rol: str) -> bool:
    """El observador ve el carrito sin la entrega ni el resumen (C3)."""
    return rol in ROLES_QUE_VEN_ENTREGA


@dataclass(frozen=True)
class Comercio:
    id: uuid.UUID
    nombre_fantasia: str
    ficticio: bool


@dataclass(frozen=True)
class Producto:
    id: uuid.UUID
    nombre: str
    presentacion: str
    unidad: str
    unidades_por_envase: int
    retracto_pierde_al_abrir: bool


@dataclass(frozen=True)
class Oferta:
    """Una oferta publicada: de un comercio activo, de un producto activo sin receta, y disponible en el catálogo."""

    id: uuid.UUID
    producto: Producto
    comercio: Comercio
    # Pesos enteros con IVA incluido (ADR-027)
    precio: int


@dataclass(frozen=True)
class Linea:
    id: uuid.UUID
    producto: Producto
    cantidad: int
    regla: Regla
    # Lo que la familia vio en el carrito (C15)
    oferta_carrito_id: uuid.UUID
    comercio_carrito: Comercio
    precio_carrito: int
    # Lo confirmado: igual al carrito en borrador
    oferta_id: uuid.UUID
    comercio: Comercio
    precio_unitario: int
    salio: bool = False
    # La copia de producto.retracto_pierde_al_abrir al confirmar (C3). None en borrador
    retracto_copiado: bool | None = None
    # MATU-62 (decisión 239): lo devuelto de la línea por una anulación parcial hecha, y lo que se está devolviendo
    monto_devuelto: int = 0
    devuelta_en: datetime | None = None
    devolucion_en_curso: int | None = None

    @property
    def subtotal(self) -> int:
        return self.cantidad * self.precio_unitario

    @property
    def retracto_pierde_al_abrir(self) -> bool:
        return self.producto.retracto_pierde_al_abrir if self.retracto_copiado is None else self.retracto_copiado


@dataclass(frozen=True)
class Cambio:
    """Lo que cambió al confirmar contra el carrito (C15). Al menos uno de los dos no es None."""

    precio_antes: int | None
    comercio_antes: Comercio | None


@dataclass(frozen=True)
class Entrega:
    calle: str
    numero: str
    depto: str | None
    comuna: str
    region: str
    referencia: str | None
    telefono: str
    # celular_cuenta (el celular verificado de quien confirmó) o escrito (decisión 203)
    telefono_origen: str


@dataclass(frozen=True)
class Pedido:
    id: uuid.UUID
    grupo_id: uuid.UUID
    persona_id: uuid.UUID
    estado: Estado
    version: int
    costo_envio: int
    total_confirmado_en: datetime | None
    total_vence_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime
    lineas: tuple[Linea, ...] = ()
    entrega: Entrega | None = None
    # MATU-62: desde aquí el total, las líneas y las condiciones quedan fijos
    pagado_en: datetime | None = None

    @property
    def etag(self) -> str:
        return f'"v{self.version}"'

    @property
    def confirmado(self) -> bool:
        return self.total_confirmado_en is not None

    def lineas_que_quedan(self) -> tuple[Linea, ...]:
        return tuple(linea for linea in self.lineas if not linea.salio)

    def salieron(self) -> tuple[Linea, ...]:
        return tuple(linea for linea in self.lineas if linea.salio) if self.confirmado else ()

    @property
    def subtotal_productos(self) -> int:
        return subtotal(self.lineas_que_quedan())

    @property
    def total(self) -> int | None:
        return self.subtotal_productos + self.costo_envio if self.confirmado else None


def subtotal(lineas: Iterable[Linea]) -> int:
    """La suma exacta de cantidad × precio, en pesos enteros: sin redondeo ni punto flotante."""
    return sum(linea.subtotal for linea in lineas)


def cambio_de(linea: Linea, confirmado: bool) -> Cambio | None:
    """Qué cambió contra el carrito (C15). None en borrador y si no cambió nada."""
    if not confirmado or linea.salio:
        return None
    precio = linea.precio_carrito if linea.precio_unitario != linea.precio_carrito else None
    comercio = linea.comercio_carrito if linea.comercio.id != linea.comercio_carrito.id else None
    if precio is None and comercio is None:
        return None
    return Cambio(precio_antes=precio, comercio_antes=comercio)


@dataclass(frozen=True)
class ParteComercio:
    comercio: Comercio
    subtotal_productos: int


def partes_por_comercio(lineas: Iterable[Linea]) -> tuple[ParteComercio, ...]:
    """Una parte por comercio de las líneas que quedan (D7), por nombre de fantasía e id."""
    sumas: dict[uuid.UUID, tuple[Comercio, int]] = {}
    for linea in lineas:
        if linea.salio:
            continue
        actual = sumas.get(linea.comercio.id, (linea.comercio, 0))
        sumas[linea.comercio.id] = (actual[0], actual[1] + linea.subtotal)
    ordenadas = sorted(sumas.values(), key=lambda par: (par[0].nombre_fantasia, str(par[0].id)))
    return tuple(ParteComercio(comercio=c, subtotal_productos=s) for c, s in ordenadas)


# --- El carrito ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LineaPedida:
    oferta_id: uuid.UUID
    cantidad: int


@dataclass(frozen=True)
class ErrorLinea:
    """Un 422 por línea: ``campo`` como lineas[i].oferta_id y ``tipo`` oferta_no_disponible o producto_repetido."""

    campo: str
    tipo: str
    mensaje: str


class CarritoInvalido(ValueError):
    def __init__(self, errores: Sequence[ErrorLinea]) -> None:
        super().__init__("el carrito no es válido")
        self.errores = tuple(errores)


@dataclass(frozen=True)
class LineaDelCarrito:
    """Una línea del carrito por guardar. ``id`` es None si es nueva."""

    id: uuid.UUID | None
    oferta: Oferta
    cantidad: int
    precio_carrito: int


def armar_carrito(
    pedidas: Sequence[LineaPedida], ofertas: Mapping[uuid.UUID, Oferta], actuales: Sequence[Linea] = ()
) -> list[LineaDelCarrito]:
    """Las líneas nuevas del carrito (decisiones 196 y 199). Lanza CarritoInvalido con un error por línea.

    El precio del carrito es el de la oferta ahora (C15). Una línea del mismo producto y la misma oferta que ya estaba
    conserva su precio del carrito; con otra oferta, toma el de la nueva. La oferta del carrito de una línea que ya
    estaba se acepta aunque haya dejado de estar publicada (LineaPedido.oferta_id): se conserva como estaba, y al
    confirmar se resuelve como cualquier producto que falta."""
    errores: list[ErrorLinea] = []
    vistos: set[uuid.UUID] = set()
    por_producto = {linea.producto.id: linea for linea in actuales}
    por_oferta = {linea.oferta_carrito_id: linea for linea in actuales}
    armadas: list[LineaDelCarrito] = []
    for i, pedida in enumerate(pedidas):
        oferta = ofertas.get(pedida.oferta_id)
        if oferta is None and pedida.oferta_id in por_oferta:
            ya = por_oferta[pedida.oferta_id]
            oferta = Oferta(
                id=ya.oferta_carrito_id, producto=ya.producto, comercio=ya.comercio_carrito, precio=ya.precio_carrito
            )
        if oferta is None:
            errores.append(
                ErrorLinea(f"lineas.{i}.oferta_id", "oferta_no_disponible", "esta oferta no está en el catálogo")
            )
            continue
        if oferta.producto.id in vistos:
            errores.append(ErrorLinea(f"lineas.{i}.oferta_id", "producto_repetido", "un producto va una sola vez"))
            continue
        vistos.add(oferta.producto.id)
        anterior = por_producto.get(oferta.producto.id)
        if anterior is not None and anterior.oferta_carrito_id == oferta.id:
            armadas.append(LineaDelCarrito(anterior.id, oferta, pedida.cantidad, anterior.precio_carrito))
        else:
            armadas.append(
                LineaDelCarrito(None if anterior is None else anterior.id, oferta, pedida.cantidad, oferta.precio)
            )
    if errores:
        raise CarritoInvalido(errores)
    return armadas


@dataclass(frozen=True)
class ReglaPedida:
    producto_id: uuid.UUID
    regla: Regla


def armar_reglas(pedidas: Sequence[ReglaPedida], productos: Iterable[uuid.UUID]) -> dict[uuid.UUID, Regla]:
    """La regla de cada producto del pedido (decisión 200): la del cuerpo o, si no viene, ``otro_comercio``."""
    del_pedido = list(productos)
    errores: list[ErrorLinea] = []
    elegidas: dict[uuid.UUID, Regla] = {}
    for i, pedida in enumerate(pedidas):
        if pedida.producto_id not in del_pedido:
            errores.append(
                ErrorLinea(f"reglas.{i}.producto_id", "producto_no_esta", "ese producto no está en el pedido")
            )
        elif pedida.producto_id in elegidas:
            errores.append(ErrorLinea(f"reglas.{i}.producto_id", "producto_repetido", "un producto va una sola vez"))
        else:
            elegidas[pedida.producto_id] = pedida.regla
    if errores:
        raise CarritoInvalido(errores)
    return {producto: elegidas.get(producto, REGLA_POR_OMISION) for producto in del_pedido}


# --- Confirmar el total (C5) -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class LineaConfirmada:
    linea_id: uuid.UUID
    # La oferta confirmada, o None si la línea sale
    oferta: Oferta | None
    retracto_pierde_al_abrir: bool

    @property
    def sale(self) -> bool:
        return self.oferta is None


class NadaDisponible(Exception):
    """Ningún comercio tiene ningún producto del carrito: el pedido no cambia (409 nada-disponible)."""


def _clave_precio(oferta: Oferta) -> tuple[int, str, str]:
    return (oferta.precio, oferta.comercio.nombre_fantasia, str(oferta.comercio.id))


def confirmar_lineas(
    lineas: Sequence[Linea],
    ofertas_por_producto: Mapping[uuid.UUID, Sequence[Oferta]],
    hay: Mapping[tuple[uuid.UUID, uuid.UUID], bool],
) -> list[LineaConfirmada]:
    """Dónde queda cada línea del carrito (C5). ``hay[(comercio_id, producto_id)]`` dice si ese comercio tiene la
    cantidad de la línea. ``ofertas_por_producto`` son las ofertas publicadas ahora, del mismo producto.

    Todas las líneas del carrito se consultan otra vez, también las que salieron antes (decisión 202). Lanza
    NadaDisponible si no queda ninguna."""
    resultado: list[LineaConfirmada] = []
    for linea in lineas:
        ofertas = ofertas_por_producto.get(linea.producto.id, ())
        propia = next(
            (o for o in ofertas if o.comercio.id == linea.comercio_carrito.id and o.producto.id == linea.producto.id),
            None,
        )
        elegida: Oferta | None = None
        if propia is not None and hay.get((propia.comercio.id, linea.producto.id), False):
            elegida = propia
        elif linea.regla is Regla.OTRO_COMERCIO:
            candidatas = [
                o
                for o in ofertas
                if o.producto.id == linea.producto.id
                and o.comercio.id != linea.comercio_carrito.id
                and hay.get((o.comercio.id, linea.producto.id), False)
            ]
            elegida = min(candidatas, key=_clave_precio, default=None)
        resultado.append(
            LineaConfirmada(
                linea_id=linea.id,
                oferta=elegida,
                retracto_pierde_al_abrir=linea.producto.retracto_pierde_al_abrir,
            )
        )
    if not any(not r.sale for r in resultado):
        raise NadaDisponible()
    return resultado


def lineas_por_consultar(
    lineas: Sequence[Linea], ofertas_por_producto: Mapping[uuid.UUID, Sequence[Oferta]]
) -> dict[uuid.UUID, list[tuple[uuid.UUID, int]]]:
    """Qué preguntar a cada comercio: una consulta por comercio (C22). A cada uno, sus productos del carrito y, solo
    para las líneas con ``otro_comercio``, los que ofrece de otros comercios del carrito. Con ``quitar`` no se busca
    en otro comercio (C5)."""
    consultas: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    for linea in lineas:
        for oferta in ofertas_por_producto.get(linea.producto.id, ()):
            propia = oferta.comercio.id == linea.comercio_carrito.id
            if propia or linea.regla is Regla.OTRO_COMERCIO:
                consultas.setdefault(oferta.comercio.id, {})[linea.producto.id] = linea.cantidad
    return {
        comercio: sorted(productos.items(), key=lambda par: str(par[0])) for comercio, productos in consultas.items()
    }


def aplicar_confirmacion(pedido: Pedido, confirmadas: Sequence[LineaConfirmada]) -> tuple[Linea, ...]:
    """Las líneas como quedan al confirmar: con la oferta, el comercio y el precio confirmados, o fuera."""
    por_id = {c.linea_id: c for c in confirmadas}
    nuevas: list[Linea] = []
    for linea in pedido.lineas:
        c = por_id[linea.id]
        if c.oferta is None:
            nuevas.append(
                replace(
                    linea,
                    oferta_id=linea.oferta_carrito_id,
                    comercio=linea.comercio_carrito,
                    precio_unitario=linea.precio_carrito,
                    salio=True,
                    retracto_copiado=c.retracto_pierde_al_abrir,
                )
            )
        else:
            nuevas.append(
                replace(
                    linea,
                    oferta_id=c.oferta.id,
                    comercio=c.oferta.comercio,
                    precio_unitario=c.oferta.precio,
                    salio=False,
                    retracto_copiado=c.retracto_pierde_al_abrir,
                )
            )
    return tuple(nuevas)


def vence_en(ahora: datetime) -> datetime:
    return ahora + VIGENCIA_TOTAL


def volver_al_carrito(lineas: Sequence[Linea]) -> tuple[Linea, ...]:
    """«Cambiar el pedido» (C1 y C9): cada línea vuelve a la oferta, el comercio y el precio del carrito, también
    las que salieron. Las reglas se conservan."""
    return tuple(
        replace(
            linea,
            oferta_id=linea.oferta_carrito_id,
            comercio=linea.comercio_carrito,
            precio_unitario=linea.precio_carrito,
            salio=False,
            retracto_copiado=None,
        )
        for linea in lineas
    )


@dataclass(frozen=True)
class DatosPiloto:
    """Lo que el resumen agrega a los montos (C1, D8), atado a la versión de las condiciones."""

    vendedor: str = "MATU, piloto académico, sin persona jurídica"
    boleta: str = "En este piloto no se emite boleta"
    ventana_entrega: str = "Entre 24 y 48 horas hábiles"
    canal_reclamo: str = "cuidaconmatu@gmail.com"


PILOTO = DatosPiloto()
