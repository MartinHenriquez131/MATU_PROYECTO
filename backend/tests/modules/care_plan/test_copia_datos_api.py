"""MATU-54 · «Datos de {nombre_pila}»: GET /v1/personas-cuidadas/{persona_id}/datos, contra PostgreSQL (Ley 21.719).

La API corre como matu_app con la RLS de siempre. La custodia es CustodiaEnMemoria y el límite usa el contador en
memoria de entorno_iam. Solo datos sintéticos: los nombres, los teléfonos y los textos son marcas inventadas que la
prueba busca en la respuesta y en los logs.
"""

import secrets
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from app.core.limite_ip import obtener_pepper_limites
from app.modules.care_circle.infrastructure import copia_datos
from app.modules.care_plan.api import router_copia
from app.modules.care_plan.api.dependencias import obtener_auditoria_ficha, obtener_custodia, obtener_pepper_pin
from app.shared.copia_datos import AVISO_COPIA
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.care_plan.conftest import EntornoFicha

pytestmark = [requiere_base, pytest.mark.rf("RF-08"), pytest.mark.rf("Ley-21.719")]

RUTA = "/v1/personas-cuidadas/{}/datos"
RUTINA = "Desayuna a las 08:30 con té. Marca sintética de la copia MATU-54"
RED = "Llamar a Rosa Sintética +56 9 0000 0154"
TELEFONO_RELEVO = "+56 9 5555 0154"
# Lo que nunca sale en la copia (C4, D-54-4 a, D-54-16 a). codigo_autorizacion va solo en «Tus datos» de quien pagó
# (F3, decisión 402): aquí sigue prohibido, también ultimos4, tarjeta y cuotas
PROHIBIDOS = {
    "id", "usuario_id", "grupo_id", "persona_id", "persona_cuidada_id", "acceso_id", "plan_id", "request_id", "ip",
    "actor_ref", "entidad_id", "detalle", "evidencia", "referencia_documento", "push_token", "token", "token_hash",
    "pin", "pin_hash", "telefono", "telefono_relevo", "telefono_contacto", "otorgado_a_telefono", "email", "correo",
    "celular", "buy_order", "session_id", "codigo_autorizacion", "etag", "tarjeta", "ultimos4", "cuotas",
}


@pytest.fixture(autouse=True)
def pepper_pin(entorno_ficha: EntornoFicha) -> Iterator[None]:
    entorno_ficha.app.dependency_overrides[obtener_pepper_pin] = lambda: secrets.token_bytes(32)
    yield
    entorno_ficha.app.dependency_overrides.pop(obtener_pepper_pin, None)


def _claves(valor: Any) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _claves(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _claves(v)}
    return set()


def _pedir(entorno: EntornoFicha, usuario: UsuarioCreado | None, familia: FamiliaCreada,
           persona: uuid.UUID | str | None = None) -> Any:
    return entorno.iam.cliente.get(RUTA.format(persona or familia.persona.id),
                                   headers=entorno._cabeceras(usuario, familia.grupo.id))


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _completa(entorno: EntornoFicha) -> FamiliaCreada:
    """Ficha con dos campos, autorización de insumos con un insumo, y un enlace de relevo compartido."""
    familia = entorno.familia()
    entorno.fabrica.ficha(familia.persona, actualizado_por=familia.admin.id, custodia=entorno.custodia,
                          textos={"rutina": RUTINA, "red_apoyo": RED})
    entorno.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin)
    entorno.fabrica.perfil_consumo(familia.persona, nombre_libre="Pañal sintético M")
    compartida = entorno.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/plan/accesos-relevo",
        json={"nombre_relevo": "Pedro", "telefono_relevo": TELEFONO_RELEVO, "motivo": "salgo_unas_horas",
              "relevo_informado": True},
        headers=entorno._cabeceras(familia.admin, familia.grupo.id))
    assert compartida.status_code == 201, compartida.text
    return familia


# --- Camino feliz -----------------------------------------------------------------------------------------------


