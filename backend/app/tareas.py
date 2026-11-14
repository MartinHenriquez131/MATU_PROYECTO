"""Programador de tareas de MATU (MATU-74): un punto de entrada para que las tareas corran solas.

Ejecutar desde backend/ (el cron del servicio lo invoca igual):

    python -m app.tareas <tarea>

Tareas:

- destruccion_fichas: claves de las fichas retiradas hace 90 días (care_plan, MATU-44).
- conservacion_consumo: perfiles de consumo a los 90 días de terminar la autorización (MATU-36).
- conservacion_sesiones: sesiones y dispositivos vencidos (iam, MATU-38).
- conservacion_pedidos: los pedidos no pagados a los 30 días y las claves de idempotencia vencidas (ordering,
  MATU-61, D5). Corre siempre, también con CAPA3_HABILITADA apagada (decisión 220): solo llama a la función SQL
  pedido_conservar, y así lo no pagado se borra a los 30 días aunque los pedidos no estén disponibles (política
  0.12, §10).
- conservacion_invitaciones: las invitaciones al grupo cerradas hace 30 días (care_circle, MATU-42, D-42-6), con
  invitacion_conservar.
- conservacion_relevo: el teléfono del relevo 30 días después de que el acceso vence o se corta (care_plan, MATU-46,
  decisión 25), con relevo_conservar. Corre siempre: no es de la capa 3.
- quiebres: el trabajo diario de la predicción de quiebre y la conservación de alertas, eventos,
  notificaciones y compras (MATU-37 y MATU-51). Si un grupo falla, los demás se procesan igual, pero la
  corrida queda "fallo" (con sus contadores) y el proceso sale con 1.
- avisos: el publicador del outbox con el consumidor de avisos (MATU-41). Sin ENVIADOR_AVISOS no toma
  ningún evento y la corrida queda como "apagada".
- conciliacion_pagos: la conciliación de los pagos (payments, MATU-62, D-62-5): cierra las ventas sin respuesta y
  reintenta las anulaciones que no terminaron. Cada 5 minutos. Corre siempre, también con CAPA3_HABILITADA apagada
  (D-62-17): un pago que el banco ya aprobó se registra o se anula igual. Usa SCHEDULER_DATABASE_URL para
  pagos_por_conciliar (solo ids) y DATABASE_URL para cerrar cada venta con app.rol = 'sistema' y su grupo.
- despacho: lleva al día los pedidos pagados y devuelve lo que faltó (backoffice, MATU-63, D-63-8). Cada 5 minutos.
  Usa SCHEDULER_DATABASE_URL para despacho_pendiente (solo ids) y DATABASE_URL para cada pedido, con app.rol =
  'sistema' y su grupo.
- codigo-retiro <parte_id>: no es una tarea programada. Operación genera o regenera el código de retiro de una parte
  lista desde la consola hasta la pantalla de MATU-81 (MATU-63, D-63-5). Usa SCHEDULER_DATABASE_URL y
  CODIGO_RETIRO_SECRETO, audita codigo_retiro.generar y escribe el código una sola vez en la salida estándar, nunca en
  el log.
- borrados: las seis de borrado (destruccion_fichas, conservacion_consumo, conservacion_sesiones,
  conservacion_pedidos, conservacion_invitaciones y conservacion_relevo).
- todas_diarias: los borrados y después los quiebres, en ese orden.

Conexiones (hallazgo H2 de Martín, migración 0022). Cada tarea reutiliza el ``ejecutar`` de su módulo:

- SCHEDULER_DATABASE_URL, como matu_scheduler: enumera los grupos activos y llama a plan_destruir_claves,
  consumo_conservar, iam_conservar, quiebre_conservar, pedido_conservar (MATU-61), invitacion_conservar (MATU-42) y
  relevo_conservar (MATU-46), con app.rol = 'operacion'.
- PUBLISHER_DATABASE_URL, como matu_publisher: llama a las funciones outbox_* con app.rol = 'operacion'.
- DATABASE_URL, como matu_app: el trabajo de cada grupo (los quiebres y el consumidor de avisos), con
  app.rol = 'sistema' y app.grupo_id, que necesita RLS.

Si falta la URL que la tarea necesita, o es de otro usuario, la tarea falla con FaltaConexion y la línea de la
corrida nombra la variable (``falta``). Nunca cae a matu_app: desde la 0022, matu_app ya no ejecuta esas funciones.

Condiciones del analista normativo (MATU-74):

- Cada tarea corre en su propio try: una que falla no detiene a las demás. Si alguna falla, el proceso
  sale con código 1. Un nombre desconocido sale con código 2, sin tocar la base.
- De una excepción se registra solo su tipo. Nunca su mensaje ni su traza, a ningún stream: los errores
  de SQLAlchemy traen los parámetros de la sentencia, como un grupo_id.
- Una línea JSON por corrida con tarea, resultado, corrida (un id al azar por invocación, también como
  request_id), inicio, fin, duracion_ms y los contadores de la tarea. Nunca un id de usuario, persona o
  grupo, un correo, un teléfono, un token, texto de la ficha ni el nombre de un insumo.
"""

