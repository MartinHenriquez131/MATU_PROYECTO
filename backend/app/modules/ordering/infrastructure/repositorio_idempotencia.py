"""Adaptador SQL de RepositorioIdempotencia (decisión 195, D5, migración 0023).

Guarda solo la huella de la petición, el estado HTTP y el id del pedido: nunca el cuerpo ni la respuesta. RLS deja
leer las claves del grupo (para reconocer la de otra cuenta) y escribir solo las propias. Las vencidas las borra
pedido_conservar (tarea conservacion_pedidos). La clave nunca va a los logs.
"""

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.ordering.domain.idempotencia import Registro

_RESERVAR = text(
    "INSERT INTO idempotencia (grupo_id, endpoint, clave, usuario_id, hash_peticion, creada_en, expira_en)"
    " VALUES (:grupo_id, :endpoint, :clave, app_usuario(), :huella, :ahora, :expira_en)"
    " ON CONFLICT (grupo_id, endpoint, clave) DO NOTHING RETURNING clave"
)
_LEER = text(
    "SELECT usuario_id, hash_peticion, estado_http, pedido_id, expira_en FROM idempotencia"
    " WHERE grupo_id = :grupo_id AND endpoint = :endpoint AND clave = :clave"
)
_REEMPLAZAR = text(
    "UPDATE idempotencia SET hash_peticion = :huella, estado_http = NULL, pedido_id = NULL, expira_en = :expira_en"
    " WHERE grupo_id = :grupo_id AND endpoint = :endpoint AND clave = :clave AND usuario_id = app_usuario()"
)
_COMPLETAR = text(
    "UPDATE idempotencia SET estado_http = :estado, pedido_id = :pedido_id"
    " WHERE grupo_id = :grupo_id AND endpoint = :endpoint AND clave = :clave AND usuario_id = app_usuario()"
)


class RepositorioIdempotenciaSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._ahora = ahora

    def reservar(
        self, endpoint: str, clave: str, usuario_id: uuid.UUID, huella: bytes, expira_en: datetime
    ) -> Registro | None:
        claves = {"grupo_id": self._grupo_id, "endpoint": endpoint, "clave": clave}
        reservada = self._sesion.execute(
            _RESERVAR, {**claves, "huella": huella, "ahora": self._ahora, "expira_en": expira_en}
        ).first()
        if reservada is not None:
            return None
        f = self._sesion.execute(_LEER, claves).first()
        if f is None:  # pragma: no cover - la fila que chocó se borró entre las dos sentencias
            return None
        return Registro(
            usuario_id=f.usuario_id,
            huella=bytes(f.hash_peticion),
            estado_http=f.estado_http,
            pedido_id=f.pedido_id,
            expira_en=f.expira_en,
        )

    def reemplazar(self, endpoint: str, clave: str, huella: bytes, expira_en: datetime) -> None:
        self._sesion.execute(
            _REEMPLAZAR,
            {
                "grupo_id": self._grupo_id,
                "endpoint": endpoint,
                "clave": clave,
                "huella": huella,
                "expira_en": expira_en,
            },
        )

    def completar(self, endpoint: str, clave: str, estado_http: int, pedido_id: uuid.UUID) -> None:
        self._sesion.execute(
            _COMPLETAR,
            {
                "grupo_id": self._grupo_id,
                "endpoint": endpoint,
                "clave": clave,
                "estado": estado_http,
                "pedido_id": pedido_id,
            },
        )
