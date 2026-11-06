"""Publicador del outbox (arquitectura 8.6, MATU-41, decisión 106).

Toma los eventos pendientes de ``evento_outbox`` y entrega cada uno a los consumidores de su tipo:

- **Al menos una vez.** Un evento se marca publicado solo cuando todos sus consumidores terminaron. Si el
  proceso se cae a mitad de camino, el arriendo de 5 minutos vence y el evento se vuelve a tomar: cada
  consumidor es idempotente (``evento_consumido`` y sus propias restricciones).
- **Sin orden garantizado** (``SKIP LOCKED`` y el backoff lo rompen por construcción).
- **Reintentos** con el backoff de la sección 8.6 (1 s, 5 s, 30 s, 2 min, 10 min, 30 min, 1 h) y tope de 8
  intentos: el octavo fallo deja ``fallido_en`` y el evento no se reintenta solo. Se registra en WARNING
  para operación, solo con el id del evento.
- **Posponer** no suma un intento: lo usa el consumidor de avisos para no enviar antes de las 09:00.
- Un tipo sin consumidores se marca publicado: nadie lo espera.
- El log lleva el id del evento y nunca el payload. De una excepción del consumidor se registra solo el
  tipo (el mensaje puede traer datos).

Este módulo no conoce a ningún consumidor (app.shared no importa app.modules): quien arma la tarea le
entrega el mapa tipo -> consumidores. Todo lo que depende de la hora usa el puerto Reloj.
"""

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from app.shared.puertos import Reloj

log = logging.getLogger("matu.outbox")

# Arquitectura 8.6
TOPE_INTENTOS = 8
BACKOFF: tuple[timedelta, ...] = (
    timedelta(seconds=1),
    timedelta(seconds=5),
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(minutes=30),
    timedelta(hours=1),
    timedelta(hours=2),
)
# Cuántos eventos se toman por vuelta (la función outbox_tomar admite de 1 a 100)
LOTE = 100


@dataclass(frozen=True)
class EventoTomado:
    """Un evento del outbox: solo identificadores, el tipo y el payload (que solo admite UUID)."""

    id: int
    grupo_id: uuid.UUID | None
    tipo: str
    payload: Mapping[str, Any] = field(repr=False)
    intentos: int


@dataclass(frozen=True)
class Hecho:
    """El consumidor terminó con el evento (envió, omitió o no tenía nada que hacer)."""


@dataclass(frozen=True)
class Reintentar:
    """Algo falló de forma pasajera: el evento vuelve con backoff y suma un intento."""


@dataclass(frozen=True)
class Posponer:
    """Todavía no es hora: el evento vuelve en ``hasta``, sin sumar un intento."""

    hasta: datetime


ResultadoConsumo = Hecho | Reintentar | Posponer


class Consumidor(Protocol):
    """Quien reacciona a un tipo de evento. Debe ser idempotente: el evento puede llegar más de una vez."""

    nombre: str

    def consumir(self, evento: EventoTomado) -> ResultadoConsumo: ...


class AlmacenOutbox(Protocol):
    """El outbox en la base. Implementación: AlmacenOutboxSql (app/shared/outbox_sql.py)."""

    def tomar(self, cantidad: int, ahora: datetime, grupo_id: uuid.UUID | None = None) -> list[EventoTomado]:
        """Arrienda hasta ``cantidad`` eventos pendientes y disponibles en ``ahora``."""
        ...

    def publicado(self, evento_id: int, ahora: datetime) -> None: ...

    def reintentar(self, evento_id: int, disponible_en: datetime, ahora: datetime) -> bool:
        """Suma un intento. Devuelve True si el evento quedó fallido (tope de 8)."""
        ...

    def posponer(self, evento_id: int, hasta: datetime, ahora: datetime) -> None: ...


def siguiente_intento(intentos_previos: int, ahora: datetime) -> datetime | None:
    """Cuándo vuelve un evento que falló por ``intentos_previos + 1``-ésima vez, o None si con este fallo
    llega al tope de 8 y queda fallido."""
    if intentos_previos < 0:
        raise ValueError("intentos_previos no puede ser negativo")
    if intentos_previos + 1 >= TOPE_INTENTOS:
        return None
    return ahora + BACKOFF[intentos_previos]


@dataclass(frozen=True)
class ResultadoPublicacion:
    publicados: int = 0
    reintentos: int = 0
    fallidos: int = 0
    pospuestos: int = 0


def _consumir(consumidor: Consumidor, evento: EventoTomado) -> ResultadoConsumo:
    try:
        return consumidor.consumir(evento)
    except Exception as error:  # noqa: BLE001 - un consumidor que falla no detiene al publicador
        # Solo el tipo: el mensaje de la excepción puede traer valores de la base
        log.warning(
            "consumidor fallo", extra={"evento_id": evento.id, "tipo_error": type(error).__name__}
        )
        return Reintentar()


def publicar_vuelta(
    almacen: AlmacenOutbox,
    consumidores: Mapping[str, Sequence[Consumidor]],
    reloj: Reloj,
    *,
    cantidad: int = LOTE,
    grupo_id: uuid.UUID | None = None,
) -> tuple[ResultadoPublicacion, int]:
    """Una vuelta: toma hasta ``cantidad`` eventos y los entrega. Devuelve el resultado y cuántos tomó."""
    publicados = reintentos = fallidos = pospuestos = 0
    eventos = almacen.tomar(cantidad, reloj.ahora(), grupo_id)
    for evento in eventos:
        resultados = [_consumir(c, evento) for c in consumidores.get(evento.tipo, ())]
        ahora = reloj.ahora()
        if any(isinstance(r, Reintentar) for r in resultados):
            disponible = siguiente_intento(evento.intentos, ahora) or ahora
            if almacen.reintentar(evento.id, disponible, ahora):
                fallidos += 1
                log.warning("evento fallido", extra={"evento_id": evento.id})
            else:
                reintentos += 1
                log.info("evento reintentado", extra={"evento_id": evento.id})
        elif pospuesto := [r.hasta for r in resultados if isinstance(r, Posponer)]:
            almacen.posponer(evento.id, max(pospuesto), ahora)
            pospuestos += 1
        else:
            almacen.publicado(evento.id, ahora)
            publicados += 1
    return ResultadoPublicacion(publicados, reintentos, fallidos, pospuestos), len(eventos)


def publicar_pendientes(
    almacen: AlmacenOutbox,
    consumidores: Mapping[str, Sequence[Consumidor]],
    reloj: Reloj,
    *,
    cantidad: int = LOTE,
    grupo_id: uuid.UUID | None = None,
    max_vueltas: int = 50,
) -> ResultadoPublicacion:
    """Vueltas hasta que no quedan eventos disponibles (o ``max_vueltas``). Un evento reintentado o
    pospuesto queda con disponible_en en el futuro y no se vuelve a tomar en esta corrida."""
    total = ResultadoPublicacion()
    for _ in range(max_vueltas):
        vuelta, tomados = publicar_vuelta(almacen, consumidores, reloj, cantidad=cantidad, grupo_id=grupo_id)
        total = ResultadoPublicacion(
            total.publicados + vuelta.publicados,
            total.reintentos + vuelta.reintentos,
            total.fallidos + vuelta.fallidos,
            total.pospuestos + vuelta.pospuestos,
        )
        if tomados < cantidad:
            break
    return total
