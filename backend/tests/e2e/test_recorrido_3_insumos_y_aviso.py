"""MATU-80 · Recorrido 3 de MATU-64: anotar los insumos y ver el aviso de quiebre.

La familia da la autorización para calcular los insumos y anota uno por la API. «Se acaban pronto» lo muestra al
momento. Después corren, como el sistema, el trabajo diario de MATU-37 (materializa la alerta y deja el evento
QuiebreProximo en el outbox) y el consumidor de avisos de MATU-41 con el correo y el push simulados (dobles en
memoria): a la cuidadora le llega el aviso, y la alerta queda notificada en la API. Solo datos sintéticos.
"""

import uuid

import psycopg
import pytest

from app.core.db import fabrica_sesiones
from app.core.push_piloto import PoliticaPush
from app.modules.consumption.infrastructure.tarea_quiebres import recalcular_grupo
from app.modules.notifications.application.avisos import ConsumidorQuiebreProximo
from app.modules.notifications.infrastructure.repositorio_avisos import UnidadAvisosSQL
from app.shared.outbox import EventoTomado, Hecho
from tests.base_datos import DSN, requiere_base
from tests.dobles.enviadores_en_memoria import EnviadorCorreoEnMemoria, EnviadorPushEnMemoria
from tests.e2e.conftest import Recorrido

pytestmark = [
    requiere_base,
    pytest.mark.e2e,
    pytest.mark.rf("RF-10"),
    pytest.mark.rf("RF-11"),
    pytest.mark.rf("RF-12"),
    pytest.mark.rf("RF-39"),
]

NOMBRE = "Pañal adulto M"


def _evento_del_outbox(grupo_id: uuid.UUID) -> EventoTomado:
    """El evento tal como el publicador del outbox se lo entrega al consumidor. Se lee por el grupo del recorrido:
    el publicador real tomaría también los eventos de otros grupos de la base de pruebas."""
    with psycopg.connect(DSN) as cx:
        [(evento_id, grupo, tipo, payload, intentos)] = cx.execute(
            "SELECT id, grupo_id, tipo, payload, intentos FROM evento_outbox WHERE grupo_id = %s", (grupo_id,)
        ).fetchall()
    return EventoTomado(evento_id, grupo, tipo, payload, intentos)


def test_recorrido_insumos_y_aviso(recorrido: Recorrido) -> None:
    r = recorrido
    f = r.familia()

    # Dado una familia que autoriza el cálculo de los insumos
    autorizacion = r.autorizar(f, "consumo")
    assert autorizacion.status_code == 201, autorizacion.text

    # Cuando anota un insumo: 24 pañales, 4 al día, avisa con 7 días por omisión
    perfil = r.anotar_insumo(f, nombre_libre=NOMBRE, tasa_unidades=4, stock_unidades=24)

    # Entonces MATU calcula cuándo se acaba (el reloj está en el 20-10-2026) y «Se acaban pronto» lo muestra
    assert perfil["fecha_quiebre_estimada"] == "2026-10-26"
    pronto = r.de_la_persona(f, "GET", "/consumo/por-acabarse")
    assert pronto.status_code == 200, pronto.text
    [item] = pronto.json()["items"]
    assert (item["id"], item["avisando"], item["alerta_id"]) == (perfil["id"], True, None)

    # Cuando corre el trabajo diario, como el sistema
    assert recalcular_grupo(fabrica_sesiones(), f.grupo_id, r.iam.reloj).materializadas == 1

    # Y el consumidor de avisos toma el evento QuiebreProximo, con el correo y el push simulados
    correo, push = EnviadorCorreoEnMemoria(), EnviadorPushEnMemoria()
    consumidor = ConsumidorQuiebreProximo(
        unidad=UnidadAvisosSQL(fabrica_sesiones()),
        correo=correo,
        push=push,
        reloj=r.iam.reloj,
        origen_web="https://matu.example",
        push_permitido=PoliticaPush(entorno="pruebas").permite,
    )
    assert isinstance(consumidor.consumir(_evento_del_outbox(f.grupo_id)), Hecho)

    # Entonces a la cuidadora le llega el aviso por correo, sin el nombre del insumo ni de la persona
    [enviado] = correo.enviados
    assert enviado.destino == f.cuenta.email
    assert NOMBRE not in str(enviado) and "Elena" not in str(enviado)

    # Y la API muestra la alerta: en «Se acaban pronto» con su id, y notificada en las alertas
    [item] = r.de_la_persona(f, "GET", "/consumo/por-acabarse").json()["items"]
    assert item["avisando"] is True and item["alerta_id"] is not None
    alertas = r.de_la_persona(f, "GET", "/consumo/alertas")
    assert alertas.status_code == 200, alertas.text
    [alerta] = alertas.json()["items"]
    assert (alerta["id"], alerta["perfil_id"], alerta["estado"]) == (item["alerta_id"], perfil["id"], "notificada")

    # Y el nombre del insumo no llega a los logs de la API
    assert NOMBRE not in r.logs()
