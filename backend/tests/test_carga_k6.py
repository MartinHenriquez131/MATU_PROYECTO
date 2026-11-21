"""MATU-80 · El script de k6 (infra/carga/pedido.js) mide y exige cada paso del flujo de RNF-05 (hallazgo H4 de Martín,
17-11) contra la meta que elige CARGA_META: la del piloto (10 usuarios, 0 % de fallos y la mediana de cada paso bajo
800 ms) o la de producción (50 usuarios y el p95 bajo 800 ms), según la arquitectura, sección 2.2 (hallazgo P3 de
Martín, 21-11). Pruebas estáticas sobre el texto del script y su instructivo: no corren k6, ni la API, ni la base."""

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


def _bloque_metas() -> str:
    inicio = SCRIPT.find("const METAS = {\n")
    assert inicio >= 0, "falta METAS en pedido.js"
    return SCRIPT[inicio : SCRIPT.index("\n}\n", inicio)]


def _meta(nombre: str) -> dict[str, str]:
    """Los campos de una meta de METAS en pedido.js, como texto: `usuarios: 10,` queda {"usuarios": "10"}."""
    encontrada = re.search(rf"^  {nombre}: \{{\n(.*?)\n  \}},?$", _bloque_metas(), re.DOTALL | re.MULTILINE)
    assert encontrada is not None, f"falta la meta {nombre} en METAS"
    return dict(re.findall(r"^    (\w+): (.+?),?$", encontrada.group(1), re.MULTILINE))


def test_hay_solo_dos_metas_y_la_de_omision_es_la_del_piloto() -> None:
    assert re.findall(r"^  (\w+): \{$", _bloque_metas(), re.MULTILINE) == ["piloto", "produccion"]
    assert "const CARGA_META = __ENV.CARGA_META || 'piloto'" in SCRIPT
    assert "const META = METAS[CARGA_META]" in SCRIPT


def test_una_meta_que_no_existe_no_deja_partir_la_carga() -> None:
    # Como BASE_URL: se revisa al cargar el script, antes de que k6 lea las opciones o envíe una petición
    guarda = re.search(
        r"if \(!Object\.prototype\.hasOwnProperty\.call\(METAS, CARGA_META\)\) \{\n\s+throw new Error\('CARGA_META",
        SCRIPT,
    )
    assert guarda is not None, "pedido.js no se niega a partir con una CARGA_META desconocida"
    assert guarda.start() < SCRIPT.index("const META = METAS[CARGA_META]")
    assert guarda.start() < SCRIPT.index("export const options")


def test_la_meta_del_piloto_es_la_mediana_de_cada_paso_sin_fallos_con_10_usuarios() -> None:
    piloto = _meta("piloto")
    assert piloto["usuarios"] == "10"
    assert piloto["porPaso"] == "'med<800'"
    assert piloto["fallidas"] == "'rate==0'"
    # El p95 se informa, no se exige: ni por paso ni en total
    assert piloto["total"] == "null"


def test_la_meta_de_produccion_es_el_p95_por_paso_y_en_total_con_50_usuarios() -> None:
    produccion = _meta("produccion")
    assert produccion["usuarios"] == "50"
    assert produccion["porPaso"] == "'p(95)<800'"
    assert produccion["total"] == "'p(95)<800'"
    assert produccion["fallidas"] == "'rate<0.01'"


def test_los_umbrales_salen_de_la_meta_activa() -> None:
    assert "umbrales[`http_req_duration{paso:${paso}}`] = [META.porPaso]" in SCRIPT
    assert "return META.total ? { http_req_duration: [META.total] } : {}" in SCRIPT
    assert "...umbralTotal()," in SCRIPT
    assert "http_req_failed: [META.fallidas]," in SCRIPT
    # Ningún umbral de tiempo ni de fallos escrito a mano fuera de METAS: ningún modo puede quedar exigiendo el otro
    opciones = SCRIPT[SCRIPT.index("function umbralesPorPaso") : SCRIPT.index("const JSON_CT")]
    for escrito_a_mano in ("p(95)<", "med<", "rate<0.01", "rate==0"):
        assert escrito_a_mano not in opciones


def test_los_usuarios_por_omision_son_los_de_la_meta_y_se_pueden_sobrescribir() -> None:
    assert "const USUARIOS = parseInt(__ENV.CARGA_USUARIOS || String(META.usuarios), 10)" in SCRIPT
    assert "vus: USUARIOS," in SCRIPT