def test_la_copia_del_admin_trae_todo_lo_guardado_sin_lo_que_nunca_sale(entorno_ficha: EntornoFicha) -> None:
    familia = _completa(entorno_ficha)

    respuesta = _pedir(entorno_ficha, familia.admin, familia)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["content-disposition"] == 'inline; filename="matu-datos-2026-10-20.json"'
    cuerpo = respuesta.json()
    assert (cuerpo["formato"], cuerpo["tipo"], cuerpo["aviso"]) == ("matu-datos/1", "persona_cuidada", AVISO_COPIA)
    assert cuerpo["generado_en"] == "2026-10-20T09:00:00-03:00"
    assert cuerpo["persona"]["nombre"] == familia.persona.nombre
    # La ficha, descifrada y completa, con «A quién llamar» tal como se escribió (D-54-4 a)
    ficha = cuerpo["ficha"]
    assert (ficha["estado"], ficha["completitud"]) == ("disponible", 67)
    textos = {c["campo"]: c["texto"] for c in ficha["campos"]}
    assert textos == {"rutina": RUTINA, "manejo_situaciones": None, "red_apoyo": RED}
    # Las autorizaciones de la ficha y de los insumos, con quién las registró y sin la referencia
    assert {a["finalidad"] for a in cuerpo["autorizaciones"]} == {"plan_cuidado", "consumo"}
    assert all(a["registrada_por"]["nombre"] == familia.admin.nombre for a in cuerpo["autorizaciones"])
    # El enlace, sin el teléfono del relevo
    [enlace] = cuerpo["enlaces_relevo"]
    assert (enlace["nombre_relevo"], enlace["estado"], enlace["aperturas"]) == ("Pedro", "vigente", [])
    assert TELEFONO_RELEVO not in respuesta.text and "+56955550154" not in respuesta.text
    # Los insumos, con su lista
    assert cuerpo["insumos"]["estado"] == "disponible"
    assert [i["nombre"] for i in cuerpo["insumos"]["lista"]] == ["Pañal sintético M"]
    # El historial del admin: todo, con la copia que acaba de pedir y el enlace compartido
    historial = cuerpo["historial"]
    assert historial["alcance"] == "todo" and historial["hay_hechos_sin_asociar"] is False
    tipos = [h["tipo"] for h in historial["hechos"]]
    assert tipos[0] == "pidio_una_copia" and "compartio_la_ficha" in tipos
    # Con la capa 3 registrada, los pedidos van (vacíos)
    assert cuerpo["pedidos"] == []
    assert not _claves(cuerpo) & PROHIBIDOS


def test_la_copia_queda_registrada_con_la_persona_y_sin_detalle(entorno_ficha: EntornoFicha) -> None:
    familia = _completa(entorno_ficha)

    assert _pedir(entorno_ficha, familia.admin, familia).status_code == 200

    assert _filas("SELECT actor_tipo, actor_ref, entidad, entidad_id, persona_cuidada_id, detalle FROM auditoria"
                  " WHERE accion = 'persona.datos_descargar' AND grupo_id = %s", familia.grupo.id) == [
        ("usuario", familia.admin.id, "persona_cuidada", familia.persona.id, familia.persona.id, None)]
    # La escritura del enlace también llevó su persona (0028)
    assert _filas("SELECT persona_cuidada_id FROM auditoria WHERE accion = 'relevo.compartir' AND grupo_id = %s",
                  familia.grupo.id) == [(familia.persona.id,)]


def test_el_cuidador_ve_solo_lo_suyo_en_el_historial(entorno_ficha: EntornoFicha) -> None:
    familia = _completa(entorno_ficha)
    cuidador = familia.miembros["cuidador"].usuario
    assert _pedir(entorno_ficha, familia.admin, familia).status_code == 200

    respuesta = _pedir(entorno_ficha, cuidador, familia)

    assert respuesta.status_code == 200, respuesta.text
    historial = respuesta.json()["historial"]
    assert historial["alcance"] == "lo_tuyo"
    # Solo su propia copia: ni la del admin ni el enlace que compartió el admin (D-54-6 a)
    assert [(h["tipo"], h["quien"]["nombre"]) for h in historial["hechos"]] == [("pidio_una_copia", cuidador.nombre)]
    # La ficha sí la lee completa: la ve quien cuida
    assert respuesta.json()["ficha"]["estado"] == "disponible"


