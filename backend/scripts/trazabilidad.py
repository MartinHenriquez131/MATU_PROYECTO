"""Trazabilidad de los requisitos Debe contra las pruebas (MATU-79, estrategia de pruebas, sección 14).

Lista los requisitos comprometidos como *Debe* que no tienen ninguna prueba marcada con @pytest.mark.rf("RF-NN") o
@pytest.mark.rf("RNF-NN"), y sale con 1 si hay alguno: «un requisito comprometido sin prueba no está terminado».

    python scripts/trazabilidad.py --arquitectura ../../MATU/docs/arquitectura.md --pendientes RF-32,RF-40

Funcionales (RF): las tablas de la sección 3 de docs/arquitectura.md del repositorio de documentos (MATU), una fila por
requisito con la forma «| RF-NN | texto | `módulo` | Debe |», con o sin una nota después de la prioridad. Desde el
recorte de MATU-123 son 25 comprometidos: el script exige al menos --minimo (25 por omisión) y dice cuántos encontró.

No funcionales (RNF): la tabla 2.2, con la forma «| RNF-NN | prioridad | atributo | escenario | cómo se verifica |
Debe | automática |».
Solo los *Debe* con verificación *automática* necesitan una prueba; los *manuales* se verifican con personas, con la
carga de k6 o con una revisión. El script exige al menos --minimo-rnf (6 por omisión). Una fila RNF sin las columnas
«Obligación» y «Verificación» detiene la puerta, para que una tabla mal leída no pase en silencio. --rnf-opcional sirve
mientras la arquitectura publicada no tenga la tabla con ID: si no encuentra ninguna fila RNF, lo avisa y revisa solo
los RF; si encuentra alguna, exige todo.

Si la arquitectura agrega requisitos, la puerta los revisa sin cambiar nada; si una tabla se lee mal y salen menos que
el mínimo, sale con 2 y no pasa. La ruta se da con --arquitectura o con la variable MATU_ARQUITECTURA. En el CI el
repositorio de documentos se descarga junto al de código (.github/workflows/ci.yml, paso «Documentos de MATU»).

--pendientes es la lista explícita de los RF o RNF que todavía no tienen prueba y se aceptan por ahora (la fija el
workflow, con el motivo). La puerta falla también si un pendiente ya tiene prueba, para que nadie se olvide de sacarlo
de la lista, y sale con 2 si un pendiente no existe en ninguna tabla, para que un error de tipeo no tape nada. Un
pendiente que existe pero ya no se exige (un RF Debería o Podría, o un RNF manual, por ejemplo tras un recorte) solo
se avisa en el log: hay que sacarlo de la lista, pero la puerta no depende del orden en que se fusionen los PR.

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
# La celda de la prioridad puede traer una nota después de la palabra, como «Debería (recorte de MATU-123: …)»
FILA_RF = re.compile(r"^\|\s*(RF-\d{2})\s*\|.*\|\s*(Debe|Debería|Podría)\b[^|]*\|\s*$")
INICIO_RNF = re.compile(r"^\|\s*(RNF-\d{2})\s*\|")
FILA_RNF = re.compile(r"^\|\s*(RNF-\d{2})\s*\|.*\|\s*(Debe|Debería|Podría)\b[^|]*\|\s*(automática|manual)\b[^|]*\|\s*$")
# 25 desde el recorte de MATU-123 (RF-32 a Debería, MATU#116). La arquitectura de main todavía tiene 26, y 26 >= 25:
# la puerta pasa con las dos, en cualquier orden de fusión
MINIMO = 25
MINIMO_RNF = 6


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


def identificadores(arquitectura: Path) -> set[str]:
    """Todos los RF y RNF de las tablas, con cualquier prioridad, obligación o verificación."""
    ids: set[str] = set()
    for linea in arquitectura.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        for patron in (FILA_RF, INICIO_RNF):
            coincidencia = patron.match(linea)
            if coincidencia:
                ids.add(coincidencia.group(1))
    return ids


def rnf_de_la_tabla(arquitectura: Path) -> tuple[int, list[str]]:
    """Cuántas filas RNF tiene la tabla 2.2, y cuáles son Debe con verificación automática, en orden."""
    vistos: dict[str, tuple[str, str]] = {}
    for linea in arquitectura.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        inicio = INICIO_RNF.match(linea)
        if inicio is None:
            continue
        coincidencia = FILA_RNF.match(linea)
        if coincidencia is None:
            raise SystemExit(
                f"{inicio.group(1)} no tiene las columnas Obligación y Verificación en {arquitectura.name}"
            )
        rnf, obligacion, verificacion = coincidencia.groups()
        anterior = vistos.setdefault(rnf, (obligacion, verificacion))
        if anterior != (obligacion, verificacion):
            raise SystemExit(f"{rnf} aparece dos veces con otra obligación o verificación en {arquitectura.name}")
    automaticos = sorted(r for r, (o, v) in vistos.items() if o == "Debe" and v == "automática")
    return len(vistos), automaticos


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
        help=f"cuántos RF Debe se esperan como mínimo (por omisión {MINIMO}, arquitectura 3.5)",
    )
    parser.add_argument(
        "--minimo-rnf",
        type=int,
        default=MINIMO_RNF,
        help=f"cuántos RNF Debe automáticos se esperan como mínimo (por omisión {MINIMO_RNF}, arquitectura 2.2)",
    )
    parser.add_argument(
        "--rnf-opcional",
        action="store_true",
        help="si la arquitectura no tiene ninguna fila RNF, avisa y revisa solo los RF",
    )
    parser.add_argument(
        "--pendientes",
        default="",
        help="RF o RNF sin prueba que se aceptan por ahora, separados por coma (por ejemplo RF-32,RF-40)",
    )
    parser.add_argument("--pruebas", type=Path, default=RAIZ_BACKEND / "tests")
    args = parser.parse_args(argv)

    if args.arquitectura is None or not Path(args.arquitectura).is_file():
        print("Falta docs/arquitectura.md: usa --arquitectura <ruta> o MATU_ARQUITECTURA", file=sys.stderr)
        return 2
    if args.minimo < 1 or args.minimo_rnf < 1:
        print("--minimo y --minimo-rnf deben ser al menos 1: con 0 la puerta pasaría sin revisar nada", file=sys.stderr)
        return 2
    arquitectura = Path(args.arquitectura)
    debe = requisitos_debe(arquitectura)
    print(f"Se leyeron {len(debe)} requisitos Debe de {arquitectura.name} (mínimo {args.minimo})")
    if len(debe) < args.minimo:
        print(
            f"Se leyeron {len(debe)} requisitos Debe y se esperaban al menos {args.minimo}: {', '.join(debe)}",
            file=sys.stderr,
        )
        return 2

    filas_rnf, rnf = rnf_de_la_tabla(arquitectura)
    if filas_rnf == 0 and args.rnf_opcional:
        print(f"Aviso: {arquitectura.name} no tiene la tabla de RNF con ID; con --rnf-opcional se revisan solo los RF")
    else:
        print(f"Se leyeron {len(rnf)} RNF Debe automáticos de {filas_rnf} filas RNF (mínimo {args.minimo_rnf})")
        if len(rnf) < args.minimo_rnf:
            print(
                f"Se leyeron {len(rnf)} RNF Debe automáticos y se esperaban al menos {args.minimo_rnf}:"
                f" {', '.join(rnf) or 'ninguno'}",
                file=sys.stderr,
            )
            return 2
    exigidos = debe + rnf

    pendientes = sorted({r.strip() for r in args.pendientes.split(",") if r.strip()})
    existentes = identificadores(arquitectura)
    desconocidos = [r for r in pendientes if r not in existentes]
    if desconocidos:
        print(f"Pendientes que no existen en {arquitectura.name}: {', '.join(desconocidos)}", file=sys.stderr)
        return 2
    no_exigidos = [r for r in pendientes if r not in exigidos]
    if no_exigidos:
        # MATU-123: un recorte (RF-32 a Debería) deja el pendiente sin objeto. Se avisa y no se falla, para que no
        # importe en qué orden se fusionan el PR de documentos y el que saca el pendiente del workflow
        print(
            f"Aviso: {', '.join(no_exigidos)} ya no se exige (no es Debe, o es un RNF manual): sácalo de --pendientes"
        )
        pendientes = [r for r in pendientes if r in exigidos]

    por_rf = pruebas_por_requisito(args.pruebas)
    sin_prueba = [r for r in exigidos if not por_rf.get(r)]
    sin_prueba_no_aceptados = [r for r in sin_prueba if r not in pendientes]
    pendientes_con_prueba = [r for r in pendientes if por_rf.get(r)]

    print(
        f"\nTrazabilidad: {len(debe)} RF Debe y {len(rnf)} RNF Debe automáticos,"
        f" {len(exigidos) - len(sin_prueba)} de {len(exigidos)} con al menos una prueba"
    )
    for requisito in exigidos:
        marca = " (pendiente)" if requisito in pendientes else ""
        print(f"  {requisito}: {len(por_rf.get(requisito, []))} pruebas{marca}")
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
