"""MATU-46 · La regla del teléfono del relevo (decisión 25, C1, C2 y C13), sin base de datos y con el puerto Reloj."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_plan.application.conservacion_relevo import ResultadoConservacionRelevo, conservar
from app.modules.care_plan.domain.relevo import (
    CONSERVACION_TELEFONO,
    MARGEN_RELOJ,
    fin_del_acceso,
    limite_telefono,
    telefono_por_borrar,
)
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-05")

FIN = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)


def test_el_plazo_es_de_30_dias() -> None:
    assert CONSERVACION_TELEFONO == timedelta(days=30)
    assert limite_telefono(FIN + timedelta(days=30, minutes=5)) == FIN


@pytest.mark.parametrize("adelanto", [timedelta(0), timedelta(minutes=1), timedelta(minutes=5)])
def test_un_reloj_adelantado_no_acorta_el_plazo(adelanto: timedelta) -> None:
    """MATU-107 (46-H2): relevo_conservar acepta un ahora hasta 5 minutos adelantado (0027). Con la hora real a 30 días
    menos un segundo del fin, ningún adelanto admitido borra el teléfono."""
    real = FIN + CONSERVACION_TELEFONO - timedelta(seconds=1)
    assert MARGEN_RELOJ == timedelta(minutes=5)
    assert limite_telefono(real + adelanto) <= real - CONSERVACION_TELEFONO
    assert telefono_por_borrar(FIN, None, real + adelanto) is False


def test_el_fin_es_lo_primero_entre_el_vencimiento_y_el_corte() -> None:
    # C2: sin corte (vencido, bloqueado o en pausa) cuenta el vencimiento
    assert fin_del_acceso(FIN, None) == FIN
    # C1: cortado antes de vencer, cuenta el corte
    assert fin_del_acceso(FIN + timedelta(days=5), FIN) == FIN
    # Un corte posterior al vencimiento no alarga nada
    assert fin_del_acceso(FIN, FIN + timedelta(days=5)) == FIN


@pytest.mark.parametrize(
    ("desde_el_fin", "se_borra"),
    [
        (timedelta(days=29, hours=23, minutes=59, seconds=59), False),
        # El margen del reloj (46-H2): a los 30 días exactos todavía no; a los 30 días y 5 minutos, sí
        (timedelta(days=30), False),
        (timedelta(days=30, minutes=4, seconds=59), False),
        (timedelta(days=30, minutes=5), True),
        (timedelta(days=45), True),
        (timedelta(days=-1), False),  # el acceso sigue vigente
    ],
)
def test_telefono_por_borrar_a_los_30_dias_exactos(desde_el_fin: timedelta, se_borra: bool) -> None:
    ahora = FIN + desde_el_fin
    assert telefono_por_borrar(FIN, None, ahora) is se_borra
    assert telefono_por_borrar(FIN + timedelta(days=10), FIN, ahora) is se_borra


class _UnidadEspia:
    def __init__(self) -> None:
        self.llamadas: list[tuple[datetime, datetime]] = []

    def conservar(self, limite: datetime, ahora: datetime) -> int:
        self.llamadas.append((limite, ahora))
        return 3


def test_el_caso_de_uso_pide_el_limite_con_el_instante_del_reloj() -> None:
    ahora = FIN + timedelta(days=31)
    unidad = _UnidadEspia()

    resultado = conservar(unidad, RelojFijo(ahora))

    assert resultado == ResultadoConservacionRelevo(telefonos_borrados=3)
    assert unidad.llamadas == [(ahora - timedelta(days=30, minutes=5), ahora)]
