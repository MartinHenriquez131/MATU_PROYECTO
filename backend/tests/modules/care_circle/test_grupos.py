"""MATU-06 · Crear el grupo familiar (backlog v1.3, RF-38).

Las pruebas con base corren como matu_app, con cuentas registradas e iniciadas por la API, y
revisan las filas como superusuario. Las de validación y autenticación no tocan la base: la
fábrica de sesiones se reemplaza por una que falla si alguien la usa.
"""

import uuid
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import fabrica_sesiones, obtener_fabrica_sesiones
from app.modules.care_circle.api.router import obtener_repositorio_grupos
from app.modules.care_circle.application.ports import NuevoGrupo
from app.modules.care_circle.infrastructure.repositorio_grupos import RepositorioGruposSQL
from app.modules.iam.domain.sesion import vencimiento
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from tests.base_datos import DSN, requiere_base
from tests.modules.care_circle.conftest import EntornoGrupo

PROBLEMA = "application/problem+json"
MENSAJE_NOMBRE = "Value error, el nombre del grupo debe tener entre 1 y 80 caracteres"


def _app(entorno: EntornoGrupo) -> FastAPI:
    return cast(FastAPI, entorno.iam.cliente.app)


def _sin_base(entorno: EntornoGrupo) -> None:
    """Reemplaza la fábrica de sesiones por una que falla si alguien abre una sesión."""

    def fabrica_que_falla() -> Session:
        raise AssertionError("esta petición no debía abrir una sesión")

    _app(entorno).dependency_overrides[obtener_fabrica_sesiones] = lambda: cast(
        sessionmaker[Session], fabrica_que_falla
    )


def _token_sintetico(entorno: EntornoGrupo) -> str:
    """Un token válido para un usuario cualquiera, sin pasar por la base."""
    ahora = entorno.iam.reloj.ahora()
    return EmisorJWT(entorno.iam.clave_jwt).emitir(uuid.uuid4(), ahora, vencimiento(ahora))


def _listar(entorno: EntornoGrupo, token: str | None) -> Any:
    return entorno.pedir("/v1/grupos", token)


def _fila_grupo(grupo_id: uuid.UUID) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute("SELECT nombre, creado_por, estado FROM grupo_familiar WHERE id = %s", (grupo_id,)).fetchone()


def _membresias(grupo_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute("SELECT usuario_id, rol, estado FROM membresia WHERE grupo_id = %s", (grupo_id,)).fetchall()


def _grupos_creados_por(usuario_id: uuid.UUID) -> int:
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT count(*) FROM grupo_familiar WHERE creado_por = %s", (usuario_id,)).fetchone()
        assert fila is not None
        return int(fila[0])


# --- Camino feliz --------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-38")
def test_crear_grupo_deja_admin(entorno_grupo: EntornoGrupo) -> None:
    # Dado un usuario con sesión
    a = entorno_grupo.cuenta()

    # Cuando crea un grupo
    respuesta = entorno_grupo.crear_grupo(a.token, {"nombre": "  Familia Sintética "})

    # Entonces responde 201 con el grupo y su rol de admin
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "nombre", "rol"}
    assert cuerpo["nombre"] == "Familia Sintética"
    assert cuerpo["rol"] == "admin"
    grupo_id = uuid.UUID(cuerpo["id"])

    # Y en la base quedan el grupo, creado por él, y su membresía admin activa
    assert _fila_grupo(grupo_id) == ("Familia Sintética", a.id, "activo")
    assert _membresias(grupo_id) == [(a.id, "admin", "activa")]

    # Y lo ve en su lista
    lista = _listar(entorno_grupo, a.token)
    assert lista.status_code == 200
    assert lista.json() == [{"id": str(grupo_id), "nombre": "Familia Sintética", "rol": "admin"}]


