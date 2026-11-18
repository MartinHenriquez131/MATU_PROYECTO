"""MATU-113 · cifras_a_la_vista, sin base: la comprobación de que el observador no ve montos ya no falla al azar.

Antes se buscaba cada cifra como subcadena de la respuesta, y «9990» caía dentro de un UUID, del sufijo aleatorio del
catálogo sintético o de los microsegundos de actualizado_en (≈1 de cada 400). Estas pruebas fallan con esa búsqueda y
comprueban que la nueva sigue viendo un monto con cualquier clave, anidado o dentro de un texto.
"""

import json

import pytest

from tests.modules.ordering.conftest import COSTO_ENVIO, cifras_a_la_vista

pytestmark = pytest.mark.rf("RF-25")

CIFRAS = (12990, 9990, 9990 + COSTO_ENVIO)

CUERPO_DEL_AZAR = {
    "id": "e372bab4-9990-4b8b-b9b9-016659a10826",
    "lineas": [{
        "producto": {"id": "6271ef78-ab9c-4f9e-84e4-b6615a5c5b8f", "nombre": "Producto panal 199901"},
        "comercio": {"nombre_fantasia": "Bodega La Muestra 199901", "ficticio": True},
        "cantidad": 1,
    }],
    "vence_en": "2026-10-20T12:15:00Z",
    "pagado_en": None,
    "actualizado_en": "2026-11-18T07:58:43.912990Z",
}


def test_las_cifras_dentro_de_un_uuid_un_nombre_o_un_instante_no_cuentan() -> None:
    assert "9990" in json.dumps(CUERPO_DEL_AZAR) and "12990" in json.dumps(CUERPO_DEL_AZAR)
    assert cifras_a_la_vista(CUERPO_DEL_AZAR, CIFRAS) == set()


@pytest.mark.parametrize(
    ("cuerpo", "esperado"),
    [
        ({"precio_unitario": 9990}, {9990}),
        ({"cambio": {"antes": 12990}}, {12990}),
        ({"lineas": [{"otra_clave": 13980}]}, {13980}),
        ({"aviso": "Ahora cuesta $9.990"}, {9990}),
        ({"aviso": "Ahora cuesta $9.990."}, {9990}),
        ({"aviso": "Total 13980 pesos"}, {13980}),
        ({"aviso": "9990"}, {9990}),
        ({"aviso": "12.990"}, {12990}),
        ({"aviso": "Producto 2026-11-18 a 9990"}, {9990}),
    ],
)
def test_un_monto_con_cualquier_clave_anidado_o_en_un_texto_si_cuenta(cuerpo: object, esperado: set[int]) -> None:
    assert cifras_a_la_vista(cuerpo, CIFRAS) == esperado


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"aviso": "199901"},
        {"aviso": "12990.5"},
        {"aviso": "1.12990"},
        {"cantidad": 99901},
        {"ficticio": True},
        {"nada": None},
        {"vence_en": "2026-10-20T12:15:00.129990+00:00"},
    ],
)
def test_un_numero_mas_largo_un_booleano_o_un_instante_no_cuentan(cuerpo: object) -> None:
    assert cifras_a_la_vista(cuerpo, CIFRAS) == set()
