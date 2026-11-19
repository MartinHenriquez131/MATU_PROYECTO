"""MATU-128 · El caso de uso «Lo que pasó con tu pedido» (pedidos_familia.lo_que_paso), sin base: quién lo recibe lo
decide lo que pagó cada cuenta (pagados_por), nunca el rol; 404 para los demás; E4 y E5."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.backoffice.application import pedidos_familia as tus_pedidos
from app.modules.backoffice.application.pedidos_familia import CabeceraPedido, CosaAnotada
from app.modules.ordering.domain.estados import Estado

pytestmark = [pytest.mark.rf("RF-20"), pytest.mark.rf("Ley-21.719")]

AHORA = datetime(2026, 11, 19, 15, 0, tzinfo=UTC)
PEDIDO = uuid.UUID("00000000-0000-0000-0000-000000128c01")
QUIEN_PAGO = uuid.UUID("00000000-0000-0000-0000-000000128c02")
OTRA_CUENTA = uuid.UUID("00000000-0000-0000-0000-000000128c03")


def _cabecera(pagado_en: datetime = AHORA, entregado_en: datetime | None = None,
              estado: Estado = Estado.PAGADO) -> CabeceraPedido:
    return CabeceraPedido(id=PEDIDO, referencia="4790", pagado_en=pagado_en, estado=estado,
                          entregado_en=entregado_en, cancelado_en=None, total=28970, costo_envio=2990,
                          condiciones_version="0.1")


class _Lectura:
    def __init__(self, cabecera: CabeceraPedido | None, pagadores: set[uuid.UUID]) -> None:
        self._cabecera = cabecera
        self._pagadores = pagadores
        self.preguntas: list[uuid.UUID] = []

    def cabecera(self, pedido_id: uuid.UUID) -> CabeceraPedido | None:
        return self._cabecera if self._cabecera is not None and self._cabecera.id == pedido_id else None

    def pagados_por(self, pedido_ids: Sequence[uuid.UUID], usuario_id: uuid.UUID) -> set[uuid.UUID]:
        self.preguntas.append(usuario_id)
        return set(pedido_ids) if usuario_id in self._pagadores else set()


class _Notas:
    def __init__(self, cosas: list[CosaAnotada]) -> None:
        self.cosas = cosas
        self.leidas = 0

    def del_pedido(self, pedido_id: uuid.UUID) -> list[CosaAnotada]:
        self.leidas += 1
        return list(self.cosas)


def _cosa(anotado_en: datetime, nota: str = "Nota sintética") -> CosaAnotada:
    return CosaAnotada(tipo="faltante", estado="abierta", anotado_en=anotado_en, resuelto_en=None, nota=nota,
                       resolucion=None, nota_disponible=True)


def _lo_que_paso(lectura: _Lectura, notas: _Notas, rol: str, usuario: uuid.UUID) -> list[CosaAnotada]:
    return tus_pedidos.lo_que_paso(lectura, notas, rol, usuario, PEDIDO, AHORA)  # type: ignore[arg-type]


@pytest.mark.parametrize("rol", ["admin", "cuidador", "pagador", "observador"])
def test_quien_pago_lo_recibe_en_cualquier_rol(rol: str) -> None:
    lectura, notas = _Lectura(_cabecera(), {QUIEN_PAGO}), _Notas([_cosa(AHORA)])
    assert [x.nota for x in _lo_que_paso(lectura, notas, rol, QUIEN_PAGO)] == ["Nota sintética"]
    assert lectura.preguntas == [QUIEN_PAGO]


@pytest.mark.parametrize("rol", ["admin", "cuidador", "pagador", "observador"])
def test_quien_no_pago_recibe_404_en_cualquier_rol_y_no_se_lee_nada(rol: str) -> None:
    """El rol nunca alcanza: el admin y el cuidador lo ven en «Datos de», no aquí."""
    lectura, notas = _Lectura(_cabecera(), {QUIEN_PAGO}), _Notas([_cosa(AHORA)])
    with pytest.raises(tus_pedidos.PedidoNoEncontrado):
        _lo_que_paso(lectura, notas, rol, OTRA_CUENTA)
    assert notas.leidas == 0


@pytest.mark.parametrize("caso", ["rol_desconocido", "sin_pedido", "vencido"])
def test_un_rol_que_no_lee_un_pedido_ajeno_o_vencido_es_404(caso: str) -> None:
    cabecera = {
        "rol_desconocido": _cabecera(),
        "sin_pedido": None,
        # C27: dos años desde la entrega
        "vencido": _cabecera(AHORA - timedelta(days=800), AHORA - timedelta(days=799), Estado.ENTREGADO),
    }[caso]
    lectura, notas = _Lectura(cabecera, {QUIEN_PAGO}), _Notas([_cosa(AHORA)])
    with pytest.raises(tus_pedidos.PedidoNoEncontrado):
        _lo_que_paso(lectura, notas, "relevo" if caso == "rol_desconocido" else "pagador", QUIEN_PAGO)
    assert notas.leidas == 0


def test_e4_e5_vacia_sin_nada_anotado_y_en_el_orden_en_que_se_anoto() -> None:
    lectura = _Lectura(_cabecera(), {QUIEN_PAGO})
    assert _lo_que_paso(lectura, _Notas([]), "pagador", QUIEN_PAGO) == []
    despues, antes = _cosa(AHORA, "Segunda"), _cosa(AHORA - timedelta(hours=1), "Primera")
    assert [x.nota for x in _lo_que_paso(lectura, _Notas([despues, antes]), "pagador", QUIEN_PAGO)] == [
        "Primera", "Segunda"]


def test_la_nota_no_sale_en_el_repr() -> None:
    assert "Nota sintética" not in repr(_cosa(AHORA))
