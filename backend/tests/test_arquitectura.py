"""Prueba de arquitectura: reglas de dependencia y pureza de domain/ (MATU-03, ADR-021).

Recorre el árbol de importaciones con ast (no con expresiones regulares) y verifica las
cuatro reglas de la sección 6.4 de la arquitectura:

1. Las flechas de la sección 6.3 no se invierten. Un módulo solo importa a otro si hay un
   camino de flechas hacia él (clausura transitiva). backoffice es la excepción declarada:
   importa cualquier módulo salvo care_plan y consumption.
2. Nadie importa care_plan salvo consumption, y consumption solo a través de
   app.modules.care_plan.interfaz_consumo.
3. care_plan y consumption no importan fulfillment, settlement ni payments.
4. Nadie importa notifications: solo consume eventos.

Además, app.core y app.shared no importan app.modules, y ningún archivo de domain/ lee el
reloj del sistema ni importa algo fuera de la biblioteca estándar, app.shared o su módulo.

Para que no pase en vacío, el mismo verificador corre sobre árboles falsos en tmp_path que
sí rompen cada regla, y debe detectarlos.
"""

import ast
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

# ---------------------------------------------------------------------------
# El grafo permitido, declarado una sola vez
# ---------------------------------------------------------------------------

# Flechas de la sección 6.3: el módulo de la izquierda puede importar a los de la derecha
FLECHAS: dict[str, frozenset[str]] = {
    "iam": frozenset(),
    "care_circle": frozenset({"iam"}),
    "care_plan": frozenset({"care_circle"}),
    "consumption": frozenset({"care_plan", "catalog"}),
    "catalog": frozenset({"iam"}),
    "replenishment": frozenset({"consumption", "ordering"}),
    "ordering": frozenset({"care_circle", "catalog"}),
    "payments": frozenset({"ordering"}),
    "fulfillment": frozenset({"ordering"}),
    "settlement": frozenset({"fulfillment", "catalog"}),
    "rx": frozenset({"ordering"}),
    "notifications": frozenset(),
}

# backoffice no está en el diagrama: importa cualquier módulo salvo estos
BACKOFFICE = "backoffice"
BACKOFFICE_NO_IMPORTA = frozenset({"care_plan", "consumption"})

# Regla 2: care_plan solo se importa desde consumption, y solo por esta interfaz
CARE_PLAN = "care_plan"
CONSUMPTION = "consumption"
INTERFAZ_CONSUMO = "interfaz_consumo"

# Regla 3: la capa 3 que debe poder quitarse sin tocar las capas 1 y 2
CAPA_3 = frozenset({"payments", "fulfillment", "settlement"})
CAPAS_1_Y_2 = frozenset({CARE_PLAN, CONSUMPTION})

# Regla 4
NOTIFICATIONS = "notifications"

# Paquetes transversales: cualquiera los importa, ellos no importan app.modules
TRANSVERSALES = frozenset({"core", "shared"})

# Lo que domain/ no puede tocar para leer la hora
RELOJ_DEL_SISTEMA = frozenset(
    {
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "datetime.datetime.today",
        "datetime.date.today",
        "time.time",
        "time.time_ns",
    }
)


