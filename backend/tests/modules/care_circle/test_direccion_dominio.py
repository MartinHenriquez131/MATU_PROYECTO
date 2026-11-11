"""MATU-61 · La dirección de la persona y la autorización de pedidos, sin base (D1, D4, C2, C6, C8; P13).

- La precondición de la dirección: If-None-Match: * la primera vez, If-Match con el etag después (428, 422, 412).
- La cambian y la vacían admin y cuidador, sin mirar la autorización de pedidos (C8).
- despacho solo con la capa 3 (C2), con su declaración y su huella (P13).
"""

import pytest

from app.modules.care_circle.application.autorizaciones import (
    DeclaracionNoVigente,
    validar_huella_declaracion,
)
from app.modules.care_circle.domain.declaraciones import (
    DECLARACIONES_PEDIDOS,
    FORMA_HUELLA,
    huella_declaracion_pedidos,
)
from app.modules.care_circle.domain.direccion import (
    DireccionDesactualizada,
    FaltaPrecondicion,
    Precondicion,
    PrecondicionInvalida,
    SinDireccion,
    etag_de,
    exigir_precondicion_guardar,
    exigir_precondicion_vaciar,
    puede_cambiar_direccion,
)
from app.modules.care_circle.domain.personas import CalidadOtorgante, OtorgamientoInvalido, evidencia
from app.modules.care_circle.domain.retiro import FINALIDADES_RETIRABLES, finalidad_de, finalidades_retirables
TERMINOS_PROHIBIDOS = ("diagnóstico", "diagnostico", "conducta", "incidente", "deterioro", "incontinencia", "paciente")

pytestmark = pytest.mark.rf("RF-21")


@pytest.mark.parametrize(("rol", "puede"), [("admin", True), ("cuidador", True), ("pagador", False),
                                            ("observador", False), ("", False)])
def test_cambian_la_direccion_admin_y_cuidador(rol: str, puede: bool) -> None:
    assert puede_cambiar_direccion(rol) is puede


def test_la_primera_vez_if_none_match() -> None:
    exigir_precondicion_guardar(Precondicion(None, "*"), None)
    with pytest.raises(DireccionDesactualizada):
        exigir_precondicion_guardar(Precondicion(None, "*"), 1)


def test_despues_if_match_con_el_etag() -> None:
    assert etag_de(3) == '"v3"'
    exigir_precondicion_guardar(Precondicion('"v3"', None), 3)
    with pytest.raises(DireccionDesactualizada):
        exigir_precondicion_guardar(Precondicion('"v2"', None), 3)
    with pytest.raises(DireccionDesactualizada):
        exigir_precondicion_guardar(Precondicion('"v1"', None), None)


@pytest.mark.parametrize("pre", [Precondicion(None, None), Precondicion("", None), Precondicion("*", None),
                                 Precondicion(" ", " ")])
def test_sin_precondicion_428(pre: Precondicion) -> None:
    with pytest.raises(FaltaPrecondicion):
        exigir_precondicion_guardar(pre, 1)


@pytest.mark.parametrize("pre", [Precondicion('"v1"', "*"), Precondicion(None, '"v1"')])
def test_precondicion_mal_formada_422(pre: Precondicion) -> None:
    with pytest.raises(PrecondicionInvalida):
        exigir_precondicion_guardar(pre, 1)


def test_vaciar_exige_if_match_y_una_direccion() -> None:
    exigir_precondicion_vaciar('"v2"', 2)
    for valor in (None, "", "*"):
        with pytest.raises(FaltaPrecondicion):
            exigir_precondicion_vaciar(valor, 2)
    with pytest.raises(SinDireccion):
        exigir_precondicion_vaciar('"v1"', None)
    with pytest.raises(DireccionDesactualizada):
        exigir_precondicion_vaciar('"v1"', 2)


def test_despacho_solo_con_la_capa_3() -> None:
    """C2: con la capa 3 apagada, dos finalidades; encendida, tres, con despacho al final."""
    assert finalidades_retirables(False) == FINALIDADES_RETIRABLES == ("plan_cuidado", "consumo")
    assert finalidades_retirables(True) == ("plan_cuidado", "consumo", "despacho")
    assert finalidad_de("despacho") is None
    assert finalidad_de("despacho", finalidades_retirables(True)) == "despacho"


@pytest.mark.parametrize("calidad", list(CalidadOtorgante))
def test_declaracion_de_pedidos_con_su_huella(calidad: CalidadOtorgante) -> None:
    texto = DECLARACIONES_PEDIDOS[calidad]
    huella = huella_declaracion_pedidos(calidad)
    assert FORMA_HUELLA.match(huella)
    assert "{nombre_pila}" in texto and "según la política de privacidad vigente" in texto
    assert not any(t in texto.casefold() for t in TERMINOS_PROHIBIDOS)
    validar_huella_declaracion("despacho", calidad, huella)
    datos = evidencia(calidad, "0.11", "despacho", huella)
    assert datos["declaracion"] == {"id": f"declaracion_pedidos_{calidad.value}", "version": "0.11", "sha256": huella}


def test_la_huella_es_obligatoria_con_despacho_y_prohibida_con_las_otras() -> None:
    with pytest.raises(OtorgamientoInvalido) as falta:
        validar_huella_declaracion("despacho", CalidadOtorgante.TITULAR, None)
    assert falta.value.campo == "huella_declaracion"
    with pytest.raises(DeclaracionNoVigente):
        validar_huella_declaracion("despacho", CalidadOtorgante.TITULAR, "0" * 64)
    # La huella de otra calidad tampoco sirve
    with pytest.raises(DeclaracionNoVigente):
        validar_huella_declaracion(
            "despacho", CalidadOtorgante.TITULAR, huella_declaracion_pedidos(CalidadOtorgante.CUIDADOR_DE_HECHO)
        )
    for finalidad in ("consumo", "plan_cuidado"):
        validar_huella_declaracion(finalidad, CalidadOtorgante.TITULAR, None)
        with pytest.raises(OtorgamientoInvalido):
            validar_huella_declaracion(finalidad, CalidadOtorgante.TITULAR, "0" * 64)
