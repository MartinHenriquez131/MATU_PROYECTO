"""Doble del puerto RegistroAuditoria: guarda las entradas en una lista, en orden.

Para las pruebas unitarias de los casos de uso que auditan (MATU-12 y el relevo): verifican qué
se registró sin base. ``fallar_con`` simula que la base rechaza la fila, para probar que sin
auditoría la acción no responde.
"""

from app.shared.auditoria import EntradaAuditoria


class RegistroAuditoriaEnMemoria:
    def __init__(self) -> None:
        self._entradas: list[EntradaAuditoria] = []
        self._error: Exception | None = None

    @property
    def entradas(self) -> tuple[EntradaAuditoria, ...]:
        """Lo registrado, en orden. Una tupla: la prueba no puede borrar ni reescribir la auditoría."""
        return tuple(self._entradas)

    def fallar_con(self, error: Exception) -> None:
        """Desde ahora, registrar() lanza ``error`` y no guarda nada."""
        self._error = error

    def registrar(self, entrada: EntradaAuditoria) -> None:
        if self._error is not None:
            raise self._error
        if not isinstance(entrada, EntradaAuditoria):
            raise TypeError("registrar recibe una EntradaAuditoria")
        self._entradas.append(entrada)
