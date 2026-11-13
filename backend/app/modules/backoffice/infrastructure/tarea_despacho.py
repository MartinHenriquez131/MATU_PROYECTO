"""Tarea del despacho (MATU-63, D-63-8): lleva al día los pedidos pagados que quedaron atrás de sus partes y devuelve
los faltantes que no se devolvieron al marcar «Listo» (la pasarela no respondió, o la transacción del sistema no
alcanzó a correr después de la del comercio).

La corre el programador de tareas cada 5 minutos, desde backend/:

    python -m app.tareas despacho

Usa SCHEDULER_DATABASE_URL (matu_scheduler) para despacho_pendiente, que entrega solo ids, y DATABASE_URL (matu_app)
para cada pedido, con app.rol = 'sistema' y su grupo. Un pedido que falla no detiene a los demás. El log lleva solo
contadores.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Configuracion
from app.modules.backoffice.application.despacho import llevar
from app.modules.backoffice.infrastructure.sistema import AbrirDespachoSQL, pendientes
from app.modules.payments.application.ports import PasarelaWebpay
from app.modules.payments.infrastructure.pasarela import pasarela_desde
from app.shared.puertos import Reloj

log = logging.getLogger("matu.backoffice.despacho")

LOTE = 200


@dataclass(frozen=True)
class ResultadoDespacho:
    revisados: int = 0
    avanzados: int = 0
    fallidos: int = 0


def ejecutar(
    config: Configuracion,
    fabrica: sessionmaker[Session],
    fabrica_scheduler: sessionmaker[Session],
    reloj: Reloj,
    pasarela: PasarelaWebpay | None = None,
) -> ResultadoDespacho:
    pasarela = pasarela if pasarela is not None else pasarela_desde(config)
    abrir = AbrirDespachoSQL(fabrica, reloj)
    revisados = avanzados = fallidos = 0
    for pedido_id, grupo_id in pendientes(fabrica_scheduler, LOTE):
        revisados += 1
        try:
            with abrir(grupo_id) as (unidad, _):
                if llevar(unidad, pasarela, pedido_id, reloj.ahora()):
                    avanzados += 1
        except Exception as error:  # noqa: BLE001 - un pedido que falla no detiene a los demás
            fallidos += 1
            log.warning("pedido del despacho fallo", extra={"tipo_error": type(error).__name__})
    log.info("despacho: %d revisados, %d avanzados, %d fallidos", revisados, avanzados, fallidos)
    return ResultadoDespacho(revisados, avanzados, fallidos)
