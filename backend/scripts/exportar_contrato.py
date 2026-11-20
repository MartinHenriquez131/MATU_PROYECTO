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


def ordenar_como(actual: Any, previo: Any) -> Any:
    """El contrato de la API con el orden de claves del archivo versionado (hallazgo del 19-11 en MATU-79).

    En cada objeto, las claves que ya estaban van en el orden del archivo y las nuevas van al final, en orden
    alfabético; las que ya no existen salen. Las listas conservan el orden de la API (parameters, required, enum y
    allOf tienen significado), y cada elemento toma el orden de claves del que tenía la misma posición. Así --escribir
    cambia solo las líneas que de verdad cambian, y dos ramas que agregan rutas distintas no reordenan el archivo."""
    if isinstance(actual, dict):
        anterior = previo if isinstance(previo, dict) else {}
        claves = [c for c in anterior if c in actual] + sorted(c for c in actual if c not in anterior)
        return {c: ordenar_como(actual[c], anterior.get(c)) for c in claves}
    if isinstance(actual, list):
        lista = previo if isinstance(previo, list) else []
        return [ordenar_como(v, lista[i] if i < len(lista) else None) for i, v in enumerate(actual)]
    return actual


def escribir(actual: dict[str, Any], archivo: Path) -> bool:
    """Escribe el contrato con el orden del archivo que ya existe. Si coincide por contenido, no lo toca (False)."""
    previo = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}
    if archivo.exists() and not diferencias(previo, actual):
        return False
    archivo.write_text(serializar(ordenar_como(actual, previo)), encoding="utf-8", newline="\n")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--escribir", action="store_true", help="regenera docs/api/openapi.json en vez de comparar")
    args = parser.parse_args(argv)

    actual = exportar()
    esperado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    cambios = diferencias(esperado, actual)
    if args.escribir:
        # La comparación es por contenido, no por orden de claves: si ya coincide, el archivo no se toca y no
        # aparece una diferencia de solo orden que choque con otras ramas. Si no coincide, se escribe con el orden del
        # archivo (ordenar_como): solo cambian las líneas que cambian (hallazgo del 19-11)
        if not escribir(actual, ARCHIVO):
            print("docs/api/openapi.json ya coincide con la API: no se reescribe")
            return 0
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
