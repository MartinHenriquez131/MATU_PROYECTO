"""Reglas puras de la ficha de relevo (MATU-12, RF-02, ADR-023, contrato docs/api/propuestos/ficha.openapi.yaml).

Sin I/O y sin reloj: aquí viven los tres campos, quién lee y quién escribe, cómo se normaliza el
texto, la completitud y el ETag. El cifrado es un puerto (CifradorSecciones) y la persistencia otro.

- La ficha tiene tres campos, cada uno un tipo de plan_seccion: ``rutina`` (Su día),
  ``manejo_situaciones`` (Si se altera) y ``red_apoyo`` (A quién llamar). Las preguntas guía y los
  ejemplos son textos de la interfaz (docs/lenguaje.md, 5.1 a 5.3): el contrato no los incluye.
- Leen admin, cuidador y pagador con puede_ver_plan. Escriben admin y cuidador. Para cualquier otro
  la API responde 404, nunca 403 (contrato, decisión 4).
- Cada campo admite hasta 500 caracteres, contados después de quitar los espacios de los extremos
  y de convertir ``\\r\\n`` en ``\\n``. Admite saltos de línea y ningún otro carácter de control.
- Un campo con texto vacío está "Sin completar". Completitud = round(100 × campos con texto / 3).
- El servidor no interpreta el texto: no lo clasifica ni deriva datos de él (analista normativo).
- Ningún error de este módulo lleva el texto recibido.
- Toda escritura es condicional (MATU-13, RF-04, ADR-015): ``If-Match: "<etag>"`` sobre un campo
  que existe, ``If-None-Match: *`` en la primera escritura. Sin cabeceras, o con ``If-Match: *``,
  falta la precondición (428). Las dos a la vez, o ``If-None-Match`` distinto de ``*``, es una
  petición inválida (422). No hay fusión automática: quien pierde recibe el contenido actual.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# El plan del MVP es la ficha de relevo (ADR-023): es el modo con que nace en la primera escritura
MODO_FICHA_RELEVO = "ficha_relevo"


class CampoFicha(StrEnum):
    RUTINA = "rutina"
    MANEJO_SITUACIONES = "manejo_situaciones"
    RED_APOYO = "red_apoyo"


# En el orden de la interfaz: Su día, Si se altera, A quién llamar
CAMPOS_FICHA: tuple[CampoFicha, ...] = (CampoFicha.RUTINA, CampoFicha.MANEJO_SITUACIONES, CampoFicha.RED_APOYO)

LARGO_MAXIMO_CAMPO = 500

ROLES_QUE_ESCRIBEN = frozenset({"admin", "cuidador"})
ROLES_QUE_LEEN_SIEMPRE = frozenset({"admin", "cuidador"})
ROL_PAGADOR = "pagador"

# Salto de línea: el único carácter de control que admite un campo
_SALTO = "\n"


def campo_de(valor: str) -> CampoFicha | None:
    """El campo de la ficha con ese nombre, o None si no es uno de los tres (la API responde 404)."""
    try:
        return CampoFicha(valor)
    except ValueError:
        return None


def puede_leer(rol: str, puede_ver_plan: bool) -> bool:
    """admin y cuidador siempre; pagador solo con puede_ver_plan; observador nunca."""
    return rol in ROLES_QUE_LEEN_SIEMPRE or (rol == ROL_PAGADOR and puede_ver_plan)


def puede_escribir(rol: str) -> bool:
    """admin y cuidador. El pagador no escribe, ni siquiera con puede_ver_plan."""
    return rol in ROLES_QUE_ESCRIBEN


def normalizar_texto(texto: str) -> str:
    """El texto tal como se guarda: ``\\r\\n`` (y ``\\r`` suelto) como ``\\n``, sin espacios en los extremos.

    No valida el largo ni los caracteres: eso lo hace ``validar_texto``.
    """
    return texto.replace("\r\n", _SALTO).replace("\r", _SALTO).strip()


def tiene_caracteres_de_control(texto: str) -> bool:
    """Si el texto trae un carácter de control distinto del salto de línea (C0, DEL o C1)."""
    return any((ord(c) < 32 and c != _SALTO) or 127 <= ord(c) < 160 for c in texto)


def completitud(campos_con_texto: int) -> int:
    """round(100 × campos_con_texto / 3): 0, 33, 67 o 100. La interfaz nunca bloquea por ella (ADR-018)."""
    if not 0 <= campos_con_texto <= len(CAMPOS_FICHA):
        raise ValueError("campos_con_texto fuera de rango")
    return round(100 * campos_con_texto / len(CAMPOS_FICHA))


def etag(version: int) -> str:
    """ETag fuerte del campo: ``"v<version>"`` (contrato, decisión 7). Opaco para el cliente."""
    if version < 1:
        raise ValueError("la versión de un campo parte en 1")
    return f'"v{version}"'


def version_de_etag(valor: str) -> int | None:
    """La versión de un ETag ``"v<n>"`` emitido por ``etag``, o None si no es uno de ellos.

    Comparación fuerte (RFC 9110, 8.8.3.2): un ETag débil (``W/"v3"``), una lista o cualquier otro
    valor no coincide con ninguna versión, y la escritura responde 412.
    """
    valor = valor.strip()
    if len(valor) < 4 or not (valor.startswith('"v') and valor.endswith('"')):
        return None
    numero = valor[2:-1]
    if not numero.isascii() or not numero.isdigit() or numero.startswith("0"):
        return None
    return int(numero)


class FaltaPrecondicion(Exception):
    """Escritura no condicional: sin If-Match ni If-None-Match, o con ``If-Match: *`` (428)."""


class PrecondicionInvalida(Exception):
    """Cabeceras de precondición mal formadas: las dos a la vez, o If-None-Match distinto de ``*`` (422).

    ``cabecera`` nombra la cabecera, nunca su valor.
    """

    def __init__(self, cabecera: str, tipo: str) -> None:
        super().__init__(tipo)
        self.cabecera = cabecera
        self.tipo = tipo


@dataclass(frozen=True)
class SiCoincide:
    """``If-Match``: escribir solo si el campo existe y está en ``version``.

    ``version`` None: el ETag no es uno emitido por MATU, así que nunca coincide (412).
    """

    version: int | None


@dataclass(frozen=True)
class SiNoExiste:
    """``If-None-Match: *``: escribir solo si el campo nunca se escribió."""


Precondicion = SiCoincide | SiNoExiste


def precondicion_de(if_match: str | None, if_none_match: str | None) -> Precondicion:
    """La precondición de una escritura, decidida solo con las cabeceras, sin leer la base.

    - Las dos cabeceras: PrecondicionInvalida (422).
    - ``If-None-Match`` distinto de ``*``: PrecondicionInvalida (422). Solo se admite ``*``.
    - Ninguna, o ``If-Match: *``: FaltaPrecondicion (428). ``*`` no protege de pisar a otro.
    - ``If-None-Match: *``: SiNoExiste.
    - ``If-Match`` con un valor: SiCoincide con su versión (None si no es un ETag de MATU).
    """
    if if_match is not None and if_none_match is not None:
        raise PrecondicionInvalida("If-None-Match", "precondicion_doble")
    if if_none_match is not None:
        if if_none_match.strip() != "*":
            raise PrecondicionInvalida("If-None-Match", "precondicion_invalida")
        return SiNoExiste()
    if if_match is None or if_match.strip() in {"", "*"}:
        raise FaltaPrecondicion()
    return SiCoincide(version_de_etag(if_match))


@dataclass(frozen=True)
class Autor:
    """Quién guardó un campo: su id y su nombre, nunca su email (analista normativo, condición 6)."""

    id: uuid.UUID
    nombre: str


@dataclass(frozen=True)
class EstadoCampo:
    """Un campo leído y descifrado.

    | texto | version | Significado        |
    |-------|---------|--------------------|
    | None  | None    | Nunca se escribió  |
    | None  | n       | Se vació           |
    | texto | n       | Escrito            |
    """

    texto: str | None
    version: int | None
    actualizado_por: Autor | None
    actualizado_en: datetime | None

    @property
    def con_texto(self) -> bool:
        return bool(self.texto)


CAMPO_NUNCA_ESCRITO = EstadoCampo(texto=None, version=None, actualizado_por=None, actualizado_en=None)


def texto_visible(texto: str) -> str | None:
    """Un campo vaciado se guarda como texto vacío y se muestra como ``null``."""
    return texto or None
