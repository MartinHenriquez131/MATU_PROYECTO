"""Reglas puras de las secciones complementarias de la ficha (MATU-50, ADR-028, RF-03).

Contrato: docs/api/propuestos/ficha-ampliada.openapi.yaml (MATU-49). Sin I/O y sin reloj.

- Seis secciones opcionales, además de los tres campos base: quien_es, preferencias, alimentacion,
  movilidad, comunicacion y remedios, en ese orden (tabla de ADR-028). No cuentan para la completitud
  y se pueden quitar.
- Hasta 500 caracteres (800 en remedios), contados como los campos base: después de convertir
  ``\\r\\n`` en ``\\n`` y de quitar los espacios de los extremos. Una sección no se vacía: texto vacío o
  solo espacios es un 422 ``vacio`` y se quita con DELETE.
- Leen y escriben los mismos roles que la ficha (domain/ficha.puede_leer y puede_escribir).
- Quitar exige ``If-Match`` con un ETag de MATU. Sin él, o con ``*``, falta la precondición (428);
  ``If-None-Match`` en un DELETE es una petición inválida (422).
- Al compartir, los tres campos base van siempre y el servidor nunca agrega una sección por su cuenta:
  van solo las pedidas, que deben estar agregadas. ``remedios`` viene desmarcada por defecto (ADR-028).
- Un acceso de relevo ve una sección compartida solo si nació antes que el acceso, o en el mismo
  instante. Una sección quitada y vuelta a agregar es otra fila, con otro instante (decisión de Jorge del
  03-11). Editarla no cambia cuándo nació.
- El servidor no interpreta el texto: no lo clasifica ni deriva datos de él. Ningún error lleva el texto.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.modules.care_plan.domain.ficha import (
    CAMPOS_FICHA,
    FaltaPrecondicion,
    PrecondicionInvalida,
    SiCoincide,
    normalizar_texto,
    version_de_etag,
)


class SeccionComplementaria(StrEnum):
    QUIEN_ES = "quien_es"
    PREFERENCIAS = "preferencias"
    ALIMENTACION = "alimentacion"
    MOVILIDAD = "movilidad"
    COMUNICACION = "comunicacion"
    REMEDIOS = "remedios"


# En el orden de la tabla de ADR-028: es el orden de la ficha, del relevo y de la lista de un acceso
SECCIONES_COMPLEMENTARIAS: tuple[SeccionComplementaria, ...] = tuple(SeccionComplementaria)

LARGO_MAXIMO_SECCION = 500
LARGO_MAXIMO_REMEDIOS = 800

_TIPOS_BASE = frozenset(c.value for c in CAMPOS_FICHA)
_TIPOS_COMPLEMENTARIOS = frozenset(s.value for s in SECCIONES_COMPLEMENTARIAS)


def seccion_de(valor: str) -> SeccionComplementaria | None:
    """La sección con ese nombre, o None si no es una de las seis (la API responde 404).

    Un campo base (``rutina``, ``red_apoyo``…) o un tipo que la API ya no escribe (``horarios``,
    ``actividades``) tampoco es una sección complementaria.
    """
    try:
        return SeccionComplementaria(valor)
    except ValueError:
        return None


def largo_maximo(seccion: SeccionComplementaria) -> int:
    return LARGO_MAXIMO_REMEDIOS if seccion is SeccionComplementaria.REMEDIOS else LARGO_MAXIMO_SECCION


class TextoSeccionInvalido(ValueError):
    """El texto de una sección no se puede guardar. ``tipo`` va en errores[] del 422; nunca el texto."""

    def __init__(self, tipo: str, mensaje: str) -> None:
        super().__init__(tipo)
        self.tipo = tipo
        self.mensaje = mensaje


def validar_texto_seccion(seccion: SeccionComplementaria, texto: str) -> str:
    """El texto normalizado, listo para cifrar.

    - Vacío o solo espacios: TextoSeccionInvalido ``vacio``. Una sección se quita, no se vacía.
    - Más caracteres que el máximo de la sección: TextoSeccionInvalido ``largo_maximo``.

    Los caracteres de control los rechaza antes el esquema de la API, igual que en los campos base.
    """
    normalizado = normalizar_texto(texto)
    if not normalizado:
        raise TextoSeccionInvalido("vacio", "una sección no se guarda vacía: para sacarla, quítala")
    maximo = largo_maximo(seccion)
    if len(normalizado) > maximo:
        raise TextoSeccionInvalido("largo_maximo", f"admite hasta {maximo} caracteres")
    return normalizado


def precondicion_para_quitar(if_match: str | None, if_none_match: str | None) -> SiCoincide:
    """La precondición de DELETE …/plan/secciones/{seccion}, decidida solo con las cabeceras.

    - ``If-None-Match`` (con o sin ``If-Match``): PrecondicionInvalida (422). Quitar no crea nada.
    - Sin ``If-Match``, vacío o ``*``: FaltaPrecondicion (428). ``*`` no protege de borrar lo que otra
      persona acaba de escribir.
    - ``If-Match`` con un valor: SiCoincide con su versión (None si no es un ETag de MATU: 412).
    """
    if if_none_match is not None:
        raise PrecondicionInvalida("If-None-Match", "precondicion_invalida")
    if if_match is None or if_match.strip() in {"", "*"}:
        raise FaltaPrecondicion()
    return SiCoincide(version_de_etag(if_match))


# --- Compartir con un relevo --------------------------------------------------------------------------


class SeccionNoAgregada(ValueError):
    """Se pidió compartir una sección que no está agregada (422 ``seccion_no_agregada``). Sin el valor."""


def secciones_a_compartir(
    pedidas: Iterable[SeccionComplementaria], agregadas: Iterable[str]
) -> tuple[SeccionComplementaria, ...]:
    """Las secciones que comparte un acceso nuevo, en el orden de ADR-028.

    Solo las pedidas: nunca agrega una por su cuenta (``remedios`` solo va si viene). SeccionNoAgregada
    si alguna pedida no está agregada en el plan.
    """
    pedidas = set(pedidas)
    if not pedidas <= set(agregadas):
        raise SeccionNoAgregada()
    return tuple(s for s in SECCIONES_COMPLEMENTARIAS if s in pedidas)


def secciones_permitidas(secciones: Iterable[SeccionComplementaria]) -> tuple[str, ...]:
    """Lo que se guarda en acceso_relevo.secciones_permitidas: los tres campos base, siempre, y las
    secciones compartidas, en el orden de ADR-028."""
    elegidas = set(secciones)
    return tuple(c.value for c in CAMPOS_FICHA) + tuple(s.value for s in SECCIONES_COMPLEMENTARIAS if s in elegidas)


def campos_del_acceso(permitidas: Iterable[str]) -> tuple[str, ...]:
    """Los campos base de un acceso, en el orden de la ficha. Un acceso anterior a MATU-50 puede tener
    uno, dos o tres; uno nuevo, siempre los tres."""
    permitidas = set(permitidas)
    return tuple(c.value for c in CAMPOS_FICHA if c.value in permitidas)


def secciones_del_acceso(permitidas: Iterable[str]) -> tuple[SeccionComplementaria, ...]:
    """Las secciones complementarias que comparte un acceso, en el orden de ADR-028. Ninguna en los
    accesos anteriores a MATU-50."""
    permitidas = set(permitidas)
    return tuple(s for s in SECCIONES_COMPLEMENTARIAS if s.value in permitidas)


@dataclass(frozen=True)
class SeccionVisible:
    """Una sección ya descifrada, con el instante en que nació su fila. ``texto`` no sale en el repr."""

    tipo: SeccionComplementaria
    texto: str = field(repr=False)
    creado_en: datetime


def secciones_para_relevo(
    permitidas: Iterable[str], acceso_creado_en: datetime, secciones: Iterable[SeccionVisible]
) -> list[SeccionVisible]:
    """Lo que ve el relevo, en el orden de ADR-028: solo las secciones compartidas que todavía existen
    y que nacieron antes que el acceso o en el mismo instante. Una sección quitada no viene (no hay
    "Sin completar" para secciones). La política seccion_relevo de la base aplica la misma regla."""
    compartidas = set(secciones_del_acceso(permitidas))
    por_tipo = {s.tipo: s for s in secciones if s.tipo in compartidas and s.creado_en <= acceso_creado_en}
    return [por_tipo[s] for s in SECCIONES_COMPLEMENTARIAS if s in por_tipo]


def es_tipo_base(tipo: str) -> bool:
    return tipo in _TIPOS_BASE


def es_tipo_complementario(tipo: str) -> bool:
    return tipo in _TIPOS_COMPLEMENTARIOS
