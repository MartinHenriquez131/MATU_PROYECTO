"""La imagen de Railway trae todos los archivos que la semilla de demo necesita (MATU-64, H1 del 09-11).

La semilla (`infra/semillas/demo.py`) se corre dentro del contenedor por `railway ssh`. Carga por ruta
otros archivos hermanos de `infra/semillas/` (por ejemplo `catalogo_demo.py`, de MATU-59), porque
`infra/` no es un paquete. Si el Dockerfile no copia uno de ellos, la semilla falla en Railway con
`FileNotFoundError`, y nada lo detectaba antes de desplegar: así pasó el 09-11 en la demo.

Esta prueba, sin Docker ni base de datos:

1. busca qué archivos hermanos nombra `demo.py` (y, a su vez, los que nombran esos archivos);
2. exige que cada uno, y `demo.py`, tenga su propia línea `COPY infra/semillas/<archivo> ...` en
   `infra/railway/Dockerfile`;
3. exige que el Dockerfile no copie la carpeta `infra/semillas` completa, porque ahí puede quedar
   `salida/relevo-demo.txt` (con el enlace y el PIN del relevo de ejemplo) de un build local.

Para que no pase en vacío, el mismo verificador corre sobre casos sintéticos que rompen cada regla.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SEMILLAS = RAIZ / "infra" / "semillas"
DOCKERFILE = RAIZ / "infra" / "railway" / "Dockerfile"
ENTRADA = "demo.py"


def archivos_que_necesita(carpeta: Path, entrada: str = ENTRADA) -> set[str]:
    """Los .py de la carpeta que `entrada` nombra, directa o indirectamente, incluida la entrada.

    Un archivo «nombra» a un hermano si su texto contiene el nombre del hermano (por ejemplo
    `"catalogo_demo.py"` en una ruta o `catalogo_demo` en un import). Es conservador: un nombre que
    aparece solo en un comentario también cuenta, y es preferible copiar un archivo de más.
    """
    hermanos = {p.name for p in carpeta.glob("*.py")}
    necesarios = {entrada}
    pendientes = [entrada]
    while pendientes:
        texto = (carpeta / pendientes.pop()).read_text(encoding="utf-8")
        for nombre in hermanos - necesarios:
            if re.search(rf"\b{re.escape(nombre.removesuffix('.py'))}\b", texto):
                necesarios.add(nombre)
                pendientes.append(nombre)
    return necesarios


def problemas_del_dockerfile(dockerfile: str, necesarios: set[str]) -> list[str]:
    """Lo que le falta o le sobra al Dockerfile para la semilla, en texto para el mensaje de error."""
    lineas = [linea.strip() for linea in dockerfile.splitlines()]
    copias = [linea for linea in lineas if linea.upper().startswith("COPY ")]
    problemas = []
    for linea in copias:
        origenes = linea.split()[1:-1]
        if any(o.rstrip("/") in {"infra/semillas", "infra", "."} for o in origenes):
            problemas.append(
                f"«{linea}» copia la carpeta entera: copia cada archivo de infra/semillas en su propia "
                "línea, para no meter salida/relevo-demo.txt en la imagen"
            )
    for nombre in sorted(necesarios):
        origen = f"infra/semillas/{nombre}"
        if not any(origen in linea.split()[1:-1] for linea in copias):
            problemas.append(
                f"El Dockerfile no copia {origen}, que la semilla carga: agrega "
                f"«COPY {origen} /app/{origen}» debajo de la de demo.py"
            )
    return problemas


def test_el_dockerfile_copia_todo_lo_que_la_semilla_carga() -> None:
    necesarios = archivos_que_necesita(SEMILLAS)
    assert "catalogo_demo.py" in necesarios, "la búsqueda de hermanos dejó de encontrar catalogo_demo.py"
    problemas = problemas_del_dockerfile(DOCKERFILE.read_text(encoding="utf-8"), necesarios)
    assert not problemas, "\n".join(problemas)


# --- Casos sintéticos: el verificador detecta cada problema -------------------------------------------


@pytest.fixture
def carpeta_semillas(tmp_path: Path) -> Path:
    (tmp_path / "demo.py").write_text(
        'ruta = Path(__file__).parent / "catalogo_demo.py"\nimport ayuda_demo\n', encoding="utf-8"
    )
    (tmp_path / "catalogo_demo.py").write_text("# usa precios_demo\n", encoding="utf-8")
    (tmp_path / "precios_demo.py").write_text("PRECIOS = {}\n", encoding="utf-8")
    (tmp_path / "ayuda_demo.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "suelto.py").write_text("NO_LO_USA_NADIE = 1\n", encoding="utf-8")
    return tmp_path


def test_encuentra_los_hermanos_directos_e_indirectos(carpeta_semillas: Path) -> None:
    assert archivos_que_necesita(carpeta_semillas) == {
        "demo.py",
        "catalogo_demo.py",
        "precios_demo.py",
        "ayuda_demo.py",
    }


COMPLETO = """
COPY infra/semillas/demo.py /app/infra/semillas/demo.py
COPY infra/semillas/catalogo_demo.py /app/infra/semillas/catalogo_demo.py
"""


def test_un_dockerfile_completo_no_tiene_problemas() -> None:
    assert problemas_del_dockerfile(COMPLETO, {"demo.py", "catalogo_demo.py"}) == []


@pytest.mark.parametrize(
    ("dockerfile", "esperado"),
    [
        pytest.param(
            "COPY infra/semillas/demo.py /app/infra/semillas/demo.py\n",
            "no copia infra/semillas/catalogo_demo.py",
            id="falta_un_hermano",
        ),
        pytest.param(
            COMPLETO + "COPY infra/semillas /app/infra/semillas\n",
            "copia la carpeta entera",
            id="copia_la_carpeta",
        ),
        pytest.param(
            COMPLETO + "COPY infra/semillas/ /app/infra/semillas/\n",
            "copia la carpeta entera",
            id="copia_la_carpeta_con_barra",
        ),
        pytest.param(
            "# COPY infra/semillas/catalogo_demo.py /app/infra/semillas/catalogo_demo.py\n"
            "COPY infra/semillas/demo.py /app/infra/semillas/demo.py\n",
            "no copia infra/semillas/catalogo_demo.py",
            id="la_linea_esta_comentada",
        ),
    ],
)
def test_el_verificador_detecta_el_problema(dockerfile: str, esperado: str) -> None:
    problemas = problemas_del_dockerfile(dockerfile, {"demo.py", "catalogo_demo.py"})
    assert any(esperado in p for p in problemas), problemas
