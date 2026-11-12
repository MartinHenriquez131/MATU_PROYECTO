"""Reglas comunes de la copia de los datos (MATU-54, Ley 21.719, acceso y portabilidad; decisiones 343, 346 y 349).

Las usan las dos copias: «Datos de {nombre_pila}» (care_plan arma la ruta, care_circle registra los bloques) y «Tus
datos» (iam). Solo biblioteca estándar: se importa desde domain/ y application/ de cualquier módulo.

- El formato del archivo, ``matu-datos/1``, y el aviso fijo con que empieza (C10, P14 del diseñador, decisión 377).
- Los instantes van con el desfase de Chile (``America/Santiago``) y los días como ``AAAA-MM-DD``: es la única parte de
  la API que no usa UTC, porque el archivo lo lee una persona o un programa fuera de MATU (decisión 349).
- El nombre del archivo, sin el nombre de nadie (C9): ``matu-datos-AAAA-MM-DD.json`` y ``matu-cuenta-AAAA-MM-DD.json``.
- El límite: 10 copias por hora por cuenta, en un contador común a las dos (D-54-10 a, decisión 346).
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.shared.limite_ip import LimitePorIp

FORMATO = "matu-datos/1"

# P14 del diseñador (especificación v1.1, sección 9), aprobado por el orquestador (decisión 377)
AVISO_COPIA = (
    "Esta es una copia de los datos que MATU guarda, para que puedas conocerlos o llevarlos a otro lugar. No es la"
    " ficha para un relevo, y no se usa para compartirla. MATU no guarda esta copia. Este archivo queda donde lo"
    " descargaste, fuera de MATU: no vence y MATU no lo puede borrar."
)

ZONA_CHILE = ZoneInfo("America/Santiago")

ARCHIVO_PERSONA = "matu-datos"
ARCHIVO_CUENTA = "matu-cuenta"

# Por cuenta y no por IP: la huella es HMAC(PEPPER_LIMITES, "copia-datos:<usuario_id>")
LIMITE_COPIAS = LimitePorIp("copia-datos", 10)


def en_chile(instante: datetime) -> str:
    """El instante en RFC 3339 con el desfase de Chile, al segundo. Lanza ValueError sin zona horaria."""
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    return instante.astimezone(ZONA_CHILE).replace(microsecond=0).isoformat()


def en_chile_o_nada(instante: datetime | None) -> str | None:
    return None if instante is None else en_chile(instante)


def dia_en_chile(instante: datetime) -> date:
    """El día de Chile de un instante."""
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    return instante.astimezone(ZONA_CHILE).date()


def nombre_archivo(prefijo: str, ahora: datetime) -> str:
    """``<prefijo>-AAAA-MM-DD.json`` con el día de Chile. Nunca lleva un nombre de persona (C9)."""
    if prefijo not in (ARCHIVO_PERSONA, ARCHIVO_CUENTA):
        raise ValueError("prefijo de archivo desconocido")
    return f"{prefijo}-{dia_en_chile(ahora).isoformat()}.json"


def content_disposition(prefijo: str, ahora: datetime) -> str:
    """``inline``: la misma respuesta se muestra en la pantalla, y el archivo lo guarda la pantalla desde la memoria."""
    return f'inline; filename="{nombre_archivo(prefijo, ahora)}"'
