"""MATU-20 · Revocar un acceso de relevo, por la API y contra PostgreSQL (RF-07).

Usa el entorno de MATU-19 (test_abrir_relevo_api): la familia comparte por su ruta y el relevo usa un
cliente https (base_url "https://testserver"), porque la cookie __Secure-matu-relevo es Secure.
Solo datos sintéticos.
"""

import uuid
from datetime import timedelta
from typing import Any

import pytest

from tests.base_datos import requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.care_plan import test_abrir_relevo_api as abrir
from tests.modules.care_plan.test_abrir_relevo_api import (
    PROBLEMA,
    EntornoAbrir,
    _problema,
    _revocar_consentimientos,
    _todas,
    _una,
)

# Las fixtures de MATU-19: el reloj desde la hora real, el pepper y las sesiones en memoria
entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.rf("RF-07")]

RUTA_ACCESO = "/v1/accesos-relevo/{}"
RUTA_ACCESOS = "/v1/personas-cuidadas/{}/plan/accesos-relevo"


def _revocar(entorno: EntornoAbrir, usuario: UsuarioCreado | None, grupo: Any, acceso_id: Any) -> Any:
    return entorno.ficha.iam.cliente.delete(
        RUTA_ACCESO.format(acceso_id), headers=entorno.ficha._cabeceras(usuario, grupo)
    )


def _revocados(acceso_id: uuid.UUID) -> tuple[Any, Any]:
    acceso = _una("SELECT revocado_en FROM acceso_relevo WHERE id = %s", acceso_id)
    indice = _una("SELECT revocado_en FROM indice_token WHERE referencia_id = %s", acceso_id)
    assert acceso is not None and indice is not None  # revocar no borra indice_token
    return acceso[0], indice[0]


