"""MATU-41 · El envío simulado de los avisos y el armado de la tarea (decisión 112). Sin base.

El registro guarda notificacion_id, usuario_id, canal y plantilla, nunca el destino ni el texto, y no
escribe en los logs de la aplicación. Sin ENVIADOR_AVISOS la tarea no arma consumidores y no toma eventos.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Configuracion
from app.modules.consumption.events import QUIEBRE_PROXIMO
from app.modules.notifications.application.ports import EnvioCorreo, EnvioPush
from app.modules.notifications.domain.aviso import PLANTILLA_QUIEBRE, Canal, ResultadoEnvio
from app.modules.notifications.domain.mensaje import correo_quiebre
from app.modules.notifications.infrastructure import tarea_avisos
from app.modules.notifications.infrastructure.enviadores_simulados import (
    EnviadorCorreoSimulado,
    EnviadorPushSimulado,
    RegistroAvisosSimulado,
)
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-39")

EMAIL = "carmen.soto.simulado@correo.ejemplo"
TOKEN = "https://fcm.googleapis.com/fcm/send/token-sintetico-simulado"
ORIGEN = "https://matu.example"


def _enviar(registro: RegistroAvisosSimulado) -> tuple[uuid.UUID, uuid.UUID]:
    notificacion, usuario = uuid.uuid4(), uuid.uuid4()
    correo = EnviadorCorreoSimulado(registro).enviar(
        EnvioCorreo(notificacion, usuario, PLANTILLA_QUIEBRE, EMAIL, correo_quiebre(ORIGEN))
    )
    push = EnviadorPushSimulado(registro).enviar(
        EnvioPush(notificacion, usuario, PLANTILLA_QUIEBRE, TOKEN)
    )
    assert correo is push is ResultadoEnvio.ENVIADO
    return notificacion, usuario


def test_el_registro_simulado_no_guarda_el_destino_ni_el_texto(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    archivo = tmp_path / ".dev" / "avisos.jsonl"
    registro = RegistroAvisosSimulado(RelojFijo(datetime(2026, 10, 20, 12, 0, tzinfo=UTC)), archivo)

    with caplog.at_level(logging.DEBUG):
        notificacion, usuario = _enviar(registro)

    contenido = archivo.read_text(encoding="utf-8")
    lineas = [json.loads(linea) for linea in contenido.splitlines()]
    assert [set(linea) for linea in lineas] == [{"en", "notificacion_id", "usuario_id", "canal", "plantilla"}] * 2
    assert [(linea["canal"], linea["plantilla"]) for linea in lineas] == [
        ("correo", "quiebre_proximo"), ("push", "quiebre_proximo")
    ]
    assert {linea["notificacion_id"] for linea in lineas} == {str(notificacion)}
    assert {linea["usuario_id"] for linea in lineas} == {str(usuario)}
    for prohibido in (EMAIL, TOKEN, "insumo", "Abrir MATU", ORIGEN):
        assert prohibido not in contenido
    # Nunca escribe en los logs de la aplicación
    assert caplog.records == []
    assert [e.canal for e in registro.enviados] == [Canal.CORREO, Canal.PUSH]


def test_sin_archivo_queda_solo_en_memoria(tmp_path: Path) -> None:
    registro = RegistroAvisosSimulado(RelojFijo(datetime(2026, 10, 20, 12, 0, tzinfo=UTC)))
    _enviar(registro)
    assert len(registro.enviados) == 2 and list(tmp_path.iterdir()) == []


def test_ningun_repr_muestra_el_destino() -> None:
    registro = RegistroAvisosSimulado(RelojFijo(datetime(2026, 10, 20, 12, 0, tzinfo=UTC)))
    envio_correo = EnvioCorreo(uuid.uuid4(), uuid.uuid4(), PLANTILLA_QUIEBRE, EMAIL, correo_quiebre(ORIGEN))
    envio_push = EnvioPush(uuid.uuid4(), uuid.uuid4(), PLANTILLA_QUIEBRE, TOKEN)
    textos = [
        repr(registro), repr(EnviadorCorreoSimulado(registro)), repr(EnviadorPushSimulado(registro)),
        repr(envio_correo), repr(envio_push), str(envio_correo),
    ]
    for texto in textos:
        assert EMAIL not in texto and TOKEN not in texto and "insumo" not in texto


def _config(**valores: object) -> Configuracion:
    return Configuracion.model_validate({"politica_version": "0.10", **valores})


def test_sin_enviador_avisos_la_tarea_no_arma_consumidores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIADOR_AVISOS", raising=False)
    assert tarea_avisos.consumidores(_config(enviador_avisos=None), None, RelojFijo(datetime.now(UTC))) is None  # type: ignore[arg-type]


def test_sin_enviador_avisos_ejecutar_no_toma_eventos(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_publicar(*_: object, **__: object) -> None:
        raise AssertionError("sin ENVIADOR_AVISOS no se toma ningún evento")

    monkeypatch.setattr(tarea_avisos, "publicar_pendientes", no_publicar)
    config = _config(enviador_avisos=None)
    assert tarea_avisos.ejecutar(config, None, None, RelojFijo(datetime.now(UTC))) is None  # type: ignore[arg-type]


def test_con_simulado_la_tarea_consume_quiebre_proximo(tmp_path: Path) -> None:
    config = _config(enviador_avisos="simulado", registro_avisos=tmp_path / "avisos.jsonl", origen_web=ORIGEN)
    mapa = tarea_avisos.consumidores(config, None, RelojFijo(datetime.now(UTC)))  # type: ignore[arg-type]
    assert mapa is not None and list(mapa) == [QUIEBRE_PROXIMO]
    assert [c.nombre for c in mapa[QUIEBRE_PROXIMO]] == ["notifications.quiebre_proximo"]


def test_el_registro_por_omision_va_en_dev() -> None:
    assert tarea_avisos.REGISTRO_POR_OMISION.parent.name == ".dev"
