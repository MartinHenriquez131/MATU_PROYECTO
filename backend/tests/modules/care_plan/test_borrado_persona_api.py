"""MATU-72 · Borrar los datos de la persona al tiro, por la API y contra PostgreSQL (decisiones 149 a 157).

Usa el entorno de MATU-19 (test_abrir_relevo_api), como el retiro de MATU-44: la familia comparte por su ruta y el
relevo usa un cliente https. El reloj parte de la hora real, porque las políticas del relevo usan now() de la base.
Cada prueba lleva la condición del analista que verifica (C1 a C13). Solo datos sintéticos.
"""

import threading
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest
from sqlalchemy import text

from app.core.db import sesion_tenant
from app.modules.care_circle.application.borrado import SolicitudBorrado, borrar_persona
from app.modules.care_circle.application.retiro import SolicitudRetiro, retirar_autorizacion
from app.modules.care_circle.infrastructure.efectos_retiro import efectos_de
from app.modules.care_circle.infrastructure.repositorio_borrado import RepositorioBorradoSQL
from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL
from app.modules.care_plan.application import destruccion
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
from tests.modules.care_plan.test_retiro_autorizacion_api import _fabrica
from tests.textos import aparece_celular

entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.rf("RF-01")]

BORRADO = "/v1/personas-cuidadas/{}/borrado"
PERSONA = "/v1/personas-cuidadas/{}"
PREFERENCIAS = "Le gusta escuchar radio en la tarde"


def _cab(entorno: EntornoAbrir, usuario: UsuarioCreado | None, familia: FamiliaCreada) -> dict[str, str]:
    return entorno.ficha._cabeceras(usuario, familia.grupo.id)


def _cuidador(familia: FamiliaCreada) -> UsuarioCreado:
    return familia.miembros["cuidador"].usuario


def _borrar(entorno: EntornoAbrir, familia: FamiliaCreada, usuario: UsuarioCreado | None = None,
            persona: Any = None, cabeceras: dict[str, str] | None = None) -> Any:
    if cabeceras is None:
        cabeceras = _cab(entorno, usuario or familia.admin, familia)
    return entorno.ficha.iam.cliente.post(BORRADO.format(persona or familia.persona.id), headers=cabeceras)


def _completa(entorno: EntornoAbrir) -> FamiliaCreada:
    """Una familia con todo lo que el borrado toca: la ficha con una sección complementaria, la autorización de
    consumo, un insumo con una alerta y una compra."""
    familia = entorno.familia_con_ficha()
    seccion = entorno.ficha.iam.cliente.put(
        PERSONA.format(familia.persona.id) + "/plan/secciones/preferencias", json={"texto": PREFERENCIAS},
        headers={**_cab(entorno, familia.admin, familia), "If-None-Match": "*"})
    assert seccion.status_code == 201, seccion.text
    entorno.ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    perfil = entorno.ficha.fabrica.perfil_consumo(familia.persona)
    _ejecutar("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, current_date + 6)", perfil)
    _ejecutar("INSERT INTO reposicion (perfil_id, cantidad_unidades, origen, ocurrida_en) VALUES (%s, 5, 'declarada',"
              " current_date)", perfil)
    return familia


def _acciones(grupo: uuid.UUID, accion: str | None = None) -> list[tuple[Any, ...]]:
    filtro = "" if accion is None else " AND accion = %s"
    parametros: tuple[Any, ...] = (grupo,) if accion is None else (grupo, accion)
    return _todas("SELECT accion, actor_tipo, actor_ref, entidad, entidad_id, request_id, detalle, ocurrido_en, ip"
                  f" FROM auditoria WHERE grupo_id = %s{filtro} ORDER BY id", *parametros)


def _persona(familia: FamiliaCreada) -> tuple[Any, ...]:
    fila = _una("SELECT nombre, nombre_pila, nivel_apoyo, direccion_entrega_id, eliminado_en, datos_borrados_en, activa"
                " FROM persona_cuidada WHERE id = %s", familia.persona.id)
    assert fila is not None
    return fila


def _contar(sql: str, *parametros: Any) -> int:
    fila = _una(sql, *parametros)
    assert fila is not None
    return int(fila[0])