def _clausura(flechas: dict[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """Para cada módulo, todos los módulos a los que llega siguiendo flechas."""
    alcanzables: dict[str, frozenset[str]] = {}
    for origen in flechas:
        vistos: set[str] = set()
        pendientes = list(flechas[origen])
        while pendientes:
            actual = pendientes.pop()
            if actual not in vistos:
                vistos.add(actual)
                pendientes.extend(flechas.get(actual, frozenset()))
        alcanzables[origen] = frozenset(vistos)
    return alcanzables


ALCANZABLES = _clausura(FLECHAS)


# ---------------------------------------------------------------------------
# El verificador
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violacion:
    archivo: str
    linea: int
    regla: str
    detalle: str

    def __str__(self) -> str:
        return f"{self.archivo}:{self.linea} [{self.regla}] {self.detalle}"


@dataclass(frozen=True)
class Importacion:
    linea: int
    destino: str  # nombre absoluto: app.modules.ordering.domain.pedido, httpx.Client, …


def _archivos_python(raiz: Path) -> list[Path]:
    return sorted(p for p in raiz.rglob("*.py") if "__pycache__" not in p.parts)


def _nombre_modulo(raiz: Path, archivo: Path) -> tuple[str, bool]:
    """Nombre con puntos del archivo dentro del paquete raíz, y si es un __init__.py."""
    partes = [raiz.name, *archivo.relative_to(raiz).with_suffix("").parts]
    es_paquete = partes[-1] == "__init__"
    if es_paquete:
        partes.pop()
    return ".".join(partes), es_paquete


def _importaciones(raiz: Path, archivo: Path, arbol: ast.Module) -> Iterator[Importacion]:
    """Todas las importaciones del archivo, absolutas y relativas, en cualquier nivel del código."""
    nombre, es_paquete = _nombre_modulo(raiz, archivo)
    paquete_actual = nombre if es_paquete else nombre.rpartition(".")[0]
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                yield Importacion(nodo.lineno, alias.name)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                partes = paquete_actual.split(".")
                subir = nodo.level - 1
                if subir >= len(partes):
                    continue  # relativa que se sale del paquete: Python la rechaza igual
                base = ".".join(partes[: len(partes) - subir])
                if nodo.module:
                    base = f"{base}.{nodo.module}"
            else:
                base = nodo.module or ""
            for alias in nodo.names:
                yield Importacion(nodo.lineno, base if alias.name == "*" else f"{base}.{alias.name}")


def _leer(archivo: Path) -> ast.Module:
    return ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))


def _relativo(raiz: Path, archivo: Path) -> str:
    return archivo.relative_to(raiz.parent).as_posix()


def _modulo_de_negocio(nombre: str, paquete: str) -> str | None:
    """'app.modules.ordering.domain.x' → 'ordering'. None si no está dentro de un módulo."""
    partes = nombre.split(".")
    if len(partes) >= 3 and partes[0] == paquete and partes[1] == "modules":
        return partes[2]
    return None


def _bajo(nombre: str, prefijo: str) -> bool:
    return nombre == prefijo or nombre.startswith(prefijo + ".")


def _reglas_violadas(origen: str, destino: str, paquete: str) -> list[tuple[str, str]]:
    """Las reglas que rompe la importación de destino desde el archivo origen."""
    if not _bajo(destino, f"{paquete}.modules"):
        return []  # biblioteca estándar, terceros, app.core, app.shared, app.main

    partes_origen = origen.split(".")
    zona = partes_origen[1] if len(partes_origen) > 1 else ""
    if zona in TRANSVERSALES:
        return [("transversal", f"{paquete}.{zona} no importa {paquete}.modules ({destino})")]

    m_origen = _modulo_de_negocio(origen, paquete)
    m_destino = _modulo_de_negocio(destino, paquete)
    if m_origen is None or m_destino is None or m_origen == m_destino:
        return []  # main.py arma la aplicación, y un módulo se importa a sí mismo

    violadas: list[tuple[str, str]] = []

    if m_origen == BACKOFFICE:
        if m_destino in BACKOFFICE_NO_IMPORTA:
            violadas.append(("regla 1", f"backoffice no importa {m_destino}"))
    elif m_destino not in ALCANZABLES.get(m_origen, frozenset()):
        violadas.append(("regla 1", f"no hay flecha de {m_origen} hacia {m_destino} (sección 6.3)"))

    if m_destino == CARE_PLAN:
        interfaz = f"{paquete}.modules.{CARE_PLAN}.{INTERFAZ_CONSUMO}"
        if m_origen != CONSUMPTION:
            violadas.append(("regla 2", f"solo consumption importa care_plan, no {m_origen}"))
        elif not _bajo(destino, interfaz):
            violadas.append(("regla 2", f"consumption solo importa care_plan a través de {interfaz}, no {destino}"))

    if m_origen in CAPAS_1_Y_2 and m_destino in CAPA_3:
        violadas.append(("regla 3", f"{m_origen} no importa {m_destino}: la capa 3 debe poder quitarse"))

    if m_destino == NOTIFICATIONS:
        violadas.append(("regla 4", f"{m_origen} no importa notifications: notifications solo consume eventos"))

    return violadas


