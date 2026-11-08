"""MATU-74, condición R2 del analista: si un grupo falla en el trabajo diario, se registra solo el tipo del
error, sin su mensaje, su traza ni el grupo_id, y los demás grupos siguen (RF-12). Sin base: los grupos
y el recálculo por grupo son dobles.
"""

import json
import logging
import uuid
from typing import Any

import pytest

from app.core.logs import FormateadorJSON
from app.modules.consumption.application.trabajo_diario import ResultadoTrabajo
from app.modules.consumption.infrastructure import tarea_quiebres
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-12")


def test_un_grupo_que_falla_se_registra_solo_con_su_tipo_y_los_demas_siguen(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, reloj_fijo: RelojFijo
) -> None:
    falla, sigue = uuid.uuid4(), uuid.uuid4()
    secreto = str(uuid.uuid4())

    def recalcular(fabrica: Any, grupo_id: uuid.UUID, reloj: Any) -> ResultadoTrabajo:
        if grupo_id == falla:
            raise LookupError(f"[parameters: {{'grupo_id': '{grupo_id}', 'perfil': '{secreto}'}}]")
        return ResultadoTrabajo(materializadas=1, descartadas=0)

    monkeypatch.setattr(tarea_quiebres, "grupos_activos", lambda fabrica: [falla, sigue])
    monkeypatch.setattr(tarea_quiebres, "recalcular_grupo", recalcular)

    with caplog.at_level(logging.INFO, logger="matu.consumption.quiebres"):
        resultado = tarea_quiebres.recalcular_todos(None, reloj_fijo)  # type: ignore[arg-type]

    assert resultado == tarea_quiebres.ResultadoTarea(grupos=2, grupos_fallidos=1, materializadas=1, descartadas=0)
    [registro] = [r for r in caplog.records if r.name == "matu.consumption.quiebres"]
    linea = json.loads(FormateadorJSON().format(registro))
    assert linea["nivel"] == "WARNING" and linea["tipo_error"] == "LookupError"
    assert "traza" not in linea and "grupo_id" not in linea
    texto = json.dumps(linea)
    for dato in (str(falla), str(sigue), secreto, "parameters"):
        assert dato not in texto
