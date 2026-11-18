"""MATU-81 · Las reglas del PATCH de una incidencia (C13) con la resolución cifrada (decisión 471): la regla solo sabe
si hay una resolución guardada, y devuelve el texto nuevo que hay que cifrar. Sin base."""

from datetime import UTC, datetime

import pytest

from app.modules.backoffice.application.consola import FaltaResolucion, IncidenciaResuelta, nuevo_estado_incidencia

pytestmark = pytest.mark.rf("RF-40")

AHORA = datetime(2026, 11, 17, 12, tzinfo=UTC)


def test_resolver_exige_una_resolucion_nueva_o_una_ya_guardada() -> None:
    # Sin resolución guardada ni nueva: 422
    with pytest.raises(FaltaResolucion):
        nuevo_estado_incidencia("en_gestion", False, "resuelta", None, AHORA)
    # Con una guardada (cifrada), resolver no la reescribe
    cambio = nuevo_estado_incidencia("en_gestion", True, "resuelta", None, AHORA)
    assert (cambio.estado, cambio.resolucion, cambio.resuelta_en, cambio.resuelve) == ("resuelta", None, AHORA, True)
    # Una nueva se cifra y se guarda; el texto no sale en el repr
    cambio = nuevo_estado_incidencia("abierta", False, None, "Se devolvió lo que faltó", AHORA)
    assert (cambio.estado, cambio.resolucion, cambio.resuelve) == ("abierta", "Se devolvió lo que faltó", False)
    assert "Se devolvió" not in repr(cambio)
    with pytest.raises(IncidenciaResuelta):
        nuevo_estado_incidencia("resuelta", True, "abierta", None, AHORA)
