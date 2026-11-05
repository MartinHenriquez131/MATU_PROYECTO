"""Buscar un número en un texto sin que el azar haga fallar la prueba.

Las filas de auditoría, los logs y los repr traen UUID, hashes hexadecimales, request_id y fechas que
cambian en cada ejecución. Buscar un PIN o un teléfono como subcadena («5555» in fila) falla de vez en
cuando: un UUID como ``…-45555-…`` o un hash como ``a35555f`` lo contiene por azar. Estas funciones
buscan el número como dato completo, con los límites del commit ac8a315 (PR #48): sin letras,
dígitos, ``_`` ni ``-`` a los lados, ni un punto que lo una a otro número (``5555.0``, ``0.5555``). A
diferencia de ac8a315, un punto final de frase sí cuenta («su PIN es 4821.»).

- Un grupo de un UUID siempre queda entre ``-`` o dígitos hexadecimales, y ``\\w`` cubre las letras
  a-f: nunca cuenta.
- Un hash hexadecimal es una sola palabra de ``\\w``: un número en su interior nunca cuenta.
- Una fecha o una duración quedan entre ``-`` o un punto pegado a dígitos (``2026-11-05``, ``4321.0``):
  no cuentan.
- Sí cuenta como valor JSON (``"pin": "4821"``, ``"n": 4821``), tras ``=``, entre espacios o comillas y
  antes de un punto final.
"""

import re

_BORDE_IZQUIERDO = r"(?<![\w-])(?<!\d\.)"
_BORDE_DERECHO = r"(?![\w-])(?!\.\d)"


def aparece_como_dato(valor: str, texto: str) -> bool:
    """True si valor aparece completo en texto, no como parte de otra palabra, número, UUID o hash."""
    return re.search(f"{_BORDE_IZQUIERDO}{re.escape(valor)}{_BORDE_DERECHO}", texto) is not None


def aparece_celular(celular: str, texto: str) -> bool:
    """True si el celular chileno aparece en texto, escrito de cualquiera de sus formas.

    Cuenta «+56 9 5555 0137», «+56955550137» (la forma normalizada que guarda MATU), «56 9 5555 0137»,
    «9 5555 0137», «955550137» y el número sin el 9 («5555 0137», «55550137»). Buscar solo «5555» con
    aparece_como_dato no alcanzaría: en la forma normalizada los cuatro dígitos quedan pegados a otros, y
    la prueba dejaría de ver el teléfono.
    """
    digitos = re.sub(r"\D", "", celular)[-9:]
    if len(digitos) != 9:
        raise ValueError("Se espera un celular chileno de 9 dígitos, con o sin +56")
    patron = rf"(?:(?:\+?56 ?)?{digitos[0]} ?)?{digitos[1:5]} ?{digitos[5:]}"
    return re.search(f"{_BORDE_IZQUIERDO}{patron}{_BORDE_DERECHO}", texto) is not None
