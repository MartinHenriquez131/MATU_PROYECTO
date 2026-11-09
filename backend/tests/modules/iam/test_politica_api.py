"""MATU-75 · Crear la cuenta exige aceptar la política, y la titular lee su aceptación en «Tu cuenta».

Contra PostgreSQL real, conectada como matu_app. Las cuentas se crean por POST /v1/usuarios.
"""

import uuid
from datetime import datetime
from typing import Any

import psycopg
import pytest

from app.modules.iam.api.router_politica import obtener_politica_vigente
from tests.modules.iam.conftest import DSN, EntornoIam, contar_usuarios_con_email, requiere_base
from tests.politica import POLITICA_PRUEBAS

pytestmark = [pytest.mark.rf("RF-37"), requiere_base]


def _aceptaciones(usuario_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(
            "SELECT version, huella, aceptada_en FROM aceptacion_politica WHERE usuario_id = %s", (usuario_id,)
        ).fetchall()


def _token(entorno: EntornoIam, email: str, contrasena: str) -> dict[str, str]:
    entorno.cliente.cookies.clear()
    respuesta = entorno.iniciar_sesion(email=email, contrasena=contrasena)
    assert respuesta.status_code == 200
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def _registrar(entorno: EntornoIam, email: str, contrasena: str, **extra: Any) -> Any:
    return entorno.registrar(nombre="Familiar Uno", email=email, contrasena=contrasena, **extra)


@pytest.mark.parametrize("acepta", [None, False, "true", 1], ids=["sin-campo", "false", "texto", "numero"])
def test_sin_aceptar_la_politica_no_se_crea_la_cuenta(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, acepta: Any
) -> None:
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica, acepta_politica=acepta)

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["acepta_politica"]
    assert contar_usuarios_con_email(email_sintetico) == 0


def test_false_responde_politica_no_aceptada(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica, acepta_politica=False)
    assert respuesta.json()["errores"][0]["tipo"] == "politica_no_aceptada"


def test_aceptando_queda_la_fila_con_la_version_y_la_huella(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica)

    assert respuesta.status_code == 201
    [(version, huella, aceptada_en)] = _aceptaciones(uuid.UUID(respuesta.json()["id"]))
    assert (version, huella) == ("0.11", POLITICA_PRUEBAS.huella)
    assert aceptada_en == entorno_iam.reloj.ahora()


def test_con_la_huella_vigente_se_crea(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = _registrar(
        entorno_iam, email_sintetico, contrasena_sintetica, huella_politica=POLITICA_PRUEBAS.huella
    )
    assert respuesta.status_code == 201
    assert len(_aceptaciones(uuid.UUID(respuesta.json()["id"]))) == 1


def test_con_una_huella_vencida_responde_409_politica_cambio_y_no_crea_nada(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica, huella_politica="0" * 64)

    assert respuesta.status_code == 409
    assert respuesta.json()["type"] == "/errores/politica-cambio"
    assert contar_usuarios_con_email(email_sintetico) == 0


@pytest.mark.rf("RF-37")
def test_sin_huella_no_se_crea_la_cuenta(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    """Decisión 182: huella_politica es obligatoria. Sin ella, 422 junto al campo y no se crea nada."""
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica, huella_politica=None)
    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["huella_politica"]
    assert contar_usuarios_con_email(email_sintetico) == 0


def test_una_huella_mal_formada_es_422(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica, huella_politica="ABC")
    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["huella_politica"]


def test_sin_politica_disponible_responde_503_despues_de_validar(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    entorno_iam.cliente.app.dependency_overrides[obtener_politica_vigente] = lambda: None  # type: ignore[attr-defined]
    # El 422 de campos va antes que el 503
    assert _registrar(entorno_iam, email_sintetico, contrasena_sintetica, acepta_politica=False).status_code == 422
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica)
    assert respuesta.status_code == 503
    assert contar_usuarios_con_email(email_sintetico) == 0


def test_si_la_aceptacion_falla_no_queda_la_cuenta(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    """La cuenta y su aceptación van en la misma transacción: si la base rechaza la aceptación (CHECK de la
    versión), no queda la cuenta."""
    from dataclasses import replace

    rota = replace(POLITICA_PRUEBAS, version="v0.11")
    entorno_iam.cliente.app.dependency_overrides[obtener_politica_vigente] = lambda: rota  # type: ignore[attr-defined]

    assert _registrar(entorno_iam, email_sintetico, contrasena_sintetica).status_code == 500
    assert contar_usuarios_con_email(email_sintetico) == 0


# --- «Tu cuenta» -------------------------------------------------------------------------------------------------


def test_la_titular_lee_su_aceptacion_y_otra_cuenta_no(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    assert _registrar(entorno_iam, email_sintetico, contrasena_sintetica).status_code == 201
    otro_email = "otra." + email_sintetico
    otra = _registrar(entorno_iam, otro_email, contrasena_sintetica, telefono="+56 9 0000 0002")
    assert otra.status_code == 201

    cuenta = entorno_iam.cliente.get("/v1/cuenta", headers=_token(entorno_iam, email_sintetico, contrasena_sintetica))
    assert cuenta.status_code == 200
    aceptada = cuenta.json()["politica_aceptada"]
    assert set(aceptada) == {"version", "huella", "aceptada_en"}
    assert (aceptada["version"], aceptada["huella"]) == ("0.11", POLITICA_PRUEBAS.huella)
    assert datetime.fromisoformat(aceptada["aceptada_en"]) == entorno_iam.reloj.ahora()
    # Sin su propia fila, la otra cuenta no ve la de la titular: RLS aceptacion_propia_leer
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("DELETE FROM aceptacion_politica WHERE usuario_id = %s", (uuid.UUID(otra.json()["id"]),))
    de_la_otra = entorno_iam.cliente.get("/v1/cuenta", headers=_token(entorno_iam, otro_email, contrasena_sintetica))
    assert de_la_otra.json()["politica_aceptada"] is None


def test_una_cuenta_anterior_se_lee_sin_registro(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = _registrar(entorno_iam, email_sintetico, contrasena_sintetica)
    usuario_id = uuid.UUID(respuesta.json()["id"])
    # Una cuenta creada antes de MATU-75 no tiene fila (D2): se simula borrándola como superusuario
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("DELETE FROM aceptacion_politica WHERE usuario_id = %s", (usuario_id,))

    cuenta = entorno_iam.cliente.get("/v1/cuenta", headers=_token(entorno_iam, email_sintetico, contrasena_sintetica))
    assert cuenta.status_code == 200
    assert cuenta.json()["politica_aceptada"] is None
