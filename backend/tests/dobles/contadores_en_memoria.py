"""Doble del puerto ContadoresEntrada (MATU-38): los contadores de la entrada en un diccionario.

Respeta la ventana de una hora desde el primer fallo con la hora que recibe (la del Reloj de la
prueba). Con caido=True, cada método lanza ContadoresNoDisponibles, como un Redis que no responde.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from app.modules.iam.application.ports import ContadoresNoDisponibles
from app.modules.iam.domain.demora import SIN_FALLOS, VENTANA_CONTADOR, ContadorFallos

if TYPE_CHECKING:
    from fastapi import FastAPI


class ContadoresEnMemoria:
    def __init__(self, caido: bool = False) -> None:
        self.caido = caido
        # huella → (fallos, primer fallo, último fallo)
        self.datos: dict[str, tuple[int, datetime, datetime]] = {}
        self._ahora: datetime | None = None

    def _revisar(self) -> None:
        if self.caido:
            raise ContadoresNoDisponibles()

    def _vigente(self, huella: str, ahora: datetime | None) -> tuple[int, datetime, datetime] | None:
        dato = self.datos.get(huella)
        if dato is not None and ahora is not None and ahora >= dato[1] + VENTANA_CONTADOR:
            del self.datos[huella]
            return None
        return dato

    def leer(self, huella: str) -> ContadorFallos:
        self._revisar()
        dato = self._vigente(huella, self._ahora)
        return SIN_FALLOS if dato is None else ContadorFallos(dato[0], dato[2])

    def sumar_fallo(self, huella: str, ahora: datetime) -> None:
        self._revisar()
        self._ahora = ahora
        dato = self._vigente(huella, ahora)
        self.datos[huella] = (1, ahora, ahora) if dato is None else (dato[0] + 1, dato[1], ahora)

    def borrar(self, huella: str) -> None:
        self._revisar()
        self.datos.pop(huella, None)


def demora_en_memoria(app: "FastAPI") -> ContadoresEnMemoria:
    """Sobreescribe en la app la llave y los contadores de la demora de la entrada (MATU-38), para las
    pruebas que inician sesión sin Redis. Devuelve los contadores."""
    import secrets

    from app.modules.iam.api.sesion_web import obtener_contadores, obtener_pepper_limites

    contadores = ContadoresEnMemoria()
    pepper_limites = secrets.token_bytes(32)
    app.dependency_overrides[obtener_pepper_limites] = lambda: pepper_limites
    app.dependency_overrides[obtener_contadores] = lambda: contadores
    return contadores
