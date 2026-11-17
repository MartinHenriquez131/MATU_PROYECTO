"""MATU-80 · Recorrido 1 de MATU-64: crear la cuenta, la persona cuidada y su autorización, y llenar la ficha.

Todo por la API, como en la pantalla: la cuenta con la política aceptada, el grupo, la persona cuidada con la
autorización de la titular para su ficha, y los tres campos de la ficha (su día, si se altera y a quién llamar).
"""

import pytest

from tests.base_datos import requiere_base
from tests.e2e.conftest import Recorrido

pytestmark = [
    requiere_base,
    pytest.mark.e2e,
    pytest.mark.rf("RF-37"),
    pytest.mark.rf("RF-01"),
    pytest.mark.rf("RF-02"),
]

TEXTOS = {
    "rutina": "Toma desayuno a las 08:30 y duerme siesta después de almuerzo",
    "manejo_situaciones": "Si se inquieta, ayuda poner su música y hablarle despacio",
    "red_apoyo": "Su hijo Tomás Ficticio: +56 9 5555 0101",
}


def test_recorrido_alta_y_ficha(recorrido: Recorrido) -> None:
    r = recorrido

    # Dado una cuidadora que crea su cuenta, entra y arma su grupo
    cuenta = r.crear_cuenta()
    entrada = r.iam.iniciar_sesion(email=cuenta.email, contrasena=cuenta.contrasena)
    assert entrada.status_code == 200, entrada.text
    grupo_id = r.crear_grupo(cuenta)

    # Cuando da de alta a la persona cuidada, que como titular autoriza el uso de su ficha
    alta = r.dar_de_alta(cuenta, grupo_id)

    # Entonces la persona queda con su autorización vigente para la ficha
    assert alta.status_code == 201, alta.text
    persona_id = alta.json()["id"]
    consentimiento = alta.json()["consentimiento"]
    assert (consentimiento["finalidad"], consentimiento["calidad_otorgante"]) == ("plan_cuidado", "titular")
    cabeceras = r.cabeceras(cuenta, grupo_id)
    personas = r.iam.cliente.get(f"/v1/grupos/{grupo_id}/personas-cuidadas", headers=cabeceras)
    assert personas.status_code == 200, personas.text
    assert [p["id"] for p in personas.json()] == [persona_id]
    autorizaciones = r.iam.cliente.get(f"/v1/personas-cuidadas/{persona_id}/consentimientos", headers=cabeceras)
    assert autorizaciones.status_code == 200, autorizaciones.text
    assert "plan_cuidado" in autorizaciones.text

    # Y la ficha nace vacía
    ruta_ficha = f"/v1/personas-cuidadas/{persona_id}/plan/ficha"
    vacia = r.iam.cliente.get(ruta_ficha, headers=cabeceras)
    assert vacia.status_code == 200, vacia.text
    assert {c: v["texto"] for c, v in vacia.json()["campos"].items()} == dict.fromkeys(TEXTOS)

    # Cuando llena los tres campos, cada uno por primera vez (If-None-Match: *)
    for campo, texto in TEXTOS.items():
        guardado = r.iam.cliente.put(
            f"{ruta_ficha}/{campo}", json={"texto": texto}, headers={**cabeceras, "If-None-Match": "*"}
        )
        assert guardado.status_code == 201, guardado.text
        assert guardado.json()["texto"] == texto

    # Entonces la ficha trae los tres campos, completa
    ficha = r.iam.cliente.get(ruta_ficha, headers=cabeceras)
    assert ficha.status_code == 200, ficha.text
    assert {c: v["texto"] for c, v in ficha.json()["campos"].items()} == TEXTOS
    assert all(v["etag"] and v["actualizado_por"]["id"] == str(cuenta.id) for v in ficha.json()["campos"].values())
    assert ficha.json()["completitud"] == 100

    # Y ni la contraseña ni el texto de la ficha llegan a los logs
    logs = r.logs()
    assert logs.strip()
    assert cuenta.contrasena is not None and cuenta.contrasena not in logs
    assert all(texto not in logs for texto in TEXTOS.values())