def _auditoria_revocar(acceso_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return _todas(
        "SELECT actor_tipo, actor_ref, row_to_json(a)::text FROM auditoria a"
        " WHERE accion = 'relevo.revocar' AND entidad_id = %s",
        acceso_id,
    )


def _sin_cuerpo_204(respuesta: Any) -> None:
    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    assert respuesta.headers["cache-control"] == "no-store"


def _intacto(acceso_id: uuid.UUID) -> None:
    assert _revocados(acceso_id) == (None, None)
    assert _auditoria_revocar(acceso_id) == []


# --- Las dos pruebas del backlog -------------------------------------------------------------------------


def test_revocacion_efecto_inmediato(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    assert entorno.abrir(token, pin).status_code == 200

    _sin_cuerpo_204(_revocar(entorno, familia.admin, familia.grupo.id, acceso_id))

    # La misma cookie ya no abre, y el mismo enlace tampoco se presenta ni se canjea
    _problema(entorno.leer(), 410, "relevo-revocado")
    _problema(entorno.canjear(token, pin), 410, "relevo-revocado")
    _problema(entorno.presentar(token), 410, "relevo-revocado")


def test_recorrido_relevo(entorno: EntornoAbrir) -> None:
    """e2e: la familia escribe la ficha por su API, comparte, el relevo abre y la familia revoca."""
    familia = entorno.ficha.familia()
    for campo, texto in (("rutina", "Almuerza a las 13:00 en el comedor"), ("red_apoyo", "Sobrino: Tomás")):
        escrita = entorno.ficha.escribir(familia.admin, familia.grupo.id, familia.persona.id, campo, {"texto": texto})
        assert escrita.status_code in (200, 201), escrita.text
    acceso_id, token, pin = entorno.compartir(familia, campos=["rutina"])
    assert str(entorno.relevo.base_url) == "https://testserver"

    assert entorno.presentar(token).status_code == 200
    assert entorno.canjear(token, pin).status_code == 204
    ficha = entorno.leer()
    assert ficha.status_code == 200
    assert ficha.json()["campos"] == {"rutina": {"texto": "Almuerza a las 13:00 en el comedor"}}

    cuidador = familia.miembros["cuidador"].usuario
    _sin_cuerpo_204(_revocar(entorno, cuidador, familia.grupo.id, acceso_id))
    _problema(entorno.leer(), 410, "relevo-revocado")


# --- Estado, coherencia e idempotencia ---------------------------------------------------------------------


def test_coherencia_acceso_e_indice(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, _, _ = entorno.compartir(familia)
    _sin_cuerpo_204(_revocar(entorno, familia.admin, familia.grupo.id, acceso_id))
    acceso, indice = _revocados(acceso_id)
    assert acceso is not None and acceso == indice == entorno.reloj.ahora()


def test_idempotente_conserva_el_primer_revocado_en(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, _, _ = entorno.compartir(familia)
    _sin_cuerpo_204(_revocar(entorno, familia.admin, familia.grupo.id, acceso_id))
    primero = _revocados(acceso_id)

    entorno.reloj.avanzar(timedelta(minutes=10))
    _sin_cuerpo_204(_revocar(entorno, familia.miembros["cuidador"].usuario, familia.grupo.id, acceso_id))

    assert _revocados(acceso_id) == primero
    filas = _auditoria_revocar(acceso_id)
    assert len(filas) == 1
    actor_tipo, actor_ref, fila = filas[0]
    assert actor_tipo == "usuario" and actor_ref == familia.admin.id
    assert "Rosa" not in fila and "5555" not in fila  # ni el nombre ni el teléfono del relevo


def test_revocar_vencido_no_fija_revocado_en(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    # Cinco minutos: menos que la vida del access token de la familia
    expira = entorno.reloj.ahora() + timedelta(minutes=5)
    acceso_id, token, pin = entorno.compartir(familia, expira_en=expira.isoformat())
    entorno.reloj.avanzar(timedelta(minutes=5))  # vence en el instante exacto, según el Reloj

    _sin_cuerpo_204(_revocar(entorno, familia.admin, familia.grupo.id, acceso_id))

    _intacto(acceso_id)
    _problema(entorno.canjear(token, pin), 410, "relevo-vencido")


def test_lista_muestra_revocado(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    revocado_id, _, _ = entorno.compartir(familia)
    vigente_id, _, _ = entorno.compartir(familia)
    _sin_cuerpo_204(_revocar(entorno, familia.admin, familia.grupo.id, revocado_id))

    lista = entorno.ficha.iam.cliente.get(
        RUTA_ACCESOS.format(familia.persona.id), headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id)
    )
    assert lista.status_code == 200
    estados = {i["id"]: (i["estado"], i["revocado_en"]) for i in lista.json()["items"]}
    assert estados[str(vigente_id)] == ("vigente", None)
    assert estados[str(revocado_id)][0] == "revocado" and estados[str(revocado_id)][1] is not None


def test_revoca_sin_consentimiento_vigente(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, _, _ = entorno.compartir(familia)
    _revocar_consentimientos(familia)
    _sin_cuerpo_204(_revocar(entorno, familia.admin, familia.grupo.id, acceso_id))
    assert _revocados(acceso_id)[0] is not None


# --- Quién revoca y qué responde -----------------------------------------------------------------------


@pytest.mark.parametrize("etiqueta", ["pagador", "pagador_con_plan", "observador"])
def test_otros_roles_404(entorno: EntornoAbrir, etiqueta: str) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    respuesta = _revocar(entorno, familia.miembros[etiqueta].usuario, familia.grupo.id, acceso_id)
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.json()["type"] == "/errores/no-encontrado"
    _intacto(acceso_id)
    assert entorno.abrir(token, pin).status_code == 200


def test_otro_grupo_e_id_invalido_404(entorno: EntornoAbrir) -> None:
    a: FamiliaCreada = entorno.familia_con_ficha()
    b: FamiliaCreada = entorno.familia_con_ficha()
    acceso_b, _, _ = entorno.compartir(b)
    for respuesta in (
        _revocar(entorno, a.admin, a.grupo.id, acceso_b),
        _revocar(entorno, a.admin, b.grupo.id, acceso_b),
        _revocar(entorno, a.admin, a.grupo.id, "no-es-uuid"),
        _revocar(entorno, a.admin, a.grupo.id, uuid.uuid4()),
        _revocar(entorno, a.admin, None, acceso_b),
    ):
        assert respuesta.status_code == 404, respuesta.text
        assert respuesta.headers["content-type"] == PROBLEMA
    _intacto(acceso_b)


def test_sin_token_401(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, _, _ = entorno.compartir(familia)
    respuesta = _revocar(entorno, None, familia.grupo.id, acceso_id)
    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"] == PROBLEMA
    _intacto(acceso_id)


def test_logs_sin_datos_sensibles(entorno: EntornoAbrir, caplog: pytest.LogCaptureFixture) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    with caplog.at_level("DEBUG"):
        _sin_cuerpo_204(_revocar(entorno, familia.admin, familia.grupo.id, acceso_id))
    texto = caplog.text
    assert token not in texto and "Rosa" not in texto and "5555" not in texto
