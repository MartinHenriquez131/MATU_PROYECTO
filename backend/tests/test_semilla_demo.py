"""MATU-30 · La semilla de demostración (infra/semillas/demo.py) crea dos familias y un pagador con
puede_ver_plan, sus cuentas inician sesión en la API, es idempotente y no corre en producción.

Las pruebas siembran familias con emails y nombres de grupo únicos, para no chocar con una semilla
de verdad en la base local, y las borran al terminar con la fábrica. La auditoría del alta se queda:
es de solo inserción y solo lleva identificadores.
"""

import importlib.util
import io
import secrets
import sys
import uuid
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import psycopg
import pytest
from argon2 import PasswordHasher, Type
from fastapi.testclient import TestClient

from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones
from app.main import crear_app
from app.modules.iam.api.dependencias import obtener_clave_jwt
from app.modules.iam.api.router import obtener_pepper_email
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id
from app.shared.reloj_sistema import RelojSistema
from tests.base_datos import DSN, requiere_base
from tests.fabricas import Fabrica

RUTA_SEMILLA = Path(__file__).resolve().parents[2] / "infra" / "semillas" / "demo.py"

pytestmark = pytest.mark.rf("MATU-30")


def _cargar_semilla() -> ModuleType:
    spec = importlib.util.spec_from_file_location("semilla_demo", RUTA_SEMILLA)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Registrado antes de ejecutarlo: dataclasses busca el módulo de cada clase en sys.modules
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


demo = _cargar_semilla()


def _familias_unicas() -> tuple[Any, ...]:
    """Las familias de la semilla con emails y nombres de grupo únicos para esta prueba."""
    sufijo = uuid.uuid4().hex[:8]

    def unica(cuenta: Any) -> Any:
        local, dominio = cuenta.email.split("@")
        return replace(cuenta, email=f"{local}.{sufijo}@{dominio}")

    return tuple(
        replace(f, grupo=f"{f.grupo} {sufijo}", admin=unica(f.admin), miembros=tuple(unica(m) for m in f.miembros))
        for f in demo.FAMILIAS
    )


@pytest.fixture
def pepper() -> bytes:
    return secrets.token_bytes(32)


@pytest.fixture
def sembradora(pepper: bytes) -> Any:
    # Argon2id real con el costo mínimo: la API verifica con los parámetros guardados en el hash
    rapido = HasherArgon2id(PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1, type=Type.ID))
    return demo.Sembradora(
        fabrica=fabrica_sesiones(), pepper=pepper, version_politica="0.9", reloj=RelojSistema(), hasher=rapido
    )


def _anotar(fabrica: Fabrica, familias: list[Any]) -> None:
    for familia in familias:
        fabrica.anotar("grupo_familiar", familia.grupo_id)
        for usuario_id in familia.usuarios:
            if usuario_id not in fabrica.ids("usuario"):
                fabrica.anotar("usuario", usuario_id)


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


@requiere_base
def test_crea_dos_familias_y_un_pagador_con_plan(fabrica: Fabrica, sembradora: Any, pepper: bytes) -> None:
    familias_demo = _familias_unicas()
    contrasena = f"clave-{secrets.token_hex(8)}"

    familias, cuentas = demo.sembrar(sembradora, contrasena, familias_demo)
    _anotar(fabrica, familias)

    assert len(familias) == 2 and all(c.creada for c in cuentas)
    soto, riquelme = (f.grupo_id for f in familias)
    membresias = _filas(
        "SELECT g.id, u.nombre, m.rol, m.puede_ver_plan, m.invitado_por IS NOT NULL FROM membresia m"
        " JOIN grupo_familiar g ON g.id = m.grupo_id JOIN usuario u ON u.id = m.usuario_id"
        " WHERE g.id = ANY(%s::uuid[]) ORDER BY u.nombre",
        [soto, riquelme],
    )
    assert sorted(membresias) == sorted(
        [
            (soto, "Carmen Fuentes", "admin", False, False),
            (soto, "Rodrigo Soto", "pagador", True, True),
            (riquelme, "Patricia Riquelme", "admin", False, False),
            (riquelme, "Tomás Riquelme", "observador", False, True),
        ]
    )
    consentimientos = _filas(
        "SELECT p.grupo_id, p.nombre, c.calidad_otorgante, c.version_politica, c.otorgado_en, c.revision_vence_en"
        " FROM persona_cuidada p JOIN consentimiento c ON c.persona_cuidada_id = p.id"
        " WHERE p.grupo_id = ANY(%s::uuid[]) AND c.finalidad = 'plan_cuidado' AND c.revocado_en IS NULL",
        [soto, riquelme],
    )
    por_grupo = {fila[0]: fila for fila in consentimientos}
    assert por_grupo[soto][1:4] == ("María Soto", "cuidador_de_hecho", "0.9")
    assert por_grupo[soto][5] - por_grupo[soto][4] >= timedelta(days=365)
    assert por_grupo[riquelme][1:4] == ("Hernán Riquelme", "titular", "0.9")
    assert por_grupo[riquelme][5] is None

    # Las cuentas sirven para iniciar sesión en la API con el mismo pepper
    app = crear_app(stream_logs=io.StringIO())
    app.dependency_overrides[obtener_pepper_email] = lambda: pepper
    app.dependency_overrides[obtener_clave_jwt] = lambda: secrets.token_hex(32).encode()
    with TestClient(app, raise_server_exceptions=False) as cliente:
        rodrigo = next(c for c in cuentas if c.nombre == "Rodrigo Soto")
        sesion = cliente.post("/v1/sesiones", json={"email": rodrigo.email, "contrasena": contrasena})
    assert sesion.status_code == 200


