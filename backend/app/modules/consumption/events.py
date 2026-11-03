"""Eventos del módulo consumption (arquitectura 6.3).

MATU-36 no publica eventos: crear, editar, desactivar, activar o eliminar un perfil solo dejan su fila
de auditoría. El trabajo diario de MATU-37 publicará ``QuiebreProximo`` por el outbox. Cualquier
evento de este módulo lleva solo identificadores (payload_solo_identificadores): nunca nombre_libre
ni cantidades.
"""

import uuid
from dataclasses import dataclass

QUIEBRE_PROXIMO = "QuiebreProximo"


@dataclass(frozen=True)
class QuiebreProximo:
    """Reservado para MATU-37. Solo identificadores."""

    alerta_id: uuid.UUID
    perfil_id: uuid.UUID
