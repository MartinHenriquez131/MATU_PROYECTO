"""MATU-79 · Los scripts de las puertas del CI: el contrato (exportar_contrato.py) y la trazabilidad (trazabilidad.py).

Se prueban sus reglas con entradas sintéticas: cómo se leen los requisitos Debe de una tabla y cuándo dos contratos
difieren. La corrida completa de cada uno es un paso del pipeline (.github/workflows/ci.yml).
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _cargar(nombre: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / f"{nombre}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


trazabilidad = _cargar("trazabilidad")
exportar_contrato = _cargar("exportar_contrato")

TABLA = """\
### 3.1 Algo

| ID | Requisito | Módulo | Prioridad |
|---|---|---|---|
| RF-01 | Uno, con una | barra dentro del texto | `care_circle` | Debe |
| RF-16 | Dieciséis | `replenishment` | Debería |
| RF-02 | Dos | `care_plan` | Debe |

Texto que menciona RF-03 sin ser fila.

| RF-33 | Treinta y tres | `rx` | Podría |
| RF-33 | Treinta y tres, repetida en otra tabla | `rx` | Podría |
"""


def test_lee_solo_las_filas_debe_en_orden(tmp_path: Path) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA, encoding="utf-8")
    assert trazabilidad.requisitos_debe(archivo) == ["RF-01", "RF-02"]


def test_un_requisito_con_dos_prioridades_detiene_la_puerta(tmp_path: Path) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA + "| RF-02 | Dos | `care_plan` | Podría |\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="RF-02"):
        trazabilidad.requisitos_debe(archivo)


def test_otra_cantidad_de_requisitos_detiene_la_puerta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA, encoding="utf-8")
    assert trazabilidad.main(["--arquitectura", str(archivo)]) == 2
    assert "Se leyeron 2 requisitos Debe y se esperaban 26" in capsys.readouterr().err


def test_sin_arquitectura_la_puerta_no_pasa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MATU_ARQUITECTURA", raising=False)
    assert trazabilidad.main(["--arquitectura", str(tmp_path / "no-existe.md")]) == 2


def test_un_requisito_sin_prueba_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA, encoding="utf-8")
    pruebas = tmp_path / "pruebas"
    pruebas.mkdir()
    (pruebas / "test_sintetico.py").write_text(
        'import pytest\n\n\n@pytest.mark.rf("RF-01")\ndef test_uno() -> None:\n    pass\n', encoding="utf-8"
    )
    codigo = trazabilidad.main(["--arquitectura", str(archivo), "--esperados", "2", "--pruebas", str(pruebas)])
    salida = capsys.readouterr()
    assert codigo == 1
    assert "RF-01: 1 pruebas" in salida.out
    assert "sin ninguna prueba marcada: RF-02" in salida.err


def test_contratos_iguales_no_tienen_diferencias() -> None:
    contrato: dict[str, Any] = {"paths": {"/v1/salud": {"get": {"responses": {"200": {}}}}}}
    assert exportar_contrato.diferencias(contrato, {"paths": {"/v1/salud": {"get": {"responses": {"200": {}}}}}}) == []


def test_el_orden_de_las_claves_no_es_una_diferencia() -> None:
    assert exportar_contrato.diferencias({"a": 1, "b": 2}, {"b": 2, "a": 1}) == []


def test_lista_las_diferencias_por_ruta() -> None:
    versionado: dict[str, Any] = {"paths": {"/v1/salud": {"get": {"responses": {"200": {}}}}, "/v1/vieja": {}}}
    api: dict[str, Any] = {"paths": {"/v1/salud": {"get": {"responses": {"200": {}, "503": {}}}}, "/v1/nueva": {}}}
    assert exportar_contrato.diferencias(versionado, api) == [
        "solo en la API: /paths//v1/nueva",
        "solo en la API: /paths//v1/salud/get/responses/503",
        "solo en openapi.json: /paths//v1/vieja",
    ]


def test_serializa_como_el_archivo_versionado() -> None:
    texto = exportar_contrato.serializar({"info": {"title": "Configuración"}})
    assert texto == '{\n  "info": {\n    "title": "Configuración"\n  }\n}\n'
