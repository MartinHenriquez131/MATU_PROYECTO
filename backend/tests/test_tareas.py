"""MATU-74 · El programador de tareas: python -m app.tareas <tarea> y todas_diarias.

Las primeras pruebas no tocan la base: cambian las tareas por dobles y verifican el orden, que una tarea
que falla no detiene a las demás, el código de salida y que el log no lleve el mensaje de la excepción
(condiciones a y R1 del analista). Las de integración corren las tareas reales contra PostgreSQL, con un
reloj fijo y solo datos sintéticos, y verifican que una segunda corrida no repite nada: el trabajo de cada grupo
como matu_app y las funciones como matu_scheduler y matu_publisher (migración 0022, H2), con las sesiones de
tests/base_datos.py. La conexión propia de cada rol (SCHEDULER_DATABASE_URL y PUBLISHER_DATABASE_URL) la prueba
test_cada_tarea_se_conecta_con_su_rol, que se salta sin esas variables.
"""

import io
import json
import logging
import subprocess
import sys
import time
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
from tests.base_datos import DSN, fabrica_publisher, fabrica_scheduler, requiere_base
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


def _contexto(fabrica: Any = None, scheduler: Any = None, publisher: Any = None, config: Any = None) -> tareas.Contexto:
    return tareas.Contexto(
        config=config or obtener_configuracion(),
        fabrica=fabrica,
        reloj=RelojFijo(INICIO),
        fabrica_scheduler=scheduler,
        fabrica_publisher=publisher,
    )


def _lineas(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(linea) for linea in stream.getvalue().splitlines() if linea.strip()]


def _corridas(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "matu.tareas"]


# --- Sin base: orden, fallas y log ---------------------------------------------------------------------


def test_todas_diarias_corre_los_borrados_antes_que_los_quiebres() -> None:
    assert tareas.nombres_de("todas_diarias") == tareas.DIARIAS
    assert tareas.DIARIAS[-1] == "quiebres"
    # avisos y conciliacion_pagos (MATU-62) corren cada 5 minutos, no en la corrida diaria
    assert set(tareas.DIARIAS) == set(tareas.TAREAS) - {"avisos", "conciliacion_pagos", "despacho"}
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
    monkeypatch.setattr(tareas, "fabrica_tareas", lambda config: None)
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
        ("conservacion_pedidos", "ok"),
        ("conservacion_invitaciones", "ok"),
        ("conservacion_relevo", "ok"),
        ("quiebres", "ok"),
    ]
    fallo = lineas[1]
    assert fallo["tipo_error"] == "RuntimeError" and fallo["nivel"] == "ERROR"
    assert "traza" not in fallo and "contadores" not in fallo
    # Todas las líneas de la invocación comparten la corrida, que es también su request_id
    assert len({x["corrida"] for x in lineas}) == 1 and all(x["request_id"] == x["corrida"] for x in lineas)
    for linea in lineas:
        assert {"inicio", "fin", "duracion_ms"} <= set(linea)


