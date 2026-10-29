"""Doble del puerto SesionesRelevo: un diccionario con TTL según un Reloj. Como el adaptador Redis,
guarda bajo el SHA-256 del id de sesión y solo el id del acceso."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from app.shared.puertos import Reloj


class SesionesRelevoEnMemoria:
    def __init__(self, reloj: Reloj) -> None:
        self._reloj = reloj
        self.guardadas: dict[str, tuple[uuid.UUID, datetime]] = {}
        self.ttls: list[int] = []

    @staticmethod
    def clave(sesion_id: str) -> str:
        return hashlib.sha256(sesion_id.encode("utf-8")).hexdigest()

    def crear(self, acceso_id: uuid.UUID, segundos: int) -> str:
        sesion_id = secrets.token_urlsafe(32)
        self.guardadas[self.clave(sesion_id)] = (acceso_id, self._reloj.ahora() + timedelta(seconds=segundos))
        self.ttls.append(segundos)
        return sesion_id

    def acceso_de(self, sesion_id: str) -> uuid.UUID | None:
        fila = self.guardadas.get(self.clave(sesion_id))
        if fila is None or fila[1] <= self._reloj.ahora():
            return None
        return fila[0]

    def descartar(self, sesion_id: str) -> None:
        self.guardadas.pop(self.clave(sesion_id), None)
