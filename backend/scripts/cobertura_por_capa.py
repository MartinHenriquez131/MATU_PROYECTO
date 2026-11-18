"""Cobertura de líneas por capa, con su piso (MATU-79, estrategia de pruebas, secciones 1 y 8).

La estrategia no pide una meta global: pide 85% de líneas en el dominio (app/modules/*/domain y app/shared) y 70% en
los casos de uso (app/modules/*/application), y ninguna meta en infrastructure/. --cov-fail-under de pytest-cov solo
mide el total, así que este script lee el JSON de coverage.py y revisa cada capa por separado.

    pytest --cov=app --cov-report=json:cobertura.json
    python scripts/cobertura_por_capa.py cobertura.json

Sale con 1 si alguna capa queda bajo su piso. Los pisos viven en PISOS: subirlos hasta la meta es el trabajo pendiente
que deja anotado MATU-79, y bajarlos exige una decisión escrita.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Meta de la estrategia de pruebas y piso que hoy hace cumplir el CI, en porcentaje de líneas
METAS = {"dominio": 85.0, "aplicacion": 70.0}
PISOS = {"dominio": 85.0, "aplicacion": 70.0}

CAPAS = {
    "dominio": re.compile(r"^app/(modules/[^/]+/domain|shared)/"),
    "aplicacion": re.compile(r"^app/modules/[^/]+/application/"),
}
MODULO = re.compile(r"^app/(?:modules/)?([^/]+)/")


@dataclass
class Suma:
    cubiertas: int = 0
    total: int = 0

    @property
    def porcentaje(self) -> float:
        return 100.0 if self.total == 0 else 100.0 * self.cubiertas / self.total


def ruta_del_paquete(ruta: str) -> str:
    """La ruta desde app/, con barras normales. Corta en la última aparición de /app/, no en la primera de «app/»: en
    /home/runner/work/myapp/backend/app/... la primera estaría dentro de «myapp/» (hallazgo H1 de la QA)."""
    ruta = ruta.replace("\\", "/")
    if ruta.startswith("app/"):
        return ruta
    corte = ruta.rfind("/app/")
    return ruta[corte + 1 :] if corte >= 0 else ruta


def medir(informe: dict[str, Any]) -> tuple[dict[str, Suma], dict[str, dict[str, Suma]], Suma]:
    """Las líneas cubiertas y totales por capa, por capa y módulo, y del paquete app completo."""
    por_capa = {capa: Suma() for capa in CAPAS}
    por_modulo: dict[str, dict[str, Suma]] = {capa: {} for capa in CAPAS}
    total = Suma()
    for ruta, datos in informe["files"].items():
        ruta = ruta_del_paquete(ruta)
        resumen = datos["summary"]
        cubiertas, lineas = resumen["covered_lines"], resumen["num_statements"]
        total.cubiertas += cubiertas
        total.total += lineas
        for capa, patron in CAPAS.items():
            if patron.match(ruta):
                por_capa[capa].cubiertas += cubiertas
                por_capa[capa].total += lineas
                coincidencia = MODULO.match(ruta)
                modulo = coincidencia.group(1) if coincidencia else ruta
                suma = por_modulo[capa].setdefault(modulo, Suma())
                suma.cubiertas += cubiertas
                suma.total += lineas
    return por_capa, por_modulo, total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("informe", type=Path, help="el JSON de coverage.py (--cov-report=json:<archivo>)")
    args = parser.parse_args(argv)

    por_capa, por_modulo, total = medir(json.loads(args.informe.read_text(encoding="utf-8")))
    bajo_el_piso = []
    sin_lineas = [capa for capa, suma in por_capa.items() if suma.total == 0]
    for capa, suma in por_capa.items():
        print(
            f"{capa}: {suma.porcentaje:.1f}% ({suma.cubiertas} de {suma.total} líneas)"
            f" · piso {PISOS[capa]:.0f}% · meta {METAS[capa]:.0f}%"
        )
        for modulo, sub in sorted(por_modulo[capa].items(), key=lambda par: par[1].porcentaje):
            print(f"    {modulo}: {sub.porcentaje:.1f}% ({sub.cubiertas} de {sub.total})")
        if suma.porcentaje < PISOS[capa]:
            bajo_el_piso.append(capa)
    print(f"total app/ (sin meta): {total.porcentaje:.1f}% ({total.cubiertas} de {total.total} líneas)")
    if sin_lineas:
        # Hallazgo H1 de la QA: una capa sin líneas medidas no es un 100%. Es un informe que no midió lo que debía
        # (otra carpeta, otro --cov, rutas que no calzan) y la puerta no puede pasar con él
        print(
            f"Ninguna línea medida en: {', '.join(sin_lineas)}. Revisa --cov=app y las rutas del informe",
            file=sys.stderr,
        )
        return 2
    if bajo_el_piso:
        print(f"Cobertura bajo el piso en: {', '.join(bajo_el_piso)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
