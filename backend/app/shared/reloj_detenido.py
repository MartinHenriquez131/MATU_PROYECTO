"""Un Reloj detenido en un instante: todo lo que lo lee ve el mismo momento (MATU-44, decisión 124).

Implementa el puerto Reloj sin cambiarlo. Una ruta lo arma una vez por petición con el instante del Reloj
real, y se lo entrega al caso de uso y al registro de auditoría: así revocado_en, los revocado_en de los
accesos y el ocurrido_en de cada fila de auditoría de la misma transacción son exactamente el mismo
instante, sin que RegistroAuditoriaSql pida otra hora.
"""

from datetime import datetime


class RelojDetenido:
    def __init__(self, instante: datetime) -> None:
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError("RelojDetenido exige un datetime con zona horaria")
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante
