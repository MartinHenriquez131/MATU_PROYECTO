"""Fixtures de iam: la API con sus logs capturados, un pepper y una clave JWT sintéticos, un reloj
fijo y limpieza de la base."""

import io
import json
import os
import secrets
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi import Depends
from fastapi.testclient import TestClient

from app.core.config import obtener_configuracion
from app.main import crear_app
from app.modules.iam.api.dependencias import UsuarioActual, obtener_clave_jwt, obtener_reloj, usuario_actual
from app.modules.iam.api.router import obtener_pepper_email
from tests.dobles.reloj_fijo import RelojFijo

load_dotenv(Path(__file__).resolve().parents[4] / ".env")
DSN = os.environ.get("MATU_TEST_DSN", "host=localhost port=5432 user=postgres dbname=matu")

requiere_base = pytest.mark.skipif(
    not obtener_configuracion().database_url, reason="DATABASE_URL no está definida"
)


@dataclass
class EntornoIam:
    cliente: TestClient
    salida_logs: io.StringIO
    pepper: bytes
    clave_jwt: bytes
    reloj: RelojFijo
    creados: list[uuid.UUID] = field(default_factory=list)

    def registrar(self, **cuerpo: Any) -> Any:
        respuesta = self.cliente.post("/v1/usuarios", json=cuerpo)
        if respuesta.status_code == 201:
            self.creados.append(uuid.UUID(respuesta.json()["id"]))
        return respuesta

    def iniciar_sesion(self, **cuerpo: Any) -> Any:
        return self.cliente.post("/v1/sesiones", json=cuerpo)

    def yo(self, token: str | None = None, *, autorizacion: str | None = None) -> Any:
        """GET /prueba/yo, una ruta protegida por usuario_actual que solo existe en las pruebas."""
        if autorizacion is None and token is not None:
            autorizacion = f"Bearer {token}"
        cabeceras = {"Authorization": autorizacion} if autorizacion is not None else {}
        return self.cliente.get("/prueba/yo", headers=cabeceras)

    def texto_log(self) -> str:
        return self.salida_logs.getvalue()

    def lineas_log(self) -> list[dict[str, Any]]:
        return [json.loads(linea) for linea in self.texto_log().splitlines() if linea.strip()]


@pytest.fixture
def email_sintetico() -> str:
    return f"familiar.{uuid.uuid4().hex[:12]}@ejemplo.cl"


@pytest.fixture
def contrasena_sintetica() -> str:
    """Una contraseña única que nunca debe aparecer en una respuesta, un log ni la base."""
    return f"clave-{secrets.token_hex(8)}"


@pytest.fixture
def entorno_iam(reloj_fijo: RelojFijo) -> Iterator[EntornoIam]:
    salida = io.StringIO()
    pepper = secrets.token_bytes(32)
    clave_jwt = secrets.token_hex(32).encode()
    app = crear_app(stream_logs=salida)
    app.dependency_overrides[obtener_pepper_email] = lambda: pepper
    app.dependency_overrides[obtener_clave_jwt] = lambda: clave_jwt
    # El mismo reloj emite y valida: la prueba lo hace avanzar para vencer el token
    app.dependency_overrides[obtener_reloj] = lambda: reloj_fijo

    @app.get("/prueba/yo")
    def yo(usuario: Annotated[UsuarioActual, Depends(usuario_actual)]) -> dict[str, str]:
        return {"id": str(usuario.id)}

    entorno = EntornoIam(
        cliente=TestClient(app, raise_server_exceptions=False),
        salida_logs=salida,
        pepper=pepper,
        clave_jwt=clave_jwt,
        reloj=reloj_fijo,
    )
    with entorno.cliente:
        yield entorno
    if entorno.creados:
        # Las filas se borran como superusuario: matu_app no ve las cuentas de otros (RLS)
        with psycopg.connect(DSN, autocommit=True) as cx:
            cx.execute("DELETE FROM usuario WHERE id = ANY(%s)", (entorno.creados,))


def fila_usuario(usuario_id: uuid.UUID) -> dict[str, Any] | None:
    with psycopg.connect(DSN) as cx, cx.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT id, email, nombre, password_hash FROM usuario WHERE id = %s", (usuario_id,))
        return cur.fetchone()


def filas_indice(usuario_id: uuid.UUID) -> list[dict[str, Any]]:
    with psycopg.connect(DSN) as cx, cx.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT email_hash, usuario_id FROM indice_credencial WHERE usuario_id = %s", (usuario_id,))
        return cur.fetchall()


def contar_usuarios_con_email(email: str) -> int:
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT count(*) FROM usuario WHERE lower(email) = lower(%s)", (email,)).fetchone()
        assert fila is not None
        return int(fila[0])


def fijar_estado(usuario_id: uuid.UUID, estado: str) -> None:
    """Cambia el estado de una cuenta como superusuario: la API aún no bloquea cuentas."""
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE usuario SET estado = %s WHERE id = %s", (estado, usuario_id))
