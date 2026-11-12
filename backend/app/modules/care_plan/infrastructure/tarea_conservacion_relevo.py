"""Tarea de conservación del teléfono del relevo (MATU-46, decisión 25).

La corre el programador de tareas (MATU-74), desde backend/ y con SCHEDULER_DATABASE_URL de matu_scheduler:

    python -m app.tareas conservacion_relevo

Fija app.rol = 'operacion' y llama a relevo_conservar (migración 0027, solo la ejecuta matu_scheduler), que vacía el
teléfono de los accesos que vencieron o se cortaron hace 30 días o más. Corre siempre: no depende de la capa 3. El
log lleva solo el contador, nunca un teléfono ni un id.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.care_plan.application.conservacion_relevo import ResultadoConservacionRelevo, conservar
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.care_plan.conservacion_relevo")

_CONSERVAR = text("SELECT relevo_conservar(:limite, :ahora) AS borrados")


class ConservacionRelevoSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def conservar(self, limite: datetime, ahora: datetime) -> int:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            return int(sesion.execute(_CONSERVAR, {"limite": limite, "ahora": ahora}).scalar_one())


def ejecutar(fabrica: sessionmaker[Session], reloj: Reloj | None = None) -> ResultadoConservacionRelevo:
    """fabrica es la de matu_scheduler (app/tareas.py)."""
    resultado = conservar(unidad=ConservacionRelevoSql(fabrica), reloj=reloj or RelojSistema())
    log.info("conservacion del relevo: %d telefonos borrados", resultado.telefonos_borrados)
    return resultado
