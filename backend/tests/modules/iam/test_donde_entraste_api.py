"""MATU-55 · «Dónde entraste»: los últimos ingresos de la propia cuenta, la clave pública de push y la auditoría de
los avisos (RF-37, RF-39; decisiones 253 a 270).

Contra PostgreSQL real, como matu_app. Las filas que la API no puede escribir en el instante que la prueba necesita
(lo de hace 90 días, o 21 eventos) las siembra el superusuario: el CHECK auditoria_cuenta_acotada las admite porque son
acciones de la cuenta. Solo datos sintéticos.
"""

import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import jwt
import psycopg
import pytest

from app.core.vapid import clave_publica, generar_clave_privada
from app.modules.iam.api.router_sesiones import obtener_clave_publica_vapid
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from tests.modules.iam.conftest import DSN, EntornoIam, requiere_base

pytestmark = [pytest.mark.rf("RF-37"), requiere_base]

ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36"
WINDOWS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"
PUSH = "https://fcm.googleapis.com/fcm/send/ejemplo-sintetico-donde-entraste"
PUSH_2 = "https://fcm.googleapis.com/fcm/send/ejemplo-sintetico-donde-entraste-otro"
RUTA = "/v1/yo/ingresos"
RUTA_PUSH = "/v1/dispositivos/actual/push"
# Los nombres que nunca salen en un evento (C3, decisión 256)
PROHIBIDOS = {"id", "request_id", "actor_ref", "actor_tipo", "entidad", "entidad_id", "detalle", "familia_id",
              "grupo_id", "ip", "plataforma", "push_token", "accion", "agente"}


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _sembrar(usuario: uuid.UUID, accion: str, cuando: Any, *, entidad: str = "usuario",
             entidad_id: uuid.UUID | None = None, actor: str = "usuario") -> None:
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "INSERT INTO auditoria (actor_tipo, actor_ref, accion, entidad, entidad_id, ocurrido_en)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (actor, usuario if actor == "usuario" else None, accion, entidad,
             entidad_id if entidad_id is not None else usuario, cuando),
        )


def _cuenta(entorno: EntornoIam, email: str, contrasena: str) -> uuid.UUID:
    respuesta = entorno.registrar(nombre="Familiar Uno", email=email, contrasena=contrasena)
    assert respuesta.status_code == 201
    return uuid.UUID(respuesta.json()["id"])


def _entrar(entorno: EntornoIam, email: str, contrasena: str, agente: str = ANDROID) -> str:
    entorno.cliente.cookies.clear()
    respuesta = entorno.cliente.post(
        "/v1/sesiones", json={"email": email, "contrasena": contrasena}, headers={"User-Agent": agente})
    assert respuesta.status_code == 200, respuesta.text
    return str(respuesta.json()["access_token"])


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _did(entorno: EntornoIam, token: str) -> uuid.UUID:
    claims = jwt.decode(
        token, entorno.clave_jwt, algorithms=["HS256"], options={"verify_exp": False, "verify_iat": False})
    return uuid.UUID(claims["did"])


def _claves(valor: Any) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _claves(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _claves(v)}
    return set()


def _ingresos(entorno: EntornoIam, token: str, *, cabeceras: dict[str, str] | None = None, **extra: Any) -> Any:
    respuesta = entorno.cliente.get(RUTA, headers={**_bearer(token), **(cabeceras or {})}, **extra)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    return respuesta.json()


@pytest.fixture
def cuenta(entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str) -> uuid.UUID:
    return _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)


@pytest.fixture
def clave_vapid(entorno_iam: EntornoIam) -> Iterator[str]:
    """Una clave VAPID generada al correr: ninguna queda escrita en el repositorio (decisión 262)."""
    publica = clave_publica(generar_clave_privada())
    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_clave_publica_vapid] = lambda: publica  # type: ignore[attr-defined]
    yield publica
    app.dependency_overrides.pop(obtener_clave_publica_vapid, None)  # type: ignore[attr-defined]


# --- Camino feliz --------------------------------------------------------------------------------------------------


