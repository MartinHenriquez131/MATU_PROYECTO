"""Reglas puras de la recuperación del acceso y de la verificación del celular (MATU-57, RF-37).

Sin I/O ni reloj del sistema. El código se genera en application/ con secrets; los códigos y los
contadores viven en Redis (puertos AlmacenCodigos y ContadoresEnvio) y la hora llega del Reloj.

- Código de 6 dígitos, vence a los 10 minutos, un solo uso, máximo 5 intentos. Pedir otro reemplaza
  al anterior (decisión 81).
- Solo se guarda la huella HMAC-SHA-256 del código con PEPPER_RECUPERACION, ligada a la clave del
  usuario: la misma cifra para otra persona tiene otra huella.
- Envíos: 60 s entre uno y otro, 3 por hora y 10 al día por cuenta y por destino; por IP, 20 por hora
  y 50 al día (decisión 84). Las ventanas son fijas desde el primer envío.
- El código va al celular solo si está verificado; si no, al correo. El aviso del cambio de
  contraseña va por el otro canal (decisión 86).
- Ningún mensaje lleva nombres ni enlaces.
"""

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.iam.domain.demora import huella

LARGO_CODIGO = 6
VIGENCIA_CODIGO = timedelta(minutes=10)
MAX_INTENTOS = 5
ESPERA_REENVIO = timedelta(seconds=60)
VENTANA_HORA = timedelta(hours=1)
VENTANA_DIA = timedelta(days=1)

LIMITE_HORA_DESTINO = 3
LIMITE_DIA_DESTINO = 10
LIMITE_HORA_IP = 20
LIMITE_DIA_IP = 50

# Prefijos de las huellas de los contadores (con PEPPER_LIMITES, como demora.py)
PREFIJO_RECUPERAR_IP = "recuperar-ip"
PREFIJO_RECUPERAR_EMAIL = "recuperar-email"
PREFIJO_RECUPERAR_CELULAR = "recuperar-celular"
# La verificación del código tiene sus propios contadores de fallos, con la demora de demora.py
PREFIJO_VERIFICAR_IP = "recuperar-verificar-ip"
PREFIJO_VERIFICAR_EMAIL = "recuperar-verificar-email"
PREFIJO_VERIFICAR_CELULAR = "celular-verificar-usuario"

MENSAJE_AVISO = (
    "MATU: se cambió la contraseña de tu cuenta y se cerraron todas tus sesiones. Si no fuiste tú,"
    " pide un código para recuperar tu acceso."
)


class Proposito(StrEnum):
    """Para qué es el código. Cada propósito tiene su propia clave: uno no invalida al otro al pedirse."""

    RECUPERAR = "recuperar"
    CELULAR = "celular"


class Canal(StrEnum):
    SMS = "sms"
    CORREO = "correo"


class CodigoInvalido(Exception):
    """Incorrecto, vencido, ya usado, agotado o sin cuenta: un solo caso, sin decir cuál."""


def mensaje_codigo(codigo: str) -> str:
    """El texto del mensaje con el código (decisión 88). Sin nombres ni enlaces."""
    if not es_codigo(codigo):
        raise ValueError("El código debe tener 6 dígitos")
    return (
        f"MATU: tu código es {codigo}. Vence en 10 minutos. No lo compartas con nadie;"
        " MATU nunca te lo pedirá por teléfono."
    )


def es_codigo(valor: str) -> bool:
    return len(valor) == LARGO_CODIGO and valor.isascii() and valor.isdigit()


def clave_codigo(pepper: bytes, proposito: Proposito, usuario_id: str) -> str:
    """La clave del código en el almacén: la huella del usuario, nunca el email ni el celular."""
    return huella(pepper, f"codigo-{proposito.value}", usuario_id)


def huella_codigo(pepper: bytes, clave: str, codigo: str) -> str:
    """HMAC-SHA-256 del código, ligado a la clave del usuario y del propósito."""
    return huella(pepper, f"valor:{clave}", codigo)


