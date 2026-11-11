"""MATU-44 · Retirar la autorización de la ficha y cortar los accesos de relevo, por la API y contra PostgreSQL.

Usa el entorno de MATU-19 (test_abrir_relevo_api): la familia comparte por su ruta y el relevo usa un
cliente https. El reloj parte de la hora real, porque las políticas del relevo usan now() de la base.
Solo datos sintéticos.
"""

import secrets
import threading
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest
from sqlalchemy import text

from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.modules.care_circle.application.retiro import SolicitudRetiro, retirar_autorizacion
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion
from app.modules.care_circle.infrastructure.efectos_retiro import efectos_de
from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL
from app.modules.care_plan.infrastructure.repositorio_accesos import RepositorioAccesosSQL
from app.shared.auditoria_sql import RegistroAuditoriaSql
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.care_plan import test_abrir_relevo_api as abrir
from tests.modules.care_plan.test_abrir_relevo_api import (
    PROBLEMA,
    RUTINA,
    EntornoAbrir,
    _cookie_borrada,
    _ejecutar,
    _problema,
    _todas,
    _una,
)
from tests.textos import aparece_celular

entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.rf("RF-02")]

RUTA = "/v1/personas-cuidadas/{}/consentimientos"
RETIRO = RUTA + "/{}/retiro"
RUTA_ACCESOS = "/v1/personas-cuidadas/{}/plan/accesos-relevo"
RUTA_FICHA = "/v1/personas-cuidadas/{}/plan/ficha"


def _cab(entorno: EntornoAbrir, usuario: UsuarioCreado | None, familia: FamiliaCreada) -> dict[str, str]:
    return entorno.ficha._cabeceras(usuario, familia.grupo.id)


def _retirar(entorno: EntornoAbrir, familia: FamiliaCreada, usuario: UsuarioCreado | None = None,
             finalidad: str = "plan_cuidado", persona: Any = None) -> Any:
    return entorno.ficha.iam.cliente.post(
        RETIRO.format(persona or familia.persona.id, finalidad),
        headers=_cab(entorno, usuario or familia.admin, familia),
    )


def _estado(entorno: EntornoAbrir, familia: FamiliaCreada, usuario: UsuarioCreado | None = None) -> Any:
    return entorno.ficha.iam.cliente.get(RUTA.format(familia.persona.id),
                                         headers=_cab(entorno, usuario or familia.admin, familia))


def _autorizar(entorno: EntornoAbrir, familia: FamiliaCreada, finalidad: str = "plan_cuidado") -> Any:
    return entorno.ficha.iam.cliente.post(
        RUTA.format(familia.persona.id), json={"finalidad": finalidad, "calidad_otorgante": "titular"},
        headers=_cab(entorno, familia.admin, familia),
    )


def _cuidador(familia: FamiliaCreada) -> UsuarioCreado:
    return familia.miembros["cuidador"].usuario


def _acceso(acceso_id: uuid.UUID) -> tuple[Any, Any, Any]:
    fila = _una("SELECT a.revocado_en, i.revocado_en, a.pin_intentos_fallidos FROM acceso_relevo a"
                " JOIN indice_token i ON i.referencia_id = a.id WHERE a.id = %s", acceso_id)
    assert fila is not None
    return fila[0], fila[1], fila[2]


def _consentimientos(familia: FamiliaCreada, finalidad: str = "plan_cuidado") -> list[tuple[Any, ...]]:
    return _todas("SELECT id, revocado_en, revocacion_motivo FROM consentimiento"
                  " WHERE persona_cuidada_id = %s AND finalidad = %s ORDER BY otorgado_en",
                  familia.persona.id, finalidad)


def _acciones(grupo: uuid.UUID, accion: str) -> list[tuple[Any, ...]]:
    return _todas("SELECT actor_tipo, actor_ref, entidad_id, request_id, detalle FROM auditoria"
                  " WHERE grupo_id = %s AND accion = %s ORDER BY id", grupo, accion)