def verificar_dependencias(raiz: Path) -> list[Violacion]:
    """Recorre el paquete raíz y devuelve cada importación que rompe una regla de la sección 6.4."""
    paquete = raiz.name
    violaciones: list[Violacion] = []
    for archivo in _archivos_python(raiz):
        origen, _ = _nombre_modulo(raiz, archivo)
        for importacion in _importaciones(raiz, archivo, _leer(archivo)):
            for regla, detalle in _reglas_violadas(origen, importacion.destino, paquete):
                violaciones.append(Violacion(_relativo(raiz, archivo), importacion.linea, regla, detalle))
    return violaciones


def _nombre_calificado(nodo: ast.expr, alias: dict[str, str]) -> str | None:
    """'dt.now' con 'from datetime import datetime as dt' → 'datetime.datetime.now'."""
    if isinstance(nodo, ast.Name):
        return alias.get(nodo.id)
    if isinstance(nodo, ast.Attribute):
        base = _nombre_calificado(nodo.value, alias)
        return f"{base}.{nodo.attr}" if base else None
    return None


def verificar_pureza_dominio(raiz: Path) -> list[Violacion]:
    """Revisa cada archivo bajo una carpeta domain/: sin reloj del sistema y sin dependencias externas."""
    paquete = raiz.name
    violaciones: list[Violacion] = []
    for archivo in _archivos_python(raiz):
        if "domain" not in archivo.relative_to(raiz).parts[:-1]:
            continue
        origen, _ = _nombre_modulo(raiz, archivo)
        modulo = _modulo_de_negocio(origen, paquete)
        permitidos = [f"{paquete}.shared"] + ([f"{paquete}.modules.{modulo}"] if modulo else [])
        arbol = _leer(archivo)
        relativo = _relativo(raiz, archivo)

        for importacion in _importaciones(raiz, archivo, arbol):
            destino = importacion.destino
            if destino.split(".")[0] in sys.stdlib_module_names or any(_bajo(destino, p) for p in permitidos):
                continue
            violaciones.append(
                Violacion(relativo, importacion.linea, "dominio", f"domain/ no importa {destino}: solo stdlib, "
                          f"{paquete}.shared o su propio módulo")
            )

        # Nombre local → nombre calificado, para reconocer los alias del reloj del sistema
        alias: dict[str, str] = {}
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for a in nodo.names:
                    if a.asname:
                        alias[a.asname] = a.name
                    else:
                        alias[a.name.split(".")[0]] = a.name.split(".")[0]
            elif isinstance(nodo, ast.ImportFrom) and not nodo.level and nodo.module:
                for a in nodo.names:
                    alias[a.asname or a.name] = f"{nodo.module}.{a.name}"

        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Name | ast.Attribute):
                calificado = _nombre_calificado(nodo, alias)
                if calificado in RELOJ_DEL_SISTEMA:
                    violaciones.append(
                        Violacion(relativo, nodo.lineno, "dominio", f"domain/ no usa {calificado}: recibe un Reloj")
                    )
    return violaciones


def _detalle(violaciones: list[Violacion]) -> str:
    return "\n".join(str(v) for v in violaciones)


def _arbol(tmp_path: Path, archivos: dict[str, str]) -> Path:
    """Arma un paquete app/ falso en tmp_path con los archivos dados (ruta relativa a app/)."""
    raiz = tmp_path / "app"
    for ruta, codigo in archivos.items():
        destino = raiz / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(codigo, encoding="utf-8")
    return raiz


# ---------------------------------------------------------------------------
# Sobre el código real
# ---------------------------------------------------------------------------


def test_reglas_de_dependencia() -> None:
    violaciones = verificar_dependencias(APP)

    assert violaciones == [], "Importaciones que rompen la sección 6.4:\n" + _detalle(violaciones)


def test_dominio_sin_reloj_del_sistema() -> None:
    violaciones = verificar_pureza_dominio(APP)

    assert violaciones == [], "Archivos de domain/ que no son puros:\n" + _detalle(violaciones)