def _secciones(familia: FamiliaCreada) -> int:
    return _contar("SELECT count(*) FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
                   " WHERE p.persona_cuidada_id = %s", familia.persona.id)


def _perfiles(familia: FamiliaCreada) -> int:
    return _contar("SELECT count(*) FROM perfil_consumo WHERE persona_cuidada_id = %s", familia.persona.id)


def _clave(familia: FamiliaCreada) -> list[tuple[Any, ...]]:
    return _todas("SELECT id, dek_cifrada_con_kek IS NULL, destruida_en FROM clave_datos"
                  " WHERE persona_cuidada_id = %s", familia.persona.id)


def _consentimientos(familia: FamiliaCreada) -> list[tuple[Any, ...]]:
    return _todas("SELECT id, finalidad, revocado_en, revocacion_motivo FROM consentimiento"
                  " WHERE persona_cuidada_id = %s ORDER BY finalidad", familia.persona.id)


def _acceso(acceso_id: uuid.UUID) -> tuple[Any, ...]:
    fila = _una("SELECT a.revocado_en, i.revocado_en, a.nombre_pila_persona FROM acceso_relevo a"
                " JOIN indice_token i ON i.referencia_id = a.id WHERE a.id = %s", acceso_id)
    assert fila is not None
    return fila


def _sin_cambios(familia: FamiliaCreada, nombre_antes: tuple[Any, ...]) -> None:
    assert _persona(familia) == nombre_antes
    assert all(c[2] is None for c in _consentimientos(familia))
    assert _secciones(familia) == 4 and _perfiles(familia) == 1
    assert [k[1:] for k in _clave(familia)] == [(False, None)]


# --- Camino feliz (C1, C4, C6, C9, D2, D4, D5) --------------------------------------------------------------


