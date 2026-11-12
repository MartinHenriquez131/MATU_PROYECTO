"""MATU-42 · Quiénes forman el grupo, cambiar roles, sacar y salir, por la API y contra PostgreSQL (RF-38).

Contrato: docs/api/propuestos/invitar-familiar.openapi.yaml. Los accesos de relevo se siembran como superusuario,
con el instante del Reloj de la prueba. Solo datos sintéticos.
"""

import secrets
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any, cast

import psycopg
import pytest
from fastapi import FastAPI

from app.modules.care_circle.api.dependencias_grupo import obtener_pepper_codigo
from tests.base_datos import DSN, requiere_base
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado

# reloj_fijo parte de la hora real (decisión 340)
from tests.modules.care_circle.test_invitaciones_api import URL, Entorno, reloj_fijo  # noqa: F401
from tests.modules.conftest import EntornoIam

pytestmark = [requiere_base, pytest.mark.rf("RF-38")]

CAMPOS_MIEMBRO = {"id", "nombre", "rol", "puede_ver_plan", "unido_en", "eres_tu", "etag", "enlaces_vigentes"}


class EntornoMiembros(Entorno):
    def miembros(self, usuario: UsuarioCreado, grupo: uuid.UUID) -> Any:
        return self.iam.cliente.get(f"/v1/grupos/{grupo}/miembros", headers=self.cabeceras(usuario, grupo))

    def por_rol(self, usuario: UsuarioCreado, grupo: uuid.UUID) -> dict[str, dict[str, Any]]:
        respuesta = self.miembros(usuario, grupo)
        assert respuesta.status_code == 200, respuesta.text
        return {m["rol"] if m["rol"] != "admin" or m["eres_tu"] else "otro_admin": m
                for m in respuesta.json()["miembros"]}

    def cambiar(self, usuario: UsuarioCreado, grupo: uuid.UUID, membresia: Any, cuerpo: Any,
                if_match: str | None = None) -> Any:
        cabeceras = self.cabeceras(usuario, grupo)
        if if_match is not None:
            cabeceras["If-Match"] = if_match
        return self.iam.cliente.patch(f"/v1/grupos/{grupo}/miembros/{membresia}", json=cuerpo, headers=cabeceras)

    def sacar(self, usuario: UsuarioCreado, grupo: uuid.UUID, membresia: Any) -> Any:
        return self.iam.cliente.delete(f"/v1/grupos/{grupo}/miembros/{membresia}",
                                       headers=self.cabeceras(usuario, grupo))

    def salir(self, usuario: UsuarioCreado, grupo: uuid.UUID) -> Any:
        return self.iam.cliente.post(f"/v1/grupos/{grupo}/salida", headers=self.cabeceras(usuario, grupo))

    def acceso(self, familia: FamiliaCreada, otorgado_por: uuid.UUID, *, vigente: bool = True) -> uuid.UUID:
        """Un acceso de relevo que esa persona compartió, con su indice_token, como lo deja POST accesos-relevo."""
        if familia.ficha is None:
            object.__setattr__(familia, "ficha", self.fabrica.ficha(familia.persona))
        assert familia.ficha is not None
        ahora = self.iam.reloj.ahora()
        expira = ahora + (timedelta(days=1) if vigente else timedelta(seconds=1))
        acceso_id, token = uuid.uuid4(), secrets.token_bytes(32)
        with psycopg.connect(DSN, autocommit=True) as cx:
            cx.execute(
                "INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre,"
                " otorgado_a_telefono, nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo,"
                " token_hash, pin_hash,"
                " creado_en, expira_en, relevo_informado_en) VALUES (%s, %s, %s, %s, 'Relevo', '+56 9 5555 0137',"
                " 'Persona', 'Quien', ARRAY['rutina'], 'turno_de_noche', sha256(%s), 'p', %s, %s, %s)",
                (acceso_id, familia.grupo.id, familia.ficha.plan_id, otorgado_por, token, ahora, expira, ahora))
            cx.execute(
                "INSERT INTO indice_token (token_hash, tipo, grupo_id, referencia_id, expira_en, creado_en)"
                " VALUES (sha256(%s), 'relevo', %s, %s, %s, %s)", (token, familia.grupo.id, acceso_id, expira, ahora))
        return acceso_id


