"""Los textos publicados de la política de privacidad (MATU-75), en app/modules/iam/politica/.

Cada archivo politica-<versión>.md lo genera backend/scripts/generar_politica.py desde
docs/legal/politica-privacidad.md del repositorio MATU. PUBLICADAS fija, por versión, la huella SHA-256 del archivo
tal como está en el repositorio (saltos LF). Es el texto que se sirve, sin reemplazar nada.

Si el archivo cambia y su huella no, la versión no se sirve: GET /v1/politica y POST /v1/usuarios responden 503.
Así un texto nuevo no sale con el número de una versión anterior. Un texto nuevo es una versión nueva: otro archivo,
otra fila aquí y POLITICA_VERSION en la configuración. tests/modules/iam/test_politica.py lo verifica.
"""

from functools import lru_cache
from pathlib import Path

from app.modules.iam.domain.politica import PoliticaNoDisponible, huella_de, normalizar_saltos

CARPETA = Path(__file__).resolve().parents[1] / "politica"

# Versión → huella del archivo. Una fila por versión publicada; nunca se cambia la de una versión que ya se sirvió.
# La huella es pública, no un secreto: por eso el pragma de detect-secrets
PUBLICADAS: dict[str, str] = {
    "0.11": "d1753de4cbe31c87a8e8fb97c7b5e7d89b9667a2e29bcb846008c7b62a5a2e3c",  # pragma: allowlist secret
    # MATU-61 (D11): los pedidos de insumos, con su autorización aparte. La 0.11 sigue publicada para quien la aceptó
    "0.12": "c58e1e8aac0091dcc5c205d7bf0a514c7f2d25cc1bd4c1fb514322a479845132",  # pragma: allowlist secret
    # MATU-62 (D11): el pago con Transbank. La 0.12 y la 0.11 siguen publicadas para quien las aceptó
    "0.13": "135dc42b6ff28e53f32e3291a151762248a9dee3150e33b3b1e61d03a744844f",  # pragma: allowlist secret
}


def archivo_de(version: str) -> Path:
    return CARPETA / f"politica-{version}.md"


@lru_cache
def texto_publicado(version: str) -> str:
    """El texto de la versión, tal cual. Lanza PoliticaNoDisponible si no está publicada, si el archivo no está o
    si su huella no es la de PUBLICADAS."""
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