@requiere_base
@pytest.mark.rf("RF-38")
def test_creador_entra_a_su_grupo_y_otro_recibe_404(entorno_grupo: EntornoGrupo) -> None:
    # Dado un grupo recién creado por A
    a = entorno_grupo.cuenta()
    b = entorno_grupo.cuenta()
    grupo_id = entorno_grupo.crear_grupo(a.token, {"nombre": "Familia Sintética"}).json()["id"]

    # Cuando A y B piden una ruta del grupo con su X-Grupo-Id (sesion_de_grupo, MATU-02)
    propio = entorno_grupo.pedir("/prueba/grupo", a.token, grupo_id)
    ajeno = entorno_grupo.pedir("/prueba/grupo", b.token, grupo_id)

    # Entonces A entra con su contexto, y B recibe 404, nunca 403
    assert propio.status_code == 200
    assert propio.json()["app_grupo_id"] == grupo_id
    assert ajeno.status_code == 404
    assert ajeno.headers["content-type"].startswith(PROBLEMA)


# --- Aislamiento ---------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-38")
def test_no_ve_grupos_ajenos(entorno_grupo: EntornoGrupo) -> None:
    # Dados A y B, cada uno con su grupo, y C sin grupos
    a = entorno_grupo.cuenta()
    b = entorno_grupo.cuenta()
    c = entorno_grupo.cuenta()
    grupo_a = entorno_grupo.crear_grupo(a.token, {"nombre": "Familia Sintética A"}).json()["id"]
    grupo_b = entorno_grupo.crear_grupo(b.token, {"nombre": "Familia Sintética B"}).json()["id"]

    # Cuando cada uno lista sus grupos
    lista_a = _listar(entorno_grupo, a.token)
    lista_b = _listar(entorno_grupo, b.token)
    lista_c = _listar(entorno_grupo, c.token)

    # Entonces cada uno ve solo el suyo, y C una lista vacía
    assert lista_b.status_code == 200
    assert lista_b.json() == [{"id": grupo_b, "nombre": "Familia Sintética B", "rol": "admin"}]
    assert [g["id"] for g in lista_a.json()] == [grupo_a]
    assert lista_c.status_code == 200
    assert lista_c.json() == []
    assert "Familia Sintética A" not in lista_b.text
    assert "Familia Sintética A" not in lista_c.text


@requiere_base
@pytest.mark.rf("RF-38")
def test_fundador_retirado_no_ve_su_grupo(entorno_grupo: EntornoGrupo) -> None:
    # Dado un grupo creado por A, cuya membresía después queda retirada
    a = entorno_grupo.cuenta()
    grupo_id = uuid.UUID(entorno_grupo.crear_grupo(a.token, {"nombre": "Familia Sintética"}).json()["id"])
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE membresia SET estado = 'retirada' WHERE grupo_id = %s AND usuario_id = %s", (grupo_id, a.id))
    # (el grupo sigue creado por A: la política grupo_creador_ver se lo dejaría ver)
    fila = _fila_grupo(grupo_id)
    assert fila is not None
    assert fila[1] == a.id

    # Cuando lista sus grupos
    lista = _listar(entorno_grupo, a.token)

    # Entonces ya no aparece: la lista exige una membresía activa
    assert lista.status_code == 200
    assert lista.json() == []


# --- Atomicidad ----------------------------------------------------------------------------


class RepositorioConMembresiaInvalida(RepositorioGruposSQL):
    """Inserta el grupo de verdad y después una membresía que la base rechaza.

    El rol 'fundador' no existe: lo rechaza la política membresia_fundador (rol = 'admin'), que
    PostgreSQL evalúa antes del CHECK de rol. Cualquiera de los dos deja la transacción fallida.
    """

    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        super().__init__(fabrica)
        self.intentados: list[uuid.UUID] = []

    def _insertar_grupo(self, sesion: Session, grupo: NuevoGrupo) -> None:
        super()._insertar_grupo(sesion, grupo)
        self.intentados.append(grupo.id)

    def _insertar_membresia(self, sesion: Session, grupo: NuevoGrupo) -> None:
        sesion.execute(
            text("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (:g, :u, 'fundador')"),
            {"g": grupo.id, "u": grupo.creado_por},
        )