@dataclass(frozen=True)
class CodigoGuardado:
    huella: str
    expira_en: datetime
    canal: Canal

    def __repr__(self) -> str:
        return f"CodigoGuardado(expira_en={self.expira_en.isoformat()}, canal={self.canal.value})"


def codigo_nuevo(huella_del_codigo: str, canal: Canal, ahora: datetime) -> CodigoGuardado:
    if ahora.tzinfo is None:
        raise ValueError("El instante debe tener zona horaria")
    return CodigoGuardado(huella=huella_del_codigo, expira_en=ahora + VIGENCIA_CODIGO, canal=canal)


def codigo_sirve(guardado: CodigoGuardado | None, huella_presentada: str, intentos: int, ahora: datetime) -> bool:
    """True solo si hay código, no venció, los intentos (contando este) no pasan de 5 y la huella calza.

    La comparación es de tiempo constante.
    """
    if guardado is None or intentos > MAX_INTENTOS or ahora >= guardado.expira_en:
        return False
    return hmac.compare_digest(guardado.huella, huella_presentada)


def canal_del_codigo(celular_verificado: bool, solo_correo: bool) -> Canal:
    """Al celular solo si está verificado y no se pidió el correo; si no, al correo."""
    return Canal.SMS if celular_verificado and not solo_correo else Canal.CORREO


def canal_del_aviso(canal_codigo: Canal, celular_verificado: bool) -> Canal:
    """El otro canal. Si el código fue al correo y el celular no está verificado, también al correo."""
    if canal_codigo is Canal.SMS:
        return Canal.CORREO
    return Canal.SMS if celular_verificado else Canal.CORREO


@dataclass(frozen=True)
class EnviosRecientes:
    """Los envíos a una huella: el último, y cuántos van en la ventana de una hora y en la de un día,
    con el inicio de cada ventana. Sin envíos, todo en cero o None."""

    ultimo: datetime | None = None
    en_hora: int = 0
    inicio_hora: datetime | None = None
    en_dia: int = 0
    inicio_dia: datetime | None = None


SIN_ENVIOS = EnviosRecientes()


def espera_envio(envios: EnviosRecientes, ahora: datetime, limite_hora: int, limite_dia: int) -> int:
    """Segundos (hacia arriba, al menos 1 si hay espera) que faltan para poder enviar otro. 0 si se puede."""
    if ahora.tzinfo is None:
        raise ValueError("El instante debe tener zona horaria")
    hasta: list[datetime] = []
    if envios.ultimo is not None:
        hasta.append(envios.ultimo + ESPERA_REENVIO)
    if envios.inicio_hora is not None and envios.en_hora >= limite_hora:
        hasta.append(envios.inicio_hora + VENTANA_HORA)
    if envios.inicio_dia is not None and envios.en_dia >= limite_dia:
        hasta.append(envios.inicio_dia + VENTANA_DIA)
    falta = max((h - ahora).total_seconds() for h in hasta) if hasta else 0.0
    if falta <= 0:
        return 0
    return max(1, int(-(-falta // 1)))


def espera_destino(envios: EnviosRecientes, ahora: datetime) -> int:
    return espera_envio(envios, ahora, LIMITE_HORA_DESTINO, LIMITE_DIA_DESTINO)


def espera_ip(envios: EnviosRecientes, ahora: datetime) -> int:
    """La IP no tiene los 60 s entre envíos: muchas personas pueden compartirla."""
    sin_ultimo = EnviosRecientes(None, envios.en_hora, envios.inicio_hora, envios.en_dia, envios.inicio_dia)
    return espera_envio(sin_ultimo, ahora, LIMITE_HORA_IP, LIMITE_DIA_IP)


def enmascarar_celular(e164: str | None) -> str | None:
    """+56912345637 → "+56 9 •••• ••37". None si no hay celular o no tiene la forma esperada."""
    if e164 is None or len(e164) != 12 or not e164.startswith("+569") or not e164[1:].isdigit():
        return None
    return f"+56 9 •••• ••{e164[-2:]}"
