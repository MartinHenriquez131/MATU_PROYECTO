"""MATU-39 · GET /v1/grupos dice por grupo si quien consulta ve el plan (decisión 66, RF-38).

admin y cuidador siempre; pagador solo con membresia.puede_ver_plan; observador nunca. La regla
pura se prueba sin base; la lista, contra PostgreSQL real como matu_app.
"""

import uuid

import psycopg
import pytest

from app.modules.care_circle.domain.grupos import ve_el_plan
from tests.base_datos import DSN, requiere_base
from tests.fabricas.sql import insertar_grupo, insertar_membresia
from tests.modules.care_circle.conftest import EntornoGrupo

pytestmark = pytest.mark.rf("RF-38")


@pytest.mark.parametrize(
    ("rol", "permiso", "esperado"),
    [
        ("admin", False, True),
        ("cuidador", False, True),
        ("pagador", True, True),
        ("pagador", False, False),
        ("observador", False, False),
        ("observador", True, False),
        ("relevo", True, False),
    ],
)
def test_regla_ve_el_plan(rol: str, permiso: bool, esperado: bool) -> None:
    assert ve_el_plan(rol, permiso) is esperado


def _grupo_con(entorno: EntornoGrupo, creador: uuid.UUID, miembro: uuid.UUID, rol: str, permiso: bool) -> str:
    grupo_id = uuid.uuid4()
    entorno.grupos.append(grupo_id)
    with psycopg.connect(DSN, autocommit=True) as cx:
        insertar_grupo(cx, grupo_id, "Familia Sintética", creador)
        insertar_membresia(cx, grupo_id, creador, "admin")
        insertar_membresia(cx, grupo_id, miembro, rol, puede_ver_plan=permiso)
    return str(grupo_id)


@requiere_base
@pytest.mark.parametrize(
    ("rol", "permiso", "esperado"),
    [("cuidador", False, True), ("pagador", True, True), ("pagador", False, False), ("observador", False, False)],
)
def test_lista_trae_puede_ver_plan_segun_rol(
    entorno_grupo: EntornoGrupo, rol: str, permiso: bool, esperado: bool
) -> None:
    admin = entorno_grupo.cuenta()
    miembro = entorno_grupo.cuenta()
    grupo = _grupo_con(entorno_grupo, admin.id, miembro.id, rol, permiso)

    del_miembro = entorno_grupo.pedir("/v1/grupos", miembro.token)
    del_admin = entorno_grupo.pedir("/v1/grupos", admin.token)

    assert del_miembro.status_code == 200
    assert del_miembro.json() == [{"id": grupo, "nombre": "Familia Sintética", "rol": rol, "puede_ver_plan": esperado}]
    # El mismo grupo, visto por su admin, da true: el permiso es de quien consulta
    assert del_admin.json()[0]["puede_ver_plan"] is True


@requiere_base
def test_crear_grupo_responde_puede_ver_plan_true(entorno_grupo: EntornoGrupo) -> None:
    admin = entorno_grupo.cuenta()

    respuesta = entorno_grupo.crear_grupo(admin.token, {"nombre": "Familia Sintética"})

    assert respuesta.status_code == 201
    assert respuesta.json()["puede_ver_plan"] is True


def test_contrato_declara_puede_ver_plan(entorno_grupo: EntornoGrupo) -> None:
    esquemas = entorno_grupo.iam.cliente.get("/openapi.json").json()["components"]["schemas"]
    grupo = esquemas["GrupoRespuesta"]
    assert "puede_ver_plan" in grupo["required"]
    assert grupo["properties"]["puede_ver_plan"]["type"] == "boolean"
