"""Caso de uso: destruir la ficha 90 días después del retiro de su autorización (MATU-44, D3, decisión 129).

La clave de datos de cada persona sin una autorización no revocada para plan_cuidado, y cuya última
revocación es igual o anterior al límite, se destruye: la ficha y las secciones quedan ilegibles para
siempre (borrado criptográfico de MATU-11). El límite sale del Reloj, nunca de la hora del sistema.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.care_circle.domain.retiro import PLAZO_BORRADO
from app.shared.puertos import Reloj


class DestruccionClaves(Protocol):
    """Implementación: DestruccionClavesSql (infrastructure/tarea_destruccion.py)."""

    def destruir(self, limite: datetime, ahora: datetime) -> int:
        """Destruye las claves que corresponden y devuelve cuántas."""
        ...


@dataclass(frozen=True)
class ResultadoDestruccion:
    claves_destruidas: int


def limite_destruccion(ahora: datetime) -> datetime:
    """Una revocación igual o anterior a este instante ya cumplió los 90 días."""
    return ahora - PLAZO_BORRADO


def destruir_fichas_retiradas(*, unidad: DestruccionClaves, reloj: Reloj) -> ResultadoDestruccion:
    ahora = reloj.ahora()
    return ResultadoDestruccion(claves_destruidas=unidad.destruir(limite_destruccion(ahora), ahora))
