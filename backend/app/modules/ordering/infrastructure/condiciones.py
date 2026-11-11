"""Las condiciones del pedido vigentes (MATU-61, D6, R13; decisión 207).

Una sola fuente en el backend: app/modules/ordering/condiciones/condiciones-pedido-<versión>.md, el texto para la
persona de docs/legal/condiciones-pedido.md (v0.1 del piloto, aprobada por Jorge el 11-11), sin las notas internas
ni las citas a consultas legales. Tienen versión propia, separada de la política (D6). La huella es la SHA-256 del
texto exacto que se entrega (UTF-8, saltos LF), como la de la política (MATU-75).

PUBLICADAS ata cada versión a su huella: si el archivo cambia y la tabla no, las condiciones no se sirven y la
prueba falla. Un texto nuevo es una versión nueva.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Final

from app.modules.iam.domain.politica import huella_de, normalizar_saltos

CARPETA = Path(__file__).resolve().parents[1] / "condiciones"
VERSION_VIGENTE = "0.1"

PUBLICADAS: dict[str, tuple[date, str]] = {
    "0.1": (date(2026, 11, 11), "38f4c899b183d16a1aecabb6889dec61ef39926e0a0a5c90a75f1080c3aaea9b"),
}
ENLACE: Final = "/v1/condiciones-pedido"


class CondicionesNoDisponibles(RuntimeError):
    """El texto no está o no calza con su huella publicada. Mensaje fijo."""


@dataclass(frozen=True)
class Condiciones:
    version: str
    actualizada_en: date
    huella: str
    texto: str


@lru_cache
def condiciones_vigentes() -> Condiciones:
    actualizada_en, publicada = PUBLICADAS[VERSION_VIGENTE]
    archivo = CARPETA / f"condiciones-pedido-{VERSION_VIGENTE}.md"
    texto = normalizar_saltos(archivo.read_text(encoding="utf-8"))
    huella = huella_de(texto)
    if huella != publicada:
        raise CondicionesNoDisponibles("el texto de las condiciones no es el publicado")
    return Condiciones(version=VERSION_VIGENTE, actualizada_en=actualizada_en, huella=huella, texto=texto)