import importlib
import logging
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TextIO
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Configuracion, obtener_configuracion
from app.core.logs import configurar_logs, request_id_actual
from app.modules.care_circle.infrastructure import tarea_conservacion_invitaciones
from app.modules.care_plan.infrastructure import tarea_conservacion_relevo, tarea_destruccion
from app.modules.consumption.infrastructure import tarea_conservacion as tarea_conservacion_consumo
from app.modules.consumption.infrastructure import tarea_quiebres
from app.modules.iam.infrastructure import tarea_conservacion as tarea_conservacion_sesiones
from app.modules.notifications.infrastructure import tarea_avisos
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.tareas")

ZONA_CHILE = ZoneInfo("America/Santiago")

SALIDA_OK = 0
SALIDA_FALLO = 1
SALIDA_USO = 2

OK = "ok"
FALLO = "fallo"
APAGADA = "apagada"

TODAS_DIARIAS = "todas_diarias"
BORRADOS = "borrados"


# Los roles de las tareas (backend/db/00_roles.sql) y la variable con su conexión
ROL_SCHEDULER = "matu_scheduler"
ROL_PUBLISHER = "matu_publisher"
VARIABLE_DE: dict[str, str] = {ROL_SCHEDULER: "SCHEDULER_DATABASE_URL", ROL_PUBLISHER: "PUBLISHER_DATABASE_URL"}


class FaltaConexion(RuntimeError):
    """La tarea necesita la conexión de un rol que no está configurada. Lleva solo el nombre de la variable."""

    def __init__(self, variable: str) -> None:
        super().__init__(f"Falta {variable}, o no es una conexión de su rol")
        self.variable = variable


@dataclass(frozen=True)
class Contexto:
    """Lo que reciben las tareas. fabrica es la de matu_app (DATABASE_URL). Las de los roles de las tareas son
    opcionales para construir el contexto: la tarea que pide una que falta falla con FaltaConexion."""

    config: Configuracion
    fabrica: sessionmaker[Session]
    reloj: Reloj
    fabrica_scheduler: sessionmaker[Session] | None = None
    fabrica_publisher: sessionmaker[Session] | None = None

    def scheduler(self) -> sessionmaker[Session]:
        if self.fabrica_scheduler is None:
            raise FaltaConexion(VARIABLE_DE[ROL_SCHEDULER])
        return self.fabrica_scheduler

    def publisher(self) -> sessionmaker[Session]:
        if self.fabrica_publisher is None:
            raise FaltaConexion(VARIABLE_DE[ROL_PUBLISHER])
        return self.fabrica_publisher


@dataclass(frozen=True)
class Salida:
    """Lo que entrega una tarea: su resultado (ok, apagada o fallo) y sus contadores, solo cantidades."""

    resultado: str
    contadores: dict[str, int]


