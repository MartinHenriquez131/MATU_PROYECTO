"""Fixtures de care_circle: rutas de prueba protegidas por sesion_de_grupo y sesion_de_usuario,
grupos sembrados como superusuario y grupos creados por la API (MATU-06), y el entorno de personas
cuidadas con sus fábricas sintéticas (MATU-07).

Las siembras de grupos y membresías usan las mismas sentencias que las fábricas de MATU-30
(tests/fabricas/sql.py). Las pruebas nuevas usan directamente la fixture ``fabrica``."""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from app.modules.care_circle.api.dependencias import SesionDeGrupo
from app.modules.care_circle.api.router_personas import obtener_politica_version
from app.modules.iam.api.dependencias import SesionDeUsuario
from tests.base_datos import DSN
from tests.fabricas.sql import insertar_grupo, insertar_membresia
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
            insertar_grupo(cx, grupo_id, "Familia Sintética", creador.id)
            for usuario_id, estado in membresias.items():
                rol = "admin" if usuario_id == creador.id else "cuidador"
                insertar_membresia(cx, grupo_id, usuario_id, rol, estado=estado)
        return grupo_id

    def crear_grupo(self, token: str | None, cuerpo: Any) -> Any:
        """POST /v1/grupos. Si responde 201, el grupo queda anotado para limpiarlo."""
        cabeceras = {"Authorization": f"Bearer {token}"} if token is not None else {}
        respuesta = self.iam.cliente.post("/v1/grupos", json=cuerpo, headers=cabeceras)
        if respuesta.status_code == 201:
            self.grupos.append(uuid.UUID(respuesta.json()["id"]))
        return respuesta

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
    # Antes de que entorno_iam borre las cuentas: membresia y grupo_familiar las referencian.
    # También los grupos que crearon esas cuentas y que la prueba no anotó.
    if entorno.grupos or entorno_iam.creados:
        with psycopg.connect(DSN, autocommit=True) as cx:
            grupos = cx.execute(
                "SELECT id FROM grupo_familiar WHERE id = ANY(%s::uuid[]) OR creado_por = ANY(%s::uuid[])",
                (entorno.grupos, entorno_iam.creados),
            ).fetchall()
            ids = [fila[0] for fila in grupos]
            cx.execute("DELETE FROM membresia WHERE grupo_id = ANY(%s::uuid[])", (ids,))
            cx.execute("DELETE FROM grupo_familiar WHERE id = ANY(%s::uuid[])", (ids,))


# --- MATU-07 · Personas cuidadas -------------------------------------------------------------------
#
# Fábricas con datos sintéticos: nombres inventados y correos del dominio reservado example.com.

RUTA_PERSONAS = "/v1/grupos/{}/personas-cuidadas"
POLITICA_PRUEBAS = "0.9"


def cuerpo_alta(calidad: str = "titular", **cambios: Any) -> dict[str, Any]:
    """Un cuerpo válido de alta para la calidad indicada. ``cambios`` agrega o reemplaza campos."""
    cuerpo: dict[str, Any] = {
        "nombre": "Persona Ficticia Uno",
        "nombre_pila": "Uno",
        "nivel_apoyo": "apoyo_parcial",
        "calidad_otorgante": calidad,
    }
    if calidad == "representante_legal":
        cuerpo["referencia_documento"] = "Resolución sintética 123-2026"
    if calidad == "cuidador_de_hecho":
        cuerpo["aviso"] = {"id": "aviso_cuidador_de_hecho", "version": "1.0"}
    cuerpo.update(cambios)
    return cuerpo


def direccion_sintetica(**cambios: Any) -> dict[str, Any]:
    direccion: dict[str, Any] = {"calle": "Calle Ficticia", "numero": "100", "comuna": "Comuna Sintética"}
    direccion.update(cambios)
    return direccion


