"""MATU-60 · Reglas puras de la lista de insumos (RF-15, ADR-031) y de unidades_por_envase (RF-14).

Sin base ni reloj del sistema. Decisiones 117 a 121 de docs/api/README.md: entra el insumo con avisando,
la cantidad es lo que falta para 30 días descontando lo que queda (al menos 1), en envases enteros si el
perfil tiene unidades_por_envase, y el orden es fecha, nombre sin marcas, nombre y perfil_id.
"""

import uuid
from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.modules.consumption.domain.alerta import EstadoAlerta, avisa_hoy, stock_estimado_hoy
from app.modules.consumption.domain.lista import (
    COBERTURA_LISTA_DIAS,
    InsumoCandidato,
    armar_lista,
    entra,
    envases_sugeridos,
    sin_marcas,
    techo_division,
    unidades_para_cobertura,
    unidades_sugeridas,
)
from app.modules.consumption.domain.perfil import (
    SIN_CAMBIO,
    UNIDADES_POR_ENVASE_MAXIMO,
    CambiosPerfil,
    Perfil,
    UnidadConsumo,
    aplicar_cambios,
    exigir_unidades_por_envase,
    fecha_quiebre,
    nuevo_perfil,
)

HOY = date(2026, 11, 6)
AUTOR = uuid.UUID("00000000-0000-4000-8000-0000000060a1")
OTRO = uuid.UUID("00000000-0000-4000-8000-0000000060a2")


def _perfil(
    *,
    tasa_unidades: int = 4,
    tasa_dias: int = 1,
    stock_unidades: int = 12,
    medido_en: date = HOY,
    dias_aviso: int = 7,
    activo: bool = True,
    unidades_por_envase: int | None = None,
    unidad: UnidadConsumo = UnidadConsumo.UNIDAD,
    perfil_id: uuid.UUID | None = None,
) -> Perfil:
    return Perfil(
        id=perfil_id or uuid.uuid4(),
        persona_cuidada_id=uuid.UUID("00000000-0000-4000-8000-0000000060b1"),
        producto_id=None,
        nombre_libre="Pañal adulto talla M",
        unidad=unidad,
        tasa_unidades=tasa_unidades,
        tasa_dias=tasa_dias,
        stock_unidades=stock_unidades,
        stock_medido_en=medido_en,
        dias_aviso=dias_aviso,
        fecha_quiebre_estimada=fecha_quiebre(medido_en, stock_unidades, tasa_unidades, tasa_dias),
        activo=activo,
        version=1,
        actualizado_por=AUTOR,
        unidades_por_envase=unidades_por_envase,
    )


def _candidato(
    perfil: Perfil, nombre: str = "Pañal adulto talla M", estado: EstadoAlerta | None = None
) -> InsumoCandidato:
    return InsumoCandidato(perfil=perfil, nombre=nombre, estado_de_la_fecha=estado)


# --- Cuánto (decisiones 119 y 120, opción B) ----------------------------------------------------------


@pytest.mark.rf("RF-15")
def test_la_cobertura_es_de_30_dias() -> None:
    assert COBERTURA_LISTA_DIAS == 30


@pytest.mark.rf("RF-15")
@pytest.mark.parametrize(
    ("dividendo", "divisor", "esperado"),
    [(0, 7, 0), (1, 7, 1), (7, 7, 1), (8, 7, 2), (1500, 7, 215), (120, 20, 6), (108, 20, 6), (101, 20, 6)],
)
def test_techo_division_redondea_hacia_arriba_en_enteros(dividendo: int, divisor: int, esperado: int) -> None:
    assert techo_division(dividendo, divisor) == esperado


@pytest.mark.rf("RF-15")
@pytest.mark.parametrize(("dividendo", "divisor"), [(-1, 1), (1, 0)])
def test_techo_division_rechaza_fuera_de_rango(dividendo: int, divisor: int) -> None:
    with pytest.raises(ValueError):
        techo_division(dividendo, divisor)


