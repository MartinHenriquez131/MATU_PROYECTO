"""MATU-36 · Reglas puras del perfil de consumo (RF-10, RF-11). Sin base ni reloj del sistema."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.consumption.domain.perfil import (
    COBERTURA_MAXIMA_DIAS,
    CambiosPerfil,
    CoberturaMaxima,
    FaltaVersion,
    NombreLibreConProducto,
    UnidadConsumo,
    aplicar_cambios,
    coincide,
    con_activo,
    consumo_se_borra,
    dias_cobertura,
    dias_restantes,
    etag,
    exigir_if_match,
    fecha_quiebre,
    hoy_en_chile,
    limite_conservacion,
    nombre_de_pila,
    nombre_libre_valido,
    nuevo_perfil,
    puede_escribir,
    puede_leer,
)

AUTOR = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
OTRO = uuid.UUID("00000000-0000-4000-8000-0000000000a2")
HOY = date(2026, 10, 31)


def _perfil(**cambios: object):  # type: ignore[no-untyped-def]
    datos: dict[str, object] = {
        "perfil_id": uuid.uuid4(),
        "persona_cuidada_id": uuid.uuid4(),
        "producto_id": None,
        "nombre_libre": "Pañal adulto M",
        "unidad": UnidadConsumo.UNIDAD,
        "tasa_unidades": 4,
        "tasa_dias": 1,
        "stock_unidades": 24,
        "dias_aviso": 7,
        "hoy": HOY,
        "autor": AUTOR,
    }
    datos.update(cambios)
    return nuevo_perfil(**datos)  # type: ignore[arg-type]


# --- La fórmula ----------------------------------------------------------------------------------


@pytest.mark.rf("RF-11")
@pytest.mark.parametrize(
    ("stock", "tasa_u", "tasa_d", "dias"),
    [
        (24, 4, 1, 6),  # cuatro al día y quedan 24
        (160, 10, 1, 16),
        (10, 1, 2, 20),  # uno cada dos días
        (7, 2, 1, 3),  # piso: 3,5 → 3
        (1, 3, 1, 0),  # menos de un día: se acaba hoy
        (0, 4, 1, 0),  # sin stock
        (5, 3, 7, 11),  # 35/3 = 11,67 → 11
    ],
)
def test_dias_de_cobertura_son_el_piso_entero(stock: int, tasa_u: int, tasa_d: int, dias: int) -> None:
    assert dias_cobertura(stock, tasa_u, tasa_d) == dias
    assert fecha_quiebre(HOY, stock, tasa_u, tasa_d) == HOY + timedelta(days=dias)


@pytest.mark.rf("RF-11")
def test_la_formula_no_usa_punto_flotante() -> None:
    # Con flotantes, 45 * (7 / 5) da 62.99999999999999 y su piso sería 62; en enteros es exactamente 63
    assert int(45 * (7 / 5)) == 62
    assert dias_cobertura(45, 5, 7) == 63
    assert isinstance(dias_cobertura(10, 3, 1), int)


@pytest.mark.rf("RF-11")
def test_cobertura_maxima_de_3650_dias() -> None:
    assert dias_cobertura(COBERTURA_MAXIMA_DIAS, 1, 1) == COBERTURA_MAXIMA_DIAS
    with pytest.raises(CoberturaMaxima):
        dias_cobertura(COBERTURA_MAXIMA_DIAS + 1, 1, 1)


@pytest.mark.rf("RF-11")
def test_hoy_es_la_fecha_de_santiago() -> None:
    # 02:00 UTC del 1 de noviembre es todavía 31 de octubre en Santiago (UTC-3)
    assert hoy_en_chile(datetime(2026, 11, 1, 2, 0, tzinfo=UTC)) == date(2026, 10, 31)
    assert hoy_en_chile(datetime(2026, 11, 1, 4, 0, tzinfo=UTC)) == date(2026, 11, 1)
    with pytest.raises(ValueError):
        hoy_en_chile(datetime(2026, 11, 1, 4, 0))


@pytest.mark.rf("RF-11")
def test_dias_restantes() -> None:
    assert dias_restantes(date(2026, 11, 6), HOY) == 6
    assert dias_restantes(HOY, HOY) == 0
    assert dias_restantes(date(2026, 10, 30), HOY) == -1


# --- El perfil -------------------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
def test_perfil_nuevo_se_ancla_hoy() -> None:
    perfil = _perfil()
    assert perfil.stock_medido_en == HOY
    assert perfil.fecha_quiebre_estimada == date(2026, 11, 6)
    assert perfil.version == 1 and perfil.activo and perfil.actualizado_por == AUTOR


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize(("producto", "nombre"), [(None, None), (uuid.uuid4(), "Pañal")])
def test_perfil_exige_producto_o_nombre_solo_uno(producto: uuid.UUID | None, nombre: str | None) -> None:
    with pytest.raises(ValueError):
        _perfil(producto_id=producto, nombre_libre=nombre)


@pytest.mark.rf("RF-10")
def test_anotar_stock_reancla_aunque_sea_el_mismo() -> None:
    perfil = _perfil()
    despues = aplicar_cambios(perfil, CambiosPerfil(stock_unidades=24), date(2026, 11, 2), OTRO)
    assert despues.stock_medido_en == date(2026, 11, 2)
    assert despues.fecha_quiebre_estimada == date(2026, 11, 8)
    assert despues.version == 2 and despues.actualizado_por == OTRO


@pytest.mark.rf("RF-10")
def test_cambiar_la_tasa_recalcula_desde_el_ancla() -> None:
    perfil = _perfil()
    despues = aplicar_cambios(perfil, CambiosPerfil(tasa_unidades=5), date(2026, 11, 2), AUTOR)
    assert despues.stock_medido_en == HOY  # sin stock nuevo, el ancla no cambia
    assert despues.fecha_quiebre_estimada == HOY + timedelta(days=4)  # 24 // 5


@pytest.mark.rf("RF-10")
def test_editar_nombre_de_un_perfil_de_producto_falla() -> None:
    perfil = _perfil(producto_id=uuid.uuid4(), nombre_libre=None)
    with pytest.raises(NombreLibreConProducto):
        aplicar_cambios(perfil, CambiosPerfil(nombre_libre="Otro"), HOY, AUTOR)


@pytest.mark.rf("RF-10")
def test_edicion_con_cobertura_excesiva_falla() -> None:
    with pytest.raises(CoberturaMaxima):
        aplicar_cambios(_perfil(), CambiosPerfil(stock_unidades=100_000, tasa_unidades=1, tasa_dias=90), HOY, AUTOR)


@pytest.mark.rf("RF-10")
def test_desactivar_y_activar_son_idempotentes() -> None:
    perfil = _perfil()
    inactivo = con_activo(perfil, False, OTRO)
    assert not inactivo.activo and inactivo.version == 2
    assert con_activo(inactivo, False, AUTOR) is inactivo
    activo = con_activo(inactivo, True, AUTOR)
    assert activo.activo and activo.version == 3
    assert con_activo(activo, True, AUTOR) is activo


# --- Roles ---------------------------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize(
    ("rol", "lee", "escribe"),
    [("admin", True, True), ("cuidador", True, True), ("pagador", True, False), ("observador", True, False),
     ("desconocido", False, False)],
)
def test_leen_los_cuatro_roles_y_escriben_admin_y_cuidador(rol: str, lee: bool, escribe: bool) -> None:
    assert puede_leer(rol) is lee
    assert puede_escribir(rol) is escribe


# --- If-Match ------------------------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("valor", [None, "", "  ", "*"])
def test_sin_if_match_falta_version(valor: str | None) -> None:
    with pytest.raises(FaltaVersion):
        exigir_if_match(valor)


@pytest.mark.rf("RF-10")
def test_if_match_se_compara_en_forma_fuerte() -> None:
    assert etag(3) == '"v3"'
    assert coincide(exigir_if_match('"v3"'), 3)
    assert not coincide(exigir_if_match('"v2"'), 3)
    assert not coincide(exigir_if_match("v3"), 3)
    assert not coincide(exigir_if_match('W/"v3"'), 3)


# --- nombre_libre ----------------------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
def test_nombre_libre_valido() -> None:
    assert nombre_libre_valido("  Pañal adulto M ") == "Pañal adulto M"
    assert nombre_libre_valido("x" * 60) == "x" * 60


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("valor", ["", "   ", "x" * 61, "Pañal\nadulto", "Pañal\tM", "a b", "a\x00b"])
def test_nombre_libre_invalido_sin_repetir_el_valor(valor: str) -> None:
    with pytest.raises(ValueError) as error:
        nombre_libre_valido(valor)
    if valor.strip():
        assert valor.strip() not in str(error.value)


def test_nombre_de_pila() -> None:
    assert nombre_de_pila("Carmen Soto Díaz") == "Carmen"
    assert nombre_de_pila(None) is None
    assert nombre_de_pila("  ") is None


# --- Conservación (decisión 67) ---------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
def test_limite_de_conservacion_son_90_dias() -> None:
    ahora = datetime(2027, 2, 1, 12, 0, tzinfo=UTC)
    assert limite_conservacion(ahora) == ahora - timedelta(days=90)
    with pytest.raises(ValueError):
        limite_conservacion(datetime(2027, 2, 1, 12, 0))


@pytest.mark.rf("RF-10")
def test_consumo_se_borra_solo_90_dias_despues_de_terminar_la_autorizacion() -> None:
    ahora = datetime(2027, 2, 1, 12, 0, tzinfo=UTC)
    limite = limite_conservacion(ahora)
    assert consumo_se_borra(False, ahora - timedelta(days=90), limite)
    assert not consumo_se_borra(False, ahora - timedelta(days=89, hours=23), limite)
    # Con una autorización no revocada no se borra, aunque haya una vieja revocada
    assert not consumo_se_borra(True, ahora - timedelta(days=400), limite)
    # Sin ninguna revocación (nunca terminó) no se borra
    assert not consumo_se_borra(False, None, limite)
