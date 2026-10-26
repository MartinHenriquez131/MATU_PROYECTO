"""MATU-30 · Las fábricas crean lo que dicen, respetan RLS al leer como matu_app y limpian todo.

Contra PostgreSQL real: siembran como superusuario (MATU_TEST_DSN) y las lecturas de aislamiento
corren con SET ROLE matu_app o por la API. Sin DATABASE_URL se saltan, como las demás pruebas de base.
"""

import io
import secrets
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.modules.care_circle.domain.avisos import AVISO_CUIDADOR_DE_HECHO
from app.modules.iam.api.dependencias import obtener_clave_jwt
from app.modules.iam.api.router import obtener_pepper_email
from app.modules.iam.domain.credenciales import indice_email
from tests.base_datos import DSN, requiere_base
from tests.fabricas import Fabrica
from tests.fabricas.datos import DOMINIO_CORREO

pytestmark = [requiere_base, pytest.mark.rf("MATU-30")]

OTORGADO_EN = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _contar(sql: str, *parametros: Any) -> int:
    fila = _una(sql, *parametros)
    assert fila is not None
    return int(fila[0])


def _como_matu_app(usuario_id: uuid.UUID, grupo_id: uuid.UUID, sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    """Ejecuta una consulta con SET ROLE matu_app y el contexto de tenant fijado, y la revierte."""
    with psycopg.connect(DSN) as cx:
        cx.execute("SET LOCAL ROLE matu_app")
        cx.execute("SELECT set_config('app.usuario_id', %s, true)", (str(usuario_id),))
        cx.execute("SELECT set_config('app.grupo_id', %s, true)", (str(grupo_id),))
        filas = cx.execute(sql, parametros).fetchall()
        cx.rollback()
        return filas


@pytest.fixture
def cliente_api() -> Iterator[tuple[TestClient, bytes]]:
    """La API con un pepper y una clave JWT sintéticos. Devuelve el cliente y el pepper."""
    pepper = secrets.token_bytes(32)
    clave_jwt = secrets.token_hex(32).encode()
    app = crear_app(stream_logs=io.StringIO())
    app.dependency_overrides[obtener_pepper_email] = lambda: pepper
    app.dependency_overrides[obtener_clave_jwt] = lambda: clave_jwt
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente, pepper


# --- Usuario --------------------------------------------------------------------------------------


def test_usuario_con_argon2id_e_indice_de_credencial(fabrica: Fabrica) -> None:
    carmen = fabrica.usuario(nombre="Carmen Fuentes")

    fila = _una("SELECT email, nombre, password_hash, estado FROM usuario WHERE id = %s", carmen.id)
    assert fila is not None
    email, nombre, password_hash, estado = fila
    assert (email, nombre, estado) == (carmen.email, "Carmen Fuentes", "activo")
    assert email.endswith(f"@{DOMINIO_CORREO}")
    assert password_hash.startswith("$argon2id$")
    assert carmen.contrasena is not None and carmen.contrasena not in password_hash
    indice = _una("SELECT email_hash FROM indice_credencial WHERE usuario_id = %s", carmen.id)
    assert indice is not None and bytes(indice[0]) == indice_email(fabrica.pepper, carmen.email)


def test_usuario_con_hash_entregado_no_conoce_la_contrasena(fabrica: Fabrica) -> None:
    cuenta = fabrica.usuario(password_hash="hash-sintetico", estado="bloqueado")

    assert cuenta.contrasena is None
    assert _una("SELECT password_hash, estado FROM usuario WHERE id = %s", cuenta.id) == ("hash-sintetico", "bloqueado")


def test_usuario_de_la_fabrica_inicia_sesion_en_la_api(cliente_api: tuple[TestClient, bytes]) -> None:
    cliente, pepper = cliente_api
    sembradora = Fabrica(pepper=pepper)
    try:
        cuenta = sembradora.usuario()
        respuesta = cliente.post("/v1/sesiones", json={"email": cuenta.email, "contrasena": cuenta.contrasena})
        assert respuesta.status_code == 200
        assert respuesta.json()["access_token"]
    finally:
        sembradora.limpiar()


# --- Grupo y membresías -----------------------------------------------------------------------------


def test_grupo_con_su_admin(fabrica: Fabrica) -> None:
    grupo = fabrica.grupo(nombre="Familia Fuentes")

    assert _una("SELECT nombre, creado_por FROM grupo_familiar WHERE id = %s", grupo.id) == (
        "Familia Fuentes",
        grupo.admin_id,
    )
    assert _una(
        "SELECT id, rol, estado, puede_ver_plan FROM membresia WHERE grupo_id = %s AND usuario_id = %s",
        grupo.id,
        grupo.admin_id,
    ) == (grupo.membresia_admin_id, "admin", "activa", False)


@pytest.mark.parametrize(
    ("rol", "puede_ver_plan"),
    [("admin", False), ("cuidador", False), ("pagador", True), ("pagador", False), ("observador", False)],
)
def test_membresia_con_cada_rol(fabrica: Fabrica, rol: str, puede_ver_plan: bool) -> None:
    grupo = fabrica.grupo()
    miembro = fabrica.miembro(grupo, rol, puede_ver_plan=puede_ver_plan)

    assert _una(
        "SELECT rol, puede_ver_plan, estado, invitado_por FROM membresia WHERE id = %s", miembro.membresia.id
    ) == (rol, puede_ver_plan, "activa", grupo.admin_id)
    assert miembro.membresia.usuario_id == miembro.usuario.id


def test_membresia_suspendida(fabrica: Fabrica) -> None:
    grupo = fabrica.grupo()
    miembro = fabrica.miembro(grupo, "cuidador")
    otra = fabrica.membresia(fabrica.grupo(), miembro.usuario, "observador", estado="suspendida")

    assert _una("SELECT estado FROM membresia WHERE id = %s", otra.id) == ("suspendida",)


@pytest.mark.parametrize("rol", ["admin", "cuidador", "observador"])
def test_puede_ver_plan_solo_con_pagador(fabrica: Fabrica, rol: str) -> None:
    grupo = fabrica.grupo()
    cuenta = fabrica.usuario()

    with pytest.raises(ValueError, match="pagador"):
        fabrica.membresia(grupo, cuenta, rol, puede_ver_plan=True)


# --- Persona cuidada con consentimiento ---------------------------------------------------------------


def test_persona_con_consentimiento_titular(fabrica: Fabrica) -> None:
    grupo = fabrica.grupo()
    persona = fabrica.persona_cuidada(grupo, nombre="Hernán Riquelme", otorgado_en=OTORGADO_EN)

    assert _una("SELECT nombre, nombre_pila, direccion_entrega_id FROM persona_cuidada WHERE id = %s", persona.id) == (
        "Hernán Riquelme",
        "Hernán",
        persona.direccion_id,
    )
    fila = _una(
        "SELECT usuario_id, calidad_otorgante, finalidad, referencia_documento, revision_vence_en, revocado_en,"
        " evidencia FROM consentimiento WHERE id = %s",
        persona.consentimiento_id,
    )
    assert fila is not None
    assert fila[:6] == (grupo.admin_id, "titular", "plan_cuidado", None, None, None)
    assert fila[6]["modalidad"] == "registrada_por_usuario_en_presencia_del_titular"
    assert "aviso" not in fila[6]


def test_persona_con_representante_legal_lleva_referencia(fabrica: Fabrica) -> None:
    grupo = fabrica.grupo()
    persona = fabrica.persona_cuidada(grupo, calidad="representante_legal")

    fila = _una(
        "SELECT calidad_otorgante, referencia_documento, revision_vence_en FROM consentimiento WHERE id = %s",
        persona.consentimiento_id,
    )
    assert fila == ("representante_legal", "Resolución sintética 123-2026", None)


def test_persona_con_cuidador_de_hecho_revisa_a_12_meses(fabrica: Fabrica) -> None:
    grupo = fabrica.grupo()
    cuidadora = fabrica.miembro(grupo, "cuidador")
    persona = fabrica.persona_cuidada(
        grupo, otorgante=cuidadora.usuario, calidad="cuidador_de_hecho", otorgado_en=OTORGADO_EN
    )

    fila = _una(
        "SELECT usuario_id, revision_vence_en, referencia_documento, evidencia FROM consentimiento WHERE id = %s",
        persona.consentimiento_id,
    )
    assert fila is not None
    assert fila[0] == cuidadora.usuario.id
    assert fila[1] == datetime(2027, 10, 20, 12, 0, tzinfo=UTC)
    assert fila[2] is None
    assert fila[3]["aviso"] == {
        "id": AVISO_CUIDADOR_DE_HECHO.id,
        "version": AVISO_CUIDADOR_DE_HECHO.version,
        "sha256": AVISO_CUIDADOR_DE_HECHO.sha256,
    }


def test_persona_sin_consentimiento_ni_direccion(fabrica: Fabrica) -> None:
    grupo = fabrica.grupo()
    persona = fabrica.persona_cuidada(grupo, con_consentimiento=False, con_direccion=False)

    assert persona.consentimiento_id is None and persona.direccion_id is None
    assert _contar("SELECT count(*) FROM consentimiento WHERE persona_cuidada_id = %s", persona.id) == 0


def test_persona_sin_grupo_creado_exige_otorgante(fabrica: Fabrica) -> None:
    grupo = fabrica.grupo()

    with pytest.raises(ValueError, match="otorgante"):
        fabrica.persona_cuidada(grupo.id)
    assert _contar("SELECT count(*) FROM persona_cuidada WHERE grupo_id = %s", grupo.id) == 0


# --- Ficha ------------------------------------------------------------------------------------------


def test_ficha_es_un_plan_ficha_relevo_sin_secciones(fabrica: Fabrica) -> None:
    persona = fabrica.persona_cuidada(fabrica.grupo())
    ficha = fabrica.ficha(persona)

    fila = _una(
        "SELECT grupo_id, persona_cuidada_id, modo, completitud_pct FROM plan_cuidado WHERE id = %s", ficha.plan_id
    )
    assert fila == (persona.grupo_id, persona.id, "ficha_relevo", 0)
    assert _contar("SELECT count(*) FROM plan_seccion WHERE plan_id = %s", ficha.plan_id) == 0


def test_familia_tiene_un_miembro_por_rol(fabrica: Fabrica) -> None:
    familia = fabrica.familia()

    filas = _como_matu_app(
        familia.admin.id,
        familia.grupo.id,
        "SELECT rol, puede_ver_plan FROM membresia WHERE grupo_id = %s",
        familia.grupo.id,
    )
    assert sorted(filas) == sorted(
        [("admin", False), ("cuidador", False), ("pagador", True), ("pagador", False), ("observador", False)]
    )
    assert familia.miembros["pagador_con_plan"].membresia.puede_ver_plan is True
    assert familia.ficha is not None


# --- Aislamiento ------------------------------------------------------------------------------------


def test_rls_un_usuario_de_la_familia_a_no_ve_a_la_persona_de_b(fabrica: Fabrica) -> None:
    a, b = fabrica.familia(), fabrica.familia()
    carmen = a.miembros["cuidador"].usuario

    personas = _como_matu_app(carmen.id, a.grupo.id, "SELECT id FROM persona_cuidada")
    assert personas == [(a.persona.id,)]
    assert _como_matu_app(carmen.id, a.grupo.id, "SELECT id FROM persona_cuidada WHERE id = %s", b.persona.id) == []
    assert b.ficha is not None
    assert _como_matu_app(carmen.id, a.grupo.id, "SELECT id FROM plan_cuidado WHERE id = %s", b.ficha.plan_id) == []
    assert _como_matu_app(carmen.id, a.grupo.id, "SELECT id FROM consentimiento WHERE grupo_id = %s", b.grupo.id) == []


def test_api_responde_404_a_la_familia_a_por_el_grupo_de_b(cliente_api: tuple[TestClient, bytes]) -> None:
    cliente, pepper = cliente_api
    sembradora = Fabrica(pepper=pepper)
    try:
        a, b = sembradora.familia(), sembradora.familia()
        cuenta = a.admin
        sesion = cliente.post("/v1/sesiones", json={"email": cuenta.email, "contrasena": cuenta.contrasena})
        assert sesion.status_code == 200
        cabeceras = {"Authorization": f"Bearer {sesion.json()['access_token']}"}

        propia = cliente.get(
            f"/v1/grupos/{a.grupo.id}/personas-cuidadas", headers={**cabeceras, "X-Grupo-Id": str(a.grupo.id)}
        )
        ajena = cliente.get(
            f"/v1/grupos/{b.grupo.id}/personas-cuidadas", headers={**cabeceras, "X-Grupo-Id": str(b.grupo.id)}
        )

        assert propia.status_code == 200
        assert [p["id"] for p in propia.json()] == [str(a.persona.id)]
        assert ajena.status_code == 404
    finally:
        sembradora.limpiar()


# --- Limpieza ---------------------------------------------------------------------------------------


def test_limpiar_no_deja_filas_ni_lo_que_la_prueba_escribio_en_el_grupo() -> None:
    sembradora = Fabrica()
    familia = sembradora.familia(calidad="cuidador_de_hecho")
    otra = sembradora.grupo(admin=familia.miembros["cuidador"].usuario)
    sembradora.membresia(otra, familia.miembros["observador"].usuario, "observador")
    # Lo que escribiría MATU-11 por la API y la fábrica no anotó
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
            " VALUES (%s, %s, '\\x01', 1)",
            (familia.grupo.id, familia.persona.id),
        )
    grupos = [familia.grupo.id, otra.id]
    usuarios = sembradora.ids("usuario")
    assert len(usuarios) == 5

    sembradora.limpiar()

    assert sembradora.creados == []
    assert _contar("SELECT count(*) FROM usuario WHERE id = ANY(%s::uuid[])", usuarios) == 0
    assert _contar("SELECT count(*) FROM indice_credencial WHERE usuario_id = ANY(%s::uuid[])", usuarios) == 0
    for tabla in ("membresia", "persona_cuidada", "consentimiento", "direccion", "plan_cuidado", "clave_datos"):
        assert _contar(f"SELECT count(*) FROM {tabla} WHERE grupo_id = ANY(%s::uuid[])", grupos) == 0, tabla
    assert _contar("SELECT count(*) FROM grupo_familiar WHERE id = ANY(%s::uuid[])", grupos) == 0
