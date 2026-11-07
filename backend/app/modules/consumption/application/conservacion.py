"""Caso de uso de conservación del consumo (MATU-36, decisión 70).

El consumo de una persona (activo o no) se borra 90 días después de que termina su autorización para
``consumo``: cuando ya no hay una no revocada y la última se revocó hace 90 días o más. El límite lo
calcula el dominio con el puerto Reloj.
"""

from dataclasses import dataclass

from app.modules.consumption.application.ports import ConservacionConsumo, ConservacionQuiebres
from app.modules.consumption.domain.alerta import limites_conservacion
from app.modules.consumption.domain.perfil import limite_conservacion
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class ResultadoConservacionConsumo:
    perfiles_borrados: int


def conservar(*, unidad: ConservacionConsumo, reloj: Reloj) -> ResultadoConservacionConsumo:
    ahora = reloj.ahora()
    return ResultadoConservacionConsumo(perfiles_borrados=unidad.conservar(limite_conservacion(ahora), ahora))


@dataclass(frozen=True)
class ResultadoConservacionQuiebres:
    """MATU-37, decisión 77: alertas cerradas y notificaciones a los 90 días, eventos publicados a los 30.
    MATU-51, decisión 145: las compras declaradas a los 90 días de registrada_en."""

    alertas_borradas: int
    eventos_borrados: int
    notificaciones_borradas: int
    reposiciones_borradas: int = 0


def conservar_quiebres(*, unidad: ConservacionQuiebres, reloj: Reloj) -> ResultadoConservacionQuiebres:
    ahora = reloj.ahora()
    limite_alertas, limite_eventos = limites_conservacion(ahora)
    alertas, eventos, notificaciones, reposiciones = unidad.conservar(limite_alertas, limite_eventos, ahora)
    return ResultadoConservacionQuiebres(
        alertas_borradas=alertas,
        eventos_borrados=eventos,
        notificaciones_borradas=notificaciones,
        reposiciones_borradas=reposiciones,
    )
