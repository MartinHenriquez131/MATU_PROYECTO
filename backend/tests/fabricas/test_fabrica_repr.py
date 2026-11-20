"""MATU-80 (QA, P3) · El repr de la Fabrica no muestra su DSN.

pytest imprime el repr de los fixtures en la traza de una prueba que falla. Si la Fabrica mostrara su dsn, la
contraseña del superusuario de pruebas (MATU_TEST_DSN) quedaría en la salida del CI. Sin base: no conecta. Ningún
valor se imprime: la contraseña es sintética y se genera en cada corrida.
"""

import secrets

import pytest

from tests.fabricas.fabrica import Fabrica

pytestmark = pytest.mark.rf("MATU-30")


def test_el_repr_no_muestra_la_contrasena_del_dsn() -> None:
    clave = secrets.token_hex(12)
    fabrica = Fabrica(dsn=f"host=127.0.0.1 port=1 user=nadie password={clave} dbname=nada")

    texto = repr(fabrica)
    assert clave not in texto
    assert "password=" not in texto
    assert "dsn=" not in texto
    assert fabrica.dsn.endswith("dbname=nada")  # el campo sigue ahí, solo fuera del repr


def test_el_repr_de_la_fabrica_por_omision_no_muestra_el_dsn() -> None:
    texto = repr(Fabrica())
    assert "dsn=" not in texto
    assert "password" not in texto
