"""El doble CustodiaEnMemoria cumple el contrato de CustodiaClaves: ida y vuelta, rotación y destrucción."""

import secrets

import pytest

from app.modules.care_plan.application.ports import CustodiaClaves, DekCifradaInvalida, KekNoDisponible
from tests.dobles.custodia_en_memoria import CustodiaEnMemoria


def _dek() -> bytes:
    return secrets.token_bytes(32)


def test_envolver_y_desenvolver_ida_y_vuelta() -> None:
    # Dada una custodia, usada a través del puerto, y una DEK
    custodia: CustodiaClaves = CustodiaEnMemoria()
    dek = _dek()

    # Cuando se envuelve y se desenvuelve
    envuelta = custodia.envolver(dek)
    recuperada = custodia.desenvolver(envuelta.dek_cifrada, envuelta.kek_version)

    # Entonces se recupera la misma DEK, y lo guardado no es la DEK en claro
    assert recuperada == dek
    assert dek not in envuelta.dek_cifrada


def test_envolver_rechaza_dek_que_no_es_de_256_bits() -> None:
    # Dada una custodia, cuando se envuelve una DEK de 16 bytes, entonces se rechaza
    with pytest.raises(ValueError):
        CustodiaEnMemoria().envolver(secrets.token_bytes(16))


def test_dek_cifrada_alterada_no_desenvuelve() -> None:
    # Dada una DEK envuelta
    custodia = CustodiaEnMemoria()
    envuelta = custodia.envolver(_dek())

    # Cuando se altera un byte de la DEK cifrada
    alterada = bytes([envuelta.dek_cifrada[0] ^ 1]) + envuelta.dek_cifrada[1:]

    # Entonces desenvolver falla
    with pytest.raises(DekCifradaInvalida):
        custodia.desenvolver(alterada, envuelta.kek_version)


def test_rotar_kek_envuelve_con_la_nueva_y_la_anterior_sigue_desenvolviendo(custodia: CustodiaEnMemoria) -> None:
    # Dada una DEK envuelta con la versión 1, en la custodia de las fixtures globales
    dek_antigua = _dek()
    antigua = custodia.envolver(dek_antigua)

    # Cuando se rota la KEK y se envuelve otra DEK
    nueva_version = custodia.rotar()
    dek_nueva = _dek()
    nueva = custodia.envolver(dek_nueva)

    # Entonces la nueva queda con la versión nueva y ambas desenvuelven con su versión
    assert antigua.kek_version == 1
    assert nueva.kek_version == nueva_version == 2
    assert custodia.desenvolver(antigua.dek_cifrada, antigua.kek_version) == dek_antigua
    assert custodia.desenvolver(nueva.dek_cifrada, nueva.kek_version) == dek_nueva


def test_desenvolver_con_otra_version_falla() -> None:
    # Dada una DEK envuelta con la versión 1 y una KEK rotada
    custodia = CustodiaEnMemoria()
    envuelta = custodia.envolver(_dek())
    custodia.rotar()

    # Cuando se intenta desenvolver con la versión 2, entonces falla
    with pytest.raises(DekCifradaInvalida):
        custodia.desenvolver(envuelta.dek_cifrada, 2)


def test_destruir_version_impide_desenvolver_lo_que_envolvio() -> None:
    # Dada una DEK envuelta con la versión 1 y la KEK rotada a la versión 2
    custodia = CustodiaEnMemoria()
    antigua = custodia.envolver(_dek())
    custodia.rotar()
    dek_nueva = _dek()
    nueva = custodia.envolver(dek_nueva)

    # Cuando se destruye la versión 1
    custodia.destruir(1)

    # Entonces lo envuelto con la versión 1 ya no se puede desenvolver, y la versión 2 sigue sirviendo
    with pytest.raises(KekNoDisponible):
        custodia.desenvolver(antigua.dek_cifrada, antigua.kek_version)
    assert custodia.desenvolver(nueva.dek_cifrada, nueva.kek_version) == dek_nueva


def test_sin_kek_vigente_no_se_envuelve_ni_se_crea_una_nueva() -> None:
    # Dada una custodia cuya única versión fue destruida
    custodia = CustodiaEnMemoria()
    custodia.destruir(1)

    # Cuando se intenta envolver, entonces falla y no aparece una versión de reemplazo
    with pytest.raises(KekNoDisponible):
        custodia.envolver(_dek())
    assert custodia.version_vigente is None
