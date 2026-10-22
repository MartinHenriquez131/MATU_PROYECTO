"""El reloj real cumple el puerto Reloj: devuelve la hora actual con zona horaria UTC."""

from datetime import UTC, datetime, timedelta

from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema


def test_reloj_sistema_entrega_hora_actual_en_utc() -> None:
    # Dado el reloj real, usado a través del puerto
    reloj: Reloj = RelojSistema()

    # Cuando se pide la hora
    antes = datetime.now(UTC)
    ahora = reloj.ahora()
    despues = datetime.now(UTC)

    # Entonces viene con zona horaria UTC y es la hora actual
    assert ahora.utcoffset() == timedelta(0)
    assert antes <= ahora <= despues
