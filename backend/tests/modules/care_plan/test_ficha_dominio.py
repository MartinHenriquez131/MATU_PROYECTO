"""MATU-12 · Reglas puras de la ficha de relevo (RF-02): campos, roles, texto, completitud y ETag.

Sin base ni reloj. La regla de la autorización vigente está en
tests/modules/care_circle/test_autorizacion_dominio.py.
"""

import pytest

from app.modules.care_plan.domain.ficha import (
    CAMPOS_FICHA,
    LARGO_MAXIMO_CAMPO,
    CampoFicha,
    campo_de,
    completitud,
    etag,
    normalizar_texto,
    puede_escribir,
    puede_leer,
    texto_visible,
    tiene_caracteres_de_control,
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
