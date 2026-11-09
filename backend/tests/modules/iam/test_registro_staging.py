"""MATU-25 · En staging, el registro solo acepta correos de dominios reservados (decisión 105, (i), RF-37).

Staging tiene solo datos sintéticos. Con ENTORNO=staging, POST /v1/usuarios responde 422 RFC 7807 con
errores[].campo = email y errores[].tipo = dominio_no_permitido si el correo no es de example.com,
example.org, example.net (o un subdominio de ellos) ni termina en .test, .example, .invalid o
.localhost. En local y pruebas no cambia nada.

Las pruebas de la regla y del 422 no tocan la base. Las de 201 corren contra PostgreSQL real.
"""

import io
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core import config
from app.main import crear_app
from app.modules.iam.api.router import obtener_repositorio_usuarios
from app.modules.iam.application.registro import registrar_usuario
from app.modules.iam.domain.credenciales import DominioNoPermitido, es_dominio_reservado
from tests.modules.iam.conftest import EntornoIam, requiere_base
from tests.politica import POLITICA_PRUEBAS

pytestmark = pytest.mark.rf("RF-37")

PROBLEMA = "application/problem+json"


# --- La regla ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email",
    [
        "x@example.com",
        "x@example.org",
        "x@example.net",
        "x@familia.example.com",
        "x@a.b.example.org",
        "X@EXAMPLE.COM",
        "  x@example.com ",
        "x@matu.test",
        "x@algo.example",
        "x@nada.invalid",
        "x@equipo.localhost",
        "x@test",
        "x@localhost",
    ],
)
def test_dominios_reservados(email: str) -> None:
    assert es_dominio_reservado(email)


@pytest.mark.parametrize(
    "email",
    [
        "x@gmail.com",
        "x@ejemplo.cl",
        "x@correo.ejemplo",
        "x@notexample.com",
        "x@example.com.cl",
        "x@example.co",
        "x@example.comx",
        "x@test.cl",
        "x@example.testing",
        "x@example.com.",
        "x@.example.com",
        "x@example..com",
        "x@",
        "sin-arroba",
        "x@example.com@gmail.com",
    ],
)
def test_dominios_no_reservados(email: str) -> None:
    assert not es_dominio_reservado(email)


class _RepositorioQueNoSeUsa:
    def crear(self, usuario: object) -> None:
        raise AssertionError("un correo de otro dominio no debía llegar al repositorio")


class _HasherQueNoSeUsa:
    def hashear(self, contrasena: str) -> str:
        raise AssertionError("un correo de otro dominio no debía llegar al hash")

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        raise AssertionError("no se usa")


def test_el_caso_de_uso_rechaza_antes_de_hashear_y_de_guardar(contrasena_sintetica: str) -> None:
    with pytest.raises(DominioNoPermitido) as error:
        registrar_usuario(
            nombre="Familiar",
            email="familiar@gmail.com",
            contrasena=contrasena_sintetica,
            telefono="+56900000001",
            pepper=b"p" * 32,
            hasher=_HasherQueNoSeUsa(),
            repositorio=_RepositorioQueNoSeUsa(),  # type: ignore[arg-type]
            politica=POLITICA_PRUEBAS,
            ahora=datetime(2026, 11, 9, 12, tzinfo=UTC),
            solo_dominios_reservados=True,
        )

    assert "gmail" not in str(error.value)


# --- La API -----------------------------------------------------------------------------------------


@pytest.fixture
def en_staging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """La configuración de la petición con ENTORNO=staging. La custodia y el envío no intervienen en el
    registro; se apagan para que el .env del equipo no cambie el resultado."""
    monkeypatch.setenv("ENTORNO", "staging")
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    monkeypatch.setenv("CUSTODIA_KEK", "")
    monkeypatch.setenv("KEK_ENTORNO", "")
    config.obtener_configuracion.cache_clear()
    yield
    config.obtener_configuracion.cache_clear()


@pytest.fixture
def sin_repositorio(entorno_iam: EntornoIam) -> EntornoIam:
    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_repositorio_usuarios] = _RepositorioQueNoSeUsa  # type: ignore[attr-defined]
    return entorno_iam


@pytest.mark.parametrize("email", ["x@gmail.com", "familiar@ejemplo.cl", "carmen@correo.ejemplo", "x@example.com.cl"])
def test_en_staging_otro_dominio_422_dominio_no_permitido(
    sin_repositorio: EntornoIam, en_staging: None, contrasena_sintetica: str, email: str
) -> None:
    respuesta = sin_repositorio.registrar(nombre="Familiar", email=email, contrasena=contrasena_sintetica)

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == PROBLEMA
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "/errores/validacion"
    assert cuerpo["status"] == 422
    assert [(e["campo"], e["tipo"]) for e in cuerpo["errores"]] == [("email", "dominio_no_permitido")]
    # Nunca repite el email, ni en la respuesta ni en el log
    assert email not in respuesta.text
    assert email.split("@")[1] not in respuesta.text
    assert email not in sin_repositorio.texto_log()
    assert sin_repositorio.creados == []


def test_en_staging_un_cuerpo_invalido_sigue_siendo_el_422_de_siempre(
    sin_repositorio: EntornoIam, en_staging: None
) -> None:
    # El cuerpo se valida antes que el dominio: una contraseña corta da su propio 422
    respuesta = sin_repositorio.registrar(nombre="Familiar", email="x@gmail.com", contrasena="corta")

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["contrasena"]


@requiere_base
def test_en_staging_example_com_201(entorno_iam: EntornoIam, en_staging: None, contrasena_sintetica: str) -> None:
    email = f"familiar.{uuid.uuid4().hex[:12]}@example.com"

    respuesta = entorno_iam.registrar(nombre="Familiar", email=email, contrasena=contrasena_sintetica)

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["email"] == email


@requiere_base
@pytest.mark.parametrize("entorno", ["local", "pruebas"])
def test_en_local_y_pruebas_ejemplo_cl_201(
    entorno_iam: EntornoIam, monkeypatch: pytest.MonkeyPatch, contrasena_sintetica: str, entorno: str
) -> None:
    monkeypatch.setenv("ENTORNO", entorno)
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    config.obtener_configuracion.cache_clear()
    try:
        email = f"familiar.{uuid.uuid4().hex[:12]}@ejemplo.cl"
        respuesta = entorno_iam.registrar(nombre="Familiar", email=email, contrasena=contrasena_sintetica)
    finally:
        config.obtener_configuracion.cache_clear()

    assert respuesta.status_code == 201, respuesta.text


# --- Contrato ---------------------------------------------------------------------------------------


def test_contrato_declara_dominio_no_permitido_en_el_422() -> None:
    esquema: dict[str, Any] = crear_app(io.StringIO()).openapi()
    operacion = esquema["paths"]["/v1/usuarios"]["post"]

    assert "dominio_no_permitido" in operacion["responses"]["422"]["description"]
    assert "staging" in operacion["description"]
