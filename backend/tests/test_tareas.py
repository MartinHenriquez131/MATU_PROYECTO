"""MATU-74 · El programador de tareas: python -m app.tareas <tarea> y todas_diarias.

Las primeras pruebas no tocan la base: cambian las tareas por dobles y verifican el orden, que una tarea
que falla no detiene a las demás, el código de salida y que el log no lleve el mensaje de la excepción
(condiciones a y R1 del analista). Las de integración corren las tareas reales contra PostgreSQL como
matu_app, con un reloj fijo y solo datos sintéticos, y verifican que una segunda corrida no repite nada.
"""

import io
import json
import logging
import subprocess
import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest

from app import tareas
from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones
from app.core.logs import FormateadorJSON
from tests.base_datos import DSN, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import Fabrica

BACKEND = Path(__file__).resolve().parents[1]
# 09:00 en Santiago: el trabajo diario y los avisos ya pueden correr
INICIO = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


@pytest.fixture
def logs_restaurados() -> Iterator[None]:
    """main() configura el log raíz: se devuelve como estaba para no afectar a las demás pruebas."""
    raiz = logging.getLogger()
    manejadores, nivel = list(raiz.handlers), raiz.level
    yield
    raiz.handlers, raiz.level = manejadores, nivel


def _contexto(fabrica: Any = None) -> tareas.Contexto:
    return tareas.Contexto(config=obtener_configuracion(), fabrica=fabrica, reloj=RelojFijo(INICIO))


def _lineas(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(linea) for linea in stream.getvalue().splitlines() if linea.strip()]


def _corridas(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "matu.tareas"]


# --- Sin base: orden, fallas y log ---------------------------------------------------------------------


def test_todas_diarias_corre_los_borrados_antes_que_los_quiebres() -> None:
    assert tareas.nombres_de("todas_diarias") == tareas.DIARIAS
    assert tareas.DIARIAS[-1] == "quiebres"
    assert set(tareas.DIARIAS) == set(tareas.TAREAS) - {"avisos"}
    assert tareas.nombres_de("borrados") == tareas.DIARIAS[:-1]


@pytest.mark.parametrize("argv", [["no_existe"], [], ["quiebres", "avisos"], ["QUIEBRES"]])
def test_un_nombre_desconocido_sale_con_codigo_distinto_de_cero(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert tareas.main(argv) == tareas.SALIDA_USO
    salida = capsys.readouterr()
    assert salida.out == ""
    assert "uso: python -m app.tareas" in salida.err and "todas_diarias" in salida.err
    assert "no_existe" not in salida.err  # no repite lo recibido


def test_el_modulo_se_invoca_con_python_m_y_un_nombre_desconocido_falla() -> None:
    proceso = subprocess.run(
        [sys.executable, "-m", "app.tareas", "no_existe"], cwd=BACKEND, capture_output=True, text=True, timeout=60
    )
    assert proceso.returncode == tareas.SALIDA_USO
    assert "Traceback" not in proceso.stderr and "uso: python -m app.tareas" in proceso.stderr


def test_una_tarea_que_falla_no_detiene_a_las_demas_y_el_log_no_lleva_su_mensaje(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], logs_restaurados: None
) -> None:
    secreto = str(uuid.uuid4())
    corridas: list[str] = []

    def doble(nombre: str, falla: bool = False) -> tareas.Tarea:
        def tarea(ctx: tareas.Contexto) -> tareas.Salida:
            corridas.append(nombre)
            if falla:
                # Como un error de SQLAlchemy, que trae los parámetros de la sentencia
                raise RuntimeError(f"(psycopg.errors.Algo) [parameters: {{'grupo_id': '{secreto}'}}]")
            return tareas.Salida(tareas.OK, {"borrados": 0})

        return tarea

    for nombre in tareas.DIARIAS:
        monkeypatch.setitem(tareas.TAREAS, nombre, doble(nombre, falla=nombre == "conservacion_consumo"))
    monkeypatch.setattr(tareas, "fabrica_sesiones", lambda: None)
    stream = io.StringIO()

    codigo = tareas.main(["todas_diarias"], stream=stream)

    assert codigo == tareas.SALIDA_FALLO
    assert corridas == list(tareas.DIARIAS)
    # R1: ni el mensaje ni la traza, en ningún stream
    capturado = capsys.readouterr()
    for texto in (stream.getvalue(), capturado.out, capturado.err):
        assert secreto not in texto and "parameters" not in texto and "Traceback" not in texto
    lineas = _lineas(stream)
    assert [(x["tarea"], x["resultado"]) for x in lineas] == [
        ("destruccion_fichas", "ok"),
        ("conservacion_consumo", "fallo"),
        ("conservacion_sesiones", "ok"),
        ("quiebres", "ok"),
    ]
    fallo = lineas[1]
    assert fallo["tipo_error"] == "RuntimeError" and fallo["nivel"] == "ERROR"
    assert "traza" not in fallo and "contadores" not in fallo
    # Todas las líneas de la invocación comparten la corrida, que es también su request_id
    assert len({x["corrida"] for x in lineas}) == 1 and all(x["request_id"] == x["corrida"] for x in lineas)
    for linea in lineas:
        assert {"inicio", "fin", "duracion_ms"} <= set(linea)


