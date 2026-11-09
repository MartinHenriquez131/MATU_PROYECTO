"""Tarea de destrucción de las fichas retiradas hace 90 días (MATU-44, D3, decisión 129).

La corre el programador de tareas (MATU-74), desde backend/ y con SCHEDULER_DATABASE_URL de matu_scheduler:

    python -m app.tareas destruccion_fichas

Fija app.rol = 'operacion' y llama a plan_destruir_claves (migración 0016; desde la 0022 solo la ejecuta
matu_scheduler), SECURITY DEFINER y acotada,
que destruye las claves y registra clave.destruir en la misma sentencia. Es idempotente. Operación no lee
ninguna clave: la función solo devuelve un contador. El log lleva solo ese contador, nunca un
identificador ni un dato de la ficha.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.care_plan.application.destruccion import ResultadoDestruccion, destruir_fichas_retiradas
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.care_plan.destruccion")

_DESTRUIR = text("SELECT plan_destruir_claves(:limite, :ahora) AS destruidas")


class DestruccionClavesSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def destruir(self, limite: datetime, ahora: datetime) -> int:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            return int(sesion.execute(_DESTRUIR, {"limite": limite, "ahora": ahora}).scalar_one())


def ejecutar(fabrica: sessionmaker[Session], reloj: Reloj | None = None) -> ResultadoDestruccion:
    """fabrica es la de matu_scheduler (app/tareas.py): matu_app ya no ejecuta plan_destruir_claves."""
    resultado = destruir_fichas_retiradas(unidad=DestruccionClavesSql(fabrica), reloj=reloj or RelojSistema())
    log.info("destruccion de fichas retiradas: %d claves destruidas", resultado.claves_destruidas)
    return resultado