# --- Autorización retirada o en pausa (D-54-5 a) --------------------------------------------------------------


def test_con_la_ficha_retirada_va_solo_el_estado_y_la_fecha_de_borrado(entorno_ficha: EntornoFicha) -> None:
    familia = _completa(entorno_ficha)
    retiro = entorno_ficha.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos/plan_cuidado/retiro",
        headers=entorno_ficha._cabeceras(familia.admin, familia.grupo.id))
    assert retiro.status_code == 200, retiro.text

    respuesta = _pedir(entorno_ficha, familia.admin, familia)

    assert respuesta.status_code == 200, respuesta.text
    ficha = respuesta.json()["ficha"]
    # 20-10 a las 12:00 UTC más 90 días: 18-01-2027 a las 09:00 en Chile
    assert ficha == {"estado": "retirada", "borrado_el": "2027-01-18", "completitud": None, "campos": None,
                     "secciones": None}
    assert RUTINA not in respuesta.text and "Rosa Sintética" not in respuesta.text
    # El retiro queda en el historial, con su finalidad (F1)
    retiros = [h for h in respuesta.json()["historial"]["hechos"] if h["tipo"] == "retiro_una_autorizacion"]
    assert [h["finalidad"] for h in retiros] == ["plan_cuidado"]
    # Los enlaces siguen: dicen a quién se comunicaron los datos
    assert len(respuesta.json()["enlaces_relevo"]) == 1


def test_con_la_revision_vencida_la_ficha_y_los_insumos_estan_en_pausa(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia(calidad="cuidador_de_hecho")
    entorno_ficha.fabrica.ficha(familia.persona, actualizado_por=familia.admin.id, custodia=entorno_ficha.custodia,
                                textos={"rutina": RUTINA})
    entorno_ficha.fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin, calidad="cuidador_de_hecho")
    entorno_ficha.fabrica.perfil_consumo(familia.persona)
    with psycopg.connect(DSN) as cx:
        # consentimiento es inalterable (0006): el superusuario apaga el trigger solo para sembrar
        cx.execute("SET LOCAL session_replication_role = replica")
        cx.execute("UPDATE consentimiento SET revision_vence_en = %s WHERE persona_cuidada_id = %s",
                   (entorno_ficha.iam.reloj.ahora() - timedelta(days=1), familia.persona.id))

    respuesta = _pedir(entorno_ficha, familia.admin, familia)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["ficha"]["estado"], cuerpo["ficha"]["campos"]) == ("en_pausa", None)
    assert cuerpo["insumos"] == {"estado": "en_pausa", "borrado_el": None, "lista": None, "compras": None,
                                 "avisos": None}
    assert {a["estado"] for a in cuerpo["autorizaciones"]} == {"revision_vencida"}
    assert RUTINA not in respuesta.text and "Pañal adulto M" not in respuesta.text


