"""Reglas puras del borrado de los datos de la persona, al tiro y a pedido (MATU-72, decisiones 149 a 157).

Sin I/O y sin reloj del sistema: el instante llega como argumento (puerto Reloj).

- Borran admin y cuidador, la misma regla del retiro (D1): ``puede_borrar`` es ``puede_retirar``. Los demás: 404.
- Una persona ya borrada no se borra otra vez (409 ya-borrada, C3). Una eliminada sin borrado, o que no está en
  el grupo, es 404.
- La persona sale de MATU: la fila queda con su id y sin datos. NOMBRE_BORRADO es el valor fijo, sin datos, que
  reemplaza su nombre, su nombre de pila y el nombre de pila copiado en los accesos de relevo (D5).
- Las autorizaciones no revocadas se retiran en un orden fijo (C1): plan_cuidado, consumo y cualquier otra
  finalidad al final, para que dos transacciones bloqueen siempre en el mismo orden.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.care_circle.domain.retiro import FINALIDADES_RETIRABLES, puede_retirar

# D5: el valor fijo que reemplaza los nombres. No dice nada de la persona
NOMBRE_BORRADO = "borrada"


class YaBorrada(Exception):
    """Los datos de la persona ya se borraron. La API responde 409 ya-borrada."""


class PersonaNoEncontrada(LookupError):
    """La persona no es del grupo, no existe o se eliminó sin un borrado. La API responde 404."""


@dataclass(frozen=True)
class PersonaParaBorrar:
    """La fila de la persona, bloqueada, sin ningún dato: solo lo que decide si se puede borrar."""

    id: uuid.UUID
    eliminado_en: datetime | None
    datos_borrados_en: datetime | None
    direccion_id: uuid.UUID | None


def puede_borrar(rol: str) -> bool:
    """D1: la misma regla y la misma barrera del retiro (app_retira_autorizacion() en la base)."""
    return puede_retirar(rol)


def exigir_borrable(persona: PersonaParaBorrar | None) -> PersonaParaBorrar:
    """La persona, si se puede borrar. YaBorrada antes que el filtro de eliminado_en (C3)."""
    if persona is None:
        raise PersonaNoEncontrada()
    if persona.datos_borrados_en is not None:
        raise YaBorrada()
    if persona.eliminado_en is not None:
        raise PersonaNoEncontrada()
    return persona


def orden_de_bloqueo(finalidad: str) -> int:
    """La posición de la finalidad en el orden de bloqueo de C1: plan_cuidado, consumo y las demás al final."""
    if finalidad in FINALIDADES_RETIRABLES:
        return FINALIDADES_RETIRABLES.index(finalidad)
    return len(FINALIDADES_RETIRABLES)
