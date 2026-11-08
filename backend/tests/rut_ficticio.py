"""RUT ficticios para las pruebas: siempre con un dígito verificador que no pasa el módulo 11.

Así un RUT de prueba nunca puede ser el de una persona o una empresa real, en ninguna corrida.
"""

DIGITOS_VERIFICADORES = "0123456789K"


def modulo_11(numero: str) -> str:
    """El dígito verificador correcto del número (sin puntos ni guion): 0 a 9 o K."""
    suma, factor = 0, 2
    for digito in reversed(numero):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: "0", 10: "K"}.get(resto, str(resto))


def dv_invalido(numero: str) -> str:
    """Un dígito verificador que nunca es el correcto: el siguiente al del módulo 11, dando la vuelta tras K."""
    correcto = DIGITOS_VERIFICADORES.index(modulo_11(numero))
    return DIGITOS_VERIFICADORES[(correcto + 1) % len(DIGITOS_VERIFICADORES)]


def rut_ficticio(numero: str) -> str:
    """El RUT con puntos y guion (``77.123.456-X``), con un dígito verificador inválido a propósito."""
    cuerpo = f"{int(numero):,}".replace(",", ".")
    return f"{cuerpo}-{dv_invalido(numero)}"
