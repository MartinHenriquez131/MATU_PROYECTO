"""Reglas puras del cifrado de las secciones de la ficha (MATU-11, ADR-014, ADR-016, modelo de
datos sección 6).

Sin I/O, sin reloj y sin biblioteca criptográfica: aquí viven los estados de la clave de datos,
los datos asociados (AAD) y la forma de una sección cifrada. El cifrado con AES-256-GCM y la
custodia de la clave maestra son adaptadores (infrastructure/ y el puerto CustodiaClaves).

- La clave de datos (DEK) de una persona tiene tres estados que no se confunden: todavía no
  existe (se crea en la primera escritura), vigente, y destruida (borrado criptográfico).
  Con la clave destruida no se escribe ni se lee, y nunca se genera una clave de reemplazo.
- AAD = plan_id ‖ tipo: los 16 bytes del UUID del plan, seguidos del tipo en UTF-8. El plan
  tiene largo fijo, así que la concatenación no es ambigua. Mover un texto cifrado a otra
  sección o a otro plan cambia el AAD y el descifrado falla.
- Ningún error de este módulo lleva en su mensaje el texto, la clave ni un valor recibido:
  cada uno tiene un mensaje fijo y genérico.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum

LARGO_DEK = 32  # AES-256
LARGO_NONCE = 12  # 96 bits, el recomendado para GCM
LARGO_TAG = 16  # 128 bits

# Los tipos que admite plan_seccion (CHECK de 01_esquema.sql). La ficha de relevo usa tres:
# rutina, manejo_situaciones y red_apoyo (ADR-023).
TIPOS_SECCION = frozenset(
    {
        "rutina",
        "horarios",
        "manejo_situaciones",
        "preferencias",
        "actividades",
        "red_apoyo",
        "alimentacion",
        "movilidad",
    }
)


# --- Errores de dominio -------------------------------------------------------------------------


class ErrorCifrado(Exception):
    """Base de los errores del cifrado. El mensaje es siempre el fijo de la clase: ningún
    argumento entra en str(), repr() ni args, para que nada sensible llegue a un log o a una
    respuesta por accidente."""

    mensaje = "no se pudo descifrar la sección"

    def __init__(self) -> None:
        super().__init__(self.mensaje)


class ClaveDestruida(ErrorCifrado):
    """La clave de datos de la persona fue destruida (borrado criptográfico). No se lee ni se
    escribe, y nunca se crea una clave nueva en su lugar."""

    mensaje = "la clave de datos de la persona fue destruida"


class ClaveInexistente(ErrorCifrado):
    """La persona todavía no tiene clave de datos: nunca se escribió su ficha. Es un estado
    distinto de ClaveDestruida."""

    mensaje = "la persona todavía no tiene clave de datos"


class ClaveNoDisponible(ErrorCifrado):
    """La custodia no pudo envolver o desenvolver la clave de datos."""

    mensaje = "no se pudo obtener la clave de datos"


class SeccionIlegible(ErrorCifrado):
    """El texto cifrado fue alterado, se movió de sección o de plan, o no corresponde a la clave."""

    mensaje = "no se pudo descifrar la sección"


class TipoSeccionInvalido(ErrorCifrado):
    mensaje = "tipo de sección desconocido"


# --- La clave de datos de una persona -------------------------------------------------------------


class EstadoClave(StrEnum):
    NO_EXISTE = "no_existe"
    VIGENTE = "vigente"
    DESTRUIDA = "destruida"


@dataclass(frozen=True)
class ClaveGuardada:
    """La fila de clave_datos de una persona, tal como se lee de la base.

    ``dek_cifrada`` es la DEK envuelta con la KEK, o None si la clave fue destruida: el CHECK
    clave_datos_destruccion amarra dek_cifrada_con_kek NULL a destruida_en con valor. No sale en
    el repr: ni la DEK envuelta llega a un log.
    """

    kek_version: int
    dek_cifrada: bytes | None = field(repr=False)

    @property
    def destruida(self) -> bool:
        return self.dek_cifrada is None


def estado_clave(clave: ClaveGuardada | None) -> EstadoClave:
    if clave is None:
        return EstadoClave.NO_EXISTE
    return EstadoClave.DESTRUIDA if clave.destruida else EstadoClave.VIGENTE


def clave_para_escribir(clave: ClaveGuardada | None) -> ClaveGuardada | None:
    """La clave con que se escribe una sección.

    - None si la persona no tiene clave: hay que crearla (primera escritura de la ficha).
    - La clave, si está vigente.
    - ClaveDestruida si fue destruida. Nunca None en ese caso: eso llevaría a crear otra.
    """
    if estado_clave(clave) is EstadoClave.DESTRUIDA:
        raise ClaveDestruida()
    return clave


def clave_para_leer(clave: ClaveGuardada | None) -> ClaveGuardada:
    """La clave con que se lee una sección. ClaveInexistente si nunca se creó, ClaveDestruida si
    fue destruida."""
    estado = estado_clave(clave)
    if estado is EstadoClave.NO_EXISTE:
        raise ClaveInexistente()
    if estado is EstadoClave.DESTRUIDA:
        raise ClaveDestruida()
    assert clave is not None
    return clave


# --- Datos asociados y sección cifrada --------------------------------------------------------------


def datos_asociados(plan_id: uuid.UUID, tipo: str) -> bytes:
    """AAD = plan_id ‖ tipo: los 16 bytes del UUID seguidos del tipo en UTF-8.

    Lanza TipoSeccionInvalido si el tipo no es uno de TIPOS_SECCION.
    """
    if tipo not in TIPOS_SECCION:
        raise TipoSeccionInvalido()
    return plan_id.bytes + tipo.encode("utf-8")


@dataclass(frozen=True)
class SeccionCifrada:
    """Lo que se guarda en plan_seccion: contenido_cifrado, nonce, tag_auth y kek_version.

    ``kek_version`` es la versión de KEK que envolvía la DEK con que se cifró la sección (la de
    clave_datos en ese momento). Se registra como pide el modelo de datos; para descifrar se usa
    siempre la DEK vigente de clave_datos, que es la misma aunque la KEK rote.

    Un nonce o un tag de largo distinto al de AES-GCM es una sección ilegible.
    """

    contenido_cifrado: bytes = field(repr=False)
    nonce: bytes
    tag_auth: bytes
    kek_version: int

    def __post_init__(self) -> None:
        if len(self.nonce) != LARGO_NONCE or len(self.tag_auth) != LARGO_TAG:
            raise SeccionIlegible()
