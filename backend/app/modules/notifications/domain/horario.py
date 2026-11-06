"""Hora de envío de los avisos (MATU-41, decisión 109, decisión de Jorge del 04-11).

Los avisos por correo y push no salen antes de las 09:00 hora de Chile (America/Santiago). Un evento que
el trabajo diario crea a las 04:00 queda disponible desde las 09:00 del mismo día. Desde las 09:00 se
envía al momento. ``ahora`` viene del puerto Reloj: este módulo nunca lee la hora del sistema.
"""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

ZONA_CHILE = ZoneInfo("America/Santiago")
HORA_DESDE = time(9, 0)


def disponible_desde(ahora: datetime) -> datetime | None:
    """None si ya se puede enviar; si no, las 09:00 de hoy en Chile, en UTC."""
    if ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")
    local = ahora.astimezone(ZONA_CHILE)
    if local.time() >= HORA_DESDE:
        return None
    # En Chile el cambio de hora ocurre a medianoche: las 09:00 siempre existen y no se repiten
    return datetime.combine(local.date(), HORA_DESDE, tzinfo=ZONA_CHILE).astimezone(UTC)
