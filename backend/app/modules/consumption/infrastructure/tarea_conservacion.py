"""Tarea de conservación del consumo (MATU-36, decisión 70).

La corre el programador de tareas (MATU-74), desde backend/ y con SCHEDULER_DATABASE_URL de matu_scheduler:

    python -m app.tareas conservacion_consumo

Fija app.rol = 'operacion' y llama a consumo_conservar (migración 0009; desde la 0022 solo la ejecuta
matu_scheduler), que borra los perfiles de
consumo de las personas cuya autorización para ``consumo`` terminó hace 90 días o más. Operación no ve
ninguna fila de perfil_consumo: la función, SECURITY DEFINER y acotada, solo borra y devuelve un
contador. El log lleva solo ese contador, nunca un identificador ni un dato de las filas.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.consumption.application.conservacion import ResultadoConservacionConsumo, conservar
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.consumption.conservacion")

_CONSERVAR = text("SELECT consumo_conservar(:limite, :ahora) AS borrados")


class ConservacionConsumoSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def conservar(self, limite: datetime, ahora: datetime) -> int:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            return int(sesion.execute(_CONSERVAR, {"limite": limite, "ahora": ahora}).scalar_one())


def ejecutar(fabrica: sessionmaker[Session], reloj: Reloj | None = None) -> ResultadoConservacionConsumo:
    """fabrica es la de matu_scheduler (app/tareas.py): matu_app ya no ejecuta consumo_conservar."""
    resultado = conservar(unidad=ConservacionConsumoSql(fabrica), reloj=reloj or RelojSistema())
    log.info("conservacion del consumo: %d perfiles borrados", resultado.perfiles_borrados)
    return resultado
