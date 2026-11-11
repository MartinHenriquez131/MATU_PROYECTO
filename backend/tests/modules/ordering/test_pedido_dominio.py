"""MATU-61 · Reglas puras del pedido sin pagar (RF-21, ADR-027; decisiones 196 a 209; C1, C3 y C5). Sin base.

- Nunca otra marca: solo ofertas del mismo producto.
- Con otro_comercio, el de menor precio (empate por nombre y id), marcado en cambio; con quitar, sale sin buscar.
- Total = suma exacta de cantidad × precio + un envío, en pesos enteros con IVA incluido.
"""

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.modules.ordering.domain import idempotencia
from app.modules.ordering.domain.estados import Estado
from app.modules.ordering.domain.pedido import (
    CarritoInvalido,
    Comercio,
    Linea,
    LineaPedida,
    NadaDisponible,
    Oferta,
    Pedido,
    Producto,
    Regla,
    ReglaPedida,
    aplicar_confirmacion,
    armar_carrito,
    armar_reglas,
    cambio_de,
    confirmar_lineas,
    lineas_por_consultar,
    partes_por_comercio,
    puede_escribir,
    puede_leer,
    ve_entrega,
    volver_al_carrito,
)

pytestmark = pytest.mark.rf("RF-21")

AHORA = datetime(2026, 11, 20, 14, 5, tzinfo=UTC)
UNO = Comercio(uuid.UUID(int=1), "Almacén El Ejemplo", True)
DOS = Comercio(uuid.UUID(int=2), "Bodega La Muestra", True)
TRES = Comercio(uuid.UUID(int=3), "Casa de Prueba", True)
PANAL = Producto(uuid.UUID(int=11), "Pañal adulto M", "Paquete de 30 unidades", "unidad", 30, True)
TOALLAS = Producto(uuid.UUID(int=12), "Toallitas húmedas", "Paquete de 80 unidades", "unidad", 80, True)
OTRA_MARCA = Producto(uuid.UUID(int=13), "Pañal adulto M de otra marca", "Paquete de 30 unidades", "unidad", 30, True)


def _oferta(producto: Producto, comercio: Comercio, precio: int) -> Oferta:
    return Oferta(id=uuid.uuid5(uuid.NAMESPACE_OID, f"{producto.id}{comercio.id}"), producto=producto,
                  comercio=comercio, precio=precio)


def _linea(oferta: Oferta, cantidad: int = 1, regla: Regla = Regla.OTRO_COMERCIO) -> Linea:
    return Linea(
        id=uuid.uuid4(),
        producto=oferta.producto,
        cantidad=cantidad,
        regla=regla,
        oferta_carrito_id=oferta.id,
        comercio_carrito=oferta.comercio,
        precio_carrito=oferta.precio,
        oferta_id=oferta.id,
        comercio=oferta.comercio,
        precio_unitario=oferta.precio,
    )


def _pedido(*lineas: Linea, costo_envio: int = 3990) -> Pedido:
    return Pedido(
        id=uuid.uuid4(),
        grupo_id=uuid.uuid4(),
        persona_id=uuid.uuid4(),
        estado=Estado.BORRADOR,
        version=1,
        costo_envio=costo_envio,
        total_confirmado_en=None,
        total_vence_en=None,
        creado_en=AHORA,
        actualizado_en=AHORA,
        lineas=lineas,
    )


def _confirmado(pedido: Pedido, ofertas: dict[uuid.UUID, list[Oferta]], hay: dict[tuple[uuid.UUID, uuid.UUID], bool]
                ) -> Pedido:
    lineas = aplicar_confirmacion(pedido, confirmar_lineas(pedido.lineas, ofertas, hay))
    return replace(pedido, estado=Estado.TOTAL_CONFIRMADO, total_confirmado_en=AHORA, total_vence_en=AHORA,
                   lineas=lineas)


# --- Roles (C3) ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rol", "escribe", "lee", "entrega"),
    [
        ("admin", True, True, True),
        ("cuidador", True, True, True),
        ("pagador", False, True, True),
        ("observador", False, True, False),
        ("desconocido", False, False, False),
    ],
)
def test_roles_de_c3(rol: str, escribe: bool, lee: bool, entrega: bool) -> None:
    assert (puede_escribir(rol), puede_leer(rol), ve_entrega(rol)) == (escribe, lee, entrega)


