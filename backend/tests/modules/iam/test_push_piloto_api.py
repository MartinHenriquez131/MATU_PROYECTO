"""MATU-107 · C14 del piloto en la API: fuera de local y pruebas, solo las cuentas del equipo activan los avisos push.

Condiciones C-107-1, C-107-2, C-107-7 y C-107-8 del analista normativo. La política se reemplaza por una de staging o
produccion con UUID sintéticos generados en cada prueba; la regla es la real (app/core/push_piloto.py). Contra
PostgreSQL real, como matu_app. Solo datos sintéticos.
"""

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import psycopg
import pytest

from app.core.push_piloto import PoliticaPush, politica_push
from app.core.vapid import clave_publica, generar_clave_privada
from app.modules.iam.api.router_sesiones import obtener_clave_publica_vapid
from tests.modules.iam.conftest import DSN, EntornoIam, requiere_base

pytestmark = [pytest.mark.rf("RF-39"), requiere_base]

RUTA_PUSH = "/v1/dispositivos/actual/push"
PUSH = "https://fcm.googleapis.com/fcm/send/ejemplo-sintetico-push-piloto"
TIPO_409 = "/errores/push-no-permitido"

Fijar = Callable[[PoliticaPush], None]


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _cuenta_y_token(entorno: EntornoIam, email: str, contrasena: str) -> tuple[uuid.UUID, str]:
    registro = entorno.registrar(nombre="Familiar Uno", email=email, contrasena=contrasena)
    assert registro.status_code == 201, registro.text
    entorno.cliente.cookies.clear()
    entrada = entorno.cliente.post("/v1/sesiones", json={"email": email, "contrasena": contrasena})
    assert entrada.status_code == 200, entrada.text
    return uuid.UUID(registro.json()["id"]), str(entrada.json()["access_token"])


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _did(entorno: EntornoIam, token: str) -> uuid.UUID:
    claims = jwt.decode(
        token, entorno.clave_jwt, algorithms=["HS256"], options={"verify_exp": False, "verify_iat": False})
    return uuid.UUID(claims["did"])


def _push_guardado(dispositivo: uuid.UUID) -> str | None:
    [(token,)] = _filas("SELECT push_token FROM dispositivo WHERE id = %s", dispositivo)
    return token  # type: ignore[no-any-return]


def _acciones(cuenta: uuid.UUID) -> list[str]:
    return [f[0] for f in _filas("SELECT accion FROM auditoria WHERE actor_ref = %s ORDER BY id", cuenta)]


@pytest.fixture
def clave_vapid(entorno_iam: EntornoIam) -> Iterator[str]:
    """Una clave VAPID generada al correr (decisión 262): sin permiso, no debe llegar a la pantalla."""
    publica = clave_publica(generar_clave_privada())
    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_clave_publica_vapid] = lambda: publica  # type: ignore[attr-defined]
    yield publica
    app.dependency_overrides.pop(obtener_clave_publica_vapid, None)  # type: ignore[attr-defined]


@pytest.fixture
def fijar_politica(entorno_iam: EntornoIam) -> Iterator[Fijar]:
    """Reemplaza la política de la configuración por la de un entorno desplegado."""
    app = entorno_iam.cliente.app

    def fijar(politica: PoliticaPush) -> None:
        app.dependency_overrides[politica_push] = lambda: politica  # type: ignore[attr-defined]

    yield fijar
    app.dependency_overrides.pop(politica_push, None)  # type: ignore[attr-defined]


# --- Lista vacía: falla cerrada (C-107-1 a C-107-3) -----------------------------------------------------------------


@pytest.mark.parametrize("entorno", ["staging", "produccion"])
def test_con_la_lista_vacia_no_se_guarda_y_el_get_no_entrega_la_clave(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, clave_vapid: str, fijar_politica: Fijar,
    entorno: str,
) -> None:
    fijar_politica(PoliticaPush(entorno=entorno))
    cuenta, token = _cuenta_y_token(entorno_iam, email_sintetico, contrasena_sintetica)

    vista = entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token))
    assert vista.status_code == 200
    assert vista.json() == {"clave_publica": None, "permitido": False, "registrado": False, "envio_simulado": True}
    assert clave_vapid not in vista.text

    respuesta = entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token))
    assert respuesta.status_code == 409
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo = respuesta.json()
    assert cuerpo["type"] == TIPO_409 and cuerpo["status"] == 409
    assert PUSH not in respuesta.text and "fcm" not in respuesta.text
    assert _push_guardado(_did(entorno_iam, token)) is None
    # C-107-8: el rechazo no se audita
    assert _acciones(cuenta) == ["sesion.iniciar"]


