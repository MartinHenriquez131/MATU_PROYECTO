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