def test_borrar_borra_todo_al_tiro_en_una_transaccion_y_un_instante(entorno: EntornoAbrir) -> None:
    familia = _completa(entorno)
    vigente, _, _ = entorno.compartir(familia)
    bloqueado, _, _ = entorno.compartir(familia)
    vencido, _, _ = entorno.compartir(familia)
    _ejecutar("UPDATE acceso_relevo SET pin_intentos_fallidos = 5 WHERE id = %s", bloqueado)
    _ejecutar("UPDATE acceso_relevo SET creado_en = now() - interval '3 days', expira_en = now() - interval '1 day'"
              " WHERE id = %s", vencido)
    direccion = familia.persona.direccion_id
    [(clave_id, _, _)] = _clave(familia)
    # La alerta y la compra anotada (`reposicion`) del insumo, por su perfil: la cascada de perfil_consumo las
    # borra (MATU-66, condición 2)
    perfiles = [f[0] for f in _todas("SELECT id FROM perfil_consumo WHERE persona_cuidada_id = %s", familia.persona.id)]
    hijas = ("SELECT (SELECT count(*) FROM alerta_quiebre WHERE perfil_id = ANY(%s::uuid[])),"
             " (SELECT count(*) FROM reposicion WHERE perfil_id = ANY(%s::uuid[]))")
    assert len(perfiles) == 1 and _una(hijas, perfiles, perfiles) == (1, 1)
    entorno.reloj.avanzar(timedelta(minutes=1))
    ahora = entorno.reloj.ahora()

    respuesta = _borrar(entorno, familia, _cuidador(familia))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"persona_id", "borrado_en", "enlaces_cortados", "autorizaciones_retiradas"}
    assert cuerpo["persona_id"] == str(familia.persona.id)
    assert cuerpo["borrado_en"].startswith(ahora.strftime("%Y-%m-%dT%H:%M:%S"))
    assert (cuerpo["enlaces_cortados"], cuerpo["autorizaciones_retiradas"]) == (2, 2)
    # D2: las dos autorizaciones, con motivo borrado y el mismo instante
    assert [(c[1], c[2], c[3]) for c in _consentimientos(familia)] == [
        ("consumo", ahora, "borrado"), ("plan_cuidado", ahora, "borrado")]
    # C9: vigentes y bloqueados cortados; el vencido no. Todos sin el nombre de pila de la persona (D5)
    for acceso in (vigente, bloqueado):
        assert _acceso(acceso) == (ahora, ahora, "borrada")
    assert _acceso(vencido) == (None, None, "borrada")
    # C6: la clave destruida y ninguna fila de la ficha; el plan se conserva en 0 de 3
    assert _clave(familia) == [(clave_id, True, ahora)]
    assert _secciones(familia) == 0
    assert _una("SELECT completitud_pct FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == (0,)
    # El consumo: perfiles, alertas y compras
    assert _perfiles(familia) == 0
    assert _una(hijas, perfiles, perfiles) == (0, 0)
    # D5: la persona sale de MATU, la fila queda sin datos y su dirección se borra
    assert _persona(familia) == ("borrada", "borrada", None, None, ahora, ahora, False)
    assert _una("SELECT 1 FROM direccion WHERE id = %s", direccion) is None
    # C4: la auditoría, sin contenido, con el mismo request_id e instante
    filas = _acciones(familia.grupo.id)
    del_borrado = [f for f in filas if f[7] == ahora]
    assert sorted(f[0] for f in del_borrado) == sorted(
        ["consentimiento.revocar"] * 2 + ["relevo.revocar"] * 2 + ["clave.destruir", "persona.borrar"])
    assert {f[1] for f in del_borrado} == {"usuario"} and {f[2] for f in del_borrado} == {_cuidador(familia).id}
    assert len({f[5] for f in del_borrado}) == 1 and del_borrado[0][5] is not None
    assert {f[6] for f in del_borrado} == {None} and {f[8] for f in del_borrado} == {None}
    [persona_borrar] = [f for f in del_borrado if f[0] == "persona.borrar"]
    assert (persona_borrar[3], persona_borrar[4]) == ("persona_cuidada", familia.persona.id)
    [destruir] = [f for f in del_borrado if f[0] == "clave.destruir"]
    assert (destruir[3], destruir[4]) == ("clave_datos", clave_id)
    assert {f[4] for f in del_borrado if f[0] == "relevo.revocar"} == {vigente, bloqueado}


def test_despues_del_borrado_la_persona_sale_de_matu(entorno: EntornoAbrir) -> None:
    """Decisión 153: fuera de la lista y 404 en todas sus rutas; borrar de nuevo, 409."""
    familia = _completa(entorno)
    assert _borrar(entorno, familia).status_code == 200
    cliente, cab, persona = entorno.ficha.iam.cliente, _cab(entorno, familia.admin, familia), familia.persona.id

    lista = cliente.get(f"/v1/grupos/{familia.grupo.id}/personas-cuidadas", headers=cab)
    assert lista.status_code == 200 and str(persona) not in lista.text
    respuestas = [
        cliente.get(PERSONA.format(persona) + "/plan/ficha", headers=cab),
        cliente.put(PERSONA.format(persona) + "/plan/ficha/rutina", json={"texto": "x"},
                    headers={**cab, "If-Match": '"v1"'}),
        cliente.put(PERSONA.format(persona) + "/plan/secciones/movilidad", json={"texto": "x"},
                    headers={**cab, "If-None-Match": "*"}),
        cliente.get(PERSONA.format(persona) + "/plan/accesos-relevo", headers=cab),
        cliente.post(PERSONA.format(persona) + "/plan/accesos-relevo", json={
            "nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "otro",
            "relevo_informado": True}, headers=cab),
        cliente.get(PERSONA.format(persona) + "/plan/aperturas", headers=cab),
        cliente.get(PERSONA.format(persona) + "/consentimientos", headers=cab),
        cliente.post(PERSONA.format(persona) + "/consentimientos",
                     json={"finalidad": "plan_cuidado", "calidad_otorgante": "titular"}, headers=cab),
        cliente.post(PERSONA.format(persona) + "/consentimientos/consumo/retiro", headers=cab),
        cliente.get(PERSONA.format(persona) + "/consumo", headers=cab),
        cliente.post(PERSONA.format(persona) + "/consumo", json={
            "nombre_libre": "Pañal adulto M", "tasa_unidades": 4, "stock_unidades": 24}, headers=cab),
        cliente.get(PERSONA.format(persona) + "/consumo/lista", headers=cab),
        cliente.get(PERSONA.format(persona) + "/consumo/alertas", headers=cab),
    ]
    for respuesta in respuestas:
        assert respuesta.status_code == 404, (respuesta.request.method, respuesta.request.url, respuesta.text)
        assert respuesta.headers["cache-control"] == "no-store"
    # Nada nuevo se escribió para ella
    assert _contar("SELECT count(*) FROM consentimiento WHERE persona_cuidada_id = %s AND revocado_en IS NULL",
                   persona) == 0


def test_borrar_dos_veces_409_sin_otra_auditoria(entorno: EntornoAbrir) -> None:
    """C3: 409 ya-borrada antes del 404 de eliminado_en, sin escribir nada."""
    familia = entorno.familia_con_ficha()
    assert _borrar(entorno, familia).status_code == 200
    antes = _acciones(familia.grupo.id)

    segunda = _borrar(entorno, familia, _cuidador(familia))

    assert segunda.status_code == 409, segunda.text
    assert segunda.headers["content-type"] == PROBLEMA and segunda.headers["cache-control"] == "no-store"
    assert segunda.json()["type"] == "/errores/ya-borrada"
    assert _acciones(familia.grupo.id) == antes


@pytest.mark.rf("RF-07")
def test_el_relevo_queda_cortado_para_siempre_tambien_con_la_sesion_abierta(entorno: EntornoAbrir) -> None:
    """C9: la sesión de relevo abierta recibe 410 en su siguiente petición y la cookie se borra."""
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    assert entorno.abrir(token, pin).status_code == 200

    assert _borrar(entorno, familia).status_code == 200

    ficha = entorno.leer()
    _problema(ficha, 410, "relevo-revocado")
    _cookie_borrada(ficha)
    assert entorno.sesiones.guardadas == {}
    _problema(entorno.presentar(token), 410, "relevo-revocado")
    _problema(entorno.canjear(token, "0000" if pin != "0000" else "1111"), 410, "relevo-revocado")
    _problema(entorno.canjear(token, pin), 410, "relevo-revocado")
    assert _una("SELECT pin_intentos_fallidos FROM acceso_relevo WHERE id = %s", acceso_id) == (0,)


def test_una_autorizacion_ya_retirada_conserva_su_motivo(entorno: EntornoAbrir) -> None:
    """D2: solo se retiran las vigentes; la retirada antes sigue con retiro y su fecha."""
    familia = entorno.familia_con_ficha()
    entorno.ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    retiro = entorno.ficha.iam.cliente.post(PERSONA.format(familia.persona.id) + "/consentimientos/plan_cuidado/retiro",
                                            headers=_cab(entorno, familia.admin, familia))
    assert retiro.status_code == 200
    [(_, _, retirada_en, _)] = [c for c in _consentimientos(familia) if c[1] == "plan_cuidado"]
    entorno.reloj.avanzar(timedelta(minutes=1))

    respuesta = _borrar(entorno, familia)

    assert respuesta.status_code == 200 and respuesta.json()["autorizaciones_retiradas"] == 1
    motivos = {c[1]: (c[2], c[3]) for c in _consentimientos(familia)}
    assert motivos["plan_cuidado"] == (retirada_en, "retiro")
    assert motivos["consumo"] == (entorno.reloj.ahora(), "borrado")
    # Aunque la autorización de la ficha estaba retirada, la clave y las secciones se borran al tiro
    assert _secciones(familia) == 0 and [k[1] for k in _clave(familia)] == [True]


def test_persona_sin_ficha_ni_consumo_ni_direccion(entorno: EntornoAbrir) -> None:
    familia = entorno.ficha.familia()
    persona = entorno.ficha.fabrica.persona_cuidada(familia.grupo, con_direccion=False)
    respuesta = entorno.ficha.iam.cliente.post(BORRADO.format(persona.id),
                                               headers=_cab(entorno, familia.admin, familia))
    assert respuesta.status_code == 200, respuesta.text
    assert (respuesta.json()["enlaces_cortados"], respuesta.json()["autorizaciones_retiradas"]) == (0, 1)
    assert [a[0] for a in _acciones(familia.grupo.id)] == ["consentimiento.revocar", "persona.borrar"]


def test_una_direccion_que_usa_otra_persona_no_se_borra(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    otra = entorno.ficha.fabrica.persona_cuidada(familia.grupo, con_direccion=False)
    _ejecutar("UPDATE persona_cuidada SET direccion_entrega_id = %s WHERE id = %s", familia.persona.direccion_id,
              otra.id)
    assert _borrar(entorno, familia).status_code == 200
    assert _una("SELECT 1 FROM direccion WHERE id = %s", familia.persona.direccion_id) == (1,)
    assert _una("SELECT direccion_entrega_id FROM persona_cuidada WHERE id = %s", otra.id) == (
        familia.persona.direccion_id,)


# --- Quién (D1, C2) -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("etiqueta", ["pagador", "pagador_con_plan", "observador"])
def test_pagador_y_observador_no_borran_404_y_nada_cambia(entorno: EntornoAbrir, etiqueta: str) -> None:
    familia = _completa(entorno)
    antes = _persona(familia)
    respuesta = _borrar(entorno, familia, familia.miembros[etiqueta].usuario)
    assert respuesta.status_code == 404 and respuesta.json()["type"] == "/errores/no-encontrado"
    assert respuesta.headers["cache-control"] == "no-store"
    _sin_cambios(familia, antes)
    assert _acciones(familia.grupo.id, "persona.borrar") == []


@pytest.mark.parametrize("etiqueta", ["pagador", "observador"])
def test_pagador_y_observador_404_tambien_si_ya_se_borro(entorno: EntornoAbrir, etiqueta: str) -> None:
    familia = entorno.familia_con_ficha()
    assert _borrar(entorno, familia).status_code == 200
    assert _borrar(entorno, familia, familia.miembros[etiqueta].usuario).status_code == 404


def test_otro_grupo_sin_membresia_sin_token_o_id_invalido(entorno: EntornoAbrir) -> None:
    a, b = _completa(entorno), _completa(entorno)
    antes_b = _persona(b)
    respuestas = [
        _borrar(entorno, a, persona=b.persona.id),  # persona de otro grupo con el grupo propio
        _borrar(entorno, a, cabeceras=_cab(entorno, b.admin, a)),  # sin membresía en el grupo
        _borrar(entorno, a, persona="no-es-uuid"),
        _borrar(entorno, a, persona=uuid.uuid4()),
    ]
    for respuesta in respuestas:
        assert respuesta.status_code == 404, respuesta.text
        assert respuesta.headers["cache-control"] == "no-store"
    sin_token = _borrar(entorno, a, cabeceras={"X-Grupo-Id": str(a.grupo.id)})
    assert sin_token.status_code == 401
    _sin_cambios(b, antes_b)
    _sin_cambios(a, _persona(a))


def test_borrada_de_otro_grupo_404(entorno: EntornoAbrir) -> None:
    a, b = entorno.familia_con_ficha(), entorno.familia_con_ficha()
    assert _borrar(entorno, b).status_code == 200
    assert _borrar(entorno, a, persona=b.persona.id).status_code == 404


def test_otras_personas_y_otros_grupos_no_se_tocan(entorno: EntornoAbrir) -> None:
    a, b = _completa(entorno), _completa(entorno)
    hermana = entorno.ficha.fabrica.persona_cuidada(a.grupo)
    _, token_b, pin_b = entorno.compartir(b)
    antes_b, antes_hermana = _persona(b), _una("SELECT nombre, eliminado_en FROM persona_cuidada WHERE id = %s",
                                               hermana.id)
    assert _borrar(entorno, a).status_code == 200
    _sin_cambios(b, antes_b)
    assert _una("SELECT nombre, eliminado_en FROM persona_cuidada WHERE id = %s", hermana.id) == antes_hermana
    assert _una("SELECT revocado_en FROM consentimiento WHERE id = %s", hermana.consentimiento_id) == (None,)
    assert entorno.abrir(token_b, pin_b).status_code == 200


# --- Si algo falla, nada (C13) ---------------------------------------------------------------------------------


def test_si_falla_el_corte_de_un_acceso_nada_queda_escrito(
    entorno: EntornoAbrir, monkeypatch: pytest.MonkeyPatch
) -> None:
    familia = _completa(entorno)
    primero, _, _ = entorno.compartir(familia)
    segundo, token, pin = entorno.compartir(familia)
    antes = _persona(familia)
    original = RepositorioAccesosSQL.revocar
    llamadas: list[uuid.UUID] = []

    def revocar_y_fallar(self: RepositorioAccesosSQL, acceso_id: uuid.UUID, *args: Any) -> None:
        llamadas.append(acceso_id)
        if len(llamadas) == 2:
            raise RuntimeError("falla sintética del corte")
        original(self, acceso_id, *args)

    monkeypatch.setattr(RepositorioAccesosSQL, "revocar", revocar_y_fallar)

    respuesta = _borrar(entorno, familia)

    assert respuesta.status_code == 500 and len(llamadas) == 2
    _sin_cambios(familia, antes)
    assert _acceso(primero)[:2] == (None, None) and _acceso(segundo)[:2] == (None, None)
    assert _acceso(primero)[2] == familia.persona.nombre_pila
    assert _una("SELECT 1 FROM direccion WHERE id = %s", familia.persona.direccion_id) == (1,)
    assert _acciones(familia.grupo.id, "consentimiento.revocar") == []
    assert _acciones(familia.grupo.id, "relevo.revocar") == []
    assert _acciones(familia.grupo.id, "persona.borrar") == []
    monkeypatch.undo()
    assert entorno.abrir(token, pin).status_code == 200


# --- Logs (C5) -------------------------------------------------------------------------------------------------


def test_los_logs_no_llevan_nada_de_la_persona(entorno: EntornoAbrir) -> None:
    familia = _completa(entorno)
    _, token, pin = entorno.compartir(familia)
    assert _borrar(entorno, familia).status_code == 200
    _borrar(entorno, familia)
    log = entorno.ficha.iam.texto_log()
    for dato in (familia.persona.nombre, familia.persona.nombre_pila, str(familia.persona.id), "Rosa", token, pin,
                 RUTINA, PREFERENCIAS, "Pañal"):
        assert dato not in log
    assert not aparece_celular("+56 9 5555 0137", log)
    peticiones = [linea for linea in entorno.ficha.iam.lineas_log() if linea.get("ruta") == BORRADO.format(
        "{persona_id}")]
    assert [linea["estado"] for linea in peticiones] == [200, 409]
    assert not any("enlaces" in str(linea) or "autorizaciones" in str(linea) for linea in peticiones)


# --- Un solo instante (C1) ---------------------------------------------------------------------------------------


class _RelojQueAvanza:
    """Un reloj que avanza un milisegundo cada vez que se lee: si algo pide su propia hora, se nota."""

    def __init__(self, inicio: Any) -> None:
        self.actual = inicio

    def ahora(self) -> Any:
        self.actual += timedelta(milliseconds=1)
        return self.actual


def test_el_borrado_usa_un_solo_instante_en_todo(entorno: EntornoAbrir) -> None:
    from app.modules.iam.api.dependencias import obtener_reloj

    familia = _completa(entorno)
    entorno.compartir(familia)
    cabeceras = _cab(entorno, familia.admin, familia)  # el token se emite con el reloj fijo
    reloj = _RelojQueAvanza(entorno.reloj.ahora())
    entorno.ficha.app.dependency_overrides[obtener_reloj] = lambda: reloj
    try:
        respuesta = _borrar(entorno, familia, cabeceras=cabeceras)
    finally:
        entorno.ficha.app.dependency_overrides[obtener_reloj] = lambda: entorno.reloj
    assert respuesta.status_code == 200, respuesta.text
    [(_, _, _, _, _, borrado_en, _)] = [_persona(familia)]
    instantes = {c[2] for c in _consentimientos(familia)} | {k[2] for k in _clave(familia)}
    instantes |= {f[7] for f in _acciones(familia.grupo.id) if f[0] != "relevo.compartir"}
    instantes |= {f[0] for f in _todas("SELECT a.revocado_en FROM acceso_relevo a WHERE a.grupo_id = %s",
                                       familia.grupo.id)}
    assert instantes == {borrado_en}


# --- Las tareas y lo que ya existía (C8, C10) -------------------------------------------------------------------


@pytest.mark.rf("RF-02")
def test_las_tareas_son_idempotentes_sobre_una_persona_borrada(entorno: EntornoAbrir) -> None:
    from datetime import UTC, datetime

    from app.core.db import fabrica_sesiones
    from app.modules.care_plan.infrastructure.tarea_destruccion import DestruccionClavesSql
    from app.modules.consumption.application.conservacion import conservar
    from app.modules.consumption.infrastructure.tarea_conservacion import ConservacionConsumoSql
    from tests.dobles.reloj_fijo import RelojFijo

    familia = _completa(entorno)
    assert _borrar(entorno, familia).status_code == 200
    clave, antes = _clave(familia), _acciones(familia.grupo.id)
    reloj = RelojFijo(datetime.now(UTC))

    destruccion.destruir_fichas_retiradas(unidad=DestruccionClavesSql(fabrica_sesiones()), reloj=reloj)
    conservar(unidad=ConservacionConsumoSql(fabrica_sesiones()), reloj=reloj)

    assert _clave(familia) == clave and _acciones(familia.grupo.id) == antes
    assert _persona(familia)[5] is not None and _secciones(familia) == 0 and _perfiles(familia) == 0


# --- Carreras (C1, C3, C6, C8) ----------------------------------------------------------------------------------


def _borrar_en_transaccion(entorno: EntornoAbrir, familia: FamiliaCreada, sesion: Any) -> Any:
    registro = RegistroAuditoriaSql(sesion, entorno.reloj)
    return borrar_persona(
        SolicitudBorrado(usuario_id=familia.admin.id, rol="admin", persona_id=familia.persona.id),
        entorno.reloj, RepositorioBorradoSQL(sesion, familia.grupo.id, registro),
        RepositorioRetirosSQL(sesion, familia.grupo.id, registro), efectos_de(sesion, familia.grupo.id, registro),
    )


def _mientras_borra(entorno: EntornoAbrir, familia: FamiliaCreada, peticion: Any) -> Any:
    """Corre ``peticion`` en otro hilo mientras un borrado sigue abierto: debe esperar su bloqueo. Las cabeceras
    (y el inicio de sesión, que tarda) se arman antes: lo único que puede hacer esperar al hilo es el bloqueo."""
    respuestas: list[Any] = []
    hilo = threading.Thread(target=lambda: respuestas.append(peticion()))
    with sesion_tenant(_fabrica(entorno), usuario_id=familia.admin.id, grupo_id=familia.grupo.id) as sesion:
        _borrar_en_transaccion(entorno, familia, sesion)
        hilo.start()
        hilo.join(timeout=1.0)
        assert hilo.is_alive()  # espera el bloqueo del borrado
    hilo.join(timeout=15)
    [respuesta] = respuestas
    return respuesta


def test_dos_borrados_a_la_vez_el_segundo_espera_y_409(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    cab = _cab(entorno, _cuidador(familia), familia)
    respuesta = _mientras_borra(entorno, familia, lambda: _borrar(entorno, familia, cabeceras=cab))
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/ya-borrada"
    assert len(_acciones(familia.grupo.id, "persona.borrar")) == 1


def test_autorizar_durante_un_borrado_espera_y_404_sin_escribir(entorno: EntornoAbrir) -> None:
    """C8: otorgar toma la fila de la persona con FOR SHARE y falla si ya tiene eliminado_en."""
    familia = entorno.familia_con_ficha()
    cab = _cab(entorno, _cuidador(familia), familia)
    respuesta = _mientras_borra(entorno, familia, lambda: entorno.ficha.iam.cliente.post(
        PERSONA.format(familia.persona.id) + "/consentimientos",
        json={"finalidad": "consumo", "calidad_otorgante": "titular"}, headers=cab))
    assert respuesta.status_code == 404, respuesta.text
    assert [c[1] for c in _consentimientos(familia)] == ["plan_cuidado"]
    assert _acciones(familia.grupo.id, "consentimiento.otorgar") == []


def test_retirar_durante_un_borrado_espera_y_409(entorno: EntornoAbrir) -> None:
    """C8: el retiro espera el bloqueo de la autorización y la encuentra revocada por el borrado."""
    familia = entorno.familia_con_ficha()
    cab = _cab(entorno, _cuidador(familia), familia)
    respuesta = _mientras_borra(entorno, familia, lambda: entorno.ficha.iam.cliente.post(
        PERSONA.format(familia.persona.id) + "/consentimientos/plan_cuidado/retiro", headers=cab))
    assert respuesta.status_code in (404, 409), respuesta.text
    assert [(c[1], c[3]) for c in _consentimientos(familia)] == [("plan_cuidado", "borrado")]


def test_borrar_durante_un_retiro_espera_y_la_retirada_conserva_su_motivo(entorno: EntornoAbrir) -> None:
    """C8: el borrado espera el bloqueo del retiro; la autorización queda con retiro y la de consumo con borrado."""
    familia = entorno.familia_con_ficha()
    entorno.ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    respuestas: list[Any] = []
    cab = _cab(entorno, _cuidador(familia), familia)
    hilo = threading.Thread(target=lambda: respuestas.append(_borrar(entorno, familia, cabeceras=cab)))
    with sesion_tenant(_fabrica(entorno), usuario_id=familia.admin.id, grupo_id=familia.grupo.id) as sesion:
        registro = RegistroAuditoriaSql(sesion, entorno.reloj)
        retirar_autorizacion(
            SolicitudRetiro(usuario_id=familia.admin.id, rol="admin", persona_id=familia.persona.id,
                            finalidad="plan_cuidado"),
            entorno.reloj, RepositorioRetirosSQL(sesion, familia.grupo.id, registro),
            efectos_de(sesion, familia.grupo.id, registro),
        )
        hilo.start()
        hilo.join(timeout=1.0)
        assert hilo.is_alive()  # el borrado espera el bloqueo de la autorización
    hilo.join(timeout=15)
    [respuesta] = respuestas
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["autorizaciones_retiradas"] == 1
    assert {c[1]: c[3] for c in _consentimientos(familia)} == {"plan_cuidado": "retiro", "consumo": "borrado"}
    assert _persona(familia)[5] is not None


@pytest.mark.rf("RF-02")
def test_una_seccion_confirmada_mientras_el_borrado_espera_la_clave_tambien_se_borra(entorno: EntornoAbrir) -> None:
    """C6: una escritura que tiene la clave con FOR SHARE (la de RepositorioClavesSQL al escribir) y confirma una
    sección mientras el UPDATE de la clave del borrado espera. Como la clave y las secciones van en sentencias
    separadas, la sección nueva también se borra. En una sola sentencia con CTE quedaría viva."""
    familia = entorno.familia_con_ficha()
    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id)
    assert plan is not None
    respuestas: list[Any] = []
    cab = _cab(entorno, familia.admin, familia)
    borrado = threading.Thread(target=lambda: respuestas.append(_borrar(entorno, familia, cabeceras=cab)))
    with sesion_tenant(_fabrica(entorno), usuario_id=_cuidador(familia).id, grupo_id=familia.grupo.id) as sesion:
        clave = sesion.execute(text("SELECT id FROM clave_datos WHERE persona_cuidada_id = :p AND destruida_en IS NULL"
                                    " FOR SHARE"), {"p": familia.persona.id}).first()
        assert clave is not None
        sesion.execute(text(
            "INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version, version,"
            " actualizado_por) VALUES (:plan, 'movilidad', :c, :n, :t, 1, 1, :u)"),
            {"plan": plan[0], "c": b"\x01" * 24, "n": b"\x02" * 12, "t": b"\x03" * 16, "u": _cuidador(familia).id})
        borrado.start()
        borrado.join(timeout=1.0)
        assert borrado.is_alive()  # el UPDATE de la clave espera el FOR SHARE de la escritura
    borrado.join(timeout=15)
    [respuesta] = respuestas
    assert respuesta.status_code == 200, respuesta.text
    assert _secciones(familia) == 0


def test_la_auditoria_del_borrado_no_lleva_nombres_ni_contadores(entorno: EntornoAbrir) -> None:
    """C4: ni detalle, ni IP, ni el nombre en ninguna fila del grupo."""
    familia = _completa(entorno)
    entorno.compartir(familia)
    assert _borrar(entorno, familia).status_code == 200
    with psycopg.connect(DSN) as cx:
        filas = cx.execute("SELECT row_to_json(a)::text FROM auditoria a WHERE grupo_id = %s",
                           (familia.grupo.id,)).fetchall()
    texto = " ".join(f[0] for f in filas)
    for dato in (familia.persona.nombre, familia.persona.nombre_pila, "Rosa", "Pañal", "enlaces"):
        assert dato not in texto
    assert all('"detalle":null' in f[0] and '"ip":null' in f[0] for f in filas if '"persona.borrar"' in f[0])
