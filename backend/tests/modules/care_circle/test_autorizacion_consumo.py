"""MATU-36 · Autorización para el consumo (decisión 37): evidencia y caso de uso, sin base."""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.care_circle.application.autorizaciones import (
    AutorizacionVigente,
    NuevaAutorizacion,
    RolSinPermisoAutorizacion,
    SolicitudAutorizacion,
    otorgar_autorizacion_consumo,
)
from app.modules.care_circle.domain.personas import (
    FINALIDAD_CONSUMO,
    AvisoMostrado,
    CalidadOtorgante,
    OtorgamientoInvalido,
    evidencia,
)
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-10")

AHORA = datetime(2026, 11, 3, 14, 20, tzinfo=UTC)


class Repo:
    def __init__(self, vigente: bool = False) -> None:
        self.vigente = vigente
        self.guardadas: list[NuevaAutorizacion] = []

    def bloquear_persona(self, persona_id: uuid.UUID) -> bool:
        return True

    def hay_vigente(self, persona_id: uuid.UUID, finalidad: str) -> bool:
        assert finalidad == FINALIDAD_CONSUMO
        return self.vigente

    def guardar(self, autorizacion: NuevaAutorizacion) -> None:
        self.guardadas.append(autorizacion)


def _solicitud(calidad: CalidadOtorgante, rol: str = "cuidador", aviso: AvisoMostrado | None = None,
               referencia: str | None = None) -> SolicitudAutorizacion:
    return SolicitudAutorizacion(
        usuario_id=uuid.uuid4(), grupo_id=uuid.uuid4(), rol=rol, persona_id=uuid.uuid4(),
        calidad_otorgante=calidad, referencia_documento=referencia, aviso=aviso,
    )


@pytest.mark.parametrize("calidad", list(CalidadOtorgante))
def test_la_declaracion_del_consumo_es_propia(calidad: CalidadOtorgante) -> None:
    datos = evidencia(calidad, "0.10", FINALIDAD_CONSUMO)
    assert datos["declaracion"] == {"id": f"declaracion_consumo_{calidad.value}", "version": "0.10"}
    # La del plan de cuidado no cambia (MATU-07)
    assert evidencia(calidad, "0.10")["declaracion"]["id"] == f"declaracion_{calidad.value}"


def test_cuidador_de_hecho_con_aviso_queda_con_revision_anual() -> None:
    repo = Repo()
    resultado = otorgar_autorizacion_consumo(
        _solicitud(CalidadOtorgante.CUIDADOR_DE_HECHO, aviso=AvisoMostrado("aviso_cuidador_de_hecho", "1.1")),
        "0.10", RelojFijo(AHORA), repo,
    )
    [guardada] = repo.guardadas
    assert guardada.finalidad == FINALIDAD_CONSUMO and guardada.otorgado_en == AHORA
    assert guardada.revision_vence_en == datetime(2027, 11, 3, 14, 20, tzinfo=UTC)
    assert resultado.aviso is not None


@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_pagador_y_observador_no_autorizan(rol: str) -> None:
    with pytest.raises(RolSinPermisoAutorizacion):
        otorgar_autorizacion_consumo(_solicitud(CalidadOtorgante.TITULAR, rol=rol), "0.10", RelojFijo(AHORA), Repo())


def test_las_reglas_de_la_calidad_son_las_del_alta() -> None:
    with pytest.raises(OtorgamientoInvalido):
        otorgar_autorizacion_consumo(_solicitud(CalidadOtorgante.CUIDADOR_DE_HECHO), "0.10", RelojFijo(AHORA), Repo())
    with pytest.raises(OtorgamientoInvalido):
        otorgar_autorizacion_consumo(
            _solicitud(CalidadOtorgante.REPRESENTANTE_LEGAL), "0.10", RelojFijo(AHORA), Repo()
        )


def test_ya_vigente_es_conflicto_y_no_escribe() -> None:
    repo = Repo(vigente=True)
    with pytest.raises(AutorizacionVigente):
        otorgar_autorizacion_consumo(_solicitud(CalidadOtorgante.TITULAR), "0.10", RelojFijo(AHORA), repo)
    assert repo.guardadas == []
