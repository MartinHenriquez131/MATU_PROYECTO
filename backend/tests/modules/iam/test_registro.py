"""MATU-04 · Crear una cuenta (backlog v1.3, RF-37).

Las pruebas de validación no tocan la base. Las de registro corren contra PostgreSQL real,
como matu_app, y revisan las filas como superusuario.
"""

import hashlib
import hmac

import pytest

from app.modules.iam.api.router import obtener_repositorio_usuarios
from app.modules.iam.domain.credenciales import EmailYaRegistrado
from tests.modules.iam.conftest import (
    EntornoIam,
    contar_usuarios_con_email,
    fila_usuario,
    filas_indice,
    requiere_base,
)

PROBLEMA = "application/problem+json"


# --- Camino feliz --------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-37")
def test_registro_guarda_argon2id(entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str) -> None:
    respuesta = entorno_iam.registrar(nombre="Familiar Uno", email=email_sintetico, contrasena=contrasena_sintetica)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "nombre", "email"}
    assert cuerpo["nombre"] == "Familiar Uno"

    fila = fila_usuario(entorno_iam.creados[0])
    assert fila is not None
    assert fila["password_hash"].startswith("$argon2id$")
    assert contrasena_sintetica not in fila["password_hash"]


@requiere_base
@pytest.mark.rf("RF-37")
def test_registro_normaliza_el_email(entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str) -> None:
    respuesta = entorno_iam.registrar(
        nombre="Familiar Uno", email=f"  {email_sintetico.upper()} ", contrasena=contrasena_sintetica
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["email"] == email_sintetico
    fila = fila_usuario(entorno_iam.creados[0])
    assert fila is not None
    assert fila["email"] == email_sintetico


@requiere_base
@pytest.mark.rf("RF-37")
def test_indice_credencial_no_guarda_email(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    entorno_iam.registrar(nombre="Familiar Uno", email=email_sintetico.upper(), contrasena=contrasena_sintetica)

    filas = filas_indice(entorno_iam.creados[0])

    assert len(filas) == 1
    email_hash = bytes(filas[0]["email_hash"])
    # Es el HMAC del email normalizado con el pepper, y no contiene el email
    assert email_hash == hmac.new(entorno_iam.pepper, email_sintetico.encode(), hashlib.sha256).digest()
    assert email_sintetico.encode() not in email_hash
    assert email_hash != hashlib.sha256(email_sintetico.encode()).digest()


# --- Email duplicado -----------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-37")
def test_email_duplicado_409(entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str) -> None:
    primera = entorno_iam.registrar(nombre="Familiar Uno", email=email_sintetico, contrasena=contrasena_sintetica)
    # El mismo email con otras mayúsculas es el mismo email
    segunda = entorno_iam.registrar(
        nombre="Familiar Dos", email=email_sintetico.upper(), contrasena=contrasena_sintetica
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert segunda.headers["content-type"].startswith(PROBLEMA)
    assert segunda.json()["type"] == "/errores/email-registrado"
    assert contar_usuarios_con_email(email_sintetico) == 1


@requiere_base
@pytest.mark.rf("RF-37")
def test_email_duplicado_no_aparece_en_respuesta_ni_logs(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    entorno_iam.registrar(nombre="Familiar Uno", email=email_sintetico, contrasena=contrasena_sintetica)
    segunda = entorno_iam.registrar(nombre="Familiar Dos", email=email_sintetico, contrasena=contrasena_sintetica)

    assert segunda.status_code == 409
    usuario_local = email_sintetico.split("@")[0]
    assert usuario_local not in segunda.text
    assert usuario_local not in entorno_iam.texto_log()
    assert contrasena_sintetica not in entorno_iam.texto_log()


def test_duplicado_de_la_base_se_traduce_a_409(entorno_iam: EntornoIam, contrasena_sintetica: str) -> None:
    # Sin base: el repositorio informa el duplicado y la API responde 409 sin guardar nada
    class RepositorioConDuplicado:
        def crear(self, usuario: object) -> None:
            raise EmailYaRegistrado()

    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_repositorio_usuarios] = RepositorioConDuplicado  # type: ignore[attr-defined]

    respuesta = entorno_iam.cliente.post(
        "/v1/usuarios", json={"nombre": "Familiar", "email": "familiar@ejemplo.cl", "contrasena": contrasena_sintetica}
    )

    assert respuesta.status_code == 409
    assert "familiar@ejemplo.cl" not in respuesta.text


# --- Validación: nunca se repite el valor recibido -----------------------------------------


@pytest.mark.rf("RF-37")
def test_contrasena_corta_422_sin_el_valor(entorno_iam: EntornoIam) -> None:
    corta = "Zq9-corta"  # 9 caracteres

    respuesta = entorno_iam.registrar(nombre="Familiar", email="familiar@ejemplo.cl", contrasena=corta)

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["contrasena"]
    assert corta not in respuesta.text
    assert corta not in entorno_iam.texto_log()


@pytest.mark.parametrize(
    "email_invalido",
    ["sin-arroba.ejemplo.cl", "con espacio@ejemplo.cl", "familiar@sin-punto", "<script>@ejemplo.cl ñ"],
)
def test_email_invalido_422_sin_el_valor(
    entorno_iam: EntornoIam, contrasena_sintetica: str, email_invalido: str
) -> None:
    respuesta = entorno_iam.registrar(nombre="Familiar", email=email_invalido, contrasena=contrasena_sintetica)

    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert [e["campo"] for e in errores] == ["email"]
    # Ni el valor ni sus caracteres raros aparecen en el mensaje (sugerencia de Jorge en el PR #2)
    assert email_invalido not in respuesta.text
    assert "<script>" not in respuesta.text
    assert email_invalido not in entorno_iam.texto_log()


def test_nombre_en_blanco_422(entorno_iam: EntornoIam, contrasena_sintetica: str) -> None:
    respuesta = entorno_iam.registrar(nombre="   ", email="familiar@ejemplo.cl", contrasena=contrasena_sintetica)

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["nombre"]


def test_campos_extra_422(entorno_iam: EntornoIam, contrasena_sintetica: str) -> None:
    # La cuenta no recibe nada más que nombre, email y contraseña (minimización)
    respuesta = entorno_iam.registrar(
        nombre="Familiar", email="familiar@ejemplo.cl", contrasena=contrasena_sintetica, es_operacion=True
    )

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["es_operacion"]


def test_contrasena_demasiado_larga_422(entorno_iam: EntornoIam) -> None:
    respuesta = entorno_iam.registrar(nombre="Familiar", email="familiar@ejemplo.cl", contrasena="x" * 129)

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["contrasena"]


# --- Privacidad del camino feliz -----------------------------------------------------------


@requiere_base
def test_registro_no_deja_contrasena_ni_email_en_logs(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = entorno_iam.registrar(nombre="Familiar Uno", email=email_sintetico, contrasena=contrasena_sintetica)

    assert respuesta.status_code == 201
    assert contrasena_sintetica not in respuesta.text
    log = entorno_iam.texto_log()
    assert contrasena_sintetica not in log
    assert email_sintetico not in log
    assert any(linea.get("ruta") == "/v1/usuarios" and linea.get("estado") == 201 for linea in entorno_iam.lineas_log())
