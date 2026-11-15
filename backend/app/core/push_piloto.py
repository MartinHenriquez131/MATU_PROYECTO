"""Quién puede activar los avisos push durante el piloto (MATU-107, hallazgo 55-H2, condición C14).

Es el único lugar que lee PUSH_CUENTAS_PERMITIDAS. iam (PUT y GET de /v1/dispositivos/actual/push) y notifications (el
consumidor de avisos, la segunda barrera) consultan ``PoliticaPush.permite`` y nunca la lista.

Con ENTORNO en ENTORNOS_PUSH_SIN_LISTA (local y pruebas) toda cuenta puede. En cualquier otro, incluida produccion, solo
las cuentas de la lista, y la lista ausente o vacía no deja pasar a nadie (falla cerrada, C-107-3).

La lista nunca sale de aquí: ni en el repr, ni en un log, ni en un error, ni en una respuesta (C-107-6 y C-107-7).
"""

import logging
import uuid
from dataclasses import dataclass, field

from app.core.config import ENTORNOS_PUSH_SIN_LISTA, Configuracion, obtener_configuracion

log = logging.getLogger("matu.push_piloto")


@dataclass(frozen=True, repr=False, eq=False)
class PoliticaPush:
    """La regla de C14 ya resuelta para un entorno y una lista. Sin valores en el repr."""

    entorno: str
    permitidas: frozenset[uuid.UUID] = field(default_factory=frozenset)

    @classmethod
    def desde(cls, config: Configuracion) -> "PoliticaPush":
        return cls(entorno=config.entorno, permitidas=config.push_cuentas_permitidas)

    def permite(self, usuario_id: uuid.UUID) -> bool:
        """Si la cuenta puede activar los avisos push (y recibirlos) en este entorno."""
        if self.entorno in ENTORNOS_PUSH_SIN_LISTA:
            return True
        return usuario_id in self.permitidas

    def __repr__(self) -> str:
        return "PoliticaPush()"


def politica_push() -> PoliticaPush:
    """La política de la configuración vigente. Es la dependencia de la API: las pruebas la reemplazan."""
    return PoliticaPush.desde(obtener_configuracion())


def avisar_al_arrancar(config: Configuracion) -> None:
    """Un aviso fijo, sin valores (C-107-7): fuera de local y pruebas, push solo para las cuentas de la lista."""
    if config.entorno not in ENTORNOS_PUSH_SIN_LISTA:
        log.warning("avisos push del piloto: solo las cuentas de PUSH_CUENTAS_PERMITIDAS pueden activarlos")