def test_si_todas_terminan_el_codigo_es_cero(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setitem(tareas.TAREAS, "avisos", lambda ctx: tareas.Salida(tareas.APAGADA, {}))
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(["avisos"], _contexto()) == tareas.SALIDA_OK
    [registro] = _corridas(caplog)
    assert registro.__dict__["resultado"] == "apagada" and registro.__dict__["contadores"] == {}


def test_una_configuracion_invalida_sale_distinto_de_cero_sin_su_mensaje(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], logs_restaurados: None
) -> None:
    url_sintetica = "postgresql://matu_app:" + uuid.uuid4().hex + "@localhost/matu"

    def falla() -> None:
        raise ValueError(f"Could not parse SQLAlchemy URL from string '{url_sintetica}'")

    monkeypatch.setattr(tareas, "fabrica_sesiones", falla)
    stream = io.StringIO()
    assert tareas.main(["quiebres"], stream=stream) == tareas.SALIDA_FALLO
    [linea] = _lineas(stream)
    assert (linea["tarea"], linea["resultado"], linea["tipo_error"]) == ("arranque", "fallo", "ValueError")
    capturado = capsys.readouterr()
    for texto in (stream.getvalue(), capturado.out, capturado.err):
        assert url_sintetica not in texto


def test_la_linea_de_la_corrida_pasa_el_formateador_sin_campos_de_mas(caplog: pytest.LogCaptureFixture) -> None:
    contadores = {"claves_destruidas": 0}
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        tareas.correr_una("destruccion_fichas", lambda ctx: tareas.Salida(tareas.OK, contadores), _contexto(), "c1")
    [registro] = _corridas(caplog)
    linea = json.loads(FormateadorJSON().format(registro))
    assert set(linea) == {
        "ts",
        "nivel",
        "logger",
        "mensaje",
        "request_id",
        "tarea",
        "resultado",
        "corrida",
        "inicio",
        "fin",
        "duracion_ms",
        "contadores",
    }
    assert linea["inicio"] == linea["fin"] == "2026-10-20T12:00:00+00:00"
    assert linea["contadores"] == contadores


# --- Con base: las tareas reales -----------------------------------------------------------------------


def _contadores(caplog: pytest.LogCaptureFixture) -> dict[str, dict[str, int]]:
    registros = _corridas(caplog)
    assert all(r.__dict__["resultado"] in ("ok", "apagada") for r in registros), [
        (r.__dict__["tarea"], r.__dict__.get("tipo_error")) for r in registros
    ]
    return {r.__dict__["tarea"]: r.__dict__["contadores"] for r in registros}


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