@pytest.mark.rf("RF-15")
@pytest.mark.parametrize(
    ("tasa_unidades", "tasa_dias", "esperado"),
    [
        (4, 1, 120),  # pañal, 4 al día
        (50, 7, 215),  # crema, 50 ml cada 7 días: techo(1500 / 7)
        (12, 3, 120),  # toallitas, 12 cada 3 días
        (1, 90, 1),  # la tasa más baja: techo(30 / 90) = 1
        (10_000, 1, 300_000),  # el máximo con los topes de la decisión 43
    ],
)
def test_lo_de_30_dias_redondea_hacia_arriba(tasa_unidades: int, tasa_dias: int, esperado: int) -> None:
    assert unidades_para_cobertura(tasa_unidades, tasa_dias) == esperado


@pytest.mark.rf("RF-15")
def test_descuenta_lo_que_queda_hoy_y_el_envase_redondea_hacia_arriba() -> None:
    # Pañal de 4 al día anotado hoy con 12: 120 - 12 = 108 unidades, techo(108 / 20) = 6 envases
    perfil = _perfil(stock_unidades=12, unidades_por_envase=20)
    unidades = unidades_sugeridas(perfil, HOY)
    assert unidades == 108
    assert envases_sugeridos(unidades, perfil.unidades_por_envase) == 6


@pytest.mark.rf("RF-15")
def test_sin_envase_la_cantidad_va_en_la_unidad_y_envases_es_none() -> None:
    # Toallitas de 12 cada 3 días, 14 anotadas hace 3 días: quedan piso((42 - 36) / 3) = 2, y 120 - 2 = 118
    perfil = _perfil(tasa_unidades=12, tasa_dias=3, stock_unidades=14, medido_en=HOY - timedelta(days=3))
    assert stock_estimado_hoy(perfil, HOY) == 2
    unidades = unidades_sugeridas(perfil, HOY)
    assert unidades == 118
    assert envases_sugeridos(unidades, None) is None


@pytest.mark.rf("RF-15")
def test_con_stock_0_se_sugieren_los_30_dias_completos() -> None:
    perfil = _perfil(tasa_unidades=50, tasa_dias=7, stock_unidades=0, unidades_por_envase=250, unidad=UnidadConsumo.ML)
    assert unidades_sugeridas(perfil, HOY) == 215
    assert envases_sugeridos(215, 250) == 1


@pytest.mark.rf("RF-15")
def test_lo_estimado_negativo_cuenta_como_0() -> None:
    # Anotado hace 20 días con 24 a 4 por día: la estimación da negativo, queda 0, y se sugieren los 120
    perfil = _perfil(stock_unidades=24, medido_en=HOY - timedelta(days=20))
    assert stock_estimado_hoy(perfil, HOY) == 0
    assert unidades_sugeridas(perfil, HOY) == 120


@pytest.mark.rf("RF-15")
@pytest.mark.parametrize("stock", [120, 121, 200])
def test_si_lo_que_queda_alcanza_para_30_dias_o_mas_el_minimo_es_1(stock: int) -> None:
    # dias_aviso admite hasta 60: un insumo puede estar avisando con más de 30 días de stock
    perfil = _perfil(stock_unidades=stock, dias_aviso=60)
    assert unidades_sugeridas(perfil, HOY) == 1
    assert envases_sugeridos(1, 20) == 1


@pytest.mark.rf("RF-15")
def test_la_cantidad_sube_a_medida_que_pasan_los_dias() -> None:
    perfil = _perfil(stock_unidades=12)
    assert [unidades_sugeridas(perfil, HOY + timedelta(days=d)) for d in range(5)] == [108, 112, 116, 120, 120]


@pytest.mark.rf("RF-15")
def test_envase_de_una_unidad_da_tantos_envases_como_unidades() -> None:
    assert envases_sugeridos(108, 1) == 108


# --- Qué entra (decisión 117, avisando) -------------------------------------------------------------


