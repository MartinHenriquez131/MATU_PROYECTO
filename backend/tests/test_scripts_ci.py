"""MATU-79 · Los scripts de las puertas del CI: contrato, trazabilidad y cobertura por capa.

Se prueban sus reglas con entradas sintéticas: cómo se leen los requisitos Debe de una tabla y cuándo dos contratos
difieren. La corrida completa de cada uno es un paso del pipeline (.github/workflows/ci.yml).
"""

import importlib.util
import json
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
cobertura_por_capa = _cargar("cobertura_por_capa")

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


def test_una_prioridad_con_nota_se_lee(tmp_path: Path) -> None:
    # Como quedó RF-32 en el recorte de MATU-123
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(
        TABLA
        + "| RF-32 | Treinta y dos | `backoffice` | Debería (recorte de MATU-123: solo las incidencias, RF-40) |\n"
        + "| RF-05 | Cinco | `care_plan` | Debe (nota) |\n",
        encoding="utf-8",
    )
    assert trazabilidad.requisitos_debe(archivo) == ["RF-01", "RF-02", "RF-05"]
    assert {"RF-32", "RF-16"} <= trazabilidad.identificadores(archivo)


def test_un_requisito_con_dos_prioridades_detiene_la_puerta(tmp_path: Path) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA + "| RF-02 | Dos | `care_plan` | Podría |\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="RF-02"):
        trazabilidad.requisitos_debe(archivo)


def test_menos_requisitos_que_el_minimo_detiene_la_puerta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA, encoding="utf-8")
    assert trazabilidad.main(["--arquitectura", str(archivo)]) == 2
    salida = capsys.readouterr()
    assert "Se leyeron 2 requisitos Debe de arquitectura.md (mínimo 25)" in salida.out
    assert "Se leyeron 2 requisitos Debe y se esperaban al menos 25" in salida.err


def test_un_minimo_de_cero_no_se_acepta(tmp_path: Path) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text("sin tablas\n", encoding="utf-8")
    assert trazabilidad.main(["--arquitectura", str(archivo), "--minimo", "0"]) == 2


def test_sin_arquitectura_la_puerta_no_pasa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MATU_ARQUITECTURA", raising=False)
    assert trazabilidad.main(["--arquitectura", str(tmp_path / "no-existe.md")]) == 2


def _correr(
    tmp_path: Path, nombre: str, marcas: list[str], *extra: str, tabla: str = TABLA, rnf_opcional: bool = True
) -> int:
    """La puerta sobre una tabla sintética, con una carpeta de pruebas que marca los requisitos dados (uno por prueba).

    Por omisión, la TABLA sin RNF y --rnf-opcional, para las pruebas de los RF."""
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(tabla, encoding="utf-8")
    pruebas = tmp_path / "pruebas"
    pruebas.mkdir()
    cuerpo = "import pytest\n"
    for i, rf in enumerate(marcas):
        cuerpo += f'\n\n@pytest.mark.rf("{rf}")\ndef test_{i}() -> None:\n    pass\n'
    # Un nombre de módulo distinto en cada prueba: pytest.main corre varias veces en el mismo proceso
    (pruebas / f"test_{nombre}.py").write_text(cuerpo, encoding="utf-8")
    args = ["--arquitectura", str(archivo), "--minimo", "2", "--pruebas", str(pruebas), *extra]
    if rnf_opcional:
        args.append("--rnf-opcional")
    resultado: int = trazabilidad.main(args)
    return resultado


def test_un_requisito_sin_prueba_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _correr(tmp_path, "sin_prueba", ["RF-01"]) == 1
    salida = capsys.readouterr()
    assert "RF-01: 1 pruebas" in salida.out
    assert "sin ninguna prueba marcada: RF-02" in salida.err


def test_un_pendiente_sin_prueba_se_acepta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _correr(tmp_path, "pendiente", ["RF-01"], "--pendientes", "RF-02") == 0
    assert "RF-02: 0 pruebas (pendiente)" in capsys.readouterr().out


def test_un_pendiente_que_ya_tiene_prueba_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _correr(tmp_path, "pendiente_con_prueba", ["RF-01", "RF-02"], "--pendientes", "RF-02") == 1
    assert "Ya tienen prueba y siguen en --pendientes: RF-02" in capsys.readouterr().err


def test_un_pendiente_que_no_existe_detiene_la_puerta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # RF-16 es Debería en la TABLA y RF-99 no existe: solo RF-99 detiene la puerta
    assert _correr(tmp_path, "pendiente_desconocido", ["RF-01", "RF-02"], "--pendientes", "RF-16,RF-99") == 2
    assert "Pendientes que no existen en arquitectura.md: RF-99" in capsys.readouterr().err


