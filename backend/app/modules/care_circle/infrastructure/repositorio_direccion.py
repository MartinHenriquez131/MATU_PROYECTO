"""Adaptador SQL de RepositorioDireccion (MATU-61, decisiones 189 a 191 y 216).

Con la sesión del contexto de grupo: RLS acota persona_cuidada y direccion al grupo (direccion_familia), y solo admin y
cuidador modifican la persona (persona_familia_editar, migración 0018). El filtro por grupo es además explícito.
Nunca registra la dirección en los logs. Sin lat ni lng (C8: la migración 0023 exige que sean nulas).
"""

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session

from app.modules.care_circle.application.direccion import DireccionDePersona
from app.modules.care_circle.application.ports import DatosDireccion

_BLOQUEAR = text(
    "SELECT p.id AS persona_id, p.direccion_entrega_id, d.etiqueta, d.calle, d.numero, d.depto, d.comuna,"
    " d.region, d.referencia, d.version"
    " FROM persona_cuidada p LEFT JOIN direccion d ON d.id = p.direccion_entrega_id AND d.grupo_id = p.grupo_id"
    " WHERE p.id = :persona_id AND p.grupo_id = :grupo_id AND p.eliminado_en IS NULL FOR UPDATE OF p"
)
_COMPARTIDA = text(
    "SELECT EXISTS (SELECT 1 FROM persona_cuidada WHERE direccion_entrega_id = :direccion_id"
    " AND grupo_id = :grupo_id AND id <> :persona_id)"
)
_INSERTAR = text(
    "INSERT INTO direccion (id, grupo_id, etiqueta, calle, numero, depto, comuna, region, referencia, creado_en)"
    " VALUES (:id, :grupo_id, :etiqueta, :calle, :numero, :depto, :comuna, :region, :referencia, :ahora)"
)
_APUNTAR = text(
    "UPDATE persona_cuidada SET direccion_entrega_id = :direccion_id WHERE id = :persona_id AND grupo_id = :grupo_id"
)
_ACTUALIZAR = text(
    "UPDATE direccion SET etiqueta = :etiqueta, calle = :calle, numero = :numero, depto = :depto, comuna = :comuna,"
    " region = :region, referencia = :referencia, version = version + 1"
    " WHERE id = :id AND grupo_id = :grupo_id RETURNING version"
)
_SOLTAR = text("UPDATE persona_cuidada SET direccion_entrega_id = NULL WHERE id = :persona_id AND grupo_id = :grupo_id")
_BORRAR_SI_NADIE = text(
    "DELETE FROM direccion d WHERE d.id = :direccion_id AND d.grupo_id = :grupo_id"
    " AND NOT EXISTS (SELECT 1 FROM persona_cuidada p WHERE p.direccion_entrega_id = d.id)"
)


class DireccionNoEscrita(RuntimeError):
    """La base no aplicó el cambio (RLS). Mensaje fijo, sin datos."""


def _campos(datos: DatosDireccion) -> dict[str, Any]:
    return {
        "etiqueta": datos.etiqueta,
        "calle": datos.calle,
        "numero": datos.numero,
        "depto": datos.depto,
        "comuna": datos.comuna,
        "region": datos.region,
        "referencia": datos.referencia,
    }


class RepositorioDireccionSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def bloquear(self, persona_id: uuid.UUID) -> DireccionDePersona | None:
        fila = self._sesion.execute(_BLOQUEAR, {"persona_id": persona_id, "grupo_id": self._grupo_id}).first()
        if fila is None:
            return None
        direccion = None
        if fila.direccion_entrega_id is not None and fila.calle is not None:
            direccion = DatosDireccion(
                etiqueta=fila.etiqueta,
                calle=fila.calle,
                numero=fila.numero,
                depto=fila.depto,
                comuna=fila.comuna,
                region=fila.region,
                referencia=fila.referencia,
                version=fila.version,
            )
        return DireccionDePersona(
            persona_id=fila.persona_id,
            direccion_id=fila.direccion_entrega_id if direccion is not None else None,
            direccion=direccion,
        )

    def compartida(self, direccion_id: uuid.UUID, persona_id: uuid.UUID) -> bool:
        parametros = {"direccion_id": direccion_id, "persona_id": persona_id, "grupo_id": self._grupo_id}
        return bool(self._sesion.execute(_COMPARTIDA, parametros).scalar_one())

    def crear(self, persona_id: uuid.UUID, datos: DatosDireccion, ahora: datetime) -> uuid.UUID:
        direccion_id = uuid.uuid4()
        self._sesion.execute(
            _INSERTAR, {"id": direccion_id, "grupo_id": self._grupo_id, "ahora": ahora, **_campos(datos)}
        )
        self._apuntar(persona_id, direccion_id)
        return direccion_id

    def actualizar(self, direccion_id: uuid.UUID, datos: DatosDireccion) -> int:
        version = self._sesion.execute(
            _ACTUALIZAR, {"id": direccion_id, "grupo_id": self._grupo_id, **_campos(datos)}
        ).scalar_one_or_none()
        if version is None:
            raise DireccionNoEscrita("la dirección no se guardó")
        return int(version)

    def vaciar(self, persona_id: uuid.UUID, direccion_id: uuid.UUID) -> None:
        resultado = cast(
            CursorResult[Any], self._sesion.execute(_SOLTAR, {"persona_id": persona_id, "grupo_id": self._grupo_id})
        )
        if resultado.rowcount != 1:
            raise DireccionNoEscrita("la dirección no se vació")
        self._sesion.execute(_BORRAR_SI_NADIE, {"direccion_id": direccion_id, "grupo_id": self._grupo_id})

    def _apuntar(self, persona_id: uuid.UUID, direccion_id: uuid.UUID) -> None:
        resultado = cast(
            CursorResult[Any],
            self._sesion.execute(
                _APUNTAR, {"persona_id": persona_id, "direccion_id": direccion_id, "grupo_id": self._grupo_id}
            ),
        )
        if resultado.rowcount != 1:
            raise DireccionNoEscrita("la dirección no se guardó")
