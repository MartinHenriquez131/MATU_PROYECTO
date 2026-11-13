"""MATU-107 · C-107-5: la segunda barrera de C14 en el consumidor de avisos.

Fuera de local y pruebas, una cuenta que no está en PUSH_CUENTAS_PERMITIDAS no tiene destino push aunque su
dispositivo tenga un push_token guardado (por ejemplo, de antes del control): su fila queda omitida con el código
existente sin_destino y no se envía nada. El correo no cambia. Contra PostgreSQL real, como matu_app. Solo datos
sintéticos.
"""

import pytest

from app.core.push_piloto import PoliticaPush
from app.shared.outbox import Hecho
from tests.base_datos import requiere_base
from tests.modules.notifications.conftest import EntornoAvisos

pytestmark = [requiere_base, pytest.mark.rf("RF-39")]

TOKEN = "https://fcm.googleapis.com/fcm/send/token-sintetico-piloto-{}"


def test_una_cuenta_fuera_de_la_lista_queda_sin_destino_push(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    admin, cuidador = familia.admin, familia.miembros["cuidador"].usuario
    e.dispositivo(admin, TOKEN.format(1))
    e.dispositivo(cuidador, TOKEN.format(2))
    # Solo el cuidador es del equipo
    e.politica = PoliticaPush(entorno="staging", permitidas=frozenset({cuidador.id}))
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)

    assert e.avisos(familia) == {
        (admin.id, "correo"): ("enviada", None),
        (admin.id, "push"): ("omitida", "sin_destino"),
        (cuidador.id, "correo"): ("enviada", None),
        (cuidador.id, "push"): ("enviada", None),
    }
    assert [(x.usuario_id, x.push_token) for x in e.push.enviados] == [(cuidador.id, TOKEN.format(2))]


def test_con_la_lista_vacia_ningun_push_sale(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    e.dispositivo(familia.admin, TOKEN.format(3))
    e.politica = PoliticaPush(entorno="produccion")
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)

    avisos = e.avisos(familia)
    assert avisos[(familia.admin.id, "push")] == ("omitida", "sin_destino")
    assert avisos[(familia.admin.id, "correo")] == ("enviada", None)
    assert e.push.enviados == []
    # El correo llegó: la alerta queda notificada igual
    assert e.estado_alerta(avisado) == ("notificada", True)


def test_en_pruebas_el_push_sale_como_antes(entorno_avisos: EntornoAvisos) -> None:
    e = entorno_avisos
    familia = e.familia()
    e.dispositivo(familia.admin, TOKEN.format(4))
    avisado = e.avisar(familia)

    assert isinstance(e.consumir(avisado), Hecho)

    assert e.avisos(familia)[(familia.admin.id, "push")] == ("enviada", None)
    assert [x.push_token for x in e.push.enviados] == [TOKEN.format(4)]
