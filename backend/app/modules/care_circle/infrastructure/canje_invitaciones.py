"""Adaptador SQL del puerto CanjeInvitaciones (MATU-42, D-42-12 a, migración 0026 (e)).

La persona invitada no es de la familia: la sesión no fija app.grupo_id (y en la aceptación fija solo app.usuario_id).
Lo que puede ver y escribir lo deciden invitacion_presentar, invitacion_verificar e invitacion_aceptar, SECURITY
DEFINER, que devuelven solo lo que cada paso muestra y escriben la auditoría en la misma transacción. indice_token no
tiene RLS: de ahí sale el id de la invitación para el HMAC del código.

Nunca se registra el token, el código ni sus huellas.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_circle.application.ports_grupo import Aceptacion, Presentacion, Verificacion
from app.modules.care_circle.domain.invitaciones import ResultadoCanje

_INVITACION_DE = text("SELECT referencia_id FROM indice_token WHERE token_hash = :token_hash AND tipo = 'invitacion'")
_PRESENTAR = text("SELECT * FROM invitacion_presentar(:token_hash, :ahora)")
_VERIFICAR = text("SELECT * FROM invitacion_verificar(:token_hash, :codigo_hash, :ahora, :request_id)")
_ACEPTAR = text("SELECT * FROM invitacion_aceptar(:token_hash, :codigo_hash, :ahora, :request_id)")


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


class CanjeInvitacionesSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def invitacion_de(self, token_hash: bytes) -> uuid.UUID | None:
        fila = self._sesion.execute(_INVITACION_DE, {"token_hash": token_hash}).one_or_none()
        return None if fila is None else fila.referencia_id

    def presentar(self, token_hash: bytes, ahora: datetime) -> Presentacion:
        f = self._sesion.execute(_PRESENTAR, {"token_hash": token_hash, "ahora": ahora}).one()
        return Presentacion(
            resultado=ResultadoCanje(f.resultado),
            nombre_pila_invita=f.nombre_pila_invita,
            rol=f.rol,
            expira_en=_utc(f.expira_en),
        )

    def verificar(self, token_hash: bytes, codigo_hash: bytes, ahora: datetime, request_id: str | None) -> Verificacion:
        f = self._sesion.execute(
            _VERIFICAR, {"token_hash": token_hash, "codigo_hash": codigo_hash, "ahora": ahora, "request_id": request_id}
        ).one()
        return Verificacion(
            resultado=ResultadoCanje(f.resultado),
            nombre_pila_invita=f.nombre_pila_invita,
            grupo=f.grupo,
            personas=tuple(f.personas or ()),
            rol=f.rol,
            expira_en=_utc(f.expira_en),
            intentos_restantes=f.intentos_restantes,
        )

    def aceptar(self, token_hash: bytes, codigo_hash: bytes, ahora: datetime, request_id: str | None) -> Aceptacion:
        f = self._sesion.execute(
            _ACEPTAR, {"token_hash": token_hash, "codigo_hash": codigo_hash, "ahora": ahora, "request_id": request_id}
        ).one()
        return Aceptacion(
            resultado=ResultadoCanje(f.resultado),
            nombre_pila_invita=f.nombre_pila_invita,
            grupo_id=f.grupo_id,
            membresia_id=f.membresia_id,
            grupo=f.grupo,
            rol=f.rol,
            intentos_restantes=f.intentos_restantes,
        )