Tarea = Callable[[Contexto], Salida]


def _destruccion_fichas(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_destruccion.ejecutar(ctx.scheduler(), ctx.reloj)))


def _conservacion_consumo(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_conservacion_consumo.ejecutar(ctx.scheduler(), ctx.reloj)))


def _conservacion_sesiones(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_conservacion_sesiones.ejecutar(ctx.scheduler(), ctx.reloj)))


# MATU-61: se importa al correr, no al cargar este archivo (es de ordering), pero corre siempre, con la capa 3
# encendida o apagada: lo no pagado se borra a los 30 días aunque los pedidos no estén disponibles (decisión 220)
TAREA_CONSERVACION_PEDIDOS = "app.modules.ordering.infrastructure.tarea_conservacion"


def _conservacion_pedidos(ctx: Contexto) -> Salida:
    tarea = importlib.import_module(TAREA_CONSERVACION_PEDIDOS)
    return Salida(OK, asdict(tarea.ejecutar(ctx.scheduler(), ctx.reloj)))


def _conservacion_invitaciones(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_conservacion_invitaciones.ejecutar(ctx.scheduler(), ctx.reloj)))


def _conservacion_relevo(ctx: Contexto) -> Salida:
    return Salida(OK, asdict(tarea_conservacion_relevo.ejecutar(ctx.scheduler(), ctx.reloj)))


def _quiebres(ctx: Contexto) -> Salida:
    trabajo, conservacion = tarea_quiebres.ejecutar(ctx.fabrica, ctx.scheduler(), ctx.reloj)
    # Un grupo que falla no detiene a los demás, pero la corrida queda fallida para que el cron lo muestre
    resultado = FALLO if trabajo.grupos_fallidos > 0 else OK
    return Salida(resultado, {**asdict(trabajo), **asdict(conservacion)})


def _avisos(ctx: Contexto) -> Salida:
    # Con los avisos apagados no se abre ninguna conexión: no hace falta PUBLISHER_DATABASE_URL
    if not tarea_avisos.encendidos(ctx.config):
        tarea_avisos.avisar_apagados()
        return Salida(APAGADA, {})
    resultado = tarea_avisos.ejecutar(ctx.config, ctx.fabrica, ctx.publisher(), ctx.reloj)
    return Salida(APAGADA, {}) if resultado is None else Salida(OK, asdict(resultado))


# MATU-62: se importa al correr, no al cargar este archivo (es de payments), y corre con la capa 3 encendida o apagada
TAREA_CONCILIACION_PAGOS = "app.modules.payments.infrastructure.tarea_conciliacion"


def _conciliacion_pagos(ctx: Contexto) -> Salida:
    tarea = importlib.import_module(TAREA_CONCILIACION_PAGOS)
    scheduler = ctx.scheduler()
    resultado = tarea.ejecutar(ctx.config, ctx.fabrica, scheduler, ctx.reloj)
    return Salida(FALLO if resultado.fallidas > 0 else OK, asdict(resultado))


# MATU-63: se importa al correr (es de backoffice, capa 3). Lleva los pedidos pagados al día y devuelve lo que faltó
TAREA_DESPACHO = "app.modules.backoffice.infrastructure.tarea_despacho"


def _despacho(ctx: Contexto) -> Salida:
    tarea = importlib.import_module(TAREA_DESPACHO)
    resultado = tarea.ejecutar(ctx.config, ctx.fabrica, ctx.scheduler(), ctx.reloj)
    return Salida(FALLO if resultado.fallidos > 0 else OK, asdict(resultado))


TAREAS: dict[str, Tarea] = {
    "destruccion_fichas": _destruccion_fichas,
    "conservacion_consumo": _conservacion_consumo,
    "conservacion_sesiones": _conservacion_sesiones,
    "conservacion_pedidos": _conservacion_pedidos,
    "conservacion_invitaciones": _conservacion_invitaciones,
    "conservacion_relevo": _conservacion_relevo,
    "quiebres": _quiebres,
    "avisos": _avisos,
    "conciliacion_pagos": _conciliacion_pagos,
    "despacho": _despacho,
}