def test_verificador_recorre_el_paquete_real() -> None:
    # Si APP apuntara a otra carpeta, las dos pruebas anteriores pasarían en vacío
    relativos = {_relativo(APP, a) for a in _archivos_python(APP)}

    assert "app/shared/puertos.py" in relativos
    assert "app/modules/care_plan/application/ports.py" in relativos


def test_grafo_permitido_sin_ciclos() -> None:
    con_ciclo = sorted(m for m, alcanzables in ALCANZABLES.items() if m in alcanzables)

    assert con_ciclo == []


def test_modulos_existentes_declarados_en_el_grafo() -> None:
    # Un módulo nuevo debe agregarse a FLECHAS antes de escribir sus importaciones
    existentes = {p.parent.name for p in (APP / "modules").glob("*/__init__.py")}

    assert existentes - set(FLECHAS) - {BACKOFFICE} == set()


# ---------------------------------------------------------------------------
# No pasa en vacío: árboles falsos que rompen cada regla
# ---------------------------------------------------------------------------

IMPORTACIONES_PROHIBIDAS = [
    pytest.param("modules/catalog/application/servicio.py", "from app.modules.ordering.domain import pedido\n",
                 "regla 1", id="catalog-importa-ordering"),
    pytest.param("modules/catalog/application/servicio.py", "from ...ordering import api\n",
                 "regla 1", id="catalog-importa-ordering-relativo"),
    pytest.param("modules/catalog/servicio.py",
                 "def f():\n    from app.modules.ordering import pedido\n    return pedido\n",
                 "regla 1", id="catalog-importa-ordering-dentro-de-funcion"),
    pytest.param("modules/iam/servicio.py", "import app.modules.care_circle.domain\n",
                 "regla 1", id="iam-importa-care_circle"),
    pytest.param("modules/payments/servicio.py", "from app.modules.settlement import conciliacion\n",
                 "regla 1", id="payments-importa-settlement"),
    pytest.param("modules/backoffice/api/router.py", "from app.modules.consumption.application import lista\n",
                 "regla 1", id="backoffice-importa-consumption"),
    pytest.param("modules/care_circle/servicio.py", "from app.modules.care_plan.application.ports import X\n",
                 "regla 2", id="care_circle-importa-care_plan"),
    pytest.param("modules/backoffice/api/router.py", "from app.modules.care_plan import interfaz_consumo\n",
                 "regla 2", id="backoffice-importa-care_plan"),
    pytest.param("modules/consumption/application/prediccion.py", "from app.modules.care_plan.domain import seccion\n",
                 "regla 2", id="consumption-importa-submodulo-de-care_plan"),
    pytest.param("modules/consumption/application/prediccion.py", "from app.modules.care_plan import CustodiaClaves\n",
                 "regla 2", id="consumption-importa-paquete-care_plan"),
    pytest.param("modules/consumption/application/prediccion.py", "import app.modules.care_plan\n",
                 "regla 2", id="consumption-importa-care_plan-con-import"),
    pytest.param("modules/consumption/application/lista.py", "from app.modules.payments.application import cobro\n",
                 "regla 3", id="consumption-importa-payments"),
    pytest.param("modules/care_plan/application/x.py", "import app.modules.fulfillment.domain\n",
                 "regla 3", id="care_plan-importa-fulfillment"),
    pytest.param("modules/consumption/x.py", "from ..settlement import liquidacion\n",
                 "regla 3", id="consumption-importa-settlement-relativo"),
    pytest.param("modules/ordering/application/x.py", "from app.modules.notifications import enviar\n",
                 "regla 4", id="ordering-importa-notifications"),
    pytest.param("modules/backoffice/x.py", "import app.modules.notifications.application\n",
                 "regla 4", id="backoffice-importa-notifications"),
    pytest.param("shared/eventos.py", "from app.modules.catalog import eventos\n",
                 "transversal", id="shared-importa-modulo"),
    pytest.param("core/dependencias.py", "import app.modules.iam.api\n",
                 "transversal", id="core-importa-modulo"),
]