def test_un_rf_deberia_en_pendientes_avisa_y_no_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # MATU-123: RF-32 baja a Debería con el recorte y sigue en --pendientes hasta que se saque del workflow
    assert _correr(tmp_path, "pendiente_deberia", ["RF-01", "RF-02"], "--pendientes", "RF-16") == 0
    salida = capsys.readouterr().out
    assert "Aviso: RF-16 ya no se exige" in salida
    assert "sácalo de --pendientes" in salida
    assert "RF-16:" not in salida


def test_un_rf_deberia_con_prueba_en_pendientes_solo_avisa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Ya no se exige: que tenga prueba no lo vuelve un «pendiente con prueba»
    assert _correr(tmp_path, "deberia_con_prueba", ["RF-01", "RF-02", "RF-16"], "--pendientes", "RF-16") == 0
    assert "Aviso: RF-16 ya no se exige" in capsys.readouterr().out


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


def _archivo(cubiertas: int, total: int) -> dict[str, Any]:
    return {"summary": {"covered_lines": cubiertas, "num_statements": total}}


INFORME: dict[str, Any] = {
    "files": {
        r"app\modules\consumption\domain\quiebre.py": _archivo(9, 10),
        "app/shared/eventos.py": _archivo(8, 10),
        "app/modules/ordering/application/casos.py": _archivo(7, 10),
        "app/modules/ordering/infrastructure/repositorio.py": _archivo(0, 10),
        "app/core/db.py": _archivo(10, 10),
    }
}


def test_la_cobertura_se_mide_por_capa_y_sin_infraestructura() -> None:
    por_capa, por_modulo, total = cobertura_por_capa.medir(INFORME)
    assert (por_capa["dominio"].cubiertas, por_capa["dominio"].total) == (17, 20)
    assert (por_capa["aplicacion"].cubiertas, por_capa["aplicacion"].total) == (7, 10)
    assert set(por_modulo["dominio"]) == {"consumption", "shared"}
    assert (total.cubiertas, total.total) == (34, 50)


def test_una_capa_bajo_su_piso_falla(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archivo = tmp_path / "cobertura.json"
    archivo.write_text(json.dumps(INFORME), encoding="utf-8")
    monkeypatch.setattr(cobertura_por_capa, "PISOS", {"dominio": 85.0, "aplicacion": 70.0})
    assert cobertura_por_capa.main([str(archivo)]) == 0
    monkeypatch.setattr(cobertura_por_capa, "PISOS", {"dominio": 86.0, "aplicacion": 70.0})
    assert cobertura_por_capa.main([str(archivo)]) == 1
    assert "bajo el piso en: dominio" in capsys.readouterr().err


def test_h1_una_capa_sin_lineas_medidas_no_pasa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Hallazgo H1 de la QA: sin líneas de casos de uso, antes contaba 100% y pasaba
    informe = {"files": {"app/modules/consumption/domain/quiebre.py": _archivo(10, 10)}}
    archivo = tmp_path / "cobertura.json"
    archivo.write_text(json.dumps(informe), encoding="utf-8")
    assert cobertura_por_capa.main([str(archivo)]) == 2
    assert "Ninguna línea medida en: aplicacion" in capsys.readouterr().err


def test_h1_un_informe_vacio_no_pasa(tmp_path: Path) -> None:
    archivo = tmp_path / "cobertura.json"
    archivo.write_text(json.dumps({"files": {}}), encoding="utf-8")
    assert cobertura_por_capa.main([str(archivo)]) == 2


@pytest.mark.parametrize(
    ("ruta", "esperada"),
    [
        (
            "/home/runner/work/myapp/backend/app/modules/ordering/domain/pedido.py",
            "app/modules/ordering/domain/pedido.py",
        ),
        (r"C:\trabajo\miapp\backend\app\shared\eventos.py", "app/shared/eventos.py"),
        ("app/modules/catalog/application/catalogo.py", "app/modules/catalog/application/catalogo.py"),
    ],
)
def test_h1_la_ruta_se_corta_en_la_ultima_carpeta_app(ruta: str, esperada: str) -> None:
    assert cobertura_por_capa.ruta_del_paquete(ruta) == esperada


def test_h1_una_ruta_absoluta_con_myapp_cuenta_en_su_capa() -> None:
    informe = {
        "files": {
            "/home/runner/work/myapp/backend/app/modules/ordering/domain/pedido.py": _archivo(9, 10),
            "/home/runner/work/myapp/backend/app/modules/ordering/application/casos.py": _archivo(7, 10),
        }
    }
    por_capa, _, _ = cobertura_por_capa.medir(informe)
    assert (por_capa["dominio"].cubiertas, por_capa["dominio"].total) == (9, 10)
    assert (por_capa["aplicacion"].cubiertas, por_capa["aplicacion"].total) == (7, 10)


TABLA_RNF = """### 2.2 Atributos de calidad priorizados

| ID | Prioridad | Atributo | Escenario medible | Cómo se verifica | Obligación | Verificación |
|---|---|---|---|---|---|---|
| RNF-01 | 1 | **Uno** | Con una | barra en el escenario | Prueba de reintento | Debe | automática |
| RNF-02 | 2 | **Dos** | Escenario | Prueba de aislamiento | Debe | automática |
| RNF-03 | 3 | **Tres** | Escenario | Prueba con usuarios | Debe | manual |
| RNF-04 | 4 | **Cuatro** | Escenario | Prueba automática | Debería | automática |
"""


def test_lee_los_rnf_debe_automaticos(tmp_path: Path) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA_RNF, encoding="utf-8")
    assert trazabilidad.rnf_de_la_tabla(archivo) == (4, ["RNF-01", "RNF-02"])