# --- El carrito ---------------------------------------------------------------------------------------------------


def test_el_carrito_toma_el_precio_de_la_oferta_y_rechaza_lo_que_no_esta() -> None:
    panal = _oferta(PANAL, UNO, 12990)
    otra = uuid.uuid4()
    lineas = armar_carrito([LineaPedida(panal.id, 2)], {panal.id: panal})
    assert [(x.oferta, x.cantidad, x.precio_carrito, x.id) for x in lineas] == [(panal, 2, 12990, None)]

    with pytest.raises(CarritoInvalido) as error:
        armar_carrito([LineaPedida(panal.id, 1), LineaPedida(otra, 1)], {panal.id: panal})
    assert [(e.campo, e.tipo) for e in error.value.errores] == [("lineas.1.oferta_id", "oferta_no_disponible")]


def test_un_producto_va_una_sola_vez_aunque_sea_de_otro_comercio() -> None:
    a, b = _oferta(PANAL, UNO, 12990), _oferta(PANAL, DOS, 9990)
    with pytest.raises(CarritoInvalido) as error:
        armar_carrito([LineaPedida(a.id, 1), LineaPedida(b.id, 1)], {a.id: a, b.id: b})
    assert [(e.campo, e.tipo) for e in error.value.errores] == [("lineas.1.oferta_id", "producto_repetido")]


def test_ajustar_conserva_el_precio_del_carrito_con_la_misma_oferta() -> None:
    """C15: el cambio de precio se marca contra el precio que la familia vio en el carrito."""
    vista = _oferta(PANAL, UNO, 12990)
    linea = _linea(vista, 1)
    subio = replace(vista, precio=13990)
    [ajustada] = armar_carrito([LineaPedida(vista.id, 3)], {vista.id: subio}, [linea])
    assert (ajustada.id, ajustada.cantidad, ajustada.precio_carrito) == (linea.id, 3, 12990)
    # Con otra oferta del mismo producto, el precio del carrito es el de la nueva
    otra = _oferta(PANAL, DOS, 9990)
    [cambiada] = armar_carrito([LineaPedida(otra.id, 1)], {otra.id: otra}, [linea])
    assert (cambiada.id, cambiada.precio_carrito, cambiada.oferta) == (linea.id, 9990, otra)


def test_reglas_por_omision_otro_comercio_y_errores() -> None:
    reglas = armar_reglas([ReglaPedida(TOALLAS.id, Regla.QUITAR)], [PANAL.id, TOALLAS.id])
    assert reglas == {PANAL.id: Regla.OTRO_COMERCIO, TOALLAS.id: Regla.QUITAR}
    with pytest.raises(CarritoInvalido) as error:
        armar_reglas(
            [ReglaPedida(OTRA_MARCA.id, Regla.QUITAR), ReglaPedida(PANAL.id, Regla.QUITAR),
             ReglaPedida(PANAL.id, Regla.OTRO_COMERCIO)],
            [PANAL.id],
        )
    assert [e.tipo for e in error.value.errores] == ["producto_no_esta", "producto_repetido"]
    # Nunca otra marca: no existe una tercera acción
    assert {r.value for r in Regla} == {"otro_comercio", "quitar"}


# --- Confirmar (C5) -----------------------------------------------------------------------------------------------


def test_queda_en_el_comercio_del_carrito_si_lo_tiene() -> None:
    a, b = _oferta(PANAL, UNO, 12990), _oferta(PANAL, DOS, 9990)
    linea = _linea(a)
    [c] = confirmar_lineas([linea], {PANAL.id: [a, b]}, {(UNO.id, PANAL.id): True, (DOS.id, PANAL.id): True})
    # Aunque otro sea más barato: no recomienda, se queda donde la familia eligió
    assert c.oferta == a


def test_con_otro_comercio_busca_el_mismo_producto_el_de_menor_precio() -> None:
    a = _oferta(PANAL, UNO, 12990)
    caro, barato = _oferta(PANAL, DOS, 14990), _oferta(PANAL, TRES, 13490)
    otra_marca = _oferta(OTRA_MARCA, DOS, 5990)
    linea = _linea(a)
    hay = {(DOS.id, PANAL.id): True, (TRES.id, PANAL.id): True, (DOS.id, OTRA_MARCA.id): True}
    [c] = confirmar_lineas([linea], {PANAL.id: [a, caro, barato], OTRA_MARCA.id: [otra_marca]}, hay)
    assert c.oferta == barato
    # Nunca otra marca ni otro producto
    assert c.oferta is not None and c.oferta.producto == PANAL