def test_los_ultimos_ingresos_de_la_propia_cuenta(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    reloj = entorno_iam.reloj
    telefono = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    reloj.avanzar(timedelta(minutes=1))
    assert entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(telefono)).status_code == 204
    reloj.avanzar(timedelta(minutes=1))
    assert entorno_iam.cliente.put(
        "/v1/yo/avisos", json={"correo": False, "push": True}, headers=_bearer(telefono)).status_code == 200
    reloj.avanzar(timedelta(minutes=1))
    computador = _entrar(entorno_iam, email_sintetico, contrasena_sintetica, agente=WINDOWS)
    reloj.avanzar(timedelta(minutes=1))
    id_telefono = _did(entorno_iam, telefono)
    assert entorno_iam.cliente.delete(f"/v1/dispositivos/{id_telefono}", headers=_bearer(computador)).status_code == 204

    cuerpo = _ingresos(entorno_iam, computador)

    telefono_vista = {"nombre": "Chrome en Android", "clase": "telefono", "actual": False}
    assert cuerpo == {
        "eventos": [
            # El dispositivo de cerraste_en_dispositivo es el que se cerró; el de origen no se muestra
            {"tipo": "cerraste_en_dispositivo", "ocurrido_en": "2026-10-20T12:04:00Z", "dispositivo": telefono_vista},
            {"tipo": "entraste", "ocurrido_en": "2026-10-20T12:03:00Z",
             "dispositivo": {"nombre": "Firefox en Windows", "clase": "computador", "actual": True}},
            {"tipo": "avisos_cambiados", "ocurrido_en": "2026-10-20T12:02:00Z", "dispositivo": None},
            {"tipo": "avisos_activados", "ocurrido_en": "2026-10-20T12:01:00Z", "dispositivo": telefono_vista},
            {"tipo": "entraste", "ocurrido_en": "2026-10-20T12:00:00Z", "dispositivo": telefono_vista},
        ],
        "hay_mas": False,
    }
    assert not _claves(cuerpo) & PROHIBIDOS
    assert PUSH not in str(cuerpo) and str(id_telefono) not in str(cuerpo) and str(cuenta) not in str(cuerpo)
    # Leer no se audita (C10)
    assert _filas("SELECT count(*) FROM auditoria WHERE actor_ref = %s", cuenta) == [(5,)]


