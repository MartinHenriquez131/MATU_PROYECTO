"""MATU-26 · Política de privacidad v0.9.

Criterio 3: su versión se publica en la configuración como POLITICA_VERSION, en formato
MAYOR.MENOR. Esta historia no tiene RF: su traza es la Ley 21.719.

MATU-07 (RF-01) la hace obligatoria fuera del ambiente de pruebas: sin ella la API no arranca.

Las pruebas leen solo del entorno que fijan, nunca del .env del equipo.
"""

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.core import config
from app.core.config import POLITICA_VERSION_FABRICA, Configuracion
from app.main import crear_app


class ConfiguracionSinArchivo(Configuracion):
    # Hereda todo de Configuracion menos el .env, para no depender del archivo local
    model_config = SettingsConfigDict(env_file=None)


@pytest.fixture(autouse=True)
def _sin_env(configuracion_sin_env: None) -> None:
    """Ninguna prueba de este archivo ve el .env del equipo, ni el copiado a os.environ."""


def cargar() -> Configuracion:
    return ConfiguracionSinArchivo()


def test_politica_version_se_lee_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLITICA_VERSION", "0.9")

    assert cargar().politica_version == "0.9"


def test_politica_version_acepta_varios_digitos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLITICA_VERSION", "10.12")

    assert cargar().politica_version == "10.12"


# --- MATU-07 · POLITICA_VERSION obligatoria fuera del ambiente de pruebas ---------------------------


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("entorno", ["local", "produccion"])
def test_sin_politica_version_fuera_de_pruebas_no_carga(monkeypatch: pytest.MonkeyPatch, entorno: str) -> None:
    monkeypatch.setenv("ENTORNO", entorno)
    monkeypatch.delenv("POLITICA_VERSION", raising=False)

    with pytest.raises(ValidationError) as error:
        cargar()

    assert "Falta POLITICA_VERSION" in str(error.value)


@pytest.mark.rf("RF-01")
def test_sin_politica_version_en_pruebas_usa_la_version_de_fabrica(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTORNO", "pruebas")
    monkeypatch.delenv("POLITICA_VERSION", raising=False)

    assert cargar().politica_version == POLITICA_VERSION_FABRICA == "0.0"


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("entorno", ["local", "pruebas", "produccion"])
def test_politica_version_definida_manda_en_todo_entorno(monkeypatch: pytest.MonkeyPatch, entorno: str) -> None:
    monkeypatch.setenv("ENTORNO", entorno)
    monkeypatch.setenv("POLITICA_VERSION", "0.9")

    assert cargar().politica_version == "0.9"


@pytest.mark.rf("RF-01")
def test_sin_politica_version_la_api_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    # app.main crea la app al importarse con obtener_configuracion(): si la configuración no carga,
    # uvicorn no levanta. Se prueba con la configuración real, sin el .env del equipo.
    monkeypatch.setattr(config, "Configuracion", ConfiguracionSinArchivo)
    monkeypatch.setenv("ENTORNO", "produccion")
    monkeypatch.delenv("POLITICA_VERSION", raising=False)
    config.obtener_configuracion.cache_clear()
    try:
        with pytest.raises(ValidationError) as error:
            crear_app()
        assert "Falta POLITICA_VERSION" in str(error.value)
    finally:
        config.obtener_configuracion.cache_clear()


@pytest.mark.parametrize(
    "valor",
    ["v1", "0.9.1", "1", "0.", ".9", "0,9", "0.9 ", " 0.9", "0.9\n", "a.b", "", "٠.٩"],
)
def test_politica_version_con_otro_formato_no_carga(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    monkeypatch.setenv("POLITICA_VERSION", valor)

    with pytest.raises(ValidationError) as error:
        cargar()

    assert [e["loc"] for e in error.value.errors()] == [("politica_version",)]


# --- MATU-05a · JWT_CLAVE ---------------------------------------------------------------------


def test_jwt_clave_se_lee_del_entorno_como_secreto(monkeypatch: pytest.MonkeyPatch) -> None:
    clave = "k" * 64
    monkeypatch.setenv("JWT_CLAVE", clave)

    configuracion = cargar()

    assert configuracion.jwt_clave is not None
    assert configuracion.jwt_clave.get_secret_value() == clave
    # Al imprimir la configuración, la clave no aparece
    assert clave not in repr(configuracion)


@pytest.mark.parametrize("valor", [None, ""])
def test_jwt_clave_ausente_o_vacia_carga_como_none(monkeypatch: pytest.MonkeyPatch, valor: str | None) -> None:
    if valor is None:
        monkeypatch.delenv("JWT_CLAVE", raising=False)
    else:
        monkeypatch.setenv("JWT_CLAVE", valor)

    assert cargar().jwt_clave is None


def test_jwt_clave_corta_no_carga(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_CLAVE", "k" * 31)

    with pytest.raises(ValidationError) as error:
        cargar()

    assert [e["loc"] for e in error.value.errors()] == [("jwt_clave",)]
    assert "k" * 31 not in str(error.value)


def test_pepper_email_corto_no_aparece_en_el_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEPPER_EMAIL", "p" * 31)

    with pytest.raises(ValidationError) as error:
        cargar()

    assert [e["loc"] for e in error.value.errors()] == [("pepper_email",)]
    assert "p" * 31 not in str(error.value)


def test_jwt_clave_igual_a_pepper_email_no_carga(monkeypatch: pytest.MonkeyPatch) -> None:
    clave = "m" * 64
    monkeypatch.setenv("JWT_CLAVE", clave)
    monkeypatch.setenv("PEPPER_EMAIL", clave)

    with pytest.raises(ValidationError) as error:
        cargar()

    assert "deben ser claves distintas" in str(error.value)
    assert clave not in str(error.value)


def test_jwt_clave_distinta_de_pepper_email_carga(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_CLAVE", "k" * 64)
    monkeypatch.setenv("PEPPER_EMAIL", "p" * 64)

    configuracion = cargar()

    assert configuracion.jwt_clave is not None
    assert configuracion.pepper_email is not None
    assert configuracion.jwt_clave.get_secret_value() != configuracion.pepper_email.get_secret_value()
