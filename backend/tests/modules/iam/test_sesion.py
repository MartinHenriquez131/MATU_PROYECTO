"""MATU-05a · Iniciar sesión y validar el access token (backlog v1.3, RF-37).

Las pruebas de login corren contra PostgreSQL real, como matu_app: el usuario se resuelve por
indice_credencial y la fila de usuario se lee con su contexto RLS. Las de usuario_actual no tocan
la base: el token se firma con la clave sintética del entorno.

Los tokens maliciosos se arman en la prueba, nunca como texto fijo en el código.
"""

import base64
import json
import uuid
from datetime import timedelta
from typing import Any

import jwt
import pytest

from app.modules.iam.api import dependencias
from app.modules.iam.api.router import obtener_repositorio_usuarios
from app.modules.iam.domain.sesion import vencimiento
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from tests.modules.iam.conftest import EntornoIam, fijar_estado, requiere_base

PROBLEMA = "application/problem+json"
CREDENCIALES_INVALIDAS = {
    "type": "/errores/credenciales-invalidas",
    "title": "No autenticado",
    "status": 401,
    "detail": "Email o contraseña incorrectos",
    "errores": [],
}


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _sin_request_id(respuesta: Any) -> dict[str, Any]:
    cuerpo = dict(respuesta.json())
    assert cuerpo.pop("request_id")
    return cuerpo


def _cuenta(entorno: EntornoIam, email: str, contrasena: str) -> uuid.UUID:
    respuesta = entorno.registrar(nombre="Familiar Uno", email=email, contrasena=contrasena)
    assert respuesta.status_code == 201
    return uuid.UUID(respuesta.json()["id"])


def _token(entorno: EntornoIam, usuario_id: uuid.UUID | None = None) -> str:
    """Un token válido firmado con la clave del entorno, emitido ahora según su reloj."""
    ahora = entorno.reloj.ahora()
    return EmisorJWT(entorno.clave_jwt).emitir(usuario_id or uuid.uuid4(), ahora, vencimiento(ahora))


def _rechazado(respuesta: Any) -> None:
    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert respuesta.headers["www-authenticate"] == "Bearer"


# --- Criterio 1 y 3: login correcto ----------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-37")
def test_login_correcto_entrega_jwt(entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str) -> None:
    usuario_id = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)

    # El email se normaliza igual que en el registro
    respuesta = entorno_iam.iniciar_sesion(email=f" {email_sintetico.upper()} ", contrasena=contrasena_sintetica)

    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"access_token", "token_type", "expira_en"}
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expira_en"] == 900

    token = cuerpo["access_token"]
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    claims = jwt.decode(token, entorno_iam.clave_jwt, algorithms=["HS256"], options={"verify_exp": False})
    assert claims["sub"] == str(usuario_id)
    assert claims["iat"] == int(entorno_iam.reloj.ahora().timestamp())
    assert claims["exp"] - claims["iat"] == 15 * 60

    # Y el token abre una ruta protegida
    yo = entorno_iam.yo(token)
    assert yo.status_code == 200
    assert yo.json() == {"id": str(usuario_id)}


# --- Criterio 2: el mismo 401 para cualquier falla ------------------------------------------


@requiere_base
@pytest.mark.rf("RF-37")
def test_login_incorrecto_mismo_mensaje(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)

    contrasena_mala = entorno_iam.iniciar_sesion(email=email_sintetico, contrasena=contrasena_sintetica + "x")
    email_malo = entorno_iam.iniciar_sesion(email="x" + email_sintetico, contrasena=contrasena_sintetica)

    for respuesta in (contrasena_mala, email_malo):
        assert respuesta.status_code == 401
        assert respuesta.headers["content-type"].startswith(PROBLEMA)
        assert "access_token" not in respuesta.text
    assert _sin_request_id(contrasena_mala) == _sin_request_id(email_malo) == CREDENCIALES_INVALIDAS


@requiere_base
@pytest.mark.rf("RF-37")
def test_email_inexistente_mismo_cuerpo_que_contrasena_incorrecta(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)

    contrasena_mala = entorno_iam.iniciar_sesion(email=email_sintetico, contrasena="otra-" + contrasena_sintetica)
    inexistente = entorno_iam.iniciar_sesion(
        email=f"nadie.{uuid.uuid4().hex[:12]}@ejemplo.cl", contrasena=contrasena_sintetica
    )

    assert contrasena_mala.status_code == inexistente.status_code == 401
    assert _sin_request_id(contrasena_mala) == _sin_request_id(inexistente)
    assert contrasena_mala.headers.keys() == inexistente.headers.keys()


