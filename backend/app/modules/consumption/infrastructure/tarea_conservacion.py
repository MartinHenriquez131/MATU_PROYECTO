"""Tarea de conservación del consumo (MATU-36, decisión 70).

Igual que la de iam (MATU-38): sin programador de tareas todavía, se invoca a mano o desde cron, desde
backend/ y con DATABASE_URL de matu_app:

    python -m app.modules.consumption.infrastructure.tarea_conservacion

Fija app.rol = 'operacion' y llama a consumo_conservar (migración 0009), que borra los perfiles de
consumo de las personas cuya autorización para ``consumo`` terminó hace 90 días o más. Operación no ve
ninguna fila de perfil_consumo: la función, SECURITY DEFINER y acotada, solo borra y devuelve un
contador. El log lleva solo ese contador, nunca un identificador ni un dato de las filas.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones, sesion_tenant
from app.core.logs import configurar_logs
from app.modules.consumption.application.conservacion import ResultadoConservacionConsumo, conservar
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.consumption.conservacion")

_CONSERVAR = text("SELECT consumo_conservar(:limite, :ahora) AS borrados")


class ConservacionConsumoSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def conservar(self, limite: datetime, ahora: datetime) -> int:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            return int(sesion.execute(_CONSERVAR, {"limite": limite, "ahora": ahora}).scalar_one())


def ejecutar() -> ResultadoConservacionConsumo:
    resultado = conservar(unidad=ConservacionConsumoSql(fabrica_sesiones()), reloj=RelojSistema())
    log.info("conservacion del consumo: %d perfiles borrados", resultado.perfiles_borrados)
    return resultado


if __name__ == "__main__":  # pragma: no cover
    configurar_logs(obtener_configuracion().log_nivel)
    ejecutar()