@pytest.mark.parametrize(("ruta", "codigo", "regla"), IMPORTACIONES_PROHIBIDAS)
def test_importacion_prohibida_falla(tmp_path: Path, ruta: str, codigo: str, regla: str) -> None:
    # Dado un paquete falso con una importación prohibida
    raiz = _arbol(tmp_path, {ruta: codigo})

    # Cuando se verifica
    violaciones = verificar_dependencias(raiz)

    # Entonces se detecta la regla rota, en ese archivo
    assert regla in {v.regla for v in violaciones}, _detalle(violaciones)
    assert {v.archivo for v in violaciones} == {f"app/{ruta}"}


def test_violacion_indica_archivo_linea_y_regla(tmp_path: Path) -> None:
    # Dado un archivo cuya tercera línea importa a contramano
    raiz = _arbol(tmp_path, {"modules/catalog/x.py": '"""Catálogo."""\n\nfrom app.modules.ordering import pedido\n'})

    # Cuando se verifica
    violaciones = verificar_dependencias(raiz)

    # Entonces el informe dice dónde y qué
    assert [(v.archivo, v.linea, v.regla) for v in violaciones] == [("app/modules/catalog/x.py", 3, "regla 1")]


IMPORTACIONES_PERMITIDAS = [
    pytest.param("modules/consumption/application/perfil.py",
                 "from app.modules.care_plan.interfaz_consumo import PerfilLectura\n", id="consumption-por-interfaz"),
    pytest.param("modules/consumption/application/perfil.py",
                 "from app.modules.care_plan import interfaz_consumo\n", id="consumption-interfaz-como-submodulo"),
    pytest.param("modules/consumption/application/lista.py",
                 "from app.modules.catalog.domain import producto\n", id="consumption-a-catalog"),
    pytest.param("modules/consumption/application/lista.py",
                 "from app.modules.care_circle.domain import persona\n", id="consumption-a-care_circle-transitiva"),
    pytest.param("modules/settlement/servicio.py",
                 "from app.modules.iam.domain import usuario\n", id="settlement-a-iam-transitiva"),
    pytest.param("modules/replenishment/servicio.py",
                 "from app.modules.catalog import api\nfrom app.modules.consumption import eventos\n",
                 id="replenishment-a-catalog-y-consumption"),
    pytest.param("modules/rx/servicio.py", "import app.modules.care_circle.domain\n", id="rx-a-care_circle-transitiva"),
    pytest.param("modules/backoffice/api/router.py",
                 "from app.modules.payments.application import cobros\nfrom app.modules.iam import api\n",
                 id="backoffice-a-payments-e-iam"),
    pytest.param("modules/ordering/application/servicio.py",
                 "from app.core.config import obtener_configuracion\nfrom app.shared.puertos import Reloj\n",
                 id="modulo-a-core-y-shared"),
    pytest.param("modules/catalog/application/servicio.py",
                 "from ..domain import producto\nfrom . import otro\nfrom app.modules.catalog.domain import oferta\n",
                 id="modulo-a-si-mismo"),
    pytest.param("modules/notifications/application/envio.py",
                 "from app.modules.notifications.domain import plantilla\n", id="notifications-a-si-mismo"),
    pytest.param("main.py", "from app.modules.catalog.api import router\n", id="main-arma-la-aplicacion"),
    pytest.param("shared/eventos.py", "from app.core.config import obtener_configuracion\nimport httpx\n",
                 id="shared-a-core-y-terceros"),
]


@pytest.mark.parametrize(("ruta", "codigo"), IMPORTACIONES_PERMITIDAS)
def test_importacion_permitida_no_falla(tmp_path: Path, ruta: str, codigo: str) -> None:
    # Dado un paquete falso con una importación que sigue las flechas
    raiz = _arbol(tmp_path, {ruta: codigo})

    # Cuando se verifica, entonces no hay violaciones
    violaciones = verificar_dependencias(raiz)
    assert violaciones == [], _detalle(violaciones)


# ---------------------------------------------------------------------------
# Pureza de domain/: árboles falsos que la rompen
# ---------------------------------------------------------------------------

DOMINIO = "modules/care_plan/domain/relevo.py"

