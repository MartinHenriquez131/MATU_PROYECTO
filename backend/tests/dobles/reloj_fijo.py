"""Doble del puerto Reloj: una hora fija que la prueba hace avanzar a voluntad."""

from datetime import UTC, datetime, timedelta


class RelojFijo:
    """Reloj detenido en un instante. "Esperar dos horas" se escribe reloj.avanzar(timedelta(hours=2))."""

    def __init__(self, inicio: datetime) -> None:
        if inicio.tzinfo is None or inicio.utcoffset() is None:
            raise ValueError("RelojFijo exige un datetime con zona horaria")
        self._actual = inicio.astimezone(UTC)

    def ahora(self) -> datetime:
        return self._actual

    def avanzar(self, delta: timedelta) -> None:
        if delta < timedelta(0):
            raise ValueError("RelojFijo solo avanza: para otro instante, crea otro reloj")
        self._actual += delta
