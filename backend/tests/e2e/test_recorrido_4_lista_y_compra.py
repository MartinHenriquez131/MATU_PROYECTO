"""MATU-80 · Recorrido 4 de MATU-64: exportar la lista de reposición y anotar lo que se compró.

La lista sale de GET …/consumo/lista y la pantalla la imprime, la guarda como PDF o la comparte como texto, sin enlace
(RF-15, ADR-031, decisión 122): no hay una ruta de exportación, así que el recorrido lee la lista que se exporta.
Después la familia anota «Compré» con un envase (RF-13) y el insumo sale de la lista y de «Se acaban pronto».
"""

import pytest

from tests.base_datos import requiere_base
from tests.e2e.conftest import Recorrido

pytestmark = [
    requiere_base,
    pytest.mark.e2e,
    pytest.mark.rf("RF-09"),
    pytest.mark.rf("RF-13"),
    pytest.mark.rf("RF-14"),
    pytest.mark.rf("RF-15"),
]

NOMBRE = "Crema protectora de ejemplo"


def test_recorrido_lista_y_compra(recorrido: Recorrido) -> None:
    r = recorrido
    f = r.familia()
    assert r.autorizar(f, "consumo").status_code == 201

    # Dado un insumo que se acaba en 6 días (24 unidades a 4 al día), que viene en envases de 10
    perfil = r.anotar_insumo(f, nombre_libre=NOMBRE, tasa_unidades=4, stock_unidades=24, unidades_por_envase=10)

    # Cuando la familia abre la lista para exportarla
    lista = r.de_la_persona(f, "GET", "/consumo/lista")

    # Entonces trae el insumo con lo que falta para 30 días, en envases enteros: 120 - 24 = 96, son 10 envases
    assert lista.status_code == 200, lista.text
    assert lista.headers["cache-control"] == "no-store"
    assert lista.json()["fecha"] == "2026-10-20"
    [linea] = lista.json()["items"]
    assert (linea["perfil_id"], linea["nombre"], linea["dias_restantes"]) == (perfil["id"], NOMBRE, 6)
    assert (linea["unidades_sugeridas"], linea["unidades_por_envase"], linea["envases_sugeridos"]) == (96, 10, 10)

    # Cuando compra fuera de MATU y anota «Compré» con 1 envase, sobre la versión que vio
    abierto = r.de_la_persona(f, "GET", f"/consumo/{perfil['id']}")
    assert abierto.status_code == 200, abierto.text
    compra = r.de_la_persona(
        f, "POST", f"/consumo/{perfil['id']}/reponer", {"envases": 1}, **{"If-Match": abierto.headers["ETag"]}
    )

    # Entonces el stock suma el envase y la fecha se corre: 34 unidades alcanzan para 8 días más
    assert compra.status_code == 200, compra.text
    assert (compra.json()["stock_unidades"], compra.json()["fecha_quiebre_estimada"]) == (34, "2026-10-28")
    assert compra.headers["ETag"] != abierto.headers["ETag"]

    # Y el insumo sale de la lista y de «Se acaban pronto»: ya no está en su ventana de aviso
    assert r.de_la_persona(f, "GET", "/consumo/lista").json()["items"] == []
    assert r.de_la_persona(f, "GET", "/consumo/por-acabarse").json()["items"] == []

    # Y la misma compra repetida con la versión vieja no se suma dos veces
    repetida = r.de_la_persona(
        f, "POST", f"/consumo/{perfil['id']}/reponer", {"envases": 1}, **{"If-Match": abierto.headers["ETag"]}
    )
    assert repetida.status_code == 412, repetida.text
    assert r.de_la_persona(f, "GET", f"/consumo/{perfil['id']}").json()["stock_unidades"] == 34
    assert NOMBRE not in r.logs()
