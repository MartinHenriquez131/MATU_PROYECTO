"""Tarea de conservación de las invitaciones cerradas (MATU-42, D-42-6).

La corre el programador de tareas (MATU-74), desde backend/ y con SCHEDULER_DATABASE_URL de matu_scheduler:

    python -m app.tareas conservacion_invitaciones

Fija app.rol = 'operacion' y llama a invitacion_conservar (migración 0026, solo la ejecuta matu_scheduler), que borra
las invitaciones aceptadas, anuladas, bloqueadas o vencidas hace 30 días o más, con su indice_token. El log lleva solo
el contador. La auditoría se queda: solo lleva identificadores y el rol.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.care_circle.domain.invitaciones import CONSERVACION
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.care_circle.conservacion")

_CONSERVAR = text("SELECT invitacion_conservar(:limite, :ahora) AS borradas")


@dataclass(frozen=True)
class ResultadoConservacionInvitaciones:
    invitaciones_borradas: int


def limite_cerradas(ahora: datetime) -> datetime:
    return ahora - CONSERVACION


def ejecutar(fabrica: sessionmaker[Session], reloj: Reloj | None = None) -> ResultadoConservacionInvitaciones:
    """fabrica es la de matu_scheduler (app/tareas.py)."""
    ahora = (reloj or RelojSistema()).ahora()
    with sesion_tenant(fabrica, rol="operacion") as sesion:
        borradas = int(sesion.execute(_CONSERVAR, {"limite": limite_cerradas(ahora), "ahora": ahora}).scalar_one())
    log.info("conservacion de invitaciones: %d borradas", borradas)
    return ResultadoConservacionInvitaciones(invitaciones_borradas=borradas)
