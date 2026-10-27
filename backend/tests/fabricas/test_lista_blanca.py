"""MATU-30 · anotar() y limpiar() solo aceptan las tablas de la lista blanca.

Sin base: la validación ocurre antes de abrir cualquier conexión. El DSN apunta a un puerto sin
servidor para que, si la validación faltara, la prueba fallara en vez de borrar algo.
"""

import uuid

import pytest

from tests.fabricas.fabrica import TABLAS_ANOTABLES, Fabrica

pytestmark = pytest.mark.rf("MATU-30")

DSN_SIN_SERVIDOR = "host=127.0.0.1 port=1 user=nadie dbname=nada connect_timeout=1"


@pytest.mark.parametrize("tabla", ["auditoria", "usuario; DROP TABLE usuario", "plan_seccion", ""])
def test_anotar_rechaza_una_tabla_fuera_de_la_lista(tabla: str) -> None:
    fabrica = Fabrica(dsn=DSN_SIN_SERVIDOR)

    with pytest.raises(ValueError, match="tabla no anotable"):
        fabrica.anotar(tabla, uuid.uuid4())
    assert fabrica.creados == []


@pytest.mark.parametrize("tabla", sorted(TABLAS_ANOTABLES))
def test_anotar_acepta_las_tablas_de_la_lista(tabla: str) -> None:
    fabrica = Fabrica(dsn=DSN_SIN_SERVIDOR)
    fila_id = uuid.uuid4()

    fabrica.anotar(tabla, fila_id)

    assert fabrica.creados == [(tabla, fila_id)]


def test_limpiar_rechaza_una_tabla_que_no_paso_por_anotar() -> None:
    fabrica = Fabrica(dsn=DSN_SIN_SERVIDOR)
    fabrica.creados.append(("auditoria", uuid.uuid4()))

    # ValueError y no un error de conexión: valida antes de conectarse
    with pytest.raises(ValueError, match="tabla no anotable"):
        fabrica.limpiar()
