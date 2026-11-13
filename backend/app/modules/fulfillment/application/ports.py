"""Puertos del despacho (ADR-021, MATU-63).

- RepositorioComercio: lo que hace y ve la sesión de un comercio, solo por las funciones SECURITY DEFINER de la 0029.
  Nunca recibe el pedido, el grupo, la persona, montos ni el código (D-63-1).
- RepositorioDespacho: lo que el sistema y operación leen y escriben del pedido después del pago, en la transacción de
  su grupo (RLS por rol, migración 0029).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.fulfillment.domain.despacho import EstadoParte, LineaDespacho


@dataclass(frozen=True)
class Comercio:
    id: uuid.UUID
    nombre_fantasia: str
    ficticio: bool


@dataclass(frozen=True)
class ParteComercio:
    """La proyección de una parte para su comercio (D-63-1)."""

    id: uuid.UUID
    referencia: str
    estado: EstadoParte
    version: int
    enviado_en: datetime
    lineas: int
    retirada_en: datetime | None
    cancelada_en: datetime | None
    codigo_generado_en: datetime | None
    codigo_con_hash: bool
    codigo_expira_en: datetime | None
    codigo_usado_en: datetime | None
    codigo_bloqueado_en: datetime | None


@dataclass(frozen=True)
class LineaComercio:
    id: uuid.UUID
    producto_nombre: str
    presentacion: str
    cantidad: int
    estado_linea: str
    unidades_faltantes: int


@dataclass(frozen=True)
class ProductoComercio:
    oferta_id: uuid.UUID
    nombre: str
    presentacion: str
    precio: int
    stock: int
    apartado: int
    disponible: bool
    actualizado_en: datetime


class RepositorioComercio(Protocol):
    """Implementación: RepositorioComercioSQL (infrastructure/repositorio_comercio.py)."""

    def comercio(self) -> Comercio | None: ...

    def partes(self, desde: datetime) -> list[ParteComercio]: ...

    def parte(self, parte_id: uuid.UUID) -> ParteComercio | None: ...

    def lineas(self, parte_id: uuid.UUID) -> list[LineaComercio]: ...

    def preparar(self, parte_id: uuid.UUID, version: int | None, ahora: datetime) -> str: ...

    def marcar_linea(
        self, parte_id: uuid.UUID, linea_id: uuid.UUID, estado: str, faltantes: int, version: int | None
    ) -> str: ...

    def listo(self, parte_id: uuid.UUID, version: int | None, ahora: datetime) -> str: ...

    def validar_codigo(self, parte_id: uuid.UUID, huella: str, ahora: datetime) -> tuple[str, int]: ...

    def productos(self, ahora: datetime) -> list[ProductoComercio]: ...

    def cambiar_producto(
        self, oferta_id: uuid.UUID, stock: int | None, disponible: bool | None, antes: datetime | None, ahora: datetime
    ) -> bool | None:
        """True si cambió, False si la versión no calza (412), None si la oferta no es del comercio."""
        ...


@dataclass(frozen=True)
class PedidoDespacho:
    id: uuid.UUID
    grupo_id: uuid.UUID
    persona_id: uuid.UUID
    estado: str
    pagado_en: datetime | None
    entregado_en: datetime | None
    costo_envio: int
    condiciones_version: str | None


@dataclass(frozen=True)
class ParteDespacho:
    id: uuid.UUID
    comercio_id: uuid.UUID
    estado: EstadoParte
    enviado_en: datetime | None


class RepositorioDespacho(Protocol):
    """Implementación: RepositorioDespachoSQL (infrastructure/repositorio_despacho.py)."""

    def pedido(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> PedidoDespacho | None: ...

    def partes(self, pedido_id: uuid.UUID) -> list[ParteDespacho]: ...

    def lineas(self, pedido_id: uuid.UUID) -> list[LineaDespacho]: ...

    def comercio_de_parte(self, parte_id: uuid.UUID) -> uuid.UUID | None: ...

    def cambiar_estado(
        self,
        pedido_id: uuid.UUID,
        desde: str,
        hacia: str,
        actor_tipo: str,
        actor_ref: uuid.UUID | None,
        motivo: str | None,
        ahora: datetime,
    ) -> None:
        """El estado del pedido y su fila en la línea de tiempo. Con hacia = entregado fija entregado_en."""
        ...

    def cancelar_partes(self, pedido_id: uuid.UUID, motivo: str, ahora: datetime) -> None: ...

    def guardar_codigo(self, parte_id: uuid.UUID, huella: str, generado_en: datetime, expira_en: datetime) -> bool:
        """El código nuevo de una parte lista: borra el uso, los intentos y el bloqueo anteriores. False si la parte no
        está lista o ya se retiró."""
        ...

    def registrar_consumo(self, parte: ParteDespacho, pedido_id: uuid.UUID, monto: int, ahora: datetime) -> None: ...

    def emitir(self, tipo: str, pedido_id: uuid.UUID, grupo_id: uuid.UUID, ahora: datetime) -> None: ...