# --- El retiro y el corte -------------------------------------------------------------------------------


def test_retiro_corta_vigentes_bloqueados_y_en_pausa_y_no_toca_vencidos_ni_cortados(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    vigente, _, _ = entorno.compartir(familia)
    bloqueado, _, _ = entorno.compartir(familia)
    vencido, _, _ = entorno.compartir(familia)
    cortado, _, _ = entorno.compartir(familia)
    _ejecutar("UPDATE acceso_relevo SET pin_intentos_fallidos = 5 WHERE id = %s", bloqueado)
    _ejecutar("UPDATE acceso_relevo SET creado_en = now() - interval '3 days', expira_en = now() - interval '1 day'"
              " WHERE id = %s", vencido)
    assert entorno.ficha.iam.cliente.delete(f"/v1/accesos-relevo/{cortado}",
                                            headers=_cab(entorno, familia.admin, familia)).status_code == 204
    primer_corte = _acceso(cortado)[0]
    entorno.reloj.avanzar(timedelta(minutes=1))
    ahora = entorno.reloj.ahora()

    respuesta = _retirar(entorno, familia, _cuidador(familia))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo = respuesta.json()
    assert cuerpo["enlaces_cortados"] == 2
    vista = cuerpo["autorizacion"]
    assert vista["finalidad"] == "plan_cuidado" and vista["estado"] == "retirada" and vista["borrada"] is False
    assert vista["id"] == str(familia.persona.consentimiento_id)
    assert vista["revocado_en"].startswith(ahora.strftime("%Y-%m-%dT%H:%M:%S"))
    assert vista["borrado_en"].startswith((ahora + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S"))
    for acceso in (vigente, bloqueado):
        revocado, indice, _ = _acceso(acceso)
        assert revocado == indice == ahora
    assert _acceso(vencido)[:2] == (None, None)
    assert _acceso(cortado)[0] == primer_corte
    # El retiro fija la fila vigente: nunca crea una fila de retiro
    assert _consentimientos(familia) == [(familia.persona.consentimiento_id, ahora, "retiro")]
    [revocar] = _acciones(familia.grupo.id, "consentimiento.revocar")
    assert revocar[:3] == ("usuario", _cuidador(familia).id, familia.persona.consentimiento_id)
    assert revocar[4] is None
    cortes = [f for f in _acciones(familia.grupo.id, "relevo.revocar") if f[2] in (vigente, bloqueado)]
    assert len(cortes) == 2 and {f[3] for f in cortes} == {revocar[3]} and revocar[3] is not None


def test_el_relevo_queda_cortado_para_siempre(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    assert entorno.abrir(token, pin).status_code == 200

    assert _retirar(entorno, familia).status_code == 200

    ficha = entorno.leer()
    _problema(ficha, 410, "relevo-revocado")
    _cookie_borrada(ficha)
    assert entorno.sesiones.guardadas == {}
    _problema(entorno.presentar(token), 410, "relevo-revocado")
    _problema(entorno.canjear(token, "0000" if pin != "0000" else "1111"), 410, "relevo-revocado")
    assert _acceso(acceso_id)[2] == 0  # el canje no contó como intento
    # Una autorización nueva no reabre el mismo enlace
    assert _autorizar(entorno, familia).status_code == 201
    _problema(entorno.presentar(token), 410, "relevo-revocado")
    _problema(entorno.canjear(token, pin), 410, "relevo-revocado")


def test_la_ficha_tras_el_retiro_403_y_la_lista_y_las_aperturas_200(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    entorno.compartir(familia)
    assert _retirar(entorno, familia).status_code == 200
    cliente, cab, persona = entorno.ficha.iam.cliente, _cab(entorno, familia.admin, familia), familia.persona.id

    respuestas = [
        cliente.get(RUTA_FICHA.format(persona), headers=cab),
        cliente.put(RUTA_FICHA.format(persona) + "/rutina", json={"texto": "x"}, headers={**cab, "If-Match": '"v1"'}),
        cliente.put(f"/v1/personas-cuidadas/{persona}/plan/secciones/preferencias", json={"texto": "x"},
                    headers={**cab, "If-None-Match": "*"}),
        cliente.delete(f"/v1/personas-cuidadas/{persona}/plan/secciones/preferencias",
                       headers={**cab, "If-Match": '"v1"'}),
        cliente.post(RUTA_ACCESOS.format(persona), json={
            "nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "otro", "relevo_informado": True,
        }, headers=cab),
    ]
    for respuesta in respuestas:
        assert respuesta.status_code == 403, respuesta.text
        assert respuesta.json()["type"] == "/errores/sin-consentimiento"
    lista = cliente.get(RUTA_ACCESOS.format(persona), headers=cab)
    assert lista.status_code == 200 and {i["estado"] for i in lista.json()["items"]} == {"revocado"}
    assert cliente.get(f"/v1/personas-cuidadas/{persona}/plan/aperturas", headers=cab).status_code == 200


def test_volver_a_autorizar_antes_de_90_dias_lo_escrito_vuelve(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    assert _retirar(entorno, familia).status_code == 200

    creada = _autorizar(entorno, familia)

    assert creada.status_code == 201, creada.text
    assert creada.json()["consentimiento"]["finalidad"] == "plan_cuidado"
    fila = _una("SELECT evidencia FROM consentimiento WHERE id = %s", creada.json()["consentimiento"]["id"])
    assert fila is not None and fila[0]["declaracion"]["id"] == "declaracion_titular"
    ficha = entorno.ficha.leer(familia.admin, familia.grupo.id, familia.persona.id)
    assert ficha.status_code == 200 and ficha.json()["campos"]["rutina"]["texto"] == RUTINA
    # Con una autorización vigente, otra responde 409
    otra = _autorizar(entorno, familia)
    assert otra.status_code == 409 and otra.json()["type"] == "/errores/autorizacion-vigente"


def test_ya_retirada_409_sin_otra_auditoria(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    assert _retirar(entorno, familia).status_code == 200
    segunda = _retirar(entorno, familia, _cuidador(familia))
    assert segunda.status_code == 409
    assert segunda.headers["content-type"] == PROBLEMA and segunda.headers["cache-control"] == "no-store"
    assert segunda.json()["type"] == "/errores/ya-retirada"
    assert len(_acciones(familia.grupo.id, "consentimiento.revocar")) == 1


def test_se_retira_con_la_revision_anual_vencida(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha(calidad="cuidador_de_hecho")
    _, token, _ = entorno.compartir(familia)
    # El consentimiento es inalterable: solo para la prueba, el superusuario apaga el trigger (rol de réplica)
    with psycopg.connect(DSN) as cx, cx.transaction():
        cx.execute("SET LOCAL session_replication_role = replica")
        cx.execute("UPDATE consentimiento SET revision_vence_en = now() - interval '1 day' WHERE id = %s",
                   (familia.persona.consentimiento_id,))
    _problema(entorno.presentar(token), 410, "relevo-pausado")

    respuesta = _retirar(entorno, familia)

    assert respuesta.status_code == 200 and respuesta.json()["enlaces_cortados"] == 1
    _problema(entorno.presentar(token), 410, "relevo-revocado")


# --- Quién -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("etiqueta", ["pagador", "pagador_con_plan", "observador"])
@pytest.mark.parametrize("finalidad", ["plan_cuidado", "consumo"])
def test_pagador_y_observador_no_retiran_ni_autorizan_404_y_nada_cambia(
    entorno: EntornoAbrir, etiqueta: str, finalidad: str
) -> None:
    """D1: retirar y volver a autorizar siguen siendo solo de admin y cuidador."""
    familia = entorno.familia_con_ficha()
    entorno.ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    acceso_id, _, _ = entorno.compartir(familia)
    usuario = familia.miembros[etiqueta].usuario
    autorizar = entorno.ficha.iam.cliente.post(
        RUTA.format(familia.persona.id), json={"finalidad": finalidad, "calidad_otorgante": "titular"},
        headers=_cab(entorno, usuario, familia),
    )
    for respuesta in (_retirar(entorno, familia, usuario, finalidad=finalidad), autorizar):
        assert respuesta.status_code == 404
        assert respuesta.json()["type"] == "/errores/no-encontrado"
        assert respuesta.headers["cache-control"] == "no-store"
    assert _acceso(acceso_id)[:2] == (None, None)
    assert _consentimientos(familia)[0][1] is None
    assert _consentimientos(familia, "consumo")[0][1] is None


CAMPOS_RESUMEN = {"finalidad", "estado", "id", "otorgado_en", "revision_vence_en", "revocado_en", "borrado_en",
                  "borrada"}


@pytest.mark.parametrize(("etiqueta", "con_calidad"), [
    ("admin", True), ("cuidador", True), ("pagador", False), ("pagador_con_plan", False), ("observador", False),
])
def test_el_estado_lo_ven_los_cuatro_roles_y_la_calidad_solo_admin_y_cuidador(
    entorno: EntornoAbrir, etiqueta: str, con_calidad: bool
) -> None:
    """P2 y C5: el pagador y el observador ven el estado y sus fechas, con otro esquema sin la calidad."""
    familia = entorno.familia_con_ficha()
    assert _retirar(entorno, familia).status_code == 200
    usuario = familia.admin if etiqueta == "admin" else familia.miembros[etiqueta].usuario

    respuesta = _estado(entorno, familia, usuario)

    assert respuesta.status_code == 200 and respuesta.headers["cache-control"] == "no-store"
    plan, consumo = respuesta.json()["autorizaciones"]
    campos = CAMPOS_RESUMEN | {"calidad_otorgante"} if con_calidad else CAMPOS_RESUMEN
    assert set(plan) == set(consumo) == campos
    assert (plan["finalidad"], plan["estado"], plan["borrada"]) == ("plan_cuidado", "retirada", False)
    assert plan["borrado_en"] is not None and consumo["estado"] == "sin_autorizar"
    assert "titular" not in respuesta.text or con_calidad


def test_el_estado_de_otro_grupo_o_sin_membresia_404(entorno: EntornoAbrir) -> None:
    a, b = entorno.familia_con_ficha(), entorno.familia_con_ficha()
    otra = entorno.ficha.iam.cliente.get(RUTA.format(b.persona.id), headers=_cab(entorno, a.admin, a))
    assert otra.status_code == 404 and otra.headers["cache-control"] == "no-store"
    sin_grupo = entorno.ficha.iam.cliente.get(RUTA.format(a.persona.id), headers=_cab(entorno, b.admin, a))
    assert sin_grupo.status_code == 404


def test_otro_grupo_finalidad_y_persona_invalidas_404(entorno: EntornoAbrir) -> None:
    a, b = entorno.familia_con_ficha(), entorno.familia_con_ficha()
    acceso_b, token_b, _ = entorno.compartir(b)
    for respuesta in (
        _retirar(entorno, a, persona=b.persona.id),
        _retirar(entorno, a, finalidad="despacho"),
        _retirar(entorno, a, persona="no-es-uuid"),
        _retirar(entorno, a, finalidad="consumo"),  # nunca se autorizó
        entorno.ficha.iam.cliente.post(RETIRO.format(a.persona.id, "plan_cuidado"), headers={}),
    ):
        assert respuesta.status_code in (401, 404), respuesta.text
    assert _acceso(acceso_b)[:2] == (None, None)
    assert entorno.presentar(token_b).status_code == 200


def test_otras_personas_y_otros_grupos_no_se_tocan(entorno: EntornoAbrir) -> None:
    a, b = entorno.familia_con_ficha(), entorno.familia_con_ficha()
    _, token_a, _ = entorno.compartir(a)
    _, token_b, pin_b = entorno.compartir(b)
    assert _retirar(entorno, a).status_code == 200
    _problema(entorno.presentar(token_a), 410, "relevo-revocado")
    assert entorno.abrir(token_b, pin_b).status_code == 200


def test_retirar_consumo_no_toca_la_ficha_ni_los_enlaces(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    entorno.ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    _, token, pin = entorno.compartir(familia)

    respuesta = _retirar(entorno, familia, finalidad="consumo")

    assert respuesta.status_code == 200 and respuesta.json()["enlaces_cortados"] == 0
    assert respuesta.json()["autorizacion"]["finalidad"] == "consumo"
    assert entorno.abrir(token, pin).status_code == 200
    assert entorno.ficha.leer(familia.admin, familia.grupo.id, familia.persona.id).status_code == 200


# --- Una sola transacción ---------------------------------------------------------------------------------


def test_si_falla_el_corte_de_un_acceso_todo_vuelve_atras(
    entorno: EntornoAbrir, monkeypatch: pytest.MonkeyPatch
) -> None:
    familia = entorno.familia_con_ficha()
    primero, _, _ = entorno.compartir(familia)
    segundo, token, pin = entorno.compartir(familia)
    original = RepositorioAccesosSQL.revocar
    llamadas: list[uuid.UUID] = []

    def revocar_y_fallar(self: RepositorioAccesosSQL, acceso_id: uuid.UUID, *args: Any) -> None:
        llamadas.append(acceso_id)
        if len(llamadas) == 2:
            raise RuntimeError("falla sintética del corte")
        original(self, acceso_id, *args)

    monkeypatch.setattr(RepositorioAccesosSQL, "revocar", revocar_y_fallar)

    respuesta = _retirar(entorno, familia)

    assert respuesta.status_code == 500
    assert len(llamadas) == 2
    assert _consentimientos(familia)[0][1:] == (None, None)
    assert _acceso(primero)[:2] == (None, None) and _acceso(segundo)[:2] == (None, None)
    assert _acciones(familia.grupo.id, "consentimiento.revocar") == []
    assert _acciones(familia.grupo.id, "relevo.revocar") == []
    monkeypatch.undo()
    assert entorno.abrir(token, pin).status_code == 200


# --- El estado de las autorizaciones ------------------------------------------------------------------------


def test_estado_de_las_dos_autorizaciones(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    antes = _estado(entorno, familia, _cuidador(familia))
    assert antes.status_code == 200 and antes.headers["cache-control"] == "no-store"
    plan, consumo = antes.json()["autorizaciones"]
    assert (plan["finalidad"], plan["estado"], plan["calidad_otorgante"]) == ("plan_cuidado", "vigente", "titular")
    assert (plan["revocado_en"], plan["borrado_en"], plan["borrada"]) == (None, None, False)
    assert consumo == {"finalidad": "consumo", "estado": "sin_autorizar", "id": None, "calidad_otorgante": None,
                       "otorgado_en": None, "revision_vence_en": None, "revocado_en": None, "borrado_en": None,
                       "borrada": False, "se_puede_otorgar": True}

    retiro = _retirar(entorno, familia).json()["autorizacion"]
    despues = _estado(entorno, familia).json()["autorizaciones"][0]
    assert despues == retiro and despues["estado"] == "retirada"
    # Sin la referencia, la evidencia, la versión de la política ni quién la dio
    assert set(despues) == {"finalidad", "estado", "id", "calidad_otorgante", "otorgado_en", "revision_vence_en",
                            "revocado_en", "borrado_en", "borrada", "se_puede_otorgar"}


# --- La carrera con compartir (condición 7) ------------------------------------------------------------------


def _fabrica(entorno: EntornoAbrir) -> Any:
    return (entorno.ficha.app.dependency_overrides.get(obtener_fabrica_sesiones) or obtener_fabrica_sesiones)()


def test_retiro_primero_compartir_espera_y_ve_la_autorizacion_retirada(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    fabrica, grupo, persona = _fabrica(entorno), familia.grupo.id, familia.persona.id
    visto: list[Any] = []

    def compartir() -> None:
        with sesion_tenant(fabrica, usuario_id=_cuidador(familia).id, grupo_id=grupo) as sesion:
            leida = persona_con_autorizacion(sesion, grupo, persona, bloquear=True)
            visto.append(None if leida is None else leida.autorizacion)

    with sesion_tenant(fabrica, usuario_id=familia.admin.id, grupo_id=grupo) as sesion:
        registro = RegistroAuditoriaSql(sesion, entorno.reloj)
        retirar_autorizacion(
            SolicitudRetiro(usuario_id=familia.admin.id, rol="admin", persona_id=persona, finalidad="plan_cuidado"),
            entorno.reloj, RepositorioRetirosSQL(sesion, grupo, registro), efectos_de(sesion, grupo, registro),
        )
        hilo = threading.Thread(target=compartir)
        hilo.start()
        hilo.join(timeout=0.5)
        assert hilo.is_alive()  # compartir espera el bloqueo del retiro
    hilo.join(timeout=10)
    assert visto == [None]  # sin autorización: la ruta responde 403


def test_compartir_primero_el_retiro_espera_y_corta_el_acceso_nuevo(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    fabrica, grupo, persona = _fabrica(entorno), familia.grupo.id, familia.persona.id
    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
    assert plan is not None
    acceso_id = uuid.uuid4()
    cortados: list[int] = []

    def retirar() -> None:
        with sesion_tenant(fabrica, usuario_id=familia.admin.id, grupo_id=grupo) as sesion:
            registro = RegistroAuditoriaSql(sesion, entorno.reloj)
            resultado = retirar_autorizacion(
                SolicitudRetiro(usuario_id=familia.admin.id, rol="admin", persona_id=persona, finalidad="plan_cuidado"),
                entorno.reloj, RepositorioRetirosSQL(sesion, grupo, registro), efectos_de(sesion, grupo, registro),
            )
            cortados.append(resultado.enlaces_cortados)

    with sesion_tenant(fabrica, usuario_id=_cuidador(familia).id, grupo_id=grupo) as sesion:
        leida = persona_con_autorizacion(sesion, grupo, persona, bloquear=True)
        assert leida is not None and leida.autorizacion is not None
        ahora = entorno.reloj.ahora()
        huella = secrets.token_bytes(32)
        sesion.execute(text(
            "INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,"
            " nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash,"
            " creado_en, expira_en, relevo_informado_en) VALUES (:id, :g, :plan, :u, 'Rosa', '+56955550137', 'P',"
            " 'C', ARRAY['rutina'], 'otro', :h, 'p', :ahora, :expira, :ahora)"),
            {"id": acceso_id, "g": grupo, "plan": plan[0], "u": _cuidador(familia).id, "h": huella, "ahora": ahora,
             "expira": ahora + timedelta(hours=24)})
        sesion.execute(text(
            "INSERT INTO indice_token (token_hash, tipo, grupo_id, referencia_id, expira_en, creado_en)"
            " VALUES (:h, 'relevo', :g, :id, :expira, :ahora)"),
            {"h": huella, "g": grupo, "id": acceso_id, "expira": ahora + timedelta(hours=24), "ahora": ahora})
        hilo = threading.Thread(target=retirar)
        hilo.start()
        hilo.join(timeout=0.5)
        assert hilo.is_alive()  # el retiro espera a que compartir confirme
    hilo.join(timeout=10)
    assert cortados == [1]
    revocado, indice, _ = _acceso(acceso_id)
    assert revocado is not None and revocado == indice



# La misma carrera por la ruta POST …/accesos-relevo, de punta a punta (P3 de la revisión de Martín)

CUERPO_ACCESO = {"nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "turno_de_noche",
                 "relevo_informado": True}


def _crear_acceso(entorno: EntornoAbrir, familia: FamiliaCreada) -> Any:
    return entorno.ficha.iam.cliente.post(RUTA_ACCESOS.format(familia.persona.id), json=CUERPO_ACCESO,
                                          headers=_cab(entorno, _cuidador(familia), familia))


def _accesos_del_grupo(grupo: uuid.UUID) -> list[tuple[Any, ...]]:
    return _todas("SELECT id FROM acceso_relevo WHERE grupo_id = %s", grupo)


@pytest.mark.rf("RF-02")
def test_crear_un_acceso_simultaneo_a_un_retiro_espera_y_termina_en_403(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    fabrica, grupo, persona = _fabrica(entorno), familia.grupo.id, familia.persona.id
    respuestas: list[Any] = []

    def crear() -> None:
        respuestas.append(_crear_acceso(entorno, familia))

    with sesion_tenant(fabrica, usuario_id=familia.admin.id, grupo_id=grupo) as sesion:
        registro = RegistroAuditoriaSql(sesion, entorno.reloj)
        retirar_autorizacion(
            SolicitudRetiro(usuario_id=familia.admin.id, rol="admin", persona_id=persona, finalidad="plan_cuidado"),
            entorno.reloj, RepositorioRetirosSQL(sesion, grupo, registro), efectos_de(sesion, grupo, registro),
        )
        hilo = threading.Thread(target=crear)
        hilo.start()
        hilo.join(timeout=1.0)
        assert hilo.is_alive()  # crear el acceso espera el bloqueo del retiro (FOR SHARE contra FOR UPDATE)
    hilo.join(timeout=15)
    [respuesta] = respuestas
    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["type"] == "/errores/sin-consentimiento"
    # Sin el acceso creado: ni la fila, ni su índice de token, ni la auditoría de compartir
    assert _accesos_del_grupo(grupo) == []
    assert _todas("SELECT 1 FROM indice_token WHERE grupo_id = %s AND tipo = 'relevo'", grupo) == []
    assert _acciones(grupo, "relevo.compartir") == []


@pytest.mark.rf("RF-02")
def test_crear_un_acceso_primero_el_retiro_espera_y_lo_corta(
    entorno: EntornoAbrir, monkeypatch: pytest.MonkeyPatch
) -> None:
    familia = entorno.familia_con_ficha()
    grupo = familia.grupo.id
    insertado, soltar = threading.Event(), threading.Event()
    original = RepositorioAccesosSQL.crear

    def crear_y_esperar(self: RepositorioAccesosSQL, acceso: Any) -> None:
        # El acceso queda escrito en la transacción de la petición, que sigue abierta con el FOR SHARE tomado
        original(self, acceso)
        insertado.set()
        assert soltar.wait(timeout=15)

    monkeypatch.setattr(RepositorioAccesosSQL, "crear", crear_y_esperar)
    creadas: list[Any] = []
    retiros: list[Any] = []
    crear = threading.Thread(target=lambda: creadas.append(_crear_acceso(entorno, familia)))
    retirar = threading.Thread(target=lambda: retiros.append(_retirar(entorno, familia)))

    crear.start()
    assert insertado.wait(timeout=15)
    retirar.start()
    retirar.join(timeout=1.0)
    assert retirar.is_alive()  # el retiro espera a que crear el acceso confirme (FOR UPDATE contra FOR SHARE)
    soltar.set()
    crear.join(timeout=15)
    retirar.join(timeout=15)

    [creada], [retiro] = creadas, retiros
    assert creada.status_code == 201, creada.text
    assert retiro.status_code == 200, retiro.text
    assert retiro.json()["enlaces_cortados"] == 1
    acceso_id = uuid.UUID(creada.json()["id"])
    assert _accesos_del_grupo(grupo) == [(acceso_id,)]
    revocado, indice, _ = _acceso(acceso_id)
    assert revocado is not None and revocado == indice
    [corte] = _acciones(grupo, "relevo.revocar")
    assert corte[2] == acceso_id

# --- Logs ----------------------------------------------------------------------------------------------------


def test_los_logs_no_llevan_nombres_telefonos_tokens_ni_texto(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    _, token, pin = entorno.compartir(familia)
    assert _retirar(entorno, familia).status_code == 200
    _retirar(entorno, familia)
    _estado(entorno, familia)
    entorno.presentar(token)
    log = entorno.ficha.iam.texto_log()
    for dato in (familia.persona.nombre, familia.persona.nombre_pila, "Rosa", token, RUTINA):
        assert dato not in log
    assert not aparece_celular("+56 9 5555 0137", log)


# --- La otra finalidad y un solo instante (cierre del analista) ------------------------------------------------


def test_retirar_la_ficha_no_toca_los_insumos(entorno: EntornoAbrir) -> None:
    """Contraparte de test_retirar_consumo_no_toca_la_ficha_ni_los_enlaces: perfiles, alertas y lectura intactos."""
    familia = entorno.familia_con_ficha()
    entorno.ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    perfil = entorno.ficha.fabrica.perfil_consumo(familia.persona)
    with psycopg.connect(DSN, autocommit=True) as cx:
        fila = cx.execute("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, current_date + 6)"
                          " RETURNING id", (perfil,)).fetchone()
    assert fila is not None
    alerta = fila[0]
    antes = _una("SELECT version, stock_unidades, activo FROM perfil_consumo WHERE id = %s", perfil)

    assert _retirar(entorno, familia).status_code == 200

    assert _una("SELECT version, stock_unidades, activo FROM perfil_consumo WHERE id = %s", perfil) == antes
    assert _una("SELECT estado, cerrada_en FROM alerta_quiebre WHERE id = %s", alerta) == ("pendiente", None)
    assert _consentimientos(familia, "consumo")[0][1:] == (None, None)
    assert _acciones(familia.grupo.id, "alerta.descartar") == []
    lectura = entorno.ficha.iam.cliente.get(f"/v1/personas-cuidadas/{familia.persona.id}/consumo",
                                            headers=_cab(entorno, familia.admin, familia))
    assert lectura.status_code == 200 and [p["id"] for p in lectura.json()["items"]] == [str(perfil)]


class _RelojQueAvanza:
    """Un reloj que avanza un milisegundo cada vez que se lee: si algo pide su propia hora, se nota."""

    def __init__(self, inicio: Any) -> None:
        self.actual = inicio
        self.lecturas = 0

    def ahora(self) -> Any:
        self.lecturas += 1
        self.actual += timedelta(milliseconds=1)
        return self.actual


def test_el_retiro_usa_un_solo_instante_en_todo(entorno: EntornoAbrir) -> None:
    """Decisión 124: revocado_en, el corte de cada acceso e indice_token y el ocurrido_en de toda la auditoría del
    retiro son el mismo instante, aunque el Reloj real avance entre una lectura y otra."""
    from app.modules.iam.api.dependencias import obtener_reloj

    familia = entorno.familia_con_ficha()
    primero, _, _ = entorno.compartir(familia)
    segundo, _, _ = entorno.compartir(familia)
    avanza = _RelojQueAvanza(entorno.reloj.ahora())
    app = entorno.ficha.app
    anterior = app.dependency_overrides[obtener_reloj]
    app.dependency_overrides[obtener_reloj] = lambda: avanza
    try:
        respuesta = _retirar(entorno, familia)
    finally:
        app.dependency_overrides[obtener_reloj] = anterior

    assert respuesta.status_code == 200, respuesta.text
    assert avanza.lecturas >= 2  # el reloj real sí avanzó durante la petición
    [(revocado,)] = _todas("SELECT revocado_en FROM consentimiento WHERE id = %s", familia.persona.consentimiento_id)
    instantes = {revocado}
    for acceso in (primero, segundo):
        instantes |= set(_acceso(acceso)[:2])
    instantes |= {f[0] for f in _todas(
        "SELECT ocurrido_en FROM auditoria WHERE grupo_id = %s"
        " AND accion IN ('consentimiento.revocar', 'relevo.revocar')"
        " AND ocurrido_en >= %s", familia.grupo.id, revocado - timedelta(seconds=1))}
    assert instantes == {revocado}
    assert len(_acciones(familia.grupo.id, "relevo.revocar")) == 2