def test_lista_vacia_y_parametros_ignorados(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    otro_email = f"otro.{uuid.uuid4().hex[:10]}@ejemplo.cl"
    otro = _cuenta(entorno_iam, otro_email, contrasena_sintetica)
    # Ni un parámetro de usuario ni X-Grupo-Id cambian qué se ve (C2): A sigue viendo solo lo suyo
    cuerpo = _ingresos(entorno_iam, token, params={"usuario_id": str(otro), "desde": "2020-01-01", "pagina": "2"},
                       cabeceras={"X-Grupo-Id": str(uuid.uuid4())})
    assert [e["tipo"] for e in cuerpo["eventos"]] == ["entraste"]
    # Otra persona sin ingresos ve la lista vacía, no la de A
    _sembrar(otro, "cuenta.celular_solicitar", entorno_iam.reloj.ahora())
    assert _ingresos(entorno_iam, _token_sin_did(entorno_iam, otro)) == {"eventos": [], "hay_mas": False}


def _token_sin_did(entorno: EntornoIam, usuario: uuid.UUID) -> str:
    ahora = entorno.reloj.ahora()
    return EmisorJWT(entorno.clave_jwt).emitir(usuario, ahora, ahora + timedelta(minutes=15))


def test_ventana_de_90_dias_tope_de_20_y_fallidos_fuera(entorno_iam: EntornoIam, cuenta: uuid.UUID) -> None:
    ahora = entorno_iam.reloj.ahora()
    limite = ahora - timedelta(days=90)
    _sembrar(cuenta, "cuenta.contrasena_cambiar", limite - timedelta(seconds=1))  # fuera de la ventana
    _sembrar(cuenta, "cuenta.celular_verificar", limite)  # justo en el borde: entra
    # Lo que nunca entra (D1, Q5)
    for accion in ("cuenta.celular_solicitar", "cuenta.celular_verificar_fallido"):
        _sembrar(cuenta, accion, ahora)
    _sembrar(cuenta, "cuenta.recuperar_verificar_fallido", ahora, actor="sistema")
    _sembrar(cuenta, "cuenta.recuperar_solicitar", ahora - timedelta(days=1), actor="sistema")
    token = _token_sin_did(entorno_iam, cuenta)

    cuerpo = _ingresos(entorno_iam, token)
    assert cuerpo == {
        "eventos": [
            {"tipo": "codigo_recuperacion_pedido", "ocurrido_en": "2026-10-19T12:00:00Z", "dispositivo": None},
            {"tipo": "celular_confirmado", "ocurrido_en": "2026-07-22T12:00:00Z", "dispositivo": None},
        ],
        "hay_mas": False,
    }

    # Con 20 en la ventana no hay más; con 21, hay_mas y se muestran los 20 más recientes, a igual instante el último
    for minuto in range(18):
        _sembrar(cuenta, "avisos.preferencia", ahora - timedelta(minutes=minuto))
    cuerpo = _ingresos(entorno_iam, token)
    assert len(cuerpo["eventos"]) == 20 and cuerpo["hay_mas"] is False
    _sembrar(cuenta, "sesion.cerrar", ahora, entidad="dispositivo", entidad_id=uuid.uuid4())
    cuerpo = _ingresos(entorno_iam, token)
    assert len(cuerpo["eventos"]) == 20 and cuerpo["hay_mas"] is True
    # El de id mayor primero a igual instante; su dispositivo ya no existe: null
    assert cuerpo["eventos"][0] == {"tipo": "saliste", "ocurrido_en": "2026-10-20T12:00:00Z", "dispositivo": None}
    assert cuerpo["eventos"][-1]["tipo"] == "codigo_recuperacion_pedido"


# --- Camino de error -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("autorizacion", [None, "Bearer no-es-un-token"])
def test_sin_sesion_responde_401_sin_datos(entorno_iam: EntornoIam, autorizacion: str | None) -> None:
    cabeceras = {} if autorizacion is None else {"Authorization": autorizacion}
    for ruta in (RUTA, RUTA_PUSH):
        respuesta = entorno_iam.cliente.get(ruta, headers=cabeceras)
        assert respuesta.status_code == 401
        assert respuesta.headers["content-type"].startswith("application/problem+json")
        assert respuesta.json()["type"] in {"/errores/no-autenticado", "/errores/token-invalido"}
        assert respuesta.headers["cache-control"] == "no-store"
        assert respuesta.headers["www-authenticate"] == "Bearer"
        assert "eventos" not in respuesta.text and "clave_publica" not in respuesta.text


# --- Push: la clave pública y la auditoría solo si cambia (decisiones 260 a 262) -----------------------------------


@pytest.mark.rf("RF-39")
def test_ver_push_actual_con_la_clave_publica(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str, clave_vapid: str
) -> None:
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    respuesta = entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token))
    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.json() == {
        "clave_publica": clave_vapid, "permitido": True, "registrado": False, "envio_simulado": True}
    assert len(clave_vapid) == 87 and clave_vapid.startswith("B")

    assert entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token)).status_code == 204
    respuesta = entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token))
    assert respuesta.json()["registrado"] is True and PUSH not in respuesta.text
    # GET /v1/dispositivos dice también si tiene los avisos activados (C5)
    [dispositivo] = entorno_iam.cliente.get("/v1/dispositivos", headers=_bearer(token)).json()["items"]
    assert (dispositivo["clase"], dispositivo["push_activo"]) == ("telefono", True)
    # Leer no se audita
    assert [f[0] for f in _filas("SELECT accion FROM auditoria WHERE actor_ref = %s ORDER BY id", cuenta)] == [
        "sesion.iniciar", "dispositivo.push_registrar"]


