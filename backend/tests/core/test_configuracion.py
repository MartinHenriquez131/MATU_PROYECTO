"""MATU-26 · Política de privacidad v0.9.

Criterio 3: su versión se publica en la configuración como POLITICA_VERSION, en formato
MAYOR.MENOR. Esta historia no tiene RF: su traza es la Ley 21.719.

Las pruebas leen solo del entorno que fijan, nunca del .env del equipo.
"""

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import Configuracion


class ConfiguracionSinArchivo(Configuracion):
    # Hereda todo de Configuracion menos el .env, para no depender del archivo local
    model_config = SettingsConfigDict(env_file=None)


def cargar() -> Configuracion:
    return ConfiguracionSinArchivo()


def test_politica_version_se_lee_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLITICA_VERSION", "0.9")

    assert cargar().politica_version == "0.9"


def test_politica_version_acepta_varios_digitos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLITICA_VERSION", "10.12")

    assert cargar().politica_version == "10.12"


def test_sin_politica_version_la_configuracion_carga_igual(monkeypatch: pytest.MonkeyPatch) -> None:
    # Exigirla fuera del ambiente de pruebas es un criterio de MATU-07, no de esta historia
    monkeypatch.delenv("POLITICA_VERSION", raising=False)

    assert cargar().politica_version is None


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
