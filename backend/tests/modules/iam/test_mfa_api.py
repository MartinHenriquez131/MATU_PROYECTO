"""MATU-81 · La entrada de operación en dos pasos contra PostgreSQL (C26 a C33).

POST /v1/sesiones con la contraseña de una cuenta de operación responde 401 mfa-requerido con un desafío y sin
tokens ni cookie; POST /v1/sesiones/mfa con el código entrega la sesión con la marca del segundo factor y 12 horas
de vida, sin ventana deslizante. Los tres fallos tienen su tipo, el quinto bloquea, un paso no se usa dos veces y sin
Redis o sin la KEK la entrada falla cerrada. Nada de esto queda en el log.
"""

import re
import uuid
from datetime import timedelta
from typing import Any

import jwt
import psycopg
import pytest

from app.modules.iam.api.router_mfa import obtener_cifrador_mfa
from app.modules.iam.domain.mfa import hotp, paso_de
from app.modules.iam.domain.refresh import NOMBRE_COOKIE
from tests.modules.iam.conftest import DSN, EntornoIam, requiere_base

pytestmark = [pytest.mark.rf("RF-37"), pytest.mark.rf("Ley-21.719"), requiere_base]

WEB = {"X-MATU-Cliente": "web"}


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _operacion(entorno: EntornoIam, email: str, contrasena: str) -> tuple[uuid.UUID, bytes]:
    r = entorno.registrar(nombre="Persona de Operación", email=email, contrasena=contrasena)
    assert r.status_code == 201, r.text
    usuario_id = uuid.UUID(r.json()["id"])
    return usuario_id, entorno.dar_alta_operacion(usuario_id)


def _desafio(entorno: EntornoIam, email: str, contrasena: str) -> Any:
    return entorno.iniciar_sesion(email=email, contrasena=contrasena)


def _mfa(entorno: EntornoIam, desafio: str, codigo: str, **cabeceras: str) -> Any:
    return entorno.cliente.post("/v1/sesiones/mfa", json={"desafio": desafio, "codigo": codigo}, headers=cabeceras)


def _otro_codigo(secreto: bytes, paso: int) -> str:
    validos = {hotp(secreto, paso + x) for x in (-1, 0, 1)}
    return next(c for c in (f"{n:06d}" for n in range(1000000)) if c not in validos)


