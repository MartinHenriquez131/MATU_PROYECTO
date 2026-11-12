"""MATU-38 · Mantener la sesión abierta: refresh rotativo y dispositivos (RF-37).

Contra PostgreSQL real, como matu_app. La demora de la entrada usa ContadoresEnMemoria (el pipeline no
tiene Redis); el adaptador de Redis tiene su propia prueba (test_contadores_redis.py).

La cookie se envía a mano en cada petición: el TestClient habla http y el navegador nunca enviaría una
cookie Secure por http. Así cada prueba elige qué cookie presenta.
"""

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import psycopg
import pytest

from app.modules.iam.application.sesiones import conservar
from app.modules.iam.domain.dispositivo import LimitesConservacion, limites_conservacion
from app.modules.iam.domain.refresh import NOMBRE_COOKIE
from app.modules.iam.infrastructure.repositorio_sesiones import UnidadIamSql
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from tests.base_datos import fabrica_scheduler
from tests.dobles.contadores_en_memoria import ContadoresEnMemoria
from tests.modules.iam.conftest import DSN, EntornoIam, requiere_base

pytestmark = [pytest.mark.rf("RF-37"), requiere_base]

WEB = {"X-MATU-Cliente": "web"}
ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36"
WINDOWS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"
PUSH = "https://fcm.googleapis.com/fcm/send/ejemplo-sintetico-no-valido"
_COOKIE = re.compile(rf"^{re.escape(NOMBRE_COOKIE)}=([A-Za-z0-9_-]*); (.*)$")
ATRIBUTOS = "Path=/v1/sesiones; HttpOnly; Secure; SameSite=Strict"


# --- Apoyo ----------------------------------------------------------------------------------------


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _cuenta(entorno: EntornoIam, email: str, contrasena: str) -> uuid.UUID:
    respuesta = entorno.registrar(nombre="Familiar Uno", email=email, contrasena=contrasena)
    assert respuesta.status_code == 201
    return uuid.UUID(respuesta.json()["id"])


def _cookie(respuesta: Any) -> tuple[str, str]:
    """(valor, atributos) del Set-Cookie del refresh."""
    encontrado = _COOKIE.match(respuesta.headers["set-cookie"])
    assert encontrado, "falta la cookie del refresh"
    return encontrado.group(1), encontrado.group(2)


def _con_cookie(refresh: str | None, extra: dict[str, str] | None = None) -> dict[str, str]:
    cabeceras = dict(extra or {})
    if refresh is not None:
        cabeceras["Cookie"] = f"{NOMBRE_COOKIE}={refresh}"
    return cabeceras


def _entrar(entorno: EntornoIam, email: str, contrasena: str, *, refresh: str | None = None,
            agente: str = ANDROID) -> Any:
    entorno.cliente.cookies.clear()
    return entorno.cliente.post(
        "/v1/sesiones",
        json={"email": email, "contrasena": contrasena},
        headers=_con_cookie(refresh, {"User-Agent": agente}),
    )


def _renovar(entorno: EntornoIam, refresh: str | None, cabeceras: dict[str, str] | None = None) -> Any:
    entorno.cliente.cookies.clear()
    return entorno.cliente.post("/v1/sesiones/renovar", headers=_con_cookie(refresh, WEB if cabeceras is None
                                                                             else cabeceras))


def _cerrar(entorno: EntornoIam, refresh: str | None) -> Any:
    entorno.cliente.cookies.clear()
    return entorno.cliente.post("/v1/sesiones/cerrar", headers=_con_cookie(refresh, WEB))


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _did(entorno: EntornoIam, token: str) -> uuid.UUID:
    claims = jwt.decode(
        token, entorno.clave_jwt, algorithms=["HS256"], options={"verify_exp": False, "verify_iat": False}
    )
    return uuid.UUID(claims["did"])


def _sesion_expirada(respuesta: Any) -> None:
    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["type"] == "/errores/sesion-expirada"
    assert cuerpo["detail"] == "Vuelve a entrar con tu email y tu contraseña"
    assert respuesta.headers["set-cookie"] == f"{NOMBRE_COOKIE}=; Max-Age=0; {ATRIBUTOS}"
    assert respuesta.headers["cache-control"] == "no-store"
    assert "www-authenticate" not in respuesta.headers


def _auditoria(usuario_id: uuid.UUID) -> list[str]:
    return [fila[0] for fila in _filas(
        "SELECT accion FROM auditoria WHERE actor_ref = %s ORDER BY id", usuario_id)]


@pytest.fixture
def cuenta(entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str) -> uuid.UUID:
    return _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)