def test_empate_de_precio_por_nombre_de_fantasia() -> None:
    a = _oferta(PANAL, UNO, 12990)
    b, t = _oferta(PANAL, DOS, 9990), _oferta(PANAL, TRES, 9990)
    [c] = confirmar_lineas([_linea(a)], {PANAL.id: [a, t, b]}, {(DOS.id, PANAL.id): True, (TRES.id, PANAL.id): True})
    assert c.oferta == b  # «Bodega…» antes que «Casa…»


def test_con_quitar_lo_que_falta_sale_sin_buscar_en_otro_comercio() -> None:
    a, b = _oferta(PANAL, UNO, 12990), _oferta(PANAL, DOS, 9990)
    t = _oferta(TOALLAS, UNO, 4490)
    quitar = _linea(a, regla=Regla.QUITAR)
    resultado = confirmar_lineas(
        [quitar, _linea(t)], {PANAL.id: [a, b], TOALLAS.id: [t]}, {(DOS.id, PANAL.id): True, (UNO.id, TOALLAS.id): True}
    )
    assert resultado[0].sale and resultado[1].oferta == t
    # A otro comercio ni se le pregunta por el producto con quitar
    consultas = lineas_por_consultar([quitar], {PANAL.id: [a, b]})
    assert consultas == {UNO.id: [(PANAL.id, 1)]}


def test_una_consulta_por_comercio_con_sus_lineas() -> None:
    a, b = _oferta(PANAL, UNO, 12990), _oferta(PANAL, DOS, 9990)
    t = _oferta(TOALLAS, UNO, 4490)
    consultas = lineas_por_consultar([_linea(a, 2), _linea(t, 1)], {PANAL.id: [a, b], TOALLAS.id: [t]})
    assert consultas == {
        UNO.id: sorted([(PANAL.id, 2), (TOALLAS.id, 1)], key=lambda par: str(par[0])),
        DOS.id: [(PANAL.id, 2)],
    }


def test_si_nadie_lo_tiene_sale_y_si_nada_queda_no_hay_total() -> None:
    a = _oferta(PANAL, UNO, 12990)
    with pytest.raises(NadaDisponible):
        confirmar_lineas([_linea(a)], {PANAL.id: [a]}, {})


def test_total_es_la_suma_exacta_mas_un_envio_y_lo_que_salio_no_suma() -> None:
    a, t, bolsa = _oferta(PANAL, UNO, 18990), _oferta(TOALLAS, DOS, 4490), _oferta(OTRA_MARCA, UNO, 7990)
    pedido = _pedido(_linea(a, 2), _linea(t, 1), _linea(bolsa, 1, Regla.QUITAR))
    hay = {(UNO.id, PANAL.id): True, (DOS.id, TOALLAS.id): True}
    confirmado = _confirmado(pedido, {PANAL.id: [a], TOALLAS.id: [t], OTRA_MARCA.id: [bolsa]}, hay)

    assert confirmado.subtotal_productos == 2 * 18990 + 4490 == 42470
    # Un solo envío aunque lo preparen dos comercios (ADR-027); todos los precios con IVA incluido (C5)
    assert confirmado.total == 42470 + 3990 == 46460
    assert isinstance(confirmado.total, int)
    assert [x.producto for x in confirmado.salieron()] == [OTRA_MARCA]
    assert [(p.comercio, p.subtotal_productos) for p in partes_por_comercio(confirmado.lineas)] == [
        (UNO, 37980), (DOS, 4490)
    ]


def test_cambio_marca_el_precio_y_el_comercio_contra_el_carrito() -> None:
    a = _oferta(PANAL, UNO, 3990)
    b = _oferta(PANAL, DOS, 4490)
    confirmado = _confirmado(_pedido(_linea(a)), {PANAL.id: [a, b]}, {(DOS.id, PANAL.id): True})
    [linea] = confirmado.lineas
    cambio = cambio_de(linea, confirmado=True)
    assert cambio is not None and (cambio.precio_antes, cambio.comercio_antes) == (3990, UNO)
    # Sin cambios no hay marca, y en borrador nunca
    assert cambio_de(_linea(a), confirmado=True) is None
    assert cambio_de(linea, confirmado=False) is None


