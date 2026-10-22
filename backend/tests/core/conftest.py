"""Fixtures del esqueleto de la API: una app con rutas de prueba y sus logs capturados."""

import io
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errores import ErrorMATU
from app.main import crear_app


class CuerpoPrueba(BaseModel):
    nombre: str
    edad: int


@dataclass
class Entorno:
    cliente: TestClient
    salida_logs: io.StringIO

    def lineas_log(self) -> list[dict[str, Any]]:
        return [json.loads(linea) for linea in self.salida_logs.getvalue().splitlines() if linea.strip()]

    def texto_log(self) -> str:
        return self.salida_logs.getvalue()


@pytest.fixture
def secreto() -> str:
    """Un valor sintético único que nunca debe aparecer en una respuesta de error ni en un log."""
    return f"no-debe-aparecer-{uuid.uuid4().hex}"


@pytest.fixture
def entorno() -> Iterator[Entorno]:
    salida = io.StringIO()
    app = crear_app(stream_logs=salida)

    @app.post("/prueba/eco")
    def eco(cuerpo: CuerpoPrueba) -> dict[str, str]:
        return {"ok": "si"}

    @app.get("/prueba/item/{item_id}")
    def item(item_id: str) -> dict[str, str]:
        return {"ok": "si"}

    @app.get("/prueba/conflicto")
    def conflicto() -> None:
        raise ErrorMATU(409, tipo="email-registrado", detalle="Ese email ya tiene una cuenta")

    @app.post("/prueba/falla")
    def falla(cuerpo: dict[str, str]) -> None:
        # Simula un error de la base cuyo mensaje trae un valor de la fila
        raise RuntimeError("Key (email)=(" + cuerpo.get("valor", "") + ") already exists")

    # Un router con prefijo, como los de /v1, con un parámetro en la ruta
    router = APIRouter()

    @router.get("/grupos/{grupo_id}/cosas")
    def cosas(grupo_id: str) -> dict[str, str]:
        return {"ok": "si"}

    app.include_router(router, prefix="/prueba-v1")

    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield Entorno(cliente=cliente, salida_logs=salida)
