"""MATU-63 · Las reglas puras del despacho: el código de retiro, el estado del pedido según sus partes, la cancelación
después de pagar, la referencia que se dicta y lo que MATU le debe al comercio (D-63-3 a D-63-8, D-63-11, O3 y O6)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.fulfillment.domain.despacho import (
    ALFABETO_REFERENCIA,
    VIDA_CODIGO,
    EstadoCodigo,
    EstadoParte,
    LineaDespacho,
    avance,
    cancelable_despues_de_pagar,
    codigo_valido,
    estado_codigo,
    huella_codigo,
    monto_consumo,
    preparar_antes_de,
    referencia_valida,
    todo_falta,
)
from app.modules.ordering.infrastructure.repositorio_pedidos import ALFABETO_REFERENCIA as ALFABETO_ORDERING
from app.modules.ordering.infrastructure.repositorio_pedidos import nueva_referencia_parte

pytestmark = pytest.mark.rf("RF-26")

AHORA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
P = EstadoParte


def _codigo(**cambios: object) -> EstadoCodigo:
    base: dict[str, object] = {
        "generado_en": AHORA - timedelta(minutes=10),
        "con_hash": True,
        "expira_en": AHORA - timedelta(minutes=10) + VIDA_CODIGO,
        "usado_en": None,
        "bloqueado_en": None,
        "ahora": AHORA,
    }
    return estado_codigo(**{**base, **cambios})  # type: ignore[arg-type]


def test_estado_del_codigo() -> None:
    assert _codigo() is EstadoCodigo.VIGENTE
    assert _codigo(generado_en=None, expira_en=None, con_hash=False) is EstadoCodigo.SIN_CODIGO
    assert _codigo(usado_en=AHORA) is EstadoCodigo.USADO
    assert _codigo(bloqueado_en=AHORA, con_hash=False) is EstadoCodigo.BLOQUEADO
    # Vence a los 90 minutos, también si el hash todavía no se vació
    assert _codigo(ahora=AHORA + VIDA_CODIGO) is EstadoCodigo.VENCIDO
    assert _codigo(con_hash=False) is EstadoCodigo.VENCIDO


def test_vida_del_codigo_es_de_90_minutos() -> None:
    assert timedelta(minutes=90) == VIDA_CODIGO


def test_huella_del_codigo_depende_de_la_parte_y_del_secreto() -> None:
    secreto, parte, otra = b"s" * 32, uuid.uuid4(), uuid.uuid4()
    huella = huella_codigo(secreto, parte, "482173")
    assert len(huella) == 64 and "482173" not in huella
    assert huella == huella_codigo(secreto, parte, "482173")
    assert huella != huella_codigo(secreto, otra, "482173")
    assert huella != huella_codigo(b"t" * 32, parte, "482173")
    with pytest.raises(ValueError):
        huella_codigo(b"", parte, "482173")


@pytest.mark.parametrize("codigo, valido", [("482173", True), ("48217", False), ("4821734", False),
                                            ("48a173", False), ("４８２１７３", False)])
def test_el_codigo_son_seis_cifras(codigo: str, valido: bool) -> None:
    assert codigo_valido(codigo) is valido


def test_la_referencia_se_dicta() -> None:
    assert ALFABETO_REFERENCIA == ALFABETO_ORDERING
    assert not set("0O1IL") & set(ALFABETO_REFERENCIA)
    referencias = {nueva_referencia_parte() for _ in range(200)}
    assert all(referencia_valida(r) for r in referencias) and len(referencias) > 190
    assert not referencia_valida("K4M7X0") and not referencia_valida("K4M7XPQ")


def test_preparar_antes_de_son_dos_horas() -> None:
    assert preparar_antes_de(AHORA) == AHORA + timedelta(hours=2)


@pytest.mark.parametrize(
    "estado, partes, esperado",
    [
        ("pagado", [P.ENVIADA], ["enviado_a_comercio"]),
        ("pagado", [P.PREPARANDO, P.ENVIADA], ["enviado_a_comercio", "preparando"]),
        ("enviado_a_comercio", [P.ENVIADA, P.ENVIADA], []),
        ("preparando", [P.LISTA, P.PREPARANDO], []),
        ("preparando", [P.LISTA, P.CANCELADA], ["listo_retiro"]),
        ("preparando", [P.CANCELADA, P.CANCELADA], ["cancelado_con_devolucion"]),
        ("listo_retiro", [P.RETIRADA, P.LISTA], []),
        ("listo_retiro", [P.RETIRADA, P.CANCELADA], ["retirado"]),
        ("preparando", [P.RETIRADA], ["listo_retiro", "retirado"]),
        ("en_ruta", [P.RETIRADA], []),
        ("cancelado_con_devolucion", [P.CANCELADA], []),
    ],
)
def test_el_pedido_sigue_a_sus_partes(estado: str, partes: list[EstadoParte], esperado: list[str]) -> None:
    pasos = avance(estado, partes)
    assert [p.hacia for p in pasos] == esperado
    # Cada paso es una transición declarada de la arquitectura 8.1
    from app.modules.ordering.domain.estados import Estado, permitida

    assert all(permitida(Estado(p.desde), Estado(p.hacia)) for p in pasos)


def test_si_todo_falta_el_motivo_es_producto_faltante() -> None:
    [paso] = avance("preparando", [P.CANCELADA])
    assert (paso.motivo, paso.por_comercio) == ("producto_faltante", True)
    assert todo_falta([P.CANCELADA, P.CANCELADA]) and not todo_falta([P.CANCELADA, P.LISTA]) and not todo_falta([])
    # El paso a enviado_a_comercio no lo causa el comercio
    assert not avance("pagado", [P.ENVIADA])[0].por_comercio


@pytest.mark.parametrize(
    "estado, partes, cancelable",
    [
        ("pagado", [P.ENVIADA], True),
        ("enviado_a_comercio", [P.ENVIADA, P.ENVIADA], True),
        ("enviado_a_comercio", [P.ENVIADA, P.PREPARANDO], False),
        ("preparando", [P.PREPARANDO], False),
        ("total_confirmado", [], False),
    ],
)
@pytest.mark.rf("R15")
def test_r15_se_cancela_mientras_nadie_prepara(estado: str, partes: list[EstadoParte], cancelable: bool) -> None:
    assert cancelable_despues_de_pagar(estado, partes) is cancelable


@pytest.mark.rf("RF-31")
def test_lo_que_se_debe_al_comercio_descuenta_lo_que_falto() -> None:
    parte = uuid.uuid4()
    lineas = [
        LineaDespacho(uuid.uuid4(), parte, cantidad=3, unidades_faltantes=1, precio_unitario=12990, monto_devuelto=0),
        LineaDespacho(uuid.uuid4(), parte, cantidad=2, unidades_faltantes=0, precio_unitario=4490, monto_devuelto=0),
    ]
    assert monto_consumo(lineas) == 2 * 12990 + 2 * 4490
    assert lineas[0].monto_faltante == 12990 and lineas[0].entregadas == 2
