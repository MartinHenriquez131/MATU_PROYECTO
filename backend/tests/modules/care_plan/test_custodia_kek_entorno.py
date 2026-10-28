"""MATU-12 · KEK en variable de entorno (decisión D-A de Jorge del 28-10, desvío explícito del ADR-016).

Condiciones del analista normativo que se prueban aquí:
(a) solo con ENTORNO local o pruebas: con produccion o un entorno desconocido la API no arranca;
(b) se enciende explícitamente, y apagada no hay custodia (las rutas responden 503, ver test_ficha_api);
(c) 32 bytes en base64, distinta de los demás secretos, nunca en repr, errores ni logs;
(d) versión fija: otra KEK bajo la misma versión es un error, nunca una DEK nueva;
(e) WARNING fijo al arrancar, sin la clave.

Las pruebas de configuración leen solo del entorno que fijan, nunca del .env del equipo. Toda clave
es sintética y se genera en la prueba.
"""

import base64
import logging
import secrets
import uuid

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict

from app.core.config import Configuracion
from app.modules.care_plan.application.ports import DekCifradaInvalida, KekNoDisponible
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from app.modules.care_plan.infrastructure.custodia_kek_entorno import (
    AVISO_ARRANQUE,
    CustodiaKekEntorno,
    CustodiaNoPermitida,
    KekInvalida,
)
from tests.dobles.repositorio_claves_en_memoria import RepositorioClavesEnMemoria

pytestmark = pytest.mark.rf("RF-02")

VARIABLES = ("ENTORNO", "CUSTODIA_KEK", "KEK_ENTORNO", "KEK_VERSION", "JWT_CLAVE", "PEPPER_EMAIL", "POLITICA_VERSION")


def _kek() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def _dek() -> bytes:
    return secrets.token_bytes(32)


class ConfiguracionSinArchivo(Configuracion):
    # Hereda todo de Configuracion menos el .env, para no depender del archivo local
    model_config = SettingsConfigDict(env_file=None)


@pytest.fixture
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("POLITICA_VERSION", "0.9")
    return monkeypatch


# --- El adaptador -------------------------------------------------------------------------------


def test_envuelve_y_desenvuelve_con_aes_key_wrap() -> None:
    custodia = CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno="pruebas")
    dek = _dek()

    envuelta = custodia.envolver(dek)

    assert envuelta.kek_version == 1
    assert len(envuelta.dek_cifrada) == 40  # RFC 3394: la DEK más 8 bytes de integridad
    assert dek not in envuelta.dek_cifrada
    assert custodia.desenvolver(envuelta.dek_cifrada, 1) == dek
    # Determinista y sin nonce: la misma DEK envuelta dos veces da lo mismo
    assert custodia.envolver(dek).dek_cifrada == envuelta.dek_cifrada


def test_cifrador_aes_gcm_funciona_con_la_custodia_de_entorno() -> None:
    custodia = CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno="local")
    cifrador = CifradorAesGcm(custodia, RepositorioClavesEnMemoria())
    persona, plan = uuid.uuid4(), uuid.uuid4()
    texto = "Rodrigo, su hijo: +56 9 5555 0102"

    seccion = cifrador.cifrar(grupo_id=uuid.uuid4(), persona_cuidada_id=persona, plan_id=plan, tipo="red_apoyo",
                              texto=texto)

    assert cifrador.descifrar(persona_cuidada_id=persona, plan_id=plan, tipo="red_apoyo", seccion=seccion) == texto


def test_otra_kek_con_la_misma_version_no_desenvuelve() -> None:
    # (d) Si la clave cambia sin cambiar KEK_VERSION, error: nunca una DEK distinta
    antes = CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno="pruebas")
    despues = CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno="pruebas")
    envuelta = antes.envolver(_dek())

    with pytest.raises(DekCifradaInvalida):
        despues.desenvolver(envuelta.dek_cifrada, 1)


def test_otra_kek_con_la_misma_version_no_crea_dek_nueva_al_escribir() -> None:
    claves = RepositorioClavesEnMemoria()
    persona, plan, grupo = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    CifradorAesGcm(CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno="pruebas"), claves).cifrar(
        grupo_id=grupo, persona_cuidada_id=persona, plan_id=plan, tipo="rutina", texto="Primera"
    )
    guardada = claves.obtener(persona)
    otra = CifradorAesGcm(CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno="pruebas"), claves)

    with pytest.raises(Exception) as error:
        otra.cifrar(grupo_id=grupo, persona_cuidada_id=persona, plan_id=plan, tipo="rutina", texto="Segunda")

    assert type(error.value).__name__ == "ClaveNoDisponible"
    assert claves.obtener(persona) == guardada


def test_dek_alterada_no_desenvuelve() -> None:
    custodia = CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno="pruebas")
    envuelta = bytearray(custodia.envolver(_dek()).dek_cifrada)
    envuelta[3] ^= 0x01

    with pytest.raises(DekCifradaInvalida):
        custodia.desenvolver(bytes(envuelta), 1)


def test_otra_version_no_existe_en_esta_custodia() -> None:
    custodia = CustodiaKekEntorno(SecretStr(_kek()), kek_version=2, entorno="pruebas")
    envuelta = custodia.envolver(_dek())

    assert envuelta.kek_version == 2
    with pytest.raises(KekNoDisponible):
        custodia.desenvolver(envuelta.dek_cifrada, 1)


@pytest.mark.parametrize("entorno", ["produccion", "staging", "", "Local", "pruebas "])
def test_no_se_construye_fuera_de_local_o_pruebas(entorno: str) -> None:
    # (a) Lista permitida: produccion y cualquier valor desconocido quedan fuera
    with pytest.raises(CustodiaNoPermitida):
        CustodiaKekEntorno(SecretStr(_kek()), kek_version=1, entorno=entorno)


