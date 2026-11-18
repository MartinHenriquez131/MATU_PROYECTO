"""Trazabilidad de los requisitos Debe contra las pruebas (MATU-79, estrategia de pruebas, sección 14).

Lista los requisitos comprometidos como *Debe* que no tienen ninguna prueba marcada con @pytest.mark.rf("RF-NN"), y
sale con 1 si hay alguno: «un requisito comprometido sin prueba no está terminado».

    python scripts/trazabilidad.py --arquitectura ../../MATU/docs/arquitectura.md

De dónde salen los requisitos: las tablas de la sección 3 de docs/arquitectura.md del repositorio de documentos (MATU),
una fila por requisito con la forma «| RF-NN | texto | `módulo` | Debe |». La arquitectura dice que son los 26
comprometidos; el script lo verifica y falla si encuentra otra cantidad sin --esperados, para que una tabla mal leída no
pase en silencio. La ruta se da con --arquitectura o con la variable MATU_ARQUITECTURA. En el CI el repositorio de
documentos se descarga junto al de código (.github/workflows/ci.yml, paso «Documentos de MATU»).

De dónde salen las pruebas: pytest recoge la carpeta tests/ sin correr nada (--collect-only) y se leen las marcas rf de
cada prueba, también las de pytestmark del módulo o de la clase. Se corre desde backend/.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
FILA_RF = re.compile(r"^\|\s*(RF-\d{2})\s*\|.*\|\s*(Debe|Debería|Podría)\s*\|\s*$")
ESPERADOS = 26


def requisitos_debe(arquitectura: Path) -> list[str]:
    """Los RF con prioridad Debe de las tablas de requisitos, en orden y sin repetir."""
    vistos: dict[str, str] = {}
    for linea in arquitectura.read_text(encoding="utf-8").splitlines():
        coincidencia = FILA_RF.match(linea.strip())
        if coincidencia:
            rf, prioridad = coincidencia.groups()
            anterior = vistos.setdefault(rf, prioridad)
            if anterior != prioridad:
                raise SystemExit(f"{rf} aparece como {anterior} y como {prioridad} en {arquitectura.name}")
    return sorted(rf for rf, prioridad in vistos.items() if prioridad == "Debe")


class _Recolector:
    """Plugin de pytest que junta, por requisito, los nodos que lo marcan."""

    def __init__(self) -> None:
        self.por_rf: dict[str, list[str]] = defaultdict(list)

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        for item in items:
            for marca in item.iter_markers(name="rf"):
                for requisito in marca.args:
                    self.por_rf[str(requisito)].append(item.nodeid)


def pruebas_por_requisito(carpeta: Path) -> dict[str, list[str]]:
    recolector = _Recolector()
    codigo = pytest.main(["--collect-only", "-qq", "-p", "no:cacheprovider", str(carpeta)], plugins=[recolector])
    # 5 es «no se recogió ninguna prueba»; cualquier otro distinto de 0 es un error de recolección
    if codigo not in (0, 5):
        raise SystemExit(f"pytest no pudo recoger las pruebas (código {int(codigo)})")
    return dict(recolector.por_rf)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--arquitectura",
        type=Path,
        default=os.environ.get("MATU_ARQUITECTURA"),
        help="docs/arquitectura.md del repositorio de documentos (o MATU_ARQUITECTURA)",
    )
    parser.add_argument(
        "--esperados",
        type=int,
        default=ESPERADOS,
        help=f"cuántos requisitos Debe se esperan (por omisión {ESPERADOS}, arquitectura 3.5)",
    )
    parser.add_argument("--pruebas", type=Path, default=RAIZ_BACKEND / "tests")
    args = parser.parse_args(argv)

    if args.arquitectura is None or not Path(args.arquitectura).is_file():
        print("Falta docs/arquitectura.md: usa --arquitectura <ruta> o MATU_ARQUITECTURA", file=sys.stderr)
        return 2
    debe = requisitos_debe(Path(args.arquitectura))
    if len(debe) != args.esperados:
        print(
            f"Se leyeron {len(debe)} requisitos Debe y se esperaban {args.esperados}: {', '.join(debe)}",
            file=sys.stderr,
        )
        return 2

    por_rf = pruebas_por_requisito(args.pruebas)
    sin_prueba = [rf for rf in debe if not por_rf.get(rf)]

    print(f"\nTrazabilidad: {len(debe)} requisitos Debe, {len(debe) - len(sin_prueba)} con al menos una prueba")
    for rf in debe:
        print(f"  {rf}: {len(por_rf.get(rf, []))} pruebas")
    if sin_prueba:
        print(f"Requisitos Debe sin ninguna prueba marcada: {', '.join(sin_prueba)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
