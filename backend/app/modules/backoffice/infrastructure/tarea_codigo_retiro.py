"""El código de retiro desde la consola de operación (MATU-63, D-63-5; decisión 426). Hasta la pantalla de MATU-81,
en la demo operación lo genera con:

    python -m app.tareas codigo-retiro <parte_id>

Corre con SCHEDULER_DATABASE_URL (matu_scheduler) y app.rol = 'operacion', nunca con la conexión de la API: la función
codigo_retiro_guardar (0029) guarda solo la huella HMAC de una parte lista y audita codigo_retiro.generar sin el
código. El código vuelve aquí y app.tareas lo escribe una sola vez en la salida estándar, sin pasar por el logger.
Sin CODIGO_RETIRO_SECRETO, falla sin tocar la base.
"""

import secrets
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Configuracion
from app.core.db import sesion_tenant
from app.modules.fulfillment.domain.despacho import CIFRAS_CODIGO, VIDA_CODIGO, huella_codigo
from app.shared.puertos import Reloj

_GUARDAR = text("SELECT codigo_retiro_guardar(:parte, :huella, :generado, :expira)")


class SinSecretoCodigo(RuntimeError):
    """Falta CODIGO_RETIRO_SECRETO. El mensaje nombra la variable, nunca un valor."""

    def __init__(self) -> None:
        super().__init__("Falta CODIGO_RETIRO_SECRETO")


class ParteSinCodigo(LookupError):
    """La parte no existe o no está lista para retirar."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def generar(
    config: Configuracion, fabrica_scheduler: sessionmaker[Session], reloj: Reloj, parte_id: uuid.UUID
) -> tuple[str, datetime]:
    """Genera o regenera el código de una parte lista. Devuelve el código y hasta cuándo vale."""
    if config.codigo_retiro_secreto is None:
        raise SinSecretoCodigo()
    secreto = config.codigo_retiro_secreto.get_secret_value().encode("utf-8")
    codigo = f"{secrets.randbelow(10**CIFRAS_CODIGO):0{CIFRAS_CODIGO}d}"
    ahora = reloj.ahora()
    expira = ahora + VIDA_CODIGO
    with sesion_tenant(fabrica_scheduler, rol="operacion") as sesion:
        huella = huella_codigo(secreto, parte_id, codigo)
        resultado = sesion.execute(
            _GUARDAR, {"parte": parte_id, "huella": huella, "generado": ahora, "expira": expira}
        ).scalar()
    if resultado != "ok":
        raise ParteSinCodigo(str(resultado))
    return codigo, expira
