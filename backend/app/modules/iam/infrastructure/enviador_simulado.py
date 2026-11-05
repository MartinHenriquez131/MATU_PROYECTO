"""Envío simulado de los códigos de MATU-57 (decisión 82).

No envía nada. Deja cada mensaje en un registro de desarrollo: una lista en memoria (la leen las
pruebas) y, si se define REGISTRO_ENVIOS, una línea JSON en ese archivo, que debe estar en una
carpeta ignorada por git (por ejemplo .dev/envios.jsonl), para probar a mano.

Nunca escribe en los logs de la aplicación: el destino y el mensaje (con el código) solo quedan en
este registro. La configuración impide encenderlo con ENTORNO=produccion (app/core/config.py).
"""

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.modules.iam.domain.recuperacion import Canal


@dataclass(frozen=True)
class EnvioSimulado:
    canal: Canal
    destino: str
    mensaje: str

    def __repr__(self) -> str:
        return f"EnvioSimulado(canal={self.canal.value})"


class EnviadorSimulado:
    def __init__(self, archivo: Path | None = None) -> None:
        self._archivo = archivo
        self._candado = threading.Lock()
        self.enviados: list[EnvioSimulado] = []

    def __repr__(self) -> str:
        return "EnviadorSimulado()"

    def enviar(self, canal: Canal, destino: str, mensaje: str) -> None:
        with self._candado:
            self.enviados.append(EnvioSimulado(canal, destino, mensaje))
            if self._archivo is not None:
                self._archivo.parent.mkdir(parents=True, exist_ok=True)
                linea = {
                    "en": datetime.now(UTC).isoformat(timespec="seconds"),
                    "canal": canal.value,
                    "destino": destino,
                    "mensaje": mensaje,
                }
                with self._archivo.open("a", encoding="utf-8") as salida:
                    salida.write(json.dumps(linea, ensure_ascii=False) + "\n")
