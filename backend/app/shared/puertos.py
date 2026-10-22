"""Puertos transversales: los que usa más de un módulo (ADR-021).

Los puertos de un solo módulo viven en application/ports.py de ese módulo.
"""

from datetime import datetime
from typing import Protocol


class Reloj(Protocol):
    """La hora actual, entregada desde afuera.

    Ninguna regla de dominio llama a datetime.now(): recibe un Reloj. Así el vencimiento
    del acceso de relevo o la predicción de quiebre se prueban con un RelojFijo, sin esperar.

    Implementaciones: RelojSistema (app/shared/reloj_sistema.py) y RelojFijo (tests/dobles).
    """

    def ahora(self) -> datetime:
        """Devuelve el instante actual, siempre con zona horaria y en UTC."""
        ...