@requiere_base
@pytest.mark.rf("RF-12")
@pytest.mark.rf("RF-10")
@pytest.mark.rf("RF-02")
def test_todas_diarias_corre_cada_tarea_y_una_segunda_corrida_no_repite_nada(
    fabrica: Fabrica, caplog: pytest.LogCaptureFixture
) -> None:
    familia = fabrica.familia()
    fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin, otorgado_en=INICIO)
    perfil = fabrica.perfil_consumo(familia.persona)
    ctx = _contexto(fabrica_sesiones())

    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(tareas.nombres_de("todas_diarias") or (), ctx) == tareas.SALIDA_OK
    primera = _contadores(caplog)
    assert list(primera) == list(tareas.DIARIAS)
    assert primera["quiebres"]["materializadas"] >= 1 and primera["quiebres"]["grupos_fallidos"] == 0
    assert _filas("SELECT estado FROM alerta_quiebre WHERE perfil_id = %s", perfil) == [("pendiente",)]
    assert len(_filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id)) == 1

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(tareas.DIARIAS, ctx) == tareas.SALIDA_OK
    segunda = _contadores(caplog)
    # Solo "grupos" cuenta lo que hay; todo lo demás es lo que la corrida hizo, y la segunda no hace nada
    assert {t: {k: v for k, v in c.items() if k != "grupos"} for t, c in segunda.items()} == {
        t: dict.fromkeys((k for k in c if k != "grupos"), 0) for t, c in primera.items()
    }
    assert _filas("SELECT estado FROM alerta_quiebre WHERE perfil_id = %s", perfil) == [("pendiente",)]
    assert len(_filas("SELECT 1 FROM evento_outbox WHERE grupo_id = %s", familia.grupo.id)) == 1
    # El log de la corrida no lleva identificadores de la familia ni el nombre del insumo
    texto = "\n".join(FormateadorJSON().format(r) for r in caplog.records)
    for dato in (familia.grupo.id, familia.persona.id, familia.admin.id, perfil):
        assert str(dato) not in texto
    assert familia.admin.email not in texto and "Pañal" not in texto


@requiere_base
@pytest.mark.rf("RF-39")
def test_avisos_publica_al_archivo_simulado_nunca_a_stdout_y_no_repite(
    fabrica: Fabrica, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    familia = fabrica.familia()
    fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin, otorgado_en=INICIO)
    fabrica.perfil_consumo(familia.persona)
    registro = tmp_path / "avisos.jsonl"
    config = obtener_configuracion().model_copy(update={"enviador_avisos": "simulado", "registro_avisos": registro})
    ctx = tareas.Contexto(config=config, fabrica=fabrica_sesiones(), reloj=RelojFijo(INICIO))

    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(["quiebres"], ctx) == tareas.SALIDA_OK
        assert tareas.correr(["avisos"], ctx) == tareas.SALIDA_OK
    assert _contadores(caplog)["avisos"]["publicados"] >= 1
    # El simulado escribe al archivo (usuario y plantilla, nunca el destino ni el texto)
    enviados = registro.read_text(encoding="utf-8")
    assert str(familia.admin.id) in enviados and familia.admin.email not in enviados

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(["avisos"], ctx) == tareas.SALIDA_OK
    assert _contadores(caplog)["avisos"] == {"publicados": 0, "reintentos": 0, "fallidos": 0, "pospuestos": 0}
    assert registro.read_text(encoding="utf-8") == enviados
    # ...y nunca a stdout ni stderr
    capturado = capsys.readouterr()
    assert str(familia.admin.id) not in capturado.out + capturado.err
    assert familia.admin.email not in capturado.out + capturado.err


@requiere_base
def test_avisos_sin_enviador_queda_apagada_y_no_toma_eventos(caplog: pytest.LogCaptureFixture) -> None:
    config = obtener_configuracion().model_copy(update={"enviador_avisos": None})
    ctx = tareas.Contexto(config=config, fabrica=fabrica_sesiones(), reloj=RelojFijo(INICIO))
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(["avisos"], ctx) == tareas.SALIDA_OK
    [registro] = _corridas(caplog)
    assert registro.__dict__["resultado"] == "apagada"
