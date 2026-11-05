"""Doble del puerto ContadorVentana (MATU-25): el límite por IP en un diccionario.

Ventana fija, como el script de Redis: el vencimiento se fija con el primer incremento, con la hora
del Reloj de la prueba, y los siguientes no lo mueven. Con caido=True, sumar() lanza
ContadorNoDisponible, como un Redis que no responde.
"""

import math
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.core.limite_ip import ContadorNoDisponible, Conteo
from app.shared.puertos import Reloj

if TYPE_CHECKING:
    from fastapi import FastAPI


class ContadorVentanaEnMemoria:
    def __init__(self, reloj: Reloj, caido: bool = False) -> None:
        self.reloj = reloj
        self.caido = caido
        # clave → (conteo, vence_en)
        self.datos: dict[str, tuple[int, datetime]] = {}

    def sumar(self, clave: str, ventana_segundos: int) -> Conteo:
        if self.caido:
            raise ContadorNoDisponible()
        ahora = self.reloj.ahora()
        dato = self.datos.get(clave)
        if dato is None or ahora >= dato[1]:
            dato = (1, ahora + timedelta(seconds=ventana_segundos))
        else:
            dato = (dato[0] + 1, dato[1])
        self.datos[clave] = dato
        return Conteo(dato[0], math.ceil((dato[1] - ahora).total_seconds()))


def limite_ip_en_memoria(app: "FastAPI", reloj: Reloj, pepper: bytes | None = None) -> ContadorVentanaEnMemoria:
    """Sobreescribe en la app el contador del límite por IP (MATU-25) y, si no está ya, la llave de las
    huellas. Devuelve el contador."""
    from app.core.limite_ip import obtener_contador_ventana, obtener_pepper_limites

    contador = ContadorVentanaEnMemoria(reloj)
    app.dependency_overrides[obtener_contador_ventana] = lambda: contador
    if obtener_pepper_limites not in app.dependency_overrides:
        llave = pepper or secrets.token_bytes(32)
        app.dependency_overrides[obtener_pepper_limites] = lambda: llave
    return contador
