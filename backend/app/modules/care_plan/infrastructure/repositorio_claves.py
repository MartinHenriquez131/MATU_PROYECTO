"""Adaptador SQL del puerto RepositorioClaves: la fila de clave_datos de cada persona (MATU-11).

Trabaja con la sesión de la petición (sesion_tenant), con el contexto ya fijado: RLS acota cada
consulta al grupo en contexto (política clave_familia) o al acceso de relevo vigente
(clave_relevo). Nunca abre su propia sesión ni fija contexto.

No borra claves: matu_app no tiene DELETE sobre clave_datos, y una clave destruida no vuelve a tener DEK
(trigger clave_datos_destruida_fija, migración 0003). Desde MATU-44 la destruye en un caso: al volver a
autorizar la ficha 90 días o más después del retiro (decisión 128). La tarea de los 90 días usa la función
plan_destruir_claves (migración 0016), no este adaptador.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session

from app.modules.care_plan.application.ports import DekEnvuelta
from app.modules.care_plan.domain.cifrado import ClaveGuardada

_OBTENER = "SELECT dek_cifrada_con_kek, kek_version FROM clave_datos WHERE persona_cuidada_id = :persona_id"
_LEER = text(_OBTENER)
# Bloqueo compartido: dos escrituras de la misma ficha no se esperan entre sí, pero una
# destrucción concurrente (UPDATE) espera a que la escritura termine.
_LEER_PARA_ESCRIBIR = text(_OBTENER + " FOR SHARE")

# Sin RETURNING, como el resto de los repositorios. Si la persona ya tiene una fila (vigente o
# destruida), el UNIQUE de persona_cuidada_id hace que no se escriba nada. Si otra transacción la
# está creando, esta espera a que termine y después decide.
_CREAR = text(
    "INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
    " VALUES (:grupo_id, :persona_id, :dek_cifrada, :kek_version)"
    " ON CONFLICT (persona_cuidada_id) DO NOTHING"
)


# MATU-44: el borrado criptográfico, en la misma sentencia (CHECK clave_datos_destruccion)
_DESTRUIR = text(
    "UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = :ahora"
    " WHERE persona_cuidada_id = :persona_id AND destruida_en IS NULL RETURNING id, grupo_id"
)
_DESTRUIDA_EN = text("SELECT destruida_en FROM clave_datos WHERE persona_cuidada_id = :persona_id")


class RepositorioClavesSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener(self, persona_cuidada_id: uuid.UUID, *, para_escribir: bool = False) -> ClaveGuardada | None:
        sentencia = _LEER_PARA_ESCRIBIR if para_escribir else _LEER
        fila = self._sesion.execute(sentencia, {"persona_id": persona_cuidada_id}).one_or_none()
        if fila is None:
            return None
        dek_cifrada, kek_version = fila
        return ClaveGuardada(
            kek_version=kek_version, dek_cifrada=bytes(dek_cifrada) if dek_cifrada is not None else None
        )

    def crear(self, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, envuelta: DekEnvuelta) -> bool:
        resultado = cast(
            CursorResult[Any],
            self._sesion.execute(
                _CREAR,
                {
                    "grupo_id": grupo_id,
                    "persona_id": persona_cuidada_id,
                    "dek_cifrada": envuelta.dek_cifrada,
                    "kek_version": envuelta.kek_version,
                },
            ),
        )
        return resultado.rowcount == 1

    def destruir(self, persona_cuidada_id: uuid.UUID, ahora: datetime) -> uuid.UUID | None:
        """Destruye la clave vigente de la persona. Devuelve su id, o None si no había o ya estaba destruida."""
        fila = self._sesion.execute(_DESTRUIR, {"persona_id": persona_cuidada_id, "ahora": ahora}).first()
        return None if fila is None else fila.id

    def destruida_en(self, persona_cuidada_id: uuid.UUID) -> datetime | None:
        """Cuándo se destruyó la clave de la persona, o None si no tiene o está vigente."""
        fila = self._sesion.execute(_DESTRUIDA_EN, {"persona_id": persona_cuidada_id}).first()
        return None if fila is None or fila.destruida_en is None else fila.destruida_en.astimezone(UTC)
