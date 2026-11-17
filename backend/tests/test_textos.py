"""Los buscadores de tests/textos.py ven el dato de verdad y no lo confunden con un UUID o un hash.

Los UUID y hashes de estas pruebas son fijos y sintéticos, armados para contener el número buscado.
"""

import pytest

from tests.textos import aparece_celular, aparece_como_dato

# El fallo observado: un UUID de la fila de auditoría contenía 45555
UUID_CON_45555 = "6f1c2b9e-1767-4a0b-9c0d-0e1f2a345555"
UUID_CON_GRUPO_4821 = "6f1c2b9e-4821-4a0b-9c0d-0e1f2a3b4c5d"
HASH_CON_5555 = "3f9a5555c2b1" + "0" * 52


def test_la_subcadena_si_los_confunde() -> None:
    # El defecto: con «in», estos UUID y este hash «contienen» el número aunque nadie lo haya escrito
    assert "5555" in UUID_CON_45555 and "5555" in HASH_CON_5555 and "4821" in UUID_CON_GRUPO_4821


@pytest.mark.parametrize(
    ("texto", "aparece"),
    [
        ("tel 5555", True),
        ('{"pin": "5555"}', True),
        ('{"n": 5555}', True),
        ("pin=5555 ", True),
        ("pin='5555'", True),
        ("[5555]", True),
        ("su PIN es 5555.", True),
        (f'"entidad_id": "{UUID_CON_45555}"', False),
        (HASH_CON_5555, False),
        ("455550", False),
        ('"duracion_ms": 5555.0', False),
        ('"duracion_ms": 0.5555', False),
        ("v5555", False),
        ("2026-11-05 10:00:00", False),
    ],
)
def test_aparece_como_dato_no_confunde_un_uuid_con_el_numero(texto: str, aparece: bool) -> None:
    assert aparece_como_dato("5555", texto) is aparece


def test_aparece_como_dato_un_grupo_del_uuid_no_cuenta() -> None:
    assert not aparece_como_dato("4821", f"AccesoEntregado(id=UUID('{UUID_CON_GRUPO_4821}'))")
    assert aparece_como_dato("4821", f"AccesoEntregado(id=UUID('{UUID_CON_GRUPO_4821}'), pin='4821')")


@pytest.mark.parametrize(
    "escrito",
    [
        "+56 9 5555 0137", "+56955550137", "56 9 5555 0137", "9 5555 0137", "955550137", "5555 0137", "55550137",
        "Rosa, +56 9 5555 0137.",
    ],
)
def test_aparece_celular_en_todas_sus_formas(escrito: str) -> None:
    assert aparece_celular("+56 9 5555 0137", f'{{"detalle": "{escrito}"}}')


@pytest.mark.parametrize(
    "texto",
    [
        f'"entidad_id": "{UUID_CON_45555}"',
        "6f1c2b9e-1767-4a0b-9c0d-a955550137bc",  # los nueve dígitos dentro de un UUID
        "a955550137f" + "0" * 53,  # y dentro de un hash
        "+56 9 5555 0102",  # otro número de la serie
        "+56 9 5555 01370",  # un número más largo
    ],
)
def test_aparece_celular_no_confunde_un_uuid_ni_otro_numero(texto: str) -> None:
    assert not aparece_celular("+56 9 5555 0137", texto)


def test_aparece_celular_exige_nueve_digitos() -> None:
    with pytest.raises(ValueError):
        aparece_celular("5555 0137", "texto")


def test_el_precio_dentro_de_un_request_id_no_es_un_dato_del_log() -> None:
    """MATU-81, hallazgo de Martín (CI de #101, run 44189078321): el request_id de una línea «peticion» traía
    «12990», el precio del pañal de las pruebas, y ``str(PRECIO_PANAL) not in logs`` fallaba sin que el log
    llevara el monto. La Idempotency-Key no estaba en el log: pytest muestra «is contained here» también para la
    primera mitad de un ``A and B`` aunque sea la segunda la que falla."""
    linea = ('{"ts": "2026-11-17T22:23:47.689+00:00", "nivel": "INFO", "logger": "matu.api", "mensaje": "peticion",'
             ' "request_id": "3f6d1a2e-8c4b-4f2b-b63a-5e1299067ca2", "ruta": "/v1/comercio/partes/{parte_id}/listo",'
             ' "estado": 200, "duracion_ms": 14.1}')
    assert "12990" in linea  # la comprobación de antes fallaba aquí
    assert not aparece_como_dato("12990", linea)
    assert aparece_como_dato("12990", '{"monto": 12990}')
