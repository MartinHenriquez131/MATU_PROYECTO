"""Adaptador SQL de RepositorioDespacho (MATU-63, migración 0029).

Trabaja en la transacción del sistema (app.rol = 'sistema' y el grupo del pedido, sin cuenta) o de operación
(app.rol = 'operacion', sin cuenta). Las políticas de la 0029 les dejan mover el estado del pedido después del pago, por
las transiciones del despacho (trigger pedido_escritura_del_pago), y actualizar las partes. El evento del outbox lleva
solo identificadores.
"""

import json
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.fulfillment.application.ports import ParteDespacho, PedidoDespacho
from app.modules.fulfillment.domain.despacho import EstadoParte, LineaDespacho

_PEDIDO = (
    "SELECT id, grupo_id, persona_cuidada_id, estado, pagado_en, entregado_en, costo_envio, condiciones_version"
    " FROM pedido WHERE id = :pedido_id AND grupo_id = :grupo_id"
)
_PEDIDO_LEER = text(_PEDIDO)
_PEDIDO_BLOQUEAR = text(_PEDIDO + " FOR UPDATE")
_PARTES = text(
    "SELECT id, comercio_id, estado, enviado_en FROM pedido_comercio WHERE pedido_id = :pedido_id"
    " AND grupo_id = :grupo_id ORDER BY creado_en, id"
)
_LINEAS = text(
    "SELECT id, pedido_comercio_id, cantidad, unidades_faltantes, precio_unitario, monto_devuelto FROM pedido_linea"
    " WHERE pedido_id = :pedido_id AND estado_linea <> 'sin_stock' ORDER BY creado_en, id"
)
_COMERCIO_DE_PARTE = text("SELECT comercio_id FROM pedido_comercio WHERE id = :parte AND grupo_id = :grupo_id")
_ESTADO = text(
    "UPDATE pedido SET estado = :hacia,"
    " entregado_en = CASE WHEN :hacia = 'entregado' THEN CAST(:ahora AS timestamptz) ELSE entregado_en END"
    " WHERE id = :pedido_id AND grupo_id = :grupo_id AND estado = :desde"
)
_TRANSICION = text(
    "INSERT INTO pedido_transicion (pedido_id, desde, hacia, actor_tipo, actor_ref, motivo, ocurrido_en)"
    " VALUES (:pedido_id, :desde, :hacia, :actor_tipo, :actor_ref, :motivo, :ahora)"
)
_CANCELAR_PARTES = text(
    "UPDATE pedido_comercio SET estado = 'cancelada', cancelada_en = :ahora, motivo_cancelacion = :motivo,"
    " codigo_hash = NULL, version = version + 1"
    " WHERE pedido_id = :pedido_id AND grupo_id = :grupo_id AND estado IN ('enviada', 'preparando', 'lista')"
)
_CODIGO = text(
    "UPDATE pedido_comercio SET codigo_hash = :huella, codigo_generado_en = :generado, codigo_expira_en = :expira,"
    " codigo_usado_en = NULL, codigo_intentos = 0, codigo_bloqueado_en = NULL, version = version + 1"
    " WHERE id = :parte AND grupo_id = :grupo_id AND estado = 'lista' RETURNING id"
)
_CONSUMO = text(
    "INSERT INTO consumo_comercio (comercio_id, pedido_id, pedido_comercio_id, monto_autorizado, creado_en)"
    " VALUES (:comercio, :pedido_id, :parte, :monto, :ahora) ON CONFLICT (pedido_comercio_id) DO NOTHING"
)
_EMITIR = text(
    "INSERT INTO evento_outbox (grupo_id, tipo, agregado_tipo, agregado_id, payload, creado_en, disponible_en)"
    " VALUES (:grupo_id, :tipo, 'pedido', :pedido_id, CAST(:payload AS jsonb), :ahora, :ahora)"
)


class EstadoCambiado(Exception):
    """Otro proceso movió el pedido entre la lectura y la escritura: se vuelve a leer."""


class RepositorioDespachoSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def pedido(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> PedidoDespacho | None:
        consulta = _PEDIDO_BLOQUEAR if bloquear else _PEDIDO_LEER
        f = self._sesion.execute(consulta, {"pedido_id": pedido_id, "grupo_id": self._grupo_id}).first()
        if f is None:
            return None
        return PedidoDespacho(
            id=f.id,
            grupo_id=f.grupo_id,
            persona_id=f.persona_cuidada_id,
            estado=f.estado,
            pagado_en=f.pagado_en,
            entregado_en=f.entregado_en,
            costo_envio=int(f.costo_envio),
            condiciones_version=f.condiciones_version,
        )

    def partes(self, pedido_id: uuid.UUID) -> list[ParteDespacho]:
        return [
            ParteDespacho(f.id, f.comercio_id, EstadoParte(f.estado), f.enviado_en)
            for f in self._sesion.execute(_PARTES, {"pedido_id": pedido_id, "grupo_id": self._grupo_id})
        ]

    def lineas(self, pedido_id: uuid.UUID) -> list[LineaDespacho]:
        return [
            LineaDespacho(
                id=f.id,
                parte_id=f.pedido_comercio_id,
                cantidad=int(f.cantidad),
                unidades_faltantes=int(f.unidades_faltantes),
                precio_unitario=int(f.precio_unitario),
                monto_devuelto=int(f.monto_devuelto),
            )
            for f in self._sesion.execute(_LINEAS, {"pedido_id": pedido_id})
        ]

    def comercio_de_parte(self, parte_id: uuid.UUID) -> uuid.UUID | None:
        f = self._sesion.execute(_COMERCIO_DE_PARTE, {"parte": parte_id, "grupo_id": self._grupo_id}).first()
        return None if f is None else f.comercio_id

    def cambiar_estado(
        self,
        pedido_id: uuid.UUID,
        desde: str,
        hacia: str,
        actor_tipo: str,
        actor_ref: uuid.UUID | None,
        motivo: str | None,
        ahora: datetime,
    ) -> None:
        cambio = self._sesion.execute(
            _ESTADO,
            {"pedido_id": pedido_id, "grupo_id": self._grupo_id, "desde": desde, "hacia": hacia, "ahora": ahora},
        )
        if cambio.rowcount != 1:  # type: ignore[attr-defined]
            raise EstadoCambiado()
        self._sesion.execute(
            _TRANSICION,
            {
                "pedido_id": pedido_id,
                "desde": desde,
                "hacia": hacia,
                "actor_tipo": actor_tipo,
                "actor_ref": actor_ref,
                "motivo": motivo,
                "ahora": ahora,
            },
        )

    def cancelar_partes(self, pedido_id: uuid.UUID, motivo: str, ahora: datetime) -> None:
        self._sesion.execute(
            _CANCELAR_PARTES, {"pedido_id": pedido_id, "grupo_id": self._grupo_id, "motivo": motivo, "ahora": ahora}
        )

    def guardar_codigo(self, parte_id: uuid.UUID, huella: str, generado_en: datetime, expira_en: datetime) -> bool:
        fila = self._sesion.execute(
            _CODIGO,
            {
                "parte": parte_id,
                "grupo_id": self._grupo_id,
                "huella": huella,
                "generado": generado_en,
                "expira": expira_en,
            },
        ).first()
        return fila is not None

    def registrar_consumo(self, parte: ParteDespacho, pedido_id: uuid.UUID, monto: int, ahora: datetime) -> None:
        self._sesion.execute(
            _CONSUMO,
            {"comercio": parte.comercio_id, "pedido_id": pedido_id, "parte": parte.id, "monto": monto, "ahora": ahora},
        )

    def emitir(self, tipo: str, pedido_id: uuid.UUID, grupo_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(
            _EMITIR,
            {
                "grupo_id": grupo_id,
                "tipo": tipo,
                "pedido_id": pedido_id,
                "payload": json.dumps({"pedido_id": str(pedido_id)}),
                "ahora": ahora,
            },
        )
