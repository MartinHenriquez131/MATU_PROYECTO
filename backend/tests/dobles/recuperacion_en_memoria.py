"""Dobles de MATU-57: el almacén de códigos y los contadores de envíos en diccionarios.

Respetan los vencimientos con el Reloj de la prueba. Con caido=True, cada método lanza
ContadoresNoDisponibles, como un Redis que no responde.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.modules.iam.application.ports import ContadoresNoDisponibles
from app.modules.iam.domain.recuperacion import SIN_ENVIOS, VENTANA_DIA, VENTANA_HORA, CodigoGuardado, EnviosRecientes
from app.shared.puertos import Reloj


@dataclass
class AlmacenCodigosEnMemoria:
    reloj: Reloj
    caido: bool = False
    datos: dict[str, tuple[CodigoGuardado, int]] = field(default_factory=dict)

    def _revisar(self) -> None:
        if self.caido:
            raise ContadoresNoDisponibles()

    def _vigente(self, clave: str) -> tuple[CodigoGuardado, int] | None:
        dato = self.datos.get(clave)
        # Como el TTL de Redis: un segundo después del vencimiento ya no existe
        if dato is not None and (self.reloj.ahora() - dato[0].expira_en).total_seconds() > 1:
            del self.datos[clave]
            return None
        return dato

    def guardar(self, clave: str, codigo: CodigoGuardado) -> None:
        self._revisar()
        self.datos[clave] = (codigo, 0)

    def leer(self, clave: str) -> CodigoGuardado | None:
        self._revisar()
        dato = self._vigente(clave)
        return None if dato is None else dato[0]

    def sumar_intento(self, clave: str) -> int:
        self._revisar()
        dato = self._vigente(clave)
        if dato is None:
            return 0
        self.datos[clave] = (dato[0], dato[1] + 1)
        return dato[1] + 1

    def consumir(self, clave: str) -> bool:
        self._revisar()
        return self.datos.pop(clave, None) is not None


@dataclass
class ContadoresEnvioEnMemoria:
    reloj: Reloj
    caido: bool = False
    datos: dict[str, EnviosRecientes] = field(default_factory=dict)

    def _revisar(self) -> None:
        if self.caido:
            raise ContadoresNoDisponibles()

    def _vigente(self, huella: str, ahora: datetime) -> EnviosRecientes:
        e = self.datos.get(huella, SIN_ENVIOS)
        if e.inicio_hora is not None and ahora >= e.inicio_hora + VENTANA_HORA:
            e = EnviosRecientes(None, 0, None, e.en_dia, e.inicio_dia)
        if e.inicio_dia is not None and ahora >= e.inicio_dia + VENTANA_DIA:
            e = EnviosRecientes(e.ultimo, e.en_hora, e.inicio_hora, 0, None)
        return e

    def leer(self, huella: str) -> EnviosRecientes:
        self._revisar()
        return self._vigente(huella, self.reloj.ahora())

    def sumar(self, huella: str, ahora: datetime) -> None:
        self._revisar()
        e = self._vigente(huella, ahora)
        self.datos[huella] = EnviosRecientes(
            ultimo=ahora,
            en_hora=e.en_hora + 1,
            inicio_hora=e.inicio_hora or ahora,
            en_dia=e.en_dia + 1,
            inicio_dia=e.inicio_dia or ahora,
        )
