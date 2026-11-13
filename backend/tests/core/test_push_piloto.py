"""MATU-107 · C14 del piloto: los avisos push solo se activan en las cuentas del equipo (hallazgo 55-H2). Sin base.

PUSH_CUENTAS_PERMITIDAS se lee con pydantic-settings y solo la consulta app/core/push_piloto.py. Falla cerrada fuera de
local y pruebas (C-107-3), nunca aparece en el repr, un error ni un log (C-107-6 y C-107-7), y la tarea de avisos arma
la segunda barrera con ella (C-107-5). Los UUID son sintéticos y se generan en cada prueba.
"""

import io
import json
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core import config
from app.core.config import ENTORNOS_PUSH_SIN_LISTA, Configuracion
from app.core.push_piloto import PoliticaPush, politica_push
from app.main import crear_app
from app.modules.consumption.events import QUIEBRE_PROXIMO
from app.modules.notifications.infrastructure import tarea_avisos
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-39")


@pytest.fixture(autouse=True)
def _sin_env(configuracion_sin_env: None) -> None:
    """Ninguna prueba de este archivo ve el .env del equipo, ni el copiado a os.environ."""


def _cargar(monkeypatch: pytest.MonkeyPatch, entorno: str, cuentas: str | None) -> Configuracion:
    monkeypatch.setenv("ENTORNO", entorno)
    monkeypatch.setenv("POLITICA_VERSION", "0.18")
    if cuentas is not None:
        monkeypatch.setenv("PUSH_CUENTAS_PERMITIDAS", cuentas)
    return Configuracion()


# --- La variable (C-107-3 y C-107-6) --------------------------------------------------------------------------------


@pytest.mark.parametrize("cuentas", [None, "", "   ", " , ,"])
def test_ausente_o_vacia_es_la_lista_vacia(monkeypatch: pytest.MonkeyPatch, cuentas: str | None) -> None:
    assert _cargar(monkeypatch, "staging", cuentas).push_cuentas_permitidas == frozenset()


def test_se_lee_separada_por_comas(monkeypatch: pytest.MonkeyPatch) -> None:
    uno, dos = uuid.uuid4(), uuid.uuid4()
    leida = _cargar(monkeypatch, "staging", f" {uno},{dos} ,").push_cuentas_permitidas
    assert leida == frozenset({uno, dos})


@pytest.mark.parametrize("entorno", ["staging", "produccion", "pruebas"])
def test_una_entrada_que_no_es_uuid_impide_cargar_sin_mostrar_el_valor(
    monkeypatch: pytest.MonkeyPatch, entorno: str
) -> None:
    valida = uuid.uuid4()
    invalida = f"no-es-uuid-{uuid.uuid4().hex[:8]}"
    with pytest.raises(ValidationError) as error:
        _cargar(monkeypatch, entorno, f"{valida},{invalida}")
    mensaje = str(error.value)
    assert "PUSH_CUENTAS_PERMITIDAS" in mensaje
    assert invalida not in mensaje and str(valida) not in mensaje


def test_la_lista_no_aparece_en_el_repr_de_la_configuracion(monkeypatch: pytest.MonkeyPatch) -> None:
    cuenta = uuid.uuid4()
    cargada = _cargar(monkeypatch, "staging", str(cuenta))
    assert cuenta in cargada.push_cuentas_permitidas
    assert str(cuenta) not in repr(cargada) and str(cuenta) not in str(cargada)


# --- La regla (C-107-1 a C-107-3) -----------------------------------------------------------------------------------


@pytest.mark.parametrize("entorno", ["staging", "produccion"])
def test_fuera_de_local_y_pruebas_falla_cerrada(monkeypatch: pytest.MonkeyPatch, entorno: str) -> None:
    dentro, fuera = uuid.uuid4(), uuid.uuid4()
    assert not PoliticaPush.desde(_cargar(monkeypatch, entorno, None)).permite(fuera)
    assert not PoliticaPush.desde(_cargar(monkeypatch, entorno, "")).permite(fuera)
    politica = PoliticaPush.desde(_cargar(monkeypatch, entorno, str(dentro)))
    assert politica.permite(dentro) and not politica.permite(fuera)


