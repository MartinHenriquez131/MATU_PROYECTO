"""MATU-79 · Los errores de la base no copian los parámetros de la consulta (hide_parameters=True).

Sin hide_parameters, el texto de un DBAPIError de SQLAlchemy termina en «[parameters: {...}]» con los valores enviados:
un email, un nombre de pila, una huella. Ese texto llega a un log en cuanto alguien registra la excepción. Las dos
primeras pruebas miran la opción de cada engine sin conectarse. Las últimas provocan un error real en PostgreSQL con un
valor sintético y verifican que no aparece ni en el texto de la excepción ni en la línea de log JSON de la API.
"""

import io
import logging
from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import tareas
from app.core import db
from app.core.config import obtener_configuracion
from app.core.logs import FormateadorJSON
from tests.base_datos import requiere_base

# Sin contraseña: detect-secrets no la confunde con un secreto, y crear el engine no conecta
URL_SINTETICA = "postgresql+psycopg://u@db.invalid/x"
VALOR_SINTETICO = "parametro-sintetico-matu79@example.invalid"


@pytest.fixture
def engine_de_la_api_sin_cache() -> Iterator[None]:
    db.obtener_engine.cache_clear()
    yield
    db.obtener_engine.cache_clear()


def test_el_engine_de_la_api_oculta_los_parametros(
    monkeypatch: pytest.MonkeyPatch, engine_de_la_api_sin_cache: None
) -> None:
    config = obtener_configuracion().model_copy(update={"database_url": SecretStr(URL_SINTETICA)})
    monkeypatch.setattr(db, "obtener_configuracion", lambda: config)
    assert db.obtener_engine().hide_parameters is True


def test_los_engines_de_las_tareas_ocultan_los_parametros() -> None:
    # matu_app, matu_scheduler y matu_publisher salen todos de _fabrica
    engine = tareas._fabrica(URL_SINTETICA, obtener_configuracion()).kw["bind"]
    assert engine.hide_parameters is True


def _provocar_error(sesion: Session) -> DBAPIError:
    with pytest.raises(DBAPIError) as error:
        # División por cero: PostgreSQL no repite el valor en su mensaje (una conversión inválida sí lo haría), así que
        # si el valor aparece, lo agregó SQLAlchemy con «[parameters: ...]»
        sesion.execute(text("SELECT CAST(:valor AS text), 1 / 0"), {"valor": VALOR_SINTETICO})
    sesion.rollback()
    return error.value


def _linea_de_log(error: DBAPIError) -> str:
    # El peor caso: alguien registra la excepción con su texto en el mensaje y con la traza
    salida = io.StringIO()
    manejador = logging.StreamHandler(salida)
    manejador.setFormatter(FormateadorJSON())
    registro = logging.getLogger("matu.prueba_parametros")
    registro.addHandler(manejador)
    registro.propagate = False
    try:
        registro.error("falló la consulta: %s", error, exc_info=error)
    finally:
        registro.removeHandler(manejador)
    return salida.getvalue()


@requiere_base
def test_un_error_de_la_api_no_lleva_el_parametro_al_log(engine_de_la_api_sin_cache: None) -> None:
    with Session(db.obtener_engine()) as sesion:
        error = _provocar_error(sesion)
    # 22012: division_by_zero. Se compara el código y no el texto, que depende del idioma de PostgreSQL
    assert getattr(error.orig, "sqlstate", None) == "22012", "debe ser la división por cero, no otro error"
    assert VALOR_SINTETICO not in str(error)
    assert "hidden due to hide_parameters" in str(error)
    assert VALOR_SINTETICO not in _linea_de_log(error)


@requiere_base
def test_un_error_de_las_tareas_no_lleva_el_parametro_al_log() -> None:
    fabrica = tareas.fabrica_tareas(obtener_configuracion())
    with fabrica() as sesion:
        error = _provocar_error(sesion)
    assert VALOR_SINTETICO not in str(error)
    assert VALOR_SINTETICO not in _linea_de_log(error)
