"""Fixtures compartidas por las pruebas de módulos: la API con sus logs capturados, un pepper y una
clave JWT sintéticos, un reloj fijo y limpieza de las cuentas creadas."""

import io
import json
import secrets
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Annotated, Any

import psycopg
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.main import crear_app
from app.modules.iam.api.dependencias import UsuarioActual, obtener_clave_jwt, obtener_reloj, usuario_actual
from app.modules.iam.api.router import obtener_pepper_email
from tests.base_datos import DSN
from tests.dobles.reloj_fijo import RelojFijo


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
def rutas_de_prueba() -> Callable[[FastAPI], None]:
    """Registra rutas que solo existen en las pruebas. Cada módulo la sobreescribe en su conftest."""
    return lambda app: None


@pytest.fixture
def entorno_iam(reloj_fijo: RelojFijo, rutas_de_prueba: Callable[[FastAPI], None]) -> Iterator[EntornoIam]:
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

    rutas_de_prueba(app)

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
