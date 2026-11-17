"""El retracto en PostgreSQL (MATU-63, migración 0029: retracto y retracto_linea, RLS forzado).

La familia (sesion_de_grupo) lo pide: crean el admin o quien pagó (retracto_familia_crear). Operación lo resuelve
(retracto_operacion_*), con el grupo del pedido. Sin montos guardados: lo que se devuelve se calcula de las líneas.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.payments.application.retractos import PedidoEntregado, Retracto

_PEDIDO = text(
    "SELECT id, persona_cuidada_id, estado, entregado_en, costo_envio, condiciones_version FROM pedido"
    " WHERE id = :pedido_id AND grupo_id = :grupo_id"
)
_LINEAS_PEDIDAS = text(
    "SELECT rl.pedido_linea_id, sum(rl.cantidad) AS pedidas,"
    " COALESCE(sum(rl.cantidad) FILTER (WHERE r.estado <> 'rechazado'), 0) AS vigentes"
    " FROM retracto_linea rl JOIN retracto r ON r.id = rl.retracto_id"
    " WHERE r.pedido_id = :pedido_id GROUP BY rl.pedido_linea_id"
)
_ENVIO_PEDIDO = text(
    "SELECT EXISTS (SELECT 1 FROM retracto WHERE pedido_id = :pedido_id AND incluye_envio AND estado <> 'rechazado')"
)
_CREAR = text(
    "INSERT INTO retracto (id, grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta, incluye_envio, origen)"
    " VALUES (:id, :grupo_id, :pedido_id, :por, :en, :plazo, :envio, :origen)"
)
_CREAR_LINEA = text(
    "INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad) VALUES (:r, :grupo_id, :l, :c)"
)
_COLUMNAS = (
    "SELECT id, grupo_id, pedido_id, solicitado_en, plazo_hasta, incluye_envio, estado, origen, solicitado_por,"
    " resuelto_en, motivo_rechazo FROM retracto"
)
_RETRACTO = _COLUMNAS + " WHERE id = :id"
_RETRACTO_LEER = text(_RETRACTO)
_RETRACTO_BLOQUEAR = text(_RETRACTO + " FOR UPDATE")
_LINEAS_DE = text("SELECT pedido_linea_id, cantidad FROM retracto_linea WHERE retracto_id = :id")
_RESOLVER = text(
    "UPDATE retracto SET estado = :estado, resuelto_en = :en, resuelto_por = :por WHERE id = :id"
    " AND estado = 'solicitado'"
)
# MATU-81: la lista de operación por estado. Primero los por resolver, del más antiguo al más reciente; después los
# resueltos, del resuelto más reciente al más antiguo. Uno más que el límite, para saber si hay más
_POR_ESTADO = text(
    _COLUMNAS + " WHERE estado = ANY(CAST(:estados AS text[])) ORDER BY (estado <> 'solicitado'),"
    " CASE WHEN estado = 'solicitado' THEN solicitado_en END, resuelto_en DESC, id LIMIT :limite"
)
_DE_PEDIDO = text(_COLUMNAS + " WHERE pedido_id = :pedido_id ORDER BY solicitado_en, id")
# MATU-92 (C8): un bloqueo de la transacción por pedido. No FOR UPDATE sobre pedido: con un pedido pagado, RLS no deja
# bloquear su fila a quien pagó con el rol pagador (pedido_pagador_condiciones exige pagado_en IS NULL), y el bloqueo
# tiene que valer para todos los que piden, operación incluida. pg_advisory_xact_lock no pide permisos (como la 0026)
_BLOQUEAR = text("SELECT pg_advisory_xact_lock(hashtextextended('retracto:' || CAST(:pedido_id AS text), 0))")


def _retracto(f: Any) -> Retracto:
    return Retracto(
        f.id, f.grupo_id, f.pedido_id, f.solicitado_en, f.plazo_hasta, f.incluye_envio, f.estado, f.origen,
        f.solicitado_por, f.resuelto_en, f.motivo_rechazo,
    )


class RepositorioRetractosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID | None = None) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def pedido(self, pedido_id: uuid.UUID) -> PedidoEntregado | None:
        f = self._sesion.execute(_PEDIDO, {"pedido_id": pedido_id, "grupo_id": self._grupo_id}).first()
        if f is None:
            return None
        return PedidoEntregado(
            f.id, f.persona_cuidada_id, f.estado, f.entregado_en, int(f.costo_envio), f.condiciones_version
        )

    def lineas_pedidas(self, pedido_id: uuid.UUID) -> dict[uuid.UUID, tuple[int, int]]:
        return {
            f.pedido_linea_id: (int(f.pedidas), int(f.vigentes))
            for f in self._sesion.execute(_LINEAS_PEDIDAS, {"pedido_id": pedido_id})
        }

    def envio_pedido(self, pedido_id: uuid.UUID) -> bool:
        return bool(self._sesion.execute(_ENVIO_PEDIDO, {"pedido_id": pedido_id}).scalar())

    def crear(self, retracto: Retracto, por: uuid.UUID, lineas: dict[uuid.UUID, int]) -> None:
        self._sesion.execute(
            _CREAR,
            {
                "id": retracto.id,
                "grupo_id": retracto.grupo_id,
                "pedido_id": retracto.pedido_id,
                "por": por,
                "en": retracto.solicitado_en,
                "plazo": retracto.plazo_hasta,
                "envio": retracto.incluye_envio,
                "origen": retracto.origen,
            },
        )
        for linea_id, cantidad in lineas.items():
            self._sesion.execute(
                _CREAR_LINEA, {"r": retracto.id, "grupo_id": retracto.grupo_id, "l": linea_id, "c": cantidad}
            )

    def retracto(self, retracto_id: uuid.UUID, *, bloquear: bool = False) -> Retracto | None:
        f = self._sesion.execute(_RETRACTO_BLOQUEAR if bloquear else _RETRACTO_LEER, {"id": retracto_id}).first()
        return None if f is None else _retracto(f)

    def por_estado(self, estados: Sequence[str], limite: int) -> list[Retracto]:
        """MATU-81: los retractos de esos estados, hasta ``limite`` (el orden está en _POR_ESTADO)."""
        filas = self._sesion.execute(_POR_ESTADO, {"estados": list(estados), "limite": limite})
        return [_retracto(f) for f in filas]

    def de_pedido(self, pedido_id: uuid.UUID) -> list[Retracto]:
        return [_retracto(f) for f in self._sesion.execute(_DE_PEDIDO, {"pedido_id": pedido_id})]

    def bloquear_pedido(self, pedido_id: uuid.UUID) -> None:
        self._sesion.execute(_BLOQUEAR, {"pedido_id": pedido_id})

    def lineas_de(self, retracto_id: uuid.UUID) -> dict[uuid.UUID, int]:
        return {f.pedido_linea_id: int(f.cantidad) for f in self._sesion.execute(_LINEAS_DE, {"id": retracto_id})}

    def resolver(self, retracto_id: uuid.UUID, estado: str, en: datetime, por: uuid.UUID) -> bool:
        cambio = self._sesion.execute(_RESOLVER, {"id": retracto_id, "estado": estado, "en": en, "por": por})
        return bool(cambio.rowcount)  # type: ignore[attr-defined]