def test_los_pasos_exigidos_son_el_flujo_de_rnf05() -> None:
    assert _lista("PASOS_RNF05") == PASOS_RNF05
    assert "for (const paso of PASOS_RNF05) umbrales[`http_req_duration{paso:${paso}}`]" in SCRIPT


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


def test_las_respuestas_esperadas_declaran_sus_codigos() -> None:
    # El 409 de C4 y el 401 del token vencido son parte del flujo: con `rate==0` en el piloto, sin su lista de códigos
    # esperados contarían en http_req_failed (observación O1 del QA, 21-11). Solo el éxito de hoy más ese código
    assert "const ESPERADAS_PEDIDO = http.expectedStatuses(201, 409)" in SCRIPT
    assert "const ESPERADAS_CATALOGO = http.expectedStatuses(200, 401)" in SCRIPT
    assert SCRIPT.count("http.expectedStatuses(") == 2
    # Cada lista va con la petición que maneja ese código, justo antes de su rama de recuperación
    for constante, rama in (
        ("ESPERADAS_PEDIDO", "if (r.status === 409) {"),
        ("ESPERADAS_CATALOGO", "if (catalogo.status === 401) {"),
    ):
        uso = SCRIPT.index(f"responseCallback: {constante},")
        assert uso < SCRIPT.index(rama) < uso + 120


def test_solo_esas_dos_peticiones_tienen_codigos_esperados_propios() -> None:
    # Ninguna otra petición se vuelve más tolerante: ni un responseCallback más, ni uno global para todo el script
    con_lista = []
    for llamada in LLAMADA_HTTP.finditer(SCRIPT):
        argumentos = _argumentos(llamada.end() - 1)
        lista = re.search(r"\bresponseCallback:\s*(\w+)", argumentos)
        if lista:
            paso = ETIQUETA_PASO.search(argumentos)
            assert paso is not None
            con_lista.append((paso.group(0), lista.group(1)))
    assert con_lista == [("paso: 'pedido'", "ESPERADAS_PEDIDO"), ("paso: 'catalogo'", "ESPERADAS_CATALOGO")]
    assert SCRIPT.count("responseCallback") == 2
    assert "setResponseCallback" not in SCRIPT
    # El segundo intento de crear el pedido, después de cancelar, ya no espera el 409
    segundo = SCRIPT.index("    r = http.post(ruta, cuerpo,")
    assert "responseCallback" not in _argumentos(SCRIPT.index("(", segundo))


def test_entrar_se_mide_sin_exigirle_la_meta() -> None:
    assert "umbrales['http_req_duration{paso:entrar}'] = ['max>=0']" in SCRIPT
    assert "'no se exige'" in SCRIPT


def test_se_mantiene_el_umbral_de_checks_en_las_dos_metas() -> None:
    assert "checks: ['rate>0.99']," in SCRIPT


def test_el_resumen_da_p50_p95_y_p99_por_paso_sin_datos_personales() -> None:
    assert "export function handleSummary(datos)" in SCRIPT
    assert "summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max']" in SCRIPT
    resumen = SCRIPT[SCRIPT.index("function resumenPorPaso") :]
    for estadistica in ("v.med", "v['p(95)']", "v['p(99)']"):
        assert estadistica in resumen
    # La tabla dice contra qué meta se mide cada fila y si la cumple: en el piloto el p95 se ve, pero no decide
    assert "const filas = [['paso', 'meta', 'med', 'p95', 'p99', 'estado']]" in resumen
    assert "META.metaPaso" in resumen
    assert "meta ${CARGA_META}: ${META.descripcion}" in resumen
    assert "(meta ${META.metaFallidas})" in resumen
    assert "? 'CUMPLE' : 'NO CUMPLE'" in SCRIPT
    assert _meta("piloto")["metaPaso"] == "'med < 800 ms'"
    assert _meta("produccion")["metaPaso"] == "'p95 < 800 ms'"
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


def test_el_instructivo_explica_las_dos_metas() -> None:
    assert "| `CARGA_META` | `pedido.js` |" in README
    assert "| `piloto` (por omisión) | 10 |" in README
    assert "| `produccion` | 50 |" in README
    for umbral in ("`med<800`", "`rate==0`", "`p(95)<800`"):
        assert umbral in README
    assert "CARGA_META=produccion k6 run infra/carga/pedido.js" in README
    assert "El 409 y el 401 esperados no cuentan como fallo" in README
