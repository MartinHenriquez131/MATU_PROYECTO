"""MATU-57 · Recuperar el acceso con un código al celular o al correo, y verificar el celular (RF-37).

Contra PostgreSQL real, como matu_app. Redis (códigos y contadores) y el envío van en memoria: el envío
simulado deja cada mensaje en EntornoIam.enviador.enviados, de donde la prueba lee el código.
"""

import re
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from app.modules.iam.api.router_recuperacion import obtener_pepper_recuperacion
from app.modules.iam.domain.refresh import NOMBRE_COOKIE
from tests.modules.iam.conftest import DSN, EntornoIam, requiere_base

pytestmark = [pytest.mark.rf("RF-37"), requiere_base]

CELULAR = "+56 9 1234 5637"
CELULAR_E164 = "+56912345637"
WEB = {"X-MATU-Cliente": "web"}
_CODIGO = re.compile(r"tu código es (\d{6})\.")


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _auditoria(usuario_id: uuid.UUID) -> list[tuple[str, Any, Any]]:
    return [
        (fila[0], fila[1], fila[2])
        for fila in _filas(
            "SELECT accion, detalle, grupo_id FROM auditoria WHERE (actor_ref = %s OR entidad_id = %s)"
            " AND accion LIKE 'cuenta.%%' ORDER BY id",
            usuario_id,
            usuario_id,
        )
    ]


def _cuenta(entorno: EntornoIam, email: str, contrasena: str) -> uuid.UUID:
    respuesta = entorno.registrar(nombre="Familiar Uno", email=email, contrasena=contrasena, telefono=CELULAR)
    assert respuesta.status_code == 201
    return uuid.UUID(respuesta.json()["id"])


def _entrar(entorno: EntornoIam, email: str, contrasena: str) -> Any:
    entorno.cliente.cookies.clear()
    return entorno.iniciar_sesion(email=email, contrasena=contrasena)


def _token(entorno: EntornoIam, email: str, contrasena: str) -> dict[str, str]:
    respuesta = _entrar(entorno, email, contrasena)
    assert respuesta.status_code == 200
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def _pedir(entorno: EntornoIam, email: str, canal: str | None = None) -> Any:
    cuerpo: dict[str, Any] = {"email": email}
    if canal is not None:
        cuerpo["canal"] = canal
    return entorno.cliente.post("/v1/recuperacion/codigo", json=cuerpo)


def _cambiar(entorno: EntornoIam, email: str, codigo: str, nueva: str) -> Any:
    return entorno.cliente.post(
        "/v1/recuperacion/contrasena", json={"email": email, "codigo": codigo, "contrasena_nueva": nueva}
    )


def _ultimo_codigo(entorno: EntornoIam) -> str:
    encontrado = _CODIGO.search(entorno.enviador.enviados[-1].mensaje)
    assert encontrado
    return encontrado.group(1)


def _otro(codigo: str) -> str:
    return f"{(int(codigo) + 1) % 1_000_000:06d}"


def _codigo_invalido(respuesta: Any) -> None:
    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/codigo-invalido"
    assert respuesta.headers["cache-control"] == "no-store"


def _verificar_celular(entorno: EntornoIam, cabeceras: dict[str, str]) -> None:
    assert entorno.cliente.post("/v1/cuenta/celular/codigo", headers=cabeceras).status_code == 202
    codigo = _ultimo_codigo(entorno)
    respuesta = entorno.cliente.post("/v1/cuenta/celular/verificar", json={"codigo": codigo}, headers=cabeceras)
    assert respuesta.status_code == 204
    entorno.reloj.avanzar(timedelta(seconds=61))


@pytest.fixture
def nueva() -> str:
    return f"nueva-{uuid.uuid4().hex[:12]}"


# --- No revela si la cuenta existe -----------------------------------------------------------------