@requiere_base
@pytest.mark.rf("RF-37")
def test_cuenta_bloqueada_401_mismo_mensaje(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario_id = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    fijar_estado(usuario_id, "bloqueado")

    # Aun con la contraseña correcta
    respuesta = entorno_iam.iniciar_sesion(email=email_sintetico, contrasena=contrasena_sintetica)

    assert respuesta.status_code == 401
    assert _sin_request_id(respuesta) == CREDENCIALES_INVALIDAS


@pytest.mark.rf("RF-37")
def test_contrasena_corta_no_da_422(entorno_iam: EntornoIam) -> None:
    # Sin largo mínimo en el login: un 422 por largo distinguiría casos. Sin base, ninguna cuenta.
    class SinCuentas:
        def buscar_credencial(self, email_hash: bytes) -> None:
            return None

    entorno_iam.cliente.app.dependency_overrides[obtener_repositorio_usuarios] = SinCuentas  # type: ignore[attr-defined]

    respuesta = entorno_iam.iniciar_sesion(email="familiar@ejemplo.cl", contrasena="corta")

    assert respuesta.status_code == 401
    assert _sin_request_id(respuesta) == CREDENCIALES_INVALIDAS


# --- Validación del cuerpo: nunca se repite el valor ----------------------------------------


@pytest.mark.rf("RF-37")
def test_login_contrasena_demasiado_larga_422_sin_el_valor(entorno_iam: EntornoIam) -> None:
    larga = "Zq9-larga-" + "y" * 119  # 129 caracteres

    respuesta = entorno_iam.iniciar_sesion(email="familiar@ejemplo.cl", contrasena=larga)

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["contrasena"]
    assert larga not in respuesta.text
    assert larga not in entorno_iam.texto_log()


@pytest.mark.rf("RF-37")
def test_login_email_demasiado_largo_422(entorno_iam: EntornoIam, contrasena_sintetica: str) -> None:
    respuesta = entorno_iam.iniciar_sesion(email="x" * 250 + "@ejemplo.cl", contrasena=contrasena_sintetica)

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["email"]


@pytest.mark.rf("RF-37")
def test_login_campos_extra_422(entorno_iam: EntornoIam, contrasena_sintetica: str) -> None:
    respuesta = entorno_iam.iniciar_sesion(email="familiar@ejemplo.cl", contrasena=contrasena_sintetica, rol="admin")

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["rol"]
    assert contrasena_sintetica not in respuesta.text


# --- Criterio 4: usuario_actual valida firma, vencimiento y algoritmo ------------------------


@pytest.mark.rf("RF-37")
def test_token_valido_abre_la_ruta(entorno_iam: EntornoIam) -> None:
    usuario_id = uuid.uuid4()

    respuesta = entorno_iam.yo(_token(entorno_iam, usuario_id))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": str(usuario_id)}


@pytest.mark.rf("RF-37")
def test_token_vencido_401(entorno_iam: EntornoIam) -> None:
    token = _token(entorno_iam)

    entorno_iam.reloj.avanzar(timedelta(minutes=14, seconds=59))
    assert entorno_iam.yo(token).status_code == 200

    entorno_iam.reloj.avanzar(timedelta(seconds=1))
    respuesta = entorno_iam.yo(token)

    _rechazado(respuesta)
    assert respuesta.json()["type"] == "/errores/token-invalido"
    assert respuesta.json()["detail"] == "Inicia sesión de nuevo"


@pytest.mark.rf("RF-37")
def test_token_alterado_401(entorno_iam: EntornoIam) -> None:
    cabecera, payload, firma = _token(entorno_iam).split(".")
    # Un carácter distinto en el payload, con la firma original
    alterado = payload[:5] + ("A" if payload[5] != "A" else "B") + payload[6:]

    respuesta = entorno_iam.yo(f"{cabecera}.{alterado}.{firma}")

    _rechazado(respuesta)
    assert respuesta.json()["type"] == "/errores/token-invalido"


@pytest.mark.rf("RF-37")
def test_token_con_otro_usuario_y_la_firma_original_401(entorno_iam: EntornoIam) -> None:
    cabecera, payload, firma = _token(entorno_iam).split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["sub"] = str(uuid.uuid4())

    respuesta = entorno_iam.yo(f"{cabecera}.{_b64(json.dumps(claims).encode())}.{firma}")

    _rechazado(respuesta)


@pytest.mark.rf("RF-37")
def test_alg_none_401(entorno_iam: EntornoIam) -> None:
    ahora = entorno_iam.reloj.ahora()
    cabecera = _b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    claims = {
        "sub": str(uuid.uuid4()),
        "iat": int(ahora.timestamp()),
        "exp": int(vencimiento(ahora).timestamp()),
    }

    respuesta = entorno_iam.yo(f"{cabecera}.{_b64(json.dumps(claims).encode())}.")

    _rechazado(respuesta)
    assert respuesta.json()["type"] == "/errores/token-invalido"


@pytest.mark.rf("RF-37")
def test_token_firmado_con_otra_clave_401(entorno_iam: EntornoIam) -> None:
    ahora = entorno_iam.reloj.ahora()
    ajeno = EmisorJWT(b"otra-clave-sintetica-" + entorno_iam.clave_jwt[:32]).emitir(
        uuid.uuid4(), ahora, vencimiento(ahora)
    )

    _rechazado(entorno_iam.yo(ajeno))


@pytest.mark.rf("RF-37")
def test_token_sin_exp_401(entorno_iam: EntornoIam) -> None:
    claims = {"sub": str(uuid.uuid4()), "iat": int(entorno_iam.reloj.ahora().timestamp())}
    token = jwt.encode(claims, entorno_iam.clave_jwt, algorithm="HS256")

    _rechazado(entorno_iam.yo(token))


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("autorizacion", [None, "", "Bearer", "Basic abc", "Token abc", "bearer"])
def test_sin_authorization_bearer_401(entorno_iam: EntornoIam, autorizacion: str | None) -> None:
    respuesta = entorno_iam.yo(autorizacion=autorizacion)

    _rechazado(respuesta)
    assert respuesta.json()["type"] == "/errores/no-autenticado"


@pytest.mark.parametrize("ruta", ["/v1/sesiones", "/prueba/yo"])
def test_sin_clave_jwt_responde_500_sin_detalle(
    entorno_iam: EntornoIam, monkeypatch: pytest.MonkeyPatch, ruta: str
) -> None:
    # Sin JWT_CLAVE no se emite ni se valida nada: es un error de despliegue, no del usuario
    class SinClave:
        jwt_clave = None

    class SinCuentas:
        def buscar_credencial(self, email_hash: bytes) -> None:
            return None

    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_repositorio_usuarios] = SinCuentas  # type: ignore[attr-defined]
    del app.dependency_overrides[dependencias.obtener_clave_jwt]  # type: ignore[attr-defined]
    monkeypatch.setattr(dependencias, "obtener_configuracion", SinClave)

    if ruta == "/v1/sesiones":
        respuesta = entorno_iam.iniciar_sesion(email="familiar@ejemplo.cl", contrasena="clave-sintetica")
    else:
        respuesta = entorno_iam.yo(_token(entorno_iam))

    assert respuesta.status_code == 500
    assert "JWT_CLAVE" not in respuesta.text


# --- Privacidad -------------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-37")
def test_login_no_deja_token_ni_contrasena_en_logs(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)

    respuesta = entorno_iam.iniciar_sesion(email=email_sintetico, contrasena=contrasena_sintetica)
    token = respuesta.json()["access_token"]
    entorno_iam.yo(token)
    otra_contrasena = "otra-" + contrasena_sintetica  # pragma: allowlist secret
    entorno_iam.iniciar_sesion(email=email_sintetico, contrasena=otra_contrasena)
    entorno_iam.reloj.avanzar(timedelta(minutes=15))
    entorno_iam.yo(token)

    log = entorno_iam.texto_log()
    assert token not in log
    # Ni siquiera la firma o el payload por separado
    for parte in token.split("."):
        assert parte not in log
    assert contrasena_sintetica not in log
    assert email_sintetico not in log
    estados = [(linea.get("ruta"), linea.get("estado")) for linea in entorno_iam.lineas_log()]
    assert ("/v1/sesiones", 200) in estados
    assert ("/v1/sesiones", 401) in estados
    assert ("/prueba/yo", 401) in estados
