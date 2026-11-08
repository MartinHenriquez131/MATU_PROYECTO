"""Programador de tareas de MATU (MATU-74): un punto de entrada para que las tareas corran solas.

Ejecutar desde backend/, con DATABASE_URL de matu_app (el cron del servicio lo invoca igual):

    python -m app.tareas <tarea>

Tareas:

- destruccion_fichas: claves de las fichas retiradas hace 90 días (care_plan, MATU-44).
- conservacion_consumo: perfiles de consumo a los 90 días de terminar la autorización (MATU-36).
- conservacion_sesiones: sesiones y dispositivos vencidos (iam, MATU-38).
- quiebres: el trabajo diario de la predicción de quiebre y la conservación de alertas, eventos,
  notificaciones y compras (MATU-37 y MATU-51).
- avisos: el publicador del outbox con el consumidor de avisos (MATU-41). Sin ENVIADOR_AVISOS no toma
  ningún evento y la corrida queda como "apagada".
- borrados: las tres de borrado (destruccion_fichas, conservacion_consumo y conservacion_sesiones).
- todas_diarias: los borrados y después los quiebres, en ese orden.

Cada tarea reutiliza el ``ejecutar`` de su módulo y se conecta como matu_app con el app.rol que ya usa
(operacion, y sistema por grupo en los quiebres y los avisos). matu_scheduler y matu_publisher no alcanzan:
no tienen credenciales en la infraestructura del semestre y las funciones SECURITY DEFINER dan EXECUTE
solo a matu_app (migraciones 0008, 0009, 0011, 0014 y 0016).

Condiciones del analista normativo (MATU-74):

- Cada tarea corre en su propio try: una que falla no detiene a las demás. Si alguna falla, el proceso
  sale con código 1. Un nombre desconocido sale con código 2, sin tocar la base.
- De una excepción se registra solo su tipo. Nunca su mensaje ni su traza, a ningún stream: los errores
  de SQLAlchemy traen los parámetros de la sentencia, como un grupo_id.
- Una línea JSON por corrida con tarea, resultado, corrida (un id al azar por invocación, también como
  request_id), inicio, fin, duracion_ms y los contadores de la tarea. Nunca un id de usuario, persona o
  grupo, un correo, un teléfono, un token, texto de la ficha ni el nombre de un insumo.
"""

import logging
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TextIO

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Configuracion, obtener_configuracion
from app.core.db import fabrica_sesiones
from app.core.logs import configurar_logs, request_id_actual
from app.modules.care_plan.infrastructure import tarea_destruccion
from app.modules.consumption.infrastructure import tarea_conservacion as tarea_conservacion_consumo
from app.modules.consumption.infrastructure import tarea_quiebres
from app.modules.iam.infrastructure import tarea_conservacion as tarea_conservacion_sesiones
from app.modules.notifications.infrastructure import tarea_avisos
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.tareas")

SALIDA_OK = 0
SALIDA_FALLO = 1
SALIDA_USO = 2

OK = "ok"
FALLO = "fallo"
APAGADA = "apagada"

TODAS_DIARIAS = "todas_diarias"
BORRADOS = "borrados"


@dataclass(frozen=True)
class Contexto:
    config: Configuracion
    fabrica: sessionmaker[Session]
    reloj: Reloj


@dataclass(frozen=True)
class Salida:
    """Lo que entrega una tarea: su resultado (ok o apagada) y sus contadores, solo cantidades."""

    resultado: str
    contadores: dict[str, int]


Tarea = Callable[[Contexto], Salida]


def _destruccion_fichas(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_destruccion.ejecutar(ctx.fabrica, ctx.reloj)))


def _conservacion_consumo(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_conservacion_consumo.ejecutar(ctx.fabrica, ctx.reloj)))


def _conservacion_sesiones(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_conservacion_sesiones.ejecutar(ctx.fabrica, ctx.reloj)))


def _quiebres(ctx: Contexto) -> Salida:
    trabajo, conservacion = tarea_quiebres.ejecutar(ctx.fabrica, ctx.reloj)
    return Salida(OK, {**asdict(trabajo), **asdict(conservacion)})


