"""Tarea de conservación de sesiones y dispositivos (MATU-38, decisión 59).

La corre el programador de tareas (MATU-74), desde backend/ y con DATABASE_URL de matu_app:

    python -m app.tareas conservacion_sesiones

Fija app.rol = 'operacion' y llama a iam_conservar (migración 0008), que borra las sesiones 30 días
después de vencer o de revocarse y los dispositivos 90 días después de su último uso sin sesiones
vigentes. Escribe en el log solo los dos contadores, nunca un identificador ni un dato de las filas.
"""

import logging

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones
from app.core.logs import configurar_logs
from app.modules.iam.application.sesiones import ResultadoConservacion, conservar
from app.modules.iam.infrastructure.repositorio_sesiones import UnidadIamSql
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.iam.conservacion")


def ejecutar(fabrica: sessionmaker[Session] | None = None, reloj: Reloj | None = None) -> ResultadoConservacion:
    reloj = reloj or RelojSistema()
    resultado = conservar(unidad=UnidadIamSql(fabrica or fabrica_sesiones(), reloj), reloj=reloj)
    log.info(
        "conservacion de sesiones: %d sesiones y %d dispositivos borrados",
        resultado.sesiones_borradas,
        resultado.dispositivos_borrados,
    )
    return resultado


if __name__ == "__main__":  # pragma: no cover
    configurar_logs(obtener_configuracion().log_nivel)
    ejecutar()
