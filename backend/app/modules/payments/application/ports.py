"""Puertos del pago (ADR-021, MATU-62).

- PasarelaWebpay: Webpay Plus en venta normal. Implementaciones: PasarelaTransbank (el SDK, infrastructure/) y
  PasarelaFalsa (infrastructure/, responde como Transbank: un commit repetido devuelve la misma transacción y, después
  de una anulación parcial, PARTIALLY_NULLIFIED con el saldo; informe de Martín del 10-11, H4).
- RepositorioPagos: el cargo, sus participaciones, sus ventas y anulaciones, y lo del pedido que el pago escribe,
  en la transacción del contexto (RLS por grupo y por rol, migración 0024).

Nada de lo que pasa por estos puertos va a los logs ni a los errores: ni el token, ni el buy_order, ni el session_id,
ni la respuesta de Transbank, ni los últimos 4 (decisión 247).
"""

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.payments.domain.cargo import EstadoCargo, EstadoParticipacion
from app.modules.payments.domain.venta import Anulacion, RespuestaAnulacion, RespuestaTransaccion, Venta
from app.shared.puertos import RegistroAuditoria

# --- La pasarela ------------------------------------------------------------------------------------------------


class PasarelaNoDisponible(Exception):
    """Webpay no respondió (red, tiempo agotado o un 5xx). Mensaje fijo: nunca el de la librería."""

    def __init__(self) -> None:
        super().__init__("la pasarela no responde")


class PasarelaRechazo(Exception):
    """Transbank respondió con un error (el token no existe, venció o la operación no corresponde). Mensaje fijo."""

    def __init__(self) -> None:
        super().__init__("la pasarela rechazó la operación")


@dataclass(frozen=True)
class InicioVenta:
    url: str
    token: str


class PasarelaWebpay(Protocol):
    """Webpay Plus, venta normal (ADR-027). Transbank recibe solo el monto, el buy_order y el session_id."""

    @property
    def url_formulario(self) -> str:
        """El action del formulario de Webpay (integración o producción)."""
        ...

    @property
    def pago_de_prueba(self) -> bool:
        """True si no se mueve dinero real (integración o la falsa): el sello de D-62-7."""
        ...

    def crear(self, buy_order: str, session_id: str, monto: int, return_url: str) -> InicioVenta:
        """create. Lanza PasarelaNoDisponible o PasarelaRechazo."""
        ...

    def confirmar(self, token: str) -> RespuestaTransaccion:
        """commit. Un commit repetido no falla: devuelve la misma transacción (prueba del 10-11)."""
        ...

    def consultar(self, token: str) -> RespuestaTransaccion:
        """status."""
        ...

    def anular(self, token: str, monto: int) -> RespuestaAnulacion:
        """refund: total (REVERSED o NULLIFIED) o parcial (NULLIFIED), a la misma tarjeta."""
        ...


# --- Lo que el pago lee y escribe -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Cargo:
    id: uuid.UUID
    pedido_id: uuid.UUID
    estado: EstadoCargo
    monto_cobrado: int = 0
    monto_devuelto: int = 0


@dataclass(frozen=True)
class Participacion:
    id: uuid.UUID
    cargo_id: uuid.UUID
    usuario_id: uuid.UUID
    estado: EstadoParticipacion
    monto_cobrado: int = 0
    monto_devuelto: int = 0


@dataclass(frozen=True)
class PedidoCobro:
    """Lo del pedido que el pago necesita, aunque la persona ya no esté (la vuelta y la conciliación)."""

    id: uuid.UUID
    grupo_id: uuid.UUID
    persona_id: uuid.UUID
    estado: str
    subtotal_productos: int
    costo_envio: int
    total: int
    total_confirmado_en: datetime | None
    total_vence_en: datetime | None
    pagado_en: datetime | None
    referencia: str | None = None


@dataclass(frozen=True)
class CondicionesAceptadas:
    version: str
    huella: str
    aceptadas_en: datetime
    aceptadas_por: uuid.UUID


@dataclass(frozen=True)
class LineaPagada:
    """Una línea del pedido pagado, con su precio pagado (fijo) y su devolución."""

    id: uuid.UUID
    producto_id: uuid.UUID
    nombre: str
    presentacion: str
    unidad: str
    unidades_por_envase: int
    cantidad: int
    precio_unitario: int
    salio: bool
    monto_devuelto: int
    devuelta_en: datetime | None
    # MATU-63 (D-63-8): las unidades que el comercio no tenía
    unidades_faltantes: int = 0

    @property
    def subtotal(self) -> int:
        return self.cantidad * self.precio_unitario


