"""MATU-39 · POST /v1/usuarios pide el celular chileno, obligatorio (decisión 65, RF-37), y el
contrato declara su 409 email-registrado. El celular nunca aparece en logs, auditoría ni respuesta."""

import io
from typing import Any

import psycopg
import pytest

from app.main import crear_app
from app.modules.iam.api.router import obtener_repositorio_usuarios
from app.modules.iam.domain.credenciales import EmailYaRegistrado
from app.shared.celular import normalizar_celular
from tests.base_datos import DSN
from tests.modules.iam.conftest import EntornoIam, requiere_base

pytestmark = pytest.mark.rf("RF-37")


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("+56912345678", "+56912345678"),
        ("+56 9 1234 5678", "+56912345678"),
        ("56 9 1234 5678", "+56912345678"),
        ("912345678", "+56912345678"),
        ("9 1234 5678", "+56912345678"),
    ],
)
def test_celular_se_normaliza_a_e164(entrada: str, esperado: str) -> None:
    assert normalizar_celular(entrada) == esperado


@requiere_base
def test_registro_guarda_el_celular_normalizado(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = entorno_iam.registrar(
        nombre="Familiar Uno", email=email_sintetico, contrasena=contrasena_sintetica, telefono="+56 9 0000 0042"
    )

    assert respuesta.status_code == 201
    # La respuesta no devuelve el celular (minimización)
    assert set(respuesta.json()) == {"id", "nombre", "email"}
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT telefono FROM usuario WHERE id = %s", (entorno_iam.creados[0],)).fetchone()
        auditado = cx.execute(
            "SELECT count(*) FROM auditoria WHERE detalle::text LIKE %s", ("%900000042%",)
        ).fetchone()
    assert fila == ("+56900000042",)
    assert auditado == (0,)
    log = entorno_iam.texto_log()
    assert "900000042" not in log
    assert "0000 0042" not in log


@pytest.mark.parametrize(
    "invalido",
    ["221234567", "+56 2 2123 4567", "9123456", "+5691234567890", "+54 9 1234 5678", "nueve", "", "   "],
)
def test_celular_invalido_422_sin_el_valor(entorno_iam: EntornoIam, contrasena_sintetica: str, invalido: str) -> None:
    respuesta = entorno_iam.registrar(
        nombre="Familiar", email="familiar@ejemplo.cl", contrasena=contrasena_sintetica, telefono=invalido
    )

    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert [(e["campo"], e["tipo"]) for e in errores] == [("telefono", "celular_invalido")]
    if invalido.strip():
        assert invalido not in respuesta.text
        assert invalido not in entorno_iam.texto_log()
    assert entorno_iam.creados == []


def test_sin_celular_422(entorno_iam: EntornoIam, contrasena_sintetica: str) -> None:
    respuesta = entorno_iam.registrar(
        nombre="Familiar", email="familiar@ejemplo.cl", contrasena=contrasena_sintetica, telefono=None
    )

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["telefono"]


# --- Contrato ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def _operacion(esquema: dict[str, Any]) -> dict[str, Any]:
    operacion: dict[str, Any] = esquema["paths"]["/v1/usuarios"]["post"]
    return operacion


def test_contrato_declara_el_409_con_esquema_y_ejemplo(esquema: dict[str, Any]) -> None:
    contenido = _operacion(esquema)["responses"]["409"]["content"]["application/problem+json"]
    assert contenido["schema"]["properties"]["type"]["const"] == "/errores/email-registrado"
    assert contenido["schema"]["properties"]["status"]["const"] == 409
    assert contenido["example"]["type"] == "/errores/email-registrado"
    assert contenido["example"]["status"] == 409


def test_contrato_pide_el_celular(esquema: dict[str, Any]) -> None:
    ref = _operacion(esquema)["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    solicitud = esquema["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    assert "telefono" in solicitud["required"]
    assert "pattern" in solicitud["properties"]["telefono"]


def test_el_409_real_calza_con_el_ejemplo_declarado(
    entorno_iam: EntornoIam, contrasena_sintetica: str, esquema: dict[str, Any]
) -> None:
    class RepositorioConDuplicado:
        def crear(self, usuario: object) -> None:
            raise EmailYaRegistrado()

    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_repositorio_usuarios] = RepositorioConDuplicado  # type: ignore[attr-defined]
    respuesta = entorno_iam.registrar(nombre="Familiar", email="familiar@ejemplo.cl", contrasena=contrasena_sintetica)

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    ejemplo = _operacion(esquema)["responses"]["409"]["content"]["application/problem+json"]["example"]
    assert set(cuerpo) == set(ejemplo)
    campos = ("type", "title", "status", "detail")
    assert {k: cuerpo[k] for k in campos} == {k: ejemplo[k] for k in campos}