@requiere_base
def test_es_idempotente(fabrica: Fabrica, sembradora: Any) -> None:
    familias_demo = _familias_unicas()

    primera, _ = demo.sembrar(sembradora, f"clave-{secrets.token_hex(8)}", familias_demo)
    _anotar(fabrica, primera)
    segunda, cuentas = demo.sembrar(sembradora, f"clave-{secrets.token_hex(8)}", familias_demo)
    _anotar(fabrica, segunda)

    assert [f.grupo_id for f in segunda] == [f.grupo_id for f in primera]
    assert [f.usuarios for f in segunda] == [f.usuarios for f in primera]
    assert not any(c.creada for c in cuentas)
    assert not any(f.persona_creada for f in segunda)
    grupos = [f.grupo_id for f in primera]
    conteo = _filas(
        "SELECT (SELECT count(*) FROM membresia WHERE grupo_id = ANY(%s::uuid[])),"
        " (SELECT count(*) FROM persona_cuidada WHERE grupo_id = ANY(%s::uuid[])),"
        " (SELECT count(*) FROM consentimiento WHERE grupo_id = ANY(%s::uuid[]))",
        grupos,
        grupos,
        grupos,
    )
    assert conteo == [(4, 2, 2)]


@pytest.mark.usefixtures("configuracion_sin_env")
def test_no_corre_en_produccion(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("ENTORNO", "produccion")
    monkeypatch.setenv("POLITICA_VERSION", "0.9")
    obtener_configuracion.cache_clear()
    try:
        assert demo.main() == 2
    finally:
        obtener_configuracion.cache_clear()
    assert "produccion" in capsys.readouterr().err


# --- Solo como matu_app ---------------------------------------------------------------------------------

# Sin contraseña en la URL: basta para comprobar que el mensaje no la muestra
URL_SINTETICA = "postgresql+psycopg://dueno_sintetico@127.0.0.1:1/base_sintetica"


class _SesionFalsa:
    def __init__(self, resultado: str | Exception) -> None:
        self.resultado = resultado

    def __enter__(self) -> "_SesionFalsa":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sentencia: Any) -> "_SesionFalsa":
        assert str(sentencia) == "SELECT current_user"
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self

    def scalar_one(self) -> str:
        assert isinstance(self.resultado, str)
        return self.resultado


@pytest.fixture
def entorno_local(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Configuración local completa y sintética, con DATABASE_URL apuntando a nada."""
    monkeypatch.setenv("ENTORNO", "local")
    monkeypatch.setenv("POLITICA_VERSION", "0.9")
    monkeypatch.setenv("PEPPER_EMAIL", secrets.token_hex(32))
    monkeypatch.setenv("JWT_CLAVE", secrets.token_hex(32))
    monkeypatch.setenv("DATABASE_URL", URL_SINTETICA)
    obtener_configuracion.cache_clear()
    yield
    obtener_configuracion.cache_clear()


def _con_rol(monkeypatch: pytest.MonkeyPatch, resultado: str | Exception) -> list[str]:
    """Hace que la semilla vea ``resultado`` al preguntar current_user, y anota si llegó a sembrar."""
    sembro: list[str] = []
    monkeypatch.setattr(demo, "fabrica_sesiones", lambda: lambda: _SesionFalsa(resultado))

    def sembrar(*_: Any, **__: Any) -> tuple[list[Any], list[Any]]:
        sembro.append("sembro")
        return [], []

    monkeypatch.setattr(demo, "sembrar", sembrar)
    return sembro


@pytest.mark.parametrize("rol", ["postgres", "matu_owner", "MATU_APP"])
def test_se_niega_si_no_esta_conectada_como_matu_app(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], rol: str
) -> None:
    sembro = _con_rol(monkeypatch, rol)

    assert demo.main() == 2

    salida = capsys.readouterr()
    assert sembro == []
    assert "matu_app" in salida.err
    for fragmento in (URL_SINTETICA, "dueno_sintetico", "127.0.0.1", "base_sintetica"):
        assert fragmento not in salida.err + salida.out


def test_si_no_se_conecta_sale_con_1_sin_mostrar_la_url(
    entorno_local: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from sqlalchemy.exc import OperationalError

    sembro = _con_rol(monkeypatch, OperationalError("SELECT current_user", {}, Exception(URL_SINTETICA)))

    assert demo.main() == 1

    salida = capsys.readouterr()
    assert sembro == []
    assert "DATABASE_URL" in salida.err
    assert URL_SINTETICA not in salida.err + salida.out


def test_como_matu_app_siembra(entorno_local: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    sembro = _con_rol(monkeypatch, "matu_app")

    assert demo.main() == 0
    assert sembro == ["sembro"]


@requiere_base
def test_la_conexion_de_la_api_entra_como_matu_app() -> None:
    assert demo.rol_de_la_conexion(fabrica_sesiones()) == "matu_app"