# --- Cuenta fuera y cuenta dentro de la lista -----------------------------------------------------------------------


def test_una_cuenta_fuera_de_la_lista_no_guarda_ni_audita(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, clave_vapid: str, fijar_politica: Fijar
) -> None:
    otra = uuid.uuid4()
    fijar_politica(PoliticaPush(entorno="staging", permitidas=frozenset({otra})))
    cuenta, token = _cuenta_y_token(entorno_iam, email_sintetico, contrasena_sintetica)

    respuesta = entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token))

    assert respuesta.status_code == 409 and respuesta.json()["type"] == TIPO_409
    # Ni el token ni la lista en la respuesta
    assert PUSH not in respuesta.text and str(otra) not in respuesta.text
    assert _push_guardado(_did(entorno_iam, token)) is None
    assert "dispositivo.push_registrar" not in _acciones(cuenta)
    assert entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token)).json()["permitido"] is False


def test_una_cuenta_de_la_lista_guarda_y_audita_como_hoy(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, clave_vapid: str, fijar_politica: Fijar
) -> None:
    cuenta, token = _cuenta_y_token(entorno_iam, email_sintetico, contrasena_sintetica)
    fijar_politica(PoliticaPush(entorno="produccion", permitidas=frozenset({cuenta, uuid.uuid4()})))

    assert entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token)).json() == {
        "clave_publica": clave_vapid, "permitido": True, "registrado": False, "envio_simulado": True}
    assert entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token)).status_code == 204

    assert _push_guardado(_did(entorno_iam, token)) == PUSH
    assert _acciones(cuenta) == ["sesion.iniciar", "dispositivo.push_registrar"]
    assert entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token)).json()["registrado"] is True


# --- Apagar funciona siempre (C-107-1) ------------------------------------------------------------------------------


def test_delete_salir_y_sacar_un_dispositivo_funcionan_sin_permiso(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, fijar_politica: Fijar
) -> None:
    cuenta, token = _cuenta_y_token(entorno_iam, email_sintetico, contrasena_sintetica)
    did = _did(entorno_iam, token)
    # Guardado mientras la cuenta estaba en la lista; después se saca de la lista
    fijar_politica(PoliticaPush(entorno="staging", permitidas=frozenset({cuenta})))
    assert entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token)).status_code == 204
    fijar_politica(PoliticaPush(entorno="staging"))

    for _vez in range(2):
        assert entorno_iam.cliente.delete(RUTA_PUSH, headers=_bearer(token)).status_code == 204
    assert _push_guardado(did) is None
    assert _acciones(cuenta) == ["sesion.iniciar", "dispositivo.push_registrar", "dispositivo.push_borrar"]

    # Sacar el dispositivo también responde como siempre
    assert entorno_iam.cliente.delete(f"/v1/dispositivos/{did}", headers=_bearer(token)).status_code == 204


# --- En pruebas, sin cambios -----------------------------------------------------------------------------------------


def test_con_entorno_pruebas_no_cambia_nada(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, clave_vapid: str
) -> None:
    # Sin reemplazar la política: la de la configuración de las pruebas
    cuenta, token = _cuenta_y_token(entorno_iam, email_sintetico, contrasena_sintetica)
    assert entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token)).json() == {
        "clave_publica": clave_vapid, "permitido": True, "registrado": False, "envio_simulado": True}
    assert entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token)).status_code == 204
    assert _acciones(cuenta) == ["sesion.iniciar", "dispositivo.push_registrar"]


# --- Logs (C-107-7) --------------------------------------------------------------------------------------------------


def test_el_rechazo_deja_solo_la_linea_de_la_peticion(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, fijar_politica: Fijar
) -> None:
    otra, tercera = uuid.uuid4(), uuid.uuid4()
    fijar_politica(PoliticaPush(entorno="staging", permitidas=frozenset({otra, tercera})))
    cuenta, token = _cuenta_y_token(entorno_iam, email_sintetico, contrasena_sintetica)

    assert entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token)).status_code == 409

    texto = entorno_iam.texto_log()
    for prohibido in (PUSH, "fcm.googleapis", str(otra), otra.hex, str(tercera), tercera.hex, token):
        assert prohibido not in texto, prohibido
    [linea] = [x for x in entorno_iam.lineas_log() if x.get("ruta") == RUTA_PUSH]
    assert linea["mensaje"] == "peticion" and linea["metodo"] == "PUT" and linea["estado"] == 409
    assert linea["usuario_id"] == str(cuenta) and linea.get("request_id")
    # Ni la lista ni su largo: la línea solo tiene los campos de siempre
    assert not {"permitidas", "cuentas", "largo", "push_token"} & set(linea)
