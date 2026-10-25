"""MATU-07 · Reglas puras del alta de la persona cuidada y su consentimiento (RF-01, Ley 21.719).

Sin base ni API: reglas cruzadas por calidad, evidencia mínima, revisión a 12 meses con el borde
del 29 de febrero, aviso canónico con su huella y vista por rol.
"""

import hashlib
import unicodedata
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.modules.care_circle.domain.avisos import AVISO_CUIDADOR_DE_HECHO, Aviso
from app.modules.care_circle.domain.personas import (
    MODALIDAD_TITULAR,
    AvisoMostrado,
    CalidadOtorgante,
    OtorgamientoInvalido,
    VistaPersona,
    aviso_de,
    evidencia,
    puede_dar_de_alta,
    revision_vence_en,
    sumar_meses,
    validar_otorgamiento,
    vista_para_rol,
)

TITULAR = CalidadOtorgante.TITULAR
REPRESENTANTE = CalidadOtorgante.REPRESENTANTE_LEGAL
CUIDADOR = CalidadOtorgante.CUIDADOR_DE_HECHO
AVISO_VIGENTE = AvisoMostrado(id="aviso_cuidador_de_hecho", version="1.0")
REFERENCIA = "Resolución sintética 123-2026"


# --- Reglas cruzadas por calidad -------------------------------------------------------------


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("calidad", "referencia", "aviso"),
    [(TITULAR, None, None), (REPRESENTANTE, REFERENCIA, None), (CUIDADOR, None, AVISO_VIGENTE)],
    ids=["titular", "representante", "cuidador"],
)
def test_combinaciones_validas(calidad: CalidadOtorgante, referencia: str | None, aviso: AvisoMostrado | None) -> None:
    validar_otorgamiento(calidad, referencia, aviso)


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("calidad", "referencia", "aviso", "campo"),
    [
        (TITULAR, REFERENCIA, None, "referencia_documento"),
        (TITULAR, None, AVISO_VIGENTE, "aviso"),
        (REPRESENTANTE, None, None, "referencia_documento"),
        (REPRESENTANTE, "", None, "referencia_documento"),
        (REPRESENTANTE, REFERENCIA, AVISO_VIGENTE, "aviso"),
        (CUIDADOR, None, None, "aviso"),
        (CUIDADOR, REFERENCIA, AVISO_VIGENTE, "referencia_documento"),
        (CUIDADOR, None, AvisoMostrado(id="aviso_cuidador_de_hecho", version="0.9"), "aviso"),
        (CUIDADOR, None, AvisoMostrado(id="otro_aviso", version="1.0"), "aviso"),
    ],
    ids=[
        "titular-con-referencia",
        "titular-con-aviso",
        "representante-sin-referencia",
        "representante-referencia-vacia",
        "representante-con-aviso",
        "cuidador-sin-aviso",
        "cuidador-con-referencia",
        "cuidador-aviso-version-antigua",
        "cuidador-aviso-otro-id",
    ],
)
def test_combinaciones_invalidas(
    calidad: CalidadOtorgante, referencia: str | None, aviso: AvisoMostrado | None, campo: str
) -> None:
    with pytest.raises(OtorgamientoInvalido) as error:
        validar_otorgamiento(calidad, referencia, aviso)

    assert error.value.campo == campo
    # El mensaje nunca lleva el valor recibido
    assert REFERENCIA not in str(error.value)


# --- Evidencia mínima ------------------------------------------------------------------------


@pytest.mark.rf("RF-01")
def test_evidencia_del_titular_registra_la_modalidad() -> None:
    assert evidencia(TITULAR, "0.9") == {
        "esquema": 1,
        "declaracion": {"id": "declaracion_titular", "version": "0.9"},
        "modalidad": MODALIDAD_TITULAR,
    }


@pytest.mark.rf("RF-01")
def test_evidencia_del_representante_solo_cita_la_declaracion() -> None:
    assert evidencia(REPRESENTANTE, "0.9") == {
        "esquema": 1,
        "declaracion": {"id": "declaracion_representante_legal", "version": "0.9"},
    }


@pytest.mark.rf("RF-01")
def test_evidencia_del_cuidador_de_hecho_cita_el_aviso_mostrado() -> None:
    assert evidencia(CUIDADOR, "0.9") == {
        "esquema": 1,
        "declaracion": {"id": "declaracion_cuidador_de_hecho", "version": "0.9"},
        "aviso": {"id": "aviso_cuidador_de_hecho", "version": "1.0", "sha256": AVISO_CUIDADOR_DE_HECHO.sha256},
    }


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("calidad", list(CalidadOtorgante))
def test_evidencia_sin_ip_agente_ni_texto(calidad: CalidadOtorgante) -> None:
    texto = repr(evidencia(calidad, "0.9")).lower()

    for prohibido in ("ip", "agente", "user_agent", "titulo", "parrafos", "texto"):
        assert f"'{prohibido}'" not in texto
    assert AVISO_CUIDADOR_DE_HECHO.titulo not in texto


# --- Revisión a 12 meses ---------------------------------------------------------------------


@pytest.mark.rf("RF-01")
def test_revision_del_cuidador_de_hecho_es_doce_meses_de_calendario() -> None:
    otorgado = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

    assert revision_vence_en(CUIDADOR, otorgado) == datetime(2027, 10, 20, 12, 0, tzinfo=UTC)


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize("calidad", [TITULAR, REPRESENTANTE])
def test_otras_calidades_sin_revision(calidad: CalidadOtorgante) -> None:
    assert revision_vence_en(calidad, datetime(2026, 10, 20, tzinfo=UTC)) is None


