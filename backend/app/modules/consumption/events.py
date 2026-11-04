"""Eventos del módulo consumption (arquitectura 6.3 y 8.6).

El trabajo diario de MATU-37 publica ``QuiebreProximo`` por el outbox, en la misma transacción en que
materializa la alerta. Lleva solo identificadores (payload_solo_identificadores): nunca nombre_libre,
producto ni cantidades. MATU-41 lo consume para avisar; MATU-37 no envía nada.
"""

import uuid
from dataclasses import dataclass

QUIEBRE_PROXIMO = "QuiebreProximo"
AGREGADO_ALERTA = "alerta_quiebre"


@dataclass(frozen=True)
class QuiebreProximo:
    """Solo identificadores."""

    alerta_id: uuid.UUID
    perfil_id: uuid.UUID
    persona_cuidada_id: uuid.UUID

    def payload(self) -> dict[str, str]:
        return {
            "alerta_id": str(self.alerta_id),
            "perfil_id": str(self.perfil_id),
            "persona_cuidada_id": str(self.persona_cuidada_id),
        }
