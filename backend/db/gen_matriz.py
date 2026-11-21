"""Genera la matriz de acceso por eje (10-rls-matriz-de-acceso.png y .svg) en MATU_DIAGRAMAS,
por defecto ../MATU/docs/diagramas/modelo-datos.
Copia la tabla 5.3 de docs/modelo-datos.md, que es la que manda: cada celda está respaldada
por una prueba de tests/test_aislamiento.py, y las marcas ¹ a ⁷ remiten a las notas de esa sección."""

import os
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Los diagramas se publican en el repositorio de documentación (MATU), clonado junto a este.
# Se puede cambiar con la variable MATU_DIAGRAMAS.
POR_DEFECTO = pathlib.Path(__file__).resolve().parents[3] / "MATU" / "docs" / "diagramas" / "modelo-datos"
SALIDA = pathlib.Path(os.environ.get("MATU_DIAGRAMAS", POR_DEFECTO))
COLUMNAS = [
    "Plan de\ncuidado",
    "Perfil de\nconsumo",
    "Pedido",
    "Líneas y\nprecios",
    "Dirección\nde entrega",
    "Cargo y\npagos",
    "Liquidación",
    "Auditoría",
]
FILAS = [
    (
        "Familia",
        [
            "Según rol¹",
            "Sí",
            "Ven todos;\nescriben admin\ny cuidador³",
            "Ven todos;\nescriben admin\ny cuidador³",
            "Admin y cuidador\nla cambian;\nel pagador la ve;\nel observador no\nve la del pedido³",
            "Sí",
            "Nunca",
            "Su grupo, y\ncada persona la\nde su cuenta⁴",
        ],
    ),
    (
        "Relevo",
        [
            "Solo secciones\nhabilitadas\ny vigente",
            "Nunca",
            "Nunca",
            "Nunca",
            "Nunca",
            "Nunca",
            "Nunca",
            "Inserta la suya",
        ],
    ),
    (
        "Comercio",
        [
            "Nunca",
            "Nunca",
            "Solo su parte,\npor funciones²",
            "Solo las suyas,\npor funciones²",
            "Nunca",
            "Nunca",
            "Solo lee\nconsumo_comercio,\nlos suyos",
            "Inserta la suya,\nsin grupo⁵",
        ],
    ),
    (
        "Repartidor",
        ["Nunca", "Nunca", "Su asignación\nactiva", "Nunca", "Su asignación\nactiva", "Nunca", "Nunca", "Nunca"],
    ),
    (
        "Operación",
        ["Nunca", "Nunca", "Todos", "Todos", "Nunca⁶", "Todos", "Todos", "Inserta,\nsin leer⁷"],
    ),
    (
        "Sistema\n(worker)",
        ["Nunca", "Su grupo", "Su grupo", "Su grupo", "Nunca⁶", "Su grupo", "Nunca", "Inserta"],
    ),
    ("Sin contexto", ["Nunca"] * 8),
]
NOTAS = "¹²³⁴⁵⁶⁷"


def color(v: str) -> str:
    v = v.rstrip(NOTAS)
    if v.startswith("Nunca"):
        return "#f6d5d2"
    if v in ("Sí", "Todos"):
        return "#d4ecd9"
    return "#fdf0c8"


ALTO = {0: 0.10, 1: 0.20}  # la fila de la familia lleva celdas de cinco líneas

fig, ax = plt.subplots(figsize=(18, 8))
ax.axis("off")
t = ax.table(
    cellText=[f[1] for f in FILAS],
    rowLabels=[f[0] for f in FILAS],
    colLabels=COLUMNAS,
    cellLoc="center",
    loc="center",
    cellColours=[[color(v) for v in f[1]] for f in FILAS],
    rowColours=["#eef1f6"] * len(FILAS),
    colColours=["#0A253E"] * len(COLUMNAS),
)
t.auto_set_font_size(False)
t.set_fontsize(10.5)
for (r, c), celda in t.get_celld().items():
    celda.set_height(ALTO.get(r, 0.10))
    celda.set_edgecolor("#9aa4b2")
    if r == 0:
        celda.get_text().set_color("white")
        celda.get_text().set_fontweight("bold")
    if c == -1:
        celda.get_text().set_fontweight("bold")
        celda.set_width(0.10)
    elif c >= 0:
        celda.set_width(0.112)
ax.set_title(
    "MATU · Qué filas alcanza cada eje de acceso (RLS forzado · verificado por tests/test_aislamiento.py)",
    fontsize=14,
    weight="bold",
    pad=18,
)
fig.text(
    0.02,
    0.02,
    "¹ admin y cuidador siempre · pagador solo con puede_ver_plan · observador nunca.     "
    "² a ⁷: ver las notas de modelo-datos.md, sección 5.3.\n"
    "Verde: acceso completo     Amarillo: acotado     Rojo: cero filas por política",
    fontsize=10,
)
SALIDA.mkdir(parents=True, exist_ok=True)
for ext in ("png", "svg"):
    fig.savefig(SALIDA / f"10-rls-matriz-de-acceso.{ext}", dpi=160, bbox_inches="tight", facecolor="white")
print("matriz escrita")
