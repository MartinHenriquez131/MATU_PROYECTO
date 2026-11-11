"""MATU-61 · La autorización de pedidos (despacho) con la capa 3 apagada y encendida (C2, decisión 217).

Sin importar ordering: estas pruebas corren también en el intérprete sin la capa 3 (tests/test_capa3_desacoplable.py,
FLUJOS). Con la capa 3 apagada, GET …/consentimientos trae dos ítems, despacho no se otorga ni se retira por la ruta,
y borrar a la persona funciona y revoca también una autorización despacho que quedó de cuando estaba encendida, sin
tocar pedidos. Con la capa 3 encendida, tres ítems.
"""

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest

from app.modules.care_circle.api.router_autorizaciones import finalidades_activas
from app.modules.care_circle.domain.declaraciones import huella_declaracion_pedidos
from app.modules.care_circle.domain.personas import CalidadOtorgante, evidencia
from app.modules.care_circle.domain.retiro import finalidades_retirables
from tests.base_datos import DSN, requiere_base
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.conftest import EntornoIam

pytestmark = [pytest.mark.rf("RF-21"), requiere_base]

CONSENTIMIENTOS = "/v1/personas-cuidadas/{}/consentimientos"


@pytest.fixture
def fabrica_despacho(entorno_iam: EntornoIam) -> Iterator[Fabrica]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    try:
        yield fabrica
    finally:
        fabrica.limpiar()


def _cabeceras(entorno: EntornoIam, usuario: UsuarioCreado, familia: FamiliaCreada) -> dict[str, str]:
    assert usuario.contrasena is not None
    token = entorno.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena).json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Grupo-Id": str(familia.grupo.id)}


def _despacho_que_quedo(familia: FamiliaCreada) -> uuid.UUID:
    """Una autorización despacho otorgada cuando la capa 3 estaba encendida."""
    consentimiento = uuid.uuid4()
    calidad = CalidadOtorgante.TITULAR
    datos = evidencia(calidad, "0.11", "despacho", huella_declaracion_pedidos(calidad))
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "INSERT INTO consentimiento (id, grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
            " version_politica, evidencia, otorgado_en) VALUES (%s, %s, %s, %s, 'titular', 'despacho', '0.11',"
            " %s::jsonb, %s)",
            (
                consentimiento,
                familia.grupo.id,
                familia.persona.id,
                familia.admin.id,
                json.dumps(datos),
                datetime.now(UTC),
            ),
        )
    return consentimiento


def test_sin_la_capa_3_son_dos_autorizaciones_y_despacho_no_existe(
    entorno_iam: EntornoIam, fabrica_despacho: Fabrica
) -> None:
    familia = fabrica_despacho.familia()
    cab = _cabeceras(entorno_iam, familia.admin, familia)
    ruta = CONSENTIMIENTOS.format(familia.persona.id)

    estado = entorno_iam.cliente.get(ruta, headers=cab)
    assert [a["finalidad"] for a in estado.json()["autorizaciones"]] == ["plan_cuidado", "consumo"]

    otorgar = entorno_iam.cliente.post(
        ruta,
        headers=cab,
        json={
            "finalidad": "despacho",
            "calidad_otorgante": "titular",
            "huella_declaracion": huella_declaracion_pedidos(CalidadOtorgante.TITULAR),
        },
    )
    assert otorgar.status_code == 422 and otorgar.json()["errores"][0]["campo"] == "finalidad"
    assert entorno_iam.cliente.post(ruta + "/despacho/retiro", headers=cab).status_code == 404


def test_sin_la_capa_3_borrar_a_la_persona_funciona_y_revoca_despacho(
    entorno_iam: EntornoIam, fabrica_despacho: Fabrica
) -> None:
    """C2: el borrado de MATU-72 sigue funcionando sin la capa 3 y no toca pedidos."""
    familia = fabrica_despacho.familia()
    despacho = _despacho_que_quedo(familia)

    borrado = entorno_iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/borrado", headers=_cabeceras(entorno_iam, familia.admin, familia)
    )

    assert borrado.status_code == 200, borrado.text
    assert borrado.json()["autorizaciones_retiradas"] == 2  # plan_cuidado y despacho
    with psycopg.connect(DSN) as cx:
        assert cx.execute("SELECT revocacion_motivo FROM consentimiento WHERE id = %s", (despacho,)).fetchone() == (
            "borrado",
        )


def test_con_la_capa_3_son_tres_autorizaciones(entorno_iam: EntornoIam, fabrica_despacho: Fabrica) -> None:
    entorno_iam.cliente.app.dependency_overrides[finalidades_activas] = lambda: finalidades_retirables(True)  # type: ignore[attr-defined]
    familia = fabrica_despacho.familia()
    cab = _cabeceras(entorno_iam, familia.admin, familia)
    estado = entorno_iam.cliente.get(CONSENTIMIENTOS.format(familia.persona.id), headers=cab).json()
    assert [a["finalidad"] for a in estado["autorizaciones"]] == ["plan_cuidado", "consumo", "despacho"]
    despacho = estado["autorizaciones"][2]
    assert (despacho["estado"], despacho["borrado_en"], despacho["borrada"]) == ("sin_autorizar", None, False)


def test_la_direccion_con_su_precondicion_y_sus_roles(entorno_iam: EntornoIam, fabrica_despacho: Fabrica) -> None:
    """D4, C6 y C8: admin y cuidador, If-Match obligatorio, 404 a pagador y observador, auditada sin contenido."""
    familia = fabrica_despacho.familia()
    ruta = f"/v1/personas-cuidadas/{familia.persona.id}/direccion"
    cab = _cabeceras(entorno_iam, familia.admin, familia)
    cuerpo = {"calle": "Calle de Prueba", "numero": "9", "comuna": "Comuna Sintética"}
    cliente = entorno_iam.cliente

    assert cliente.put(ruta, headers=cab, json=cuerpo).status_code == 428
    viejo = cliente.put(ruta, headers={**cab, "If-Match": '"v9"'}, json=cuerpo)
    assert viejo.status_code == 412 and viejo.json()["actual"]["etag"] == '"v1"'
    assert cliente.put(ruta, headers={**cab, "If-Match": '"v1"'}, json={**cuerpo, "lat": -33.4}).status_code == 422
    for rol in ("pagador", "observador"):
        otro = _cabeceras(entorno_iam, familia.miembros[rol].usuario, familia)
        assert cliente.put(ruta, headers={**otro, "If-Match": '"v1"'}, json=cuerpo).status_code == 404, rol

    cambiada = cliente.put(ruta, headers={**cab, "If-Match": '"v1"'}, json=cuerpo)
    assert cambiada.status_code == 200 and cambiada.headers["ETag"] == '"v2"'
    assert cambiada.headers["Cache-Control"] == "no-store"
    assert cliente.delete(ruta, headers={**cab, "If-Match": '"v2"'}).status_code == 204
    assert cliente.delete(ruta, headers={**cab, "If-Match": '"v2"'}).status_code == 404
    primera = cliente.put(ruta, headers={**cab, "If-None-Match": "*"}, json=cuerpo)
    assert primera.status_code == 200 and primera.json()["etag"] == '"v1"'
    with psycopg.connect(DSN) as cx:
        filas = cx.execute(
            "SELECT entidad, detalle FROM auditoria WHERE accion = 'direccion.cambiar' AND grupo_id = %s",
            (familia.grupo.id,),
        ).fetchall()
    assert filas == [("direccion", None)] * 3
    assert "Calle de Prueba" not in entorno_iam.texto_log()
