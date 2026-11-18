"""Doble de MATU-81: el almacén del segundo factor en diccionarios, con los vencimientos del Reloj de la prueba.

Con caido=True, cada método lanza ContadoresNoDisponibles, como un Redis que no responde.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.modules.iam.application.ports import ContadoresNoDisponibles, DesafioGuardado
from app.modules.iam.domain.mfa import SIN_FALLOS, FallosMfa
from app.shared.puertos import Reloj


@dataclass
class AlmacenMfaEnMemoria:
    reloj: Reloj
    caido: bool = False
    desafios: dict[str, DesafioGuardado] = field(default_factory=dict)
    fallos: dict[str, tuple[int, datetime]] = field(default_factory=dict)
    pasos: dict[str, tuple[int, datetime]] = field(default_factory=dict)

    def _revisar(self) -> None:
        if self.caido:
            raise ContadoresNoDisponibles()

    def guardar_desafio(self, huella: str, desafio: DesafioGuardado) -> None:
        self._revisar()
        self.desafios[huella] = desafio

    def leer_desafio(self, huella: str) -> DesafioGuardado | None:
        self._revisar()
        return self.desafios.get(huella)

    def borrar_desafio(self, huella: str) -> bool:
        self._revisar()
        return self.desafios.pop(huella, None) is not None

    def _fallos(self, cuenta: str) -> tuple[int, datetime] | None:
        dato = self.fallos.get(cuenta)
        if dato is not None and dato[1] <= self.reloj.ahora():
            del self.fallos[cuenta]
            return None
        return dato

    def leer_fallos(self, cuenta: str) -> FallosMfa:
        self._revisar()
        dato = self._fallos(cuenta)
        if dato is None:
            return SIN_FALLOS
        return FallosMfa(dato[0], int((dato[1] - self.reloj.ahora()).total_seconds()))

    def sumar_fallo(self, cuenta: str, ventana_segundos: int) -> FallosMfa:
        self._revisar()
        dato = self._fallos(cuenta)
        vence = dato[1] if dato is not None else self.reloj.ahora() + timedelta(seconds=ventana_segundos)
        conteo = (dato[0] if dato is not None else 0) + 1
        self.fallos[cuenta] = (conteo, vence)
        return FallosMfa(conteo, int((vence - self.reloj.ahora()).total_seconds()))

    def borrar_fallos(self, cuenta: str) -> None:
        self._revisar()
        self.fallos.pop(cuenta, None)

    def usar_paso(self, cuenta: str, paso: int, vida_segundos: int) -> bool:
        self._revisar()
        dato = self.pasos.get(cuenta)
        if dato is not None and dato[1] > self.reloj.ahora() and paso <= dato[0]:
            return False
        self.pasos[cuenta] = (paso, self.reloj.ahora() + timedelta(seconds=vida_segundos))
        return True
