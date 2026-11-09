"""MATU-59 · La consulta de stock que sale por CatalogoComercio no lleva nada de la familia (condiciones 4.1 a 4.7).

Prueba de dominio del módulo catalog (arquitectura 12.5): el objeto tiene exactamente sus líneas y una referencia
opaca, la referencia es aleatoria y nueva en cada consulta, el puerto no recibe la sesión, y el adaptador simulado
no usa la red y solo registra cuántas líneas hubo. Sin base.
"""

import dataclasses
import inspect
import json
import logging
import re
import socket
import uuid
from typing import Any

import pytest

from app.modules.catalog.application import catalogo as casos
from app.modules.catalog.application.ports import CatalogoComercio
from app.modules.catalog.domain.consulta_stock import (
    CANTIDAD_MAXIMA,
    ConsultaInvalida,
    ConsultaStock,
    LineaConsulta,
    RespuestaStock,
    nueva_consulta,
)
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado

pytestmark = pytest.mark.rf("RF-26")

PRODUCTO_1, PRODUCTO_2 = uuid.UUID(int=0x59F1), uuid.UUID(int=0x59F2)
COMERCIO = uuid.UUID(int=0x59C1)

# Lo que una familia tiene y nunca debe viajar al comercio: ids y datos sintéticos
FAMILIA = {
    "grupo_id": str(uuid.UUID(int=0x59A1)),
    "persona_cuidada_id": str(uuid.UUID(int=0x59A2)),
    "usuario_id": str(uuid.UUID(int=0x59A3)),
    "pedido_id": str(uuid.UUID(int=0x59A4)),
    "nombre": "Persona Sintética",
    "correo": "familia.59@example.com",
    "telefono": "+56900000059",
    "direccion": "Calle de Prueba 59",
    "comuna": "Ñuñoa",
}
CLAVES_PROHIBIDAS = (
    "grupo", "persona", "usuario", "pedido", "nombre", "correo", "email", "telefono", "direccion", "comuna",
    "token", "cookie", "ip", "user_agent", "request_id", "jwt",
)


def _serializado(consulta: ConsultaStock) -> str:
    return json.dumps(dataclasses.asdict(consulta), default=str, ensure_ascii=False)


def _consulta() -> ConsultaStock:
    return nueva_consulta([(PRODUCTO_1, 2), (PRODUCTO_2, 1)])


def test_la_consulta_tiene_exactamente_lineas_y_referencia() -> None:
    assert [c.name for c in dataclasses.fields(ConsultaStock)] == ["lineas", "referencia"]
    assert [c.name for c in dataclasses.fields(LineaConsulta)] == ["producto_id", "cantidad"]


def test_la_consulta_es_inmutable() -> None:
    consulta = _consulta()

    with pytest.raises(dataclasses.FrozenInstanceError):
        consulta.referencia = "otra"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        consulta.lineas[0].cantidad = 5  # type: ignore[misc]
    assert isinstance(consulta.lineas, tuple)


def test_lo_serializado_no_lleva_nada_de_la_familia() -> None:
    serializado = _serializado(_consulta())

    claves = set(re.findall(r'"([a-z_]+)":', serializado))
    assert claves == {"lineas", "producto_id", "cantidad", "referencia"}
    assert not any(prohibida in clave for clave in claves for prohibida in CLAVES_PROHIBIDAS)
    for valor in FAMILIA.values():
        assert valor not in serializado


def test_la_referencia_es_nueva_en_cada_consulta_aunque_las_lineas_sean_iguales() -> None:
    referencias = {_consulta().referencia for _ in range(200)}

    assert len(referencias) == 200


def test_la_referencia_es_opaca_sin_fecha_ni_correlativo() -> None:
    referencias = [_consulta().referencia for _ in range(20)]

    for referencia in referencias:
        # 128 bits en base64 url: 22 caracteres, sin guiones de fecha ni el formato de un UUID del grupo
        assert re.fullmatch(r"[A-Za-z0-9_-]{22}", referencia)
        assert not re.search(r"20\d\d-?\d\d-?\d\d", referencia)
        assert not any(valor.replace("-", "") in referencia for valor in FAMILIA.values())
    assert not all(a < b for a, b in zip(referencias, referencias[1:], strict=False))


