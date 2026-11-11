"""La capa 3 es desacoplable: la API arranca sin ella y las capas 1 y 2 siguen respondiendo (MATU-40).

Garantía ejecutable de la decisión 2 de cabecera y del ADR-002 (arquitectura, secciones 6.4 y 12.7):
se puede quitar el despacho completo y el sistema arranca. La capa 3 se quita de verdad: en un
intérprete aparte, sus paquetes (tests/capa3.py) no se pueden importar, como si sus carpetas no
existieran, y CAPA3_HABILITADA queda apagada.

Qué protege cada prueba:

1. Arranque: con la capa 3 bloqueada, app.main se importa, crea la API y no carga nada de la capa 3.
2. Contrato: el OpenAPI trae la ficha, el relevo, el consumo, las alertas y la lista, y ninguna ruta del despacho.
3. Respuestas: las rutas de las capas 1 y 2 llegan a su código (401, 422), no a un 404 de ruteo ni a un 500.
4. Interruptor: CAPA3_HABILITADA monta ROUTERS_CAPA_3, y apagado ni siquiera los importa.
5. Importaciones: nada de lo que app.main carga, siguiendo sus importaciones, llega a la capa 3.
   Complementa a test_arquitectura.py, que revisa cada importación suelta pero exime a main.py y a
   backoffice: aquí se sigue la cadena completa desde el punto de entrada.
6. Esquema: ninguna tabla fuera de la capa 3 tiene una llave foránea hacia ella (con base).
7. Flujos: los caminos felices de la ficha, el relevo, el consumo, las alertas y la lista pasan con la capa 3
   bloqueada (con base).
"""

import io
import json
import os
import re
import secrets
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import psycopg
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from tests.base_datos import DSN, requiere_base
from tests.capa3 import PAQUETES_CAPA_3, es_de_la_capa_3
from tests.test_arquitectura import ALCANZABLES, APP, _archivos_python, _importaciones, _leer, _nombre_modulo

BACKEND = APP.parent
CAPAS_1_Y_2 = ("iam", "care_circle", "care_plan", "consumption")
# El núcleo del despacho: lo que la decisión 2 de cabecera quita (sección 6.4, regla 3, más ordering y
# catalog por la decisión 104 de docs/api/README.md)
NUCLEO_DESPACHO = frozenset({"catalog", "ordering", "payments", "fulfillment", "settlement"})

PERSONA = str(uuid.UUID(int=1))

# Las rutas que deben estar: ficha (capa 1), relevo (capa 1), consumo, alertas y lista (capa 2)
RUTAS_CAPAS_1_Y_2 = (
    "/v1/personas-cuidadas/{persona_id}/plan/ficha",
    "/v1/personas-cuidadas/{persona_id}/plan/accesos-relevo",
    "/v1/relevo/presentacion",
    "/v1/relevo/canje",
    "/v1/relevo/ficha",
    "/v1/personas-cuidadas/{persona_id}/consumo",
    "/v1/personas-cuidadas/{persona_id}/consumo/por-acabarse",
    "/v1/personas-cuidadas/{persona_id}/consumo/alertas",
    "/v1/personas-cuidadas/{persona_id}/consumo/lista",
    # MATU-51: «Compré» y «Me quedan N» son capa 2 y no dependen del despacho (decisión C de Jorge)
    "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/reponer",
    "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/recontar",
    # MATU-72: borrar a la persona no depende del despacho; si existiera un pedido, se conserva (C12)
    "/v1/personas-cuidadas/{persona_id}/borrado",
    # MATU-61 (C6, C8): la dirección de la persona es de care_circle y existe sin la capa 3
    "/v1/personas-cuidadas/{persona_id}/direccion",
)

# Los prefijos del despacho en el contrato (arquitectura, sección 9.4)
PREFIJOS_CAPA_3 = (
    "/v1/catalogo",
    "/v1/pedidos",
    "/v1/cargos",
    "/v1/pagos",
    "/v1/comercio/",
    "/v1/backoffice/comercios",
    "/v1/backoffice/consumos",
    # MATU-61: el pedido de la persona, el pedido en curso y las condiciones del pedido
    "/v1/personas-cuidadas/{persona_id}/pedido",
    "/v1/condiciones-pedido",
)

