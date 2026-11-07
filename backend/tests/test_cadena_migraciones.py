"""Prueba de arquitectura: las migraciones de Alembic son una sola cadena lineal (MATU-70).

Dos ramas que agregan cada una su migración sobre la misma cabeza chocan al fusionarse: Alembic
queda con dos cabezas y `upgrade head` falla, o, si las dos usan el mismo número, una tapa a la
otra sin aviso. Esta prueba lo detecta antes de fusionar, sin base de datos: lee las migraciones
con ScriptDirectory y la configuración de backend/alembic.ini.

Verifica que:

1. hay exactamente una cabeza;
2. no hay ramas ni revisiones de merge: ningún down_revision repetido ni en tupla, y ninguna
   revisión repetida entre archivos;
3. cada archivo empieza con su revision, las revisiones son 0001, 0002, ... seguidas, sin huecos,
   y cada down_revision es la anterior (la 0001 tiene None).

Para que no pase en vacío, el mismo verificador corre sobre carpetas sintéticas en tmp_path que
rompen cada regla, y debe detectarlas.
"""

import warnings
from collections.abc import Mapping
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND / "alembic.ini"
DIGITOS = 4

# {nombre del archivo: (revision, down_revision)}
Migraciones = Mapping[str, tuple[str, str | tuple[str, ...] | None]]


def _carpeta_versiones(script: ScriptDirectory) -> Path:
    return Path(script.versions)


def problemas_de_la_cadena(script: ScriptDirectory) -> list[str]:
    """Devuelve los problemas de la cadena de migraciones. Una cadena sana devuelve []."""
    problemas: list[str] = []

    # Alembic avisa con un warning, y se queda con una, cuando dos archivos declaran la misma revision.
    # Se cuenta por archivo para que el choque no quede tapado
    archivos = sorted(p for p in _carpeta_versiones(script).glob("*.py") if p.name != "__init__.py")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        revisiones = list(script.walk_revisions())

    por_archivo = {Path(r.path).name: r for r in revisiones}
    sin_leer = [a.name for a in archivos if a.name not in por_archivo]
    if sin_leer:
        problemas.append(
            f"Hay archivos con una revision repetida o que Alembic no leyó: {sin_leer}. "
            "Cada migración nueva usa el número siguiente al de la última."
        )

    cabezas = sorted(script.get_heads())
    if len(cabezas) != 1:
        problemas.append(
            f"Alembic tiene {len(cabezas)} cabezas: {cabezas}. Hay una sola cadena: la migración nueva "
            "debe apuntar (down_revision) a la última, y se renumera si otra rama ya ocupó su número."
        )

    hijas: dict[str, list[str]] = {}
    for r in revisiones:
        abajo = r.down_revision
        if isinstance(abajo, tuple | list):
            problemas.append(f"La revisión {r.revision} es un merge (down_revision={abajo}). No se usan merges.")
            continue
        if abajo is not None:
            hijas.setdefault(abajo, []).append(r.revision)
    for padre, varias in sorted(hijas.items()):
        if len(varias) > 1:
            problemas.append(f"Rama de Alembic: {sorted(varias)} tienen el mismo down_revision {padre!r}.")

    for r in revisiones:
        nombre = Path(r.path).name
        if not nombre.startswith(f"{r.revision}_"):
            problemas.append(f"El archivo {nombre} no empieza con su revision {r.revision!r}_.")
        if not (len(r.revision) == DIGITOS and r.revision.isdigit()):
            problemas.append(f"La revisión {r.revision!r} ({nombre}) no tiene {DIGITOS} dígitos.")

    numeradas = sorted(
        (r for r in revisiones if len(r.revision) == DIGITOS and r.revision.isdigit()), key=lambda r: r.revision
    )
    for posicion, r in enumerate(numeradas, start=1):
        esperada = f"{posicion:0{DIGITOS}d}"
        anterior = None if posicion == 1 else f"{posicion - 1:0{DIGITOS}d}"
        if r.revision != esperada:
            problemas.append(f"Hueco en la numeración: se esperaba {esperada} y viene {r.revision}.")
            break
        if r.down_revision != anterior:
            problemas.append(
                f"La revisión {r.revision} tiene down_revision={r.down_revision!r}, y debe ser {anterior!r}."
            )

    return problemas


def _script_del_repositorio() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))


def test_las_migraciones_del_repositorio_son_una_sola_cadena() -> None:
    script = _script_del_repositorio()
    assert list(script.walk_revisions()), "el verificador no encontró migraciones"
    assert problemas_de_la_cadena(script) == []


def test_la_cadena_tiene_una_sola_cabeza() -> None:
    cabezas = _script_del_repositorio().get_heads()
    assert len(cabezas) == 1, (
        f"Alembic tiene {len(cabezas)} cabezas: {sorted(cabezas)}. La migración nueva debe apuntar a la última."
    )


# ---------------------------------------------------------------------------
# El verificador detecta cada choque (DdT 6: falla sin la corrección)
# ---------------------------------------------------------------------------


def _carpeta_sintetica(raiz: Path, migraciones: Migraciones) -> ScriptDirectory:
    """Crea una carpeta de Alembic con archivos {nombre: (revision, down_revision)} y la lee."""
    versiones = raiz / "versions"
    versiones.mkdir(parents=True)
    for nombre, (revision, abajo) in migraciones.items():
        (versiones / nombre).write_text(
            f'"""Migración sintética."""\nrevision = {revision!r}\ndown_revision = {abajo!r}\n'
            "branch_labels = None\ndepends_on = None\n\n\ndef upgrade() -> None:\n    pass\n\n\n"
            "def downgrade() -> None:\n    pass\n",
            encoding="utf-8",
        )
    return ScriptDirectory(str(raiz))


SANA = {
    "0001_inicial.py": ("0001", None),
    "0002_segunda.py": ("0002", "0001"),
    "0003_tercera.py": ("0003", "0002"),
}


def test_una_cadena_sana_no_tiene_problemas(tmp_path: Path) -> None:
    assert problemas_de_la_cadena(_carpeta_sintetica(tmp_path, SANA)) == []


CHOQUES = {
    "dos_cabezas": (
        {**SANA, "0004_rama_a.py": ("0004", "0003"), "0005_rama_b.py": ("0005", "0003")},
        "2 cabezas: ['0004', '0005']",
    ),
    "mismo_numero_en_dos_ramas": (
        {**SANA, "0004_rama_a.py": ("0004", "0003"), "0004_rama_b.py": ("0004", "0003")},
        "revision repetida",
    ),
    "merge": (
        {**SANA, "0004_rama_a.py": ("0004", "0002"), "0005_merge.py": ("0005", ("0003", "0004"))},
        "es un merge",
    ),
    "hueco": (
        {**SANA, "0005_salta.py": ("0005", "0003")},
        "Hueco en la numeración",
    ),
    "down_revision_no_es_la_anterior": (
        {"0001_inicial.py": ("0001", None), "0002_segunda.py": ("0002", None)},
        "debe ser '0001'",
    ),
    "archivo_no_empieza_con_su_revision": (
        {**SANA, "0009_mal_nombre.py": ("0004", "0003")},
        "no empieza con su revision",
    ),
}


@pytest.mark.parametrize(("migraciones", "esperado"), CHOQUES.values(), ids=CHOQUES.keys())
def test_el_verificador_detecta_el_choque(tmp_path: Path, migraciones: Migraciones, esperado: str) -> None:
    problemas = problemas_de_la_cadena(_carpeta_sintetica(tmp_path, migraciones))
    assert any(esperado in p for p in problemas), problemas
