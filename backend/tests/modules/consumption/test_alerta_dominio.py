"""MATU-37 · Predicción de quiebre y alertas: reglas puras (RF-12). Sin base y sin reloj del sistema.

Los ocho casos de la arquitectura (sección 15.4, sprint 5) más una propiedad amplia, parametrizada
porque hypothesis no está en el entorno. La fórmula es la de MATU-36 (perfil.fecha_quiebre): aquí se
prueba como predicción, no se duplica.
"""

import itertools
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.consumption.domain.alerta import (
    AlertaAbierta,
    AlertaCerrada,
    EstadoAlerta,
    InsumoEnSeguimiento,
    avisa_por_defecto,
    avisando,
    corresponde_alerta,
    exigir_abierta,
    limites_conservacion,
    planificar,
    reponer,
    stock_estimado_hoy,
)
from app.modules.consumption.domain.perfil import (
    CoberturaMaxima,
    UnidadConsumo,
    dias_restantes,
    fecha_quiebre,
    nuevo_perfil,
)

pytestmark = pytest.mark.rf("RF-12")

ANCLA = date(2026, 11, 3)


def _dias(stock: int, tasa_unidades: int, tasa_dias: int = 1) -> int:
    return (fecha_quiebre(ANCLA, stock, tasa_unidades, tasa_dias) - ANCLA).days


# --- Los ocho casos ---------------------------------------------------------------------------------


def test_1_stock_30_a_una_por_dia_alcanza_30_dias() -> None:
    assert _dias(30, 1) == 30


def test_2_tasa_fraccionaria_dos_cada_tres_dias() -> None:
    assert _dias(10, 2, 3) == 15


def test_3_redondea_hacia_abajo() -> None:
    assert _dias(7, 2) == 3


def test_4_sin_stock_se_acaba_el_mismo_dia() -> None:
    assert fecha_quiebre(ANCLA, 0, 4, 1) == ANCLA


def test_5_menos_que_una_dosis_es_cero_dias() -> None:
    assert _dias(1, 2) == 0


def test_6_los_dias_transcurridos_se_descuentan_y_pueden_ser_negativos() -> None:
    hace_diez = ANCLA - timedelta(days=10)
    quiebre = fecha_quiebre(hace_diez, 30, 1, 1)
    assert dias_restantes(quiebre, ANCLA) == 20
    assert dias_restantes(quiebre, ANCLA + timedelta(days=25)) == -5


def test_7_umbral_avisa_con_dias_aviso_o_menos() -> None:
    def hay(restantes: int) -> bool:
        return corresponde_alerta(
            activo=True, autorizado=True, fecha_quiebre=ANCLA + timedelta(days=restantes), dias_aviso=5, hoy=ANCLA
        )

    assert hay(5) and hay(0) and hay(-3)
    assert not hay(6)


@pytest.mark.parametrize(("activo", "autorizado"), [(False, True), (True, False), (False, False)])
def test_8_inactivo_o_sin_autorizacion_no_hay_alerta(activo: bool, autorizado: bool) -> None:
    assert not corresponde_alerta(activo=activo, autorizado=autorizado, fecha_quiebre=ANCLA, dias_aviso=7, hoy=ANCLA)


# --- Propiedad: nunca antes del stock y monótona en el stock -----------------------------------------


@pytest.mark.parametrize(
    ("tasa_unidades", "tasa_dias"), list(itertools.product((1, 2, 3, 7, 10, 250, 10_000), (1, 2, 3, 7, 30, 90)))
)
def test_la_fecha_nunca_es_anterior_al_stock_y_crece_con_el_stock(tasa_unidades: int, tasa_dias: int) -> None:
    anterior = ANCLA
    for stock in range(0, 400, 7):
        try:
            fecha = fecha_quiebre(ANCLA, stock, tasa_unidades, tasa_dias)
        except CoberturaMaxima:
            break  # sobre 3650 días se rechaza (decisión 43), y con más stock también
        assert fecha >= ANCLA
        assert fecha >= anterior
        anterior = fecha


# --- Avisando, cierre y el trabajo diario -------------------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        (None, True),
        (EstadoAlerta.PENDIENTE, True),
        (EstadoAlerta.NOTIFICADA, True),
        (EstadoAlerta.RESUELTA, False),
        (EstadoAlerta.DESCARTADA, False),
    ],
)
def test_avisando_se_apaga_al_cerrar_la_alerta_de_la_fecha(estado: EstadoAlerta | None, esperado: bool) -> None:
    assert avisando(en_su_ventana=True, estado_de_la_fecha=estado) is esperado
    assert avisando(en_su_ventana=False, estado_de_la_fecha=estado) is False


def test_una_alerta_cerrada_no_se_vuelve_a_cerrar() -> None:
    exigir_abierta(EstadoAlerta.PENDIENTE)
    exigir_abierta(EstadoAlerta.NOTIFICADA)
    with pytest.raises(AlertaCerrada) as error:
        exigir_abierta(EstadoAlerta.DESCARTADA)
    assert error.value.estado is EstadoAlerta.DESCARTADA