class RepositorioPagos(Protocol):
    """Implementación: RepositorioPagosSQL (infrastructure/repositorio_pagos.py)."""

    # Pedido
    def pedido(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> PedidoCobro | None: ...

    def ultimo_pagado_de(self, persona_id: uuid.UUID) -> uuid.UUID | None:
        """El pedido de pagado_en más reciente de la persona (decisión 237), o None."""
        ...

    def aceptar_condiciones(
        self, pedido_id: uuid.UUID, version: str, huella: str, aceptadas_en: datetime, por: uuid.UUID
    ) -> None: ...

    def condiciones_aceptadas(self, pedido_id: uuid.UUID) -> CondicionesAceptadas | None: ...

    def referencias(self) -> set[str]:
        """Las referencias ya usadas en el grupo del pedido."""
        ...

    def marcar_pagado(self, pedido_id: uuid.UUID, pagado_en: datetime, referencia: str) -> None: ...

    def transicion(
        self, pedido_id: uuid.UUID, desde: str, hacia: str, motivo: str | None, ocurrido_en: datetime
    ) -> None:
        """Una fila de la línea de tiempo, con actor sistema."""
        ...

    def lineas_pagadas(self, pedido_id: uuid.UUID) -> list[LineaPagada]: ...

    def devolver_linea(self, linea_id: uuid.UUID, monto: int, devuelta_en: datetime) -> None: ...

    def correo_propio(self) -> str | None:
        """El correo de la cuenta de quien lee (para el comprobante de quien pagó, D-62-3), o None."""
        ...

    def asociar_clave(self, endpoint: str, clave: str, venta_id: uuid.UUID) -> None:
        """La venta de una Idempotency-Key de pagar (decisión 229)."""
        ...

    def venta_de_clave(self, endpoint: str, clave: str) -> uuid.UUID | None: ...

    def liberar_clave(self, endpoint: str, clave: str) -> None:
        """Un 503 de pagar no se guarda en la clave (decisión 229)."""
        ...

    def emitir(self, tipo: str, pedido_id: uuid.UUID, ahora: datetime) -> None:
        """El evento al outbox, en la misma transacción, solo con identificadores."""
        ...

    # Cargo y participación
    def cargo_de(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> Cargo | None: ...

    def cargo(self, cargo_id: uuid.UUID, *, bloquear: bool = False) -> Cargo | None: ...

    def crear_cargo(self, cargo: Cargo, ahora: datetime) -> None: ...

    def guardar_cargo(self, cargo: Cargo) -> None: ...

    def participacion(self, participacion_id: uuid.UUID) -> Participacion | None: ...

    def participacion_de(self, cargo_id: uuid.UUID, usuario_id: uuid.UUID) -> Participacion | None: ...

    def crear_participacion(self, participacion: Participacion) -> None: ...

    def guardar_participacion(self, participacion: Participacion) -> None: ...

    # Ventas y anulaciones
    def ventas(self, cargo_id: uuid.UUID) -> list[Venta]:
        """Por creado_en."""
        ...

    def venta(self, venta_id: uuid.UUID, *, bloquear: bool = False) -> Venta | None: ...

    def insertar_venta(self, venta: Venta, clave_pasarela: str) -> None: ...

    def guardar_venta(self, venta: Venta) -> None: ...

    def anulaciones(self, cargo_id: uuid.UUID) -> list[Anulacion]:
        """Por solicitada_en."""
        ...

    def anulacion(self, anulacion_id: uuid.UUID, *, bloquear: bool = False) -> Anulacion | None: ...

    def insertar_anulacion(self, anulacion: Anulacion, clave_pasarela: str) -> None: ...

    def guardar_anulacion(self, anulacion: Anulacion) -> None: ...


# La vuelta y la conciliación: cada venta en su propia transacción, con el grupo de la venta y app.rol = 'sistema'


@dataclass(frozen=True)
class Unidad:
    repositorio: RepositorioPagos
    registro: RegistroAuditoria


AbrirGrupo = Callable[[uuid.UUID], AbstractContextManager[Unidad]]


class ResolverVenta(Protocol):
    def __call__(
        self, token: str | None, orden: str | None, sesion: str | None
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        """La venta y su grupo, por token o por buy_order y session_id juntos (pago_resolver_venta). Solo ids."""
        ...


class ListarPorConciliar(Protocol):
    def __call__(self, limite: datetime, cantidad: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """pagos_por_conciliar: (transacción, grupo) de lo que hay que cerrar o reintentar."""
        ...
