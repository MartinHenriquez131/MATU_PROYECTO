"""MATU-44 · Retirar la autorización de los insumos, contra PostgreSQL (D5, condición 10 del analista, RF-10).

El reloj es el de entorno_iam (20-10-2026). El perfil por omisión de la fábrica está en su ventana de aviso.
Solo datos sintéticos.
"""

import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from app.core.db import fabrica_sesiones
from app.modules.consumption.infrastructure.tarea_quiebres import recalcular_grupo
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.consumption.conftest import EntornoConsumo

pytestmark = [requiere_base, pytest.mark.rf("RF-10")]

RUTA = "/v1/personas-cuidadas/{}/consentimientos"
NOMBRE = "Pañal adulto M"


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _alerta(perfil: uuid.UUID, estado: str, fecha: str = "2026-10-26") -> uuid.UUID:
    with psycopg.connect(DSN, autocommit=True) as cx:
        fila = cx.execute(
            "INSERT INTO alerta_quiebre (perfil_id, fecha_prevista, estado, notificada_en)"
            " VALUES (%s, %s, %s, CASE WHEN %s = 'notificada' THEN now() END) RETURNING id",
            (perfil, fecha, estado, estado),
        ).fetchone()
    assert fila is not None
    return uuid.UUID(str(fila[0]))


def _retirar(e: EntornoConsumo, familia: FamiliaCreada, usuario: UsuarioCreado | None = None) -> Any:
    return e.iam.cliente.post(RUTA.format(familia.persona.id) + "/consumo/retiro",
                              headers=e.cabeceras(usuario or familia.admin, familia.grupo.id))


def _autorizar(e: EntornoConsumo, familia: FamiliaCreada) -> Any:
    return e.iam.cliente.post(RUTA.format(familia.persona.id), json={"finalidad": "consumo",
                              "calidad_otorgante": "titular"}, headers=e.cabeceras(familia.admin, familia.grupo.id))