# Cada petición se detiene antes de la base: sin sesión responde 401, y un cuerpo inválido, 422. Así
# llega al código de la ruta sin depender de PostgreSQL ni de Redis. /v1/pedidos es el contraste: sin
# la capa 3, ese 404 es de ruteo
# Un texto (y no un objeto) viaja tal cual como cuerpo JSON. La presentación cuenta el límite por IP
# antes de validar los campos y, sin Redis, falla cerrada con 503 (MATU-25, decisión 114). Un cuerpo
# que no es JSON válido responde 422 antes del límite, sin depender de Redis
CUERPO_NO_JSON = "{no es json"
PETICIONES: list[tuple[str, str, Any, int]] = [
    ("GET", "/v1/salud", None, 200),
    ("GET", f"/v1/personas-cuidadas/{PERSONA}/plan/ficha", None, 401),
    ("GET", f"/v1/personas-cuidadas/{PERSONA}/plan/accesos-relevo", None, 401),
    ("POST", "/v1/relevo/presentacion", CUERPO_NO_JSON, 422),
    ("GET", "/v1/relevo/ficha", None, 401),
    ("GET", f"/v1/personas-cuidadas/{PERSONA}/consumo", None, 401),
    ("GET", f"/v1/personas-cuidadas/{PERSONA}/consumo/por-acabarse", None, 401),
    ("GET", f"/v1/personas-cuidadas/{PERSONA}/consumo/alertas", None, 401),
    ("GET", f"/v1/personas-cuidadas/{PERSONA}/consumo/lista", None, 401),
    ("POST", f"/v1/personas-cuidadas/{PERSONA}/consumo/{PERSONA}/reponer", {"cantidad": 1}, 401),
    ("POST", f"/v1/personas-cuidadas/{PERSONA}/consumo/{PERSONA}/recontar", {"stock_unidades": 1}, 401),
    ("POST", f"/v1/personas-cuidadas/{PERSONA}/borrado", None, 401),
    # MATU-61: la dirección existe sin la capa 3; el pedido de la persona y las condiciones, no
    ("DELETE", f"/v1/personas-cuidadas/{PERSONA}/direccion", None, 401),
    ("POST", f"/v1/personas-cuidadas/{PERSONA}/pedidos", {}, 404),
    ("GET", "/v1/condiciones-pedido", None, 404),
    ("POST", "/v1/sesiones", {}, 422),
    ("POST", "/v1/pedidos", {}, 404),
    # MATU-59: el catálogo existe, pero es capa 3: sin ella, su ruta no está (404 de ruteo, no 401)
    ("GET", "/v1/catalogo", None, 404),
]

# Corre en un intérprete aparte: bloquea la capa 3, arranca la API y deja lo que vio en un archivo JSON
# (la salida estándar es de los logs)
ARRANQUE = """
import json, sys
from tests.capa3 import PAQUETES_CAPA_3, bloquear, es_de_la_capa_3
bloquear()
bloqueo = {}
for paquete in PAQUETES_CAPA_3:
    try:
        __import__(paquete)
        bloqueo[paquete] = "se importó"
    except ModuleNotFoundError:
        bloqueo[paquete] = "bloqueado"
import app.main
from fastapi.testclient import TestClient
peticiones = json.loads(sys.argv[2])
with TestClient(app.main.app, raise_server_exceptions=False) as cliente:
    respuestas = [
        (cliente.request(m, r, content=c, headers={"Content-Type": "application/json"}) if isinstance(c, str)
         else cliente.request(m, r, json=c)).status_code
        for m, r, c, _ in peticiones
    ]
    rutas = sorted(cliente.get("/openapi.json").json()["paths"])
with open(sys.argv[1], "w", encoding="utf-8") as salida:
    json.dump({
        "bloqueo": bloqueo,
        "rutas": rutas,
        "respuestas": respuestas,
        "cargados": sorted(n for n in sys.modules if es_de_la_capa_3(n)),
    }, salida)
"""


def _entorno_sin_capa3() -> dict[str, str]:
    entorno = {**os.environ, "ENTORNO": "pruebas", "CAPA3_HABILITADA": "false", "PYTHONIOENCODING": "utf-8"}
    entorno["PYTHONPATH"] = os.pathsep.join(filter(None, [str(BACKEND), os.environ.get("PYTHONPATH")]))
    return entorno


# Las llaves que las rutas piden antes de responder 401 o 422: sin ellas responden 500 (falla cerrada).
# El pipeline no las define y no tiene .env
LLAVES_DEL_ARRANQUE = ("JWT_CLAVE", "PEPPER_EMAIL", "PEPPER_LIMITES", "PEPPER_PIN")


