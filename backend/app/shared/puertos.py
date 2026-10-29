"""Puertos transversales: los que usa más de un módulo (ADR-021).

Los puertos de un solo módulo viven en application/ports.py de ese módulo.
"""

from datetime import datetime
from typing import Protocol

from app.shared.auditoria import EntradaAuditoria


class Reloj(Protocol):
    """La hora actual, entregada desde afuera.

    Ninguna regla de dominio llama a datetime.now(): recibe un Reloj. Así el vencimiento
    del acceso de relevo o la predicción de quiebre se prueban con un RelojFijo, sin esperar.

    Implementaciones: RelojSistema (app/shared/reloj_sistema.py) y RelojFijo (tests/dobles).
    """

    def ahora(self) -> datetime:
        """Devuelve el instante actual, siempre con zona horaria y en UTC."""
        ...


class RegistroAuditoria(Protocol):
    """Deja constancia de una acción en la auditoría (MATU-14, RF-08).

    Un solo método, de escritura. Sin lectura, actualización ni borrado: la auditoría es de solo
    inserción, por permiso y por trigger. Sin IP ni user agent: no se guardan (decisión 27 del
    contrato de MATU-09).

    El caso de uso llama a registrar() dentro de la misma transacción de la acción que audita. Si
    registrar() falla, la excepción sube y la acción completa se deshace: sin la fila de auditoría
    no hay respuesta.

    Implementaciones: RegistroAuditoriaSql (app/shared/auditoria_sql.py) y RegistroAuditoriaEnMemoria
    (tests/dobles).
    """

    def registrar(self, entrada: EntradaAuditoria) -> None:
        """Inserta una fila con la entrada y el instante del Reloj. Lanza si no puede."""
        ...
