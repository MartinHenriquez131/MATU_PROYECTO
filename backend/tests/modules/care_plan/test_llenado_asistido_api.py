"""MATU-42 · Llenado asistido (RF-42, decisión 313) y el autor que ya no está (decisión 309), contra PostgreSQL.

Rosa entra al grupo con una invitación como cuidadora y escribe «Su día»: la ficha la muestra como autora y plan.editar
lleva su cuenta. Sin ruta nueva y sin en_nombre_de. Cuando sale, la ficha la muestra como alguien que ya no está.
Solo datos sintéticos.
"""

import re
import secrets
import uuid

import pytest

from app.modules.care_circle.api.dependencias_grupo import obtener_pepper_codigo
from tests.base_datos import requiere_base

# reloj_fijo parte de la hora real (decisión 340)
from tests.modules.care_circle.test_invitaciones_api import reloj_fijo  # noqa: F401
from tests.modules.care_plan.conftest import EntornoFicha

pytestmark = [requiere_base, pytest.mark.rf("RF-42")]

URL = re.compile(r"^https://[^/#]+/invitacion#([A-Za-z0-9_-]{43})$")
SU_DIA = "Se levanta a las 8, toma desayuno y sale a caminar a la plaza"


def test_quien_entra_con_una_invitacion_completa_la_ficha_con_su_cuenta(entorno_ficha: EntornoFicha) -> None:
    pepper = secrets.token_bytes(32)
    entorno_ficha.app.dependency_overrides[obtener_pepper_codigo] = lambda: pepper
    cliente = entorno_ficha.iam.cliente
    familia = entorno_ficha.familia()
    grupo = familia.grupo.id
    creada = cliente.post(f"/v1/grupos/{grupo}/invitaciones", json={"rol": "cuidador"},
                          headers=entorno_ficha._cabeceras(familia.admin, grupo))
    assert creada.status_code == 201, creada.text
    coincide = URL.match(creada.json()["url"])
    assert coincide
    rosa = entorno_ficha.fabrica.usuario(nombre="Rosa Pérez")
    union = cliente.post("/v1/invitaciones/aceptacion",
                         json={"token": coincide.group(1), "codigo": creada.json()["codigo"]},
                         headers=entorno_ficha._cabeceras(rosa, None))
    assert union.status_code == 201, union.text

    # Rosa escribe «Su día» con la ruta que ya existe
    escrita = entorno_ficha.escribir(rosa, grupo, familia.persona.id, "rutina", {"texto": SU_DIA})
    assert escrita.status_code in (200, 201), escrita.text
    assert escrita.json()["actualizado_por"] == {"id": str(rosa.id), "nombre": rosa.nombre, "autor_activo": True}
    [evento] = entorno_ficha.auditoria.ediciones
    assert evento.usuario_id == rosa.id and evento.campo == "rutina"

    # La admin ve a Rosa como autora
    ficha = entorno_ficha.leer(familia.admin, grupo, familia.persona.id)
    assert ficha.status_code == 200
    assert ficha.json()["campos"]["rutina"]["actualizado_por"] == {
        "id": str(rosa.id), "nombre": rosa.nombre, "autor_activo": True}

    # Rosa sale: queda como alguien que ya no está, con su id y sin nombre (decisión 309)
    salida = cliente.post(f"/v1/grupos/{grupo}/salida", headers=entorno_ficha._cabeceras(rosa, grupo))
    assert salida.status_code == 200, salida.text
    ficha = entorno_ficha.leer(familia.admin, grupo, familia.persona.id)
    autor = ficha.json()["campos"]["rutina"]["actualizado_por"]
    assert autor == {"id": str(rosa.id), "nombre": None, "autor_activo": False}
    assert rosa.nombre not in ficha.text
    assert uuid.UUID(autor["id"]) == rosa.id
