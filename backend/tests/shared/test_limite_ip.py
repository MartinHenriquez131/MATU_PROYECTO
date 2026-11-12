"""MATU-25 · Reglas puras del límite por IP (decisiones 27, 29 y 114). Sin I/O."""

import hashlib
import hmac
from datetime import timedelta

import pytest

from app.modules.iam.domain import demora
from app.shared.limite_ip import (
    LIMITE_CANJE,
    LIMITE_PRESENTACION,
    LIMITE_REGISTRO,
    LIMITES,
    LimitePorIp,
    excedido,
    huella,
    retry_after,
)

PEPPER = b"pepper-sintetico-de-pruebas-0123456789abcdef"
IP = "198.51.100.23"  # TEST-NET-2 (RFC 5737), sintética


@pytest.mark.rf("RF-37")
def test_cinco_cuentas_por_hora_por_ip() -> None:
    assert (LIMITE_REGISTRO.maximo, LIMITE_REGISTRO.ventana_segundos) == (5, 3600)


@pytest.mark.rf("RF-06")
def test_canje_diez_y_presentacion_treinta_por_hora() -> None:
    assert (LIMITE_CANJE.maximo, LIMITE_CANJE.ventana_segundos) == (10, 3600)
    assert (LIMITE_PRESENTACION.maximo, LIMITE_PRESENTACION.ventana_segundos) == (30, 3600)


@pytest.mark.rf("RF-06")
@pytest.mark.rf("RF-37")
def test_cada_contador_tiene_su_prefijo_distinto_tambien_de_la_demora() -> None:
    prefijos = [limite.prefijo for limite in LIMITES] + [demora.PREFIJO_IP, demora.PREFIJO_EMAIL]
    assert len(set(prefijos)) == len(prefijos)
    assert [limite.prefijo for limite in LIMITES] == [
        "usuarios-ip", "canje-ip", "presentacion-ip", "presentacion-invitacion-ip", "canje-invitacion-ip"]


@pytest.mark.rf("RF-06")
@pytest.mark.rf("RF-37")
def test_la_misma_ip_deja_una_huella_distinta_en_cada_contador() -> None:
    huellas = {huella(PEPPER, prefijo, IP) for prefijo in [*(lim.prefijo for lim in LIMITES), demora.PREFIJO_IP]}
    assert len(huellas) == len(LIMITES) + 1
    for valor in huellas:
        assert IP not in valor
        assert len(valor) == 64 and set(valor) <= set("0123456789abcdef")


@pytest.mark.rf("RF-37")
def test_la_huella_es_hmac_sha256_con_el_prefijo_y_exige_pepper() -> None:
    esperado = hmac.new(PEPPER, f"canje-ip:{IP}".encode(), hashlib.sha256).hexdigest()
    assert huella(PEPPER, "canje-ip", IP) == esperado
    assert huella(PEPPER, "canje-ip", IP) != huella(b"otro-pepper-sintetico-0123456789abcdef", "canje-ip", IP)
    with pytest.raises(ValueError):
        huella(b"", "canje-ip", IP)
    # La demora de la entrada (MATU-38) usa la misma función
    assert demora.huella is huella


@pytest.mark.rf("RF-37")
def test_excedido_desde_la_peticion_siguiente_al_maximo() -> None:
    assert not excedido(1, LIMITE_REGISTRO)
    assert not excedido(5, LIMITE_REGISTRO)
    assert excedido(6, LIMITE_REGISTRO)
    assert excedido(500, LIMITE_REGISTRO)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(("ttl", "esperado"), [(3600, 3600), (61, 61), (1, 1), (0, 1), (-1, 1), (99999, 3600)])
def test_retry_after_entre_uno_y_la_ventana(ttl: int, esperado: int) -> None:
    assert retry_after(ttl, LIMITE_REGISTRO) == esperado


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(
    "argumentos",
    [("", 5), ("con:dos-puntos", 5), ("ok", 0), ("ok", -1)],
)
def test_un_limite_mal_declarado_no_se_crea(argumentos: tuple[str, int]) -> None:
    with pytest.raises(ValueError):
        LimitePorIp(*argumentos)
    with pytest.raises(ValueError):
        LimitePorIp("ok", 1, timedelta(0))
