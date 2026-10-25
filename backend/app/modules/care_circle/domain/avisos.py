"""Avisos canónicos que MATU muestra al dar una autorización (MATU-07, RF-01, Ley 21.719).

El texto es literal de la política de privacidad v0.9 (docs/legal/politica-privacidad.md del
repositorio MATU, sección 5, "Aviso para quien cuida sin ser representante legal"). Vive aquí como
datos, no como Markdown, para que el servidor sea la única fuente del texto que se muestra y para
que la evidencia del consentimiento pueda citar exactamente qué versión se mostró.

Cambiar una sola letra del título o de un párrafo es una versión nueva del aviso: se sube
``version`` y cambia ``sha256``. Las evidencias ya guardadas siguen citando la versión anterior.
"""

import hashlib
import unicodedata
from dataclasses import dataclass

# Separador de título y párrafos al calcular el hash: una línea en blanco, como en el documento
SEPARADOR_PARRAFOS = "\n\n"


@dataclass(frozen=True)
class Aviso:
    """Un aviso versionado: identificador, versión, título y párrafos en texto plano."""

    id: str
    version: str
    titulo: str
    parrafos: tuple[str, ...]

    @property
    def sha256(self) -> str:
        """SHA-256 en hexadecimal del título y los párrafos unidos por una línea en blanco.

        El texto se normaliza a Unicode NFC y se codifica en UTF-8 antes del hash, para que la
        misma frase escrita con tildes compuestas o precompuestas dé el mismo resultado.
        """
        texto = SEPARADOR_PARRAFOS.join((self.titulo, *self.parrafos))
        return hashlib.sha256(unicodedata.normalize("NFC", texto).encode("utf-8")).hexdigest()


AVISO_CUIDADOR_DE_HECHO = Aviso(
    id="aviso_cuidador_de_hecho",
    version="1.0",
    titulo="Aviso: tu autorización tiene un límite",
    parrafos=(
        "Declaraste que cuidas a esta persona y que no eres su representante legal. Con esa declaración "
        "puedes organizar su cuidado en MATU, pero tu autorización no equivale a la de la propia persona ni "
        "a la de su representante legal. MATU no puede comprobar lo que declaras. Por eso deja registrado "
        "que la autorización la diste tú, como cuidadora o cuidador de hecho, con la fecha y la versión de "
        "la política.",
        "Te pedimos tres cosas: anota solo lo necesario para su cuidado, cuéntale qué guardas en MATU si "
        "puede comprenderlo, y respeta lo que ella decida. Ella o su representante legal pueden pedir en "
        "cualquier momento que se borren sus datos.",
        "En 12 meses te pediremos confirmar que sigues a cargo de su cuidado.",
    ),
)
