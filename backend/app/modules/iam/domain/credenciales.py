"""Reglas puras de las credenciales de una cuenta (MATU-04, RF-37).

Sin I/O ni dependencias externas: el hash de la contraseña con Argon2id es un puerto
(application/ports.py), porque necesita una librería fuera de la biblioteca estándar.
"""

import hashlib
import hmac

LARGO_MINIMO_CONTRASENA = 10
# Tope para que un cuerpo enorme no convierta el hash de Argon2id en una forma de saturar la API
LARGO_MAXIMO_CONTRASENA = 128
LARGO_MAXIMO_EMAIL = 254


class EmailYaRegistrado(Exception):
    """Ya existe una cuenta con ese email. Nunca lleva el email en su mensaje."""


class DominioNoPermitido(Exception):
    """El email no es de un dominio reservado y el entorno solo admite esos (decisión 105). Nunca lleva
    el email en su mensaje."""


# Dominios reservados para documentación y pruebas (RFC 2606 y RFC 6761): nunca son el correo de una
# persona real. Se admiten ellos y cualquier subdominio suyo
DOMINIOS_RESERVADOS = frozenset({"example.com", "example.org", "example.net"})
# Nombres de primer nivel reservados (RFC 2606 y RFC 6761): todo lo que termina en ellos
TLD_RESERVADOS = frozenset({"test", "example", "invalid", "localhost"})


def es_dominio_reservado(email: str) -> bool:
    """True si el email es de un dominio reservado: example.com, example.org, example.net o un
    subdominio de ellos, o un dominio terminado en .test, .example, .invalid o .localhost.

    Se compara el email normalizado (sin espacios en los extremos y en minúsculas). Un dominio con una
    etiqueta vacía (``a@.example.com``, ``a@example..com``) o con un punto final no es reservado.
    """
    _, arroba, dominio = normalizar_email(email).rpartition("@")
    if not arroba or not dominio:
        return False
    etiquetas = dominio.split(".")
    if any(not etiqueta for etiqueta in etiquetas):
        return False
    if etiquetas[-1] in TLD_RESERVADOS:
        return True
    return any(dominio == d or dominio.endswith("." + d) for d in DOMINIOS_RESERVADOS)


def normalizar_email(email: str) -> str:
    """El email se guarda y se compara sin espacios en los extremos y en minúsculas."""
    return email.strip().lower()


def indice_email(pepper: bytes, email_normalizado: str) -> bytes:
    """HMAC-SHA256(pepper, email normalizado), la llave de indice_credencial.

    Resuelve email → usuario en el login sin guardar el email en una tabla sin RLS. Sin el
    pepper, que vive fuera de la base, el hash no se revierte con un diccionario de emails.
    """
    if not pepper:
        raise ValueError("El pepper no puede estar vacío")
    return hmac.new(pepper, email_normalizado.encode("utf-8"), hashlib.sha256).digest()