@pytest.mark.parametrize(
    "kek",
    [
        base64.b64encode(secrets.token_bytes(16)).decode(),
        base64.b64encode(secrets.token_bytes(33)).decode(),
        "no es base64 " + secrets.token_hex(8),
        secrets.token_hex(32),
    ],
    ids=["16-bytes", "33-bytes", "no-base64", "hex-de-64"],
)
def test_kek_invalida_no_se_construye_y_el_error_no_la_muestra(kek: str) -> None:
    with pytest.raises(KekInvalida) as error:
        CustodiaKekEntorno(SecretStr(kek), kek_version=1, entorno="pruebas")

    assert kek not in str(error.value)
    assert kek not in repr(error.value)
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_la_kek_no_sale_en_repr_ni_en_errores_ni_en_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    kek = _kek()
    crudo = base64.b64decode(kek)

    custodia = CustodiaKekEntorno(SecretStr(kek), kek_version=1, entorno="pruebas")
    errores: list[BaseException] = []
    for intento in (lambda: custodia.desenvolver(secrets.token_bytes(40), 1),
                    lambda: custodia.desenvolver(secrets.token_bytes(40), 7)):
        try:
            intento()
        except Exception as error:
            errores.append(error)

    # (e) El WARNING de arranque, fijo
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [(logging.WARNING, AVISO_ARRANQUE)]
    # (c) Ni en repr, ni en str, ni en errores, ni en logs, ni en los atributos del objeto
    assert repr(custodia) == str(custodia) == "CustodiaKekEntorno(kek_version=1)"
    assert len(errores) == 2
    for texto in (repr(custodia), str(custodia), caplog.text, *(repr(e) for e in errores), *(str(e) for e in errores)):
        assert kek not in texto
        assert crudo.hex() not in texto
    assert not hasattr(custodia, "__dict__")


# --- La configuración y el arranque ---------------------------------------------------------------


@pytest.mark.parametrize("entorno", ["local", "pruebas"])
def test_custodia_encendida_carga_en_local_y_pruebas(entorno_limpio: pytest.MonkeyPatch, entorno: str) -> None:
    kek = _kek()
    entorno_limpio.setenv("ENTORNO", entorno)
    entorno_limpio.setenv("CUSTODIA_KEK", "entorno_sintetico")
    entorno_limpio.setenv("KEK_ENTORNO", kek)

    configuracion = ConfiguracionSinArchivo()

    assert configuracion.custodia_kek == "entorno_sintetico"
    assert configuracion.kek_version == 1
    assert configuracion.kek_entorno is not None
    assert kek not in repr(configuracion)


@pytest.mark.parametrize(
    "variables",
    [{"CUSTODIA_KEK": "entorno_sintetico", "KEK_ENTORNO": "kek"}, {"CUSTODIA_KEK": "entorno_sintetico"},
     {"KEK_ENTORNO": "kek"}],
    ids=["encendida-con-kek", "encendida-sin-kek", "kek-sin-encender"],
)
def test_en_produccion_no_carga(entorno_limpio: pytest.MonkeyPatch, variables: dict[str, str]) -> None:
    kek = _kek()
    entorno_limpio.setenv("ENTORNO", "produccion")
    for nombre, valor in variables.items():
        entorno_limpio.setenv(nombre, kek if valor == "kek" else valor)

    with pytest.raises(ValidationError) as error:
        ConfiguracionSinArchivo()

    assert "solo se admite con ENTORNO local o pruebas" in str(error.value)
    assert kek not in str(error.value)


def test_entorno_desconocido_no_carga(entorno_limpio: pytest.MonkeyPatch) -> None:
    kek = _kek()
    entorno_limpio.setenv("ENTORNO", "staging")
    entorno_limpio.setenv("CUSTODIA_KEK", "entorno_sintetico")
    entorno_limpio.setenv("KEK_ENTORNO", kek)

    with pytest.raises(ValidationError) as error:
        ConfiguracionSinArchivo()

    assert kek not in str(error.value)


@pytest.mark.parametrize(
    "kek",
    [base64.b64encode(secrets.token_bytes(31)).decode(), "kek-sintetica-que-no-es-base64-" + secrets.token_hex(8)],
    ids=["31-bytes", "no-base64"],
)
def test_kek_de_largo_invalido_no_carga_ni_muestra_el_valor(entorno_limpio: pytest.MonkeyPatch, kek: str) -> None:
    entorno_limpio.setenv("ENTORNO", "local")
    entorno_limpio.setenv("CUSTODIA_KEK", "entorno_sintetico")
    entorno_limpio.setenv("KEK_ENTORNO", kek)

    with pytest.raises(ValidationError) as error:
        ConfiguracionSinArchivo()

    assert [e["loc"] for e in error.value.errors()] == [("kek_entorno",)]
    assert kek not in str(error.value)


@pytest.mark.parametrize("otra", ["JWT_CLAVE", "PEPPER_EMAIL"])
def test_kek_distinta_de_los_demas_secretos(entorno_limpio: pytest.MonkeyPatch, otra: str) -> None:
    # Una KEK en base64 de 44 caracteres también es un secreto válido de 32 o más caracteres
    kek = _kek()
    entorno_limpio.setenv("ENTORNO", "local")
    entorno_limpio.setenv("CUSTODIA_KEK", "entorno_sintetico")
    entorno_limpio.setenv("KEK_ENTORNO", kek)
    entorno_limpio.setenv(otra, kek)

    with pytest.raises(ValidationError) as error:
        ConfiguracionSinArchivo()

    assert f"KEK_ENTORNO y {otra} deben ser claves distintas" in str(error.value)
    assert kek not in str(error.value)