@pytest.fixture
def entorno(entorno_iam: EntornoIam) -> Iterator[EntornoMiembros]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    pepper = secrets.token_bytes(32)
    cast(FastAPI, entorno_iam.cliente.app).dependency_overrides[obtener_pepper_codigo] = lambda: pepper
    try:
        yield EntornoMiembros(entorno_iam, fabrica)
    finally:
        fabrica.limpiar()


def _todas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _auditoria(membresia: Any) -> list[tuple[str, Any]]:
    return [(f[0], f[1]) for f in _todas("SELECT accion, detalle FROM auditoria WHERE entidad = 'membresia'"
                                         " AND entidad_id = %s ORDER BY id", uuid.UUID(str(membresia)))]


# --- La lista ------------------------------------------------------------------------------------------


def test_la_lista_no_trae_email_celular_ni_usuario_id(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    for usuario in (familia.admin, familia.miembros["observador"].usuario):
        respuesta = entorno.miembros(usuario, familia.grupo.id)
        assert respuesta.status_code == 200
        assert respuesta.headers["Cache-Control"] == "no-store"
        miembros = respuesta.json()["miembros"]
        assert len(miembros) == 4
        for miembro in miembros:
            # Falla si aparece cualquier otro campo, como email, celular o usuario_id (C9)
            assert set(miembro) == CAMPOS_MIEMBRO
        texto = respuesta.text
        for cuenta in [familia.admin, *(m.usuario for m in familia.miembros.values())]:
            assert cuenta.email not in texto and str(cuenta.id) not in texto
        assert "+56" not in texto


def test_enlaces_vigentes_para_quien_administra_y_en_la_propia_fila(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    cuidador = familia.miembros["cuidador"].usuario
    entorno.acceso(familia, cuidador.id)
    entorno.acceso(familia, cuidador.id)
    entorno.acceso(familia, cuidador.id, vigente=False)
    entorno.iam.reloj.avanzar(timedelta(seconds=2))
    vista_admin = entorno.por_rol(familia.admin, familia.grupo.id)
    assert vista_admin["cuidador"]["enlaces_vigentes"] == 2 and vista_admin["admin"]["enlaces_vigentes"] == 0
    assert vista_admin["pagador"]["puede_ver_plan"] is False and vista_admin["cuidador"]["puede_ver_plan"] is None
    vista_cuidador = entorno.por_rol(cuidador, familia.grupo.id)
    assert vista_cuidador["cuidador"]["eres_tu"] and vista_cuidador["cuidador"]["enlaces_vigentes"] == 2
    assert vista_cuidador["otro_admin"]["enlaces_vigentes"] is None


def test_otro_grupo_es_404(entorno: EntornoMiembros) -> None:
    a, b = entorno.familia(), entorno.familia()
    assert entorno.iam.cliente.get(f"/v1/grupos/{b.grupo.id}/miembros",
                                   headers=entorno.cabeceras(a.admin, a.grupo.id)).status_code == 404
    assert entorno.miembros(a.admin, b.grupo.id).status_code == 404
    otro = entorno.por_rol(b.admin, b.grupo.id)["cuidador"]
    assert entorno.cambiar(a.admin, a.grupo.id, otro["id"], {"rol": "observador"}, otro["etag"]).status_code == 404
    assert entorno.sacar(a.admin, a.grupo.id, otro["id"]).status_code == 404
    assert entorno.sacar(a.admin, a.grupo.id, "no-es-uuid").status_code == 404


# --- Cambiar el rol y el permiso -----------------------------------------------------------------------


def test_dar_al_pagador_el_permiso_de_ver_la_ficha(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    pagador = entorno.por_rol(familia.admin, familia.grupo.id)["pagador"]
    respuesta = entorno.cambiar(familia.admin, familia.grupo.id, pagador["id"], {"puede_ver_plan": True},
                                pagador["etag"])
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["miembro"]["puede_ver_plan"] is True and respuesta.json()["enlaces_cortados"] == 0
    assert respuesta.json()["miembro"]["etag"] == '"v2"' == respuesta.headers["ETag"]
    assert _auditoria(pagador["id"]) == [("membresia.permiso_ficha", {"rol": "pagador"})]
    # El pagador ya ve la ficha
    grupos = entorno.iam.cliente.get("/v1/grupos", headers=entorno.cabeceras(familia.miembros["pagador"].usuario))
    assert grupos.json()[0]["puede_ver_plan"] is True


def test_patch_428_422_412_y_sin_cambios(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    grupo = familia.grupo.id
    cuidador = entorno.por_rol(familia.admin, grupo)["cuidador"]
    for if_match in (None, "", "*"):
        respuesta = entorno.cambiar(familia.admin, grupo, cuidador["id"], {"rol": "pagador"}, if_match)
        assert respuesta.status_code == 428 and respuesta.json()["type"] == "/errores/falta-version"
    # 428 antes que el cuerpo inválido
    assert entorno.cambiar(familia.admin, grupo, cuidador["id"], {"rol": "jefe"}).status_code == 428
    for cuerpo in ({}, {"rol": None}, {"rol": "jefe"}, {"puede_ver_plan": None}, {"otro": 1}):
        assert entorno.cambiar(familia.admin, grupo, cuidador["id"], cuerpo, cuidador["etag"]).status_code == 422
    permiso = entorno.cambiar(familia.admin, grupo, cuidador["id"], {"puede_ver_plan": True}, cuidador["etag"])
    assert permiso.status_code == 422 and permiso.json()["errores"][0]["tipo"] == "permiso_solo_pagador"
    viejo = entorno.cambiar(familia.admin, grupo, cuidador["id"], {"rol": "admin"}, '"v9"')
    assert viejo.status_code == 412 and viejo.json()["type"] == "/errores/version-desactualizada"
    assert viejo.json()["actual"]["etag"] == cuidador["etag"] and viejo.headers["ETag"] == cuidador["etag"]
    igual = entorno.cambiar(familia.admin, grupo, cuidador["id"], {"rol": "cuidador"}, cuidador["etag"])
    assert igual.status_code == 200 and igual.json()["miembro"]["etag"] == cuidador["etag"]
    assert _auditoria(cuidador["id"]) == []


@pytest.mark.parametrize("etiqueta", ["cuidador", "pagador", "observador"])
def test_solo_admin_cambia_y_saca(entorno: EntornoMiembros, etiqueta: str) -> None:
    familia = entorno.familia()
    miembro = familia.miembros[etiqueta].usuario
    otro = entorno.por_rol(familia.admin, familia.grupo.id)["admin"]
    assert entorno.cambiar(miembro, familia.grupo.id, otro["id"], {"rol": "observador"}, otro["etag"]).status_code \
        == 404
    assert entorno.sacar(miembro, familia.grupo.id, otro["id"]).status_code == 404


def test_el_ultimo_admin_no_se_degrada(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    admin = entorno.por_rol(familia.admin, familia.grupo.id)["admin"]
    respuesta = entorno.cambiar(familia.admin, familia.grupo.id, admin["id"], {"rol": "cuidador"}, admin["etag"])
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/ultimo-admin"
    assert _todas("SELECT rol FROM membresia WHERE id = %s", uuid.UUID(admin["id"])) == [("admin",)]


def test_pasar_de_cuidador_a_observador_corta_sus_enlaces(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    grupo = familia.grupo.id
    cuidador = familia.miembros["cuidador"].usuario
    accesos = [entorno.acceso(familia, cuidador.id), entorno.acceso(familia, cuidador.id)]
    del_admin = entorno.acceso(familia, familia.admin.id)
    fila = entorno.por_rol(familia.admin, grupo)["cuidador"]
    respuesta = entorno.cambiar(familia.admin, grupo, fila["id"], {"rol": "observador"}, fila["etag"])
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["enlaces_cortados"] == 2
    assert respuesta.json()["miembro"]["rol"] == "observador" and respuesta.json()["miembro"]["enlaces_vigentes"] == 0
    cortados = _todas("SELECT a.id, a.revocado_en IS NOT NULL, t.revocado_en IS NOT NULL FROM acceso_relevo a"
                      " JOIN indice_token t ON t.referencia_id = a.id WHERE a.grupo_id = %s", grupo)
    assert {(a, x, y) for a, x, y in cortados} == {(accesos[0], True, True), (accesos[1], True, True),
                                                  (del_admin, False, False)}
    revocar = _todas("SELECT entidad_id FROM auditoria WHERE accion = 'relevo.revocar' AND grupo_id = %s", grupo)
    assert {r[0] for r in revocar} == set(accesos)
    assert _auditoria(fila["id"]) == [("membresia.cambiar_rol", {"rol": "observador"})]


def test_pasar_de_cuidador_a_admin_no_corta(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    cuidador = familia.miembros["cuidador"].usuario
    entorno.acceso(familia, cuidador.id)
    fila = entorno.por_rol(familia.admin, familia.grupo.id)["cuidador"]
    respuesta = entorno.cambiar(familia.admin, familia.grupo.id, fila["id"], {"rol": "admin"}, fila["etag"])
    assert respuesta.status_code == 200 and respuesta.json()["enlaces_cortados"] == 0


def test_quien_deja_de_administrar_pierde_sus_invitaciones(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    grupo = familia.grupo.id
    # El cuidador pasa a admin, invita y vuelve a cuidador
    fila = entorno.por_rol(familia.admin, grupo)["cuidador"]
    assert entorno.cambiar(familia.admin, grupo, fila["id"], {"rol": "admin"}, fila["etag"]).status_code == 200
    nuevo_admin = familia.miembros["cuidador"].usuario
    creada = entorno.crear(nuevo_admin, grupo)
    assert creada.status_code == 201
    token = URL.match(creada.json()["url"]).group(1)  # type: ignore[union-attr]
    fila = entorno.por_rol(familia.admin, grupo)["otro_admin"]
    assert entorno.cambiar(familia.admin, grupo, fila["id"], {"rol": "cuidador"}, fila["etag"]).status_code == 200
    assert entorno.presentar(token).json()["type"] == "/errores/invitacion-no-disponible"
    assert [f[0] for f in _todas("SELECT accion FROM auditoria WHERE entidad_id = %s ORDER BY id",
                                 uuid.UUID(creada.json()["id"]))] == ["invitacion.crear", "invitacion.anular"]


# --- Sacar y salir -------------------------------------------------------------------------------------


def test_sacar_a_alguien_corta_sus_enlaces_y_deja_de_ver_el_grupo(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    grupo = familia.grupo.id
    cuidador = familia.miembros["cuidador"].usuario
    acceso = entorno.acceso(familia, cuidador.id)
    fila = entorno.por_rol(familia.admin, grupo)["cuidador"]
    respuesta = entorno.sacar(familia.admin, grupo, fila["id"])
    assert respuesta.status_code == 200 and respuesta.json() == {"enlaces_cortados": 1}
    assert _todas("SELECT revocado_en IS NOT NULL FROM acceso_relevo WHERE id = %s", acceso) == [(True,)]
    assert _todas("SELECT estado, retirado_en IS NOT NULL FROM membresia WHERE id = %s", uuid.UUID(fila["id"])) == [
        ("retirada", True)]
    assert _auditoria(fila["id"]) == [("membresia.sacar", {"rol": "cuidador"})]
    # No es idempotente, y quien salió ya no ve el grupo ni aparece en la lista
    assert entorno.sacar(familia.admin, grupo, fila["id"]).status_code == 404
    assert entorno.miembros(cuidador, grupo).status_code == 404
    assert "cuidador" not in entorno.por_rol(familia.admin, grupo)


def test_salir_del_grupo(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    observador = familia.miembros["observador"].usuario
    respuesta = entorno.salir(observador, familia.grupo.id)
    assert respuesta.status_code == 200 and respuesta.json() == {"enlaces_cortados": 0}
    assert entorno.iam.cliente.get("/v1/grupos", headers=entorno.cabeceras(observador)).json() == []
    fila = familia.miembros["observador"].membresia.id
    assert _auditoria(fila) == [("membresia.salir", {"rol": "observador"})]


def test_el_unico_admin_no_sale_y_la_unica_persona_tampoco(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    respuesta = entorno.salir(familia.admin, familia.grupo.id)
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/ultimo-admin"
    # Sacarse a uno mismo es salir: el mismo 409
    propia = entorno.por_rol(familia.admin, familia.grupo.id)["admin"]
    assert entorno.sacar(familia.admin, familia.grupo.id, propia["id"]).json()["type"] == "/errores/ultimo-admin"
    cuenta = entorno.fabrica.usuario()
    grupo_solo = entorno.fabrica.grupo(admin=cuenta)
    respuesta = entorno.salir(cuenta, grupo_solo.id)
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/unica-persona"


def test_un_admin_sale_si_queda_otro_y_se_le_puede_volver_a_invitar(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    grupo = familia.grupo.id
    fila = entorno.por_rol(familia.admin, grupo)["cuidador"]
    assert entorno.cambiar(familia.admin, grupo, fila["id"], {"rol": "admin"}, fila["etag"]).status_code == 200
    salida = entorno.salir(familia.admin, grupo)
    assert salida.status_code == 200
    # El otro admin la vuelve a invitar: una fila nueva (índice único parcial, D-42-11 a)
    otro_admin = familia.miembros["cuidador"].usuario
    token, codigo, _ = entorno.invitar_como(otro_admin, grupo)  # type: ignore[attr-defined]
    assert entorno.aceptar(familia.admin, token, codigo).status_code == 201
    assert _todas("SELECT estado FROM membresia WHERE grupo_id = %s AND usuario_id = %s ORDER BY estado",
                  grupo, familia.admin.id) == [("activa",), ("retirada",)]


def _invitar_como(self: EntornoMiembros, usuario: UsuarioCreado, grupo: uuid.UUID) -> tuple[str, str, dict[str, Any]]:
    respuesta = self.crear(usuario, grupo)
    assert respuesta.status_code == 201, respuesta.text
    coincide = URL.match(respuesta.json()["url"])
    assert coincide
    return coincide.group(1), respuesta.json()["codigo"], respuesta.json()


EntornoMiembros.invitar_como = _invitar_como  # type: ignore[attr-defined]


# --- El autor que ya no está (decisión 309) y la autorización de quien salió (decisión 311) -----------


def test_el_autor_y_quien_autorizo_cuando_ya_no_estan(entorno: EntornoMiembros) -> None:
    familia = entorno.familia()
    grupo = familia.grupo.id
    # El admin autorizó (la fábrica) y comparte; otro admin queda y el primero sale
    fila = entorno.por_rol(familia.admin, grupo)["cuidador"]
    assert entorno.cambiar(familia.admin, grupo, fila["id"], {"rol": "admin"}, fila["etag"]).status_code == 200
    otro = familia.miembros["cuidador"].usuario
    estado = entorno.iam.cliente.get(f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
                                     headers=entorno.cabeceras(otro, grupo))
    assert estado.status_code == 200
    assert [a["autorizo_alguien_que_ya_no_esta"] for a in estado.json()["autorizaciones"]] == [False, False]
    assert entorno.salir(familia.admin, grupo).status_code == 200
    estado = entorno.iam.cliente.get(f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
                                     headers=entorno.cabeceras(otro, grupo))
    plan = next(a for a in estado.json()["autorizaciones"] if a["finalidad"] == "plan_cuidado")
    assert plan["estado"] == "vigente" and plan["autorizo_alguien_que_ya_no_esta"] is True
    assert str(familia.admin.id) not in estado.text
    # Quien observa no ve el campo (AutorizacionVistaResumen)
    resumen = entorno.iam.cliente.get(f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
                                      headers=entorno.cabeceras(familia.miembros["observador"].usuario, grupo))
    assert all("autorizo_alguien_que_ya_no_esta" not in a for a in resumen.json()["autorizaciones"])