BORRADOS_DIARIOS: tuple[str, ...] = (
    "destruccion_fichas",
    "conservacion_consumo",
    "conservacion_sesiones",
    "conservacion_pedidos",
    "conservacion_invitaciones",
    # MATU-46: corre siempre, también con CAPA3_HABILITADA apagada, como conservacion_pedidos
    "conservacion_relevo",
)
# Los borrados antes que los quiebres: el trabajo diario no recalcula lo que ya debía borrarse
DIARIAS: tuple[str, ...] = (*BORRADOS_DIARIOS, "quiebres")

# Los nombres que corren varias tareas, cada una en su propio try
GRUPOS: dict[str, tuple[str, ...]] = {BORRADOS: BORRADOS_DIARIOS, TODAS_DIARIAS: DIARIAS}


# Los horarios de los cron, en UTC: el cron de Railway no sabe de zonas horarias. Hallazgos H3 y H5 de Martín:
# - avisos cada 5 minutos, el mínimo de Railway;
# - borrados a las 06:00 UTC: 03:00 de Chile en horario de verano (UTC-3) y 02:00 en invierno (UTC-4);
# - quiebres a las 08:00 UTC: 05:00 en verano y 04:00 en invierno. Dos horas después de los borrados, aunque estos
#   tarden, y con dos horas (verano) o tres (invierno) para terminar antes de las 07:00 de Chile.
# backend/README.md e infra/railway/README.md los repiten, y tests/test_tareas.py verifica las dos temporadas.
HORARIOS: dict[str, str] = {
    BORRADOS: "0 6 * * *",
    "quiebres": "0 8 * * *",
    "avisos": "*/5 * * * *",
    # MATU-62 (D-62-5): cada 5 minutos, el mínimo de Railway. Con la vida de la venta (10 minutos), una vuelta perdida
    # se cierra en menos de 15
    "conciliacion_pagos": "*/5 * * * *",
    # MATU-63 (D-63-8): cada 5 minutos, para que un faltante se devuelva el mismo día aunque falle la primera vez
    "despacho": "*/5 * * * *",
}

# Tope de espera para abrir una conexión, en segundos (connect_timeout de libpq). Sin él, con la base
# inalcanzable cada tarea espera lo que dé el sistema operativo (unos 130 s) antes de fallar.
TIEMPO_CONEXION_S = 10


def _fabrica(url: str) -> sessionmaker[Session]:
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": TIEMPO_CONEXION_S})
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def fabrica_tareas(config: Configuracion) -> sessionmaker[Session]:
    """La fábrica de sesiones de matu_app para las tareas: como la de la API (app/core/db.py), con tope de conexión.

    Un engine propio para no cambiar el de la API web. No conecta todavía."""
    if not config.database_url:
        raise RuntimeError("Falta DATABASE_URL")
    return _fabrica(config.database_url)


def fabrica_de_rol(url: str, rol: str) -> sessionmaker[Session] | None:
    """La fábrica de un rol de las tareas, o None si su variable está vacía o la URL es de otro usuario.

    Con None, la tarea que la pide falla con FaltaConexion: una URL de matu_app copiada en SCHEDULER_DATABASE_URL
    no sirve de atajo. No conecta todavía y nunca registra la URL."""
    if not url:
        return None
    try:
        usuario = make_url(url).username
    except Exception:  # noqa: BLE001 - una URL que no se lee cuenta como ausente, sin dejar su texto
        return None
    return _fabrica(url) if usuario == rol else None


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
        if isinstance(error, FaltaConexion):
            # El nombre de la variable que falta, nunca un valor
            extra.update(falta=error.variable)
        ok = False
    else:
        extra.update(resultado=salida.resultado, contadores=salida.contadores)
        ok = salida.resultado != FALLO
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
    print(f"     python -m app.tareas {CODIGO_RETIRO} <parte_id>", file=stream)