@dataclass
class EntornoPersonas:
    base: EntornoGrupo

    def cuenta(self) -> Cuenta:
        """Registra una cuenta sintética con un correo de example.com e inicia sesión con ella."""
        email = f"familiar.{uuid.uuid4().hex[:12]}@example.com"
        contrasena = f"clave-{uuid.uuid4().hex[:16]}"
        registro = self.base.iam.registrar(nombre="Familiar Ficticio", email=email, contrasena=contrasena)
        assert registro.status_code == 201
        sesion = self.base.iam.iniciar_sesion(email=email, contrasena=contrasena)
        assert sesion.status_code == 200
        return Cuenta(id=uuid.UUID(registro.json()["id"]), token=sesion.json()["access_token"])

    def grupo_con_roles(self, creador: Cuenta, roles: dict[uuid.UUID, str] | None = None) -> uuid.UUID:
        """Siembra como superusuario un grupo con el creador como admin y los demás con su rol."""
        grupo_id = uuid.uuid4()
        self.base.grupos.append(grupo_id)
        with psycopg.connect(DSN, autocommit=True) as cx:
            insertar_grupo(cx, grupo_id, "Familia Ficticia", creador.id)
            for usuario_id, rol in {creador.id: "admin", **(roles or {})}.items():
                insertar_membresia(cx, grupo_id, usuario_id, rol)
        return grupo_id

    def _cabeceras(self, token: str | None, grupo: uuid.UUID | str | None) -> dict[str, str]:
        cabeceras = {}
        if token is not None:
            cabeceras["Authorization"] = f"Bearer {token}"
        if grupo is not None:
            cabeceras["X-Grupo-Id"] = str(grupo)
        return cabeceras

    def crear(
        self, token: str | None, grupo: uuid.UUID | str | None, cuerpo: Any, grupo_path: uuid.UUID | str | None = None
    ) -> Any:
        """POST /v1/grupos/{grupo_path}/personas-cuidadas con X-Grupo-Id: grupo. Por omisión, el mismo."""
        ruta = RUTA_PERSONAS.format(grupo_path if grupo_path is not None else grupo)
        return self.base.iam.cliente.post(ruta, json=cuerpo, headers=self._cabeceras(token, grupo))

    def listar(
        self, token: str | None, grupo: uuid.UUID | str | None, grupo_path: uuid.UUID | str | None = None
    ) -> Any:
        ruta = RUTA_PERSONAS.format(grupo_path if grupo_path is not None else grupo)
        return self.base.iam.cliente.get(ruta, headers=self._cabeceras(token, grupo))


def _borrar_personas(grupos: list[uuid.UUID], usuarios: list[uuid.UUID]) -> None:
    """Borra como superusuario lo que el alta escribió en esos grupos. La auditoría es de solo
    inserción (trigger auditoria_solo_insercion) y se queda: solo lleva identificadores."""
    with psycopg.connect(DSN, autocommit=True) as cx, cx.transaction():
        filas = cx.execute(
            "SELECT id FROM grupo_familiar WHERE id = ANY(%s::uuid[]) OR creado_por = ANY(%s::uuid[])",
            (grupos, usuarios),
        ).fetchall()
        ids = [fila[0] for fila in filas]
        # consentimiento no se borra (trigger consentimiento_sin_borrado, 0006): solo para esta
        # sentencia, el superusuario apaga los triggers con el rol de réplica
        cx.execute("SET LOCAL session_replication_role = replica")
        cx.execute("DELETE FROM consentimiento WHERE grupo_id = ANY(%s::uuid[])", (ids,))
        cx.execute("SET LOCAL session_replication_role = origin")
        cx.execute("DELETE FROM persona_cuidada WHERE grupo_id = ANY(%s::uuid[])", (ids,))
        cx.execute("DELETE FROM direccion WHERE grupo_id = ANY(%s::uuid[])", (ids,))


@pytest.fixture
def entorno_personas(entorno_grupo: EntornoGrupo) -> Iterator[EntornoPersonas]:
    """La API contra la base, con la versión de la política fijada en POLITICA_PRUEBAS."""
    app = cast(FastAPI, entorno_grupo.iam.cliente.app)
    app.dependency_overrides[obtener_politica_version] = lambda: POLITICA_PRUEBAS
    entorno = EntornoPersonas(base=entorno_grupo)
    yield entorno
    # Antes de que entorno_grupo borre grupos y membresías, y entorno_iam las cuentas
    if entorno_grupo.grupos or entorno_grupo.iam.creados:
        _borrar_personas(entorno_grupo.grupos, entorno_grupo.iam.creados)
