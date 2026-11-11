"""Las condiciones del pedido vigentes (MATU-61, D6, R13; decisión 207).

Una sola fuente en el backend: app/modules/ordering/condiciones/condiciones-pedido-<versión>.md, copia exacta de
docs/legal/condiciones-pedido.md del repositorio MATU (v0.1 del piloto, aprobada por Jorge el 11-11) desde
«## 1. Quién vende» hasta el final: el encabezado queda fuera, como la política cuenta desde «En un minuto» (decisión
de Jorge del 11-11). Tienen versión propia, separada de la política (D6). La huella es la SHA-256 de ese texto exacto,
el que se entrega (UTF-8, saltos LF).

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
    "0.1": (
        date(2026, 11, 11),
        "966f02be1457944be712d8c064ce19aeb6cff25e9543083f96c8e21fc7f08e4f",  # pragma: allowlist secret
    ),
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
