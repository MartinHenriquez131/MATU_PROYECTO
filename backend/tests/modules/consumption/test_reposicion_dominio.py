"""MATU-51 · «Compré» y «Me quedan N»: reglas puras (RF-10, RF-11, decisiones 137 a 139 y 144). Sin base ni reloj.

Lo comprado sale de cantidad_comprada (envases × unidades_por_envase, o cantidad) y se suma con reponer(), la
misma función de «Ya lo resolví». «Me quedan N» es recontar(), que llama a aplicar_cambios. Las alertas que
dejan de corresponder salen de planificar (decisión 75), sin otra regla.
"""

import uuid
from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.modules.consumption.domain import alerta as dominio_alerta
from app.modules.consumption.domain import perfil as dominio_perfil
from app.modules.consumption.domain.alerta import (
    CANTIDAD_MAXIMA,
    ENVASES_MAXIMO,
    AlertaAbierta,
    EnvasesOCantidad,
    SinUnidadesPorEnvase,
    StockMaximo,
    cantidad_comprada,
    dejan_de_corresponder,
    reponer,
)
from app.modules.consumption.domain.perfil import (
    STOCK_MAXIMO,
    CambiosPerfil,
    CoberturaMaxima,
    Perfil,
    UnidadConsumo,
    aplicar_cambios,
    nuevo_perfil,
    recontar,
)

pytestmark = pytest.mark.rf("RF-11")

HOY = date(2026, 11, 7)
AUTOR = uuid.UUID("00000000-0000-4000-8000-0000000051a1")


def _perfil(
    stock: int = 24, tasa_u: int = 4, tasa_d: int = 1, hace: int = 0, envase: int | None = None, aviso: int = 7
) -> Perfil:
    return nuevo_perfil(
        perfil_id=uuid.UUID("00000000-0000-4000-8000-0000000051b1"),
        persona_cuidada_id=uuid.UUID("00000000-0000-4000-8000-0000000051c1"),
        producto_id=None,
        nombre_libre="Pañal adulto M",
        unidad=UnidadConsumo.UNIDAD,
        tasa_unidades=tasa_u,
        tasa_dias=tasa_d,
        stock_unidades=stock,
        dias_aviso=aviso,
        hoy=HOY - timedelta(days=hace),
        autor=AUTOR,
        unidades_por_envase=envase,
    )


# --- Lo comprado: envases o cantidad (decisión 137) --------------------------------------------------------


def test_los_topes_son_los_del_ajuste_de_jorge() -> None:
    assert (ENVASES_MAXIMO, CANTIDAD_MAXIMA, STOCK_MAXIMO) == (99, 10_000, 100_000)


def test_envases_se_multiplican_por_las_unidades_del_envase() -> None:
    assert cantidad_comprada(_perfil(envase=30), envases=2, cantidad=None) == 60


def test_cantidad_va_en_la_unidad_del_insumo_aunque_haya_envase() -> None:
    assert cantidad_comprada(_perfil(envase=30), envases=None, cantidad=7) == 7
    assert cantidad_comprada(_perfil(), envases=None, cantidad=CANTIDAD_MAXIMA) == 10_000


def test_envases_por_unidades_puede_pasar_de_10000() -> None:
    # 3 bidones de 5.000 ml: 15.000, se acepta (lo limitan el stock y la cobertura)
    assert cantidad_comprada(_perfil(envase=5000), envases=3, cantidad=None) == 15_000


@pytest.mark.parametrize(("envases", "cantidad"), [(None, None), (1, 1)])
def test_exactamente_uno_de_envases_y_cantidad(envases: int | None, cantidad: int | None) -> None:
    with pytest.raises(EnvasesOCantidad):
        cantidad_comprada(_perfil(envase=10), envases=envases, cantidad=cantidad)


def test_envases_sin_unidades_por_envase() -> None:
    with pytest.raises(SinUnidadesPorEnvase):
        cantidad_comprada(_perfil(envase=None), envases=1, cantidad=None)


@pytest.mark.parametrize(("envases", "cantidad"), [(0, None), (100, None), (None, 0), (None, 10_001), (None, -2)])
def test_fuera_de_rango(envases: int | None, cantidad: int | None) -> None:
    with pytest.raises(ValueError):
        cantidad_comprada(_perfil(envase=10), envases=envases, cantidad=cantidad)


# --- «Compré» suma con reponer() (condición 2, decisión 138) -------------------------------------------------


def test_compre_suma_a_lo_que_queda_hoy_mide_hoy_y_sube_la_version() -> None:
    # Anotado hace 2 días: 24 - 8 = 16; + 2 envases de 30 = 76, a 4 por día alcanza 19 días
    perfil = _perfil(hace=2, envase=30)
    nuevo = reponer(perfil, cantidad_comprada(perfil, envases=2, cantidad=None), HOY, AUTOR)
    assert (nuevo.stock_unidades, nuevo.stock_medido_en, nuevo.version) == (76, HOY, 2)
    assert nuevo.fecha_quiebre_estimada == HOY + timedelta(days=19)
    assert nuevo.actualizado_por == AUTOR and nuevo.unidades_por_envase == 30


def test_compre_con_lo_estimado_negativo_parte_de_cero() -> None:
    nuevo = reponer(_perfil(hace=30), 8, HOY, AUTOR)
    assert (nuevo.stock_unidades, nuevo.fecha_quiebre_estimada) == (8, HOY + timedelta(days=2))