@pytest.mark.rf("RF-12")
@pytest.mark.parametrize(("fallidos", "resultado", "codigo"), [(1, "fallo", 1), (0, "ok", 0)])
def test_quiebres_con_un_grupo_fallido_queda_fallo_y_sale_con_uno_pero_procesa_los_demas(
    fallidos: int, resultado: str, codigo: int, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.modules.consumption.application.conservacion import ResultadoConservacionQuiebres
    from app.modules.consumption.application.trabajo_diario import ResultadoTrabajo
    from app.modules.consumption.infrastructure import tarea_quiebres

    grupos = [uuid.uuid4(), uuid.uuid4()]
    procesados: list[uuid.UUID] = []

    def recalcular(fabrica: Any, grupo_id: uuid.UUID, reloj: Any) -> ResultadoTrabajo:
        procesados.append(grupo_id)
        if grupo_id == grupos[0] and fallidos:
            raise LookupError(str(grupo_id))
        return ResultadoTrabajo(materializadas=1, descartadas=0)

    monkeypatch.setattr(tarea_quiebres, "grupos_activos", lambda fabrica: grupos)
    monkeypatch.setattr(tarea_quiebres, "recalcular_grupo", recalcular)
    monkeypatch.setattr(tarea_quiebres, "conservar_quiebres", lambda **_: ResultadoConservacionQuiebres(0, 0, 0, 0))
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(["quiebres"], _contexto(scheduler=object())) == codigo
    assert procesados == grupos
    [registro] = _corridas(caplog)
    assert registro.__dict__["resultado"] == resultado
    assert registro.levelname == ("ERROR" if fallidos else "INFO")
    contadores = registro.__dict__["contadores"]
    assert (contadores["grupos"], contadores["grupos_fallidos"]) == (2, fallidos)
    assert contadores["materializadas"] == 2 - fallidos
    assert all(str(g) not in FormateadorJSON().format(r) for r in caplog.records for g in grupos)


def test_el_engine_de_las_tareas_lleva_un_tope_de_conexion(monkeypatch: pytest.MonkeyPatch) -> None:
    recibido: dict[str, Any] = {}

    def crear(url: str, **opciones: Any) -> Any:
        recibido.update(opciones)
        return None

    monkeypatch.setattr(tareas, "create_engine", crear)
    config = obtener_configuracion().model_copy(update={"database_url": "postgresql+psycopg://u@db.invalid/x"})
    tareas.fabrica_tareas(config)
    assert recibido.pop("connect_args") == {"connect_timeout": tareas.TIEMPO_CONEXION_S}
    assert 0 < tareas.TIEMPO_CONEXION_S <= 10
    # Las conexiones de los roles de las tareas llevan el mismo tope
    for rol in (tareas.ROL_SCHEDULER, tareas.ROL_PUBLISHER):
        assert tareas.fabrica_de_rol(f"postgresql+psycopg://{rol}@db.invalid/x", rol) is not None
        assert recibido.pop("connect_args") == {"connect_timeout": tareas.TIEMPO_CONEXION_S}


def test_con_la_base_inalcanzable_la_tarea_falla_pronto(caplog: pytest.LogCaptureFixture) -> None:
    # 10.255.255.1 no se enruta: sin tope, la conexión espera lo que dé el sistema operativo (~130 s)
    url = "postgresql+psycopg://matu_app@10.255.255.1:5432/matu_inalcanzable"
    config = obtener_configuracion().model_copy(update={"database_url": url})
    scheduler = tareas.fabrica_de_rol(url.replace("matu_app@", "matu_scheduler@"), tareas.ROL_SCHEDULER)
    ctx = _contexto(tareas.fabrica_tareas(config), scheduler=scheduler, config=config)
    inicio = time.monotonic()
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(["conservacion_sesiones"], ctx) == tareas.SALIDA_FALLO
    assert time.monotonic() - inicio < 20
    [registro] = _corridas(caplog)
    assert registro.__dict__["resultado"] == "fallo"


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

    def falla(config: Any) -> None:
        raise ValueError(f"Could not parse SQLAlchemy URL from string '{url_sintetica}'")

    monkeypatch.setattr(tareas, "fabrica_tareas", falla)
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
    ctx = _contexto(fabrica_sesiones(), scheduler=fabrica_scheduler())

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
    ctx = _contexto(fabrica_sesiones(), fabrica_scheduler(), fabrica_publisher(), config)

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
    ctx = _contexto(fabrica_sesiones(), config=config)
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr(["avisos"], ctx) == tareas.SALIDA_OK
    [registro] = _corridas(caplog)
    assert registro.__dict__["resultado"] == "apagada"


# --- MATU-74, hallazgo H2: cada tarea con la conexión de su rol --------------------------------------------------


class _Prohibida:
    """Una fábrica de matu_app que la tarea no debe usar: falla si se abre una sesión."""

    def __call__(self, **_: Any) -> Any:
        raise AssertionError("la tarea abrió una sesión que no le corresponde")


@pytest.mark.parametrize(
    ("tarea", "variable"),
    [
        ("destruccion_fichas", "SCHEDULER_DATABASE_URL"),
        ("conservacion_consumo", "SCHEDULER_DATABASE_URL"),
        ("conservacion_sesiones", "SCHEDULER_DATABASE_URL"),
        ("conservacion_pedidos", "SCHEDULER_DATABASE_URL"),
        ("conservacion_invitaciones", "SCHEDULER_DATABASE_URL"),
        ("conservacion_relevo", "SCHEDULER_DATABASE_URL"),
        ("quiebres", "SCHEDULER_DATABASE_URL"),
        ("avisos", "PUBLISHER_DATABASE_URL"),
        # MATU-62: pagos_por_conciliar es solo de matu_scheduler
        ("conciliacion_pagos", "SCHEDULER_DATABASE_URL"),
    ],
)
def test_sin_la_conexion_de_su_rol_la_tarea_falla_y_nombra_la_variable(
    tarea: str, variable: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Nunca cae a matu_app: la fábrica de matu_app ni se abre, y la línea nombra la variable, sin su valor."""
    config = obtener_configuracion().model_copy(update={"enviador_avisos": "simulado"})
    with caplog.at_level(logging.INFO, logger="matu.tareas"):
        assert tareas.correr([tarea], _contexto(_Prohibida(), config=config)) == tareas.SALIDA_FALLO
    [registro] = _corridas(caplog)
    linea = json.loads(FormateadorJSON().format(registro))
    assert (linea["resultado"], linea["tipo_error"], linea["falta"]) == ("fallo", "FaltaConexion", variable)


def test_la_conexion_de_un_rol_no_acepta_la_url_de_otro_usuario(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tareas, "create_engine", lambda url, **_: None)
    rol = tareas.ROL_SCHEDULER
    assert tareas.fabrica_de_rol("", rol) is None
    assert tareas.fabrica_de_rol("postgresql+psycopg://matu_app@db.invalid/matu", rol) is None  # DATABASE_URL copiada
    assert tareas.fabrica_de_rol("postgresql+psycopg://matu_publisher@db.invalid/matu", rol) is None
    assert tareas.fabrica_de_rol("esto no es una url", rol) is None
    assert tareas.fabrica_de_rol("postgresql+psycopg://matu_scheduler@db.invalid/matu", rol) is not None


def test_main_arma_cada_conexion_con_su_variable(monkeypatch: pytest.MonkeyPatch, logs_restaurados: None) -> None:
    vistos: list[tareas.Contexto] = []

    def espia(ctx: tareas.Contexto) -> tareas.Salida:
        vistos.append(ctx)
        return tareas.Salida(tareas.OK, {})

    roles = ("matu_app", "matu_scheduler", "matu_publisher")
    urls = {rol: f"postgresql+psycopg://{rol}@db.invalid/matu" for rol in roles}
    config = obtener_configuracion().model_copy(update={
        "database_url": urls["matu_app"],
        "scheduler_database_url": urls["matu_scheduler"],
        "publisher_database_url": urls["matu_publisher"],
    })
    monkeypatch.setattr(tareas, "obtener_configuracion", lambda: config)
    monkeypatch.setattr(tareas, "create_engine", lambda url, **_: url)
    monkeypatch.setitem(tareas.TAREAS, "avisos", espia)

    assert tareas.main(["avisos"], stream=io.StringIO()) == tareas.SALIDA_OK

    [ctx] = vistos
    assert ctx.fabrica.kw["bind"] == urls["matu_app"]
    assert ctx.scheduler().kw["bind"] == urls["matu_scheduler"]
    assert ctx.publisher().kw["bind"] == urls["matu_publisher"]


class _Espia:
    """Cuenta las sesiones que la tarea abre con una fábrica."""

    def __init__(self, fabrica: Any) -> None:
        self._fabrica = fabrica
        self.sesiones = 0

    def __call__(self, **opciones: Any) -> Any:
        self.sesiones += 1
        return self._fabrica(**opciones)


_CONFIG = obtener_configuracion()
requiere_roles = pytest.mark.skipif(
    not (_CONFIG.scheduler_database_url and _CONFIG.publisher_database_url),
    reason="SCHEDULER_DATABASE_URL o PUBLISHER_DATABASE_URL no están definidas",
)


@requiere_base
@requiere_roles
@pytest.mark.rf("RF-02")
@pytest.mark.rf("RF-39")
def test_cada_tarea_se_conecta_con_su_rol(fabrica: Fabrica, tmp_path: Path) -> None:
    """Con las URL de .env, como el cron: cada conexión es de su rol (current_user), y cada tarea abre sesiones
    solo con las que le tocan."""
    from sqlalchemy import text

    config = _CONFIG.model_copy(
        update={
            "enviador_avisos": "simulado",
            "registro_avisos": tmp_path / "avisos.jsonl",
            # MATU-62: con una pasarela, la conciliación lista lo pendiente con matu_scheduler
            "pasarela_pago": "falsa",
        }
    )
    conexiones = {
        "matu_app": tareas.fabrica_tareas(config),
        "matu_scheduler": tareas.fabrica_de_rol(config.scheduler_database_url, tareas.ROL_SCHEDULER),
        "matu_publisher": tareas.fabrica_de_rol(config.publisher_database_url, tareas.ROL_PUBLISHER),
    }
    for rol, fabrica_rol in conexiones.items():
        assert fabrica_rol is not None, rol
        with fabrica_rol() as sesion:
            assert sesion.execute(text("SELECT current_user")).scalar_one() == rol
    familia = fabrica.familia()
    fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin, otorgado_en=INICIO)
    fabrica.perfil_consumo(familia.persona)

    usa = {
        "destruccion_fichas": {"matu_scheduler"},
        "conservacion_consumo": {"matu_scheduler"},
        "conservacion_sesiones": {"matu_scheduler"},
        "conservacion_pedidos": {"matu_scheduler"},
        "conservacion_invitaciones": {"matu_scheduler"},
        "conservacion_relevo": {"matu_scheduler"},
        "quiebres": {"matu_app", "matu_scheduler"},
        "avisos": {"matu_app", "matu_publisher"},
        # MATU-62: pagos_por_conciliar con matu_scheduler; sin ventas por cerrar no abre matu_app
        "conciliacion_pagos": {"matu_scheduler"},
    }
    for tarea, esperadas in usa.items():
        espias = {rol: _Espia(f) for rol, f in conexiones.items()}
        ctx = tareas.Contexto(
            config=config,
            fabrica=espias["matu_app"],  # type: ignore[arg-type]
            reloj=RelojFijo(INICIO),
            fabrica_scheduler=espias["matu_scheduler"],  # type: ignore[arg-type]
            fabrica_publisher=espias["matu_publisher"],  # type: ignore[arg-type]
        )
        assert tareas.correr([tarea], ctx) == tareas.SALIDA_OK, tarea
        usadas = {rol for rol, e in espias.items() if e.sesiones}
        if tarea == "conciliacion_pagos":
            # Si quedara una venta por cerrar en la base, también abre matu_app (app.rol = 'sistema') para cerrarla
            assert "matu_scheduler" in usadas and usadas <= {"matu_app", "matu_scheduler"}, tarea
        else:
            assert usadas == esperadas, tarea


# --- MATU-74, hallazgo H4: en staging el registro de los avisos es la tabla notificacion ---------------------------


@requiere_base
@pytest.mark.rf("RF-39")
def test_en_staging_los_avisos_no_escriben_el_archivo_y_quedan_en_notificacion(
    fabrica: Fabrica, tmp_path: Path
) -> None:
    familia = fabrica.familia()
    fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin, otorgado_en=INICIO)
    fabrica.perfil_consumo(familia.persona)
    registro = tmp_path / "avisos.jsonl"
    config = obtener_configuracion().model_copy(
        update={"entorno": "staging", "enviador_avisos": "simulado", "registro_avisos": registro}
    )
    ctx = _contexto(fabrica_sesiones(), fabrica_scheduler(), fabrica_publisher(), config)

    assert tareas.correr(["quiebres"], ctx) == tareas.SALIDA_OK
    assert tareas.correr(["avisos"], ctx) == tareas.SALIDA_OK

    assert not registro.exists() and list(tmp_path.iterdir()) == []
    enviadas = _filas(
        "SELECT usuario_id, canal FROM notificacion WHERE grupo_id = %s AND estado = 'enviada'"
        " AND enviada_en IS NOT NULL",
        familia.grupo.id,
    )
    assert (familia.admin.id, "correo") in enviadas


@pytest.mark.parametrize(("entorno", "escribe"), [("local", True), ("pruebas", True), ("staging", False)])
def test_el_archivo_del_registro_de_avisos_es_solo_local_y_de_pruebas(
    entorno: str, escribe: bool, tmp_path: Path
) -> None:
    from app.modules.notifications.infrastructure import tarea_avisos

    archivo = tmp_path / "avisos.jsonl"
    config = obtener_configuracion().model_copy(update={"entorno": entorno, "registro_avisos": archivo})
    assert tarea_avisos.archivo_del_registro(config) == (archivo if escribe else None)


# --- MATU-74, hallazgos H3 y H5 (condición C17): los horarios, en verano y en invierno -----------------------------


def _hora_minuto(cron: str) -> tuple[int, int]:
    minuto, hora, *resto = cron.split()
    assert resto == ["*", "*", "*"], cron
    return int(hora), int(minuto)


def test_los_horarios_caen_de_madrugada_y_separados_en_verano_y_en_invierno() -> None:
    """Cada día de un año, con los cambios de hora de Chile: los borrados entre las 00:00 y las 06:59, los quiebres
    al menos 60 minutos después y con una hora para terminar antes de las 07:00, y los avisos cada 5 minutos."""
    from datetime import date, time, timedelta
    from zoneinfo import ZoneInfo

    chile = ZoneInfo("America/Santiago")
    assert tareas.HORARIOS["avisos"] == "*/5 * * * *"
    borrados, quiebres = _hora_minuto(tareas.HORARIOS["borrados"]), _hora_minuto(tareas.HORARIOS["quiebres"])
    desfases: set[timedelta] = set()
    dia = date(2026, 11, 1)
    while dia < date(2027, 11, 1):
        b = datetime(dia.year, dia.month, dia.day, *borrados, tzinfo=UTC).astimezone(chile)
        q = datetime(dia.year, dia.month, dia.day, *quiebres, tzinfo=UTC).astimezone(chile)
        assert time(0, 0) <= b.time() <= time(6, 59), (dia, b)
        assert q - b >= timedelta(minutes=60), (dia, b, q)
        assert b.date() == q.date() and q.time() <= time(6, 0), (dia, q)
        desfases.add(b.utcoffset() or timedelta(0))
        dia += timedelta(days=1)
    # El año cubre las dos temporadas: verano (UTC-3) e invierno (UTC-4)
    assert desfases == {timedelta(hours=-3), timedelta(hours=-4)}


def test_los_readme_dicen_los_mismos_horarios() -> None:
    raiz = BACKEND.parent
    for readme in (BACKEND / "README.md", raiz / "infra" / "railway" / "README.md"):
        texto = readme.read_text(encoding="utf-8")
        for tarea, cron in tareas.HORARIOS.items():
            assert f"`{cron}`" in texto, (readme.name, tarea)
        for viejo in ("`10 6,7 * * *`", "`30 7 * * *`", "`*/15 * * * *`"):
            assert viejo not in texto, (readme.name, viejo)


@requiere_base
@pytest.mark.rf("RF-21")
def test_conservacion_pedidos_corre_con_la_capa_3_apagada() -> None:
    """MATU-61 (decisión 220, política 0.12 §10): con CAPA3_HABILITADA apagada, lo no pagado igual se borra a los 30
    días. La tarea llama a pedido_conservar con matu_scheduler y queda ok, no apagada."""
    config = _CONFIG.model_copy(update={"capa3_habilitada": False})
    espia = _Espia(fabrica_scheduler())
    ctx = tareas.Contexto(
        config=config,
        fabrica=_Prohibida(),  # type: ignore[arg-type]
        reloj=RelojFijo(datetime.now(UTC)),
        fabrica_scheduler=espia,  # type: ignore[arg-type]
    )
    assert tareas.correr(["conservacion_pedidos"], ctx) == tareas.SALIDA_OK
    assert espia.sesiones

