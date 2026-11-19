"""MATU-113 · cifras_a_la_vista, sin base: la comprobación de que el observador no ve montos ya no falla al azar.

Antes se buscaba cada cifra como subcadena de la respuesta, y «9990» caía dentro de un UUID, del sufijo aleatorio del
catálogo sintético o de los microsegundos de actualizado_en (≈1 de cada 400). Estas pruebas fallan con esa búsqueda y
comprueban que la nueva sigue viendo un monto con cualquier clave, anidado o dentro de un texto.
"""

import json
import random
import uuid

import pytest

from tests.modules.ordering.conftest import COSTO_ENVIO, cifras_a_la_vista

pytestmark = pytest.mark.rf("RF-25")

CIFRAS = (12990, 9990, 9990 + COSTO_ENVIO)

CUERPO_DEL_AZAR = {
    "id": "e372bab4-9990-4b8b-b9b9-016659a10826",
    "lineas": [
        {
            "producto": {"id": "6271ef78-ab9c-4f9e-84e4-b6615a5c5b8f", "nombre": "Producto panal 199901"},
            "comercio": {"nombre_fantasia": "Bodega La Muestra 199901", "ficticio": True},
            "cantidad": 1,
        }
    ],
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
        # Negativos: una devolución o un descuento
        ({"devuelto": -12990}, {12990}),
        ({"devuelto": -9990.0}, {9990}),
        # Decimales que son solo ceros
        ({"aviso": "9990.0"}, {9990}),
        ({"aviso": "9990.00"}, {9990}),
        ({"aviso": "$9.990,00"}, {9990}),
        ({"aviso": "Total 13980.0."}, {13980}),
        # Un UUID o un instante dentro del texto se saca, y lo demás se sigue revisando
        ({"aviso": "2026-11-18T12:00:00Z total $9.990"}, {9990}),
        ({"aviso": "e372bab4-9990-4b8b-b9b9-016659a10826 $12.990"}, {12990}),
        # Un monto pegado a la hora no se toma por desfase, segundos ni minutos (QA de eced18b)
        ({"aviso": "2026-11-18T12:00-9990"}, {9990}),
        ({"aviso": "2026-11-18T12:00:00+9990"}, {9990}),
        ({"aviso": "2026-11-18T12:00:00-03:00-9990"}, {9990}),
        ({"aviso": "2026-11-18T12:00:9990"}, {9990}),
        ({"aviso": "2026-11-18T12:9990"}, {9990}),
        ({"aviso": "2026-11-18T12:00:00+03:00 $12.990"}, {12990}),
    ],
)
def test_un_monto_con_cualquier_clave_anidado_o_en_un_texto_si_cuenta(cuerpo: object, esperado: set[int]) -> None:
    assert cifras_a_la_vista(cuerpo, CIFRAS) == esperado


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"aviso": "199901"},
        {"aviso": "12990.5"},
        {"aviso": "12990.05"},
        {"aviso": "9990,5"},
        {"aviso": "1.12990"},
        {"cantidad": 99901},
        {"cantidad": 9990.4},
        {"ficticio": True},
        {"nada": None},
        {"vence_en": "2026-10-20T12:15:00.129990+00:00"},
        # Un UUID o un instante dentro de un texto más largo
        {"ruta": "/pedidos/e372bab4-9990-4b8b-b9b9-016659a10826"},
        {"aviso": "Actualizado el 2026-11-18T07:58:43.912990Z"},
    ],
)
def test_un_numero_mas_largo_un_booleano_o_un_instante_no_cuentan(cuerpo: object) -> None:
    assert cifras_a_la_vista(cuerpo, CIFRAS) == set()


# --- Casos adversariales del QA de MATU-113 (8a9c6ab) ----------------------------------------------------------------

CIFRAS_QA = (12990, 25980, 3990, 29970, 9990, 13980)