def test_compre_es_aritmetica_entera() -> None:
    # 10 a 3 cada 7 días, anotado hace 4: piso(10 - 12/7) = 8; + 5 = 13 cubre piso(13 * 7 / 3) = 30 días
    nuevo = reponer(_perfil(10, 3, 7, hace=4), 5, HOY, AUTOR)
    assert isinstance(nuevo.stock_unidades, int)
    assert (nuevo.stock_unidades, nuevo.fecha_quiebre_estimada) == (13, HOY + timedelta(days=30))


def test_compre_no_pasa_del_tope_del_stock() -> None:
    perfil = _perfil(stock=95_000, tasa_u=10_000, envase=5000)
    with pytest.raises(StockMaximo):
        reponer(perfil, cantidad_comprada(perfil, envases=2, cantidad=None), HOY, AUTOR)
    # Justo en el tope sí
    assert reponer(perfil, 5000, HOY, AUTOR).stock_unidades == STOCK_MAXIMO


def test_compre_no_pasa_de_la_cobertura_maxima() -> None:
    with pytest.raises(CoberturaMaxima):
        reponer(_perfil(stock=10, tasa_u=1, tasa_d=90), 10_000, HOY, AUTOR)


# --- «Me quedan N» con aplicar_cambios (condición 1, decisión 139) -----------------------------------------------


def test_me_quedan_reemplaza_el_stock_y_es_lo_mismo_que_el_patch() -> None:
    perfil = _perfil(hace=3)
    nuevo = recontar(perfil, 40, HOY, AUTOR)
    assert nuevo == aplicar_cambios(perfil, CambiosPerfil(stock_unidades=40), HOY, AUTOR)
    assert (nuevo.stock_unidades, nuevo.stock_medido_en, nuevo.version) == (40, HOY, 2)
    assert nuevo.fecha_quiebre_estimada == HOY + timedelta(days=10)


def test_me_quedan_cero_se_acaba_hoy() -> None:
    assert recontar(_perfil(), 0, HOY, AUTOR).fecha_quiebre_estimada == HOY


@pytest.mark.parametrize("stock", [-1, 100_001])
def test_me_quedan_de_0_a_100000(stock: int) -> None:
    with pytest.raises(ValueError):
        recontar(_perfil(), stock, HOY, AUTOR)


def test_me_quedan_no_pasa_de_la_cobertura_maxima() -> None:
    with pytest.raises(CoberturaMaxima):
        recontar(_perfil(tasa_u=1, tasa_d=90), 100, HOY, AUTOR)


def test_me_quedan_reutiliza_aplicar_cambios(monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas: list[CambiosPerfil] = []
    original = dominio_perfil.aplicar_cambios

    def espia(perfil: Perfil, cambios: CambiosPerfil, hoy: date, autor: uuid.UUID) -> Perfil:
        llamadas.append(cambios)
        return original(perfil, cambios, hoy, autor)

    monkeypatch.setattr(dominio_perfil, "aplicar_cambios", espia)
    recontar(_perfil(), 5, HOY, AUTOR)
    assert llamadas == [CambiosPerfil(stock_unidades=5)]


# --- Las alertas que dejan de corresponder (condición 9, decisión 75) -------------------------------------------


def _abierta(fecha: date) -> AlertaAbierta:
    return AlertaAbierta(id=uuid.uuid4(), fecha_prevista=fecha)


@pytest.mark.rf("RF-12")
def test_salir_de_la_ventana_descarta_todas_las_abiertas() -> None:
    perfil = _perfil(stock=200)  # 50 días: fuera de la ventana de 7
    abiertas = (_abierta(HOY + timedelta(days=3)), _abierta(perfil.fecha_quiebre_estimada))
    assert dejan_de_corresponder(perfil, abiertas, HOY) == tuple(a.id for a in abiertas)


@pytest.mark.rf("RF-12")
def test_en_la_ventana_queda_la_de_la_fecha_nueva_y_se_descartan_las_demas() -> None:
    perfil = _perfil(stock=12)  # 3 días: en la ventana
    vigente, vieja = _abierta(perfil.fecha_quiebre_estimada), _abierta(HOY + timedelta(days=6))
    assert dejan_de_corresponder(perfil, (vigente, vieja), HOY) == (vieja.id,)


@pytest.mark.rf("RF-12")
def test_sin_abiertas_no_hay_nada_que_cerrar_ni_se_pide_crear_una() -> None:
    assert dejan_de_corresponder(_perfil(stock=12), (), HOY) == ()


@pytest.mark.rf("RF-12")
def test_dejan_de_corresponder_usa_planificar(monkeypatch: pytest.MonkeyPatch) -> None:
    vistas: list[object] = []
    original = dominio_alerta.planificar

    def espia(insumo: dominio_alerta.InsumoEnSeguimiento, hoy: date) -> dominio_alerta.PlanAlertas:
        vistas.append(insumo)
        return original(insumo, hoy)

    monkeypatch.setattr(dominio_alerta, "planificar", espia)
    dejan_de_corresponder(_perfil(), (), HOY)
    assert len(vistas) == 1


@pytest.mark.rf("RF-12")
def test_un_perfil_inactivo_descarta_todas() -> None:
    perfil = replace(_perfil(stock=12), activo=False)
    abierta = _abierta(perfil.fecha_quiebre_estimada)
    assert dejan_de_corresponder(perfil, (abierta,), HOY) == (abierta.id,)


def test_el_dominio_no_lee_el_reloj_del_sistema() -> None:
    import inspect

    for modulo in (dominio_alerta, dominio_perfil):
        fuente = inspect.getsource(modulo)
        assert "datetime.now" not in fuente and "date.today" not in fuente