def test_el_precio_que_sube_en_el_mismo_comercio_se_marca() -> None:
    vista = _oferta(PANAL, UNO, 12990)
    linea = _linea(vista)
    subio = replace(vista, precio=13990)
    confirmado = _confirmado(_pedido(linea), {PANAL.id: [subio]}, {(UNO.id, PANAL.id): True})
    cambio = cambio_de(confirmado.lineas[0], confirmado=True)
    assert cambio is not None and (cambio.precio_antes, cambio.comercio_antes) == (12990, None)
    assert confirmado.lineas[0].precio_unitario == 13990


def test_el_retracto_se_copia_al_confirmar() -> None:
    """C3: la línea guarda una copia de producto.retracto_pierde_al_abrir."""
    a = _oferta(PANAL, UNO, 12990)
    confirmado = _confirmado(_pedido(_linea(a)), {PANAL.id: [a]}, {(UNO.id, PANAL.id): True})
    assert confirmado.lineas[0].retracto_copiado is True


def test_volver_al_carrito_recupera_lo_que_salio_y_el_precio_visto() -> None:
    """C1 y C9: «Cambiar el pedido» devuelve cada línea al carrito, también la que salió."""
    a, b = _oferta(PANAL, UNO, 3990), _oferta(PANAL, DOS, 4490)
    t = _oferta(TOALLAS, UNO, 4490)
    confirmado = _confirmado(_pedido(_linea(a), _linea(t)), {PANAL.id: [a, b], TOALLAS.id: [t]},
                             {(DOS.id, PANAL.id): True})
    assert any(x.salio for x in confirmado.lineas)
    for linea in volver_al_carrito(confirmado.lineas):
        assert not linea.salio and linea.retracto_copiado is None
        assert (linea.comercio, linea.precio_unitario) == (linea.comercio_carrito, linea.precio_carrito)


# --- Idempotencia -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("clave", ["0b5e8f2a-6c1d-4e7a-9f3b-2d4c6e8a0b1c", "a" * 16, "A_b-" * 16])
def test_forma_de_la_clave_valida(clave: str) -> None:
    assert idempotencia.exigir_forma(clave) == clave


@pytest.mark.parametrize("clave", ["corta", "a" * 65, "con espacio 123456", "ñandú-ñandú-ñandú"])
def test_forma_de_la_clave_invalida(clave: str) -> None:
    with pytest.raises(idempotencia.ClaveInvalida):
        idempotencia.exigir_forma(clave)


def test_decidir_que_hacer_con_la_misma_clave() -> None:
    yo, otro = uuid.uuid4(), uuid.uuid4()
    huella = idempotencia.huella_peticion("POST /v1/x", {"lineas": [{"cantidad": 1}]})
    vence = idempotencia.expira_en(AHORA)
    terminada = idempotencia.Registro(yo, huella, 201, uuid.uuid4(), vence)
    D = idempotencia.Decision
    assert idempotencia.decidir(None, yo, huella, AHORA) is D.NUEVA
    assert idempotencia.decidir(terminada, yo, huella, AHORA) is D.REPETIDA
    assert idempotencia.decidir(terminada, otro, huella, AHORA) is D.REUTILIZADA
    otra = idempotencia.huella_peticion("POST /v1/x", {"lineas": [{"cantidad": 2}]})
    assert idempotencia.decidir(terminada, yo, otra, AHORA) is D.REUTILIZADA
    assert idempotencia.decidir(replace(terminada, estado_http=None), yo, huella, AHORA) is D.EN_CURSO
    # Vale 24 horas
    assert idempotencia.decidir(terminada, yo, huella, vence) is D.NUEVA


def test_la_huella_no_depende_del_orden_de_las_claves_y_no_guarda_el_cuerpo() -> None:
    a = idempotencia.huella_peticion("e", {"a": 1, "b": 2})
    assert a == idempotencia.huella_peticion("e", {"b": 2, "a": 1})
    assert len(a) == 32 and b"a" not in a[:0]
    assert a != idempotencia.huella_peticion("otra", {"a": 1, "b": 2})
