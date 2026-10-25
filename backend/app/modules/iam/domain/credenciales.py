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
