"""Reglas puras del grupo familiar (MATU-06, RF-38).

Sin I/O: el nombre se valida aquí y la persistencia es un puerto (application/ports.py).
"""

LARGO_MINIMO_NOMBRE = 1
LARGO_MAXIMO_NOMBRE = 80

# Quien crea un grupo queda como admin de él, en la misma transacción
ROL_FUNDADOR = "admin"

# Quienes ven el plan de cuidado por su rol. El pagador solo con el permiso explícito de su
# membresía (membresia.puede_ver_plan); el observador nunca. Es la misma regla que app_puede_ver_plan()
# en la RLS y que care_plan/domain/ficha.puede_leer.
ROLES_QUE_VEN_PLAN = frozenset({"admin", "cuidador"})
ROL_PAGADOR = "pagador"


def ve_el_plan(rol: str, permiso_pagador: bool) -> bool:
    """Si quien tiene esa membresía ve el plan de cuidado (decisión 66, GET /v1/grupos)."""
    return rol in ROLES_QUE_VEN_PLAN or (rol == ROL_PAGADOR and permiso_pagador)


class NombreGrupoInvalido(ValueError):
    """El nombre del grupo está vacío o es demasiado largo. Nunca lleva el nombre en su mensaje."""

    def __init__(self) -> None:
        super().__init__(
            f"el nombre del grupo debe tener entre {LARGO_MINIMO_NOMBRE} y {LARGO_MAXIMO_NOMBRE} caracteres"
        )


def normalizar_nombre(nombre: str) -> str:
    """El nombre se guarda sin espacios en los extremos, con 1 a 80 caracteres.

    Lanza NombreGrupoInvalido si, sin esos espacios, queda fuera de ese largo.
    """
    limpio = nombre.strip()
    if not LARGO_MINIMO_NOMBRE <= len(limpio) <= LARGO_MAXIMO_NOMBRE:
        raise NombreGrupoInvalido()
    return limpio
