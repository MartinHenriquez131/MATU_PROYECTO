"""Adaptadores SQL de UnidadIam y RepositorioSesiones (MATU-38).

- resolver_refresh lee indice_token (sin RLS) antes de tener contexto, como el relevo (arquitectura
  7.7, excepción b). Después, cada transacción fija app.usuario_id con sesion_tenant y RLS
  (sesion_propia, dispositivo_propio, usuario_propio_*) acota todo al usuario.
- Nunca se lee push_token ni token_hash para devolverlos: solo se escriben.
- conservar fija app.rol = 'operacion' y llama a iam_conservar (migración 0008), que solo borra.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.iam.application.ports import (
    DatosCuenta,
    DispositivoGuardado,
    NuevoRefresh,
    RefreshIndexado,
    SesionGuardada,
    TransaccionIam,
)
from app.modules.iam.domain.dispositivo import NOMBRE_GENERICO, PLATAFORMA_WEB, LimitesConservacion
from app.modules.iam.domain.refresh import EstadoRefresh
from app.modules.iam.domain.sesion import puede_iniciar_sesion
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import RegistroAuditoria, Reloj

_RESOLVER = text(
    "SELECT usuario_id, referencia_id FROM indice_token"
    " WHERE token_hash = :hash AND tipo = 'refresh' AND usuario_id IS NOT NULL"
)

_SESION = text(
    "SELECT s.id, s.familia_id, s.dispositivo_id, s.expira_en, s.usado_en, s.revocado_en,"
    " d.revocado_en AS dispositivo_revocado_en, u.estado"
    " FROM sesion_refresh s"
    " JOIN dispositivo d ON d.id = s.dispositivo_id"
    " JOIN usuario u ON u.id = s.usuario_id"
    " WHERE s.id = :id"
    " FOR UPDATE OF s"
)

_DISPOSITIVO_COLUMNAS = "id, plataforma, nombre, creado_en, ultimo_uso_en, revocado_en"


def _dispositivo(fila: object) -> DispositivoGuardado:
    return DispositivoGuardado(
        id=fila.id,  # type: ignore[attr-defined]
        plataforma=fila.plataforma,  # type: ignore[attr-defined]
        nombre=fila.nombre or NOMBRE_GENERICO,  # type: ignore[attr-defined]
        creado_en=fila.creado_en,  # type: ignore[attr-defined]
        ultimo_uso_en=fila.ultimo_uso_en,  # type: ignore[attr-defined]
        revocado=fila.revocado_en is not None,  # type: ignore[attr-defined]
    )


class RepositorioSesionesSql:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def sesion_para_actualizar(self, sesion_id: uuid.UUID) -> SesionGuardada | None:
        fila = self._sesion.execute(_SESION, {"id": sesion_id}).one_or_none()
        if fila is None:
            return None
        return SesionGuardada(
            id=fila.id,
            familia_id=fila.familia_id,
            dispositivo_id=fila.dispositivo_id,
            estado=EstadoRefresh(
                expira_en=fila.expira_en,
                usado_en=fila.usado_en,
                revocado_en=fila.revocado_en,
                dispositivo_revocado=fila.dispositivo_revocado_en is not None,
                cuenta_activa=puede_iniciar_sesion(fila.estado),
            ),
        )

    def crear_refresh(self, nuevo: NuevoRefresh) -> None:
        self._sesion.execute(
            text(
                "INSERT INTO sesion_refresh (id, usuario_id, dispositivo_id, familia_id, token_hash, emitido_en,"
                " expira_en) VALUES (:id, :usuario_id, :dispositivo_id, :familia_id, :token_hash, :emitido_en,"
                " :expira_en)"
            ),
            {
                "id": nuevo.id,
                "usuario_id": nuevo.usuario_id,
                "dispositivo_id": nuevo.dispositivo_id,
                "familia_id": nuevo.familia_id,
                "token_hash": nuevo.token_hash,
                "emitido_en": nuevo.emitido_en,
                "expira_en": nuevo.expira_en,
            },
        )
        self._sesion.execute(
            text(
                "INSERT INTO indice_token (token_hash, tipo, usuario_id, referencia_id, expira_en, creado_en)"
                " VALUES (:token_hash, 'refresh', :usuario_id, :id, :expira_en, :emitido_en)"
            ),
            {
                "token_hash": nuevo.token_hash,
                "usuario_id": nuevo.usuario_id,
                "id": nuevo.id,
                "expira_en": nuevo.expira_en,
                "emitido_en": nuevo.emitido_en,
            },
        )

    def marcar_usado(self, sesion_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(
            text("UPDATE sesion_refresh SET usado_en = :ahora WHERE id = :id"), {"id": sesion_id, "ahora": ahora}
        )

    def _revocar(self, condicion: str, valor: uuid.UUID, motivo: str, ahora: datetime) -> list[uuid.UUID]:
        filas = self._sesion.execute(
            text(
                "UPDATE sesion_refresh SET revocado_en = :ahora, motivo_revocacion = :motivo"
                f" WHERE {condicion} = :valor AND revocado_en IS NULL RETURNING id, familia_id"
            ),
            {"valor": valor, "motivo": motivo, "ahora": ahora},
        ).all()
        ids = [fila.id for fila in filas]
        if ids:
            # La copia de indice_token (0007) también, para que una lectura sin contexto sepa que no sirve
            self._sesion.execute(
                text(
                    "UPDATE indice_token SET revocado_en = :ahora"
                    " WHERE tipo = 'refresh' AND referencia_id = ANY(:ids) AND revocado_en IS NULL"
                ),
                {"ahora": ahora, "ids": ids},
            )
        return [fila.familia_id for fila in filas]

    def revocar_familia(self, familia_id: uuid.UUID, motivo: str, ahora: datetime) -> int:
        return len(self._revocar("familia_id", familia_id, motivo, ahora))

    def revocar_todas(self, motivo: str, ahora: datetime) -> int:
        # RLS (sesion_propia) acota el UPDATE al usuario en contexto; la condición lo repite
        return len(set(self._revocar("usuario_id", self._usuario_id(), motivo, ahora)))

    def _usuario_id(self) -> uuid.UUID:
        valor = self._sesion.execute(text("SELECT app_usuario()")).scalar_one()
        if valor is None:
            raise RuntimeError("revocar_todas exige app.usuario_id")
        return uuid.UUID(str(valor))

    def revocar_sesiones_de_dispositivo(self, dispositivo_id: uuid.UUID, motivo: str, ahora: datetime) -> int:
        return len(set(self._revocar("dispositivo_id", dispositivo_id, motivo, ahora)))

    def crear_dispositivo(self, usuario_id: uuid.UUID, nombre: str, ahora: datetime) -> uuid.UUID:
        dispositivo_id = uuid.uuid4()
        self._sesion.execute(
            text(
                "INSERT INTO dispositivo (id, usuario_id, plataforma, nombre, creado_en, ultimo_uso_en)"
                " VALUES (:id, :usuario_id, :plataforma, :nombre, :ahora, :ahora)"
            ),
            {"id": dispositivo_id, "usuario_id": usuario_id, "plataforma": PLATAFORMA_WEB, "nombre": nombre,
             "ahora": ahora},
        )
        return dispositivo_id

    def tocar_dispositivo(self, dispositivo_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(
            text("UPDATE dispositivo SET ultimo_uso_en = :ahora WHERE id = :id"), {"id": dispositivo_id, "ahora": ahora}
        )

    def dispositivo_para_actualizar(self, dispositivo_id: uuid.UUID) -> DispositivoGuardado | None:
        fila = self._sesion.execute(
            text(f"SELECT {_DISPOSITIVO_COLUMNAS} FROM dispositivo WHERE id = :id FOR UPDATE"), {"id": dispositivo_id}
        ).one_or_none()
        return None if fila is None else _dispositivo(fila)

    def revocar_dispositivo(self, dispositivo_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(
            text(
                "UPDATE dispositivo SET revocado_en = coalesce(revocado_en, :ahora), push_token = NULL WHERE id = :id"
            ),
            {"id": dispositivo_id, "ahora": ahora},
        )

    def listar_dispositivos(self) -> list[DispositivoGuardado]:
        filas = self._sesion.execute(
            text(
                f"SELECT {_DISPOSITIVO_COLUMNAS} FROM dispositivo WHERE revocado_en IS NULL"
                " ORDER BY ultimo_uso_en DESC NULLS LAST, creado_en DESC"
            )
        ).all()
        return [_dispositivo(fila) for fila in filas]

    def guardar_push(self, dispositivo_id: uuid.UUID, push_token: str | None) -> bool:
        resultado = self._sesion.execute(
            text("UPDATE dispositivo SET push_token = :push WHERE id = :id AND revocado_en IS NULL RETURNING id"),
            {"id": dispositivo_id, "push": push_token},
        ).one_or_none()
        return resultado is not None


_DATOS_CUENTA = text(
    "SELECT id, nombre, email, telefono, estado, celular_verificado_en, celular_canal FROM usuario"
    " WHERE id = app_usuario()"
)


class RepositorioCuentaSql:
    """La fila de usuario del contexto (MATU-57). RLS usuario_propio_leer y usuario_propio_editar la acotan al
    usuario."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def datos(self) -> DatosCuenta | None:
        fila = self._sesion.execute(_DATOS_CUENTA).one_or_none()
        if fila is None:
            return None
        return DatosCuenta(
            id=fila.id,
            nombre=fila.nombre,
            email=fila.email,
            telefono=fila.telefono,
            estado=fila.estado,
            celular_verificado_en=fila.celular_verificado_en,
            celular_canal=fila.celular_canal,
        )

    def cambiar_contrasena(self, password_hash: str, ahora: datetime) -> None:
        self._sesion.execute(
            text("UPDATE usuario SET password_hash = :hash, actualizado_en = :ahora WHERE id = app_usuario()"),
            {"hash": password_hash, "ahora": ahora},
        )

    def marcar_celular_verificado(self, ahora: datetime, canal: str) -> None:
        self._sesion.execute(
            text(
                "UPDATE usuario SET celular_verificado_en = :ahora, celular_canal = :canal, actualizado_en = :ahora"
                " WHERE id = app_usuario()"
            ),
            {"ahora": ahora, "canal": canal},
        )


