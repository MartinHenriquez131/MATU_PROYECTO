"""MATU-26 · Política de privacidad v0.9.

Criterio 3: su versión se publica en la configuración como POLITICA_VERSION, en formato
MAYOR.MENOR. Esta historia no tiene RF: su traza es la Ley 21.719.

MATU-07 (RF-01) la hace obligatoria fuera del ambiente de pruebas: sin ella la API no arranca.

MATU-25 (decisión 105): ENTORNO admite staging, que también exige POLITICA_VERSION; la KEK y el envío
simulado tienen cada uno su lista permitida, y el arranque registra el entorno.

Las pruebas leen solo del entorno que fijan, nunca del .env del equipo.
"""

import io
import json

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.core import config
from app.core.config import (
    ENTORNOS_ENVIO_SIMULADO,
    ENTORNOS_KEK_SINTETICA,
    ENTORNOS_SOLO_DOMINIOS_RESERVADOS,
    POLITICA_VERSION_FABRICA,
    Configuracion,
)
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
@pytest.mark.parametrize("entorno", ["local", "staging", "produccion"])
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
@pytest.mark.parametrize("entorno", ["local", "pruebas", "staging", "produccion"])
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


# --- MATU-38: PEPPER_LIMITES, la llave de las huellas de la demora de la entrada (RF-37) ----------


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("valor", [None, ""])
def test_pepper_limites_ausente_o_vacio_carga_como_none(monkeypatch: pytest.MonkeyPatch, valor: str | None) -> None:
    if valor is not None:
        monkeypatch.setenv("PEPPER_LIMITES", valor)
    assert cargar().pepper_limites is None


@pytest.mark.rf("RF-37")
def test_pepper_limites_corto_no_carga_ni_aparece_en_el_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEPPER_LIMITES", "l" * 31)
    with pytest.raises(ValidationError) as error:
        cargar()
    assert "l" * 31 not in str(error.value)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("otra", ["PEPPER_EMAIL", "JWT_CLAVE", "PEPPER_PIN"])
def test_pepper_limites_igual_a_otro_secreto_no_carga(monkeypatch: pytest.MonkeyPatch, otra: str) -> None:
    clave = "z" * 64
    monkeypatch.setenv("PEPPER_LIMITES", clave)
    monkeypatch.setenv(otra, clave)
    with pytest.raises(ValidationError) as error:
        cargar()
    assert "deben ser claves distintas" in str(error.value)
    assert clave not in str(error.value)


@pytest.mark.rf("RF-37")
def test_pepper_limites_distinto_carga_como_secreto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEPPER_LIMITES", "l" * 64)
    configuracion = cargar()
    assert configuracion.pepper_limites is not None
    assert "l" * 64 not in repr(configuracion)


# --- MATU-57: PEPPER_RECUPERACION y el envío simulado (RF-37) ------------------------------------


@pytest.mark.rf("RF-37")
def test_pepper_recuperacion_corto_no_carga_ni_aparece_en_el_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEPPER_RECUPERACION", "q" * 31)
    with pytest.raises(ValidationError) as error:
        cargar()
    assert "q" * 31 not in str(error.value)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("otra", ["PEPPER_EMAIL", "JWT_CLAVE", "PEPPER_PIN", "PEPPER_LIMITES"])
def test_pepper_recuperacion_igual_a_otro_secreto_no_carga(monkeypatch: pytest.MonkeyPatch, otra: str) -> None:
    clave = "y" * 64
    monkeypatch.setenv("PEPPER_RECUPERACION", clave)
    monkeypatch.setenv(otra, clave)
    with pytest.raises(ValidationError) as error:
        cargar()
    assert "deben ser claves distintas" in str(error.value)
    assert clave not in str(error.value)


@pytest.mark.rf("RF-37")
def test_pepper_recuperacion_distinto_carga_como_secreto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEPPER_RECUPERACION", "q" * 64)
    configuracion = cargar()
    assert configuracion.pepper_recuperacion is not None
    assert "q" * 64 not in repr(configuracion)


@pytest.mark.rf("RF-37")
def test_envio_simulado_en_produccion_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTORNO", "produccion")
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    monkeypatch.setenv("ENVIADOR_CODIGOS", "simulado")
    with pytest.raises(ValidationError) as error:
        cargar()
    assert "ENVIADOR_CODIGOS=simulado" in str(error.value)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("entorno", ["local", "pruebas", "staging"])
def test_envio_simulado_fuera_de_produccion_carga(monkeypatch: pytest.MonkeyPatch, entorno: str) -> None:
    monkeypatch.setenv("ENTORNO", entorno)
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    monkeypatch.setenv("ENVIADOR_CODIGOS", "simulado")
    assert cargar().enviador_codigos == "simulado"


