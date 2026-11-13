"""Adaptador SQL de RepositorioComercio (MATU-63, migración 0029).

Corre en la sesión del comercio (app.usuario_id y app.comercio_id, nunca app.grupo_id, D-63-14). Lee y escribe el
pedido solo por las funciones SECURITY DEFINER de la 0029: las políticas ya no le dejan ver ninguna fila de pedido,
pedido_comercio ni pedido_linea (D-63-1). Del comercio lee su nombre de fantasía y si es ficticio, y de sus ofertas
cambia solo stock y disponible (trigger oferta_comercio_acotada). Nada de esto va a los logs.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.modules.fulfillment.application.ports import Comercio, LineaComercio, ParteComercio, ProductoComercio
from app.modules.fulfillment.domain.despacho import EstadoParte

_COMERCIO = text(
    "SELECT id, nombre_fantasia, ficticio FROM comercio WHERE id = app_comercio() AND estado = 'activo'"
)
_PARTES = text("SELECT * FROM comercio_partes(:desde)")
_LINEAS = text("SELECT * FROM comercio_lineas(:parte)")
_PREPARAR = text("SELECT comercio_preparar(:parte, :version, :ahora)")
_MARCAR = text("SELECT comercio_marcar_linea(:parte, :linea, :estado, :faltantes, :version)")
_LISTO = text("SELECT comercio_listo(:parte, :version, :ahora)")
_VALIDAR = text("SELECT resultado, intentos_restantes FROM comercio_validar_codigo(:parte, :huella, :ahora)")
_PRODUCTOS = text("SELECT * FROM comercio_existencias(:ahora)")
_CAMBIAR = text(
    "UPDATE oferta SET stock = COALESCE(:stock, stock), disponible = COALESCE(:disponible, disponible),"
    " actualizado_en = :ahora"
    " WHERE id = :oferta AND comercio_id = app_comercio()"
    " AND (CAST(:antes AS timestamptz) IS NULL OR actualizado_en = :antes) RETURNING id"
)
_EXISTE = text("SELECT 1 FROM oferta WHERE id = :oferta AND comercio_id = app_comercio()")
# El primer día de la historia: la parte que se pide por id puede haberse cerrado antes de hoy
DESDE_SIEMPRE = datetime(2000, 1, 1).astimezone()


def _parte(f: Row[Any]) -> ParteComercio:
    return ParteComercio(
        id=f.parte_id,
        referencia=f.referencia,
        estado=EstadoParte(f.estado),
        version=int(f.version),
        enviado_en=f.enviado_en,
        lineas=int(f.lineas),
        retirada_en=f.retirada_en,
        cancelada_en=f.cancelada_en,
        codigo_generado_en=f.codigo_generado_en,
        codigo_con_hash=bool(f.codigo_con_hash),
        codigo_expira_en=f.codigo_expira_en,
        codigo_usado_en=f.codigo_usado_en,
        codigo_bloqueado_en=f.codigo_bloqueado_en,
        motivo_cancelacion=f.motivo_cancelacion,
    )


class RepositorioComercioSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def comercio(self) -> Comercio | None:
        f = self._sesion.execute(_COMERCIO).first()
        return None if f is None else Comercio(f.id, f.nombre_fantasia, bool(f.ficticio))

    def partes(self, desde: datetime) -> list[ParteComercio]:
        return [_parte(f) for f in self._sesion.execute(_PARTES, {"desde": desde})]

    def parte(self, parte_id: uuid.UUID) -> ParteComercio | None:
        return next((p for p in self.partes(DESDE_SIEMPRE) if p.id == parte_id), None)

    def lineas(self, parte_id: uuid.UUID) -> list[LineaComercio]:
        return [
            LineaComercio(
                id=f.linea_id,
                producto_nombre=f.producto_nombre,
                presentacion=f.presentacion,
                cantidad=int(f.cantidad),
                estado_linea=f.estado_linea,
                unidades_faltantes=int(f.unidades_faltantes),
            )
            for f in self._sesion.execute(_LINEAS, {"parte": parte_id})
        ]

    def preparar(self, parte_id: uuid.UUID, version: int | None, ahora: datetime) -> str:
        return str(self._sesion.execute(_PREPARAR, {"parte": parte_id, "version": version, "ahora": ahora}).scalar())

    def marcar_linea(
        self, parte_id: uuid.UUID, linea_id: uuid.UUID, estado: str, faltantes: int, version: int | None
    ) -> str:
        return str(
            self._sesion.execute(
                _MARCAR,
                {"parte": parte_id, "linea": linea_id, "estado": estado, "faltantes": faltantes, "version": version},
            ).scalar()
        )

    def listo(self, parte_id: uuid.UUID, version: int | None, ahora: datetime) -> str:
        return str(self._sesion.execute(_LISTO, {"parte": parte_id, "version": version, "ahora": ahora}).scalar())

    def validar_codigo(self, parte_id: uuid.UUID, huella: str, ahora: datetime) -> tuple[str, int]:
        f = self._sesion.execute(_VALIDAR, {"parte": parte_id, "huella": huella, "ahora": ahora}).one()
        return str(f.resultado), int(f.intentos_restantes)

    def productos(self, ahora: datetime) -> list[ProductoComercio]:
        return [
            ProductoComercio(
                oferta_id=f.oferta_id,
                nombre=f.producto_nombre,
                presentacion=f.presentacion,
                precio=int(f.precio),
                stock=int(f.stock),
                apartado=int(f.apartado),
                disponible=bool(f.disponible),
                actualizado_en=f.actualizado_en,
            )
            for f in self._sesion.execute(_PRODUCTOS, {"ahora": ahora})
        ]

    def cambiar_producto(
        self, oferta_id: uuid.UUID, stock: int | None, disponible: bool | None, antes: datetime | None, ahora: datetime
    ) -> bool | None:
        cambio = self._sesion.execute(
            _CAMBIAR,
            {"oferta": oferta_id, "stock": stock, "disponible": disponible, "antes": antes, "ahora": ahora},
        ).first()
        if cambio is not None:
            return True
        return False if self._sesion.execute(_EXISTE, {"oferta": oferta_id}).first() is not None else None
