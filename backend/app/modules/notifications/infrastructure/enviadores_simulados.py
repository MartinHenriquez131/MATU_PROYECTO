"""Envío simulado de los avisos por correo y push (MATU-41, decisión 112).

No envía nada: no hay proveedores reales en esta historia. Cada envío queda en un registro de desarrollo,
una lista en memoria (la leen las pruebas) y una línea JSON en REGISTRO_AVISOS, por omisión
``.dev/avisos.jsonl``, carpeta ignorada por git.

El registro guarda solo ``notificacion_id``, ``usuario_id``, canal, plantilla y la hora: **nunca el destino
(email o push_token) ni el texto**. Nunca escribe en los logs de la aplicación, y ni el ``repr`` de los
adaptadores ni el de lo que guardan muestran un destino. La configuración impide encenderlo fuera de
ENTORNOS_ENVIO_SIMULADO (app/core/config.py).
"""

import json
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.modules.notifications.application.ports import EnvioCorreo, EnvioPush
from app.modules.notifications.domain.aviso import Canal, ResultadoEnvio
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class EnvioRegistrado:
    notificacion_id: uuid.UUID
    usuario_id: uuid.UUID
    canal: Canal
    plantilla: str


class RegistroAvisosSimulado:
    def __init__(self, reloj: Reloj, archivo: Path | None = None) -> None:
        self._reloj = reloj
        self._archivo = archivo
        self._candado = threading.Lock()
        self.enviados: list[EnvioRegistrado] = []

    def __repr__(self) -> str:
        return "RegistroAvisosSimulado()"

    def anotar(self, envio: EnvioRegistrado) -> None:
        with self._candado:
            self.enviados.append(envio)
            if self._archivo is None:
                return
            self._archivo.parent.mkdir(parents=True, exist_ok=True)
            linea = {
                "en": self._reloj.ahora().isoformat(timespec="seconds"),
                "notificacion_id": str(envio.notificacion_id),
                "usuario_id": str(envio.usuario_id),
                "canal": envio.canal.value,
                "plantilla": envio.plantilla,
            }
            with self._archivo.open("a", encoding="utf-8") as salida:
                salida.write(json.dumps(linea, ensure_ascii=False) + "\n")


class EnviadorCorreoSimulado:
    def __init__(self, registro: RegistroAvisosSimulado) -> None:
        self._registro = registro

    def __repr__(self) -> str:
        return "EnviadorCorreoSimulado()"

    def enviar(self, envio: EnvioCorreo) -> ResultadoEnvio:
        self._registro.anotar(EnvioRegistrado(envio.notificacion_id, envio.usuario_id, Canal.CORREO, envio.plantilla))
        return ResultadoEnvio.ENVIADO


class EnviadorPushSimulado:
    def __init__(self, registro: RegistroAvisosSimulado) -> None:
        self._registro = registro

    def __repr__(self) -> str:
        return "EnviadorPushSimulado()"

    def enviar(self, envio: EnvioPush) -> ResultadoEnvio:
        self._registro.anotar(EnvioRegistrado(envio.notificacion_id, envio.usuario_id, Canal.PUSH, envio.plantilla))
        return ResultadoEnvio.ENVIADO
