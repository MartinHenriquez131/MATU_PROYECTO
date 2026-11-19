"""Adaptador SQL de LecturaPedidos (MATU-92), en la transacción de la petición (sesion_de_grupo), sin migración.

RLS acota todo al grupo. El observador lee el pedido, sus líneas y sus partes; el cargo, su participación y los
retractos, solo de los pedidos que pagó (MATU-116, migración 0032: «o pagó este pedido»), y nunca la entrega.
Nunca lee ``codigo_*`` ni la referencia opaca de la parte (C15), ni nada de la cuenta del encargado.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.backoffice.application.pedidos_familia import CabeceraPedido, LineaLeida, ParteLeida
from app.modules.ordering.domain.estados import Estado

_PERSONA = text(
    "SELECT 1 FROM persona_cuidada WHERE id = :persona_id AND grupo_id = :grupo_id AND eliminado_en IS NULL"
)
_CABECERA = (
    "SELECT p.id, p.referencia, p.pagado_en, p.estado, p.entregado_en, p.total, p.costo_envio,"
    " p.condiciones_version, (SELECT max(t.ocurrido_en) FROM pedido_transicion t WHERE t.pedido_id = p.id"
    " AND t.hacia = 'cancelado_con_devolucion') AS cancelado_en"
    " FROM pedido p JOIN persona_cuidada pc ON pc.id = p.persona_cuidada_id AND pc.grupo_id = p.grupo_id"
    " WHERE p.grupo_id = :grupo_id AND p.pagado_en IS NOT NULL AND pc.eliminado_en IS NULL"
)
_PAGADOS_DE = text(_CABECERA + " AND p.persona_cuidada_id = :persona_id")
_UNA = text(_CABECERA + " AND p.id = :pedido_id")
_LINEAS = text(
    "SELECT l.id, l.pedido_id, l.pedido_comercio_id, pr.id AS producto_id, pr.nombre, pr.presentacion, pr.unidad,"
    " pr.unidades_por_envase, l.cantidad, l.unidades_faltantes, l.precio_unitario,"
    " COALESCE(l.retracto_pierde_al_abrir, pr.retracto_pierde_al_abrir) AS retracto_pierde_al_abrir"
    " FROM pedido_linea l JOIN producto pr ON pr.id = l.producto_id"
    " WHERE l.pedido_id = ANY(:ids) AND l.estado_linea <> 'sin_stock' ORDER BY l.creado_en, l.id"
)
# Sin codigo_* ni la referencia de la parte (C15). El comercio con LEFT JOIN: uno suspendido no se lee (RLS) y su parte
# sigue apareciendo, sin nombre
_PARTES = text(
    "SELECT pc.id, pc.pedido_id, c.nombre_fantasia, COALESCE(c.ficticio, false) AS ficticio, pc.estado,"
    " pc.motivo_cancelacion FROM pedido_comercio pc LEFT JOIN comercio c ON c.id = pc.comercio_id"
    " WHERE pc.pedido_id = ANY(:ids) AND pc.grupo_id = :grupo_id ORDER BY c.nombre_fantasia, pc.id"
)
_DEVUELTO = text("SELECT pedido_id, monto_devuelto FROM cargo WHERE pedido_id = ANY(:ids)")
_PAGADOS_POR = text(
    "SELECT c.pedido_id FROM cargo c JOIN participacion pa ON pa.cargo_id = c.id"
    " WHERE c.pedido_id = ANY(:ids) AND pa.usuario_id = :usuario_id AND pa.monto_cobrado > 0"
)
_YA_PEDIDAS = text(
    "SELECT rl.pedido_linea_id, sum(rl.cantidad) AS pedidas,"
    " COALESCE(sum(rl.cantidad) FILTER (WHERE r.estado <> 'rechazado'), 0) AS vigentes"
    " FROM retracto_linea rl JOIN retracto r ON r.id = rl.retracto_id"
    " WHERE r.pedido_id = ANY(:ids) GROUP BY rl.pedido_linea_id"
)
_ENVIO_PEDIDO = text(
    "SELECT EXISTS (SELECT 1 FROM retracto WHERE pedido_id = :pedido_id AND incluye_envio AND estado <> 'rechazado')"
)


def _cabecera(f: Any) -> CabeceraPedido:
    return CabeceraPedido(
        id=f.id,
        referencia=f.referencia,
        pagado_en=f.pagado_en,
        estado=Estado(f.estado),
        entregado_en=f.entregado_en,
        cancelado_en=f.cancelado_en,
        total=int(f.total),
        costo_envio=int(f.costo_envio),
        condiciones_version=f.condiciones_version,
    )


class LecturaPedidosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def persona_viva(self, persona_id: uuid.UUID) -> bool:
        fila = self._sesion.execute(_PERSONA, {"persona_id": persona_id, "grupo_id": self._grupo_id}).first()
        return fila is not None

    def pagados_de(self, persona_id: uuid.UUID) -> list[CabeceraPedido]:
        filas = self._sesion.execute(_PAGADOS_DE, {"persona_id": persona_id, "grupo_id": self._grupo_id})
        return [_cabecera(f) for f in filas]

    def cabecera(self, pedido_id: uuid.UUID) -> CabeceraPedido | None:
        f = self._sesion.execute(_UNA, {"pedido_id": pedido_id, "grupo_id": self._grupo_id}).first()
        return None if f is None else _cabecera(f)

    def lineas(self, pedido_ids: Sequence[uuid.UUID]) -> list[LineaLeida]:
        return [
            LineaLeida(
                id=f.id,
                pedido_id=f.pedido_id,
                parte_id=f.pedido_comercio_id,
                producto_id=f.producto_id,
                nombre=f.nombre,
                presentacion=f.presentacion,
                unidad=f.unidad,
                unidades_por_envase=int(f.unidades_por_envase),
                cantidad=int(f.cantidad),
                unidades_faltantes=int(f.unidades_faltantes),
                precio_unitario=int(f.precio_unitario),
                retracto_pierde_al_abrir=bool(f.retracto_pierde_al_abrir),
            )
            for f in self._sesion.execute(_LINEAS, {"ids": list(pedido_ids)})
        ]

    def partes(self, pedido_ids: Sequence[uuid.UUID]) -> list[ParteLeida]:
        return [
            ParteLeida(f.id, f.pedido_id, f.nombre_fantasia, bool(f.ficticio), f.estado, f.motivo_cancelacion)
            for f in self._sesion.execute(_PARTES, {"ids": list(pedido_ids), "grupo_id": self._grupo_id})
        ]

    def devuelto(self, pedido_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        return {f.pedido_id: int(f.monto_devuelto) for f in self._sesion.execute(_DEVUELTO, {"ids": list(pedido_ids)})}

    def pagados_por(self, pedido_ids: Sequence[uuid.UUID], usuario_id: uuid.UUID) -> set[uuid.UUID]:
        filas = self._sesion.execute(_PAGADOS_POR, {"ids": list(pedido_ids), "usuario_id": usuario_id})
        return {f.pedido_id for f in filas}

    def ya_pedidas(self, pedido_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        return {
            f.pedido_linea_id: (int(f.pedidas), int(f.vigentes))
            for f in self._sesion.execute(_YA_PEDIDAS, {"ids": list(pedido_ids)})
        }

    def envio_pedido(self, pedido_id: uuid.UUID) -> bool:
        return bool(self._sesion.execute(_ENVIO_PEDIDO, {"pedido_id": pedido_id}).scalar())
