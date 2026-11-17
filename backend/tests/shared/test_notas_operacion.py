"""MATU-81 · Las notas de operación cifradas (opción B de Jorge del 17-11, decisión 471), sin base: el largo de 1 a 500
caracteres sobre el texto, AES-256-GCM con el AAD de la incidencia y el campo, la clave envuelta con la KEK, y que
nada sensible salga en un repr o en un error."""

import secrets
import uuid

import pytest
from pydantic import SecretStr

from app.shared.notas_operacion import (
    LARGO_MAXIMO_NOTA,
    CustodiaNotas,
    NotaInvalida,
    NotasNoDisponibles,
    aad_nota,
    cifrar_nota,
    custodia_notas_de,
    descifrar_nota,
    validar_nota,
)

pytestmark = [pytest.mark.rf("RF-40"), pytest.mark.rf("Ley-21.719")]

# El CHECK incidencia_descripcion_cifrada de la 0030: nonce (12) + etiqueta (16) + de 1 a 2000 bytes
CIFRADO_MIN = 12 + 16 + 1
CIFRADO_MAX = 12 + 16 + 4 * 500


@pytest.fixture
def dek() -> bytes:
    return secrets.token_bytes(32)


@pytest.mark.parametrize("texto", ["x", "Faltó un paquete de pañales; se devolvió su monto", "x" * LARGO_MAXIMO_NOTA])
def test_la_nota_se_cifra_y_se_descifra_con_su_incidencia_y_su_campo(dek: bytes, texto: str) -> None:
    incidencia = uuid.uuid4()
    cifrado = cifrar_nota(dek, incidencia, "descripcion", texto)
    assert texto.encode("utf-8") not in cifrado
    assert CIFRADO_MIN <= len(cifrado) <= CIFRADO_MAX
    assert descifrar_nota(dek, incidencia, "descripcion", cifrado) == texto


def test_el_nonce_cambia_en_cada_cifrado(dek: bytes) -> None:
    incidencia = uuid.uuid4()
    assert cifrar_nota(dek, incidencia, "descripcion", "igual") != cifrar_nota(dek, incidencia, "descripcion", "igual")


def test_500_caracteres_de_4_bytes_caben_en_el_check_de_la_base(dek: bytes) -> None:
    cifrado = cifrar_nota(dek, uuid.uuid4(), "resolucion", "😀" * LARGO_MAXIMO_NOTA)
    assert len(cifrado) == CIFRADO_MAX


@pytest.mark.parametrize("texto", ["", "x" * (LARGO_MAXIMO_NOTA + 1)])
def test_el_largo_se_valida_sobre_el_texto_antes_de_cifrar(dek: bytes, texto: str) -> None:
    with pytest.raises(NotaInvalida) as error:
        cifrar_nota(dek, uuid.uuid4(), "descripcion", texto)
    # El mensaje es fijo: nunca lleva el texto
    assert str(error.value) == "la nota debe tener de 1 a 500 caracteres"
    with pytest.raises(NotaInvalida):
        validar_nota(texto)
    assert validar_nota("x" * LARGO_MAXIMO_NOTA) == "x" * LARGO_MAXIMO_NOTA


def test_moverla_a_otra_incidencia_o_al_otro_campo_no_se_descifra(dek: bytes) -> None:
    incidencia = uuid.uuid4()
    cifrado = cifrar_nota(dek, incidencia, "descripcion", "Nota sintética")
    assert descifrar_nota(dek, uuid.uuid4(), "descripcion", cifrado) is None
    assert descifrar_nota(dek, incidencia, "resolucion", cifrado) is None
    assert aad_nota(incidencia, "descripcion") == f"incidencia:{incidencia}:descripcion".encode()


def test_sin_clave_otra_clave_o_alterada_la_nota_no_esta_disponible_sin_error(dek: bytes) -> None:
    incidencia = uuid.uuid4()
    cifrado = cifrar_nota(dek, incidencia, "descripcion", "Nota sintética")
    # La clave destruida (None), otra clave, un byte cambiado o algo corto: None, nunca una excepción
    assert descifrar_nota(None, incidencia, "descripcion", cifrado) is None
    assert descifrar_nota(secrets.token_bytes(32), incidencia, "descripcion", cifrado) is None
    alterado = cifrado[:-1] + bytes([cifrado[-1] ^ 1])
    assert descifrar_nota(dek, incidencia, "descripcion", alterado) is None
    assert descifrar_nota(dek, incidencia, "descripcion", b"\x00" * 10) is None
    assert descifrar_nota(dek, incidencia, "descripcion", None) is None


def test_la_custodia_envuelve_la_clave_con_la_kek_y_no_la_muestra() -> None:
    kek = secrets.token_bytes(32)
    custodia = CustodiaNotas(kek, 1)
    dek, envuelta = custodia.nueva_dek()
    # AES Key Wrap: 40 bytes, como clave_datos (CHECK clave_notas_dek_largo)
    assert len(dek) == 32 and len(envuelta) == 40 and dek not in envuelta
    assert custodia.desenvolver(envuelta, 1) == dek
    # Otra versión u otra KEK: None, nunca una clave de reemplazo
    assert custodia.desenvolver(envuelta, 2) is None
    assert CustodiaNotas(secrets.token_bytes(32), 1).desenvolver(envuelta, 1) is None
    assert repr(custodia) == "CustodiaNotas(kek_version=1)" and kek.hex() not in repr(custodia)
    with pytest.raises(NotasNoDisponibles):
        CustodiaNotas(b"corta", 1)


def test_sin_custodia_encendida_no_hay_custodia_de_notas() -> None:
    from app.core.config import Configuracion

    apagada = Configuracion.model_construct(custodia_kek=None, kek_entorno=None, kek_version=1)
    assert custodia_notas_de(apagada) is None
    import base64

    encendida = Configuracion.model_construct(
        custodia_kek="entorno_sintetico", kek_entorno=SecretStr(base64.b64encode(secrets.token_bytes(32)).decode()),
        kek_version=1,
    )
    assert isinstance(custodia_notas_de(encendida), CustodiaNotas)