def test_cuenta_inexistente_misma_respuesta_y_sin_envio(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    existe = _pedir(entorno_iam, email_sintetico)
    no_existe = _pedir(entorno_iam, f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl")

    assert existe.status_code == no_existe.status_code == 202
    assert existe.content == no_existe.content == b""
    assert set(existe.headers) - {"x-request-id"} == set(no_existe.headers) - {"x-request-id"}
    assert existe.headers["cache-control"] == "no-store"
    # Solo la cuenta existente recibe un código, y solo ella queda en la auditoría
    assert len(entorno_iam.enviador.enviados) == 1
    assert [a for a, _, _ in _auditoria(usuario)] == ["cuenta.recuperar_solicitar"]


def test_solo_recibe_el_email(entorno_iam: EntornoIam, email_sintetico: str) -> None:
    respuesta = entorno_iam.cliente.post(
        "/v1/recuperacion/codigo", json={"email": email_sintetico, "telefono": CELULAR}
    )
    assert respuesta.status_code == 422
    assert CELULAR not in respuesta.text


# --- Camino feliz: celular sin verificar → correo ---------------------------------------------------


def test_celular_no_verificado_va_al_correo_y_cambia_la_contrasena_revocando_todo(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, nueva: str
) -> None:
    usuario = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    # Dos sesiones abiertas, en dos dispositivos
    primera = _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    _entrar(entorno_iam, email_sintetico, contrasena_sintetica)
    refresh = primera.headers["set-cookie"].split(";")[0].split("=", 1)[1]

    assert _pedir(entorno_iam, email_sintetico).status_code == 202
    [envio] = entorno_iam.enviador.enviados
    assert (envio.canal.value, envio.destino) == ("correo", email_sintetico)
    codigo = _ultimo_codigo(entorno_iam)

    cambio = _cambiar(entorno_iam, email_sintetico, codigo, nueva)
    assert cambio.status_code == 204
    assert cambio.content == b""
    assert "set-cookie" not in cambio.headers  # no emite tokens

    # La contraseña anterior ya no sirve, la nueva sí
    assert _entrar(entorno_iam, email_sintetico, contrasena_sintetica).status_code == 401
    # Todas las sesiones anteriores quedaron revocadas con cambio_clave
    entorno_iam.cliente.cookies.clear()
    renovar = entorno_iam.cliente.post(
        "/v1/sesiones/renovar", headers={**WEB, "Cookie": f"{NOMBRE_COOKIE}={refresh}"}
    )
    assert renovar.status_code == 401
    assert _filas(
        "SELECT count(*) FROM sesion_refresh WHERE usuario_id = %s AND"
        " (revocado_en IS NULL OR motivo_revocacion <> 'cambio_clave') AND usado_en IS NULL",
        usuario,
    ) == [(0,)]
    assert _entrar(entorno_iam, email_sintetico, nueva).status_code == 200

    acciones = _auditoria(usuario)
    assert ("cuenta.contrasena_cambiar", {"sesiones_revocadas": 2}, None) in acciones
    # El aviso fue al correo (el celular no está verificado), sin el código
    aviso = entorno_iam.enviador.enviados[-1]
    assert aviso.canal.value == "correo" and "contraseña" in aviso.mensaje and codigo not in aviso.mensaje


def test_codigo_reutilizado(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, nueva: str
) -> None:
    _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    _pedir(entorno_iam, email_sintetico)
    codigo = _ultimo_codigo(entorno_iam)
    assert _cambiar(entorno_iam, email_sintetico, codigo, nueva).status_code == 204
    _codigo_invalido(_cambiar(entorno_iam, email_sintetico, codigo, nueva + "x"))


def test_codigo_vencido(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, nueva: str
) -> None:
    usuario = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    _pedir(entorno_iam, email_sintetico)
    codigo = _ultimo_codigo(entorno_iam)
    entorno_iam.reloj.avanzar(timedelta(minutes=10))
    _codigo_invalido(_cambiar(entorno_iam, email_sintetico, codigo, nueva))
    assert ("cuenta.recuperar_verificar_fallido", None, None) in _auditoria(usuario)


def test_intentos_agotados(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, nueva: str
) -> None:
    _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    _pedir(entorno_iam, email_sintetico)
    codigo = _ultimo_codigo(entorno_iam)
    for _ in range(5):
        _codigo_invalido(_cambiar(entorno_iam, email_sintetico, _otro(codigo), nueva))
    # El sexto intento, aunque sea el correcto, ya no sirve
    _codigo_invalido(_cambiar(entorno_iam, email_sintetico, codigo, nueva))


def test_demasiados_fallos_429_con_retry_after(
    entorno_iam: EntornoIam, email_sintetico: str, nueva: str
) -> None:
    for _ in range(6):
        _codigo_invalido(_cambiar(entorno_iam, email_sintetico, "000000", nueva))
    respuesta = _cambiar(entorno_iam, email_sintetico, "000000", nueva)
    assert respuesta.status_code == 429
    assert int(respuesta.headers["retry-after"]) >= 1


def test_cuenta_inexistente_mismo_error_al_cambiar(entorno_iam: EntornoIam, nueva: str) -> None:
    _codigo_invalido(_cambiar(entorno_iam, f"nadie.{uuid.uuid4().hex[:8]}@ejemplo.cl", "123456", nueva))


def test_pedir_otro_invalida_el_anterior(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, nueva: str
) -> None:
    _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    _pedir(entorno_iam, email_sintetico)
    primero = _ultimo_codigo(entorno_iam)
    entorno_iam.reloj.avanzar(timedelta(seconds=61))
    _pedir(entorno_iam, email_sintetico)
    segundo = _ultimo_codigo(entorno_iam)
    if primero != segundo:
        _codigo_invalido(_cambiar(entorno_iam, email_sintetico, primero, nueva))
    assert _cambiar(entorno_iam, email_sintetico, segundo, nueva).status_code == 204


def test_limite_de_envios_responde_igual_y_no_envia(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    # Antes de 60 s: 202 y sin envío
    assert _pedir(entorno_iam, email_sintetico).status_code == 202
    assert _pedir(entorno_iam, email_sintetico).status_code == 202
    assert len(entorno_iam.enviador.enviados) == 1
    # Tres por hora
    for _ in range(3):
        entorno_iam.reloj.avanzar(timedelta(seconds=61))
        assert _pedir(entorno_iam, email_sintetico).status_code == 202
    assert len(entorno_iam.enviador.enviados) == 3
    # Pasada la hora, vuelve a enviar
    entorno_iam.reloj.avanzar(timedelta(hours=1))
    assert _pedir(entorno_iam, email_sintetico).status_code == 202
    assert len(entorno_iam.enviador.enviados) == 4


def test_contrasena_nueva_corta_422_sin_repetir_valores(
    entorno_iam: EntornoIam, email_sintetico: str
) -> None:
    respuesta = _cambiar(entorno_iam, email_sintetico, "123456", "corta")
    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/validacion"
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["contrasena_nueva"]
    assert "corta" not in respuesta.text and email_sintetico not in respuesta.text


def test_sin_pepper_503(entorno_iam: EntornoIam, email_sintetico: str) -> None:
    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_pepper_recuperacion] = lambda: None  # type: ignore[attr-defined]
    assert _pedir(entorno_iam, email_sintetico).status_code == 503


# --- El celular ------------------------------------------------------------------------------------


def test_verificar_el_celular_y_recuperar_por_sms(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, nueva: str
) -> None:
    usuario = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    cabeceras = _token(entorno_iam, email_sintetico, contrasena_sintetica)

    cuenta = entorno_iam.cliente.get("/v1/cuenta", headers=cabeceras)
    assert cuenta.status_code == 200
    assert cuenta.json()["celular_enmascarado"] == "+56 9 •••• ••37"
    assert cuenta.json()["celular_verificado"] is False
    assert CELULAR_E164 not in cuenta.text

    assert entorno_iam.cliente.post("/v1/cuenta/celular/codigo", headers=cabeceras).status_code == 202
    envio = entorno_iam.enviador.enviados[-1]
    assert (envio.canal.value, envio.destino) == ("sms", CELULAR_E164)
    codigo = _ultimo_codigo(entorno_iam)
    # 60 s entre envíos: 429 con Retry-After
    otra = entorno_iam.cliente.post("/v1/cuenta/celular/codigo", headers=cabeceras)
    assert otra.status_code == 429 and otra.headers["retry-after"] == "60"
    _codigo_invalido(
        entorno_iam.cliente.post("/v1/cuenta/celular/verificar", json={"codigo": _otro(codigo)}, headers=cabeceras)
    )
    confirmado = entorno_iam.cliente.post(
        "/v1/cuenta/celular/verificar", json={"codigo": codigo}, headers=cabeceras
    )
    assert confirmado.status_code == 204
    assert entorno_iam.cliente.get("/v1/cuenta", headers=cabeceras).json()["celular_verificado"] is True
    ya = entorno_iam.cliente.post("/v1/cuenta/celular/codigo", headers=cabeceras)
    assert ya.status_code == 409 and ya.json()["type"] == "/errores/celular-verificado"

    # Con el número aún dentro de sus 60 s, el código va al correo
    _pedir(entorno_iam, email_sintetico)
    assert entorno_iam.enviador.enviados[-1].canal.value == "correo"
    # Con el celular verificado, la recuperación va al celular; con canal correo, al correo
    entorno_iam.reloj.avanzar(timedelta(seconds=61))
    _pedir(entorno_iam, email_sintetico)
    assert entorno_iam.enviador.enviados[-1].canal.value == "sms"
    entorno_iam.reloj.avanzar(timedelta(seconds=61))
    _pedir(entorno_iam, email_sintetico, canal="correo")
    assert entorno_iam.enviador.enviados[-1].destino == email_sintetico
    assert _cambiar(entorno_iam, email_sintetico, _ultimo_codigo(entorno_iam), nueva).status_code == 204
    # El código fue al correo: el aviso, al celular
    assert entorno_iam.enviador.enviados[-1].canal.value == "sms"

    acciones = [a for a, _, _ in _auditoria(usuario)]
    for accion in ("cuenta.celular_solicitar", "cuenta.celular_verificar_fallido", "cuenta.celular_verificar"):
        assert accion in acciones
    assert all(grupo is None for _, _, grupo in _auditoria(usuario))


def test_cambiar_el_numero_lo_deja_sin_verificar(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    cabeceras = _token(entorno_iam, email_sintetico, contrasena_sintetica)
    _verificar_celular(entorno_iam, cabeceras)
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE usuario SET telefono = '+56900000002' WHERE id = %s", (usuario,))
    assert entorno_iam.cliente.get("/v1/cuenta", headers=cabeceras).json()["celular_verificado"] is False


def test_rutas_de_la_cuenta_exigen_sesion(entorno_iam: EntornoIam) -> None:
    assert entorno_iam.cliente.get("/v1/cuenta").status_code == 401
    assert entorno_iam.cliente.post("/v1/cuenta/celular/codigo").status_code == 401


# --- Privacidad ------------------------------------------------------------------------------------


def test_ni_codigo_ni_celular_ni_email_en_logs_ni_auditoria(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str, nueva: str
) -> None:
    usuario = _cuenta(entorno_iam, email_sintetico, contrasena_sintetica)
    cabeceras = _token(entorno_iam, email_sintetico, contrasena_sintetica)
    _verificar_celular(entorno_iam, cabeceras)
    _pedir(entorno_iam, email_sintetico)
    codigo = _ultimo_codigo(entorno_iam)
    _cambiar(entorno_iam, email_sintetico, _otro(codigo), nueva)
    _cambiar(entorno_iam, email_sintetico, codigo, nueva)

    log = entorno_iam.texto_log()
    for secreto in (codigo, CELULAR_E164, email_sintetico, nueva):
        assert secreto not in log
    texto_auditoria = str(_filas("SELECT * FROM auditoria WHERE entidad_id = %s OR actor_ref = %s", usuario, usuario))
    for secreto in (codigo, CELULAR_E164, email_sintetico):
        assert secreto not in texto_auditoria