@pytest.mark.parametrize("entorno", ["local", "pruebas"])
def test_en_local_y_pruebas_toda_cuenta_puede(monkeypatch: pytest.MonkeyPatch, entorno: str) -> None:
    # Sin cambios respecto de MATU-55, aunque la lista exista y no incluya a la cuenta
    politica = PoliticaPush.desde(_cargar(monkeypatch, entorno, str(uuid.uuid4())))
    assert politica.permite(uuid.uuid4())
    assert ENTORNOS_PUSH_SIN_LISTA == frozenset({"local", "pruebas"})


def test_un_entorno_desconocido_no_deja_pasar() -> None:
    # La regla es una lista permitida: un valor nuevo de ENTORNO queda fuera
    cuenta = uuid.uuid4()
    assert not PoliticaPush(entorno="demo").permite(cuenta)
    assert not PoliticaPush(entorno="Pruebas").permite(cuenta)


def test_la_politica_no_muestra_la_lista() -> None:
    cuenta = uuid.uuid4()
    politica = PoliticaPush(entorno="staging", permitidas=frozenset({cuenta}))
    assert repr(politica) == "PoliticaPush()" and str(cuenta) not in str(politica)


def test_la_dependencia_de_la_api_lee_la_configuracion_vigente(monkeypatch: pytest.MonkeyPatch) -> None:
    cuenta = uuid.uuid4()
    monkeypatch.setenv("ENTORNO", "staging")
    monkeypatch.setenv("POLITICA_VERSION", "0.18")
    monkeypatch.setenv("PUSH_CUENTAS_PERMITIDAS", str(cuenta))
    config.obtener_configuracion.cache_clear()
    try:
        politica = politica_push()
        assert politica.permite(cuenta) and not politica.permite(uuid.uuid4())
    finally:
        config.obtener_configuracion.cache_clear()


# --- La segunda barrera la arma la tarea (C-107-5) -------------------------------------------------------------------


def test_la_tarea_de_avisos_arma_el_consumidor_con_la_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    dentro, fuera = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setenv("ENVIADOR_AVISOS", "simulado")
    cargada = _cargar(monkeypatch, "staging", str(dentro))
    mapa = tarea_avisos.consumidores(cargada, None, RelojFijo(datetime.now(UTC)))  # type: ignore[arg-type]
    assert mapa is not None
    [consumidor] = mapa[QUIEBRE_PROXIMO]
    permitido = consumidor._push_permitido  # type: ignore[attr-defined]
    assert permitido(dentro) and not permitido(fuera)


# --- El arranque (C-107-7) ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("entorno", "avisa"), [("staging", True), ("produccion", True), ("pruebas", False)])
def test_el_arranque_avisa_sin_valores(monkeypatch: pytest.MonkeyPatch, entorno: str, avisa: bool) -> None:
    cuenta = uuid.uuid4()
    monkeypatch.setenv("ENTORNO", entorno)
    monkeypatch.setenv("POLITICA_VERSION", "0.18")
    monkeypatch.setenv("PUSH_CUENTAS_PERMITIDAS", str(cuenta))
    config.obtener_configuracion.cache_clear()
    salida = io.StringIO()
    try:
        crear_app(stream_logs=salida)
    finally:
        config.obtener_configuracion.cache_clear()

    texto = salida.getvalue()
    lineas = [json.loads(linea) for linea in texto.splitlines() if linea.strip()]
    avisos = [(x["nivel"], x["mensaje"]) for x in lineas if x["logger"] == "matu.push_piloto"]
    esperado = [("WARNING", "avisos push del piloto: solo las cuentas de PUSH_CUENTAS_PERMITIDAS pueden activarlos")]
    assert avisos == (esperado if avisa else [])
    assert str(cuenta) not in texto and cuenta.hex not in texto