@pytest.mark.parametrize(
    "lineas",
    [
        [],
        [(PRODUCTO_1, 0)],
        [(PRODUCTO_1, CANTIDAD_MAXIMA + 1)],
        [(PRODUCTO_1, 1), (PRODUCTO_1, 2)],
        [(PRODUCTO_1, True)],
    ],
    ids=["sin-lineas", "cantidad-cero", "cantidad-sobre-el-tope", "producto-repetido", "booleano"],
)
def test_consulta_invalida(lineas: list[tuple[uuid.UUID, Any]]) -> None:
    with pytest.raises(ConsultaInvalida):
        nueva_consulta(lineas)


def test_el_puerto_no_recibe_la_sesion_ni_la_peticion() -> None:
    parametros = list(inspect.signature(CatalogoComercio.consultar_stock).parameters)
    simulado = list(inspect.signature(CatalogoComercioSimulado.consultar_stock).parameters)

    assert parametros == simulado == ["self", "comercio_id", "consulta"]


def test_el_simulado_responde_sin_red_y_registra_solo_la_cantidad_de_lineas(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def sin_red(*_: Any, **__: Any) -> None:
        raise AssertionError("el adaptador simulado abrió un socket")

    monkeypatch.setattr(socket, "socket", sin_red)
    monkeypatch.setattr(socket, "create_connection", sin_red)
    simulado = CatalogoComercioSimulado({(COMERCIO, PRODUCTO_1): 5, (COMERCIO, PRODUCTO_2): 0})
    consulta = nueva_consulta([(PRODUCTO_1, 8), (PRODUCTO_2, 1)])

    with caplog.at_level(logging.DEBUG, logger="matu.catalog"):
        respuesta = simulado.consultar_stock(COMERCIO, consulta)

    assert respuesta.referencia == consulta.referencia
    assert {(linea.producto_id, linea.disponible) for linea in respuesta.lineas} == {(PRODUCTO_1, 5), (PRODUCTO_2, 0)}
    # Una sola línea, con la cantidad de líneas y nada más: ni productos, ni cantidades, ni comercio, ni referencia
    assert [r.getMessage() for r in caplog.records] == ["consulta de stock simulada lineas=2"]
    assert all(not r.args or r.args == (2,) for r in caplog.records)
    assert simulado.precios_de_ejemplo is True


def test_otro_comercio_sin_existencias_no_tiene_el_producto() -> None:
    simulado = CatalogoComercioSimulado({(COMERCIO, PRODUCTO_1): 5})

    respuesta = casos.consultar_stock(simulado, uuid.UUID(int=0x59C2), [(PRODUCTO_1, 1)])

    assert [linea.disponible for linea in respuesta.lineas] == [0]


def test_cada_consulta_del_caso_de_uso_lleva_una_referencia_nueva() -> None:
    vistas: list[ConsultaStock] = []

    class Espia(CatalogoComercioSimulado):
        def consultar_stock(self, comercio_id: uuid.UUID, consulta: ConsultaStock) -> RespuestaStock:
            vistas.append(consulta)
            return super().consultar_stock(comercio_id, consulta)

    espia = Espia()
    for _ in range(3):
        casos.consultar_stock(espia, COMERCIO, [(PRODUCTO_1, 1)])

    assert len({c.referencia for c in vistas}) == 3


def test_una_respuesta_con_otra_referencia_se_rechaza() -> None:
    class Ajeno(CatalogoComercioSimulado):
        def consultar_stock(self, comercio_id: uuid.UUID, consulta: ConsultaStock) -> RespuestaStock:
            return RespuestaStock(referencia="otra", lineas=())

    with pytest.raises(casos.RespuestaAjena):
        casos.consultar_stock(Ajeno(), COMERCIO, [(PRODUCTO_1, 1)])