RELOJES_PROHIBIDOS = [
    pytest.param("from datetime import datetime\n\ndef vence():\n    return datetime.now()\n", id="datetime.now"),
    pytest.param("import datetime\nx = datetime.datetime.utcnow()\n", id="datetime.datetime.utcnow"),
    pytest.param("from datetime import datetime\nx = datetime.today()\n", id="datetime.today"),
    pytest.param("from datetime import datetime as dt\nx = dt.now()\n", id="alias-dt.now"),
    pytest.param("import datetime as d\nx = d.date.today()\n", id="alias-modulo-date.today"),
    pytest.param("from datetime import date\nx = date.today()\n", id="date.today"),
    pytest.param("import time\nx = time.time()\n", id="time.time"),
    pytest.param("from time import time as reloj\nx = reloj()\n", id="alias-time"),
    pytest.param("from datetime import datetime\nahora = datetime.now\n", id="referencia-sin-llamar"),
]


@pytest.mark.parametrize("codigo", RELOJES_PROHIBIDOS)
def test_dominio_con_reloj_del_sistema_falla(tmp_path: Path, codigo: str) -> None:
    # Dado un domain/ que lee la hora del sistema
    raiz = _arbol(tmp_path, {DOMINIO: codigo})

    # Cuando se verifica, entonces se detecta
    violaciones = verificar_pureza_dominio(raiz)
    assert len(violaciones) == 1, _detalle(violaciones)
    assert "Reloj" in violaciones[0].detalle


SDK_PROHIBIDOS = [
    pytest.param("import httpx\n", id="httpx"),
    pytest.param("from sqlalchemy import select\n", id="sqlalchemy"),
    pytest.param("from pydantic import BaseModel\n", id="pydantic"),
    pytest.param("from transbank.webpay.webpay_plus.transaction import Transaction\n", id="transbank"),
    pytest.param("from app.core.config import obtener_configuracion\n", id="app.core"),
    pytest.param("from app.modules.care_circle.domain import persona\n", id="otro-modulo"),
]


@pytest.mark.parametrize("codigo", SDK_PROHIBIDOS)
def test_dominio_con_sdk_externo_falla(tmp_path: Path, codigo: str) -> None:
    # Dado un domain/ que importa algo fuera de la biblioteca estándar, app.shared o su módulo
    raiz = _arbol(tmp_path, {"modules/consumption/domain/prediccion/quiebre.py": codigo})

    # Cuando se verifica, entonces se detecta
    violaciones = verificar_pureza_dominio(raiz)
    assert [v.regla for v in violaciones] == ["dominio"], _detalle(violaciones)


def test_dominio_puro_no_falla(tmp_path: Path) -> None:
    # Dado un domain/ que recibe el reloj y solo usa stdlib, app.shared y su propio módulo
    codigo = (
        "from __future__ import annotations\n"
        "import uuid\n"
        "from dataclasses import dataclass\n"
        "from datetime import UTC, date, datetime, timedelta\n"
        "from app.shared.puertos import Reloj\n"
        "from app.modules.care_plan.domain.seccion import Seccion\n"
        "from .seccion import TipoSeccion\n"
        "\n"
        "LIMITE = datetime(2026, 1, 1, tzinfo=UTC)\n"
        "\n"
        "def vencido(reloj: Reloj, desde: datetime) -> bool:\n"
        "    return reloj.ahora() > desde + timedelta(hours=2)\n"
    )
    raiz = _arbol(tmp_path, {DOMINIO: codigo})

    # Cuando se verifica, entonces no hay violaciones
    violaciones = verificar_pureza_dominio(raiz)
    assert violaciones == [], _detalle(violaciones)


def test_reloj_del_sistema_fuera_de_domain_se_permite(tmp_path: Path) -> None:
    # Dado el reloj del sistema en infrastructure/, donde vive la implementación real
    raiz = _arbol(
        tmp_path,
        {"modules/care_plan/infrastructure/reloj.py": "from datetime import UTC, datetime\nx = datetime.now(UTC)\n"},
    )

    # Cuando se verifica la pureza de domain/, entonces no aplica
    assert verificar_pureza_dominio(raiz) == []
