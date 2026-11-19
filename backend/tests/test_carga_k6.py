"""MATU-80 · El script de k6 (infra/carga/pedido.js) mide y exige cada paso del flujo de RNF-05 (hallazgo H4 de Martín,
17-11). Pruebas estáticas sobre el texto del script y su instructivo: no corren k6, ni la API, ni la base."""

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.rf("RNF-05")]

CARGA = Path(__file__).resolve().parents[2] / "infra" / "carga"
SCRIPT = (CARGA / "pedido.js").read_text(encoding="utf-8")
README = (CARGA / "README.md").read_text(encoding="utf-8")

PASOS_RNF05 = ["catalogo", "pedido", "confirmar", "pagar", "retorno"]


def _lista(nombre: str) -> list[str]:
    encontrada = re.search(rf"const {nombre} = \[([^\]]*)\]", SCRIPT)
    assert encontrada is not None, f"falta {nombre} en pedido.js"
    return re.findall(r"['\"]([\w-]+)['\"]", encontrada.group(1))


def test_los_pasos_exigidos_son_el_flujo_de_rnf05() -> None:
    assert _lista("PASOS_RNF05") == PASOS_RNF05
    assert "const META_P95_MS = 800" in SCRIPT
    assert "umbrales[`http_req_duration{paso:${paso}}`] = [`p(95)<${META_P95_MS}`]" in SCRIPT


def test_toda_etiqueta_paso_del_script_tiene_su_umbral_y_su_fila_en_el_resumen() -> None:
    # Cualquier forma de la etiqueta: con otras en el mismo objeto, sin espacios, con comillas dobles o con guion bajo
    etiquetas = set(re.findall(r"\bpaso:\s*['\"]([\w-]+)['\"]", SCRIPT))
    assert etiquetas == {"entrar", *PASOS_RNF05}
    # PASOS es lo que recorren los umbrales y el resumen: ninguna etiqueta queda sin medir
    assert set(_lista("PASOS_RNF05")) | {"entrar"} == etiquetas
    assert "const PASOS = ['entrar', ...PASOS_RNF05]" in SCRIPT


LLAMADA_HTTP = re.compile(r"\bhttp\.(?:get|post|put|patch|del|request)\s*\(")
ETIQUETA_PASO = re.compile(r"\bpaso:\s*['\"][\w-]+['\"]")
# Las de setup() son la comprobación previa, antes de medir: no son pasos del flujo
COMPROBACION_PREVIA = {"`${BASE_URL}/v1/salud`", "`${BASE_URL}/v1/condiciones-pedido`"}


def _argumentos(desde: int) -> str:
    """El texto de la llamada desde su paréntesis de apertura hasta el que la cierra, sin contar los paréntesis que
    van dentro de cadenas."""
    profundidad, comilla, i = 0, "", desde
    while i < len(SCRIPT):
        c = SCRIPT[i]
        if comilla:
            if c == "\\":
                i += 1
            elif c == comilla:
                comilla = ""
        elif c in "'\"`":
            comilla = c
        elif c == "(":
            profundidad += 1
        elif c == ")":
            profundidad -= 1
            if profundidad == 0:
                return SCRIPT[desde : i + 1]
        i += 1
    raise AssertionError(f"llamada sin cerrar en la línea {SCRIPT.count(chr(10), 0, desde) + 1}")


def _rango_de_setup() -> range:
    inicio = SCRIPT.index("export function setup()")
    return range(inicio, SCRIPT.index("\n}\n", inicio))


def test_toda_peticion_del_flujo_lleva_su_paso() -> None:
    # Una petición sin `paso` solo cuenta en el total: ningún umbral por paso la vería
    setup = _rango_de_setup()
    sin_paso, previas = [], []
    for llamada in LLAMADA_HTTP.finditer(SCRIPT):
        argumentos = _argumentos(llamada.end() - 1)
        linea = SCRIPT.count("\n", 0, llamada.start()) + 1
        if llamada.start() in setup:
            previas.append(argumentos[1:].split(",")[0].strip().rstrip(")"))
        elif not ETIQUETA_PASO.search(argumentos):
            sin_paso.append(f"línea {linea}: {SCRIPT.splitlines()[linea - 1].strip()}")
    assert not sin_paso, "peticiones sin la etiqueta paso en pedido.js:\n" + "\n".join(sin_paso)
    # setup() no puede esconder un paso del flujo: solo la comprobación previa
    assert set(previas) == COMPROBACION_PREVIA


def test_entrar_se_mide_sin_exigirle_la_meta() -> None:
    assert "umbrales['http_req_duration{paso:entrar}'] = ['max>=0']" in SCRIPT
    assert "'no se exige'" in SCRIPT


def test_se_mantienen_el_umbral_total_y_los_de_funcionamiento() -> None:
    assert "http_req_duration: [`p(95)<${META_P95_MS}`]" in SCRIPT
    assert "checks: ['rate>0.99']" in SCRIPT
    assert "http_req_failed: ['rate<0.01']" in SCRIPT


def test_el_resumen_da_p50_p95_y_p99_por_paso_sin_datos_personales() -> None:
    assert "export function handleSummary(datos)" in SCRIPT
    assert "summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max']" in SCRIPT
    resumen = SCRIPT[SCRIPT.index("function resumenPorPaso") :]
    for estadistica in ("v.med", "v['p(95)']", "v['p(99)']"):
        assert estadistica in resumen
    # Solo métricas agregadas: ni la sesión, ni las credenciales, ni los cuerpos llegan al resumen
    for prohibido in ("sesion", "token", "CONTRASENA", "email", ".json(", "console.log"):
        assert prohibido not in resumen


def test_el_instructivo_explica_como_leer_y_donde_se_anota() -> None:
    assert "## Cómo leer el resultado" in README
    for paso in [*PASOS_RNF05, "entrar"]:
        assert f"| `{paso}` |" in README
    assert "Qué significa que falle uno" in README
    assert "`TESTER/`" in README
    assert "ajustar la meta de RNF-05 en la arquitectura" in README
