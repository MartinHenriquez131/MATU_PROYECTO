"""Tarea del publicador del outbox con el consumidor de avisos (MATU-41, decisiones 106 y 112).

La corre el programador de tareas (MATU-74) cada 5 minutos, el mínimo de Railway, desde backend/. Usa dos
conexiones (H2, migración 0022): PUBLISHER_DATABASE_URL de matu_publisher para el outbox y DATABASE_URL de
matu_app para el consumidor:

    python -m app.tareas avisos

1. Sin ENVIADOR_AVISOS no hace nada: no toma eventos, así que ninguno se marca publicado sin avisar.
2. Toma los eventos como matu_publisher, con app.rol = 'operacion' (funciones outbox_* de la migración 0014),
   y entrega cada ``QuiebreProximo`` al consumidor de avisos, que trabaja como matu_app con app.rol =
   'sistema' y el grupo del evento.
3. Los demás tipos no tienen consumidor todavía y se marcan publicados.

Dos corridas que se cruzan (una que pasa de 5 minutos y la siguiente) no envían dos veces: el arriendo del
outbox dura 5 minutos, pero el consumidor bloquea cada notificación (FOR UPDATE) y no reenvía una
``enviada``.

El registro de lo enviado es la tabla notificacion (estado y enviada_en, H4). El archivo REGISTRO_AVISOS del
envío simulado se escribe solo con ENTORNO en ENTORNOS_REGISTRO_AVISOS (local y pruebas): en staging se
perdía con cada contenedor del cron.

El log lleva solo contadores e identificadores, nunca un email, un token ni el texto.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import ENTORNOS_REGISTRO_AVISOS, RAIZ_REPOSITORIO, Configuracion
from app.modules.consumption.events import QUIEBRE_PROXIMO
from app.modules.notifications.application.avisos import ConsumidorQuiebreProximo
from app.modules.notifications.infrastructure.enviadores_simulados import (
    EnviadorCorreoSimulado,
    EnviadorPushSimulado,
    RegistroAvisosSimulado,
)
from app.modules.notifications.infrastructure.repositorio_avisos import UnidadAvisosSQL
from app.shared.outbox import Consumidor, ResultadoPublicacion, publicar_pendientes
from app.shared.outbox_sql import AlmacenOutboxSql
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.notifications.tarea")

REGISTRO_POR_OMISION = RAIZ_REPOSITORIO / ".dev" / "avisos.jsonl"


def encendidos(config: Configuracion) -> bool:
    """Si los avisos están encendidos (ENVIADOR_AVISOS). Apagados, la tarea no abre ninguna conexión."""
    return config.enviador_avisos == "simulado"


def avisar_apagados() -> None:
    log.warning("avisos apagados: falta ENVIADOR_AVISOS, no se toma ningun evento")


def archivo_del_registro(config: Configuracion) -> Path | None:
    """El archivo del envío simulado, o None fuera de ENTORNOS_REGISTRO_AVISOS (H4): ahí no se escribe."""
    if config.entorno not in ENTORNOS_REGISTRO_AVISOS:
        return None
    return config.registro_avisos or REGISTRO_POR_OMISION


def consumidores(
    config: Configuracion, fabrica: sessionmaker[Session], reloj: Reloj
) -> dict[str, list[Consumidor]] | None:
    """El mapa tipo -> consumidores, o None si los avisos están apagados (sin ENVIADOR_AVISOS)."""
    if not encendidos(config):
        return None
    registro = RegistroAvisosSimulado(reloj, archivo_del_registro(config))
    consumidor = ConsumidorQuiebreProximo(
        unidad=UnidadAvisosSQL(fabrica),
        correo=EnviadorCorreoSimulado(registro),
        push=EnviadorPushSimulado(registro),
        reloj=reloj,
        origen_web=config.origen_web,
    )
    return {QUIEBRE_PROXIMO: [consumidor]}


def ejecutar(
    config: Configuracion,
    fabrica: sessionmaker[Session],
    publisher: sessionmaker[Session],
    reloj: Reloj | None = None,
) -> ResultadoPublicacion | None:
    """fabrica es la de matu_app (el consumidor) y publisher la de matu_publisher (el outbox)."""
    reloj = reloj or RelojSistema()
    mapa = consumidores(config, fabrica, reloj)
    if mapa is None:
        avisar_apagados()
        return None
    resultado = publicar_pendientes(AlmacenOutboxSql(publisher), mapa, reloj)
    log.info(
        "outbox: %d publicados, %d reintentos, %d fallidos, %d pospuestos",
        resultado.publicados,
        resultado.reintentos,
        resultado.fallidos,
        resultado.pospuestos,
    )
    return resultado