def _avisos(ctx: Contexto) -> Salida:
    resultado = tarea_avisos.ejecutar(ctx.config, ctx.fabrica, ctx.reloj)
    return Salida(APAGADA, {}) if resultado is None else Salida(OK, asdict(resultado))


TAREAS: dict[str, Tarea] = {
    "destruccion_fichas": _destruccion_fichas,
    "conservacion_consumo": _conservacion_consumo,
    "conservacion_sesiones": _conservacion_sesiones,
    "quiebres": _quiebres,
    "avisos": _avisos,
}

BORRADOS_DIARIOS: tuple[str, ...] = ("destruccion_fichas", "conservacion_consumo", "conservacion_sesiones")
# Los borrados antes que los quiebres: el trabajo diario no recalcula lo que ya debía borrarse
DIARIAS: tuple[str, ...] = (*BORRADOS_DIARIOS, "quiebres")

# Los nombres que corren varias tareas, cada una en su propio try
GRUPOS: dict[str, tuple[str, ...]] = {BORRADOS: BORRADOS_DIARIOS, TODAS_DIARIAS: DIARIAS}


def _instante(reloj: Reloj) -> str:
    return reloj.ahora().isoformat(timespec="seconds")


def correr_una(nombre: str, tarea: Tarea, ctx: Contexto, corrida: str) -> bool:
    """Corre una tarea y registra su línea. True si terminó sin excepción."""
    inicio = _instante(ctx.reloj)
    t0 = time.perf_counter()
    extra: dict[str, object] = {"tarea": nombre, "corrida": corrida, "inicio": inicio}
    try:
        salida = tarea(ctx)
    except Exception as error:  # noqa: BLE001 - una tarea que falla no detiene a las demás (condición a)
        # R1: solo el tipo, sin exc_info ni str(error): el mensaje puede traer parámetros de la base
        extra.update(resultado=FALLO, tipo_error=type(error).__name__)
        ok = False
    else:
        extra.update(resultado=salida.resultado, contadores=salida.contadores)
        ok = True
    extra.update(fin=_instante(ctx.reloj), duracion_ms=round((time.perf_counter() - t0) * 1000, 1))
    if ok:
        log.info("tarea", extra=extra)
    else:
        log.error("tarea", extra=extra)
    return ok


def correr(nombres: Sequence[str], ctx: Contexto, tareas: Mapping[str, Tarea] = TAREAS) -> int:
    """Corre las tareas en orden, cada una en su propio try. Devuelve el código de salida del proceso."""
    corrida = str(uuid.uuid4())
    token = request_id_actual.set(corrida)
    try:
        resultados = [correr_una(nombre, tareas[nombre], ctx, corrida) for nombre in nombres]
    finally:
        request_id_actual.reset(token)
    return SALIDA_OK if all(resultados) else SALIDA_FALLO


def nombres_de(argumento: str, tareas: Mapping[str, Tarea] = TAREAS) -> tuple[str, ...] | None:
    """Las tareas que pide el argumento, o None si no es una tarea conocida."""
    if argumento in GRUPOS:
        return GRUPOS[argumento]
    return (argumento,) if argumento in tareas else None


def _uso(stream: TextIO) -> None:
    # No repite el argumento recibido: solo la lista de nombres válidos
    opciones = ", ".join([*TAREAS, *GRUPOS])
    print(f"uso: python -m app.tareas <tarea>, con <tarea> una de: {opciones}", file=stream)


def main(argv: Sequence[str] | None = None, *, stream: TextIO | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    nombres = nombres_de(argumentos[0]) if len(argumentos) == 1 else None
    if nombres is None:
        _uso(sys.stderr)
        return SALIDA_USO
    try:
        config = obtener_configuracion()
        # Crea el engine sin conectar: si la base no responde, falla cada tarea en su propio try
        fabrica = fabrica_sesiones()
    except Exception as error:  # noqa: BLE001 - una configuración inválida tampoco deja su mensaje (la URL)
        configurar_logs("INFO", stream)
        extra = {"tarea": "arranque", "resultado": FALLO, "tipo_error": type(error).__name__}
        log.error("tarea", extra={**extra, "corrida": str(uuid.uuid4())})
        return SALIDA_FALLO
    configurar_logs(config.log_nivel, stream)
    return correr(nombres, Contexto(config=config, fabrica=fabrica, reloj=RelojSistema()))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
