"""MATU-80 · Recorrido 2 de MATU-64: compartir la ficha con un relevo con PIN, abrirla y cortar el acceso.

Es test_recorrido_relevo de MATU-20 (backlog, RF-07), que vivía en tests/modules/care_plan/test_revocar_relevo_api.py
y se movió aquí para que los seis recorridos queden juntos. Usa el entorno de MATU-19 (test_abrir_relevo_api): el
relevo entra con otro cliente https, porque la cookie __Secure-matu-relevo es Secure, y el reloj parte de la hora
real, como en ese entorno. Solo datos sintéticos.
"""

import pytest

from tests.base_datos import requiere_base
from tests.modules.care_plan import test_abrir_relevo_api as abrir
from tests.modules.care_plan.conftest import entorno_ficha  # noqa: F401
from tests.modules.care_plan.test_abrir_relevo_api import EntornoAbrir, _problema
from tests.modules.care_plan.test_revocar_relevo_api import _revocar, _sin_cuerpo_204

# Las fixtures de MATU-19: el reloj desde la hora real, el pepper y las sesiones en memoria
entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.e2e, pytest.mark.rf("RF-05"), pytest.mark.rf("RF-06"), pytest.mark.rf("RF-07")]


def test_recorrido_relevo(entorno: EntornoAbrir) -> None:
    """e2e: la familia escribe la ficha por su API, comparte, el relevo abre y la familia revoca."""
    familia = entorno.ficha.familia()
    for campo, texto in (("rutina", "Almuerza a las 13:00 en el comedor"), ("red_apoyo", "Sobrino: Tomás")):
        escrita = entorno.ficha.escribir(familia.admin, familia.grupo.id, familia.persona.id, campo, {"texto": texto})
        assert escrita.status_code == 201, escrita.text  # primera escritura de cada campo
    # MATU-50: un acceso nuevo comparte siempre los tres campos base
    acceso_id, token, pin = entorno.compartir(familia, campos_anteriores=None)
    assert str(entorno.relevo.base_url) == "https://testserver"

    assert entorno.presentar(token).status_code == 200
    assert entorno.canjear(token, pin).status_code == 204
    ficha = entorno.leer()
    assert ficha.status_code == 200
    assert ficha.json()["campos"] == {
        "rutina": {"texto": "Almuerza a las 13:00 en el comedor"},
        "manejo_situaciones": {"texto": None},
        "red_apoyo": {"texto": "Sobrino: Tomás"},
    }

    cuidador = familia.miembros["cuidador"].usuario
    _sin_cuerpo_204(_revocar(entorno, cuidador, familia.grupo.id, acceso_id))
    _problema(entorno.leer(), 410, "relevo-revocado")