@pytest.mark.parametrize(
    ("cuerpo", "esperado"),
    [
        ({"x": 9990}, {9990}),
        ({"a": {"b": [{"c": {"d": 12990}}]}}, {12990}),
        ({"x": 9990.0}, {9990}),
        ({"x": "9990"}, {9990}),
        ({"x": "$9.990"}, {9990}),
        ({"x": "12.990"}, {12990}),
        ({"x": "$12.990 CLP"}, {12990}),
        ({"x": "Tu pedido de $25.980 ya va en camino"}, {25980}),
        ({"x": "Total:29970"}, {29970}),
        ({"x": "total=13980;"}, {13980}),
        ({"x": "CLP9990"}, {9990}),
        ({"x": "-9990"}, {9990}),
        ({"x": "(9.990)"}, {9990}),
        ({"x": "$9.990, envío $3.990"}, {9990, 3990}),
        ({"x": "9990\n"}, {9990}),
        ({"x": ["texto", "otro", "$3.990"]}, {3990}),
        ({"x": "2026-11-18T12:00:00Z total $9.990"}, {9990}),
        ({"x": "e372bab4-9990-4b8b-b9b9-016659a10826 $12.990"}, {12990}),
        ({"x": "9990.0"}, {9990}),
        ({"x": "9990.00"}, {9990}),
        ({"x": -9990}, {9990}),
        ({"devuelto": -25980}, {25980}),
    ],
)
def test_qa_un_monto_se_detecta(cuerpo: object, esperado: set[int]) -> None:
    assert cifras_a_la_vista(cuerpo, CIFRAS_QA) == esperado


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"id": "e372bab4-9990-4b8b-b9b9-016659a10826"},
        {"id": "E372BAB4-9990-4B8B-B9B9-016659A10826"},
        {"t": "2026-11-18T07:58:43.912990Z"},
        {"t": "2026-11-18T07:58:43.912990+00:00"},
        {"t": "2026-11-18 07:58:43.129990"},
        {"n": "Producto panal 199901"},
        {"n": "Producto panal 009990"},
        {"n": "Producto panal 012990"},
        {"n": "Producto panal 999000"},
        {"n": "Bodega La Muestra 139800"},
        {"x": 9990.4},
        # Las claves no se revisan aquí: lo hace MONTOS_PARA_EL_OBSERVADOR
        {"9990": "clave numérica"},
        {"x": "/pedidos/e372bab4-9990-4b8b-b9b9-016659a10826"},
        {"x": "2026-11-18T12:00:00.009990"},
        {"x": "00009990-0000-0000-0000-000000000000"},
        {"x": "urn:uuid:00009990-0000-0000-0000-000000000000"},
        {"x": "{00009990-0000-0000-0000-000000000000}"},
        {"x": "000099900000000000000000000000000"},
        {"x": "00009990000000000000000000000000"},
    ],
)
def test_qa_el_azar_no_cuenta(cuerpo: object) -> None:
    assert cifras_a_la_vista(cuerpo, CIFRAS_QA) == set()


def test_qa_cuerpos_al_azar_con_la_forma_del_pedido_nunca_dan_falso_positivo() -> None:
    rnd = random.Random(113)

    def un_uuid() -> str:
        return str(uuid.UUID(int=rnd.getrandbits(128), version=4))

    for _ in range(5_000):  # con la búsqueda como subcadena, 19 de estos 5.000 fallaban
        sufijo = f"{rnd.randrange(10**6):06d}"
        cuerpo = {
            "id": un_uuid(),
            "persona_cuidada_id": un_uuid(),
            "lineas": [
                {
                    "id": un_uuid(),
                    "producto": {"id": un_uuid(), "nombre": f"Producto panal {sufijo}"},
                    "comercio": {"id": un_uuid(), "nombre_fantasia": f"Bodega La Muestra {sufijo}"},
                    "cantidad": 2,
                }
            ],
            "actualizado_en": f"2026-11-18T07:58:43.{rnd.randrange(10**6):06d}Z",
        }
        assert cifras_a_la_vista(cuerpo, CIFRAS_QA) == set(), cuerpo