# --- Camino feliz: entrar → renovar → renovar → cerrar ----------------------------------------------


def test_ciclo_completo_entrar_renovar_renovar_cerrar(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    entrada = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    assert entrada.status_code == 200
    assert entrada.headers["cache-control"] == "no-store"
    assert set(entrada.json()) == {"access_token", "token_type", "expira_en"}
    assert entrada.json()["expira_en"] == 900
    refresh_1, atributos = _cookie(entrada)
    assert len(refresh_1) == 43
    assert atributos == f"Max-Age=2592000; {ATRIBUTOS}"
    dispositivo = _did(entorno_iam, entrada.json()["access_token"])

    # El refresh nunca está en el cuerpo, y la base guarda solo su SHA-256
    assert refresh_1 not in entrada.text
    [(familia, nombre)] = _filas(
        "SELECT s.familia_id, d.nombre FROM sesion_refresh s JOIN dispositivo d ON d.id = s.dispositivo_id"
        " WHERE s.usuario_id = %s", cuenta)
    assert nombre == "Chrome en Android"
    assert _filas("SELECT count(*) FROM sesion_refresh WHERE token_hash = %s", refresh_1.encode()) == [(0,)]

    entorno_iam.reloj.avanzar(timedelta(minutes=20))
    primera = _renovar(entorno_iam, refresh_1)
    assert primera.status_code == 200
    assert primera.headers["cache-control"] == "no-store"
    assert primera.json()["expira_en"] == 900
    refresh_2, atributos_2 = _cookie(primera)
    assert refresh_2 != refresh_1 and atributos_2 == f"Max-Age=2592000; {ATRIBUTOS}"
    assert _did(entorno_iam, primera.json()["access_token"]) == dispositivo

    entorno_iam.reloj.avanzar(timedelta(minutes=20))
    segunda = _renovar(entorno_iam, refresh_2)
    assert segunda.status_code == 200
    refresh_3, _ = _cookie(segunda)

    # Tres tokens de la misma familia: dos usados y uno vigente; ultimo_uso_en es la última renovación
    tokens = _filas(
        "SELECT usado_en IS NOT NULL, revocado_en IS NULL, expira_en - emitido_en FROM sesion_refresh"
        " WHERE familia_id = %s ORDER BY emitido_en", familia)
    assert tokens == [(True, True, timedelta(days=30))] * 2 + [(False, True, timedelta(days=30))]
    [(ultimo_uso,)] = _filas("SELECT ultimo_uso_en FROM dispositivo WHERE id = %s", dispositivo)
    assert ultimo_uso == entorno_iam.reloj.ahora()

    cierre = _cerrar(entorno_iam, refresh_3)
    assert cierre.status_code == 204
    assert cierre.content == b""
    assert cierre.headers["set-cookie"] == f"{NOMBRE_COOKIE}=; Max-Age=0; {ATRIBUTOS}"
    assert cierre.headers["cache-control"] == "no-store"
    assert _filas(
        "SELECT DISTINCT motivo_revocacion FROM sesion_refresh WHERE familia_id = %s", familia) == [("logout",)]
    assert _filas("SELECT revocado_en IS NOT NULL, push_token FROM dispositivo WHERE id = %s", dispositivo) == [
        (True, None)]

    # Después de cerrar, el refresh no renueva y cerrar otra vez sigue siendo 204
    _sesion_expirada(_renovar(entorno_iam, refresh_3))
    assert _cerrar(entorno_iam, refresh_3).status_code == 204
    assert _cerrar(entorno_iam, None).status_code == 204
    assert _cerrar(entorno_iam, "no-es-un-refresh").status_code == 204

    # Auditoría: entrar y cerrar, sin cada renovación
    assert _auditoria(cuenta) == ["sesion.iniciar", "sesion.cerrar"]
    assert _filas(
        "SELECT DISTINCT grupo_id, to_jsonb(a) ? 'ip', detalle FROM auditoria a WHERE actor_ref = %s", cuenta) == [
        (None, False, None)]


def test_ventana_deslizante_sin_tope_y_vencimiento_sin_uso(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    refresh, _ = _cookie(_entrar(entorno_iam, email_sintetico, contrasena_sintetica))
    # Renovar cada 29 días mantiene la sesión más allá de 30 días desde la entrada
    for _vuelta in range(3):
        entorno_iam.reloj.avanzar(timedelta(days=29))
        respuesta = _renovar(entorno_iam, refresh)
        assert respuesta.status_code == 200
        refresh, _ = _cookie(respuesta)
    # Un refresh sin usar durante 30 días vence solo
    entorno_iam.reloj.avanzar(timedelta(days=30))
    _sesion_expirada(_renovar(entorno_iam, refresh))


# --- Errores de la renovación ---------------------------------------------------------------------------


def test_refresh_reutilizado_revoca_la_familia_y_responde_401(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    refresh_1, _ = _cookie(_entrar(entorno_iam, email_sintetico, contrasena_sintetica))
    refresh_2, _ = _cookie(_renovar(entorno_iam, refresh_1))

    # Alguien presenta otra vez el refresh ya usado
    _sesion_expirada(_renovar(entorno_iam, refresh_1))

    # Toda la familia queda revocada con 'reutilizacion', también el token vigente
    assert _filas(
        "SELECT revocado_en IS NOT NULL, motivo_revocacion FROM sesion_refresh WHERE usuario_id = %s", cuenta
    ) == [(True, "reutilizacion")] * 2
    _sesion_expirada(_renovar(entorno_iam, refresh_2))
    assert _auditoria(cuenta) == ["sesion.iniciar", "sesion.reutilizacion_detectada"]

    # El evento de seguridad lleva la familia, nunca el token
    [evento] = [linea for linea in entorno_iam.lineas_log() if linea.get("evento") == "seguridad.reutilizacion_refresh"]
    [(familia,)] = _filas("SELECT DISTINCT familia_id FROM sesion_refresh WHERE usuario_id = %s", cuenta)
    assert evento["familia_id"] == str(familia) and evento["nivel"] == "WARNING"


@pytest.mark.parametrize(
    "cabeceras",
    [pytest.param({}, id="sin-cabecera"), pytest.param({"X-MATU-Cliente": "otro"}, id="otro-valor")],
)
def test_sin_cabecera_de_cliente_422_sin_tocar_la_sesion(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str,
    cabeceras: dict[str, str],
) -> None:
    refresh, _ = _cookie(_entrar(entorno_iam, email_sintetico, contrasena_sintetica))

    for ruta in ("/v1/sesiones/renovar", "/v1/sesiones/cerrar"):
        entorno_iam.cliente.cookies.clear()
        respuesta = entorno_iam.cliente.post(ruta, headers=_con_cookie(refresh, cabeceras))
        assert respuesta.status_code == 422
        assert respuesta.json()["type"] == "/errores/validacion"
        assert respuesta.json()["errores"][0]["campo"] == "X-MATU-Cliente"
        assert "set-cookie" not in respuesta.headers
        assert respuesta.headers["cache-control"] == "no-store"

    # No rotó ni revocó: el mismo refresh sigue sirviendo una vez
    assert _filas("SELECT usado_en, revocado_en FROM sesion_refresh WHERE usuario_id = %s", cuenta) == [(None, None)]
    assert _renovar(entorno_iam, refresh).status_code == 200


@pytest.mark.parametrize(
    "refresh",
    [pytest.param(None, id="sin-cookie"), pytest.param("corta", id="sin-forma"),
     pytest.param("A" * 43, id="desconocida")],
)
def test_cookie_que_no_sirve_es_el_mismo_401(entorno_iam: EntornoIam, refresh: str | None) -> None:
    _sesion_expirada(_renovar(entorno_iam, refresh))


def test_dispositivo_revocado_o_cuenta_bloqueada_no_renuevan(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    refresh, _ = _cookie(_entrar(entorno_iam, email_sintetico, contrasena_sintetica))
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE usuario SET estado = 'bloqueado' WHERE id = %s", (cuenta,))
    _sesion_expirada(_renovar(entorno_iam, refresh))
    # No fue reutilización: el token no se marcó ni se revocó
    assert _filas("SELECT usado_en, revocado_en FROM sesion_refresh WHERE usuario_id = %s", cuenta) == [(None, None)]


# --- Entrar: dispositivo, demora y fallos ------------------------------------------------------------------


def test_entrar_con_la_cookie_propia_reutiliza_el_dispositivo(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    primera = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    refresh_1, _ = _cookie(primera)
    segunda = _entrar(entorno_iam, email_sintetico, contrasena_sintetica, refresh=refresh_1)
    assert segunda.status_code == 200
    assert _did(entorno_iam, segunda.json()["access_token"]) == _did(entorno_iam, primera.json()["access_token"])
    assert _filas("SELECT count(*) FROM dispositivo WHERE usuario_id = %s", cuenta) == [(1,)]
    # Una sola sesión viva por dispositivo: la anterior se cerró con 'logout'
    _sesion_expirada(_renovar(entorno_iam, refresh_1))
    assert _filas(
        "SELECT count(*) FROM sesion_refresh WHERE usuario_id = %s AND motivo_revocacion = 'logout'", cuenta) == [(1,)]


def test_entrar_con_la_cookie_de_otro_usuario_crea_otro_dispositivo(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    otro_email = f"otro.{uuid.uuid4().hex[:10]}@ejemplo.cl"
    otro = _cuenta(entorno_iam, otro_email, contrasena_sintetica)
    refresh_otro, _ = _cookie(_entrar(entorno_iam, otro_email, contrasena_sintetica))

    propia = _entrar(entorno_iam, email_sintetico, contrasena_sintetica, refresh=refresh_otro)
    assert propia.status_code == 200
    assert _filas("SELECT count(*) FROM dispositivo WHERE usuario_id = %s", cuenta) == [(1,)]
    # La sesión del otro usuario no se tocó
    assert _filas("SELECT revocado_en FROM sesion_refresh WHERE usuario_id = %s", otro) == [(None,)]


def test_intentos_seguidos_responden_429_con_retry_after(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    for _ in range(5):
        assert _entrar(entorno_iam, email_sintetico, "incorrecta-1").status_code == 401
    entorno_iam.reloj.avanzar(timedelta(seconds=1))
    sexto = _entrar(entorno_iam, email_sintetico, "incorrecta-1")
    assert sexto.status_code == 401
    # Desde el 6.º fallo, 30 s de espera desde el último, aunque la contraseña sea la correcta
    entorno_iam.reloj.avanzar(timedelta(seconds=10))
    bloqueado = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    assert bloqueado.status_code == 429
    assert bloqueado.headers["retry-after"] == "20"
    assert bloqueado.headers["cache-control"] == "no-store"
    assert bloqueado.json()["type"] == "/errores/demasiadas-peticiones"
    # El mismo 429 para un email sin cuenta, con la misma IP… no: la IP aún no llega a 20. Un email sin
    # cuenta con 6 fallos recibe el mismo cuerpo
    nadie = f"nadie.{uuid.uuid4().hex[:10]}@ejemplo.cl"
    for _ in range(6):
        _entrar(entorno_iam, nadie, "incorrecta-1")
    sin_cuenta = _entrar(entorno_iam, nadie, "incorrecta-1")
    assert sin_cuenta.status_code == 429
    quitar = lambda c: {k: v for k, v in c.items() if k != "request_id"}  # noqa: E731
    assert quitar(sin_cuenta.json()) == quitar(bloqueado.json())

    # Pasada la espera, entra; el 200 borra el contador del email, nunca el de la IP. La cuenta no se bloqueó
    entorno_iam.reloj.avanzar(timedelta(seconds=20))
    assert _entrar(entorno_iam, email_sintetico, contrasena_sintetica).status_code == 200
    assert _filas("SELECT estado FROM usuario WHERE id = %s", cuenta) == [("activo",)]
    assert len(entorno_iam.contadores.datos) == 2  # la IP y el email sin cuenta

    # Cada fallo deja sesion.inicio_fallido sin actor y sin la huella del email (decisión 64)
    fallidos = _filas(
        "SELECT actor_tipo, actor_ref, grupo_id, detalle FROM auditoria WHERE accion = 'sesion.inicio_fallido'"
        " AND request_id = ANY(%s)", [r.headers["x-request-id"] for r in (sexto,)])
    assert len(fallidos) == 1
    actor_tipo, actor_ref, grupo_id, detalle = fallidos[0]
    assert (actor_tipo, actor_ref, grupo_id) == ("sistema", None, None)
    assert detalle is None


def test_sin_redis_la_entrada_falla_cerrada_con_503(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    entorno_iam.contadores.caido = True
    respuesta = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    assert respuesta.status_code == 503
    assert respuesta.json()["type"] == "/errores/servicio-no-disponible"
    assert "set-cookie" not in respuesta.headers
    assert _filas("SELECT count(*) FROM sesion_refresh WHERE usuario_id = %s", cuenta) == [(0,)]


def test_sin_pepper_limites_la_entrada_falla_cerrada(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    from app.modules.iam.api.sesion_web import obtener_pepper_limites

    app: Any = entorno_iam.cliente.app
    app.dependency_overrides[obtener_pepper_limites] = lambda: None
    assert _entrar(entorno_iam, email_sintetico, contrasena_sintetica).status_code == 503


# --- Dispositivos ----------------------------------------------------------------------------------------


def test_dispositivos_lista_el_actual_primero_sin_push_token(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    telefono = _entrar(entorno_iam, email_sintetico, contrasena_sintetica).json()["access_token"]
    entorno_iam.reloj.avanzar(timedelta(minutes=1))
    computador = _entrar(entorno_iam, email_sintetico, contrasena_sintetica, agente=WINDOWS).json()["access_token"]
    assert entorno_iam.cliente.put(
        "/v1/dispositivos/actual/push", json={"push_token": PUSH}, headers=_bearer(telefono)).status_code == 204

    respuesta = entorno_iam.cliente.get("/v1/dispositivos", headers=_bearer(telefono))
    assert respuesta.status_code == 200
    assert respuesta.headers["cache-control"] == "no-store"
    items = respuesta.json()["items"]
    assert [(d["nombre"], d["actual"]) for d in items] == [("Chrome en Android", True), ("Firefox en Windows", False)]
    # MATU-55: clase (C7) y push_activo (C5), nunca el endpoint
    assert set(items[0]) == {
        "id", "plataforma", "nombre", "clase", "creado_en", "ultimo_uso_en", "actual", "push_activo"}
    assert [(d["clase"], d["push_activo"]) for d in items] == [("telefono", True), ("computador", False)]
    assert PUSH not in respuesta.text and "push_token" not in respuesta.text and "fcm" not in respuesta.text
    assert _did(entorno_iam, computador) == uuid.UUID(items[1]["id"])


def test_sacar_un_dispositivo_revoca_sus_sesiones_y_su_push(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    entrada = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    refresh_telefono, _ = _cookie(entrada)
    telefono = entrada.json()["access_token"]
    entorno_iam.cliente.put("/v1/dispositivos/actual/push", json={"push_token": PUSH}, headers=_bearer(telefono))
    computador = _entrar(entorno_iam, email_sintetico, contrasena_sintetica, agente=WINDOWS).json()["access_token"]
    id_telefono = _did(entorno_iam, telefono)

    # Desde el computador saca el teléfono: no es el actual, así que no borra la cookie
    respuesta = entorno_iam.cliente.delete(f"/v1/dispositivos/{id_telefono}", headers=_bearer(computador))
    assert respuesta.status_code == 204
    assert "set-cookie" not in respuesta.headers
    assert _filas("SELECT revocado_en IS NOT NULL, push_token FROM dispositivo WHERE id = %s", id_telefono) == [
        (True, None)]
    assert _filas("SELECT motivo_revocacion FROM sesion_refresh WHERE dispositivo_id = %s", id_telefono) == [
        ("dispositivo",)]
    _sesion_expirada(_renovar(entorno_iam, refresh_telefono))
    [(detalle,)] = _filas(
        "SELECT detalle FROM auditoria WHERE accion = 'dispositivo.sacar' AND entidad_id = %s", id_telefono)
    assert detalle == {"sesiones_revocadas": 1}

    # Idempotente, y el teléfono ya no aparece
    assert entorno_iam.cliente.delete(f"/v1/dispositivos/{id_telefono}", headers=_bearer(computador)).status_code == 204
    listado = entorno_iam.cliente.get("/v1/dispositivos", headers=_bearer(computador)).json()["items"]
    assert [d["id"] for d in listado] == [str(_did(entorno_iam, computador))]

    # Sacar el actual borra además la cookie
    id_computador = _did(entorno_iam, computador)
    actual = entorno_iam.cliente.delete(f"/v1/dispositivos/{id_computador}", headers=_bearer(computador))
    assert actual.status_code == 204
    assert actual.headers["set-cookie"] == f"{NOMBRE_COOKIE}=; Max-Age=0; {ATRIBUTOS}"
    # Con el dispositivo revocado, el push del actual es 404
    assert entorno_iam.cliente.delete("/v1/dispositivos/actual/push", headers=_bearer(computador)).status_code == 404


@pytest.mark.parametrize("ruta", ["ajeno", "inexistente", "no-uuid"])
def test_dispositivo_ajeno_inexistente_o_sin_uuid_responde_404(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str, ruta: str
) -> None:
    propio = _entrar(entorno_iam, email_sintetico, contrasena_sintetica).json()["access_token"]
    otro_email = f"otro.{uuid.uuid4().hex[:10]}@ejemplo.cl"
    _cuenta(entorno_iam, otro_email, contrasena_sintetica)
    ajeno = _did(entorno_iam, _entrar(entorno_iam, otro_email, contrasena_sintetica).json()["access_token"])
    objetivo = {"ajeno": str(ajeno), "inexistente": str(uuid.uuid4()), "no-uuid": "no-es-uuid"}[ruta]

    respuesta = entorno_iam.cliente.delete(f"/v1/dispositivos/{objetivo}", headers=_bearer(propio))
    assert respuesta.status_code == 404
    assert respuesta.json()["type"] == "/errores/no-encontrado"
    assert respuesta.headers["cache-control"] == "no-store"
    # El dispositivo ajeno sigue intacto
    assert _filas("SELECT revocado_en FROM dispositivo WHERE id = %s", ajeno) == [(None,)]


def test_push_solo_se_escribe_y_respeta_la_lista_cerrada(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    token = _entrar(entorno_iam, email_sintetico, contrasena_sintetica).json()["access_token"]
    did = _did(entorno_iam, token)

    malo = "https://169.254.169.254/latest/meta-data/ejemplo"
    rechazo = entorno_iam.cliente.put("/v1/dispositivos/actual/push", json={"push_token": malo}, headers=_bearer(token))
    assert rechazo.status_code == 422
    assert rechazo.json()["errores"] == [
        {"campo": "push_token", "mensaje": "el servicio de avisos de este navegador no está admitido",
         "tipo": "push_no_admitido"}]
    assert malo not in rechazo.text
    extra = entorno_iam.cliente.put(
        "/v1/dispositivos/actual/push", json={"push_token": PUSH, "p256dh": "x"}, headers=_bearer(token))
    assert extra.status_code == 422

    guardado = entorno_iam.cliente.put(
        "/v1/dispositivos/actual/push", json={"push_token": PUSH}, headers=_bearer(token))
    assert guardado.status_code == 204 and guardado.content == b""
    assert _filas("SELECT push_token FROM dispositivo WHERE id = %s", did) == [(PUSH,)]
    borrado = entorno_iam.cliente.delete("/v1/dispositivos/actual/push", headers=_bearer(token))
    assert borrado.status_code == 204
    assert _filas("SELECT push_token FROM dispositivo WHERE id = %s", did) == [(None,)]
    assert entorno_iam.cliente.delete("/v1/dispositivos/actual/push", headers=_bearer(token)).status_code == 204
    # MATU-55 (decisión 260): borrar un endpoint ya vacío responde 204 sin auditar; antes eran dos push_borrar
    assert _auditoria(cuenta) == ["sesion.iniciar", "dispositivo.push_registrar", "dispositivo.push_borrar"]


def test_push_sin_did_responde_404_antes_que_422(entorno_iam: EntornoIam, cuenta: uuid.UUID) -> None:
    # Un access token anterior a MATU-38, sin did
    ahora = entorno_iam.reloj.ahora()
    viejo = EmisorJWT(entorno_iam.clave_jwt).emitir(cuenta, ahora, ahora + timedelta(minutes=15))
    for cuerpo in ({"push_token": PUSH}, {"push_token": "no-es-url"}):
        respuesta = entorno_iam.cliente.put("/v1/dispositivos/actual/push", json=cuerpo, headers=_bearer(viejo))
        assert respuesta.status_code == 404
    listado = entorno_iam.cliente.get("/v1/dispositivos", headers=_bearer(viejo))
    assert listado.status_code == 200 and listado.json() == {"items": []}
    assert entorno_iam.cliente.get("/v1/dispositivos").status_code == 401


# --- Conservación (decisión 59) ------------------------------------------------------------------------


def _sesiones_y_dispositivos(usuario_id: uuid.UUID) -> tuple[set[uuid.UUID], set[uuid.UUID], int]:
    """(dispositivos de las sesiones, dispositivos, índices de refresh) que quedan del usuario."""
    return (
        {fila[0] for fila in _filas("SELECT dispositivo_id FROM sesion_refresh WHERE usuario_id = %s", usuario_id)},
        {fila[0] for fila in _filas("SELECT id FROM dispositivo WHERE usuario_id = %s", usuario_id)},
        _filas("SELECT count(*) FROM indice_token WHERE tipo = 'refresh' AND usuario_id = %s", usuario_id)[0][0],
    )


def _por_borrar(limites: LimitesConservacion) -> tuple[int, int]:
    """MATU-73: (sesiones, dispositivos) que iam_conservar borraría ahora en toda la base, contados como
    superusuario con el mismo criterio de su definición en la migración 0008. Las sesiones son las
    vencidas o revocadas antes de limite_sesion más las que cuelgan de un dispositivo borrable; los
    dispositivos, los sin uso desde limite_dispositivo y sin una sesión vigente en ahora. Ninguna sesión
    del primer grupo es vigente, así que borrarlas antes no cambia qué dispositivos son borrables."""
    parametros = {"ls": limites.limite_sesion, "ld": limites.limite_dispositivo, "ahora": limites.ahora}
    with psycopg.connect(DSN) as cx:
        fila = cx.execute(
            """
            WITH borrables AS (
                SELECT d.id FROM dispositivo d
                 WHERE coalesce(d.ultimo_uso_en, d.creado_en) <= %(ld)s
                   AND NOT EXISTS (
                       SELECT 1 FROM sesion_refresh s
                        WHERE s.dispositivo_id = d.id AND s.revocado_en IS NULL AND s.usado_en IS NULL
                          AND s.expira_en > %(ahora)s))
            SELECT
                (SELECT count(*) FROM sesion_refresh s
                  WHERE s.expira_en <= %(ls)s
                     OR (s.revocado_en IS NOT NULL AND s.revocado_en <= %(ls)s)
                     OR s.dispositivo_id IN (SELECT id FROM borrables)),
                (SELECT count(*) FROM borrables)
            """,
            parametros,
        ).fetchone()
    assert fila is not None
    return int(fila[0]), int(fila[1])


def _dispositivo_ajeno(entorno: EntornoIam, ultimo_uso_en: datetime) -> uuid.UUID:
    """MATU-73: otra cuenta sintética con un dispositivo sin sesiones, sembrado como superusuario. El
    fixture lo borra con la cuenta."""
    respuesta = entorno.registrar(nombre="Familiar Ajeno", email=f"ajeno.{uuid.uuid4().hex[:12]}@example.com",
                                  contrasena=f"clave-{uuid.uuid4().hex[:16]}")
    assert respuesta.status_code == 201
    dispositivo_id = uuid.uuid4()
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "INSERT INTO dispositivo (id, usuario_id, plataforma, nombre, creado_en, ultimo_uso_en)"
            " VALUES (%s, %s, 'web', 'Firefox en Windows', %s, %s)",
            (dispositivo_id, respuesta.json()["id"], ultimo_uso_en, ultimo_uso_en),
        )
    return dispositivo_id


@pytest.mark.parametrize("con_ajeno", [False, True], ids=["solo_la_cuenta", "con_dispositivo_ajeno"])
def test_conservacion_borra_sesiones_y_dispositivos_vencidos(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str, con_ajeno: bool
) -> None:
    from app.modules.iam.api.dependencias import obtener_reloj
    from tests.dobles.reloj_fijo import RelojFijo

    # iam_conservar rechaza un ahora futuro: la prueba corre 100 días antes de la hora real y avanza
    reloj = RelojFijo(datetime.now(UTC) - timedelta(days=100))
    app: Any = entorno_iam.cliente.app
    app.dependency_overrides[obtener_reloj] = lambda: reloj
    entorno_iam.reloj = reloj

    # MATU-73: iam_conservar borra lo vencido de todas las cuentas de la base. La prueba mira sus filas,
    # y exige los contadores exactos contra lo que había por borrar en toda la base justo antes de cada
    # pasada. El caso con un dispositivo ajeno lo demuestra: sin uso desde medio día antes que el viejo,
    # sobrevive a la primera pasada y cae en la segunda
    ajeno = _dispositivo_ajeno(entorno_iam, reloj.ahora() - timedelta(hours=12)) if con_ajeno else None

    viejo = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    id_viejo = _did(entorno_iam, viejo.json()["access_token"])
    refresh_viejo, _ = _cookie(viejo)
    entorno_iam.reloj.avanzar(timedelta(days=80))
    actual = _entrar(entorno_iam, email_sintetico, contrasena_sintetica, agente=WINDOWS)
    id_actual = _did(entorno_iam, actual.json()["access_token"])
    assert id_viejo != id_actual
    assert _sesiones_y_dispositivos(cuenta) == ({id_viejo, id_actual}, {id_viejo, id_actual}, 2)

    # A los 89 días del viejo: su sesión venció hace 59 días (se borra), pero el dispositivo se conserva
    entorno_iam.reloj.avanzar(timedelta(days=9))
    unidad = UnidadIamSql(fabrica_scheduler(), entorno_iam.reloj)
    esperado = _por_borrar(limites_conservacion(entorno_iam.reloj.ahora()))
    resultado = conservar(unidad=unidad, reloj=entorno_iam.reloj)
    assert (resultado.sesiones_borradas, resultado.dispositivos_borrados) == esperado
    assert esperado[0] >= 1
    assert _sesiones_y_dispositivos(cuenta) == ({id_actual}, {id_viejo, id_actual}, 1)
    if ajeno is not None:
        assert _filas("SELECT count(*) FROM dispositivo WHERE id = %s", ajeno) == [(1,)]

    # A los 90 días sin uso, el viejo se borra; el actual, con sesión vigente, no
    entorno_iam.reloj.avanzar(timedelta(days=1))
    esperado = _por_borrar(limites_conservacion(entorno_iam.reloj.ahora()))
    resultado = conservar(unidad=unidad, reloj=entorno_iam.reloj)
    assert (resultado.sesiones_borradas, resultado.dispositivos_borrados) == esperado
    assert esperado[1] >= (2 if ajeno is not None else 1)
    assert _sesiones_y_dispositivos(cuenta) == ({id_actual}, {id_actual}, 1)
    if ajeno is not None:
        assert _filas("SELECT count(*) FROM dispositivo WHERE id = %s", ajeno) == [(0,)]
    _sesion_expirada(_renovar(entorno_iam, refresh_viejo))


def test_conservacion_exige_el_rol_de_operacion(entorno_iam: EntornoIam, cuenta: uuid.UUID) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from app.core.db import fabrica_sesiones, sesion_tenant

    ahora = entorno_iam.reloj.ahora()
    with pytest.raises(ProgrammingError), sesion_tenant(fabrica_sesiones(), usuario_id=cuenta) as sesion:
        sesion.execute(text("SELECT * FROM iam_conservar(:a, :a, :a)"), {"a": ahora})


# --- Logs de un ciclo completo -------------------------------------------------------------------------


def test_logs_de_un_ciclo_completo_no_tienen_secretos(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    _entrar(entorno_iam, email_sintetico, "incorrecta-1")
    entrada = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    refresh_1, _ = _cookie(entrada)
    acceso_1 = entrada.json()["access_token"]
    renovada = _renovar(entorno_iam, refresh_1)
    refresh_2, _ = _cookie(renovada)
    acceso_2 = renovada.json()["access_token"]
    entorno_iam.cliente.put("/v1/dispositivos/actual/push", json={"push_token": PUSH}, headers=_bearer(acceso_2))
    entorno_iam.cliente.get("/v1/dispositivos", headers=_bearer(acceso_2))
    _renovar(entorno_iam, refresh_1)  # reutilización
    _cerrar(entorno_iam, refresh_2)

    texto = entorno_iam.texto_log()
    assert texto
    prohibidos = {
        "refresh": refresh_1, "refresh 2": refresh_2, "access": acceso_1, "access 2": acceso_2,
        "cookie": NOMBRE_COOKIE, "contraseña": contrasena_sintetica, "contraseña incorrecta": "incorrecta-1",
        "push": PUSH, "email": email_sintetico, "ip": "testclient",
    }
    for nombre, valor in prohibidos.items():
        assert valor not in texto, f"el log contiene {nombre}"
    # Tampoco en la auditoría
    auditoria = json.dumps(_filas("SELECT row_to_json(a)::text FROM auditoria a WHERE actor_ref = %s OR "
                                  "accion = 'sesion.inicio_fallido'", cuenta), default=str)
    for nombre, valor in prohibidos.items():
        assert valor not in auditoria, f"la auditoría contiene {nombre}"


def test_contadores_en_memoria_respetan_la_ventana(reloj_fijo: Any) -> None:
    contadores = ContadoresEnMemoria()
    contadores.sumar_fallo("h", reloj_fijo.ahora())
    reloj_fijo.avanzar(timedelta(minutes=59))
    contadores.sumar_fallo("h", reloj_fijo.ahora())
    assert contadores.leer("h").fallos == 2
    reloj_fijo.avanzar(timedelta(minutes=2))
    contadores.sumar_fallo("h", reloj_fijo.ahora())
    assert contadores.leer("h").fallos == 1


def test_conservacion_con_ahora_futuro_falla_y_no_borra_nada(
    entorno_iam: EntornoIam, cuenta: uuid.UUID, email_sintetico: str, contrasena_sintetica: str
) -> None:
    from sqlalchemy.exc import DataError

    from tests.dobles.reloj_fijo import RelojFijo

    # El fixture reloj_fijo está en 2026-10-20: la sesión creada vence el 19-11
    _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    futuro = RelojFijo(datetime.now(UTC) + timedelta(days=400))
    with pytest.raises(DataError):
        conservar(unidad=UnidadIamSql(fabrica_scheduler(), futuro), reloj=futuro)
    assert _filas("SELECT count(*) FROM sesion_refresh WHERE usuario_id = %s", cuenta) == [(1,)]
    assert _filas("SELECT count(*) FROM dispositivo WHERE usuario_id = %s", cuenta) == [(1,)]
