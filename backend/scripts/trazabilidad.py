"""Trazabilidad de los requisitos Debe contra las pruebas (MATU-79, estrategia de pruebas, sección 14).

Lista los requisitos comprometidos como *Debe* que no tienen ninguna prueba marcada con @pytest.mark.rf("RF-NN"), y
sale con 1 si hay alguno: «un requisito comprometido sin prueba no está terminado».

    python scripts/trazabilidad.py --arquitectura ../../MATU/docs/arquitectura.md --pendientes RF-32,RF-40

--pendientes es la lista explícita de los Debe que todavía no tienen prueba y se aceptan por ahora (la fija el workflow,
con el motivo). La puerta falla también si un pendiente ya tiene prueba, para que nadie se olvide de sacarlo de la
lista, y si un pendiente no es un requisito Debe, para que un error de tipeo no tape nada.

De dónde salen los requisitos: las tablas de la sección 3 de docs/arquitectura.md del repositorio de documentos (MATU),
una fila por requisito con la forma «| RF-NN | texto | `módulo` | Debe |». La arquitectura dice que son 26
comprometidos: el script exige al menos --minimo (26 por omisión) y dice cuántos encontró. Si la arquitectura agrega
requisitos, la puerta los revisa sin cambiar nada; si una tabla se lee mal y salen menos, sale con 2 y no pasa.
La ruta se da con --arquitectura o con la variable MATU_ARQUITECTURA. En el CI el repositorio de documentos se descarga
junto al de código (.github/workflows/ci.yml, paso «Documentos de MATU»).

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
MINIMO = 26


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
        "--minimo",
        type=int,
        default=MINIMO,
        help=f"cuántos requisitos Debe se esperan como mínimo (por omisión {MINIMO}, arquitectura 3.5)",
    )
    parser.add_argument(
        "--pendientes",
        default="",
        help="RF Debe sin prueba que se aceptan por ahora, separados por coma (por ejemplo RF-32,RF-40)",
    )
    parser.add_argument("--pruebas", type=Path, default=RAIZ_BACKEND / "tests")
    args = parser.parse_args(argv)

    if args.arquitectura is None or not Path(args.arquitectura).is_file():
        print("Falta docs/arquitectura.md: usa --arquitectura <ruta> o MATU_ARQUITECTURA", file=sys.stderr)
        return 2
    debe = requisitos_debe(Path(args.arquitectura))
    if args.minimo < 1:
        print("--minimo debe ser al menos 1: con 0 la puerta pasaría sin revisar nada", file=sys.stderr)
        return 2
    print(f"Se leyeron {len(debe)} requisitos Debe de {Path(args.arquitectura).name} (mínimo {args.minimo})")
    if len(debe) < args.minimo:
        print(
            f"Se leyeron {len(debe)} requisitos Debe y se esperaban al menos {args.minimo}: {', '.join(debe)}",
            file=sys.stderr,
        )
        return 2
    pendientes = sorted({rf.strip() for rf in args.pendientes.split(",") if rf.strip()})
    desconocidos = [rf for rf in pendientes if rf not in debe]
    if desconocidos:
        print(f"Pendientes que no son requisitos Debe: {', '.join(desconocidos)}", file=sys.stderr)
        return 2

    por_rf = pruebas_por_requisito(args.pruebas)
    sin_prueba = [rf for rf in debe if not por_rf.get(rf)]
    sin_prueba_no_aceptados = [rf for rf in sin_prueba if rf not in pendientes]
    pendientes_con_prueba = [rf for rf in pendientes if por_rf.get(rf)]

    print(f"\nTrazabilidad: {len(debe)} requisitos Debe, {len(debe) - len(sin_prueba)} con al menos una prueba")
    for rf in debe:
        marca = " (pendiente)" if rf in pendientes else ""
        print(f"  {rf}: {len(por_rf.get(rf, []))} pruebas{marca}")
    codigo = 0
    if sin_prueba_no_aceptados:
        print(f"Requisitos Debe sin ninguna prueba marcada: {', '.join(sin_prueba_no_aceptados)}", file=sys.stderr)
        codigo = 1
    if pendientes_con_prueba:
        print(
            f"Ya tienen prueba y siguen en --pendientes: {', '.join(pendientes_con_prueba)}. Sácalos de la lista",
            file=sys.stderr,
        )
        codigo = 1
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