def test_la_contrasena_de_operacion_pide_el_codigo_y_el_codigo_abre_12_horas(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario_id, secreto = _operacion(entorno_iam, email_sintetico, contrasena_sintetica)
    primero = _desafio(entorno_iam, email_sintetico, contrasena_sintetica)
    assert primero.status_code == 401, primero.text
    cuerpo = primero.json()
    assert cuerpo["type"] == "/errores/mfa-requerido"
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", cuerpo["desafio"]) and cuerpo["desafio_expira_en"]
    assert "access_token" not in cuerpo and "set-cookie" not in primero.headers
    assert primero.headers["cache-control"] == "no-store"
    assert _filas("SELECT count(*) FROM sesion_refresh WHERE usuario_id = %s", usuario_id) == [(0,)]

    r = _mfa(entorno_iam, cuerpo["desafio"], entorno_iam.codigo_mfa(usuario_id, secreto))
    assert r.status_code == 200, r.text
    sesion = r.json()
    assert sesion["tipo_cuenta"] == "operacion" and sesion["sesion_vence_en"]
    assert NOMBRE_COOKIE in r.headers["set-cookie"]
    claims = jwt.decode(sesion["access_token"], entorno_iam.clave_jwt, algorithms=["HS256"],
                        options={"verify_exp": False})
    assert claims["mfa"] == int(entorno_iam.reloj.ahora().timestamp())
    [(mfa_en, emitido, expira)] = _filas(
        "SELECT mfa_en, emitido_en, expira_en FROM sesion_refresh WHERE usuario_id = %s", usuario_id)
    assert mfa_en is not None and expira - emitido <= timedelta(hours=12)
    # El desafío sirve una vez
    assert _mfa(entorno_iam, cuerpo["desafio"], "000000").json()["type"] == "/errores/desafio-vencido"
    # Auditoría sin grupo: mfa_correcto e iniciar; el log, sin el desafío ni el código
    acciones = [a for (a,) in _filas("SELECT accion FROM auditoria WHERE actor_ref = %s ORDER BY id", usuario_id)]
    assert acciones[-2:] == ["sesion.mfa_correcto", "sesion.iniciar"]
    assert _filas("SELECT count(*) FROM auditoria WHERE actor_ref = %s AND grupo_id IS NOT NULL", usuario_id) == [(0,)]
    assert cuerpo["desafio"] not in entorno_iam.texto_log()


def test_la_renovacion_conserva_la_marca_y_no_pasa_de_12_horas(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario_id, secreto = _operacion(entorno_iam, email_sintetico, contrasena_sintetica)
    r = entorno_iam.entrar_operacion(email_sintetico, contrasena_sintetica, usuario_id, secreto)
    assert r.status_code == 200, r.text
    refresh = r.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    entorno_iam.reloj.avanzar(timedelta(hours=11, minutes=50))
    renovada = entorno_iam.cliente.post("/v1/sesiones/renovar", headers={**WEB, "Cookie": f"{NOMBRE_COOKIE}={refresh}"})
    assert renovada.status_code == 200, renovada.text
    # El access token no vive más allá de las 12 horas (C31): quedan 10 minutos
    assert renovada.json()["expira_en"] == 600 and renovada.json()["tipo_cuenta"] == "operacion"
    claims = jwt.decode(renovada.json()["access_token"], entorno_iam.clave_jwt, algorithms=["HS256"],
                        options={"verify_exp": False})
    assert "mfa" in claims
    refresh = renovada.headers["set-cookie"].split(";")[0].split("=", 1)[1]
    entorno_iam.reloj.avanzar(timedelta(minutes=11))
    vencida = entorno_iam.cliente.post("/v1/sesiones/renovar", headers={**WEB, "Cookie": f"{NOMBRE_COOKIE}={refresh}"})
    assert vencida.status_code == 401 and vencida.json()["type"] == "/errores/sesion-expirada"


def test_cinco_codigos_que_no_coinciden_bloquean_y_un_paso_no_se_usa_dos_veces(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario_id, secreto = _operacion(entorno_iam, email_sintetico, contrasena_sintetica)
    malo = _otro_codigo(secreto, paso_de(entorno_iam.reloj.ahora()))
    desafio = _desafio(entorno_iam, email_sintetico, contrasena_sintetica).json()["desafio"]
    for restantes in (4, 3, 2, 1):
        r = _mfa(entorno_iam, desafio, malo)
        assert r.status_code == 401 and r.json()["type"] == "/errores/codigo-mfa-incorrecto"
        assert r.json()["intentos_restantes"] == restantes
    r = _mfa(entorno_iam, desafio, malo)
    assert r.status_code == 429 and r.json()["type"] == "/errores/mfa-bloqueado"
    assert int(r.headers["retry-after"]) > 0 and r.json()["minutos_espera"] >= 1
    # Bloqueada, ni el código correcto abre, con un desafío nuevo
    desafio = _desafio(entorno_iam, email_sintetico, contrasena_sintetica).json()["desafio"]
    assert _mfa(entorno_iam, desafio, hotp(secreto, paso_de(entorno_iam.reloj.ahora()))).status_code == 429
    assert _filas("SELECT count(*) FROM auditoria WHERE actor_ref = %s AND accion = 'sesion.mfa_fallido'",
                  usuario_id) == [(5,)]
    # Pasada la ventana, entra; el mismo paso otra vez no
    entorno_iam.reloj.avanzar(timedelta(minutes=16))
    paso = paso_de(entorno_iam.reloj.ahora())
    desafio = _desafio(entorno_iam, email_sintetico, contrasena_sintetica).json()["desafio"]
    assert _mfa(entorno_iam, desafio, hotp(secreto, paso)).status_code == 200
    desafio = _desafio(entorno_iam, email_sintetico, contrasena_sintetica).json()["desafio"]
    r = _mfa(entorno_iam, desafio, hotp(secreto, paso))
    assert r.status_code == 401 and r.json()["type"] == "/errores/codigo-mfa-usado"
    assert _mfa(entorno_iam, desafio, hotp(secreto, paso + 1)).status_code == 200


def test_el_desafio_vence_a_los_5_minutos(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario_id, secreto = _operacion(entorno_iam, email_sintetico, contrasena_sintetica)
    desafio = _desafio(entorno_iam, email_sintetico, contrasena_sintetica).json()["desafio"]
    entorno_iam.reloj.avanzar(timedelta(minutes=5, seconds=1))
    r = _mfa(entorno_iam, desafio, entorno_iam.codigo_mfa(usuario_id, secreto))
    assert r.status_code == 401 and r.json()["type"] == "/errores/desafio-vencido"
    assert _mfa(entorno_iam, "x" * 43, "123456").json()["type"] == "/errores/desafio-vencido"
    assert _mfa(entorno_iam, "corto", "123456").status_code == 422
    assert _mfa(entorno_iam, desafio, "12a456").status_code == 422


def test_sin_redis_o_sin_la_kek_falla_cerrada(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    usuario_id, secreto = _operacion(entorno_iam, email_sintetico, contrasena_sintetica)
    desafio = _desafio(entorno_iam, email_sintetico, contrasena_sintetica).json()["desafio"]
    app = entorno_iam.cliente.app
    app.dependency_overrides[obtener_cifrador_mfa] = lambda: None  # type: ignore[attr-defined]
    assert _mfa(entorno_iam, desafio, entorno_iam.codigo_mfa(usuario_id, secreto)).status_code == 503
    assert entorno_iam.almacen_mfa is not None
    entorno_iam.almacen_mfa.caido = True
    assert _desafio(entorno_iam, email_sintetico, contrasena_sintetica).status_code == 503


def test_una_cuenta_de_familia_entra_como_siempre_y_no_usa_el_segundo_paso(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    r = entorno_iam.registrar(nombre="Familiar Uno", email=email_sintetico, contrasena=contrasena_sintetica)
    assert r.status_code == 201
    entrada = entorno_iam.iniciar_sesion(email=email_sintetico, contrasena=contrasena_sintetica)
    assert entrada.status_code == 200 and entrada.json()["sesion_vence_en"] is None
    claims = jwt.decode(entrada.json()["access_token"], entorno_iam.clave_jwt, algorithms=["HS256"],
                        options={"verify_exp": False})
    assert "mfa" not in claims


def test_la_base_no_deja_una_sesion_de_operacion_sin_la_marca(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    """C29 en la base: el trigger sesion_refresh_mfa, también para un superusuario."""
    usuario_id, _ = _operacion(entorno_iam, email_sintetico, contrasena_sintetica)
    with psycopg.connect(DSN) as cx:
        dispositivo = cx.execute("INSERT INTO dispositivo (usuario_id, plataforma) VALUES (%s, 'web') RETURNING id",
                                 (usuario_id,)).fetchone()
        assert dispositivo is not None
        with pytest.raises(psycopg.errors.CheckViolation):
            cx.execute(
                "INSERT INTO sesion_refresh (usuario_id, dispositivo_id, familia_id, token_hash, expira_en)"
                " VALUES (%s, %s, gen_random_uuid(), sha256(gen_random_uuid()::text::bytea), now() + interval '1 h')",
                (usuario_id, dispositivo[0]),
            )
        cx.rollback()
