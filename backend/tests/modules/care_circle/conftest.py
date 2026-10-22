"""Fixtures de care_circle: rutas de prueba protegidas por sesion_de_grupo y sesion_de_usuario, y
grupos sembrados como superusuario (la API para crear grupos llega con MATU-06)."""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from app.modules.care_circle.api.dependencias import SesionDeGrupo
from app.modules.iam.api.dependencias import SesionDeUsuario
from tests.base_datos import DSN
from tests.modules.conftest import EntornoIam

_CONTEXTO = text("SELECT current_setting('app.usuario_id', true), current_setting('app.grupo_id', true)")


@pytest.fixture
def rutas_de_prueba() -> Callable[[FastAPI], None]:
    def registrar(app: FastAPI) -> None:
        @app.get("/prueba/grupo")
        def grupo(contexto: SesionDeGrupo) -> dict[str, Any]:
            usuario_en_base, grupo_en_base = contexto.sesion.execute(_CONTEXTO).one()
            return {
                "usuario_id": str(contexto.usuario_id),
                "grupo_id": str(contexto.grupo_id),
                "app_usuario_id": usuario_en_base,
                "app_grupo_id": grupo_en_base,
            }

        @app.get("/prueba/usuario")
        def usuario(sesion: SesionDeUsuario) -> dict[str, Any]:
            usuario_en_base, grupo_en_base = sesion.execute(_CONTEXTO).one()
            return {"app_usuario_id": usuario_en_base, "app_grupo_id": grupo_en_base}

    return registrar


@dataclass(frozen=True)
class Cuenta:
    id: uuid.UUID
    token: str


@dataclass
class EntornoGrupo:
    iam: EntornoIam
    grupos: list[uuid.UUID] = field(default_factory=list)

    def cuenta(self) -> Cuenta:
        """Registra una cuenta sintética por la API e inicia sesión con ella."""
        email = f"familiar.{uuid.uuid4().hex[:12]}@ejemplo.cl"
        contrasena = f"clave-{uuid.uuid4().hex[:16]}"
        registro = self.iam.registrar(nombre="Familiar Sintético", email=email, contrasena=contrasena)
        assert registro.status_code == 201
        sesion = self.iam.iniciar_sesion(email=email, contrasena=contrasena)
        assert sesion.status_code == 200
        return Cuenta(id=uuid.UUID(registro.json()["id"]), token=sesion.json()["access_token"])

    def grupo(self, creador: Cuenta, membresias: dict[uuid.UUID, str]) -> uuid.UUID:
        """Siembra un grupo y sus membresías como superusuario. membresias: usuario → estado."""
        grupo_id = uuid.uuid4()
        self.grupos.append(grupo_id)
        with psycopg.connect(DSN, autocommit=True) as cx:
            cx.execute(
                "INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES (%s, 'Familia Sintética', %s)",
                (grupo_id, creador.id),
            )
            for usuario_id, estado in membresias.items():
                rol = "admin" if usuario_id == creador.id else "cuidador"
                cx.execute(
                    "INSERT INTO membresia (grupo_id, usuario_id, rol, estado) VALUES (%s, %s, %s, %s)",
                    (grupo_id, usuario_id, rol, estado),
                )
        return grupo_id

    def pedir(self, ruta: str, token: str | None = None, grupo: str | None = None) -> Any:
        cabeceras = {}
        if token is not None:
            cabeceras["Authorization"] = f"Bearer {token}"
        if grupo is not None:
            cabeceras["X-Grupo-Id"] = grupo
        return self.iam.cliente.get(ruta, headers=cabeceras)


@pytest.fixture
def entorno_grupo(entorno_iam: EntornoIam) -> Iterator[EntornoGrupo]:
    entorno = EntornoGrupo(iam=entorno_iam)
    yield entorno
    # Antes de que entorno_iam borre las cuentas: membresia y grupo_familiar las referencian
    if entorno.grupos:
        with psycopg.connect(DSN, autocommit=True) as cx:
            cx.execute("DELETE FROM membresia WHERE grupo_id = ANY(%s)", (entorno.grupos,))
            cx.execute("DELETE FROM grupo_familiar WHERE id = ANY(%s)", (entorno.grupos,))
