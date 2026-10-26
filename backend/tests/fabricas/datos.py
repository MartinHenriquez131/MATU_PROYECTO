"""Datos sintéticos chilenos para las fábricas (estrategia de pruebas, sección 9).

Ninguno corresponde a una persona real. Los correos usan el dominio ficticio ``correo.ejemplo``,
elegido para coincidir con la demo web. No es un TLD reservado (RFC 2606 y 6761 reservan .test,
.example, .invalid y .localhost): hoy ``.ejemplo`` no existe en la raíz del DNS, pero nada garantiza
que no exista mañana. Las fábricas nunca envían correo. Las entrevistas nunca son datos de prueba:
nada de aquí sale de ellas.
"""

import random
import secrets
import unicodedata

DOMINIO_CORREO = "correo.ejemplo"

NOMBRES = ("Carmen", "Rodrigo", "Patricia", "Javiera", "Felipe", "Valentina", "Hernán", "Rosa", "Tomás", "Isidora")
APELLIDOS = ("Soto", "Muñoz", "Rojas", "Fuentes", "Riquelme", "Contreras", "Araya", "Sepúlveda", "Vergara", "Pizarro")
COMUNAS = ("La Reina", "Ñuñoa", "Maipú", "Puente Alto", "La Florida", "Providencia", "Recoleta", "Valparaíso")
CALLES = ("Los Aromos", "Los Quillayes", "Las Acacias", "Los Boldos", "Las Violetas", "El Litre")

# Un generador propio: los datos varían entre ejecuciones sin tocar el estado global de random
_azar = random.Random()


def nombre_completo() -> str:
    return f"{_azar.choice(NOMBRES)} {_azar.choice(APELLIDOS)}"


def comuna() -> str:
    return _azar.choice(COMUNAS)


def calle() -> str:
    return _azar.choice(CALLES)


def numero_calle() -> str:
    return str(_azar.randint(10, 3999))


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def email_para(nombre: str) -> str:
    """Un correo único derivado del nombre: ``carmen.soto.3f9a1c2b@correo.ejemplo``."""
    base = ".".join(_sin_tildes(nombre).lower().split()) or "familiar"
    return f"{base}.{secrets.token_hex(4)}@{DOMINIO_CORREO}"


def contrasena() -> str:
    """Una contraseña única que cumple el largo de MATU-04 (10 a 128 caracteres)."""
    return f"clave-{secrets.token_hex(8)}"
