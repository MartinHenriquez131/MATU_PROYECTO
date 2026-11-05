"""Reglas puras de la demora progresiva de la entrada (MATU-38, decisión 49).

Sin I/O ni reloj del sistema. Los contadores viven en Redis (puerto ContadoresEntrada) y la hora
llega del Reloj.

- Dos contadores de fallos: por la huella de la IP y por la huella del email normalizado. Cada huella
  es HMAC-SHA-256(PEPPER_LIMITES, "<prefijo>:<valor>"): ni la IP ni el email llegan en claro a Redis.
- Cada contador vence a la hora del primer fallo.
- Sin espera hasta 5 fallos por email y 20 por IP. Desde ahí, la espera desde el último fallo es de
  30 s, 1, 2, 4 y 8 minutos, con tope de 15 minutos.
- El mismo trato exista o no el email: no se lee la base. Nunca bloquea la cuenta.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

# La misma huella del límite por IP de MATU-25, con otro prefijo
from app.shared.limite_ip import huella as huella

UMBRAL_EMAIL = 5
UMBRAL_IP = 20
VENTANA_CONTADOR = timedelta(hours=1)
PRIMERA_ESPERA_SEGUNDOS = 30
TOPE_ESPERA_SEGUNDOS = 15 * 60

PREFIJO_IP = "entrada-ip"
PREFIJO_EMAIL = "entrada-email"


def espera_tras_fallos(fallos: int, umbral: int) -> int:
    """Segundos de espera después del último fallo, según cuántos van en la ventana.

    Hasta el umbral, 0. Con el fallo umbral + 1, 30 s; después se duplica (1, 2, 4 y 8 minutos) hasta
    el tope de 15 minutos.
    """
    if fallos <= umbral:
        return 0
    exceso = fallos - umbral
    # 30 * 2^(exceso - 1), sin calcular potencias enormes
    if exceso > 16:
        return TOPE_ESPERA_SEGUNDOS
    return int(min(PRIMERA_ESPERA_SEGUNDOS * 2 ** (exceso - 1), TOPE_ESPERA_SEGUNDOS))


@dataclass(frozen=True)
class ContadorFallos:
    """Lo guardado para una huella: cuántos fallos van y cuándo fue el último. Sin fallos, (0, None)."""

    fallos: int
    ultimo_fallo: datetime | None


SIN_FALLOS = ContadorFallos(0, None)


def segundos_restantes(contador: ContadorFallos, umbral: int, ahora: datetime) -> int:
    """Segundos enteros (hacia arriba) que faltan para poder volver a intentar. 0 si no hay espera."""
    if contador.ultimo_fallo is None:
        return 0
    if ahora.tzinfo is None or contador.ultimo_fallo.tzinfo is None:
        raise ValueError("El instante debe tener zona horaria")
    espera = espera_tras_fallos(contador.fallos, umbral)
    if espera == 0:
        return 0
    falta = (contador.ultimo_fallo + timedelta(seconds=espera) - ahora).total_seconds()
    return max(0, min(math.ceil(falta), TOPE_ESPERA_SEGUNDOS))


def retry_after(contador_ip: ContadorFallos, contador_email: ContadorFallos, ahora: datetime) -> int:
    """La espera de la entrada: la mayor de las dos huellas. 0 si se puede intentar.

    No dice cuál de las dos huellas la causó: el 429 es el mismo.
    """
    return max(
        segundos_restantes(contador_ip, UMBRAL_IP, ahora),
        segundos_restantes(contador_email, UMBRAL_EMAIL, ahora),
    )