def _insumo(**cambios: object) -> InsumoEnSeguimiento:
    base: dict[str, object] = {
        "perfil_id": uuid.uuid4(),
        "persona_cuidada_id": uuid.uuid4(),
        "fecha_quiebre_estimada": ANCLA + timedelta(days=3),
        "dias_aviso": 7,
        "autorizado": True,
    }
    base.update(cambios)
    return InsumoEnSeguimiento(**base)  # type: ignore[arg-type]


def test_planificar_materializa_en_la_ventana() -> None:
    plan = planificar(_insumo(), ANCLA)
    assert plan.materializar and plan.descartar == ()


def test_planificar_no_duplica_si_ya_hay_alerta_de_la_fecha() -> None:
    assert not planificar(_insumo(hay_alerta_de_la_fecha=True), ANCLA).materializar


def test_planificar_sin_autorizacion_no_hace_nada() -> None:
    vieja = AlertaAbierta(uuid.uuid4(), ANCLA)
    plan = planificar(_insumo(autorizado=False, abiertas=(vieja,)), ANCLA)
    assert not plan.materializar and plan.descartar == ()


def test_planificar_descarta_la_alerta_de_otra_fecha_y_crea_la_nueva() -> None:
    vieja = AlertaAbierta(uuid.uuid4(), ANCLA - timedelta(days=1))
    plan = planificar(_insumo(abiertas=(vieja,)), ANCLA)
    assert plan.materializar and plan.descartar == (vieja.id,)


def test_planificar_descarta_si_salio_de_la_ventana() -> None:
    fecha = ANCLA + timedelta(days=30)
    actual = AlertaAbierta(uuid.uuid4(), fecha)
    plan = planificar(_insumo(fecha_quiebre_estimada=fecha, abiertas=(actual,)), ANCLA)
    assert not plan.materializar and plan.descartar == (actual.id,)


def test_avisan_por_defecto_admin_y_cuidador() -> None:
    assert avisa_por_defecto("admin") and avisa_por_defecto("cuidador")
    assert not avisa_por_defecto("pagador") and not avisa_por_defecto("observador")


def test_limites_de_conservacion() -> None:
    ahora = datetime(2026, 11, 3, 12, tzinfo=UTC)
    assert limites_conservacion(ahora) == (ahora - timedelta(days=90), ahora - timedelta(days=30))
    with pytest.raises(ValueError):
        limites_conservacion(datetime(2026, 11, 3))  # noqa: DTZ001 - sin zona, a propósito


# --- «Ya lo resolví» con cantidad (decisión 79) -------------------------------------------------------

AUTOR = uuid.UUID("00000000-0000-4000-8000-0000000000a1")


def _perfil(stock: int, tasa_unidades: int = 2, tasa_dias: int = 1, anotado_hace: int = 0):  # type: ignore[no-untyped-def]
    return nuevo_perfil(
        perfil_id=uuid.uuid4(),
        persona_cuidada_id=uuid.uuid4(),
        producto_id=None,
        nombre_libre="Pañal adulto M",
        unidad=UnidadConsumo.UNIDAD,
        tasa_unidades=tasa_unidades,
        tasa_dias=tasa_dias,
        stock_unidades=stock,
        dias_aviso=7,
        hoy=ANCLA - timedelta(days=anotado_hace),
        autor=AUTOR,
    )


@pytest.mark.parametrize(
    ("stock", "tasa_u", "tasa_d", "hace", "esperado"),
    [
        (30, 2, 1, 0, 30),  # anotado hoy
        (30, 2, 1, 5, 20),  # 30 - 10
        (10, 2, 3, 4, 7),  # piso(10 - 8/3) = piso(7,33)
        (10, 2, 1, 20, 0),  # negativo: 0
        (0, 1, 1, 0, 0),
    ],
)
def test_stock_estimado_hoy_es_entero_y_nunca_negativo(
    stock: int, tasa_u: int, tasa_d: int, hace: int, esperado: int
) -> None:
    assert stock_estimado_hoy(_perfil(stock, tasa_u, tasa_d, hace), ANCLA) == esperado


def test_reponer_suma_al_estimado_mide_hoy_recalcula_y_sube_la_version() -> None:
    perfil = _perfil(10, 2, 1, anotado_hace=20)  # ya no queda nada
    nuevo = reponer(perfil, 30, ANCLA, AUTOR)
    assert (nuevo.stock_unidades, nuevo.stock_medido_en, nuevo.version) == (30, ANCLA, 2)
    assert nuevo.fecha_quiebre_estimada == ANCLA + timedelta(days=15)
    assert nuevo.tasa_unidades == perfil.tasa_unidades and nuevo.dias_aviso == perfil.dias_aviso


@pytest.mark.parametrize("cantidad", [0, -1])
def test_reponer_exige_cantidad_positiva(cantidad: int) -> None:
    # MATU-51: el tope de 1 a 10.000 lo pone cantidad_comprada (decisión 144); reponer recibe lo que salga de
    # envases × unidades_por_envase, que puede pasar de 10.000
    with pytest.raises(ValueError):
        reponer(_perfil(10), cantidad, ANCLA, AUTOR)


def test_reponer_no_pasa_de_la_cobertura_maxima() -> None:
    with pytest.raises(CoberturaMaxima):
        reponer(_perfil(10, 1, 90), 9999, ANCLA, AUTOR)
