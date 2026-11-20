"""MATU-81 · El segundo factor sin base: RFC 4226 y RFC 6238 con sus vectores, la ventana de ±1, la URI del alta, el
cifrado del secreto con su AAD y las reglas de la sesión de 12 horas (C26, C29 a C31)."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.iam.application.ports import SecretoMfaInvalido
from app.modules.iam.domain import mfa
from app.modules.iam.infrastructure.cifrador_mfa import CifradorMfaKek

pytestmark = [pytest.mark.rf("RF-37"), pytest.mark.rf("Ley-21.719")]

SECRETO_RFC = b"12345678901234567890"


@pytest.mark.parametrize(
    ("contador", "codigo"),
    list(
        enumerate(["755224", "287082", "359152", "969429", "338314", "254676", "287922", "162583", "399871", "520489"])
    ),
)
def test_hotp_con_los_vectores_del_rfc_4226(contador: int, codigo: str) -> None:
    assert mfa.hotp(SECRETO_RFC, contador) == codigo


@pytest.mark.parametrize(
    ("segundos", "codigo"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_totp_con_los_vectores_sha1_del_rfc_6238(segundos: int, codigo: str) -> None:
    assert mfa.totp(SECRETO_RFC, datetime.fromtimestamp(segundos, UTC), cifras=8) == codigo


def test_la_ventana_es_de_un_paso_a_cada_lado() -> None:
    ahora = datetime(2026, 11, 17, 12, 0, 15, tzinfo=UTC)
    secreto = secrets.token_bytes(mfa.BYTES_SECRETO)
    paso = mfa.paso_de(ahora)
    for desfase in (-1, 0, 1):
        assert mfa.paso_que_coincide(secreto, mfa.hotp(secreto, paso + desfase), ahora) == paso + desfase
    for desfase in (-2, 2):
        codigo = mfa.hotp(secreto, paso + desfase)
        if all(codigo != mfa.hotp(secreto, paso + x) for x in (-1, 0, 1)):
            assert mfa.paso_que_coincide(secreto, codigo, ahora) is None
    assert mfa.paso_que_coincide(secreto, "12345", ahora) is None
    assert mfa.paso_que_coincide(secreto, "abcdef", ahora) is None


def test_el_paso_exige_zona_horaria() -> None:
    with pytest.raises(ValueError):
        mfa.paso_de(datetime(2026, 11, 17, 12, 0))  # noqa: DTZ001


def test_la_uri_del_alta_no_lleva_el_correo_y_el_secreto_va_en_base32() -> None:
    secreto = bytes(range(20))
    uri = mfa.uri_otpauth(secreto)
    assert uri.startswith("otpauth://totp/MATU%3Aoperacion?secret=")
    assert f"secret={mfa.secreto_en_base32(secreto)}&issuer=MATU" in uri
    assert "digits=6" in uri and "period=30" in uri and "@" not in uri
    assert "=" not in mfa.secreto_en_base32(secreto)


def test_la_sesion_de_operacion_vale_12_horas_desde_el_segundo_factor() -> None:
    mfa_en = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
    assert mfa.sesion_vigente(mfa_en, mfa_en + timedelta(hours=11, minutes=59))
    assert not mfa.sesion_vigente(mfa_en, mfa_en + timedelta(hours=12))
    assert not mfa.sesion_vigente(None, mfa_en)


def test_los_fallos_se_agotan_al_quinto() -> None:
    assert mfa.FallosMfa(4, 10).restantes == 1 and not mfa.FallosMfa(4, 10).agotados
    assert mfa.FallosMfa(5, 10).agotados and mfa.FallosMfa(5, 10).restantes == 0


def test_el_desafio_se_guarda_solo_como_huella() -> None:
    desafio = secrets.token_urlsafe(mfa.BYTES_DESAFIO)
    assert mfa.tiene_forma_de_desafio(desafio)
    assert desafio not in mfa.huella_desafio(desafio) and len(mfa.huella_desafio(desafio)) == 64


def test_el_secreto_se_cifra_con_la_kek_y_el_aad_de_la_cuenta() -> None:
    cifrador = CifradorMfaKek(secrets.token_bytes(32), 1)
    cuenta, otra = uuid.uuid4(), uuid.uuid4()
    secreto = secrets.token_bytes(20)
    cifrado = cifrador.cifrar(secreto, cuenta)
    assert secreto not in cifrado and len(cifrado) == 1 + 12 + 20 + 16
    assert cifrador.descifrar(cifrado, cuenta) == secreto
    # Copiado a otra cuenta, o con otra KEK, no se descifra
    with pytest.raises(SecretoMfaInvalido):
        cifrador.descifrar(cifrado, otra)
    with pytest.raises(SecretoMfaInvalido):
        CifradorMfaKek(secrets.token_bytes(32), 1).descifrar(cifrado, cuenta)
    with pytest.raises(SecretoMfaInvalido):
        CifradorMfaKek(secrets.token_bytes(32), 2).descifrar(cifrado, cuenta)
    assert repr(cifrador) == "CifradorMfaKek(kek_version=1)"