@pytest.mark.rf("RF-15")
@pytest.mark.parametrize(
    ("estado", "entra_en_la_lista"),
    [
        (None, True),  # el trabajo diario aún no creó la alerta: entra igual
        (EstadoAlerta.PENDIENTE, True),
        (EstadoAlerta.NOTIFICADA, True),
        (EstadoAlerta.RESUELTA, False),  # «Ya lo resolví» con cantidad
        (EstadoAlerta.DESCARTADA, False),  # «No avisar esta vez» o «Ya lo resolví» sin cantidad
    ],
)
def test_entra_si_esta_avisando(estado: EstadoAlerta | None, entra_en_la_lista: bool) -> None:
    candidato = _candidato(_perfil(), estado=estado)
    assert entra(candidato, HOY) is entra_en_la_lista
    assert entra(candidato, HOY) is avisa_hoy(candidato.perfil, estado, HOY)


@pytest.mark.rf("RF-15")
def test_no_entra_el_desactivado_ni_el_que_esta_fuera_de_su_ventana() -> None:
    assert not entra(_candidato(_perfil(activo=False)), HOY)
    # 100 días de stock con aviso de 7: fuera de la ventana
    assert not entra(_candidato(_perfil(stock_unidades=400)), HOY)
    # Justo en el borde de la ventana: 7 días con aviso de 7
    assert entra(_candidato(_perfil(stock_unidades=28)), HOY)
    assert not entra(_candidato(_perfil(stock_unidades=32)), HOY)


@pytest.mark.rf("RF-15")
def test_entra_el_que_ya_paso_su_fecha() -> None:
    perfil = _perfil(stock_unidades=8, medido_en=HOY - timedelta(days=4))  # se acabó hace 2 días
    [linea] = armar_lista([_candidato(perfil)], HOY)
    assert linea.dias_restantes == -2 and linea.unidades_sugeridas == 120


# --- Orden (decisión 117) ---------------------------------------------------------------------------


@pytest.mark.rf("RF-15")
def test_sin_marcas_quita_tildes_y_aplica_casefold() -> None:
    assert sin_marcas("Óleo calcáreo") == "oleo calcareo"
    assert sin_marcas("Pañal") == "panal"
    assert sin_marcas("STRASSE") == sin_marcas("straße")


@pytest.mark.rf("RF-15")
def test_ordena_por_fecha_y_despues_por_nombre_sin_tildes() -> None:
    misma = _perfil(stock_unidades=12)
    candidatos = [
        _candidato(replace(misma, id=uuid.uuid4()), "Pañal adulto talla M"),
        _candidato(replace(misma, id=uuid.uuid4()), "óleo calcáreo"),
        _candidato(replace(misma, id=uuid.uuid4()), "Crema hidratante"),
        # Se acaba antes: va primero aunque su nombre sea el último
        _candidato(_perfil(stock_unidades=4), "Zinc en crema"),
    ]
    nombres = [linea.nombre for linea in armar_lista(candidatos, HOY)]
    # «óleo» va con la o, no después de la z
    assert nombres == ["Zinc en crema", "Crema hidratante", "óleo calcáreo", "Pañal adulto talla M"]


@pytest.mark.rf("RF-15")
def test_desempata_n_y_enie_y_mayusculas_por_casefold() -> None:
    misma = _perfil()
    candidatos = [
        _candidato(replace(misma, id=uuid.uuid4()), "Pañal"),
        _candidato(replace(misma, id=uuid.uuid4()), "panal"),
        _candidato(replace(misma, id=uuid.uuid4()), "Ánima"),
        _candidato(replace(misma, id=uuid.uuid4()), "anima"),
    ]
    nombres = [linea.nombre for linea in armar_lista(candidatos, HOY)]
    # Clave 2 empata a los pares; la clave 3 pone la letra sin marca antes (a < á, n < ñ por punto de código)
    assert nombres == ["anima", "Ánima", "panal", "Pañal"]


@pytest.mark.rf("RF-15")
def test_la_enie_compuesta_y_descompuesta_empatan_y_desempata_el_perfil_id() -> None:
    misma = _perfil()
    primero = uuid.UUID("00000000-0000-4000-8000-000000000001")
    segundo = uuid.UUID("00000000-0000-4000-8000-000000000002")
    candidatos = [
        _candidato(replace(misma, id=segundo), "Pañal"),
        _candidato(replace(misma, id=primero), "Pañal"),
    ]
    assert [linea.perfil_id for linea in armar_lista(candidatos, HOY)] == [primero, segundo]


