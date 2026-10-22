"""MATU-04 · Reglas puras de las credenciales y adaptador de Argon2id, sin base."""

import hashlib
import hmac

import pytest

from app.modules.iam.domain.credenciales import indice_email, normalizar_email
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id

PEPPER = b"p" * 32


@pytest.mark.rf("RF-37")
def test_email_se_normaliza_a_minusculas_sin_espacios() -> None:
    assert normalizar_email("  Familiar.Uno@Ejemplo.CL ") == "familiar.uno@ejemplo.cl"


@pytest.mark.rf("RF-37")
def test_indice_email_es_hmac_sha256_de_32_bytes() -> None:
    indice = indice_email(PEPPER, "familiar.uno@ejemplo.cl")

    assert indice == hmac.new(PEPPER, b"familiar.uno@ejemplo.cl", hashlib.sha256).digest()
    assert len(indice) == 32


@pytest.mark.rf("RF-37")
def test_indice_email_depende_del_pepper() -> None:
    # Sin el pepper no se reconstruye el índice con un diccionario de emails
    email = "familiar.uno@ejemplo.cl"

    assert indice_email(PEPPER, email) != indice_email(b"q" * 32, email)
    assert indice_email(PEPPER, email) != hashlib.sha256(email.encode()).digest()


def test_indice_email_sin_pepper_falla() -> None:
    with pytest.raises(ValueError):
        indice_email(b"", "familiar.uno@ejemplo.cl")


@pytest.mark.rf("RF-37")
def test_hasher_usa_argon2id_y_verifica() -> None:
    hasher = HasherArgon2id()

    hash_guardado = hasher.hashear("una-clave-sintetica")

    assert hash_guardado.startswith("$argon2id$")
    assert "una-clave-sintetica" not in hash_guardado
    assert hasher.verificar(hash_guardado, "una-clave-sintetica")
    assert not hasher.verificar(hash_guardado, "otra-clave-sintetica")
    assert not hasher.verificar("no-es-un-hash", "una-clave-sintetica")


def test_dos_hashes_de_la_misma_contrasena_difieren() -> None:
    # Cada hash lleva su propia sal
    hasher = HasherArgon2id()

    assert hasher.hashear("una-clave-sintetica") != hasher.hashear("una-clave-sintetica")
