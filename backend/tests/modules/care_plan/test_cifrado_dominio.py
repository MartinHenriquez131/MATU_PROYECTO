"""MATU-11 · Reglas puras del cifrado de secciones: estados de la clave, AAD y forma de la sección.

Trazan a ADR-014 y ADR-016 (no hay un RF): sin marca rf.
"""

import uuid

import pytest

from app.modules.care_plan.domain.cifrado import (
    LARGO_NONCE,
    LARGO_TAG,
    TIPOS_SECCION,
    ClaveDestruida,
    ClaveGuardada,
    ClaveInexistente,
    ErrorCifrado,
    EstadoClave,
    SeccionCifrada,
    SeccionIlegible,
    TipoSeccionInvalido,
    clave_para_escribir,
    clave_para_leer,
    datos_asociados,
    estado_clave,
)

PLAN = uuid.UUID("00000000-0000-0000-0000-0000000011a0")
VIGENTE = ClaveGuardada(kek_version=1, dek_cifrada=b"\x01" * 48)
DESTRUIDA = ClaveGuardada(kek_version=1, dek_cifrada=None)


def test_no_existe_vigente_y_destruida_son_estados_distintos() -> None:
    assert estado_clave(None) is EstadoClave.NO_EXISTE
    assert estado_clave(VIGENTE) is EstadoClave.VIGENTE
    assert estado_clave(DESTRUIDA) is EstadoClave.DESTRUIDA


def test_escribir_sin_clave_pide_crearla_y_con_clave_vigente_la_usa() -> None:
    assert clave_para_escribir(None) is None
    assert clave_para_escribir(VIGENTE) is VIGENTE


def test_escribir_con_clave_destruida_es_error_de_dominio_y_no_pide_crear_otra() -> None:
    with pytest.raises(ClaveDestruida):
        clave_para_escribir(DESTRUIDA)


def test_leer_distingue_sin_clave_de_clave_destruida() -> None:
    assert clave_para_leer(VIGENTE) is VIGENTE
    with pytest.raises(ClaveInexistente):
        clave_para_leer(None)
    with pytest.raises(ClaveDestruida):
        clave_para_leer(DESTRUIDA)


def test_aad_es_el_plan_en_16_bytes_seguido_del_tipo_en_utf8() -> None:
    aad = datos_asociados(PLAN, "red_apoyo")

    assert aad == PLAN.bytes + b"red_apoyo"
    assert aad[:16] == PLAN.bytes


def test_aad_distinto_por_tipo_y_por_plan() -> None:
    otro_plan = uuid.UUID("00000000-0000-0000-0000-0000000011b0")
    todos = {datos_asociados(p, t) for p in (PLAN, otro_plan) for t in TIPOS_SECCION}

    assert len(todos) == 2 * len(TIPOS_SECCION)


def test_tipo_desconocido_rechazado() -> None:
    with pytest.raises(TipoSeccionInvalido):
        datos_asociados(PLAN, "notas_libres")


def test_tipos_de_la_ficha_de_relevo_admitidos() -> None:
    assert {"rutina", "manejo_situaciones", "red_apoyo"} <= TIPOS_SECCION


@pytest.mark.parametrize(("nonce", "tag"), [(b"\x00" * 11, b"\x00" * LARGO_TAG), (b"\x00" * LARGO_NONCE, b"\x00" * 15)])
def test_seccion_con_nonce_o_tag_de_largo_invalido_es_ilegible(nonce: bytes, tag: bytes) -> None:
    with pytest.raises(SeccionIlegible):
        SeccionCifrada(contenido_cifrado=b"\xaa", nonce=nonce, tag_auth=tag, kek_version=1)


def test_repr_de_la_clave_no_muestra_la_dek_envuelta() -> None:
    dek_envuelta = bytes(range(48))

    texto = repr(ClaveGuardada(kek_version=3, dek_cifrada=dek_envuelta))

    assert dek_envuelta.hex() not in texto and repr(dek_envuelta) not in texto
    assert "kek_version=3" in texto


@pytest.mark.parametrize("error", ErrorCifrado.__subclasses__())
def test_errores_con_mensaje_fijo_sin_argumentos(error: type[ErrorCifrado]) -> None:
    instancia = error()

    assert str(instancia) == error.mensaje
    assert instancia.args == (error.mensaje,)
