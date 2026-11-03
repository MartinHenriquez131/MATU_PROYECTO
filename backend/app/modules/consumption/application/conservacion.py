"""Caso de uso de conservación del consumo (MATU-36, decisión 67).

El consumo de una persona (activo o no) se borra 90 días después de que termina su autorización para
``consumo``: cuando ya no hay una no revocada y la última se revocó hace 90 días o más. El límite lo
calcula el dominio con el puerto Reloj.
"""

from dataclasses import dataclass

from app.modules.consumption.application.ports import ConservacionConsumo
from app.modules.consumption.domain.perfil import limite_conservacion
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class ResultadoConservacionConsumo:
    perfiles_borrados: int


def conservar(*, unidad: ConservacionConsumo, reloj: Reloj) -> ResultadoConservacionConsumo:
    ahora = reloj.ahora()
    return ResultadoConservacionConsumo(perfiles_borrados=unidad.conservar(limite_conservacion(ahora), ahora))