@pytest.mark.rf("RF-15")
def test_con_todo_igual_desempata_el_perfil_id_como_texto() -> None:
    misma = _perfil()
    ids = [uuid.UUID(f"00000000-0000-4000-8000-00000000000{d}") for d in "c3a"]
    candidatos = [_candidato(replace(misma, id=i), "Toallitas") for i in ids]
    assert [str(linea.perfil_id) for linea in armar_lista(candidatos, HOY)] == sorted(str(i) for i in ids)


@pytest.mark.rf("RF-15")
def test_la_linea_trae_lo_justo_y_la_lista_vacia_es_una_lista() -> None:
    perfil = _perfil(unidades_por_envase=20)
    [linea] = armar_lista([_candidato(perfil)], HOY)
    assert (linea.perfil_id, linea.unidad, linea.dias_restantes) == (perfil.id, UnidadConsumo.UNIDAD, 3)
    assert (linea.unidades_sugeridas, linea.unidades_por_envase, linea.envases_sugeridos) == (108, 20, 6)
    assert armar_lista([], HOY) == []


# --- unidades_por_envase en el perfil (decisión 121) -------------------------------------------------


def _nuevo(unidades_por_envase: int | None = None) -> Perfil:
    return nuevo_perfil(
        perfil_id=uuid.uuid4(),
        persona_cuidada_id=uuid.uuid4(),
        producto_id=None,
        nombre_libre="Pañal adulto talla M",
        unidad=UnidadConsumo.UNIDAD,
        tasa_unidades=4,
        tasa_dias=1,
        stock_unidades=24,
        dias_aviso=7,
        hoy=HOY,
        autor=AUTOR,
        unidades_por_envase=unidades_por_envase,
    )


@pytest.mark.rf("RF-14")
def test_el_perfil_nace_sin_envase_o_con_el_que_se_anota() -> None:
    assert _nuevo().unidades_por_envase is None
    assert _nuevo(unidades_por_envase=20).unidades_por_envase == 20


@pytest.mark.rf("RF-14")
@pytest.mark.parametrize("valor", [0, -1, UNIDADES_POR_ENVASE_MAXIMO + 1])
def test_envase_fuera_de_rango_se_rechaza_sin_el_valor(valor: int) -> None:
    with pytest.raises(ValueError) as error:
        exigir_unidades_por_envase(valor)
    assert str(valor) not in str(error.value).replace("10000", "")
    with pytest.raises(ValueError):
        _nuevo(unidades_por_envase=valor)


@pytest.mark.rf("RF-14")
def test_patch_fija_cambia_y_borra_el_envase_sin_tocar_la_medicion() -> None:
    perfil = _nuevo()
    despues = HOY + timedelta(days=2)
    puesto = aplicar_cambios(perfil, CambiosPerfil(unidades_por_envase=20), despues, OTRO)
    assert puesto.unidades_por_envase == 20 and puesto.version == 2 and puesto.actualizado_por == OTRO
    # Cambiar solo el envase no vuelve a anclar el cálculo
    assert (puesto.stock_medido_en, puesto.fecha_quiebre_estimada) == (
        perfil.stock_medido_en,
        perfil.fecha_quiebre_estimada,
    )
    borrado = aplicar_cambios(puesto, CambiosPerfil(unidades_por_envase=None), despues, AUTOR)
    assert borrado.unidades_por_envase is None and borrado.version == 3


@pytest.mark.rf("RF-14")
def test_patch_sin_el_envase_lo_conserva() -> None:
    perfil = _nuevo(unidades_por_envase=20)
    assert CambiosPerfil().unidades_por_envase is SIN_CAMBIO
    despues = aplicar_cambios(perfil, CambiosPerfil(stock_unidades=10), HOY, AUTOR)
    assert despues.unidades_por_envase == 20


@pytest.mark.rf("RF-14")
def test_patch_con_envase_fuera_de_rango_no_cambia_nada() -> None:
    with pytest.raises(ValueError):
        aplicar_cambios(_nuevo(), CambiosPerfil(unidades_por_envase=0), HOY, AUTOR)
