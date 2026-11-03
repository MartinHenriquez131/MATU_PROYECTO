"""El celular chileno: forma admitida y normalización a E.164 (+569XXXXXXXX).

Lo usan el teléfono del relevo (care_plan, MATU-18) y el celular de la cuenta (iam, MATU-39).
Regla pura, sin I/O. Ningún error que la use repite el valor recibido.
"""

import re

# 9 y ocho dígitos, con o sin +56 / 56 y con o sin espacios
PATRON_CELULAR = r"^(\+?56 ?)?9( ?[0-9]){8}$"
_CELULAR = re.compile(PATRON_CELULAR)


def normalizar_celular(valor: str) -> str | None:
    """El celular chileno como +569XXXXXXXX, o None si no es un celular (fijos incluidos)."""
    if not _CELULAR.match(valor):
        return None
    digitos = re.sub(r"\D", "", valor)
    return "+56" + digitos[-9:]
