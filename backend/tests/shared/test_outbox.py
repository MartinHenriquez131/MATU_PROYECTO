"""MATU-41 · El publicador del outbox con un outbox en memoria (arquitectura 8.6, decisión 106). Sin base.

Al menos una vez, reintentos con backoff y tope de 8, posponer sin sumar un intento, y un consumidor que
lanza no detiene al publicador ni deja su mensaje en el log.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.shared.outbox import (
    BACKOFF,
    TOPE_INTENTOS,
    EventoTomado,
    Hecho,
    Posponer,
    Reintentar,
    ResultadoConsumo,
    publicar_pendientes,
    siguiente_intento,
)
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-39")

AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
TIPO = "QuiebreProximo"


@dataclass
class Fila:
    id: int
    tipo: str = TIPO
    disponible_en: datetime = AHORA
    intentos: int = 0
    publicado_en: datetime | None = None
    fallido_en: datetime | None = None


@dataclass
class OutboxEnMemoria:
    """Lo que hacen las funciones outbox_* de la migración 0014, sin el arriendo."""

    filas: dict[int, Fila] = field(default_factory=dict)

    def agregar(self, fila: Fila) -> Fila:
        self.filas[fila.id] = fila
        return fila

    def tomar(self, cantidad: int, ahora: datetime, grupo_id: uuid.UUID | None = None) -> list[EventoTomado]:
        pendientes = [
            f for f in sorted(self.filas.values(), key=lambda f: f.id)
            if f.publicado_en is None and f.fallido_en is None and f.disponible_en <= ahora
        ][:cantidad]
        for f in pendientes:
            f.disponible_en = ahora + timedelta(minutes=5)
        return [EventoTomado(f.id, uuid.uuid4(), f.tipo, {}, f.intentos) for f in pendientes]

    def publicado(self, evento_id: int, ahora: datetime) -> None:
        self.filas[evento_id].publicado_en = ahora

    def reintentar(self, evento_id: int, disponible_en: datetime, ahora: datetime) -> bool:
        fila = self.filas[evento_id]
        fila.intentos += 1
        if fila.intentos >= TOPE_INTENTOS:
            fila.fallido_en = ahora
            return True
        fila.disponible_en = disponible_en
        return False

    def posponer(self, evento_id: int, hasta: datetime, ahora: datetime) -> None:
        self.filas[evento_id].disponible_en = hasta


@dataclass
class ConsumidorProgramado:
    respuestas: list[ResultadoConsumo | Exception]
    nombre: str = "prueba"
    vistos: list[int] = field(default_factory=list)

    def consumir(self, evento: EventoTomado) -> ResultadoConsumo:
        self.vistos.append(evento.id)
        respuesta = self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


def test_siguiente_intento_sigue_el_backoff_y_corta_en_el_octavo() -> None:
    esperados = [AHORA + espera for espera in BACKOFF[:7]]
    assert [siguiente_intento(n, AHORA) for n in range(7)] == esperados
    assert BACKOFF[:4] == (timedelta(seconds=1), timedelta(seconds=5), timedelta(seconds=30), timedelta(minutes=2))
    assert siguiente_intento(7, AHORA) is None
    with pytest.raises(ValueError):
        siguiente_intento(-1, AHORA)


def test_un_evento_consumido_queda_publicado() -> None:
    outbox = OutboxEnMemoria()
    outbox.agregar(Fila(1))
    consumidor = ConsumidorProgramado([Hecho()])

    resultado = publicar_pendientes(outbox, {TIPO: [consumidor]}, RelojFijo(AHORA))

    assert resultado.publicados == 1 and outbox.filas[1].publicado_en == AHORA
    assert consumidor.vistos == [1]


def test_reintentar_suma_un_intento_con_backoff_y_al_octavo_queda_fallido(caplog: pytest.LogCaptureFixture) -> None:
    outbox = OutboxEnMemoria()
    outbox.agregar(Fila(1))
    consumidor = ConsumidorProgramado([Reintentar()])
    reloj = RelojFijo(AHORA)

    primero = publicar_pendientes(outbox, {TIPO: [consumidor]}, reloj)
    assert primero.reintentos == 1
    assert (outbox.filas[1].intentos, outbox.filas[1].disponible_en) == (1, AHORA + timedelta(seconds=1))

    with caplog.at_level(logging.WARNING, logger="matu.outbox"):
        for _ in range(7):
            reloj.avanzar(timedelta(hours=3))
            publicar_pendientes(outbox, {TIPO: [consumidor]}, reloj)
    fila = outbox.filas[1]
    assert fila.intentos == TOPE_INTENTOS and fila.fallido_en is not None and fila.publicado_en is None
    avisos = [r.message for r in caplog.records if r.name == "matu.outbox" and r.levelno >= logging.WARNING]
    assert avisos == ["evento fallido"]
    # Fallido no se reintenta solo
    reloj.avanzar(timedelta(days=1))
    assert publicar_pendientes(outbox, {TIPO: [consumidor]}, reloj).publicados == 0
    assert len(consumidor.vistos) == TOPE_INTENTOS


def test_posponer_no_suma_un_intento() -> None:
    outbox = OutboxEnMemoria()
    outbox.agregar(Fila(1))
    hasta = AHORA + timedelta(hours=5)

    resultado = publicar_pendientes(outbox, {TIPO: [ConsumidorProgramado([Posponer(hasta)])]}, RelojFijo(AHORA))

    assert resultado.pospuestos == 1
    assert (outbox.filas[1].intentos, outbox.filas[1].disponible_en) == (0, hasta)


def test_un_consumidor_que_lanza_se_reintenta_sin_dejar_su_mensaje_en_el_log(caplog: pytest.LogCaptureFixture) -> None:
    outbox = OutboxEnMemoria()
    outbox.agregar(Fila(1))
    outbox.agregar(Fila(2))
    email = "carmen.soto@correo.ejemplo"
    consumidor = ConsumidorProgramado([RuntimeError(email), Hecho()])

    with caplog.at_level(logging.DEBUG):
        resultado = publicar_pendientes(outbox, {TIPO: [consumidor]}, RelojFijo(AHORA))

    assert (resultado.reintentos, resultado.publicados) == (1, 1)
    assert outbox.filas[2].publicado_en == AHORA  # el evento siguiente no se detiene
    assert email not in caplog.text
    assert any(getattr(r, "tipo_error", None) == "RuntimeError" for r in caplog.records)


def test_un_tipo_sin_consumidor_se_marca_publicado() -> None:
    outbox = OutboxEnMemoria()
    outbox.agregar(Fila(1, tipo="PedidoEntregado"))

    assert publicar_pendientes(outbox, {TIPO: [ConsumidorProgramado([Reintentar()])]}, RelojFijo(AHORA)).publicados == 1


def test_con_dos_consumidores_uno_que_reintenta_reintenta_el_evento() -> None:
    outbox = OutboxEnMemoria()
    outbox.agregar(Fila(1))
    bien, mal = ConsumidorProgramado([Hecho()]), ConsumidorProgramado([Reintentar()])

    publicar_pendientes(outbox, {TIPO: [bien, mal]}, RelojFijo(AHORA))

    assert outbox.filas[1].publicado_en is None and outbox.filas[1].intentos == 1


def test_los_no_disponibles_no_se_toman() -> None:
    outbox = OutboxEnMemoria()
    outbox.agregar(Fila(1, disponible_en=AHORA + timedelta(minutes=1)))
    consumidor = ConsumidorProgramado([Hecho()])

    assert publicar_pendientes(outbox, {TIPO: [consumidor]}, RelojFijo(AHORA)).publicados == 0
    assert consumidor.vistos == []


def test_toma_por_lotes_hasta_vaciar() -> None:
    outbox = OutboxEnMemoria()
    for i in range(1, 8):
        outbox.agregar(Fila(i))

    resultado = publicar_pendientes(outbox, {TIPO: [ConsumidorProgramado([Hecho()])]}, RelojFijo(AHORA), cantidad=3)

    assert resultado.publicados == 7
