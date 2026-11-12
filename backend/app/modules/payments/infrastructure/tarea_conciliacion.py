"""Tarea de conciliación de los pagos (MATU-62, D-62-5; arquitectura 8.4, defensa 2).

La corre el programador de tareas (MATU-74) cada 5 minutos, desde backend/:

    python -m app.tareas conciliacion_pagos

Usa dos conexiones: SCHEDULER_DATABASE_URL (matu_scheduler) para pagos_por_conciliar, que entrega solo ids, y
DATABASE_URL (matu_app) para cerrar cada venta con app.rol = 'sistema' y su grupo. **Corre también con
CAPA3_HABILITADA apagada** (D-62-17, decisión 241): app.tareas la importa al correr, no al cargarse. Sin
PASARELA_PAGO no llama a nadie y no cambia nada. El log lleva solo contadores.
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Configuracion
from app.modules.payments.application.conciliacion import ResultadoConciliacion, conciliar
from app.modules.payments.application.ports import PasarelaWebpay
from app.modules.payments.infrastructure.pasarela import pasarela_desde
from app.modules.payments.infrastructure.sistema import AbrirGrupoSQL, ListarPorConciliarSQL
from app.shared.puertos import Reloj

log = logging.getLogger("matu.payments.conciliacion")


def ejecutar(
    config: Configuracion,
    fabrica: sessionmaker[Session],
    fabrica_scheduler: sessionmaker[Session],
    reloj: Reloj,
    pasarela: PasarelaWebpay | None = None,
) -> ResultadoConciliacion:
    pasarela = pasarela if pasarela is not None else pasarela_desde(config)
    resultado = conciliar(
        ListarPorConciliarSQL(fabrica_scheduler),
        AbrirGrupoSQL(fabrica, reloj),
        pasarela,
        reloj.ahora(),
        timedelta(minutes=config.vida_venta_webpay_minutos),
    )
    log.info(
        "conciliacion de pagos: %d revisadas, %d cerradas, %d pendientes, %d anulaciones hechas, %d fallidas",
        resultado.revisadas,
        resultado.cerradas,
        resultado.pendientes,
        resultado.anulaciones_hechas,
        resultado.fallidas,
    )
    return resultado
