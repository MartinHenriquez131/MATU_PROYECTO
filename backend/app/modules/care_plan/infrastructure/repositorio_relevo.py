"""Adaptadores SQL del relevo (MATU-19, RF-06).

- IndiceTokensSQL: indice_token, sin RLS (02_rls.sql, excepción declarada), en una transacción sin
  contexto. Lee solo el acceso, el vencimiento y la revocación (decisión 23), nunca grupo ni usuario.
- RepositorioAccesoRelevoSQL y SeccionesRelevoSQL: con la sesión de relevo (app.rol = 'relevo' y
  app.acceso_relevo_id, nunca app.grupo_id). RLS acota cada consulta al acceso de la sesión. No leen
  el teléfono ni el nombre del relevo.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_plan.application.ports import AccesoDelRelevo, EntradaIndice
from app.modules.care_plan.domain.cifrado import SeccionCifrada
from app.modules.care_plan.domain.ficha import CAMPOS_FICHA

_INDICE = "SELECT referencia_id, expira_en, revocado_en FROM indice_token WHERE tipo = 'relevo'"
_POR_TOKEN = text(_INDICE + " AND token_hash = :token_hash")
_POR_ACCESO = text(_INDICE + " AND referencia_id = :acceso_id")

_LEER = text(
    "SELECT id, grupo_id, plan_id, secciones_permitidas, nombre_pila_persona, nombre_pila_comparte, pin_hash,"
    " pin_intentos_fallidos, expira_en FROM acceso_relevo"
)
_AUTORIZACION = text("SELECT relevo_autorizacion_vigente(:ahora)")
_INTENTOS = text("UPDATE acceso_relevo SET pin_intentos_fallidos = :intentos")
_USO = text("UPDATE acceso_relevo SET usos = usos + 1, ultimo_uso_en = :ahora")

_PLAN = text("SELECT persona_cuidada_id FROM plan_cuidado WHERE id = :plan_id")
_TIPOS = ", ".join(f"'{c.value}'" for c in CAMPOS_FICHA)
_SECCIONES = text(
    "SELECT tipo, contenido_cifrado, nonce, tag_auth, kek_version FROM plan_seccion"
    f" WHERE plan_id = :plan_id AND tipo IN ({_TIPOS})"
)


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


def _entrada(fila: Any) -> EntradaIndice | None:
    if fila is None:
        return None
    return EntradaIndice(
        acceso_id=fila.referencia_id, expira_en=fila.expira_en.astimezone(UTC), revocado_en=_utc(fila.revocado_en)
    )


class IndiceTokensSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def por_token(self, token_hash: bytes) -> EntradaIndice | None:
        return _entrada(self._sesion.execute(_POR_TOKEN, {"token_hash": token_hash}).one_or_none())

    def por_acceso(self, acceso_id: uuid.UUID) -> EntradaIndice | None:
        return _entrada(self._sesion.execute(_POR_ACCESO, {"acceso_id": acceso_id}).first())


class RepositorioAccesoRelevoSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def leer(self) -> AccesoDelRelevo | None:
        f = self._sesion.execute(_LEER).one_or_none()
        if f is None:
            return None
        return AccesoDelRelevo(
            id=f.id,
            grupo_id=f.grupo_id,
            plan_id=f.plan_id,
            campos=tuple(f.secciones_permitidas),
            nombre_pila_persona=f.nombre_pila_persona,
            nombre_pila_comparte=f.nombre_pila_comparte,
            pin_hash=f.pin_hash,
            pin_intentos_fallidos=f.pin_intentos_fallidos,
            expira_en=f.expira_en.astimezone(UTC),
        )

    def autorizacion_vigente(self, ahora: datetime) -> bool:
        return bool(self._sesion.execute(_AUTORIZACION, {"ahora": ahora}).scalar_one())

    def fijar_intentos(self, intentos: int) -> None:
        self._sesion.execute(_INTENTOS, {"intentos": intentos})

    def registrar_uso(self, ahora: datetime) -> None:
        self._sesion.execute(_USO, {"ahora": ahora})


class SeccionesRelevoSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def persona_del_plan(self, plan_id: uuid.UUID) -> uuid.UUID | None:
        valor = self._sesion.execute(_PLAN, {"plan_id": plan_id}).scalar_one_or_none()
        return None if valor is None else uuid.UUID(str(valor))

    def secciones(self, plan_id: uuid.UUID) -> list[tuple[str, SeccionCifrada]]:
        return [
            (
                f.tipo,
                SeccionCifrada(
                    contenido_cifrado=bytes(f.contenido_cifrado), nonce=bytes(f.nonce), tag_auth=bytes(f.tag_auth),
                    kek_version=f.kek_version,
                ),
            )
            for f in self._sesion.execute(_SECCIONES, {"plan_id": plan_id}).all()
        ]