@dataclass(frozen=True)
class _TransaccionSql:
    sesiones: RepositorioSesionesSql
    auditoria: RegistroAuditoria
    cuenta: RepositorioCuentaSql


class UnidadIamSql:
    def __init__(self, fabrica: sessionmaker[Session], reloj: Reloj) -> None:
        self._fabrica = fabrica
        self._reloj = reloj

    def resolver_refresh(self, token_hash: bytes) -> RefreshIndexado | None:
        with self._fabrica() as sesion, sesion.begin():
            fila = sesion.execute(_RESOLVER, {"hash": token_hash}).one_or_none()
        if fila is None:
            return None
        return RefreshIndexado(usuario_id=fila.usuario_id, sesion_id=fila.referencia_id)

    @contextmanager
    def transaccion(self, usuario_id: uuid.UUID | None) -> Iterator[TransaccionIam]:
        with sesion_tenant(self._fabrica, usuario_id=usuario_id) as sesion:
            yield _TransaccionSql(
                sesiones=RepositorioSesionesSql(sesion),
                auditoria=RegistroAuditoriaSql(sesion, self._reloj),
                cuenta=RepositorioCuentaSql(sesion),
            )

    def conservar(self, limites: LimitesConservacion) -> tuple[int, int]:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            fila = sesion.execute(
                text("SELECT sesiones_borradas, dispositivos_borrados FROM iam_conservar(:ls, :ld, :ahora)"),
                {"ls": limites.limite_sesion, "ld": limites.limite_dispositivo, "ahora": limites.ahora},
            ).one()
        return int(fila.sesiones_borradas), int(fila.dispositivos_borrados)
