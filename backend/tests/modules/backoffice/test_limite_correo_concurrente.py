"""MATU-114 · C11, cierre del analista: el límite de correos del retracto es atómico. Sin base.

Diez intentos fallidos a la vez con la misma cuenta de operación: cada uno reserva su intento con un INCR (sumar) antes
de consultar. A lo más 5 llegan a «la base» (la consulta simulada) y los demás reciben 429 sin consultarla. Con leer y
después sumar, como antes, los diez podían leer 0 y consultar todos.
"""

import threading
from datetime import UTC, datetime

import pytest

from app.core.errores import ErrorMATU
from app.modules.backoffice.api.router_operacion import LIMITE_CORREO_RETRACTO, devolver_reserva, reservar_intento
from tests.dobles.contador_ventana_en_memoria import ContadorVentanaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = [pytest.mark.rf("R3"), pytest.mark.rf("Ley-21.719")]

CLAVE = "matu:limite:retracto-correo:huella-sintetica"


def test_diez_fallidos_a_la_vez_solo_cinco_consultan_la_base() -> None:
    contador = ContadorVentanaEnMemoria(RelojFijo(datetime(2026, 11, 18, 12, 0, tzinfo=UTC)))
    barrera = threading.Barrier(10)
    candado = threading.Lock()
    consultas: list[int] = []
    respuestas: list[int] = []

    def intento(n: int) -> None:
        barrera.wait()
        try:
            reservar_intento(contador, CLAVE)
        except ErrorMATU as error:
            with candado:
                respuestas.append(error.status)
            return
        with candado:
            consultas.append(n)  # la consulta a la base, que no encuentra al admin: la reserva queda
            respuestas.append(422)

    hilos = [threading.Thread(target=intento, args=(n,)) for n in range(10)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert len(consultas) == LIMITE_CORREO_RETRACTO.maximo
    assert sorted(respuestas) == [422] * 5 + [429] * 5


def test_la_reserva_de_un_correo_valido_se_devuelve_y_no_renace_vencida() -> None:
    reloj = RelojFijo(datetime(2026, 11, 18, 12, 0, tzinfo=UTC))
    contador = ContadorVentanaEnMemoria(reloj)
    reservar_intento(contador, CLAVE)
    devolver_reserva(contador, CLAVE)
    assert contador.datos[CLAVE][0] == 0
    # Nunca bajo cero, y una clave que no existe no se crea
    devolver_reserva(contador, CLAVE)
    devolver_reserva(contador, "matu:limite:retracto-correo:otra")
    assert contador.datos[CLAVE][0] == 0 and "matu:limite:retracto-correo:otra" not in contador.datos


def test_sin_redis_la_reserva_falla_cerrada_y_la_devolucion_no_corta_el_retracto() -> None:
    contador = ContadorVentanaEnMemoria(RelojFijo(datetime(2026, 11, 18, 12, 0, tzinfo=UTC)), caido=True)
    with pytest.raises(ErrorMATU) as error:
        reservar_intento(contador, CLAVE)
    assert error.value.status == 503
    devolver_reserva(contador, CLAVE)  # solo deja el log
