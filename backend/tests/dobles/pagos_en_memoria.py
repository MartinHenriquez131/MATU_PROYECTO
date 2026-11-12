"""El pago en memoria (MATU-62): RepositorioPagos, la unidad del sistema, el resolver de la vuelta y la lista de la
conciliación, sin base. Para probar los casos de uso con la PasarelaFalsa (arquitectura 12.4).

Imita lo que la base garantiza y los casos de uso necesitan: el pedido con su total, sus condiciones y su marca de
pago; un cargo por pedido; las ventas y anulaciones; la línea de tiempo y el outbox. Las restricciones de la base que
importan al flujo se repiten como aserciones: una sola venta aprobada y no anulada por cargo, el token único, lo
anulado nunca supera lo cobrado y una línea se devuelve una sola vez. Solo datos sintéticos.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from app.modules.ordering.domain.estados import VIGENCIA_TOTAL, Estado
from app.modules.ordering.domain.pedido import Comercio, Linea, Pedido, Producto, Regla
from app.modules.payments.application.ports import (
    Cargo,
    CondicionesAceptadas,
    LineaPagada,
    Participacion,
    PedidoCobro,
    Unidad,
)
from app.modules.payments.domain.cargo import EstadoCargo
from app.modules.payments.domain.venta import Anulacion, EstadoVenta, MotivoAnulacion, Venta
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria

COMERCIO = Comercio(id=uuid.UUID(int=0xC01), nombre_fantasia="Farmacia Sintética", ficticio=True)


@dataclass
class PedidoMem:
    id: uuid.UUID
    grupo_id: uuid.UUID
    persona_id: uuid.UUID
    estado: str
    version: int
    lineas: list[LineaPagada]
    costo_envio: int
    total_confirmado_en: datetime | None
    total_vence_en: datetime | None
    pagado_en: datetime | None = None
    referencia: str | None = None
    condiciones: CondicionesAceptadas | None = None
    creado_en: datetime | None = None

    @property
    def subtotal(self) -> int:
        return sum(x.subtotal for x in self.lineas if not x.salio)

    @property
    def total(self) -> int:
        return self.subtotal + self.costo_envio

    def a_pedido(self) -> Pedido:
        """El pedido de ordering que pagar recibe, como lo cargaría RepositorioPedidosSQL."""
        lineas = tuple(
            Linea(
                id=x.id,
                producto=Producto(
                    id=x.producto_id,
                    nombre=x.nombre,
                    presentacion=x.presentacion,
                    unidad=x.unidad,
                    unidades_por_envase=x.unidades_por_envase,
                    retracto_pierde_al_abrir=False,
                ),
                cantidad=x.cantidad,
                regla=Regla.OTRO_COMERCIO,
                oferta_carrito_id=uuid.UUID(int=x.id.int ^ 1),
                comercio_carrito=COMERCIO,
                precio_carrito=x.precio_unitario,
                oferta_id=uuid.UUID(int=x.id.int ^ 1),
                comercio=COMERCIO,
                precio_unitario=x.precio_unitario,
            )
            for x in self.lineas
        )
        assert self.creado_en is not None
        return Pedido(
            id=self.id,
            grupo_id=self.grupo_id,
            persona_id=self.persona_id,
            estado=Estado(self.estado),
            version=self.version,
            costo_envio=self.costo_envio,
            total_confirmado_en=self.total_confirmado_en,
            total_vence_en=self.total_vence_en,
            creado_en=self.creado_en,
            actualizado_en=self.creado_en,
            lineas=lineas,
            pagado_en=self.pagado_en,
        )


@dataclass
class BasePagos:
    """Todas las tablas del pago en memoria, de todos los grupos."""

    pedidos: dict[uuid.UUID, PedidoMem] = field(default_factory=dict)
    cargos: dict[uuid.UUID, Cargo] = field(default_factory=dict)
    participaciones: dict[uuid.UUID, Participacion] = field(default_factory=dict)
    ventas: dict[uuid.UUID, Venta] = field(default_factory=dict)
    anulaciones: dict[uuid.UUID, Anulacion] = field(default_factory=dict)
    transiciones: list[tuple[uuid.UUID, str, str, str | None, datetime]] = field(default_factory=list)
    eventos: list[tuple[str, uuid.UUID]] = field(default_factory=list)
    claves: dict[tuple[str, str], uuid.UUID | None] = field(default_factory=dict)
    correos: dict[uuid.UUID, str] = field(default_factory=dict)
    registros: dict[uuid.UUID, RegistroAuditoriaEnMemoria] = field(default_factory=dict)

    def nuevo_pedido(
        self,
        ahora: datetime,
        *,
        precios: tuple[tuple[int, int], ...] = ((2, 17990), (2, 8745)),
        costo_envio: int = 3990,
        estado: str = "total_confirmado",
        grupo_id: uuid.UUID | None = None,
    ) -> PedidoMem:
        """Un pedido con su total confirmado ahora (vence en 15 minutos). Por omisión, $57.460 como en la prueba de
        Transbank del 10-11: 2 × 17.990 + 2 × 8.745 + 3.990 de envío."""
        lineas = [
            LineaPagada(
                id=uuid.uuid4(),
                producto_id=uuid.uuid4(),
                nombre=f"Producto sintético {i}",
                presentacion="Paquete",
                unidad="unidad",
                unidades_por_envase=20,
                cantidad=cantidad,
                precio_unitario=precio,
                salio=False,
                monto_devuelto=0,
                devuelta_en=None,
            )
            for i, (cantidad, precio) in enumerate(precios, start=1)
        ]
        confirmado = estado in ("total_confirmado", "vencido")
        pedido = PedidoMem(
            id=uuid.uuid4(),
            grupo_id=grupo_id or uuid.uuid4(),
            persona_id=uuid.uuid4(),
            estado=estado,
            version=2,
            lineas=lineas,
            costo_envio=costo_envio,
            total_confirmado_en=ahora if confirmado else None,
            total_vence_en=ahora + VIGENCIA_TOTAL if confirmado else None,
            creado_en=ahora - timedelta(minutes=5),
        )
        self.pedidos[pedido.id] = pedido
        return pedido

    def volver_a_confirmar(self, pedido: PedidoMem, ahora: datetime) -> None:
        """C1: otro total (otro total_confirmado_en), con un envío distinto para que también cambie el monto."""
        pedido.estado = "total_confirmado"
        pedido.total_confirmado_en = ahora
        pedido.total_vence_en = ahora + VIGENCIA_TOTAL
        pedido.version += 1

    def cobrado_neto(self, cargo_id: uuid.UUID) -> int:
        cargo = self.cargos[cargo_id]
        return cargo.monto_cobrado - cargo.monto_devuelto


class RepositorioPagosEnMemoria:
    def __init__(self, base: BasePagos, grupo_id: uuid.UUID, usuario_id: uuid.UUID | None = None) -> None:
        self._base = base
        self._grupo_id = grupo_id
        self._usuario_id = usuario_id

    def _pedido(self, pedido_id: uuid.UUID) -> PedidoMem | None:
        p = self._base.pedidos.get(pedido_id)
        return p if p is not None and p.grupo_id == self._grupo_id else None

    # --- Pedido

    def pedido(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> PedidoCobro | None:
        p = self._pedido(pedido_id)
        if p is None:
            return None
        return PedidoCobro(
            id=p.id,
            grupo_id=p.grupo_id,
            persona_id=p.persona_id,
            estado=p.estado,
            subtotal_productos=p.subtotal,
            costo_envio=p.costo_envio,
            total=p.total,
            total_confirmado_en=p.total_confirmado_en,
            total_vence_en=p.total_vence_en,
            pagado_en=p.pagado_en,
            referencia=p.referencia,
        )

    def ultimo_pagado_de(self, persona_id: uuid.UUID) -> uuid.UUID | None:
        pagados = [
            p for p in self._base.pedidos.values()
            if p.grupo_id == self._grupo_id and p.persona_id == persona_id and p.pagado_en is not None
        ]
        return max(pagados, key=lambda p: p.pagado_en or datetime.min).id if pagados else None

    def aceptar_condiciones(
        self, pedido_id: uuid.UUID, version: str, huella: str, aceptadas_en: datetime, por: uuid.UUID
    ) -> None:
        p = self._pedido(pedido_id)
        assert p is not None and p.pagado_en is None, "con el pago, las condiciones quedan fijas"
        p.condiciones = CondicionesAceptadas(
            version=version, huella=huella, aceptadas_en=aceptadas_en, aceptadas_por=por
        )

    def condiciones_aceptadas(self, pedido_id: uuid.UUID) -> CondicionesAceptadas | None:
        p = self._pedido(pedido_id)
        return None if p is None else p.condiciones

    def referencias(self) -> set[str]:
        return {p.referencia for p in self._base.pedidos.values() if p.grupo_id == self._grupo_id and p.referencia}

    def marcar_pagado(self, pedido_id: uuid.UUID, pagado_en: datetime, referencia: str) -> None:
        p = self._pedido(pedido_id)
        assert p is not None and p.pagado_en is None and p.estado in ("total_confirmado", "vencido")
        # La base exige la venta aprobada y no anulada del mismo total (trigger pedido_escritura_del_pago)
        assert any(
            v.estado is EstadoVenta.APROBADA and not v.anulacion_total and v.monto == p.total
            and v.total_confirmado_en == p.total_confirmado_en
            for v in self._base.ventas.values()
            if self._base.cargos[v.cargo_id].pedido_id == p.id
        ), "el pago es de una venta aprobada del mismo total"
        p.estado, p.pagado_en, p.referencia = "pagado", pagado_en, referencia

    def transicion(
        self, pedido_id: uuid.UUID, desde: str, hacia: str, motivo: str | None, ocurrido_en: datetime
    ) -> None:
        self._base.transiciones.append((pedido_id, desde, hacia, motivo, ocurrido_en))

    def lineas_pagadas(self, pedido_id: uuid.UUID) -> list[LineaPagada]:
        p = self._pedido(pedido_id)
        return [] if p is None else list(p.lineas)

    def devolver_linea(self, linea_id: uuid.UUID, monto: int, devuelta_en: datetime) -> None:
        for p in self._base.pedidos.values():
            for i, x in enumerate(p.lineas):
                if x.id == linea_id:
                    assert x.monto_devuelto == 0 and monto <= x.subtotal
                    p.lineas[i] = replace(x, monto_devuelto=monto, devuelta_en=devuelta_en)
                    return
        raise AssertionError("la línea no existe")

    def correo_propio(self) -> str | None:
        return None if self._usuario_id is None else self._base.correos.get(self._usuario_id)

    def asociar_clave(self, endpoint: str, clave: str, venta_id: uuid.UUID) -> None:
        self._base.claves[(endpoint, clave)] = venta_id

    def venta_de_clave(self, endpoint: str, clave: str) -> uuid.UUID | None:
        return self._base.claves.get((endpoint, clave))

    def liberar_clave(self, endpoint: str, clave: str) -> None:
        self._base.claves.pop((endpoint, clave), None)

    def emitir(self, tipo: str, pedido_id: uuid.UUID, ahora: datetime) -> None:
        self._base.eventos.append((tipo, pedido_id))

    # --- Cargo y participación

    def cargo_de(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> Cargo | None:
        if self._pedido(pedido_id) is None:
            return None
        return next((c for c in self._base.cargos.values() if c.pedido_id == pedido_id), None)

    def cargo(self, cargo_id: uuid.UUID, *, bloquear: bool = False) -> Cargo | None:
        return self._base.cargos.get(cargo_id)

    def crear_cargo(self, cargo: Cargo, ahora: datetime) -> None:
        assert all(c.pedido_id != cargo.pedido_id for c in self._base.cargos.values()), "un cargo por pedido"
        self._base.cargos[cargo.id] = cargo

    def guardar_cargo(self, cargo: Cargo) -> None:
        assert 0 <= cargo.monto_devuelto <= cargo.monto_cobrado, "lo devuelto no supera lo cobrado"
        self._base.cargos[cargo.id] = cargo

    def participacion(self, participacion_id: uuid.UUID) -> Participacion | None:
        return self._base.participaciones.get(participacion_id)

    def participacion_de(self, cargo_id: uuid.UUID, usuario_id: uuid.UUID) -> Participacion | None:
        return next(
            (p for p in self._base.participaciones.values() if p.cargo_id == cargo_id and p.usuario_id == usuario_id),
            None,
        )

    def crear_participacion(self, participacion: Participacion) -> None:
        self._base.participaciones[participacion.id] = participacion

    def guardar_participacion(self, participacion: Participacion) -> None:
        self._base.participaciones[participacion.id] = participacion

    # --- Ventas y anulaciones

    def _con_marca(self, venta: Venta) -> Venta:
        tardio = any(
            a.venta_id == venta.id and a.motivo is MotivoAnulacion.PAGO_TARDIO for a in self._base.anulaciones.values()
        )
        return replace(venta, anulada_por_pago_tardio=tardio)

    def ventas(self, cargo_id: uuid.UUID) -> list[Venta]:
        return sorted(
            (self._con_marca(v) for v in self._base.ventas.values() if v.cargo_id == cargo_id),
            key=lambda v: (v.creado_en, str(v.id)),
        )

    def venta(self, venta_id: uuid.UUID, *, bloquear: bool = False) -> Venta | None:
        v = self._base.ventas.get(venta_id)
        return None if v is None else self._con_marca(v)

    def insertar_venta(self, venta: Venta, clave_pasarela: str) -> None:
        p = self._base.pedidos[self._base.cargos[venta.cargo_id].pedido_id]
        assert p.pagado_en is None and p.total == venta.monto and p.total_confirmado_en == venta.total_confirmado_en
        assert venta.token is None or all(v.token != venta.token for v in self._base.ventas.values())
        self._base.ventas[venta.id] = venta

    def guardar_venta(self, venta: Venta) -> None:
        anterior = self._base.ventas[venta.id]
        assert anterior.estado not in (EstadoVenta.APROBADA, EstadoVenta.RECHAZADA) or anterior.estado is venta.estado
        if venta.estado is EstadoVenta.APROBADA and not venta.anulacion_total:
            assert not any(
                v.id != venta.id and v.cargo_id == venta.cargo_id and v.estado is EstadoVenta.APROBADA
                and not v.anulacion_total
                for v in self._base.ventas.values()
            ), "una sola venta aprobada y no anulada por cargo"
        self._base.ventas[venta.id] = venta

    def anulaciones(self, cargo_id: uuid.UUID) -> list[Anulacion]:
        return sorted(
            (a for a in self._base.anulaciones.values() if a.cargo_id == cargo_id),
            key=lambda a: (a.solicitada_en, str(a.id)),
        )

    def anulacion(self, anulacion_id: uuid.UUID, *, bloquear: bool = False) -> Anulacion | None:
        return self._base.anulaciones.get(anulacion_id)

    def insertar_anulacion(self, anulacion: Anulacion, clave_pasarela: str) -> None:
        venta = self._base.ventas[anulacion.venta_id]
        assert venta.estado is EstadoVenta.APROBADA
        ya = sum(a.monto for a in self._base.anulaciones.values() if a.venta_id == venta.id)
        assert ya + anulacion.monto <= venta.monto, "lo anulado no supera lo cobrado"
        assert anulacion.pedido_linea_id is None or all(
            a.pedido_linea_id != anulacion.pedido_linea_id for a in self._base.anulaciones.values()
        ), "una línea se devuelve una sola vez"
        self._base.anulaciones[anulacion.id] = anulacion

    def guardar_anulacion(self, anulacion: Anulacion) -> None:
        self._base.anulaciones[anulacion.id] = anulacion


class SistemaEnMemoria:
    """La vuelta y la conciliación sobre la BasePagos: resolver, abrir un grupo y listar lo pendiente."""

    def __init__(self, base: BasePagos) -> None:
        self.base = base
        self.aperturas = 0

    def resolver(
        self, token: str | None, orden: str | None, sesion: str | None
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        for v in self.base.ventas.values():
            if (token is not None and v.token == token) or (
                token is None and orden is not None and sesion is not None
                and v.buy_order == orden and v.session_id == sesion
            ):
                return v.id, self.base.pedidos[self.base.cargos[v.cargo_id].pedido_id].grupo_id
        return None

    @contextmanager
    def abrir(self, grupo_id: uuid.UUID) -> Iterator[Unidad]:
        self.aperturas += 1
        registro = self.base.registros.setdefault(grupo_id, RegistroAuditoriaEnMemoria())
        yield Unidad(RepositorioPagosEnMemoria(self.base, grupo_id), registro)

    def listar(self, limite: datetime, cantidad: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
        pendientes = [
            v for v in self.base.ventas.values()
            if v.estado is EstadoVenta.AUTORIZANDO or (v.estado is EstadoVenta.INICIADA and v.creado_en <= limite)
        ]
        anulaciones = [
            a for a in self.base.anulaciones.values() if a.estado in (EstadoVenta.INICIADA, EstadoVenta.ERROR)
        ]
        filas = [(v.id, self._grupo_de(v.cargo_id), v.creado_en) for v in pendientes]
        filas += [(a.id, self._grupo_de(a.cargo_id), a.solicitada_en) for a in anulaciones]
        return [(i, g) for i, g, _ in sorted(filas, key=lambda f: (f[2], str(f[0])))][:cantidad]

    def _grupo_de(self, cargo_id: uuid.UUID) -> uuid.UUID:
        return self.base.pedidos[self.base.cargos[cargo_id].pedido_id].grupo_id


def cargo_pagado(base: BasePagos, pedido_id: uuid.UUID) -> Cargo:
    cargo = next(c for c in base.cargos.values() if c.pedido_id == pedido_id)
    assert cargo.estado in (EstadoCargo.PAGADO, EstadoCargo.DEVUELTO_PARCIAL, EstadoCargo.ANULADO)
    return cargo