@pytest.mark.rf("RF-39")
def test_ver_push_sin_clave_configurada_responde_null(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    entorno_iam.cliente.app.dependency_overrides[obtener_clave_publica_vapid] = lambda: None  # type: ignore[attr-defined]
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    assert entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token)).json() == {
        "clave_publica": None, "permitido": True, "registrado": False, "envio_simulado": True}


@pytest.mark.rf("RF-39")
def test_ver_push_sin_did_o_revocado_responde_404(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str, clave_vapid: str
) -> None:
    respuesta = entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(_token_sin_did(entorno_iam, cuenta)))
    assert respuesta.status_code == 404 and respuesta.json()["type"] == "/errores/no-encontrado"
    assert respuesta.headers["cache-control"] == "no-store" and clave_vapid not in respuesta.text
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    did = _did(entorno_iam, token)
    assert entorno_iam.cliente.delete(f"/v1/dispositivos/{did}", headers=_bearer(token)).status_code == 204
    assert entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token)).status_code == 404


@pytest.mark.rf("RF-39")
def test_push_audita_solo_si_el_endpoint_cambia(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    for cuerpo in ({"push_token": PUSH}, {"push_token": PUSH}, {"push_token": PUSH_2}):
        assert entorno_iam.cliente.put(RUTA_PUSH, json=cuerpo, headers=_bearer(token)).status_code == 204
    for _vez in range(2):
        assert entorno_iam.cliente.delete(RUTA_PUSH, headers=_bearer(token)).status_code == 204
    assert [f[0] for f in _filas("SELECT accion FROM auditoria WHERE actor_ref = %s ORDER BY id", cuenta)] == [
        "sesion.iniciar", "dispositivo.push_registrar", "dispositivo.push_registrar", "dispositivo.push_borrar"]


# --- La preferencia de avisos (decisión 259) -----------------------------------------------------------------------


@pytest.mark.rf("RF-39")
def test_la_preferencia_de_avisos_se_audita_solo_si_cambia_y_sin_valores(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    # Sin grupos, lo que corresponde por omisión es no recibir: pedir lo mismo no cambia nada
    actual = entorno_iam.cliente.get("/v1/yo/avisos", headers=_bearer(token)).json()
    assert entorno_iam.cliente.put("/v1/yo/avisos", json=actual, headers=_bearer(token)).status_code == 200
    # Un 422 no audita
    invalido = entorno_iam.cliente.put("/v1/yo/avisos", json={"correo": "talvez"}, headers=_bearer(token))
    assert invalido.status_code == 422
    cambio = {"correo": not actual["correo"], "push": actual["push"]}
    for _vez in range(2):
        assert entorno_iam.cliente.put("/v1/yo/avisos", json=cambio, headers=_bearer(token)).json() == cambio
    filas = _filas(
        "SELECT grupo_id, actor_tipo, entidad, entidad_id, detalle, request_id IS NOT NULL FROM auditoria"
        " WHERE actor_ref = %s AND accion = 'avisos.preferencia'", cuenta)
    assert filas == [(None, "usuario", "usuario", cuenta, None, True)]


# --- Logs (decisión 270) -------------------------------------------------------------------------------------------


def test_los_logs_no_llevan_los_eventos_ni_los_dispositivos(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str, clave_vapid: str
) -> None:
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    entorno_iam.cliente.put(RUTA_PUSH, json={"push_token": PUSH}, headers=_bearer(token))
    _ingresos(entorno_iam, token)
    entorno_iam.cliente.get(RUTA_PUSH, headers=_bearer(token))

    texto = entorno_iam.texto_log()
    peticiones = [linea for linea in entorno_iam.lineas_log() if linea.get("ruta") in {RUTA, RUTA_PUSH}]
    assert peticiones, "falta la línea de la petición"
    for prohibido in ("Chrome en Android", "entraste", "avisos_activados", PUSH, clave_vapid, token):
        assert prohibido not in texto, prohibido
