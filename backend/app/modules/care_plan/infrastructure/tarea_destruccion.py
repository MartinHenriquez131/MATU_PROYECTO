"""Tarea de destrucción de las fichas retiradas hace 90 días (MATU-44, D3, decisión 129).

La corre el programador de tareas (MATU-74), desde backend/ y con DATABASE_URL de matu_app:

    python -m app.tareas destruccion_fichas

Fija app.rol = 'operacion' y llama a plan_destruir_claves (migración 0016), SECURITY DEFINER y acotada,
que destruye las claves y registra clave.destruir en la misma sentencia. Es idempotente. Operación no lee
ninguna clave: la función solo devuelve un contador. El log lleva solo ese contador, nunca un
identificador ni un dato de la ficha.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones, sesion_tenant
from app.core.logs import configurar_logs
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


def ejecutar(fabrica: sessionmaker[Session] | None = None, reloj: Reloj | None = None) -> ResultadoDestruccion:
    resultado = destruir_fichas_retiradas(
        unidad=DestruccionClavesSql(fabrica or fabrica_sesiones()), reloj=reloj or RelojSistema()
    )
    log.info("destruccion de fichas retiradas: %d claves destruidas", resultado.claves_destruidas)
    return resultado


if __name__ == "__main__":  # pragma: no cover
    configurar_logs(obtener_configuracion().log_nivel)
    ejecutar()
