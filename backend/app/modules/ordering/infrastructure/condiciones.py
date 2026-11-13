"""Las condiciones del pedido (MATU-61, D6, R13; decisión 207; MATU-62, decisión 240).

Una sola fuente en el backend: app/modules/ordering/condiciones/condiciones-pedido-<versión>.md, copia exacta de
docs/legal/condiciones-pedido.md del repositorio MATU (v0.1 del piloto, aprobada por Jorge el 11-11) desde
«## 1. Quién vende» hasta el final: el encabezado queda fuera, como la política cuenta desde «En un minuto» (decisión
de Jorge del 11-11). Tienen versión propia, separada de la política (D6). La huella es la SHA-256 de ese texto exacto,
el que se entrega (UTF-8, saltos LF).

PUBLICADAS ata cada versión a su huella: si el archivo cambia y la tabla no, las condiciones no se sirven y la
prueba falla. Un texto nuevo es una versión nueva.

MATU-62: la vigente pasa a la 0.2 (segunda revisión previa del analista, 5.3, aprobada el 11-11), con el pago y la
frase del piloto **dentro** del texto con huella (decisión 221). La 0.1 sigue publicada para quien la aceptó:
condiciones_de(version) entrega cualquier versión publicada (GET /v1/condiciones-pedido?version=, decisión 240).

MATU-63: la vigente pasa a la 0.3 (D-63-16), y la 0.2 y la 0.1 siguen publicadas para quien las aceptó.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Final

from app.modules.iam.domain.politica import huella_de, normalizar_saltos

CARPETA = Path(__file__).resolve().parents[1] / "condiciones"
VERSION_VIGENTE = "0.3"

PUBLICADAS: dict[str, tuple[date, str]] = {
    "0.1": (
        date(2026, 11, 11),
        "966f02be1457944be712d8c064ce19aeb6cff25e9543083f96c8e21fc7f08e4f",  # pragma: allowlist secret
    ),
    # MATU-62: el pago, quién acepta, el pago tardío y lo que pasa si no se puede devolver
    "0.2": (
        date(2026, 11, 11),
        "64859e519a0aa19bb56b415256d2d9757f162e278824edffb1092a2985a334b7",  # pragma: allowlist secret
    ),
    # MATU-63 (D-63-16): lo que pasa después de pagar (faltantes, cancelar, entrega y retracto). Solo la aceptan los
    # pedidos nuevos; los que aceptaron la 0.1 o la 0.2 se cumplen según la suya (el envío del retracto, D-63-10)
    "0.3": (
        date(2026, 11, 13),
        "b228a65bc9d58b3d669dc45574567b92d00789e6f218ce44461789250d95739c",  # pragma: allowlist secret
    ),
}
ENLACE: Final = "/v1/condiciones-pedido"


class CondicionesNoDisponibles(RuntimeError):
    """El texto no está o no calza con su huella publicada. Mensaje fijo."""


class VersionNoPublicada(LookupError):
    """La versión pedida nunca se publicó (404)."""


@dataclass(frozen=True)
class Condiciones:
    version: str
    actualizada_en: date
    huella: str
    texto: str


@lru_cache
def condiciones_de(version: str) -> Condiciones:
    """Una versión publicada alguna vez, con su texto y su huella. VersionNoPublicada si nunca se publicó."""
    if version not in PUBLICADAS:
        raise VersionNoPublicada(version)
    actualizada_en, publicada = PUBLICADAS[version]
    archivo = CARPETA / f"condiciones-pedido-{version}.md"
    try:
        texto = normalizar_saltos(archivo.read_text(encoding="utf-8"))
    except OSError:
        raise CondicionesNoDisponibles("el texto de las condiciones no está") from None
    huella = huella_de(texto)
    if huella != publicada:
        raise CondicionesNoDisponibles("el texto de las condiciones no es el publicado")
    return Condiciones(version=version, actualizada_en=actualizada_en, huella=huella, texto=texto)


def condiciones_vigentes() -> Condiciones:
    return condiciones_de(VERSION_VIGENTE)
