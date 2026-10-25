"""Fixtures de iam: la API con sus logs capturados, un pepper sintético y limpieza de la base."""

import io
import json
import os
import secrets
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.core.config import obtener_configuracion
from app.main import crear_app
from app.modules.iam.api.router import obtener_pepper_email

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
    creados: list[uuid.UUID] = field(default_factory=list)

    def registrar(self, **cuerpo: Any) -> Any:
        respuesta = self.cliente.post("/v1/usuarios", json=cuerpo)
        if respuesta.status_code == 201:
            self.creados.append(uuid.UUID(respuesta.json()["id"]))
        return respuesta

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
def entorno_iam() -> Iterator[EntornoIam]:
    salida = io.StringIO()
    pepper = secrets.token_bytes(32)
    app = crear_app(stream_logs=salida)
    app.dependency_overrides[obtener_pepper_email] = lambda: pepper
    entorno = EntornoIam(cliente=TestClient(app, raise_server_exceptions=False), salida_logs=salida, pepper=pepper)
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
