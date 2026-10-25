"""MATU-05a · Reglas puras de la sesión: duración y vencimiento del access token (RF-37)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.modules.iam.domain.sesion import (
    DURACION_ACCESO,
    CredencialesInvalidas,
    TokenInvalido,
    esta_vigente,
    puede_iniciar_sesion,
    vencimiento,
)

EMITIDO = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


@pytest.mark.rf("RF-37")
def test_el_acceso_dura_15_minutos() -> None:
    assert DURACION_ACCESO == timedelta(minutes=15)
    assert vencimiento(EMITIDO) == datetime(2026, 10, 20, 12, 15, tzinfo=UTC)


@pytest.mark.rf("RF-37")
def test_vigente_hasta_un_instante_antes_del_vencimiento() -> None:
    exp = vencimiento(EMITIDO)

    assert esta_vigente(exp, EMITIDO)
    assert esta_vigente(exp, exp - timedelta(microseconds=1))


@pytest.mark.rf("RF-37")
def test_vencido_en_el_instante_exacto_y_despues() -> None:
    exp = vencimiento(EMITIDO)

    assert not esta_vigente(exp, exp)
    assert not esta_vigente(exp, exp + timedelta(seconds=1))


def test_vigencia_compara_instantes_en_cualquier_zona() -> None:
    # 09:14 en UTC-3 son las 12:14 UTC: todavía vigente
    santiago = timezone(timedelta(hours=-3))
    exp = vencimiento(EMITIDO)

    assert esta_vigente(exp, datetime(2026, 10, 20, 9, 14, tzinfo=santiago))
    assert not esta_vigente(exp, datetime(2026, 10, 20, 9, 15, tzinfo=santiago))


@pytest.mark.parametrize(
    "llamada",
    [
        pytest.param(lambda: vencimiento(datetime(2026, 10, 20, 12, 0)), id="vencimiento-sin-zona"),
        pytest.param(lambda: esta_vigente(datetime(2026, 10, 20, 12, 15), EMITIDO), id="exp-sin-zona"),
        pytest.param(lambda: esta_vigente(vencimiento(EMITIDO), datetime(2026, 10, 20, 12, 0)), id="ahora-sin-zona"),
    ],
)
def test_instantes_sin_zona_se_rechazan(llamada: object) -> None:
    with pytest.raises(ValueError):
        llamada()  # type: ignore[operator]


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(("estado", "puede"), [("activo", True), ("bloqueado", False), ("eliminado", False)])
def test_solo_una_cuenta_activa_inicia_sesion(estado: str, puede: bool) -> None:
    assert puede_iniciar_sesion(estado) is puede


def test_las_excepciones_no_llevan_datos() -> None:
    assert str(CredencialesInvalidas()) == ""
    assert str(TokenInvalido()) == ""
