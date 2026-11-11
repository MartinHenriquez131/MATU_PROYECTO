"""Tarea de conservación de los pedidos no pagados (MATU-61, D5).

La corre el programador de tareas (MATU-74), desde backend/ y con SCHEDULER_DATABASE_URL de matu_scheduler:

    python -m app.tareas conservacion_pedidos

Fija app.rol = 'operacion' y llama a pedido_conservar (migración 0023, solo la ejecuta matu_scheduler). La función,
SECURITY DEFINER y acotada, borra y devuelve dos contadores. El log lleva solo esos contadores. Es capa 3: app.tareas
la importa solo con CAPA3_HABILITADA.
"""

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.ordering.application.conservacion import ResultadoConservacionPedidos, conservar
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.ordering.conservacion")

_CONSERVAR = text("SELECT pedidos, idempotencias FROM pedido_conservar(:limite, :ahora)")


class ConservacionPedidosSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def conservar(self, limite: datetime, ahora: datetime) -> tuple[int, int]:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            fila = sesion.execute(_CONSERVAR, {"limite": limite, "ahora": ahora}).one()
            return int(fila.pedidos), int(fila.idempotencias)


def ejecutar(fabrica: sessionmaker[Session], reloj: Reloj | None = None) -> ResultadoConservacionPedidos:
    """fabrica es la de matu_scheduler (app/tareas.py)."""
    resultado = conservar(unidad=ConservacionPedidosSql(fabrica), reloj=reloj or RelojSistema())
    log.info(
        "conservacion de pedidos: %d pedidos y %d claves borrados",
        resultado.pedidos_borrados,
        resultado.claves_borradas,
    )
    return resultado
