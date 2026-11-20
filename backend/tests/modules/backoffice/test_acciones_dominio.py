"""MATU-92 · Lo que el servidor decide por la pantalla (C7, C10, C11 y C22): puede_cancelar y puede_arrepentirse, con
su motivo cuando no. Reglas puras de fulfillment y payments. Sin base."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.modules.fulfillment.domain.despacho import EstadoParte, MotivoNoCancelar, motivo_no_cancelar
from app.modules.payments.domain.retracto import (
    MotivoNoArrepentirse,
    motivo_no_arrepentirse,
    plazo_por_correo,
    plazo_retracto,
)

P = EstadoParte
M = MotivoNoArrepentirse
ENTREGA = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)  # viernes 13-11, 12:00 de Chile


# --- Cancelar (R15) -----------------------------------------------------------------------------------------------


@pytest.mark.rf("R15")
@pytest.mark.parametrize(
    ("rol", "estado", "partes", "esperado"),
    [
        ("admin", "pagado", [P.ENVIADA], None),
        ("admin", "enviado_a_comercio", [P.ENVIADA, P.ENVIADA], None),
        ("cuidador", "pagado", [P.ENVIADA], MotivoNoCancelar.ROL),
        ("pagador", "enviado_a_comercio", [P.ENVIADA], MotivoNoCancelar.ROL),
        ("admin", "enviado_a_comercio", [P.ENVIADA, P.PREPARANDO], MotivoNoCancelar.YA_SE_PREPARA),
        ("admin", "preparando", [P.PREPARANDO], MotivoNoCancelar.YA_SE_PREPARA),
        ("admin", "entregado", [P.RETIRADA], MotivoNoCancelar.YA_SE_PREPARA),
        # C11: ya cancelado es otro motivo, para todos los roles
        ("admin", "cancelado_con_devolucion", [P.CANCELADA], MotivoNoCancelar.CANCELADO),
        ("cuidador", "cancelado_con_devolucion", [P.CANCELADA], MotivoNoCancelar.CANCELADO),
        # El rol solo se dice mientras todavía se puede: con el comercio preparando, ya_se_prepara
        ("cuidador", "preparando", [P.PREPARANDO], MotivoNoCancelar.YA_SE_PREPARA),
    ],
)
def test_motivo_no_cancelar(
    rol: str, estado: str, partes: list[EstadoParte], esperado: MotivoNoCancelar | None
) -> None:
    assert motivo_no_cancelar(rol, estado, partes) is esperado


# --- Arrepentirse (R3) --------------------------------------------------------------------------------------------


def _motivo(ahora: datetime, *, administra: bool = True, pago: bool = False, disponibles: int = 2) -> M | None:
    return motivo_no_arrepentirse(
        entregado_en=ENTREGA, ahora=ahora, administra=administra, pago=pago, disponibles=disponibles
    )


@pytest.mark.rf("R3")
def test_el_admin_y_quien_pago_pueden_dentro_del_plazo() -> None:
    ahora = ENTREGA + timedelta(days=1)
    assert _motivo(ahora) is None
    assert _motivo(ahora, administra=False, pago=True) is None
    assert _motivo(ahora, administra=False, pago=False) is M.ROL


@pytest.mark.rf("R3")
def test_sin_entregar_no_hay_retracto() -> None:
    assert (
        motivo_no_arrepentirse(entregado_en=None, ahora=ENTREGA, administra=True, pago=True, disponibles=2)
        is M.SIN_ENTREGAR
    )


@pytest.mark.rf("R3")
def test_los_dos_plazos_c22() -> None:
    fin_app = plazo_retracto(ENTREGA)
    fin_correo = plazo_por_correo(ENTREGA)
    assert _motivo(fin_app) is None
    assert _motivo(fin_app + timedelta(microseconds=1)) is M.PLAZO_APP_VENCIDO
    assert _motivo(fin_correo) is M.PLAZO_APP_VENCIDO
    assert _motivo(fin_correo + timedelta(microseconds=1)) is M.PLAZO_VENCIDO
    # El plazo vence para todos: a quien no puede por rol, también se le dice el plazo
    assert _motivo(fin_app + timedelta(days=1), administra=False) is M.PLAZO_APP_VENCIDO


@pytest.mark.rf("R3")
def test_nada_disponible_va_despues_del_rol() -> None:
    ahora = ENTREGA + timedelta(days=1)
    assert _motivo(ahora, disponibles=0) is M.NADA_DISPONIBLE
    assert _motivo(ahora, administra=False, pago=False, disponibles=0) is M.ROL


@pytest.mark.rf("R3")
def test_o6_el_plazo_de_la_app_es_el_fin_del_dia_en_chile() -> None:
    fin = plazo_retracto(ENTREGA).astimezone(ZoneInfo("America/Santiago"))
    assert (fin.hour, fin.minute, fin.second) == (23, 59, 59)
    assert fin.date().isoformat() == "2026-11-27"