def test_sin_autorizacion_de_insumos_no_hay_insumos(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()

    cuerpo = _pedir(entorno_ficha, familia.admin, familia).json()

    assert cuerpo["insumos"]["estado"] == "sin_autorizar" and cuerpo["insumos"]["lista"] is None
    # Sin plan todavía, la ficha está disponible y en blanco
    assert cuerpo["ficha"]["completitud"] == 0


# --- Errores: 401, 404, 429 y 503 ----------------------------------------------------------------------------------


def test_sin_sesion_401(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()

    respuesta = _pedir(entorno_ficha, None, familia)

    assert respuesta.status_code == 401
    assert respuesta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("etiqueta", ["pagador", "pagador_con_plan", "observador"])
def test_pagador_y_observador_reciben_404(entorno_ficha: EntornoFicha, etiqueta: str) -> None:
    familia = _completa(entorno_ficha)

    respuesta = _pedir(entorno_ficha, familia.miembros[etiqueta].usuario, familia)

    assert respuesta.status_code == 404
    assert respuesta.headers["cache-control"] == "no-store"
    assert RUTINA not in respuesta.text and familia.persona.nombre not in respuesta.text
    assert _filas("SELECT count(*) FROM auditoria WHERE accion = 'persona.datos_descargar' AND grupo_id = %s",
                  familia.grupo.id) == [(0,)]


def test_la_persona_de_otro_grupo_o_inexistente_da_404(entorno_ficha: EntornoFicha) -> None:
    a = entorno_ficha.familia()
    b = _completa(entorno_ficha)

    # A con su grupo y la persona de B; A con el grupo de B; una persona inexistente; un id que no es UUID
    assert _pedir(entorno_ficha, a.admin, a, b.persona.id).status_code == 404
    otro = entorno_ficha.iam.cliente.get(RUTA.format(b.persona.id),
                                         headers=entorno_ficha._cabeceras(a.admin, b.grupo.id))
    assert otro.status_code == 404
    assert _pedir(entorno_ficha, a.admin, a, uuid.uuid4()).status_code == 404
    assert _pedir(entorno_ficha, a.admin, a, "no-es-uuid").status_code == 404


def test_la_persona_borrada_da_404(entorno_ficha: EntornoFicha) -> None:
    familia = _completa(entorno_ficha)
    borrado = entorno_ficha.iam.cliente.post(f"/v1/personas-cuidadas/{familia.persona.id}/borrado",
                                             headers=entorno_ficha._cabeceras(familia.admin, familia.grupo.id))
    assert borrado.status_code == 200, borrado.text

    assert _pedir(entorno_ficha, familia.admin, familia).status_code == 404


def test_la_copia_11_en_una_hora_da_429_y_no_se_registra(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    for _ in range(10):
        assert _pedir(entorno_ficha, familia.admin, familia).status_code == 200

    respuesta = _pedir(entorno_ficha, familia.admin, familia)

    assert respuesta.status_code == 429
    assert respuesta.json()["type"] == "/errores/tope-copias"
    assert respuesta.headers["cache-control"] == "no-store"
    assert 1 <= int(respuesta.headers["retry-after"]) <= 3600
    assert _filas("SELECT count(*) FROM auditoria WHERE accion = 'persona.datos_descargar' AND grupo_id = %s",
                  familia.grupo.id) == [(10,)]
    # El contador es común con «Tus datos»
    tus_datos = entorno_ficha.iam.cliente.get("/v1/yo/datos", headers=entorno_ficha._cabeceras(familia.admin, None))
    assert tus_datos.status_code == 429


def test_un_404_no_gasta_el_cupo(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    for _ in range(12):
        assert _pedir(entorno_ficha, familia.admin, familia, uuid.uuid4()).status_code == 404

    assert _pedir(entorno_ficha, familia.admin, familia).status_code == 200


def test_sin_pepper_de_limites_503(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    # Entrar también usa PEPPER_LIMITES (la demora de la entrada): primero se entra
    entorno_ficha.token(familia.admin)
    entorno_ficha.app.dependency_overrides[obtener_pepper_limites] = lambda: None
    try:
        respuesta = _pedir(entorno_ficha, familia.admin, familia)
    finally:
        entorno_ficha.app.dependency_overrides[obtener_pepper_limites] = lambda: entorno_ficha.iam.pepper_limites

    assert respuesta.status_code == 503
    assert respuesta.headers["cache-control"] == "no-store"


def test_con_la_ficha_vigente_y_sin_custodia_503_y_nada_queda_registrado(entorno_ficha: EntornoFicha) -> None:
    familia = _completa(entorno_ficha)
    entorno_ficha.app.dependency_overrides[obtener_custodia] = lambda: None
    try:
        respuesta = _pedir(entorno_ficha, familia.admin, familia)
    finally:
        entorno_ficha.app.dependency_overrides[obtener_custodia] = lambda: entorno_ficha.custodia

    assert respuesta.status_code == 503
    assert RUTINA not in respuesta.text and familia.persona.nombre not in respuesta.text
    # El registro se deshizo con la transacción
    assert _filas("SELECT count(*) FROM auditoria WHERE accion = 'persona.datos_descargar' AND grupo_id = %s",
                  familia.grupo.id) == [(0,)]


def test_si_el_registro_falla_no_se_entrega_nada(entorno_ficha: EntornoFicha, monkeypatch: pytest.MonkeyPatch) -> None:
    familia = _completa(entorno_ficha)

    class RegistroQueFalla(router_copia.RegistroAuditoriaSql):
        def registrar(self, entrada: Any) -> None:
            raise RuntimeError("la base rechazó la fila")

    monkeypatch.setattr(router_copia, "RegistroAuditoriaSql", RegistroQueFalla)

    respuesta = _pedir(entorno_ficha, familia.admin, familia)

    assert respuesta.status_code == 500
    assert RUTINA not in respuesta.text and familia.persona.nombre not in respuesta.text


# --- La capa 3 quitada (D-54-15 a) --------------------------------------------------------------------------------


def test_sin_la_capa_3_los_pedidos_van_en_null(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    fuente = copia_datos.bloque(copia_datos.BLOQUE_PEDIDOS)
    assert fuente is not None
    copia_datos.quitar_bloque(copia_datos.BLOQUE_PEDIDOS)
    try:
        respuesta = _pedir(entorno_ficha, familia.admin, familia)
    finally:
        copia_datos.registrar_bloque(copia_datos.BLOQUE_PEDIDOS, fuente)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["pedidos"] is None


def test_sin_el_bloque_de_insumos_falla_cerrada(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    fuente = copia_datos.bloque(copia_datos.BLOQUE_INSUMOS)
    assert fuente is not None
    copia_datos.quitar_bloque(copia_datos.BLOQUE_INSUMOS)
    try:
        respuesta = _pedir(entorno_ficha, familia.admin, familia)
    finally:
        copia_datos.registrar_bloque(copia_datos.BLOQUE_INSUMOS, fuente)

    assert respuesta.status_code == 500
    assert familia.persona.nombre not in respuesta.text


# --- Asociación de la auditoría a la persona (0028) ----------------------------------------------------------------


def test_con_dos_personas_cada_copia_trae_solo_lo_de_su_persona(entorno_ficha: EntornoFicha) -> None:
    """La auditoría real de la ficha: una sección quitada y una edición se atribuyen a la persona correcta."""
    entorno_ficha.app.dependency_overrides.pop(obtener_auditoria_ficha, None)
    familia = entorno_ficha.familia()
    otra = entorno_ficha.fabrica.persona_cuidada(familia.grupo)
    escrita = entorno_ficha.escribir(familia.admin, familia.grupo.id, otra.id, "rutina", {"texto": RUTINA})
    assert escrita.status_code == 201, escrita.text
    seccion = entorno_ficha.iam.cliente.put(
        f"/v1/personas-cuidadas/{otra.id}/plan/secciones/remedios", json={"texto": "Sintético"},
        headers={**entorno_ficha._cabeceras(familia.admin, familia.grupo.id), "If-None-Match": "*"})
    assert seccion.status_code == 201, seccion.text
    quitada = entorno_ficha.iam.cliente.delete(
        f"/v1/personas-cuidadas/{otra.id}/plan/secciones/remedios",
        headers={**entorno_ficha._cabeceras(familia.admin, familia.grupo.id), "If-Match": seccion.headers["etag"]})
    assert quitada.status_code == 204, quitada.text

    de_la_primera = _pedir(entorno_ficha, familia.admin, familia).json()["historial"]["hechos"]
    de_la_otra = _pedir(entorno_ficha, familia.admin, familia, otra.id).json()["historial"]["hechos"]

    assert [h["tipo"] for h in de_la_primera] == ["pidio_una_copia"]
    tipos = [(h["tipo"], h["campo"], h["seccion"]) for h in de_la_otra]
    assert tipos == [
        ("pidio_una_copia", None, None),
        ("quito_una_seccion", None, "remedios"),
        ("edito_la_ficha", None, "remedios"),
        ("edito_la_ficha", "rutina", None),
    ]


# --- Logs (C29) ----------------------------------------------------------------------------------------------------


def test_los_logs_no_llevan_la_copia(entorno_ficha: EntornoFicha) -> None:
    familia = _completa(entorno_ficha)

    assert _pedir(entorno_ficha, familia.admin, familia).status_code == 200

    logs = entorno_ficha.iam.texto_log()
    for marca in (RUTINA, RED, "Rosa Sintética", TELEFONO_RELEVO, familia.persona.nombre, "Pañal sintético M"):
        assert marca not in logs
    assert "/v1/personas-cuidadas/{persona_id}/datos" in logs or "datos" in logs
