"""Tarea del publicador del outbox con el consumidor de avisos (MATU-41, decisiones 106 y 112).

Sin programador de tareas todavía (como tarea_quiebres): se invoca a mano o desde cron, por ejemplo cada
minuto, desde backend/ y con DATABASE_URL de matu_app:

    python -m app.modules.notifications.infrastructure.tarea_avisos

1. Sin ENVIADOR_AVISOS no hace nada: no toma eventos, así que ninguno se marca publicado sin avisar.
2. Toma los eventos con app.rol = 'operacion' (funciones outbox_* de la migración 0014) y entrega cada
   ``QuiebreProximo`` al consumidor de avisos, que trabaja con app.rol = 'sistema' y el grupo del evento.
3. Los demás tipos no tienen consumidor todavía y se marcan publicados.

El log lleva solo contadores e identificadores, nunca un email, un token ni el texto.
"""

import logging

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import RAIZ_REPOSITORIO, Configuracion, obtener_configuracion
from app.core.db import fabrica_sesiones
from app.core.logs import configurar_logs
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


def consumidores(
    config: Configuracion, fabrica: sessionmaker[Session], reloj: Reloj
) -> dict[str, list[Consumidor]] | None:
    """El mapa tipo -> consumidores, o None si los avisos están apagados (sin ENVIADOR_AVISOS)."""
    if config.enviador_avisos != "simulado":
        return None
    registro = RegistroAvisosSimulado(reloj, config.registro_avisos or REGISTRO_POR_OMISION)
    consumidor = ConsumidorQuiebreProximo(
        unidad=UnidadAvisosSQL(fabrica),
        correo=EnviadorCorreoSimulado(registro),
        push=EnviadorPushSimulado(registro),
        reloj=reloj,
        origen_web=config.origen_web,
    )
    return {QUIEBRE_PROXIMO: [consumidor]}


def ejecutar() -> ResultadoPublicacion | None:
    config = obtener_configuracion()
    fabrica = fabrica_sesiones()
    reloj = RelojSistema()
    mapa = consumidores(config, fabrica, reloj)
    if mapa is None:
        log.warning("avisos apagados: falta ENVIADOR_AVISOS, no se toma ningun evento")
        return None
    resultado = publicar_pendientes(AlmacenOutboxSql(fabrica), mapa, reloj)
    log.info(
        "outbox: %d publicados, %d reintentos, %d fallidos, %d pospuestos",
        resultado.publicados,
        resultado.reintentos,
        resultado.fallidos,
        resultado.pospuestos,
    )
    return resultado


if __name__ == "__main__":  # pragma: no cover
    configurar_logs(obtener_configuracion().log_nivel)
    ejecutar()