def _entorno_del_arranque() -> dict[str, str]:
    """El entorno sin la capa 3, con las llaves que falten generadas al vuelo: sintéticas, distintas entre
    sí y de un solo uso. Nunca un literal en el código. Las que ya vienen (del .env local) se respetan."""
    entorno = _entorno_sin_capa3()
    for llave in LLAVES_DEL_ARRANQUE:
        if not entorno.get(llave):
            entorno[llave] = secrets.token_hex(32)
    # El relevo y la sesión arman la fábrica de sesiones antes de validar el cuerpo, y sin DATABASE_URL
    # responden 500. Ninguna de estas peticiones abre una conexión: basta una URL sin contraseña ni base
    if not entorno.get("DATABASE_URL"):
        entorno["DATABASE_URL"] = "postgresql+psycopg://matu_app@127.0.0.1:1/sin_base"
    return entorno


@pytest.fixture(scope="module")
def arranque(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    destino = tmp_path_factory.mktemp("capa3") / "arranque.json"
    proceso = subprocess.run(
        [sys.executable, "-c", ARRANQUE, str(destino), json.dumps(PETICIONES)],
        cwd=BACKEND,
        env=_entorno_del_arranque(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    # Si no arranca, el error de Python dice qué importación falló
    assert proceso.returncode == 0, f"La API no arranca sin la capa 3:\n{proceso.stderr[-3000:]}"
    resultado: dict[str, Any] = json.loads(destino.read_text(encoding="utf-8"))
    return resultado


# ---------------------------------------------------------------------------
# 1 a 3 · La API sin la capa 3
# ---------------------------------------------------------------------------


def test_la_capa_3_queda_bloqueada_de_verdad(arranque: dict[str, Any]) -> None:
    # Sin esto, las pruebas siguientes pasarían con la capa 3 presente
    assert arranque["bloqueo"] == {paquete: "bloqueado" for paquete in PAQUETES_CAPA_3}


def test_la_api_arranca_sin_cargar_la_capa_3(arranque: dict[str, Any]) -> None:
    assert arranque["cargados"] == []


def test_openapi_trae_las_capas_1_y_2(arranque: dict[str, Any]) -> None:
    faltan = [ruta for ruta in RUTAS_CAPAS_1_Y_2 if ruta not in arranque["rutas"]]

    assert faltan == [], f"Sin la capa 3 faltan rutas de las capas 1 y 2: {faltan}"


def test_openapi_sin_rutas_del_despacho(arranque: dict[str, Any]) -> None:
    del_despacho = [ruta for ruta in arranque["rutas"] if ruta.startswith(PREFIJOS_CAPA_3)]

    assert del_despacho == []


def test_las_rutas_de_las_capas_1_y_2_responden(arranque: dict[str, Any]) -> None:
    obtenidas = {f"{m} {r}": codigo for (m, r, _, _), codigo in zip(PETICIONES, arranque["respuestas"], strict=True)}
    esperadas = {f"{m} {r}": codigo for m, r, _, codigo in PETICIONES}

    assert obtenidas == esperadas


# ---------------------------------------------------------------------------
# 4 · El interruptor CAPA3_HABILITADA
# ---------------------------------------------------------------------------

ROUTER_FALSO = "app.modules.ordering.api.router_falso_matu40"


@pytest.fixture
def capa3(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Un router falso de la capa 3 en ROUTERS_CAPA_3, y la configuración leída de nuevo en cada prueba."""
    from app import main
    from app.core import config

    router = APIRouter()

    @router.get("/pedidos-de-prueba")
    def pedidos() -> dict[str, str]:
        return {"ok": "si"}

    modulo = ModuleType(ROUTER_FALSO)
    modulo.router = router  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, ROUTER_FALSO, modulo)
    monkeypatch.setattr(main, "ROUTERS_CAPA_3", (f"{ROUTER_FALSO}:router",))
    config.obtener_configuracion.cache_clear()
    yield monkeypatch
    config.obtener_configuracion.cache_clear()


def _crear_app() -> TestClient:
    from app.main import crear_app

    return TestClient(crear_app(stream_logs=io.StringIO()), raise_server_exceptions=False)


def test_capa_3_habilitada_monta_sus_routers(capa3: pytest.MonkeyPatch) -> None:
    capa3.setenv("CAPA3_HABILITADA", "true")

    assert _crear_app().get("/v1/pedidos-de-prueba").status_code == 200


def test_capa_3_apagada_no_monta_sus_routers(capa3: pytest.MonkeyPatch) -> None:
    capa3.setenv("CAPA3_HABILITADA", "false")

    assert _crear_app().get("/v1/pedidos-de-prueba").status_code == 404


def test_capa_3_apagada_ni_siquiera_la_importa(capa3: pytest.MonkeyPatch) -> None:
    # Dado un router de la capa 3 cuyo paquete no existe
    from app import main

    capa3.setattr(main, "ROUTERS_CAPA_3", ("app.modules.ordering.api.no_existe_matu40:router",))

    # Apagada, la API arranca: no lo busca
    capa3.setenv("CAPA3_HABILITADA", "false")
    assert _crear_app().get("/v1/salud").status_code == 200

    # Encendida, lo busca y falla: la diferencia es el interruptor
    capa3.setenv("CAPA3_HABILITADA", "true")
    from app.core import config

    config.obtener_configuracion.cache_clear()
    with pytest.raises(ModuleNotFoundError):
        _crear_app()


def test_capa_3_apagada_por_omision(configuracion_sin_env: None) -> None:
    from app.core.config import obtener_configuracion

    assert obtener_configuracion().capa3_habilitada is False


def test_routers_capa_3_solo_trae_la_capa_3() -> None:
    # ROUTERS_CAPA_3 no es una puerta trasera para apagar la ficha o el consumo por error
    from app.main import ROUTERS_CAPA_3

    ajenos = [r for r in ROUTERS_CAPA_3 if not es_de_la_capa_3(r.partition(":")[0], PAQUETES_CAPA_3)]
    assert ajenos == []


# ---------------------------------------------------------------------------
# 5 · Lo que app.main carga no llega a la capa 3
# ---------------------------------------------------------------------------


def _modulos(raiz: Path) -> dict[str, Path]:
    return {_nombre_modulo(raiz, archivo)[0]: archivo for archivo in _archivos_python(raiz)}


def _resolver(destino: str, conocidos: dict[str, Path]) -> list[str]:
    """'app.modules.x.api.router.router' → el módulo más largo que existe y los paquetes que lo contienen."""
    partes = destino.split(".")
    for largo in range(len(partes), 0, -1):
        nombre = ".".join(partes[:largo])
        if nombre in conocidos:
            return [".".join(partes[:i]) for i in range(1, largo + 1) if ".".join(partes[:i]) in conocidos]
    return []


def recorrer(raiz: Path, entrada: str, paquetes: tuple[str, ...]) -> tuple[set[str], list[str]]:
    """Recorre las importaciones desde entrada, en cualquier nivel del código (también dentro de
    funciones). Devuelve los módulos alcanzados y la cadena hasta el primer módulo de la capa 3, o []
    si no llega a ninguno. Una importación de la capa 3 sin archivo (la capa aún no existe) también cuenta."""
    conocidos = _modulos(raiz)
    padre: dict[str, str | None] = {entrada: None}
    pendientes = [entrada]
    cadena: list[str] = []
    while pendientes:
        actual = pendientes.pop()
        archivo = conocidos[actual]
        for importacion in _importaciones(raiz, archivo, _leer(archivo)):
            if es_de_la_capa_3(importacion.destino, paquetes):
                if not cadena:
                    cadena = [f"{importacion.destino} (línea {importacion.linea})", actual]
                    while (anterior := padre[cadena[-1]]) is not None:
                        cadena.append(anterior)
                    cadena.reverse()
                continue
            for modulo in _resolver(importacion.destino, conocidos):
                if modulo not in padre:
                    padre[modulo] = actual
                    pendientes.append(modulo)
    return set(padre), cadena


def cadena_hacia_la_capa_3(raiz: Path, entrada: str, paquetes: tuple[str, ...]) -> list[str]:
    return recorrer(raiz, entrada, paquetes)[1]


def test_app_main_no_llega_a_la_capa_3() -> None:
    cadena = cadena_hacia_la_capa_3(APP, "app.main", PAQUETES_CAPA_3)

    assert cadena == [], "app.main llega a la capa 3 por: " + " → ".join(cadena)


def test_el_recorrido_alcanza_las_capas_1_y_2() -> None:
    # Si el recorrido se cortara en app.main, la prueba anterior pasaría en vacío
    alcanzados, _ = recorrer(APP, "app.main", PAQUETES_CAPA_3)

    for modulo in CAPAS_1_Y_2:
        assert f"app.modules.{modulo}.api.router" in alcanzados
        assert f"app.modules.{modulo}.infrastructure" in {m.rsplit(".", 1)[0] for m in alcanzados}


def _arbol(tmp_path: Path, archivos: dict[str, str]) -> Path:
    raiz = tmp_path / "app"
    for ruta, codigo in {"__init__.py": "", "modules/__init__.py": "", **archivos}.items():
        destino = raiz / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(codigo, encoding="utf-8")
    return raiz


CADENAS_PROHIBIDAS = [
    pytest.param({"main.py": "from app.modules.payments.api.router import router\n"}, id="main-importa-payments"),
    pytest.param(
        {
            "main.py": "from app.modules.backoffice.api.router import router\n",
            "modules/backoffice/__init__.py": "",
            "modules/backoffice/api/__init__.py": "",
            "modules/backoffice/api/router.py": "def f():\n    from app.modules.ordering import pedido\n",
        },
        id="main-importa-backoffice-que-importa-ordering",
    ),
    pytest.param(
        {
            "main.py": "from app.modules.consumption.api import router\n",
            "modules/consumption/__init__.py": "from app.modules.catalog import producto\n",
            "modules/consumption/api/__init__.py": "",
            "modules/consumption/api/router.py": "",
        },
        id="paquete-consumption-importa-catalog",
    ),
]


@pytest.mark.parametrize("archivos", CADENAS_PROHIBIDAS)
def test_cadena_hacia_la_capa_3_se_detecta(tmp_path: Path, archivos: dict[str, str]) -> None:
    raiz = _arbol(tmp_path, archivos)

    assert cadena_hacia_la_capa_3(raiz, "app.main", PAQUETES_CAPA_3) != []


def test_capa_3_por_nombre_en_routers_capa_3_no_es_una_cadena(tmp_path: Path) -> None:
    # El texto de ROUTERS_CAPA_3 no es una importación: es lo que permite arrancar sin la capa 3
    raiz = _arbol(tmp_path, {"main.py": 'ROUTERS_CAPA_3 = ("app.modules.ordering.api.router:router",)\n'})

    assert cadena_hacia_la_capa_3(raiz, "app.main", PAQUETES_CAPA_3) == []


def test_paquetes_bloqueados_siguen_las_flechas() -> None:
    # Lo que llega al núcleo del despacho por las flechas de la sección 6.3 se quita con él
    bloqueados = {p.rsplit(".", 1)[1] for p in PAQUETES_CAPA_3}
    dependientes = {m for m, alcanza in ALCANZABLES.items() if alcanza & NUCLEO_DESPACHO} | NUCLEO_DESPACHO
    assert dependientes <= bloqueados

    # Y nada de lo que las capas 1 y 2 alcanzan por las flechas queda bloqueado: si alguien devuelve la
    # flecha consumption → catalog a FLECHAS, esto falla (decisión 104)
    necesarios = set(CAPAS_1_Y_2).union(*(ALCANZABLES[m] for m in CAPAS_1_Y_2))
    assert necesarios & bloqueados == set()


# ---------------------------------------------------------------------------
# 6 · Esquema: ninguna llave foránea hacia la capa 3 (con base)
# ---------------------------------------------------------------------------

# Modelo de datos, sección 3.1: las tablas de catalog, ordering, replenishment, payments, fulfillment y
# settlement
TABLAS_CAPA_3 = frozenset(
    {
        "categoria_cuidado", "producto", "comercio", "usuario_comercio", "convenio", "oferta",
        "pedido", "pedido_entrega", "pedido_linea", "regla_sustitucion", "pedido_transicion", "pedido_comercio",
        "plan_reposicion", "plan_reposicion_linea", "ocurrencia",
        "cargo", "participacion", "transaccion_pasarela", "medio_pago_inscrito",
        "repartidor", "oferta_asignacion", "asignacion", "evidencia",
        "liquidacion", "consumo_comercio",
    }
)

# Tablas que no son de las capas 1 y 2 y pueden apuntar al despacho: backoffice atiende incidencias de
# pedidos (modelo de datos, sección 3.1, BO --> ORD)
# MATU-61 (D5): idempotencia es transversal, pero solo la usan los POST de pedidos y pagos (arquitectura 9.1); su
# pedido_id cae con el pedido (ON DELETE CASCADE) y no la usa ninguna ruta de las capas 1 y 2
FUERA_DE_LAS_CAPAS_1_Y_2 = frozenset({"incidencia", "idempotencia"})

# La única llave de las capas 1 y 2 hacia la capa 3, declarada (decisión 104): el insumo puede venir del
# catálogo, y si no, va con nombre_libre (ADR-002). Es anulable, y sin catálogo queda vacía
EXCEPCIONES = frozenset({("perfil_consumo", "producto_id", "producto")})

LLAVES_FORANEAS = """
    SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text
    FROM pg_constraint c
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
    WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
"""


@pytest.fixture(scope="module")
def llaves() -> set[tuple[str, str, str]]:
    with psycopg.connect(DSN) as cx:
        return {(origen, columna, destino) for origen, columna, destino in cx.execute(LLAVES_FORANEAS)}


def violaciones_de_esquema(llaves: set[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    return sorted(
        llave
        for llave in llaves
        if llave[2] in TABLAS_CAPA_3
        and llave[0] not in TABLAS_CAPA_3 | FUERA_DE_LAS_CAPAS_1_Y_2
        and llave not in EXCEPCIONES
    )


@requiere_base
def test_ninguna_tabla_de_las_capas_1_y_2_apunta_a_la_capa_3(llaves: set[tuple[str, str, str]]) -> None:
    assert violaciones_de_esquema(llaves) == []


@requiere_base
def test_la_lista_de_tablas_de_la_capa_3_existe_y_la_consulta_ve_sus_llaves(llaves: set[tuple[str, str, str]]) -> None:
    # Si una tabla cambia de nombre, la lista no queda vieja en silencio
    tablas = {origen for origen, _, _ in llaves} | {destino for _, _, destino in llaves}
    assert TABLAS_CAPA_3 - tablas == set()
    # No pasa en vacío: la consulta ve las llaves de la capa 3 entre sí, y las excepciones existen
    assert ("cargo", "pedido_id", "pedido") in llaves
    assert EXCEPCIONES <= llaves


def test_una_llave_nueva_hacia_la_capa_3_se_detecta() -> None:
    llaves = {
        ("reposicion", "pedido_ref", "pedido"),  # la referencia opaca, si alguien le pusiera llave
        ("cargo", "pedido_id", "pedido"),
        ("incidencia", "pedido_id", "pedido"),
        *EXCEPCIONES,
    }

    assert violaciones_de_esquema(llaves) == [("reposicion", "pedido_ref", "pedido")]


# ---------------------------------------------------------------------------
# 7 · Flujos de las capas 1 y 2 con la capa 3 bloqueada (con base)
# ---------------------------------------------------------------------------

# Los caminos felices que ya existen, corridos tal cual con la capa 3 quitada. Si una cambia de nombre,
# pytest no la encuentra y esta prueba falla con ese mensaje
FLUJOS = (
    "tests/modules/care_plan/test_ficha_api.py::test_ficha_tres_campos",
    "tests/modules/care_plan/test_relevo_api.py::test_acceso_guarda_solo_hash",
    "tests/modules/care_plan/test_abrir_relevo_api.py::test_relevo_ve_solo_campos_habilitados",
    "tests/modules/consumption/test_consumo_api.py::test_crear_ver_listar_editar_desactivar_activar_eliminar",
    "tests/modules/consumption/test_alertas_api.py::test_listar_y_descartar_una_alerta",
    # La lista de insumos (MATU-60): se exporta sin catálogo, con nombre libre
    "tests/modules/consumption/test_lista_api.py::test_la_lista_trae_lo_que_avisa_con_la_cantidad_y_en_orden",
    # MATU-61 (C2): sin la capa 3, dos autorizaciones, y borrar a la persona funciona y no toca pedidos
    "tests/modules/care_circle/test_despacho_capa3_api.py::test_sin_la_capa_3_son_dos_autorizaciones_y_despacho_no_existe",
    "tests/modules/care_circle/test_despacho_capa3_api.py::test_sin_la_capa_3_borrar_a_la_persona_funciona_y_revoca_despacho",
)


@requiere_base
def test_flujos_de_las_capas_1_y_2_pasan_sin_la_capa_3() -> None:
    proceso = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.sin_capa3", "-p", "no:cacheprovider", "-q", *FLUJOS],
        cwd=BACKEND,
        env=_entorno_sin_capa3(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    salida = proceso.stdout[-3000:]

    assert proceso.returncode == 0, salida
    # Todas pasan: ni una saltada (la base está, la marca requiere_base lo asegura)
    assert re.search(rf"\b{len(FLUJOS)} passed\b", salida) and "skipped" not in salida, salida