# MATU-63 (D-63-5): el código de retiro desde la consola, hasta MATU-81. Se importa al correr (es de la capa 3)
CODIGO_RETIRO = "codigo-retiro"
TAREA_CODIGO_RETIRO = "app.modules.backoffice.infrastructure.tarea_codigo_retiro"


def codigo_retiro(
    parte: str, *, stream: TextIO | None = None, consola: TextIO | None = None, reloj: Reloj | None = None,
    config: Configuracion | None = None,
) -> int:
    """Genera el código de una parte lista y lo escribe una vez en ``consola`` (la salida estándar), nunca en el log.
    La línea del log lleva el resultado y, si falla, el tipo del error o la variable que falta."""
    try:
        parte_id = uuid.UUID(parte)
    except ValueError:
        _uso(sys.stderr)
        return SALIDA_USO
    config = config or obtener_configuracion()
    configurar_logs(config.log_nivel, stream)
    extra: dict[str, object] = {"tarea": "codigo_retiro", "corrida": str(uuid.uuid4())}
    fabrica = fabrica_de_rol(config.scheduler_database_url, ROL_SCHEDULER)
    if fabrica is None:
        log.error("tarea", extra={**extra, "resultado": FALLO, "falta": VARIABLE_DE[ROL_SCHEDULER]})
        return SALIDA_FALLO
    tarea = importlib.import_module(TAREA_CODIGO_RETIRO)
    try:
        codigo, expira = tarea.generar(config, fabrica, reloj or RelojSistema(), parte_id)
    except tarea.SinSecretoCodigo:
        log.error("tarea", extra={**extra, "resultado": FALLO, "falta": "CODIGO_RETIRO_SECRETO"})
        return SALIDA_FALLO
    except tarea.ParteSinCodigo as error:
        log.error("tarea", extra={**extra, "resultado": FALLO, "motivo": error.motivo})
        return SALIDA_FALLO
    except Exception as error:  # noqa: BLE001 - de una excepción, solo su tipo (R1)
        log.error("tarea", extra={**extra, "resultado": FALLO, "tipo_error": type(error).__name__})
        return SALIDA_FALLO
    hora = expira.astimezone(ZONA_CHILE).strftime("%H:%M")
    salida = consola or sys.stdout
    salida.write(f"Código de retiro: {codigo}\nVale hasta las {hora} (hora de Chile) y sirve una vez.\n")
    salida.flush()
    log.info("tarea", extra={**extra, "resultado": OK})
    return SALIDA_OK


def main(argv: Sequence[str] | None = None, *, stream: TextIO | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if len(argumentos) == 2 and argumentos[0] == CODIGO_RETIRO:
        return codigo_retiro(argumentos[1], stream=stream)
    nombres = nombres_de(argumentos[0]) if len(argumentos) == 1 else None
    if nombres is None:
        _uso(sys.stderr)
        return SALIDA_USO
    try:
        config = obtener_configuracion()
        # Crea el engine sin conectar: si la base no responde, falla cada tarea en su propio try
        fabrica = fabrica_tareas(config)
    except Exception as error:  # noqa: BLE001 - una configuración inválida tampoco deja su mensaje (la URL)
        configurar_logs("INFO", stream)
        extra = {"tarea": "arranque", "resultado": FALLO, "tipo_error": type(error).__name__}
        log.error("tarea", extra={**extra, "corrida": str(uuid.uuid4())})
        return SALIDA_FALLO
    configurar_logs(config.log_nivel, stream)
    contexto = Contexto(
        config=config,
        fabrica=fabrica,
        reloj=RelojSistema(),
        fabrica_scheduler=fabrica_de_rol(config.scheduler_database_url, ROL_SCHEDULER),
        fabrica_publisher=fabrica_de_rol(config.publisher_database_url, ROL_PUBLISHER),
    )
    return correr(nombres, contexto)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
