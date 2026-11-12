"""Las transacciones del sistema para la vuelta y la conciliación (MATU-62, migración 0024).

- resolver_venta: con matu_app, app.rol = 'sistema' y sin grupo ni cuenta, llama a pago_resolver_venta (SECURITY
  DEFINER), que entrega solo el id de la venta y su grupo. Así la vuelta sin sesión no ve nada más.
- abrir_grupo: una transacción con app.grupo_id de la venta y app.rol = 'sistema', sin cuenta: RLS deja leer y
  cerrar el pago de ese grupo y nada de otros (cargo_sistema_*, transaccion_sistema_*, pedido_sistema_pago).
- listar_por_conciliar: con matu_scheduler y app.rol = 'operacion', pagos_por_conciliar (solo ids).
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.payments.application.ports import Unidad
from app.modules.payments.infrastructure.repositorio_pagos import RepositorioPagosSQL
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import Reloj

_RESOLVER = text("SELECT transaccion_id, grupo_id FROM pago_resolver_venta(:token, :orden, :sesion)")
_POR_CONCILIAR = text("SELECT transaccion_id, grupo_id FROM pagos_por_conciliar(:limite, :cantidad)")


class ResolverVentaSQL:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def __call__(
        self, token: str | None, orden: str | None, sesion: str | None
    ) -> tuple[uuid.UUID, uuid.UUID] | None:
        with sesion_tenant(self._fabrica, rol="sistema") as s:
            f = s.execute(_RESOLVER, {"token": token, "orden": orden, "sesion": sesion}).first()
        return None if f is None else (f.transaccion_id, f.grupo_id)


class AbrirGrupoSQL:
    def __init__(self, fabrica: sessionmaker[Session], reloj: Reloj) -> None:
        self._fabrica = fabrica
        self._reloj = reloj

    @contextmanager
    def __call__(self, grupo_id: uuid.UUID) -> Iterator[Unidad]:
        with sesion_tenant(self._fabrica, grupo_id=grupo_id, rol="sistema") as sesion:
            yield Unidad(RepositorioPagosSQL(sesion, grupo_id), RegistroAuditoriaSql(sesion, self._reloj))


class ListarPorConciliarSQL:
    def __init__(self, fabrica_scheduler: sessionmaker[Session]) -> None:
        self._fabrica = fabrica_scheduler

    def __call__(self, limite: datetime, cantidad: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
        with sesion_tenant(self._fabrica, rol="operacion") as s:
            filas = s.execute(_POR_CONCILIAR, {"limite": limite, "cantidad": cantidad})
            return [(f.transaccion_id, f.grupo_id) for f in filas]
