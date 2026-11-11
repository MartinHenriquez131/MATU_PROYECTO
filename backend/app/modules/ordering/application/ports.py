"""Puertos del pedido (ADR-021).

RepositorioPedidos trabaja en la transacción del contexto de grupo (sesion_de_grupo): RLS acota todo al grupo y,
desde la migración 0023, solo admin y cuidador escriben. La consulta de stock va por el puerto CatalogoComercio del
catálogo (decisión 168), una consulta por comercio y sin datos de nadie.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.modules.ordering.domain.estados import Estado, Motivo
from app.modules.ordering.domain.idempotencia import Registro
from app.modules.ordering.domain.pedido import LineaDelCarrito, Oferta, Pedido


class Autorizacion(StrEnum):
    """La autorización de pedidos (despacho) de la persona, según el Reloj (C21)."""

    VIGENTE = "vigente"
    SIN_AUTORIZACION = "sin_autorizacion"
    REVISION_VENCIDA = "revision_vencida"


@dataclass(frozen=True)
class DireccionPersona:
    calle: str
    numero: str
    depto: str | None
    comuna: str
    region: str
    referencia: str | None


@dataclass(frozen=True)
class Transicion:
    desde: Estado | None
    hacia: Estado
    actor_usuario: uuid.UUID | None
    motivo: Motivo | None
    ocurrido_en: datetime


class RepositorioPedidos(Protocol):
    """Implementación: RepositorioPedidosSQL (infrastructure/repositorio_pedidos.py)."""

    def autorizacion_despacho(self, persona_id: uuid.UUID, ahora: datetime) -> Autorizacion | None:
        """La autorización de la persona, leída con FOR SHARE (un retiro simultáneo espera o hace esperar). None si
        la persona no es del grupo, no existe o está eliminada."""
        ...

    def persona_del_grupo(self, persona_id: uuid.UUID) -> bool:
        """Si la persona es del grupo y no está eliminada."""
        ...

    def en_curso(self, persona_id: uuid.UUID) -> uuid.UUID | None:
        """El pedido sin pagar de la persona (C4), o None."""
        ...

    def cargar(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> Pedido | None:
        """El pedido del grupo, de una persona no eliminada, con sus líneas y su entrega. Con ``bloquear``, la fila
        del pedido con FOR UPDATE. None si no existe para el grupo."""
        ...

    def sin_pagar_de(self, persona_id: uuid.UUID) -> list[uuid.UUID]:
        """Los pedidos sin pagar de la persona, bloqueados, aunque la persona esté por borrarse."""
        ...

    def ofertas(self, oferta_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Oferta]:
        """Las ofertas publicadas de esos ids (las demás no vienen)."""
        ...

    def ofertas_de_productos(self, producto_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, list[Oferta]]:
        """Las ofertas publicadas de esos productos, por producto."""
        ...

    def crear(self, pedido: Pedido, lineas: list[LineaDelCarrito], usuario_id: uuid.UUID) -> bool:
        """Inserta el borrador con sus líneas y reglas. False si la persona ya tiene un pedido sin pagar (C4)."""
        ...

    def reemplazar_carrito(self, pedido: Pedido, lineas: list[LineaDelCarrito], ahora: datetime) -> None:
        """Las líneas y reglas del borrador quedan como ``lineas``: entran las nuevas (después de las que ya
        estaban, en el instante ``ahora``), salen las que no vienen. Sube la versión."""
        ...

    def guardar(self, pedido: Pedido, *, rehacer_partes: bool = False) -> None:
        """Escribe el encabezado (estado, versión, montos y plazos), las líneas, las reglas y la entrega del pedido.
        Con ``rehacer_partes``, borra y vuelve a crear un registro por comercio (D7) con su referencia opaca nueva."""
        ...

    def transicion(self, pedido_id: uuid.UUID, transicion: Transicion) -> None:
        """Agrega una fila a la línea de tiempo (solo inserción)."""
        ...

    def direccion_de(self, persona_id: uuid.UUID) -> DireccionPersona | None:
        """La dirección de entrega vigente de la persona, o None."""
        ...

    def celular_verificado(self) -> str | None:
        """El celular verificado (E.164) de quien hace la petición, o None."""
        ...


class RepositorioIdempotencia(Protocol):
    """Implementación: RepositorioIdempotenciaSQL (infrastructure/repositorio_idempotencia.py)."""

    def reservar(
        self, endpoint: str, clave: str, usuario_id: uuid.UUID, huella: bytes, expira_en: datetime
    ) -> Registro | None:
        """Reserva la clave. None si quedó reservada para esta petición; si ya existía, su fila."""
        ...

    def reemplazar(self, endpoint: str, clave: str, huella: bytes, expira_en: datetime) -> None:
        """Vuelve a reservar una clave vencida de la misma cuenta."""
        ...

    def completar(self, endpoint: str, clave: str, estado_http: int, pedido_id: uuid.UUID) -> None:
        """Guarda cómo terminó la petición: solo el estado HTTP y el id del pedido (D5)."""
        ...