# --- MATU-25 · staging y las dos listas (decisión 105) --------------------------------------------


def test_staging_carga_con_politica_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTORNO", "staging")
    monkeypatch.setenv("POLITICA_VERSION", "0.10")

    assert cargar().entorno == "staging"


@pytest.mark.parametrize("entorno", ["Staging", "stage", "prod", "STAGING", "staging ", "desarrollo"])
def test_entorno_desconocido_no_carga_sin_normalizar(monkeypatch: pytest.MonkeyPatch, entorno: str) -> None:
    monkeypatch.setenv("ENTORNO", entorno)
    monkeypatch.setenv("POLITICA_VERSION", "0.10")

    with pytest.raises(ValidationError) as error:
        cargar()

    assert [e["loc"] for e in error.value.errors()] == [("entorno",)]


def test_las_dos_listas_son_separadas_y_ninguna_tiene_produccion() -> None:
    # Hoy tienen los mismos valores, pero son dos decisiones: ampliar una no amplía la otra
    assert ENTORNOS_KEK_SINTETICA is not ENTORNOS_ENVIO_SIMULADO
    assert ENTORNOS_KEK_SINTETICA == {"local", "pruebas", "staging"}
    assert ENTORNOS_ENVIO_SIMULADO == {"local", "pruebas", "staging"}
    assert ENTORNOS_SOLO_DOMINIOS_RESERVADOS == {"staging"}
    for lista in (ENTORNOS_KEK_SINTETICA, ENTORNOS_ENVIO_SIMULADO, ENTORNOS_SOLO_DOMINIOS_RESERVADOS):
        assert "produccion" not in lista


def test_el_envio_simulado_usa_su_propia_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    # Si el validador volviera a usar la lista de la KEK, sacar staging de ENTORNOS_ENVIO_SIMULADO no
    # cambiaría nada y esta prueba fallaría
    monkeypatch.setattr(config, "ENTORNOS_ENVIO_SIMULADO", frozenset({"local", "pruebas"}))
    monkeypatch.setenv("ENTORNO", "staging")
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    monkeypatch.setenv("ENVIADOR_CODIGOS", "simulado")

    with pytest.raises(ValidationError) as error:
        cargar()

    assert "ENVIADOR_CODIGOS=simulado" in str(error.value)


def test_la_kek_usa_su_propia_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    # Al revés: sacar staging de la lista de la KEK no saca el envío simulado
    monkeypatch.setattr(config, "ENTORNOS_KEK_SINTETICA", frozenset({"local", "pruebas"}))
    monkeypatch.setenv("ENTORNO", "staging")
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    monkeypatch.setenv("ENVIADOR_CODIGOS", "simulado")

    assert cargar().enviador_codigos == "simulado"

    monkeypatch.setenv("CUSTODIA_KEK", "entorno_sintetico")
    monkeypatch.setenv("KEK_ENTORNO", "a" * 43 + "=")
    with pytest.raises(ValidationError) as error:
        cargar()
    assert "La KEK en variable de entorno" in str(error.value)


@pytest.mark.parametrize(
    "variables",
    [
        {"CUSTODIA_KEK": "entorno_sintetico", "KEK_ENTORNO": "a" * 43 + "="},
        {"ENVIADOR_CODIGOS": "simulado"},
    ],
    ids=["kek", "envio-simulado"],
)
def test_produccion_no_carga_ni_con_la_kek_ni_con_el_envio_simulado(
    monkeypatch: pytest.MonkeyPatch, variables: dict[str, str]
) -> None:
    monkeypatch.setenv("ENTORNO", "produccion")
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)

    with pytest.raises(ValidationError):
        cargar()


def test_el_arranque_registra_el_entorno_y_nada_mas(monkeypatch: pytest.MonkeyPatch) -> None:
    # En WARNING: se ve aunque LOG_NIVEL=WARNING, así el despliegue siempre deja la marca (decisión 105, (j))
    monkeypatch.setattr(config, "Configuracion", ConfiguracionSinArchivo)
    monkeypatch.setenv("ENTORNO", "staging")
    monkeypatch.setenv("LOG_NIVEL", "WARNING")
    monkeypatch.setenv("POLITICA_VERSION", "0.10")
    secreto = "s" * 64
    monkeypatch.setenv("JWT_CLAVE", secreto)
    config.obtener_configuracion.cache_clear()
    salida = io.StringIO()
    try:
        crear_app(stream_logs=salida)
    finally:
        config.obtener_configuracion.cache_clear()

    lineas = [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]
    assert [(x["nivel"], x["mensaje"]) for x in lineas if x["logger"] == "matu.api.arranque"] == [
        ("WARNING", "entorno=staging")
    ]
    assert secreto not in salida.getvalue()
