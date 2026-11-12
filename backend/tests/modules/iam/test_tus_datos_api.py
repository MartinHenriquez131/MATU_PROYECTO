"""MATU-54 · «Tus datos»: GET /v1/yo/datos, contra PostgreSQL (Ley 21.719, acceso y portabilidad; decisiones 345 y 358
a 360), y «Dónde entraste» con la copia de la cuenta (C-2 y C-3, decisión 376).

La API corre como matu_app con solo app.usuario_id. Los avisos que la prueba necesita los siembra el superusuario. Solo
datos sintéticos.
"""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from app.core.limite_ip import obtener_pepper_limites
from app.modules.iam.infrastructure import copia_cuenta
from app.shared.copia_datos import AVISO_COPIA
from tests.base_datos import DSN, requiere_base
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.conftest import EntornoIam

pytestmark = [requiere_base, pytest.mark.rf("RF-37"), pytest.mark.rf("Ley-21.719")]

RUTA = "/v1/yo/datos"
# Lo que nunca sale en «Tus datos» (sección 3 de la revisión previa, C4)
PROHIBIDOS = {
    "id", "usuario_id", "grupo_id", "persona_id", "request_id", "ip", "actor_ref", "entidad_id", "detalle",
    "password_hash", "contrasena", "mfa_secreto_cifrado", "email_hash", "token_hash", "push_token", "plataforma",
    "plantilla", "error", "evento_id", "token", "buy_order", "session_id", "actual",
}


@pytest.fixture
def fabrica_iam(entorno_iam: EntornoIam) -> Iterator[Fabrica]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    yield fabrica
    fabrica.limpiar()


def _claves(valor: Any) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _claves(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _claves(v)}
    return set()


def _token(entorno: EntornoIam, usuario: UsuarioCreado) -> str:
    assert usuario.contrasena is not None
    respuesta = entorno.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
    assert respuesta.status_code == 200, respuesta.text
    return str(respuesta.json()["access_token"])


def _pedir(entorno: EntornoIam, token: str | None, **cabeceras: str) -> Any:
    if token is not None:
        cabeceras["Authorization"] = f"Bearer {token}"
    return entorno.cliente.get(RUTA, headers=cabeceras)


def _familia(fabrica: Fabrica) -> FamiliaCreada:
    return fabrica.familia()


# --- Camino feliz -------------------------------------------------------------------------------------------------


def test_tus_datos_trae_la_cuenta_sus_grupos_y_sus_eventos_sin_nada_de_la_persona(
    entorno_iam: EntornoIam, fabrica_iam: Fabrica
) -> None:
    familia = _familia(fabrica_iam)
    admin = familia.admin
    # Una persona con un nombre que ninguna cuenta sintética tiene: los nombres de la fábrica pueden repetirse
    persona = fabrica_iam.persona_cuidada(familia.grupo, nombre="Zulema Copia Cincuentaicuatro", nombre_pila="Zulema")
    token = _token(entorno_iam, admin)

    # X-Grupo-Id se ignora
    respuesta = _pedir(entorno_iam, token, **{"X-Grupo-Id": str(familia.grupo.id)})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["content-disposition"] == 'inline; filename="matu-cuenta-2026-10-20.json"'
    cuerpo = respuesta.json()
    assert (cuerpo["formato"], cuerpo["tipo"], cuerpo["aviso"]) == ("matu-datos/1", "cuenta", AVISO_COPIA)
    assert cuerpo["cuenta"]["nombre"] == admin.nombre and cuerpo["cuenta"]["correo"] == admin.email
    [grupo] = cuerpo["grupos"]
    assert (grupo["nombre"], grupo["rol"], grupo["puede_ver_ficha"]) == (familia.grupo.nombre, "admin", None)
    assert cuerpo["grupos_que_dejaste"] == []
    assert len(cuerpo["dispositivos"]) == 1
    tipos = [e["tipo"] for e in cuerpo["eventos"]]
    assert tipos[0] == "pediste_una_copia" and "entraste" in tipos
    assert cuerpo["envio_simulado"] is True and cuerpo["avisos_enviados"] == []
    # Con la capa 3 registrada, los pagos van (vacíos)
    assert cuerpo["pagos"] == [] and cuerpo["condiciones_aceptadas"] == []
    # Nada de la persona cuidada (sección 3 de la revisión previa)
    assert persona.nombre not in respuesta.text and persona.nombre_pila not in respuesta.text
    assert not _claves(cuerpo) & PROHIBIDOS


