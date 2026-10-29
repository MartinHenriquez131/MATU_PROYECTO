"""MATU-12 y MATU-13 · Reglas puras de la ficha de relevo (RF-02, RF-04): campos, roles, texto, completitud,
ETag y precondición de escritura.

Sin base ni reloj. La regla de la autorización vigente está en
tests/modules/care_circle/test_autorizacion_dominio.py.
"""

import pytest

from app.modules.care_plan.domain.ficha import (
    CAMPOS_FICHA,
    LARGO_MAXIMO_CAMPO,
    CampoFicha,
    FaltaPrecondicion,
    PrecondicionInvalida,
    SiCoincide,
    SiNoExiste,
    campo_de,
    completitud,
    etag,
    normalizar_texto,
    precondicion_de,
    puede_escribir,
    puede_leer,
    texto_visible,
    tiene_caracteres_de_control,
    version_de_etag,
)

pytestmark = pytest.mark.rf("RF-02")


def test_la_ficha_tiene_tres_campos_en_el_orden_de_la_interfaz() -> None:
    assert [c.value for c in CAMPOS_FICHA] == ["rutina", "manejo_situaciones", "red_apoyo"]
    assert LARGO_MAXIMO_CAMPO == 500


@pytest.mark.parametrize("valor", ["rutina", "manejo_situaciones", "red_apoyo"])
def test_campo_de_reconoce_los_tres(valor: str) -> None:
    assert campo_de(valor) is CampoFicha(valor)


@pytest.mark.parametrize("valor", ["horarios", "alimentacion", "Rutina", "", "diagnostico"])
def test_campo_de_rechaza_otros_tipos_de_seccion(valor: str) -> None:
    # plan_seccion admite ocho tipos, pero la ficha de relevo solo tres (ADR-023)
    assert campo_de(valor) is None


@pytest.mark.parametrize(
    ("rol", "puede_ver_plan", "lee", "escribe"),
    [
        ("admin", False, True, True),
        ("cuidador", False, True, True),
        ("pagador", True, True, False),
        ("pagador", False, False, False),
        ("observador", False, False, False),
        ("desconocido", True, False, False),
    ],
)
def test_quien_lee_y_quien_escribe(rol: str, puede_ver_plan: bool, lee: bool, escribe: bool) -> None:
    assert puede_leer(rol, puede_ver_plan) is lee
    assert puede_escribir(rol) is escribe


@pytest.mark.parametrize(
    ("campos_con_texto", "esperada"),
    [(0, 0), (1, 33), (2, 67), (3, 100)],
)
def test_completitud_redondea_por_campo(campos_con_texto: int, esperada: int) -> None:
    assert completitud(campos_con_texto) == esperada


@pytest.mark.parametrize("fuera", [-1, 4])
def test_completitud_fuera_de_rango(fuera: int) -> None:
    with pytest.raises(ValueError):
        completitud(fuera)


def test_etag_es_fuerte_y_opaco() -> None:
    assert etag(1) == '"v1"'
    assert etag(42) == '"v42"'
    with pytest.raises(ValueError):
        etag(0)


@pytest.mark.parametrize(
    ("entrada", "guardado"),
    [
        ("  Almuerza a las 13  ", "Almuerza a las 13"),
        ("08:00 Despierta\r\n13:00 Almuerza", "08:00 Despierta\n13:00 Almuerza"),
        ("Línea uno\rLínea dos", "Línea uno\nLínea dos"),
        ("\n\n  \n", ""),
    ],
)
def test_normalizar_texto(entrada: str, guardado: str) -> None:
    assert normalizar_texto(entrada) == guardado
    # Normalizar dos veces no cambia nada
    assert normalizar_texto(guardado) == guardado


@pytest.mark.parametrize("texto", ["con\ttab", "nulo\x00", "escape\x1b", "borrar\x7f", "c1\x85"])
def test_caracteres_de_control_salvo_el_salto(texto: str) -> None:
    assert tiene_caracteres_de_control(texto)


def test_salto_de_linea_y_tildes_se_admiten() -> None:
    assert not tiene_caracteres_de_control("Ñuñoa\nCanción de su pueblo: «Él volvió»")


def test_campo_vaciado_se_muestra_como_null() -> None:
    assert texto_visible("") is None
    assert texto_visible("Hola") == "Hola"


# --- MATU-13 · Editar sin pisar lo que escribió otro (RF-04, ADR-015) ---------------------------------


@pytest.mark.rf("RF-04")
@pytest.mark.parametrize("version", [1, 2, 41])
def test_version_de_etag_devuelve_la_version_de_un_etag_emitido(version: int) -> None:
    assert version_de_etag(etag(version)) == version


@pytest.mark.rf("RF-04")
@pytest.mark.parametrize(
    "valor", ['W/"v3"', "v3", '"3"', '"v"', '"v0"', '"v03"', '"v-1"', '"v3", "v4"', '"v٣"', "", '"vx"']
)
def test_version_de_etag_rechaza_lo_que_no_emitio_matu(valor: str) -> None:
    # Comparación fuerte: un ETag débil, una lista u otro valor nunca coincide (412)
    assert version_de_etag(valor) is None


@pytest.mark.rf("RF-04")
@pytest.mark.parametrize("if_match", [None, "*", " * ", ""])
def test_sin_precondicion_o_if_match_comodin_es_428(if_match: str | None) -> None:
    with pytest.raises(FaltaPrecondicion):
        precondicion_de(if_match, None)


@pytest.mark.rf("RF-04")
def test_if_none_match_comodin_es_primera_escritura() -> None:
    assert precondicion_de(None, "*") == SiNoExiste()


@pytest.mark.rf("RF-04")
def test_if_match_lleva_la_version_leida() -> None:
    assert precondicion_de('"v3"', None) == SiCoincide(3)


@pytest.mark.rf("RF-04")
def test_if_match_que_no_es_de_matu_nunca_coincide() -> None:
    assert precondicion_de('W/"v3"', None) == SiCoincide(None)


@pytest.mark.rf("RF-04")
@pytest.mark.parametrize(
    ("if_match", "if_none_match", "tipo"),
    [('"v1"', "*", "precondicion_doble"), ("*", "*", "precondicion_doble"), (None, '"v1"', "precondicion_invalida")],
)
def test_cabeceras_mal_formadas_son_422(if_match: str | None, if_none_match: str, tipo: str) -> None:
    with pytest.raises(PrecondicionInvalida) as error:
        precondicion_de(if_match, if_none_match)
    assert (error.value.cabecera, error.value.tipo) == ("If-None-Match", tipo)
    # El error nombra la cabecera, nunca su valor
    assert '"v1"' not in str(error.value)
