"""MATU-41 · GET y PUT /v1/yo/avisos contra PostgreSQL (decisión 111, RF-39).

La preferencia es del usuario autenticado: no hay forma de pedir la de otra persona, y RLS
(preferencia_propia) no lo deja aunque se intente. Solo datos sintéticos.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from tests.base_datos import requiere_base
from tests.fabricas import Fabrica, UsuarioCreado
from tests.modules.conftest import EntornoIam
from tests.modules.notifications.conftest import filas

pytestmark = [requiere_base, pytest.mark.rf("RF-39")]

RUTA = "/v1/yo/avisos"


@pytest.fixture
def fabrica_iam(entorno_iam: EntornoIam) -> Iterator[Fabrica]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    try:
        yield fabrica
    finally:
        fabrica.limpiar()


def _cabeceras(iam: EntornoIam, usuario: UsuarioCreado) -> dict[str, str]:
    respuesta = iam.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def _get(iam: EntornoIam, usuario: UsuarioCreado, **params: Any) -> Any:
    return iam.cliente.get(RUTA, headers=_cabeceras(iam, usuario), params=params)


def _put(iam: EntornoIam, usuario: UsuarioCreado, cuerpo: Any) -> Any:
    return iam.cliente.put(RUTA, json=cuerpo, headers=_cabeceras(iam, usuario))


def test_admin_sin_preferencia_recibe_por_los_dos_canales(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    familia = fabrica_iam.familia(miembros=())
    respuesta = _get(entorno_iam, familia.admin)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"correo": True, "push": True}
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_pagador_activa_y_admin_apaga(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    familia = fabrica_iam.familia(miembros=("pagador",))
    pagador = familia.miembros["pagador"].usuario
    assert _get(entorno_iam, pagador).json() == {"correo": False, "push": False}

    respuesta = _put(entorno_iam, pagador, {"correo": True, "push": False})
    assert respuesta.status_code == 200 and respuesta.json() == {"correo": True, "push": False}
    assert respuesta.headers["Cache-Control"] == "no-store"
    assert _get(entorno_iam, pagador).json() == {"correo": True, "push": False}

    admin = _put(entorno_iam, familia.admin, {"correo": False, "push": True})
    assert admin.json() == {"correo": False, "push": True}
    guardadas = filas(
        "SELECT usuario_id, canal, activo FROM preferencia_notificacion WHERE tipo_evento = 'quiebre_proximo'"
        " AND usuario_id = ANY(%s) ORDER BY canal", [pagador.id, familia.admin.id],
    )
    assert sorted(guardadas) == sorted([
        (pagador.id, "correo", True), (pagador.id, "push", False),
        (familia.admin.id, "correo", False), (familia.admin.id, "push", True),
    ])


def test_sin_grupos_no_recibe(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    assert _get(entorno_iam, fabrica_iam.usuario()).json() == {"correo": False, "push": False}


@pytest.mark.parametrize("metodo", ["GET", "PUT"])
def test_sin_sesion_es_401(entorno_iam: EntornoIam, metodo: str) -> None:
    respuesta = entorno_iam.cliente.request(metodo, RUTA, json={"correo": True, "push": True})
    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_token_invalido_es_401(entorno_iam: EntornoIam) -> None:
    respuesta = entorno_iam.cliente.get(RUTA, headers={"Authorization": "Bearer x.y.z"})
    assert respuesta.status_code == 401 and respuesta.json()["type"] == "/errores/token-invalido"


def test_otro_usuario_no_lee_ni_escribe_la_preferencia_ajena(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    carmen = fabrica_iam.familia(miembros=()).admin
    rodrigo = fabrica_iam.familia(miembros=()).admin
    assert entorno_iam.cliente.put(
        RUTA, json={"correo": False, "push": False}, headers=_cabeceras(entorno_iam, carmen)
    ).status_code == 200

    # Rodrigo ve la suya (por defecto), aunque intente pedir la de Carmen
    assert _get(entorno_iam, rodrigo).json() == {"correo": True, "push": True}
    assert _get(entorno_iam, rodrigo, usuario_id=str(carmen.id)).json() == {"correo": True, "push": True}
    # Un usuario_id en el cuerpo es 422, y la de Carmen no cambia
    respuesta = _put(entorno_iam, rodrigo, {"correo": True, "push": True, "usuario_id": str(carmen.id)})
    assert respuesta.status_code == 422
    assert _get(entorno_iam, carmen).json() == {"correo": False, "push": False}


@pytest.mark.parametrize(
    "cuerpo",
    [{"correo": "true", "push": True}, {"correo": True}, {"correo": None, "push": True}, {"correo": 1, "push": 0},
     {"correo": True, "push": True, "sms": True}],
)
def test_cuerpo_invalido_es_422_sin_repetir_el_valor(
    entorno_iam: EntornoIam, fabrica_iam: Fabrica, cuerpo: Any
) -> None:
    admin = fabrica_iam.familia(miembros=()).admin
    respuesta = entorno_iam.cliente.put(RUTA, json=cuerpo, headers=_cabeceras(entorno_iam, admin))
    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/validacion"
    assert '"true"' not in respuesta.text
    assert filas("SELECT 1 FROM preferencia_notificacion WHERE usuario_id = %s", admin.id) == []


def test_el_log_no_lleva_el_cuerpo(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    admin = fabrica_iam.familia(miembros=()).admin
    entorno_iam.cliente.put(RUTA, json={"correo": False, "push": True}, headers=_cabeceras(entorno_iam, admin))
    [linea] = [x for x in entorno_iam.lineas_log() if x.get("ruta") == RUTA]
    assert linea["usuario_id"] == str(admin.id) and "correo" not in str(linea)
    assert uuid.UUID(linea["request_id"])
