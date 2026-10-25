"""Reglas puras del grupo familiar (MATU-06, RF-38).

Sin I/O: el nombre se valida aquí y la persistencia es un puerto (application/ports.py).
"""

LARGO_MINIMO_NOMBRE = 1
LARGO_MAXIMO_NOMBRE = 80

# Quien crea un grupo queda como admin de él, en la misma transacción
ROL_FUNDADOR = "admin"


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
