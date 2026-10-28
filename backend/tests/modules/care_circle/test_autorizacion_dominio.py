"""MATU-12 · Autorización vigente para la ficha (RF-02, decisión D-B de Jorge del 28-10).

Regla pura: el instante llega desde afuera (en la API, del puerto Reloj).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_circle.domain.personas import (
    AutorizacionGuardada,
    CalidadOtorgante,
    EstadoAutorizacion,
    estado_autorizacion,
    revision_vence_en,
)

pytestmark = pytest.mark.rf("RF-02")

AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def test_sin_consentimiento() -> None:
    assert estado_autorizacion(None, AHORA) is EstadoAutorizacion.SIN_CONSENTIMIENTO


@pytest.mark.parametrize("calidad", [CalidadOtorgante.TITULAR, CalidadOtorgante.REPRESENTANTE_LEGAL])
def test_titular_y_representante_no_vencen(calidad: CalidadOtorgante) -> None:
    autorizacion = AutorizacionGuardada(calidad_otorgante=calidad.value, revision_vence_en=None)

    assert estado_autorizacion(autorizacion, AHORA + timedelta(days=3650)) is EstadoAutorizacion.VIGENTE


@pytest.mark.parametrize(
    ("vence_en", "esperado"),
    [
        (AHORA + timedelta(seconds=1), EstadoAutorizacion.VIGENTE),
        (AHORA, EstadoAutorizacion.REVISION_VENCIDA),
        (AHORA - timedelta(days=1), EstadoAutorizacion.REVISION_VENCIDA),
    ],
    ids=["vence-en-un-segundo", "vence-justo-ahora", "vencio-ayer"],
)
def test_cuidador_de_hecho_con_revision(vence_en: datetime, esperado: EstadoAutorizacion) -> None:
    autorizacion = AutorizacionGuardada(
        calidad_otorgante=CalidadOtorgante.CUIDADOR_DE_HECHO.value, revision_vence_en=vence_en
    )

    assert estado_autorizacion(autorizacion, AHORA) is esperado


def test_la_revision_vence_doce_meses_despues_del_otorgamiento() -> None:
    otorgado = datetime(2025, 10, 20, 12, 0, tzinfo=UTC)
    vence = revision_vence_en(CalidadOtorgante.CUIDADOR_DE_HECHO, otorgado)
    assert vence is not None
    autorizacion = AutorizacionGuardada(calidad_otorgante=CalidadOtorgante.CUIDADOR_DE_HECHO.value,
                                        revision_vence_en=vence)

    assert estado_autorizacion(autorizacion, vence - timedelta(microseconds=1)) is EstadoAutorizacion.VIGENTE
    assert estado_autorizacion(autorizacion, vence) is EstadoAutorizacion.REVISION_VENCIDA
