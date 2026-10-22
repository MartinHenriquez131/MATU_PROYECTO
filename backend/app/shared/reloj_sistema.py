"""Implementación real del puerto Reloj, con la hora del sistema."""

from datetime import UTC, datetime


class RelojSistema:
    """Reloj del sistema en UTC. Es el único lugar donde la aplicación lee la hora actual."""

    def ahora(self) -> datetime:
        return datetime.now(UTC)