def test_retirar_descarta_las_alertas_abiertas_en_la_misma_transaccion(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    otro = e.fabrica.perfil_consumo(familia.persona, nombre_libre="Toallitas")
    pendiente, notificada = _alerta(perfil, "pendiente"), _alerta(otro, "notificada")
    cuidador = familia.miembros["cuidador"].usuario

    respuesta = _retirar(e, familia, cuidador)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["enlaces_cortados"] == 0
    assert respuesta.json()["autorizacion"]["estado"] == "retirada"
    estados = dict(_filas("SELECT id, estado FROM alerta_quiebre WHERE id = ANY(%s)", [pendiente, notificada]))
    assert estados == {pendiente: "descartada", notificada: "descartada"}
    descartes = _filas("SELECT actor_tipo, actor_ref, entidad_id, detalle FROM auditoria"
                       " WHERE accion = 'alerta.descartar' AND grupo_id = %s ORDER BY entidad_id", familia.grupo.id)
    esperados = [("usuario", cuidador.id, pendiente, None), ("usuario", cuidador.id, notificada, None)]
    assert sorted(descartes, key=lambda f: str(f[2])) == sorted(esperados, key=lambda f: str(f[2]))


def test_los_insumos_tras_el_retiro_403_con_finalidad_consumo(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    assert _retirar(e, familia).status_code == 200

    for respuesta in (
        e.pedir("GET", familia.admin, familia),
        e.pedir("GET", familia.admin, familia, "/por-acabarse"),
        e.pedir("GET", familia.admin, familia, "/lista"),
        e.crear(familia.admin, familia),
        e.pedir("PATCH", familia.admin, familia, f"/{perfil}", json={"stock_unidades": 3}, If_Match='"v1"'),
    ):
        assert respuesta.status_code == 403, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["type"] == "/errores/sin-consentimiento" and cuerpo["finalidad"] == "consumo"


def test_el_trabajo_diario_no_crea_alertas_tras_el_retiro(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    assert _retirar(e, familia).status_code == 200

    resultado = recalcular_grupo(fabrica_sesiones(), familia.grupo.id, e.iam.reloj)

    assert resultado.materializadas == 0
    assert _filas("SELECT id FROM alerta_quiebre WHERE perfil_id = %s", perfil) == []


def test_volver_a_autorizar_antes_de_90_dias_trae_los_insumos(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    assert _retirar(e, familia).status_code == 200
    e.iam.reloj.avanzar(timedelta(minutes=1))

    assert _autorizar(e, familia).status_code == 201

    lista = e.pedir("GET", familia.admin, familia)
    assert lista.status_code == 200 and [p["id"] for p in lista.json()["items"]] == [str(perfil)]


def test_retirar_consumo_dos_veces_409_y_nunca_autorizado_404(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    assert _retirar(e, familia).status_code == 200
    segunda = _retirar(e, familia)
    assert segunda.status_code == 409 and segunda.json()["type"] == "/errores/ya-retirada"
    sin = e.familia(con_autorizacion=False)
    assert _retirar(e, sin).status_code == 404


def test_estado_tras_el_retiro_y_los_logs_sin_nombre_libre(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    e.fabrica.perfil_consumo(familia.persona, nombre_libre=NOMBRE)
    assert _retirar(e, familia).status_code == 200
    estado = e.iam.cliente.get(RUTA.format(familia.persona.id), headers=e.cabeceras(familia.admin, familia.grupo.id))
    plan, consumo = estado.json()["autorizaciones"]
    assert plan["estado"] == "vigente"
    assert consumo["estado"] == "retirada" and consumo["borrada"] is False
    assert NOMBRE not in e.iam.texto_log() and familia.persona.nombre not in e.iam.texto_log()


# --- MATU-74, condición C9 del analista: los quiebres no esperan a los borrados -----------------------------------


@pytest.mark.parametrize("estado", ["persona_borrada", "autorizacion_retirada"])
def test_los_quiebres_no_crean_alerta_ni_evento_aunque_el_borrado_no_haya_corrido(
    entorno_consumo: EntornoConsumo, estado: str
) -> None:
    """Las tareas de borrado corren dos horas antes que los quiebres (H5), pero si no corrieron, o el borrado de la
    persona quedó a medias, el trabajo diario igual no crea nada: el perfil sigue en la base, activo y en su
    ventana de aviso, y la persona está borrada o su autorización retirada. Se fija con SQL directo, sin las rutas,
    que además descartarían las alertas y borrarían los perfiles."""
    e = entorno_consumo
    familia, testigo = e.familia(), e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    e.fabrica.perfil_consumo(testigo.persona)
    with psycopg.connect(DSN, autocommit=True) as cx:
        if estado == "persona_borrada":
            cx.execute("UPDATE persona_cuidada SET eliminado_en = now(), nivel_apoyo = NULL,"
                       " direccion_entrega_id = NULL WHERE id = %s", (familia.persona.id,))
        else:
            cx.execute("UPDATE consentimiento SET revocado_en = now(), revocacion_motivo = 'retiro'"
                       " WHERE persona_cuidada_id = %s AND finalidad = 'consumo'", (familia.persona.id,))
    assert _filas("SELECT activo FROM perfil_consumo WHERE id = %s", perfil) == [(True,)]

    resultado = recalcular_grupo(fabrica_sesiones(), familia.grupo.id, e.iam.reloj)

    assert resultado.materializadas == 0
    assert _filas("SELECT 1 FROM alerta_quiebre WHERE perfil_id = %s", perfil) == []
    assert _filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id) == []
    # El testigo, con la misma fábrica y el mismo reloj, sí tiene su alerta y su evento
    assert recalcular_grupo(fabrica_sesiones(), testigo.grupo.id, e.iam.reloj).materializadas == 1
    assert len(_filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", testigo.grupo.id)) == 1
