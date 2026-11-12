"""La imagen de Railway trae los archivos de `web/public` (MATU-55, prueba de Martín en el iPhone del 12-11).

Vite copia `web/public` a la raíz de `dist`: `manifest.webmanifest`, `apple-touch-icon.png`, los íconos y `sw.js`.
Sin ellos, en Railway responden 404, iOS agrega MATU a la pantalla de inicio sin ícono y los avisos en el teléfono
no se pueden activar, porque el service worker no existe. Las pruebas de `web/` no lo detectan porque no usan Docker.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCKERFILE = RAIZ / "infra" / "railway" / "Dockerfile"
PUBLICOS = ("manifest.webmanifest", "apple-touch-icon.png", "sw.js")


def copia_web_public(dockerfile: str) -> bool:
    for linea in dockerfile.splitlines():
        partes = linea.strip().split()
        if len(partes) >= 3 and partes[0].upper() == "COPY" and "web/public" in {p.rstrip("/") for p in partes[1:-1]}:
            return True
    return False


def test_el_dockerfile_copia_web_public() -> None:
    assert copia_web_public(DOCKERFILE.read_text(encoding="utf-8")), (
        "infra/railway/Dockerfile no copia web/public: el build de Railway queda sin manifest, íconos ni sw.js"
    )


def test_web_public_tiene_los_archivos_de_la_app() -> None:
    for nombre in PUBLICOS:
        assert (RAIZ / "web" / "public" / nombre).is_file(), nombre


def test_el_verificador_no_pasa_en_vacio() -> None:
    assert not copia_web_public("COPY web/src ./src\nCOPY web/doble ./doble\n")
    assert not copia_web_public("# COPY web/public ./public\n")
    assert copia_web_public("COPY web/public ./public\n")
    assert copia_web_public("COPY web/public/ ./public/\n")
