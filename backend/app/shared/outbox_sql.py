"""El outbox en PostgreSQL, para el publicador (MATU-41, decisión 106, migración 0014).

matu_app no lee ni actualiza evento_outbox (03_permisos.sql). Todo pasa por cuatro funciones SECURITY
DEFINER que exigen app.rol = 'operacion' (como quiebre_conservar y la enumeración de grupos del trabajo
diario): tomar (con FOR UPDATE SKIP LOCKED y un arriendo de 5 minutos), publicado, reintentar y posponer.
Cada llamada es su propia transacción corta: el consumidor trabaja después, en las suyas, con app.rol =
'sistema' y el grupo del evento.
"""

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.shared.outbox import EventoTomado

_TOMAR = text("SELECT id, grupo_id, tipo, payload, intentos FROM outbox_tomar(:cantidad, :ahora, :grupo)")
_PUBLICADO = text("SELECT outbox_publicado(:id, :ahora)")
_REINTENTAR = text("SELECT outbox_reintentar(:id, :disponible_en, :ahora)")
_POSPONER = text("SELECT outbox_posponer(:id, :hasta, :ahora)")


class AlmacenOutboxSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def __repr__(self) -> str:
        return "AlmacenOutboxSql()"

    def tomar(self, cantidad: int, ahora: datetime, grupo_id: uuid.UUID | None = None) -> list[EventoTomado]:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            filas = sesion.execute(_TOMAR, {"cantidad": cantidad, "ahora": ahora, "grupo": grupo_id}).all()
        return [
            EventoTomado(
                id=int(f.id), grupo_id=f.grupo_id, tipo=f.tipo, payload=dict(f.payload), intentos=int(f.intentos)
            )
            for f in filas
        ]

    def publicado(self, evento_id: int, ahora: datetime) -> None:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            sesion.execute(_PUBLICADO, {"id": evento_id, "ahora": ahora})

    def reintentar(self, evento_id: int, disponible_en: datetime, ahora: datetime) -> bool:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            return bool(
                sesion.execute(_REINTENTAR, {"id": evento_id, "disponible_en": disponible_en, "ahora": ahora}).scalar()
            )

    def posponer(self, evento_id: int, hasta: datetime, ahora: datetime) -> None:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            sesion.execute(_POSPONER, {"id": evento_id, "hasta": hasta, "ahora": ahora})
