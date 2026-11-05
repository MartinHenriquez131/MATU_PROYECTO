"""MATU-57 · Reglas puras de la recuperación del acceso y del celular (RF-37, decisiones 81 a 88).

No hay un RF propio de recuperar el acceso en el backlog: se traza a RF-37 (registro y autenticación).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.iam.domain.recuperacion import (
    MAX_INTENTOS,
    MENSAJE_AVISO,
    VIGENCIA_CODIGO,
    Canal,
    EnviosRecientes,
    Proposito,
    canal_del_aviso,
    canal_del_codigo,
    clave_codigo,
    codigo_nuevo,
    codigo_sirve,
    enmascarar_celular,
    es_codigo,
    espera_destino,
    espera_ip,
    huella_codigo,
    mensaje_codigo,
)

pytestmark = pytest.mark.rf("RF-37")

AHORA = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
PEPPER = b"r" * 32


def test_mensaje_exacto_sin_nombres_ni_enlaces() -> None:
    assert mensaje_codigo("123456") == (
        "MATU: tu código es 123456. Vence en 10 minutos. No lo compartas con nadie;"
        " MATU nunca te lo pedirá por teléfono."
    )
    assert "http" not in mensaje_codigo("000000")


def test_aviso_del_cambio_con_el_texto_de_jorge() -> None:
    # Decisión 88, texto aprobado por Jorge el 03-11: sin «sesiones», sin nombres ni enlaces
    assert MENSAJE_AVISO == (
        "MATU: se cambió la contraseña de tu cuenta. Si no fuiste tú, pide un código para recuperar tu acceso."
    )


@pytest.mark.parametrize("valor", ["12345", "1234567", "12a456", "１２３４５６", " 12345"])
def test_codigo_mal_formado(valor: str) -> None:
    assert not es_codigo(valor)
    with pytest.raises(ValueError):
        mensaje_codigo(valor)


def test_la_huella_depende_del_usuario_y_del_proposito() -> None:
    a = clave_codigo(PEPPER, Proposito.RECUPERAR, "u1")
    assert a != clave_codigo(PEPPER, Proposito.RECUPERAR, "u2")
    assert a != clave_codigo(PEPPER, Proposito.CELULAR, "u1")
    assert huella_codigo(PEPPER, a, "123456") != huella_codigo(PEPPER, "otra", "123456")
    assert "123456" not in huella_codigo(PEPPER, a, "123456")
    assert len(huella_codigo(PEPPER, a, "123456")) == 64


def test_codigo_sirve_solo_vigente_con_intentos_y_huella() -> None:
    guardado = codigo_nuevo("h", Canal.CORREO, AHORA)
    assert guardado.expira_en == AHORA + VIGENCIA_CODIGO == AHORA + timedelta(minutes=10)
    assert codigo_sirve(guardado, "h", 1, AHORA)
    assert codigo_sirve(guardado, "h", MAX_INTENTOS, AHORA)
    assert not codigo_sirve(guardado, "h", MAX_INTENTOS + 1, AHORA)
    assert not codigo_sirve(guardado, "otra", 1, AHORA)
    assert not codigo_sirve(guardado, "h", 1, AHORA + VIGENCIA_CODIGO)
    assert not codigo_sirve(None, "h", 0, AHORA)


def test_el_codigo_va_al_celular_solo_si_esta_verificado() -> None:
    assert canal_del_codigo(celular_verificado=True, solo_correo=False) is Canal.SMS
    assert canal_del_codigo(celular_verificado=False, solo_correo=False) is Canal.CORREO
    assert canal_del_codigo(celular_verificado=True, solo_correo=True) is Canal.CORREO


def test_el_aviso_va_por_el_otro_canal() -> None:
    assert canal_del_aviso(Canal.SMS, True) is Canal.CORREO
    assert canal_del_aviso(Canal.CORREO, True) is Canal.SMS
    assert canal_del_aviso(Canal.CORREO, False) is Canal.CORREO


def test_espera_60_segundos_entre_envios() -> None:
    envios = EnviosRecientes(AHORA, 1, AHORA, 1, AHORA)
    assert espera_destino(envios, AHORA + timedelta(seconds=10)) == 50
    assert espera_destino(envios, AHORA + timedelta(seconds=60)) == 0


def test_tres_por_hora_y_diez_al_dia() -> None:
    tres = EnviosRecientes(AHORA + timedelta(minutes=20), 3, AHORA, 3, AHORA)
    assert espera_destino(tres, AHORA + timedelta(minutes=30)) == 30 * 60
    diez = EnviosRecientes(AHORA + timedelta(hours=5), 1, AHORA + timedelta(hours=5), 10, AHORA)
    assert espera_destino(diez, AHORA + timedelta(hours=6)) == 18 * 3600


def test_la_ip_no_tiene_los_60_segundos_pero_si_su_tope() -> None:
    assert espera_ip(EnviosRecientes(AHORA, 1, AHORA, 1, AHORA), AHORA) == 0
    assert espera_ip(EnviosRecientes(AHORA, 20, AHORA, 20, AHORA), AHORA) == 3600


def test_celular_enmascarado() -> None:
    assert enmascarar_celular("+56912345637") == "+56 9 •••• ••37"
    assert enmascarar_celular(None) is None
    assert enmascarar_celular("123") is None


def test_sin_zona_horaria_falla() -> None:
    with pytest.raises(ValueError):
        codigo_nuevo("h", Canal.SMS, datetime(2026, 11, 3))  # noqa: DTZ001
    with pytest.raises(ValueError):
        espera_destino(EnviosRecientes(), datetime(2026, 11, 3))  # noqa: DTZ001
