"""La conservación del teléfono del relevo (MATU-46, decisión 25).

El teléfono se borra 30 días después de que el acceso vence o se corta, lo que ocurra primero. El nombre del relevo,
el motivo y las fechas se conservan (3 años, MATU-89). El instante sale del puerto Reloj. La regla vive en
domain/relevo.py y la aplica la función SQL relevo_conservar, que devuelve solo un contador.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.care_plan.domain.relevo import limite_telefono
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class ResultadoConservacionRelevo:
    telefonos_borrados: int


class UnidadConservacionRelevo(Protocol):
    def conservar(self, limite: datetime, ahora: datetime) -> int:
        """Llama a relevo_conservar(limite, ahora). Devuelve cuántos teléfonos vació."""
        ...


def conservar(unidad: UnidadConservacionRelevo, reloj: Reloj) -> ResultadoConservacionRelevo:
    ahora = reloj.ahora()
    return ResultadoConservacionRelevo(telefonos_borrados=unidad.conservar(limite_telefono(ahora), ahora))
