"""MATU-02 · Contexto de tenant en la API (backlog v1.3, ADR-013).

Las rutas /prueba/grupo y /prueba/usuario solo existen en las pruebas: devuelven lo que la base
tiene en app.usuario_id y app.grupo_id dentro de la transacción de la petición.

Las pruebas con base corren como matu_app, con cuentas registradas e iniciadas por la API y
grupos sembrados como superusuario. Las de cabecera inválida no tocan la base: la fábrica de
sesiones se reemplaza por una que falla si alguien la usa.
"""

import uuid
from datetime import timedelta
from typing import Any, cast

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones
from app.modules.iam.domain.sesion import vencimiento
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from tests.base_datos import requiere_base
from tests.modules.care_circle.conftest import EntornoGrupo

PROBLEMA = "application/problem+json"
NO_ENCONTRADO = {
    "type": "/errores/no-encontrado",
    "title": "No encontrado",
    "status": 404,
    "detail": None,
    "errores": [],
}


def _sin_request_id(respuesta: Any) -> dict[str, Any]:
    cuerpo = dict(respuesta.json())
    assert cuerpo.pop("request_id")
    return cuerpo


def _no_encontrado(respuesta: Any) -> None:
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert _sin_request_id(respuesta) == NO_ENCONTRADO


def _peticiones(entorno: EntornoGrupo) -> list[dict[str, Any]]:
    return [linea for linea in entorno.iam.lineas_log() if linea["mensaje"] == "peticion"]


def _token_sintetico(entorno: EntornoGrupo) -> str:
    """Un token válido para un usuario cualquiera, sin pasar por la base."""
    ahora = entorno.iam.reloj.ahora()
    return EmisorJWT(entorno.iam.clave_jwt).emitir(uuid.uuid4(), ahora, vencimiento(ahora))


def _sin_base(entorno: EntornoGrupo) -> None:
    """Reemplaza la fábrica de sesiones por una que falla si alguien abre una sesión."""

    def fabrica_que_falla() -> Session:
        raise AssertionError("esta petición no debía abrir una sesión")

    app = cast(FastAPI, entorno.iam.cliente.app)
    app.dependency_overrides[obtener_fabrica_sesiones] = lambda: cast(sessionmaker[Session], fabrica_que_falla)


# --- Camino feliz --------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("ADR-013")
def test_miembro_activo_recibe_su_contexto(entorno_grupo: EntornoGrupo) -> None:
    # Dado un usuario miembro activo de un grupo
    a = entorno_grupo.cuenta()
    grupo = entorno_grupo.grupo(a, {a.id: "activa"})

    # Cuando pide una ruta del grupo con X-Grupo-Id
    respuesta = entorno_grupo.pedir("/prueba/grupo", a.token, str(grupo))

    # Entonces la transacción tiene su usuario y su grupo en el contexto
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "usuario_id": str(a.id),
        "grupo_id": str(grupo),
        "app_usuario_id": str(a.id),
        "app_grupo_id": str(grupo),
    }
    # Y el log de la petición registra la plantilla de la ruta, el usuario y el grupo
    linea = _peticiones(entorno_grupo)[-1]
    assert linea["ruta"] == "/prueba/grupo"
    assert linea["usuario_id"] == str(a.id)
    assert linea["grupo_id"] == str(grupo)
    assert a.token not in entorno_grupo.iam.texto_log()


@requiere_base
@pytest.mark.rf("ADR-013")
def test_contexto_de_la_api_no_se_filtra_entre_peticiones(entorno_grupo: EntornoGrupo) -> None:
    # Dada una petición con contexto de grupo
    a = entorno_grupo.cuenta()
    grupo = entorno_grupo.grupo(a, {a.id: "activa"})
    assert entorno_grupo.pedir("/prueba/grupo", a.token, str(grupo)).status_code == 200

    # Cuando la siguiente petición del mismo usuario no pide un grupo
    respuesta = entorno_grupo.pedir("/prueba/usuario", a.token)

    # Entonces su transacción tiene solo app.usuario_id, sin el grupo de la anterior
    assert respuesta.status_code == 200
    assert respuesta.json()["app_usuario_id"] == str(a.id)
    assert respuesta.json()["app_grupo_id"] in (None, "")
    assert "grupo_id" not in _peticiones(entorno_grupo)[-1]


# --- 404, nunca 403 ------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("ADR-013")
def test_no_miembro_recibe_404(entorno_grupo: EntornoGrupo) -> None:
    # Dado un grupo de A y un usuario B que no es miembro
    a = entorno_grupo.cuenta()
    b = entorno_grupo.cuenta()
    grupo = entorno_grupo.grupo(a, {a.id: "activa"})

    # Cuando B pide el grupo de A
    ajeno = entorno_grupo.pedir("/prueba/grupo", b.token, str(grupo))
    # Y pide un grupo que no existe
    inexistente = entorno_grupo.pedir("/prueba/grupo", b.token, str(uuid.uuid4()))

    # Entonces recibe 404, nunca 403, con el mismo cuerpo: no sabe si el grupo existe
    _no_encontrado(ajeno)
    _no_encontrado(inexistente)
    assert _sin_request_id(ajeno) == _sin_request_id(inexistente)
    # Y el log no registra un grupo que no se verificó
    assert "grupo_id" not in _peticiones(entorno_grupo)[-2]


@requiere_base
@pytest.mark.rf("ADR-013")
def test_membresia_suspendida_recibe_404(entorno_grupo: EntornoGrupo) -> None:
    a = entorno_grupo.cuenta()
    c = entorno_grupo.cuenta()
    grupo = entorno_grupo.grupo(a, {a.id: "activa", c.id: "suspendida"})

    _no_encontrado(entorno_grupo.pedir("/prueba/grupo", c.token, str(grupo)))


@requiere_base
@pytest.mark.rf("ADR-013")
def test_membresia_retirada_recibe_404(entorno_grupo: EntornoGrupo) -> None:
    a = entorno_grupo.cuenta()
    c = entorno_grupo.cuenta()
    grupo = entorno_grupo.grupo(a, {a.id: "activa", c.id: "retirada"})

    _no_encontrado(entorno_grupo.pedir("/prueba/grupo", c.token, str(grupo)))


@pytest.mark.rf("ADR-013")
@pytest.mark.parametrize("cabecera", [None, "", "no-es-un-uuid", "' OR 1=1 --"])
def test_sin_x_grupo_id_valido_recibe_404_sin_tocar_la_base(entorno_grupo: EntornoGrupo, cabecera: str | None) -> None:
    _sin_base(entorno_grupo)

    respuesta = entorno_grupo.pedir("/prueba/grupo", _token_sintetico(entorno_grupo), cabecera)

    _no_encontrado(respuesta)


# --- Autenticación -------------------------------------------------------------------------


@pytest.mark.rf("ADR-013")
def test_sin_token_recibe_401(entorno_grupo: EntornoGrupo) -> None:
    _sin_base(entorno_grupo)

    respuesta = entorno_grupo.pedir("/prueba/grupo", None, str(uuid.uuid4()))

    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.rf("ADR-013")
def test_token_vencido_recibe_401(entorno_grupo: EntornoGrupo) -> None:
    _sin_base(entorno_grupo)
    token = _token_sintetico(entorno_grupo)
    entorno_grupo.iam.reloj.avanzar(timedelta(minutes=16))

    respuesta = entorno_grupo.pedir("/prueba/grupo", token, str(uuid.uuid4()))

    assert respuesta.status_code == 401
