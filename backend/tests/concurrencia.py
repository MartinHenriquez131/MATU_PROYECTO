"""Sincronización explícita para las pruebas de carreras contra PostgreSQL (MATU-96).

Antes, las pruebas de bloqueo abrían la escritura en un hilo, esperaban un segundo (``hilo.join(timeout=1.0)``) y
daban por hecho que, si el hilo seguía vivo, ya esperaba el bloqueo. No siempre: un hilo lento todavía no había
llegado a la consulta bloqueante, la transacción que bloqueaba confirmaba antes y la escritura leía el estado ya
confirmado. Con un borrado eso es 404 y no 403 (MATU-96, dos fallos el 11-11 en ``me-quedan-borrado`` y
``consumo-borrar-borrado``).

``esperar_bloqueada_por`` pregunta a PostgreSQL, con ``pg_locks`` y ``pg_blocking_pids``, si alguna sesión espera un
bloqueo de la sesión dada. Solo vuelve cuando eso es cierto, así que lo que la prueba hace después (confirmar el
retiro o el borrado) ocurre con la escritura ya formada en la fila del bloqueo. Sin tiempos fijos: el plazo es solo
un tope para no colgar la prueba.
"""

import threading
import time

import psycopg
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.base_datos import DSN

# pg_locks y pg_blocking_pids son en vivo, no una foto de la transacción (pg_stat_activity sí lo es)
_ESPERA_A = "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE NOT granted AND %s = ANY(pg_blocking_pids(pid)))"

PLAZO = 15.0
INTERVALO = 0.01


def pid_de(sesion: Session) -> int:
    """El pid del servidor de la conexión de la sesión. Abre la transacción si aún no estaba abierta."""
    return int(sesion.execute(text("SELECT pg_backend_pid()")).scalar_one())


def esperar_bloqueada_por(pid: int, hilo: threading.Thread, *, plazo: float = PLAZO) -> None:
    """Vuelve cuando alguna sesión espera un bloqueo de ``pid``. Falla si ``hilo`` termina antes (no esperó el
    bloqueo: le falta el FOR SHARE) o si vence el plazo."""
    limite = time.monotonic() + plazo
    with psycopg.connect(DSN, autocommit=True) as cx:
        while True:
            fila = cx.execute(_ESPERA_A, (pid,)).fetchone()
            if fila and fila[0]:
                return
            if not hilo.is_alive():
                raise AssertionError("la escritura terminó sin esperar el bloqueo")
            if time.monotonic() >= limite:
                raise AssertionError(f"la escritura no llegó al bloqueo en {plazo} s")
            hilo.join(timeout=INTERVALO)
