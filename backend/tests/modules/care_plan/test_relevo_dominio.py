"""MATU-18 · Reglas puras del acceso de relevo (RF-05), sin base de datos."""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.care_plan.application.relevo import AccesoEntregado, codificar_token
from app.modules.care_plan.domain.ficha import CampoFicha
from app.modules.care_plan.domain.relevo import (
    EstadoAcceso,
    VidaAcceso,
    VigenciaInvalida,
    estado_acceso,
    nombre_pila,
    normalizar_celular,
    puede_ver_telefono,
    vigencia,
)
from app.modules.care_plan.infrastructure.credenciales_relevo import GeneradorSecrets, HuellasHmac

AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.rf("RF-05")


def test_vigencia_por_defecto_24_horas() -> None:
    assert vigencia(AHORA, None) == AHORA + timedelta(hours=24)


def test_vigencia_maxima_30_dias_en_el_dominio() -> None:
    assert vigencia(AHORA, AHORA + timedelta(days=30)) == AHORA + timedelta(days=30)
    with pytest.raises(VigenciaInvalida) as error:
        vigencia(AHORA, AHORA + timedelta(days=30, seconds=1))
    assert error.value.tipo == "vigencia_maxima"
    for pasada in (AHORA, AHORA - timedelta(seconds=1)):
        with pytest.raises(VigenciaInvalida) as error:
            vigencia(AHORA, pasada)
        assert error.value.tipo == "vigencia_pasada"


@pytest.mark.parametrize(
    "valor", ["+56 9 5555 0137", "+56955550137", "56 9 5555 0137", "9 5555 0137", "955550137"]
)
def test_celular_chileno_se_normaliza(valor: str) -> None:
    assert normalizar_celular(valor) == "+56955550137"


@pytest.mark.parametrize("valor", ["+56 2 5555 0137", "5555 0137", "+56 9 5555 013", "+1 9 5555 0137", ""])
def test_no_celular_se_rechaza(valor: str) -> None:
    assert normalizar_celular(valor) is None


def test_nombre_pila() -> None:
    assert nombre_pila("  Carmen  Soto ") == "Carmen"
    assert nombre_pila("") == ""


def test_solo_admin_y_cuidador_ven_el_telefono() -> None:
    assert puede_ver_telefono("admin") and puede_ver_telefono("cuidador")
    assert not puede_ver_telefono("pagador") and not puede_ver_telefono("observador")


def test_estado_en_el_orden_del_contrato() -> None:
    vence = AHORA + timedelta(hours=1)
    assert estado_acceso(VidaAcceso(vence, None, 0), AHORA) is EstadoAcceso.VIGENTE
    assert estado_acceso(VidaAcceso(vence, None, 5), AHORA) is EstadoAcceso.BLOQUEADO
    assert estado_acceso(VidaAcceso(AHORA, None, 5), AHORA) is EstadoAcceso.VENCIDO  # desde el instante exacto
    assert estado_acceso(VidaAcceso(AHORA, AHORA, 5), AHORA) is EstadoAcceso.REVOCADO


def test_token_de_256_bits_y_pin_de_4_digitos() -> None:
    generador = GeneradorSecrets()
    tokens = {generador.token() for _ in range(50)}
    assert len(tokens) == 50 and all(len(t) == 32 for t in tokens)
    assert all(len(codificar_token(t)) == 43 for t in tokens)
    pines = [generador.pin() for _ in range(200)]
    assert all(len(p) == 4 and p.isdigit() for p in pines)


def test_huellas_token_sha256_y_pin_hmac_ligado_al_acceso() -> None:
    pepper = b"p" * 32
    huellas = HuellasHmac(pepper)
    token = b"\x01" * 32
    assert huellas.huella_token(token) == hashlib.sha256(token).digest()
    a, b = uuid.uuid4(), uuid.uuid4()
    esperado = hmac.new(pepper, f"{a}:4821".encode(), hashlib.sha256).hexdigest()
    assert huellas.huella_pin(a, "4821") == esperado
    assert huellas.huella_pin(a, "4821") != huellas.huella_pin(b, "4821")
    assert huellas.huella_pin(a, "4821") != HuellasHmac(b"q" * 32).huella_pin(a, "4821")
    assert "p" * 32 not in repr(huellas)


def test_token_y_pin_nunca_en_el_repr() -> None:
    entregado = AccesoEntregado(
        id=uuid.uuid4(), token="TokenSinteticoDePrueba", pin="4821", campos=(CampoFicha.RUTINA,),
        expira_en=AHORA, nombre_relevo="Rosa", nombre_pila_persona="María",
    )
    assert "TokenSinteticoDePrueba" not in repr(entregado)
    assert "4821" not in repr(entregado)
