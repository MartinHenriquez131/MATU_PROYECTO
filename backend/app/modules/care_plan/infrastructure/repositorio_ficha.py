"""Adaptador SQL del puerto RepositorioFicha: plan_cuidado y las secciones de la ficha (MATU-12, RF-02).

Trabaja con la sesión del contexto de grupo (sesion_de_grupo), con app.usuario_id y app.grupo_id ya
fijados: las políticas plan_familia y seccion_familia acotan todo al grupo, y solo para quien puede
ver el plan. El filtro por grupo del plan es explícito además de RLS. Nunca abre su propia sesión ni
fija contexto, y nunca recibe texto en claro: solo SeccionCifrada.

Los INSERT no usan RETURNING (los identificadores los genera el caso de uso) y usan
ON CONFLICT DO NOTHING sobre los UNIQUE de plan_cuidado.persona_cuidada_id y de
plan_seccion (plan_id, tipo): dos primeras escrituras concurrentes dejan un solo plan y una sola
sección, y el caso de uso decide con el resultado (la que no escribió responde 412, MATU-13).

La actualización compara y escribe en una sola sentencia (``UPDATE … WHERE version = :esperada
RETURNING version``). Bajo READ COMMITTED, si otra transacción tiene la fila bloqueada, PostgreSQL
espera su commit y vuelve a evaluar el WHERE sobre la fila nueva: de dos escrituras con el mismo
If-Match gana exactamente una, y la otra no escribe nada.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session

from app.modules.care_plan.application.ports import PlanGuardado, SeccionGuardada
from app.modules.care_plan.domain.cifrado import SeccionCifrada
from app.modules.care_plan.domain.ficha import CAMPOS_FICHA, MODO_FICHA_RELEVO, Autor

# Los tres tipos de la ficha, desde las constantes del dominio (nunca desde la petición)
_TIPOS_FICHA = ", ".join(f"'{campo.value}'" for campo in CAMPOS_FICHA)

_OBTENER_PLAN = text("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = :persona_id AND grupo_id = :grupo_id")

_CREAR_PLAN = text(
    "INSERT INTO plan_cuidado (id, grupo_id, persona_cuidada_id, modo, completitud_pct, actualizado_por,"
    " creado_en, actualizado_en)"
    " VALUES (:id, :grupo_id, :persona_id, :modo, 0, :usuario_id, :ahora, :ahora)"
    " ON CONFLICT (persona_cuidada_id) DO NOTHING"
)

# El autor: id y nombre, nunca el email. Una cuenta eliminada o que RLS no muestra queda sin autor
_SELECT_SECCION = (
    "SELECT s.tipo, s.contenido_cifrado, s.nonce, s.tag_auth, s.kek_version, s.version, s.actualizado_en,"
    " u.id AS autor_id, u.nombre AS autor_nombre"
    " FROM plan_seccion s LEFT JOIN usuario u ON u.id = s.actualizado_por AND u.eliminado_en IS NULL"
)

_SECCIONES = text(_SELECT_SECCION + f" WHERE s.plan_id = :plan_id AND s.tipo IN ({_TIPOS_FICHA})")

_SECCION = text(_SELECT_SECCION + " WHERE s.plan_id = :plan_id AND s.tipo = :tipo")

_INSERTAR_SECCION = text(
    "INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version, version,"
    " actualizado_por, actualizado_en)"
    " VALUES (:plan_id, :tipo, :contenido, :nonce, :tag, :kek_version, 1, :usuario_id, :ahora)"
    " ON CONFLICT (plan_id, tipo) DO NOTHING"
)

_ACTUALIZAR_SECCION_SI_VERSION = text(
    "UPDATE plan_seccion SET contenido_cifrado = :contenido, nonce = :nonce, tag_auth = :tag,"
    " kek_version = :kek_version, version = version + 1, actualizado_por = :usuario_id, actualizado_en = :ahora"
    " WHERE plan_id = :plan_id AND tipo = :tipo AND version = :esperada"
    " RETURNING version"
)

# AES-GCM conserva el largo: un campo vaciado tiene contenido cifrado de largo 0
_CAMPOS_CON_TEXTO = text(
    "SELECT count(*) FROM plan_seccion"
    f" WHERE plan_id = :plan_id AND tipo IN ({_TIPOS_FICHA}) AND octet_length(contenido_cifrado) > 0"
)

_ACTUALIZAR_PLAN = text(
    "UPDATE plan_cuidado SET completitud_pct = :completitud, actualizado_por = :usuario_id, actualizado_en = :ahora"
    " WHERE id = :plan_id AND grupo_id = :grupo_id"
)

_AUTOR = text("SELECT id, nombre FROM usuario WHERE id = :usuario_id AND eliminado_en IS NULL")


def _utc(instante: datetime) -> datetime:
    # La API responde siempre en UTC (arquitectura 9.1), sea cual sea la zona de la sesión de la base
    return instante.astimezone(UTC)


def _cifrada(contenido: Any, nonce: Any, tag: Any, kek_version: int) -> SeccionCifrada:
    return SeccionCifrada(
        contenido_cifrado=bytes(contenido), nonce=bytes(nonce), tag_auth=bytes(tag), kek_version=kek_version
    )


class RepositorioFichaSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def obtener_plan(self, persona_cuidada_id: uuid.UUID) -> PlanGuardado | None:
        fila = self._sesion.execute(
            _OBTENER_PLAN, {"persona_id": persona_cuidada_id, "grupo_id": self._grupo_id}
        ).one_or_none()
        return None if fila is None else PlanGuardado(id=fila.id)

    def crear_plan(
        self, plan_id: uuid.UUID, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, usuario_id: uuid.UUID,
        ahora: datetime,
    ) -> bool:
        resultado = cast(
            CursorResult[Any],
            self._sesion.execute(
                _CREAR_PLAN,
                {
                    "id": plan_id,
                    "grupo_id": grupo_id,
                    "persona_id": persona_cuidada_id,
                    "modo": MODO_FICHA_RELEVO,
                    "usuario_id": usuario_id,
                    "ahora": ahora,
                },
            ),
        )
        return resultado.rowcount == 1

    @staticmethod
    def _seccion_guardada(f: Any) -> SeccionGuardada:
        return SeccionGuardada(
            tipo=f.tipo,
            cifrada=_cifrada(f.contenido_cifrado, f.nonce, f.tag_auth, f.kek_version),
            version=f.version,
            actualizado_por=None if f.autor_id is None else Autor(id=f.autor_id, nombre=f.autor_nombre),
            actualizado_en=_utc(f.actualizado_en),
        )

    def secciones(self, plan_id: uuid.UUID) -> list[SeccionGuardada]:
        filas = self._sesion.execute(_SECCIONES, {"plan_id": plan_id}).all()
        return [self._seccion_guardada(f) for f in filas]

    def seccion(self, plan_id: uuid.UUID, tipo: str) -> SeccionGuardada | None:
        fila = self._sesion.execute(_SECCION, {"plan_id": plan_id, "tipo": tipo}).one_or_none()
        return None if fila is None else self._seccion_guardada(fila)

    def insertar_seccion(
        self, plan_id: uuid.UUID, tipo: str, cifrada: SeccionCifrada, usuario_id: uuid.UUID, ahora: datetime
    ) -> bool:
        resultado = cast(
            CursorResult[Any],
            self._sesion.execute(_INSERTAR_SECCION, self._parametros(plan_id, tipo, cifrada, usuario_id, ahora)),
        )
        return resultado.rowcount == 1

    def actualizar_seccion_si_version(
        self, plan_id: uuid.UUID, tipo: str, cifrada: SeccionCifrada, version_esperada: int, usuario_id: uuid.UUID,
        ahora: datetime,
    ) -> int | None:
        parametros = self._parametros(plan_id, tipo, cifrada, usuario_id, ahora)
        parametros["esperada"] = version_esperada
        nueva = self._sesion.execute(_ACTUALIZAR_SECCION_SI_VERSION, parametros).scalar_one_or_none()
        return None if nueva is None else int(nueva)

    def campos_con_texto(self, plan_id: uuid.UUID) -> int:
        return int(self._sesion.execute(_CAMPOS_CON_TEXTO, {"plan_id": plan_id}).scalar_one())

    def actualizar_plan(self, plan_id: uuid.UUID, completitud_pct: int, usuario_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(
            _ACTUALIZAR_PLAN,
            {
                "plan_id": plan_id,
                "grupo_id": self._grupo_id,
                "completitud": completitud_pct,
                "usuario_id": usuario_id,
                "ahora": ahora,
            },
        )

    def autor(self, usuario_id: uuid.UUID) -> Autor | None:
        fila = self._sesion.execute(_AUTOR, {"usuario_id": usuario_id}).one_or_none()
        return None if fila is None else Autor(id=fila.id, nombre=fila.nombre)

    @staticmethod
    def _parametros(
        plan_id: uuid.UUID, tipo: str, cifrada: SeccionCifrada, usuario_id: uuid.UUID, ahora: datetime
    ) -> dict[str, Any]:
        return {
            "plan_id": plan_id,
            "tipo": tipo,
            "contenido": cifrada.contenido_cifrado,
            "nonce": cifrada.nonce,
            "tag": cifrada.tag_auth,
            "kek_version": cifrada.kek_version,
            "usuario_id": usuario_id,
            "ahora": ahora,
        }
