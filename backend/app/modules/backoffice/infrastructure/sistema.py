"""Las transacciones del sistema y de operación sobre un pedido pagado (MATU-63, migración 0029).

- abrir: una transacción con app.grupo_id del pedido y app.rol = 'sistema' u 'operacion', sin cuenta: RLS deja mover
  el pedido después del pago, actualizar sus partes y devolver (pedido_sistema_pago, pedido_comercio_sistema_editar,
  transaccion_sistema_crear, linea_pago_devolver y las de operación).
- resolver_parte: con app.rol = 'sistema' y sin grupo, cuenta ni comercio, despacho_resolver_parte entrega solo el
  pedido y el grupo de una parte. Así la acción del comercio sigue en una transacción del sistema sin que el comercio
  sepa nada de la familia.
- pendientes: con matu_scheduler y app.rol = 'operacion', despacho_pendiente (solo ids).
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.backoffice.application.despacho import UnidadDespacho
from app.modules.fulfillment.infrastructure.repositorio_despacho import RepositorioDespachoSQL
from app.modules.payments.application.ports import Unidad
from app.modules.payments.infrastructure.repositorio_pagos import RepositorioPagosSQL
from app.modules.payments.infrastructure.repositorio_retractos import RepositorioRetractosSQL
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import Reloj

_RESOLVER = text("SELECT pedido_id, grupo_id FROM despacho_resolver_parte(:parte)")
_PENDIENTES = text("SELECT pedido_id, grupo_id FROM despacho_pendiente(:cantidad)")


class AbrirDespachoSQL:
    def __init__(self, fabrica: sessionmaker[Session], reloj: Reloj, rol: str = "sistema") -> None:
        if rol not in ("sistema", "operacion"):
            raise ValueError("rol de despacho no permitido")
        self._fabrica = fabrica
        self._reloj = reloj
        self._rol = rol

    @contextmanager
    def __call__(self, grupo_id: uuid.UUID) -> Iterator[tuple[UnidadDespacho, RepositorioRetractosSQL]]:
        with sesion_tenant(self._fabrica, grupo_id=grupo_id, rol=self._rol) as sesion:
            pagos = Unidad(RepositorioPagosSQL(sesion, grupo_id), RegistroAuditoriaSql(sesion, self._reloj))
            yield (
                UnidadDespacho(RepositorioDespachoSQL(sesion, grupo_id), pagos),
                RepositorioRetractosSQL(sesion, grupo_id),
            )


def resolver_parte(fabrica: sessionmaker[Session], parte_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID] | None:
    with sesion_tenant(fabrica, rol="sistema") as sesion:
        f = sesion.execute(_RESOLVER, {"parte": parte_id}).first()
    return None if f is None else (f.pedido_id, f.grupo_id)


def pendientes(fabrica_scheduler: sessionmaker[Session], cantidad: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
    with sesion_tenant(fabrica_scheduler, rol="operacion") as sesion:
        return [(f.pedido_id, f.grupo_id) for f in sesion.execute(_PENDIENTES, {"cantidad": cantidad})]