def test_una_fila_rnf_sin_obligacion_ni_verificacion_detiene_la_puerta(tmp_path: Path) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text("| RNF-01 | 1 | **Uno** | Escenario | Prueba |\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="RNF-01 no tiene las columnas"):
        trazabilidad.rnf_de_la_tabla(archivo)


def test_un_rnf_automatico_sin_prueba_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    codigo = _correr(
        tmp_path, "rnf_sin_prueba", ["RF-01", "RF-02", "RNF-01"], "--minimo-rnf", "2", tabla=TABLA + TABLA_RNF
    )
    salida = capsys.readouterr()
    assert codigo == 1
    assert "RNF-01: 1 pruebas" in salida.out
    # RNF-03 es manual y RNF-04 es Debería: no se exigen
    assert "RNF-03" not in salida.out and "RNF-04" not in salida.out
    assert "sin ninguna prueba marcada: RNF-02" in salida.err


def test_un_rnf_pendiente_se_acepta_y_falla_si_ya_tiene_prueba(tmp_path: Path) -> None:
    tabla = TABLA + TABLA_RNF
    marcas = ["RF-01", "RF-02", "RNF-01"]
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    assert _correr(tmp_path / "a", "rnf_pend", marcas, "--minimo-rnf", "2", "--pendientes", "RNF-02", tabla=tabla) == 0
    con_prueba = [*marcas, "RNF-02"]
    args = ("--minimo-rnf", "2", "--pendientes", "RNF-02")
    assert _correr(tmp_path / "b", "rnf_pend_con", con_prueba, *args, tabla=tabla) == 1


def test_un_rnf_manual_en_pendientes_avisa_y_no_falla(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    marcas = ["RF-01", "RF-02", "RNF-01", "RNF-02"]
    args = ("--minimo-rnf", "2", "--pendientes", "RNF-03")
    codigo = _correr(tmp_path, "rnf_manual", marcas, *args, tabla=TABLA + TABLA_RNF)
    assert codigo == 0
    assert "Aviso: RNF-03 ya no se exige" in capsys.readouterr().out


def test_un_rnf_inexistente_en_pendientes_detiene_la_puerta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    marcas = ["RF-01", "RF-02", "RNF-01", "RNF-02"]
    args = ("--minimo-rnf", "2", "--pendientes", "RNF-99")
    assert _correr(tmp_path, "rnf_inexistente", marcas, *args, tabla=TABLA + TABLA_RNF) == 2
    assert "Pendientes que no existen en arquitectura.md: RNF-99" in capsys.readouterr().err


def test_sin_tabla_rnf_y_sin_rnf_opcional_no_pasa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _correr(tmp_path, "sin_tabla", ["RF-01", "RF-02"], rnf_opcional=False) == 2
    assert "Se leyeron 0 RNF Debe automáticos y se esperaban al menos 6: ninguno" in capsys.readouterr().err


def test_sin_tabla_rnf_con_rnf_opcional_avisa_y_pasa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _correr(tmp_path, "opcional", ["RF-01", "RF-02"]) == 0
    assert "no tiene la tabla de RNF con ID" in capsys.readouterr().out


def test_con_rnf_opcional_una_tabla_rnf_se_exige_entera(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Encontró RNF: --rnf-opcional ya no excusa nada, y 2 automáticos no llegan al mínimo de 6
    assert _correr(tmp_path, "opcional_con_tabla", ["RF-01", "RF-02"], tabla=TABLA + TABLA_RNF) == 2
    assert "Se leyeron 2 RNF Debe automáticos y se esperaban al menos 6" in capsys.readouterr().err


def test_un_minimo_rnf_de_cero_no_se_acepta(tmp_path: Path) -> None:
    archivo = tmp_path / "arquitectura.md"
    archivo.write_text(TABLA, encoding="utf-8")
    assert trazabilidad.main(["--arquitectura", str(archivo), "--minimo", "2", "--minimo-rnf", "0"]) == 2