@requiere_base
@pytest.mark.rf("RF-38")
def test_si_falla_la_membresia_no_queda_grupo(entorno_grupo: EntornoGrupo) -> None:
    # Dado un repositorio cuya membresía falla después de insertar el grupo
    a = entorno_grupo.cuenta()
    repositorio = RepositorioConMembresiaInvalida(fabrica_sesiones())
    _app(entorno_grupo).dependency_overrides[obtener_repositorio_grupos] = lambda: repositorio

    # Cuando A crea un grupo
    respuesta = entorno_grupo.crear_grupo(a.token, {"nombre": "Familia Sintética"})

    # Entonces la petición falla sin exponer el error de la base
    assert respuesta.status_code == 500
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert "fundador" not in respuesta.text
    assert "Familia Sintética" not in entorno_grupo.iam.texto_log()
    # Y el INSERT del grupo sí corrió, pero no quedó: la transacción se deshizo entera
    assert len(repositorio.intentados) == 1
    assert _fila_grupo(repositorio.intentados[0]) is None
    assert _membresias(repositorio.intentados[0]) == []
    assert _grupos_creados_por(a.id) == 0


# --- Autenticación y validación ------------------------------------------------------------


@pytest.mark.rf("RF-38")
def test_sin_token_401(entorno_grupo: EntornoGrupo) -> None:
    _sin_base(entorno_grupo)

    crear = entorno_grupo.crear_grupo(None, {"nombre": "Familia Sintética"})
    listar = _listar(entorno_grupo, None)

    for respuesta in (crear, listar):
        assert respuesta.status_code == 401
        assert respuesta.headers["www-authenticate"] == "Bearer"


@pytest.mark.rf("RF-38")
@pytest.mark.parametrize("nombre", ["", "     ", "Z" * 81], ids=["vacio", "solo-espacios", "81-caracteres"])
def test_nombre_invalido_422_sin_el_valor(entorno_grupo: EntornoGrupo, nombre: str) -> None:
    _sin_base(entorno_grupo)

    respuesta = entorno_grupo.crear_grupo(_token_sintetico(entorno_grupo), {"nombre": nombre})

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert respuesta.json()["errores"] == [{"campo": "nombre", "mensaje": MENSAJE_NOMBRE, "tipo": "value_error"}]
    if nombre.strip():
        assert nombre not in respuesta.text
        assert nombre not in entorno_grupo.iam.texto_log()


@pytest.mark.rf("RF-38")
def test_campos_extra_422(entorno_grupo: EntornoGrupo) -> None:
    _sin_base(entorno_grupo)

    respuesta = entorno_grupo.crear_grupo(
        _token_sintetico(entorno_grupo), {"nombre": "Familia Sintética", "creado_por": str(uuid.uuid4())}
    )

    assert respuesta.status_code == 422
    assert [e["campo"] for e in respuesta.json()["errores"]] == ["creado_por"]


# --- Logs ----------------------------------------------------------------------------------


@requiere_base
@pytest.mark.rf("RF-38")
def test_nombre_del_grupo_no_aparece_en_los_logs(entorno_grupo: EntornoGrupo) -> None:
    a = entorno_grupo.cuenta()

    creada = entorno_grupo.crear_grupo(a.token, {"nombre": "Familia Soto"})
    lista = _listar(entorno_grupo, a.token)

    # El nombre sí está en las respuestas
    assert creada.status_code == 201
    assert "Familia Soto" in creada.text
    assert "Familia Soto" in lista.text
    # Y el log registra las peticiones con su ruta y su usuario, nunca el nombre ni el token
    log = entorno_grupo.iam.texto_log()
    assert "Soto" not in log
    assert a.token not in log
    peticiones = [linea for linea in entorno_grupo.iam.lineas_log() if linea["mensaje"] == "peticion"]
    assert [(p["metodo"], p["ruta"], p["usuario_id"]) for p in peticiones[-2:]] == [
        ("POST", "/v1/grupos", str(a.id)),
        ("GET", "/v1/grupos", str(a.id)),
    ]
