"""Los textos publicados de la política de privacidad (MATU-75), en app/modules/iam/politica/.

Cada archivo politica-<versión>.md lo genera backend/scripts/generar_politica.py desde
docs/legal/politica-privacidad.md del repositorio MATU. PUBLICADAS fija, por versión, la huella SHA-256 del archivo
tal como está en el repositorio (con el marcador {correo_privacidad}, saltos LF).

Si el archivo cambia y su huella no, la versión no se sirve: GET /v1/politica y POST /v1/usuarios responden 503.
Así un texto nuevo no sale con el número de una versión anterior. Un texto nuevo es una versión nueva: otro archivo,
otra fila aquí y POLITICA_VERSION en la configuración. tests/modules/iam/test_politica.py lo verifica.
"""

from functools import lru_cache
from pathlib import Path

from app.modules.iam.domain.politica import PoliticaNoDisponible, huella_de, normalizar_saltos

CARPETA = Path(__file__).resolve().parents[1] / "politica"

# Versión → huella del archivo. Una fila por versión publicada; nunca se cambia la de una versión que ya se sirvió
PUBLICADAS: dict[str, str] = {
    "0.11": "941efe228ad04aa14078e55a3640d44d4538f65e3d92eefe78b0f017e6e7c467",
}


def archivo_de(version: str) -> Path:
    return CARPETA / f"politica-{version}.md"


@lru_cache
def plantilla_publicada(version: str) -> str:
    """El texto de la versión, con el marcador del correo. Lanza PoliticaNoDisponible si no está publicada, si el
    archivo no está o si su huella no es la de PUBLICADAS."""
    esperada = PUBLICADAS.get(version)
    if esperada is None:
        raise PoliticaNoDisponible("la versión configurada no tiene un texto publicado")
    try:
        texto = normalizar_saltos(archivo_de(version).read_text(encoding="utf-8"))
    except OSError:
        raise PoliticaNoDisponible("no se encuentra el archivo del texto") from None
    if huella_de(texto) != esperada:
        raise PoliticaNoDisponible("el texto de la versión cambió y su huella no")
    return texto
