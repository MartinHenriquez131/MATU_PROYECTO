"""Exporta el contrato de la API desde app.openapi() y lo compara con docs/api/openapi.json (MATU-79).

Es la puerta «openapi-diff» de la estrategia de pruebas, sección 8: falla si el código expone un contrato distinto
del versionado. Nunca mira docs/api/propuestos/ (docs/api/README.md).

    python scripts/exportar_contrato.py              # compara; sale con 1 y lista las diferencias si no coinciden
    python scripts/exportar_contrato.py --escribir   # regenera docs/api/openapi.json

Se corre desde backend/. Arma la app con ENTORNO=pruebas (publica /openapi.json) y CAPA3_HABILITADA=true (el contrato
incluye las rutas del despacho), sin leer el .env: el contrato no depende de ningún secreto, y así da lo mismo en el
equipo de cada uno y en el CI. Ninguna conexión se abre: crear la app no toca la base ni Redis.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO = RAIZ / "docs" / "api" / "openapi.json"
MAX_DIFERENCIAS = 40


def exportar() -> dict[str, Any]:
    """El contrato que expone hoy la API, con la configuración fija del contrato y sin el .env."""
    sys.path.insert(0, str(RAIZ / "backend"))
    from app.core import config

    # Solo estas dos variables importan. Cualquier otra que traiga el entorno queda igual, pero el .env no se lee
    os.environ["ENTORNO"] = "pruebas"
    os.environ["CAPA3_HABILITADA"] = "true"
    config.Configuracion.model_config["env_file"] = None
    config.obtener_configuracion.cache_clear()

    from app.main import crear_app

    # El stream de logs propio evita que el arranque escriba en la salida del script
    esquema: dict[str, Any] = crear_app(io.StringIO()).openapi()
    return esquema


def serializar(esquema: dict[str, Any]) -> str:
    """El formato de docs/api/openapi.json: dos espacios, UTF-8 sin escapes y un salto de línea al final."""
    return json.dumps(esquema, indent=2, ensure_ascii=False) + "\n"


def diferencias(esperado: Any, actual: Any, ruta: str = "") -> list[str]:
    """Las rutas JSON donde el contrato versionado (esperado) y el de la API (actual) no coinciden."""
    if isinstance(esperado, dict) and isinstance(actual, dict):
        salida: list[str] = []
        for clave in sorted(set(esperado) | set(actual)):
            sub = f"{ruta}/{clave}"
            if clave not in actual:
                salida.append(f"solo en openapi.json: {sub}")
            elif clave not in esperado:
                salida.append(f"solo en la API: {sub}")
            else:
                salida.extend(diferencias(esperado[clave], actual[clave], sub))
        return salida
    if esperado != actual:
        return [f"distinto: {ruta or '/'}"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--escribir", action="store_true", help="regenera docs/api/openapi.json en vez de comparar")
    args = parser.parse_args(argv)

    actual = exportar()
    esperado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    cambios = diferencias(esperado, actual)
    if args.escribir:
        # La comparación es por contenido, no por orden de claves: si ya coincide, el archivo no se toca y no
        # aparece una diferencia de solo orden que choque con otras ramas
        if not cambios:
            print("docs/api/openapi.json ya coincide con la API: no se reescribe")
            return 0
        ARCHIVO.write_text(serializar(actual), encoding="utf-8", newline="\n")
        print(f"Escrito {ARCHIVO.relative_to(RAIZ).as_posix()}: {len(actual.get('paths', {}))} rutas")
        return 0

    if not cambios:
        print(f"docs/api/openapi.json coincide con la API: {len(actual.get('paths', {}))} rutas")
        return 0
    print(f"docs/api/openapi.json no coincide con la API: {len(cambios)} diferencias", file=sys.stderr)
    for linea in cambios[:MAX_DIFERENCIAS]:
        print(f"  {linea}", file=sys.stderr)
    if len(cambios) > MAX_DIFERENCIAS:
        print(f"  ... y {len(cambios) - MAX_DIFERENCIAS} más", file=sys.stderr)
    print("Si el cambio es a propósito: cd backend && python scripts/exportar_contrato.py --escribir", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
