"""El efecto del retiro de ``despacho`` y del borrado de la persona sobre sus pedidos (MATU-61, D1 y D2).

Lo registra app.main en care_circle solo con la capa 3 encendida (C2, decisión 217): care_circle no importa ordering.
Corre en la transacción de la petición, con el instante del retiro: si cancelar falla, la excepción sigue y se
deshace todo, también el retiro (decisión 124).

- Al retirar despacho, los pedidos sin pagar de la persona pasan a cancelado (motivo autorizacion_retirada), se borra
  su entrega y se registra un pedido.cancelar por pedido. Los pagados siguen su plazo (CL-44).
- Al borrar a la persona (MATU-72), lo mismo con motivo persona_borrada.
- La dirección de la persona no se toca (C6).
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.ordering.application.pedidos import Actor, cancelar_sin_pagar_de
from app.modules.ordering.domain.estados import Motivo
from app.modules.ordering.infrastructure.repositorio_pedidos import RepositorioPedidosSQL
from app.shared.puertos import RegistroAuditoria

# El rol no decide nada aquí: el retiro y el borrado ya exigieron admin o cuidador (y RLS lo exige otra vez)
ROL_DEL_EFECTO = "admin"


class EfectoRetiroPedidos:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._grupo_id = grupo_id
        self._registro = registro
        self._pedidos = RepositorioPedidosSQL(sesion, grupo_id)

    def _cancelar(
        self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None, motivo: Motivo
    ) -> int:
        actor = Actor(usuario_id=usuario_id, grupo_id=self._grupo_id, rol=ROL_DEL_EFECTO, request_id=request_id)
        return cancelar_sin_pagar_de(actor, persona_id, ahora, motivo, self._pedidos, self._registro)

    def aplicar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        """Devuelve los pedidos cancelados: el retiro los informa en ``pedidos_cancelados``."""
        return self._cancelar(persona_id, ahora, usuario_id, request_id, Motivo.AUTORIZACION_RETIRADA)

    def antes_de_otorgar(
        self, persona_id: uuid.UUID, ahora: datetime, request_id: str | None, plazo_cumplido: bool
    ) -> None:
        # Retirar despacho ya canceló lo no pagado, y no hay un borrado a los 90 días (P14): nada que hacer
        return None

    def borrar(self, persona_id: uuid.UUID, ahora: datetime, usuario_id: uuid.UUID, request_id: str | None) -> int:
        self._cancelar(persona_id, ahora, usuario_id, request_id, Motivo.PERSONA_BORRADA)
        return 0  # el pedido no corta enlaces de relevo
