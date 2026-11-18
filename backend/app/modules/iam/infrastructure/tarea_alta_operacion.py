"""El alta de una cuenta de operación desde la consola (MATU-81, C28 y C33):

    python -m app.tareas operacion-alta

Interactiva. Pide el correo de una cuenta que ya existe (se crea como cualquier otra, en «Crear cuenta»), genera un
secreto TOTP de 160 bits, muestra la URI otpauth **una sola vez** en la consola para escanearla con la app del
teléfono, pide el primer código para comprobar que quedó bien y solo entonces guarda el alta. Sin SMS ni códigos de
recuperación: si se pierde el teléfono, se repite el alta, que cierra las sesiones abiertas de la cuenta.

Corre con SCHEDULER_DATABASE_URL (matu_scheduler) y app.rol = 'operacion', por operacion_buscar_cuenta y
operacion_alta (0030). Necesita PEPPER_EMAIL (la huella del correo) y la KEK (CUSTODIA_KEK=entorno_sintetico y
KEK_ENTORNO), con la que el secreto se cifra con AES-256-GCM y el AAD ``mfa:<usuario_id>``. El correo, el id, el
secreto y la URI nunca van al log: la línea de la tarea lleva solo el resultado.
"""

import secrets
import uuid
from collections.abc import Callable
from typing import TextIO

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Configuracion
from app.core.db import sesion_tenant
from app.modules.iam.domain.credenciales import indice_email, normalizar_email
from app.modules.iam.domain.mfa import BYTES_SECRETO, paso_que_coincide, uri_otpauth
from app.modules.iam.infrastructure.cifrador_mfa import cifrador_de
from app.shared.puertos import Reloj

_BUSCAR = text("SELECT usuario_id, resultado FROM operacion_buscar_cuenta(:hash)")
_ALTA = text("SELECT operacion_alta(:usuario, :secreto)")
INTENTOS_CODIGO = 3

MENSAJES = {
    "sin_cuenta": "No hay una cuenta con ese correo. Créala primero en «Crear cuenta».",
    "no_activa": "Esa cuenta no está activa.",
    "en_un_grupo": "Esa cuenta es miembro de una familia: una cuenta de operación no puede serlo (C33).",
    "de_un_comercio": "Esa cuenta es de un comercio: una cuenta de operación no puede serlo (C33).",
}


class FaltaConfiguracion(RuntimeError):
    """Falta PEPPER_EMAIL o la KEK. Lleva solo el nombre de la variable."""

    def __init__(self, variable: str) -> None:
        super().__init__(f"Falta {variable}")
        self.variable = variable


class AltaRechazada(Exception):
    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def dar_alta(
    config: Configuracion,
    fabrica_scheduler: sessionmaker[Session],
    reloj: Reloj,
    preguntar: Callable[[str], str],
    consola: TextIO,
) -> None:
    """Lanza FaltaConfiguracion, AltaRechazada (con el motivo, sin datos) o un error de la base."""
    if config.pepper_email is None:
        raise FaltaConfiguracion("PEPPER_EMAIL")
    cifrador = cifrador_de(config)
    if cifrador is None:
        raise FaltaConfiguracion("KEK_ENTORNO")
    correo = preguntar("Correo de la cuenta que será de operación: ").strip()
    huella = indice_email(config.pepper_email.get_secret_value().encode("utf-8"), normalizar_email(correo))
    with sesion_tenant(fabrica_scheduler, rol="operacion") as sesion:
        fila = sesion.execute(_BUSCAR, {"hash": huella}).one()
    if fila.resultado != "ok":
        consola.write(MENSAJES.get(fila.resultado, "No se puede dar de alta esa cuenta.") + "\n")
        raise AltaRechazada(str(fila.resultado))
    usuario_id = uuid.UUID(str(fila.usuario_id))
    secreto = secrets.token_bytes(BYTES_SECRETO)
    consola.write(
        "\nEscanea esta dirección con la app de códigos del teléfono (o cópiala en ella). Se muestra una sola vez:\n\n"
        f"{uri_otpauth(secreto)}\n\n"
    )
    consola.flush()
    for _ in range(INTENTOS_CODIGO):
        codigo = preguntar("Escribe el código de 6 cifras que muestra la app: ").strip()
        if paso_que_coincide(secreto, codigo, reloj.ahora()) is not None:
            break
        consola.write("Ese código no coincide. Revisa la hora del teléfono y vuelve a intentarlo.\n")
    else:
        consola.write("No se guardó nada. Vuelve a correr el alta.\n")
        raise AltaRechazada("codigo")
    with sesion_tenant(fabrica_scheduler, rol="operacion") as sesion:
        resultado = sesion.execute(_ALTA, {"usuario": usuario_id, "secreto": cifrador.cifrar(secreto, usuario_id)})
        estado = resultado.scalar()
    if estado != "ok":
        raise AltaRechazada(str(estado))
    consola.write("Listo: la cuenta entra en /operacion con su contraseña y el código del teléfono.\n")
    consola.flush()