@pytest.mark.rf("RF-01")
def test_revision_desde_29_de_febrero_cae_el_28() -> None:
    otorgado = datetime(2028, 2, 29, 9, 30, tzinfo=UTC)

    assert revision_vence_en(CUIDADOR, otorgado) == datetime(2029, 2, 28, 9, 30, tzinfo=UTC)


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("inicio", "meses", "esperado"),
    [
        (datetime(2026, 1, 31, tzinfo=UTC), 1, datetime(2026, 2, 28, tzinfo=UTC)),
        (datetime(2027, 1, 31, tzinfo=UTC), 13, datetime(2028, 2, 29, tzinfo=UTC)),
        (datetime(2026, 12, 15, tzinfo=UTC), 12, datetime(2027, 12, 15, tzinfo=UTC)),
        (datetime(2026, 11, 30, tzinfo=UTC), 3, datetime(2027, 2, 28, tzinfo=UTC)),
        (datetime(2026, 3, 31, tzinfo=UTC), 1, datetime(2026, 4, 30, tzinfo=UTC)),
    ],
    ids=["31-ene-a-feb", "a-bisiesto", "fin-de-anio", "cruza-anio", "mes-de-30"],
)
def test_sumar_meses(inicio: datetime, meses: int, esperado: datetime) -> None:
    assert sumar_meses(inicio, meses) == esperado


@pytest.mark.rf("RF-01")
def test_sumar_meses_conserva_la_zona() -> None:
    santiago = timezone(timedelta(hours=-3))
    inicio = datetime(2026, 10, 20, 8, 0, tzinfo=santiago)

    assert sumar_meses(inicio, 12).utcoffset() == timedelta(hours=-3)


# --- Aviso canónico --------------------------------------------------------------------------


@pytest.mark.rf("RF-01")
def test_aviso_canonico_del_cuidador_de_hecho() -> None:
    aviso = AVISO_CUIDADOR_DE_HECHO

    assert (aviso.id, aviso.version) == ("aviso_cuidador_de_hecho", "1.0")
    assert aviso.titulo == "Aviso: tu autorización tiene un límite"
    assert len(aviso.parrafos) == 3
    assert aviso.parrafos[-1] == "En 12 meses te pediremos confirmar que sigues a cargo de su cuidado."
    # Texto plano: sin marcas de Markdown
    for texto in (aviso.titulo, *aviso.parrafos):
        assert "**" not in texto and not texto.startswith(">")
    assert aviso_de(CUIDADOR) is aviso
    assert aviso_de(TITULAR) is None
    assert aviso_de(REPRESENTANTE) is None


@pytest.mark.rf("RF-01")
def test_sha256_del_aviso_es_titulo_y_parrafos_en_nfc() -> None:
    aviso = AVISO_CUIDADOR_DE_HECHO
    texto = "\n\n".join((aviso.titulo, *aviso.parrafos))

    assert aviso.sha256 == hashlib.sha256(unicodedata.normalize("NFC", texto).encode("utf-8")).hexdigest()
    assert len(aviso.sha256) == 64


@pytest.mark.rf("RF-01")
def test_sha256_no_cambia_con_tildes_descompuestas() -> None:
    compuesto = Aviso(id="a", version="1.0", titulo="autorización", parrafos=("límite",))
    descompuesto = Aviso(
        id="a",
        version="1.0",
        titulo=unicodedata.normalize("NFD", "autorización"),
        parrafos=(unicodedata.normalize("NFD", "límite"),),
    )

    assert compuesto.titulo != descompuesto.titulo
    assert compuesto.sha256 == descompuesto.sha256


@pytest.mark.rf("RF-01")
def test_sha256_cambia_si_cambia_una_letra() -> None:
    aviso = AVISO_CUIDADOR_DE_HECHO
    alterado = Aviso(id=aviso.id, version=aviso.version, titulo=aviso.titulo, parrafos=(*aviso.parrafos[:2], "Otro."))

    assert alterado.sha256 != aviso.sha256


# Huella publicada en la política de privacidad v0.9 (docs/legal/politica-privacidad.md del repositorio MATU)
HUELLA_PUBLICADA_AVISO_CUIDADOR = "9b33205fd93e18b3eaac569071b794d21071a414ccc0d8bb5b89f9c96af3dfc9"


@pytest.mark.rf("RF-01")
def test_aviso_vigente_coincide_con_la_huella_publicada_en_la_politica() -> None:
    aviso = AVISO_CUIDADOR_DE_HECHO

    assert (aviso.id, aviso.version, aviso.sha256) == (
        "aviso_cuidador_de_hecho",
        "1.0",
        HUELLA_PUBLICADA_AVISO_CUIDADOR,
    ), (
        "El aviso del cuidador de hecho ya no coincide con la huella publicada en la política de privacidad. "
        "Si cambió el texto, sube la versión del aviso y actualiza la huella en "
        "docs/legal/politica-privacidad.md del repositorio MATU."
    )


# --- Roles -----------------------------------------------------------------------------------


@pytest.mark.rf("RF-01")
@pytest.mark.parametrize(
    ("rol", "da_de_alta", "vista"),
    [
        ("admin", True, VistaPersona.COMPLETA),
        ("cuidador", True, VistaPersona.COMPLETA),
        ("pagador", False, VistaPersona.NOMBRE_Y_DIRECCION),
        ("observador", False, VistaPersona.NOMBRE),
        ("desconocido", False, VistaPersona.NOMBRE),
    ],
)
def test_permisos_y_vista_por_rol(rol: str, da_de_alta: bool, vista: VistaPersona) -> None:
    assert puede_dar_de_alta(rol) is da_de_alta
    assert vista_para_rol(rol) is vista