def test_la_copia_de_la_cuenta_se_registra_sin_grupo_ni_detalle(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    usuario = fabrica_iam.usuario()
    token = _token(entorno_iam, usuario)

    assert _pedir(entorno_iam, token).status_code == 200

    with psycopg.connect(DSN) as cx:
        filas = cx.execute(
            "SELECT grupo_id, actor_tipo, entidad, entidad_id, persona_cuidada_id, detalle FROM auditoria"
            " WHERE accion = 'cuenta.datos_descargar' AND actor_ref = %s", (usuario.id,)).fetchall()
    assert filas == [(None, "usuario", "usuario", usuario.id, None, None)]


def test_los_avisos_simulados_no_salen_como_enviados(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    familia = _familia(fabrica_iam)
    with psycopg.connect(DSN) as cx:
        cx.execute(
            "INSERT INTO notificacion (usuario_id, grupo_id, evento_id, canal, plantilla, estado, enviada_en)"
            " VALUES (%s, %s, 990054, 'correo', 'quiebre_proximo', 'enviada', now()),"
            " (%s, %s, 990055, 'push', 'quiebre_proximo', 'omitida', NULL)",
            (familia.admin.id, familia.grupo.id, familia.admin.id, familia.grupo.id))

    respuesta = _pedir(entorno_iam, _token(entorno_iam, familia.admin))

    assert respuesta.status_code == 200, respuesta.text
    avisos = respuesta.json()["avisos_enviados"]
    assert sorted((a["canal"], a["resultado"]) for a in avisos) == [
        ("correo", "en_el_piloto_no_salio"), ("push", "no_salio")]
    # Ni la plantilla ni el destino
    assert "quiebre_proximo" not in respuesta.text


# --- Errores ------------------------------------------------------------------------------------------------------


def test_sin_sesion_401(entorno_iam: EntornoIam) -> None:
    respuesta = _pedir(entorno_iam, None)

    assert respuesta.status_code == 401
    assert respuesta.headers["cache-control"] == "no-store"


def test_la_copia_11_da_429(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    token = _token(entorno_iam, fabrica_iam.usuario())
    for _ in range(10):
        assert _pedir(entorno_iam, token).status_code == 200

    respuesta = _pedir(entorno_iam, token)

    assert respuesta.status_code == 429 and respuesta.json()["type"] == "/errores/tope-copias"
    assert respuesta.headers["cache-control"] == "no-store" and int(respuesta.headers["retry-after"]) >= 1


def test_sin_pepper_de_limites_503(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    token = _token(entorno_iam, fabrica_iam.usuario())
    overrides = entorno_iam.cliente.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[obtener_pepper_limites] = lambda: None
    try:
        respuesta = _pedir(entorno_iam, token)
    finally:
        overrides[obtener_pepper_limites] = lambda: entorno_iam.pepper_limites

    assert respuesta.status_code == 503 and respuesta.headers["cache-control"] == "no-store"


def test_sin_la_capa_3_los_pagos_van_en_null(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    token = _token(entorno_iam, fabrica_iam.usuario())
    fuente = copia_cuenta.bloque_cuenta(copia_cuenta.BLOQUE_PAGOS)
    assert fuente is not None
    copia_cuenta.quitar_bloque_cuenta(copia_cuenta.BLOQUE_PAGOS)
    try:
        respuesta = _pedir(entorno_iam, token)
    finally:
        copia_cuenta.registrar_bloque_cuenta(copia_cuenta.BLOQUE_PAGOS, fuente)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["pagos"] is None and respuesta.json()["condiciones_aceptadas"] is None


# --- «Dónde entraste» (C-2 y C-3) ---------------------------------------------------------------------------------


def test_donde_entraste_muestra_la_copia_de_la_cuenta_y_no_la_de_la_persona(
    entorno_iam: EntornoIam, fabrica_iam: Fabrica
) -> None:
    familia = _familia(fabrica_iam)
    token = _token(entorno_iam, familia.admin)
    assert _pedir(entorno_iam, token).status_code == 200
    with psycopg.connect(DSN) as cx:
        # Una copia de la persona, como la deja la otra ruta: con su grupo y su persona
        cx.execute(
            "INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, persona_cuidada_id)"
            " VALUES (%s, 'usuario', %s, 'persona.datos_descargar', 'persona_cuidada', %s, %s)",
            (familia.grupo.id, familia.admin.id, familia.persona.id, familia.persona.id))

    respuesta = entorno_iam.cliente.get("/v1/yo/ingresos", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200, respuesta.text
    eventos = respuesta.json()["eventos"]
    assert [e["tipo"] for e in eventos].count("pediste_una_copia") == 1
    assert next(e for e in eventos if e["tipo"] == "pediste_una_copia")["dispositivo"] is None


def test_los_logs_no_llevan_la_copia(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    usuario = fabrica_iam.usuario()

    assert _pedir(entorno_iam, _token(entorno_iam, usuario)).status_code == 200

    logs = entorno_iam.texto_log()
    assert usuario.email not in logs and usuario.nombre not in logs


@pytest.mark.rf("RF-38")
def test_un_grupo_del_que_saliste_va_sin_su_nombre(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    """F2 del cierre del analista (decisión 401): la membresía retirada, leída con membresia_propia: rol, unido_en y
    retirado_en, sin el nombre del grupo, que grupo_mis_grupos ya no deja leer."""
    familia = _familia(fabrica_iam)
    otro = fabrica_iam.grupo(nombre="Grupo Sintético Que Dejó 54")
    miembro = fabrica_iam.membresia(otro, familia.admin, "cuidador")
    with psycopg.connect(DSN) as cx:
        cx.execute("UPDATE membresia SET estado = 'retirada', retirado_en = now() WHERE id = %s", (miembro.id,))

    respuesta = _pedir(entorno_iam, _token(entorno_iam, familia.admin))

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert [g["nombre"] for g in cuerpo["grupos"]] == [familia.grupo.nombre]
    [dejado] = cuerpo["grupos_que_dejaste"]
    assert set(dejado) == {"rol", "unido_en", "retirado_en"} and dejado["rol"] == "cuidador"
    assert dejado["retirado_en"] is not None
    assert "Grupo Sintético Que Dejó 54" not in respuesta.text
