"""Adaptador SQL de RepositorioPagos (MATU-62, migración 0024).

Trabaja en la sesión que le dan: la de la familia (sesion_de_grupo, para pagar y leer) o la del sistema (app.rol =
'sistema' y el grupo de la venta, para la vuelta y la conciliación). RLS decide qué filas ve y escribe cada uno:
leen admin, cuidador y pagador; abren la venta admin y pagador; cierran y anulan el sistema y operación. El filtro
por grupo es además explícito en el pedido.

Nunca escribe payload_respuesta (CHECK, D-62-9) ni lee más de lo que el dominio necesita. Nada de esto va a los logs.
"""

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.modules.payments.application.ports import (
    Cargo,
    CondicionesAceptadas,
    LineaPagada,
    Participacion,
    PedidoCobro,
)
from app.modules.payments.domain.cargo import EstadoCargo, EstadoParticipacion
from app.modules.payments.domain.venta import (
    Anulacion,
    EstadoVenta,
    MotivoAnulacion,
    MotivoCierre,
    TipoTarjeta,
    Venta,
)

PROVEEDOR = "webpay_plus"

_PEDIDO = (
    "SELECT id, grupo_id, persona_cuidada_id, estado, subtotal_productos, costo_envio, total, total_confirmado_en,"
    " total_vence_en, pagado_en, referencia FROM pedido WHERE id = :pedido_id AND grupo_id = :grupo_id"
)
_PEDIDO_LEER = text(_PEDIDO)
_PEDIDO_BLOQUEAR = text(_PEDIDO + " FOR UPDATE")
_ULTIMO_PAGADO = text(
    "SELECT p.id FROM pedido p JOIN persona_cuidada pc ON pc.id = p.persona_cuidada_id AND pc.grupo_id = p.grupo_id"
    " WHERE p.grupo_id = :grupo_id AND p.persona_cuidada_id = :persona_id AND p.pagado_en IS NOT NULL"
    " AND pc.eliminado_en IS NULL ORDER BY p.pagado_en DESC, p.id LIMIT 1"
)
_ACEPTAR = text(
    "UPDATE pedido SET condiciones_version = :version, condiciones_huella = :huella,"
    " condiciones_aceptadas_en = :en, condiciones_aceptadas_por = :por"
    " WHERE id = :pedido_id AND grupo_id = :grupo_id AND pagado_en IS NULL"
)
_CONDICIONES = text(
    "SELECT condiciones_version, condiciones_huella, condiciones_aceptadas_en, condiciones_aceptadas_por"
    " FROM pedido WHERE id = :pedido_id AND grupo_id = :grupo_id"
)
_REFERENCIAS = text("SELECT referencia FROM pedido WHERE grupo_id = :grupo_id AND referencia IS NOT NULL")
_MARCAR_PAGADO = text(
    "UPDATE pedido SET estado = 'pagado', pagado_en = :en, referencia = :referencia"
    " WHERE id = :pedido_id AND grupo_id = :grupo_id"
)
_TRANSICION = text(
    "INSERT INTO pedido_transicion (pedido_id, desde, hacia, actor_tipo, actor_ref, motivo, ocurrido_en)"
    " VALUES (:pedido_id, :desde, :hacia, 'sistema', NULL, :motivo, :ocurrido_en)"
)
_LINEAS = text(
    "SELECT l.id, pr.id AS producto_id, pr.nombre, pr.presentacion, pr.unidad, pr.unidades_por_envase, l.cantidad,"
    " l.precio_unitario, l.estado_linea, l.monto_devuelto, l.devuelta_en"
    " FROM pedido_linea l JOIN producto pr ON pr.id = l.producto_id"
    " WHERE l.pedido_id = :pedido_id ORDER BY l.creado_en, l.id"
)
_DEVOLVER_LINEA = text(
    "UPDATE pedido_linea SET estado_linea = 'devuelta', monto_devuelto = :monto, devuelta_en = :en WHERE id = :id"
)
# Sin RETURNING: matu_app solo inserta en el outbox (03_permisos.sql)
_EMITIR = text(
    "INSERT INTO evento_outbox (grupo_id, tipo, agregado_tipo, agregado_id, payload, creado_en, disponible_en)"
    " VALUES (:grupo_id, :tipo, 'pedido', :pedido_id, CAST(:payload AS jsonb), :ahora, :ahora)"
)

_CORREO = text("SELECT email FROM usuario WHERE id = app_usuario()")
_ASOCIAR_CLAVE = text(
    "UPDATE idempotencia SET transaccion_id = :venta_id"
    " WHERE grupo_id = :grupo_id AND endpoint = :endpoint AND clave = :clave AND usuario_id = app_usuario()"
)
_VENTA_DE_CLAVE = text(
    "SELECT transaccion_id FROM idempotencia WHERE grupo_id = :grupo_id AND endpoint = :endpoint AND clave = :clave"
    " AND usuario_id = app_usuario()"
)
_LIBERAR_CLAVE = text(
    "DELETE FROM idempotencia WHERE grupo_id = :grupo_id AND endpoint = :endpoint AND clave = :clave"
    " AND usuario_id = app_usuario() AND estado_http IS NULL"
)

_CARGO = "SELECT id, pedido_id, estado, monto_cobrado, monto_devuelto FROM cargo"
_CARGO_DE = text(_CARGO + " WHERE pedido_id = :pedido_id")
_CARGO_DE_BLOQUEAR = text(_CARGO + " WHERE pedido_id = :pedido_id FOR UPDATE")
_CARGO_ID = text(_CARGO + " WHERE id = :cargo_id")
_CARGO_ID_BLOQUEAR = text(_CARGO + " WHERE id = :cargo_id FOR UPDATE")
_CREAR_CARGO = text(
    "INSERT INTO cargo (id, pedido_id, estado, creado_en, actualizado_en) VALUES (:id, :pedido_id, :estado, :ahora,"
    " :ahora)"
)
_GUARDAR_CARGO = text(
    "UPDATE cargo SET estado = :estado, monto_cobrado = :cobrado, monto_devuelto = :devuelto WHERE id = :id"
)
_PARTICIPACION = "SELECT id, cargo_id, usuario_id, estado, monto_cobrado, monto_devuelto FROM participacion"
_PARTICIPACION_ID = text(_PARTICIPACION + " WHERE id = :id")
_PARTICIPACION_DE = text(_PARTICIPACION + " WHERE cargo_id = :cargo_id AND usuario_id = :usuario_id")
_CREAR_PARTICIPACION = text(
    "INSERT INTO participacion (id, cargo_id, usuario_id, porcentaje_bp, estado)"
    " VALUES (:id, :cargo_id, :usuario_id, 10000, :estado)"
)
_GUARDAR_PARTICIPACION = text(
    "UPDATE participacion SET estado = :estado, monto_cobrado = :cobrado, monto_devuelto = :devuelto WHERE id = :id"
)

_VENTA = (
    "SELECT t.id, t.cargo_id, t.participacion_id, pa.usuario_id, t.estado, t.monto, t.total_confirmado_en, t.token,"
    " t.buy_order, t.session_id, t.creado_en, t.cerrada_en, t.motivo_cierre, t.tipo_tarjeta, t.ultimos4, t.cuotas,"
    " t.codigo_autorizacion, t.anulacion_total, t.retorno_recibido_en, t.commit_intentado_en,"
    " EXISTS (SELECT 1 FROM transaccion_pasarela a WHERE a.venta_id = t.id AND a.tipo = 'anulacion'"
    "         AND a.motivo_anulacion = 'pago_tardio') AS por_pago_tardio"
    " FROM transaccion_pasarela t JOIN participacion pa ON pa.id = t.participacion_id WHERE t.tipo = 'venta'"
)
_VENTAS = text(_VENTA + " AND t.cargo_id = :cargo_id ORDER BY t.creado_en, t.id")
_VENTA_ID = text(_VENTA + " AND t.id = :id")
_VENTA_ID_BLOQUEAR = text(_VENTA + " AND t.id = :id FOR UPDATE OF t")
_INSERTAR_VENTA = text(
    "INSERT INTO transaccion_pasarela (id, participacion_id, cargo_id, proveedor, tipo, buy_order, session_id, token,"
    " monto, estado, idempotency_key, total_confirmado_en, creado_en, actualizado_en)"
    " VALUES (:id, :participacion_id, :cargo_id, :proveedor, 'venta', :buy_order, :session_id, :token, :monto,"
    " :estado, :clave, :total_confirmado_en, :ahora, :ahora)"
)
_GUARDAR_VENTA = text(
    "UPDATE transaccion_pasarela SET estado = :estado, cerrada_en = :cerrada_en, motivo_cierre = :motivo_cierre,"
    " tipo_tarjeta = :tipo_tarjeta, ultimos4 = :ultimos4, cuotas = :cuotas, codigo_autorizacion = :codigo,"
    " anulacion_total = :anulacion_total, retorno_recibido_en = :retorno, commit_intentado_en = :commit"
    " WHERE id = :id AND tipo = 'venta'"
)
_ANULACION = (
    "SELECT id, venta_id, cargo_id, participacion_id, monto, motivo_anulacion, estado, creado_en, buy_order,"
    " pedido_linea_id, cerrada_en, intentos FROM transaccion_pasarela WHERE tipo = 'anulacion' AND venta_id IS NOT NULL"
)
_ANULACIONES = text(_ANULACION + " AND cargo_id = :cargo_id ORDER BY creado_en, id")
_ANULACION_ID = text(_ANULACION + " AND id = :id")
_ANULACION_ID_BLOQUEAR = text(_ANULACION + " AND id = :id FOR UPDATE")
_INSERTAR_ANULACION = text(
    "INSERT INTO transaccion_pasarela (id, participacion_id, cargo_id, proveedor, tipo, buy_order, monto, estado,"
    " idempotency_key, venta_id, motivo_anulacion, pedido_linea_id, creado_en, actualizado_en)"
    " VALUES (:id, :participacion_id, :cargo_id, :proveedor, 'anulacion', :buy_order, :monto, :estado, :clave,"
    " :venta_id, :motivo, :linea_id, :ahora, :ahora)"
)
_GUARDAR_ANULACION = text(
    "UPDATE transaccion_pasarela SET estado = :estado, cerrada_en = :hecha_en, intentos = :intentos"
    " WHERE id = :id AND tipo = 'anulacion'"
)


def _cargo(f: Row[Any]) -> Cargo:
    return Cargo(
        id=f.id,
        pedido_id=f.pedido_id,
        estado=EstadoCargo(f.estado),
        monto_cobrado=int(f.monto_cobrado),
        monto_devuelto=int(f.monto_devuelto),
    )


def _participacion(f: Row[Any]) -> Participacion:
    return Participacion(
        id=f.id,
        cargo_id=f.cargo_id,
        usuario_id=f.usuario_id,
        estado=EstadoParticipacion(f.estado),
        monto_cobrado=int(f.monto_cobrado),
        monto_devuelto=int(f.monto_devuelto),
    )


def _venta(f: Row[Any]) -> Venta:
    return Venta(
        id=f.id,
        cargo_id=f.cargo_id,
        participacion_id=f.participacion_id,
        usuario_id=f.usuario_id,
        estado=EstadoVenta(f.estado),
        monto=int(f.monto),
        total_confirmado_en=f.total_confirmado_en,
        token=f.token,
        buy_order=f.buy_order,
        session_id=f.session_id,
        creado_en=f.creado_en,
        cerrada_en=f.cerrada_en,
        motivo_cierre=None if f.motivo_cierre is None else MotivoCierre(f.motivo_cierre),
        tipo_tarjeta=None if f.tipo_tarjeta is None else TipoTarjeta(f.tipo_tarjeta),
        ultimos4=None if f.ultimos4 is None else str(f.ultimos4).strip(),
        cuotas=f.cuotas,
        codigo_autorizacion=f.codigo_autorizacion,
        anulacion_total=bool(f.anulacion_total),
        anulada_por_pago_tardio=bool(f.por_pago_tardio),
        retorno_recibido_en=f.retorno_recibido_en,
        commit_intentado_en=f.commit_intentado_en,
    )


def _anulacion(f: Row[Any]) -> Anulacion:
    return Anulacion(
        id=f.id,
        venta_id=f.venta_id,
        cargo_id=f.cargo_id,
        participacion_id=f.participacion_id,
        monto=int(f.monto),
        motivo=MotivoAnulacion(f.motivo_anulacion),
        estado=EstadoVenta(f.estado),
        solicitada_en=f.creado_en,
        buy_order=f.buy_order,
        pedido_linea_id=f.pedido_linea_id,
        hecha_en=f.cerrada_en,
        intentos=int(f.intentos),
    )


class RepositorioPagosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    # --- Pedido

    def pedido(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> PedidoCobro | None:
        consulta = _PEDIDO_BLOQUEAR if bloquear else _PEDIDO_LEER
        f = self._sesion.execute(consulta, {"pedido_id": pedido_id, "grupo_id": self._grupo_id}).first()
        if f is None:
            return None
        return PedidoCobro(
            id=f.id,
            grupo_id=f.grupo_id,
            persona_id=f.persona_cuidada_id,
            estado=f.estado,
            subtotal_productos=int(f.subtotal_productos),
            costo_envio=int(f.costo_envio),
            total=int(f.total),
            total_confirmado_en=f.total_confirmado_en,
            total_vence_en=f.total_vence_en,
            pagado_en=f.pagado_en,
            referencia=f.referencia,
        )

    def ultimo_pagado_de(self, persona_id: uuid.UUID) -> uuid.UUID | None:
        f = self._sesion.execute(_ULTIMO_PAGADO, {"grupo_id": self._grupo_id, "persona_id": persona_id}).first()
        return None if f is None else f.id

    def aceptar_condiciones(
        self, pedido_id: uuid.UUID, version: str, huella: str, aceptadas_en: datetime, por: uuid.UUID
    ) -> None:
        self._sesion.execute(
            _ACEPTAR,
            {
                "pedido_id": pedido_id,
                "grupo_id": self._grupo_id,
                "version": version,
                "huella": huella,
                "en": aceptadas_en,
                "por": por,
            },
        )

    def condiciones_aceptadas(self, pedido_id: uuid.UUID) -> CondicionesAceptadas | None:
        f = self._sesion.execute(_CONDICIONES, {"pedido_id": pedido_id, "grupo_id": self._grupo_id}).first()
        if f is None or f.condiciones_version is None:
            return None
        return CondicionesAceptadas(
            version=f.condiciones_version,
            huella=f.condiciones_huella,
            aceptadas_en=f.condiciones_aceptadas_en,
            aceptadas_por=f.condiciones_aceptadas_por,
        )

    def referencias(self) -> set[str]:
        return {f.referencia for f in self._sesion.execute(_REFERENCIAS, {"grupo_id": self._grupo_id})}

    def marcar_pagado(self, pedido_id: uuid.UUID, pagado_en: datetime, referencia: str) -> None:
        self._sesion.execute(
            _MARCAR_PAGADO,
            {"pedido_id": pedido_id, "grupo_id": self._grupo_id, "en": pagado_en, "referencia": referencia},
        )

    def transicion(
        self, pedido_id: uuid.UUID, desde: str, hacia: str, motivo: str | None, ocurrido_en: datetime
    ) -> None:
        self._sesion.execute(
            _TRANSICION,
            {"pedido_id": pedido_id, "desde": desde, "hacia": hacia, "motivo": motivo, "ocurrido_en": ocurrido_en},
        )

    def lineas_pagadas(self, pedido_id: uuid.UUID) -> list[LineaPagada]:
        return [
            LineaPagada(
                id=f.id,
                producto_id=f.producto_id,
                nombre=f.nombre,
                presentacion=f.presentacion,
                unidad=f.unidad,
                unidades_por_envase=f.unidades_por_envase,
                cantidad=f.cantidad,
                precio_unitario=int(f.precio_unitario),
                salio=f.estado_linea == "sin_stock",
                monto_devuelto=int(f.monto_devuelto),
                devuelta_en=f.devuelta_en,
            )
            for f in self._sesion.execute(_LINEAS, {"pedido_id": pedido_id})
        ]

    def devolver_linea(self, linea_id: uuid.UUID, monto: int, devuelta_en: datetime) -> None:
        self._sesion.execute(_DEVOLVER_LINEA, {"id": linea_id, "monto": monto, "en": devuelta_en})

    def correo_propio(self) -> str | None:
        f = self._sesion.execute(_CORREO).first()
        return None if f is None else f.email

    def asociar_clave(self, endpoint: str, clave: str, venta_id: uuid.UUID) -> None:
        self._sesion.execute(
            _ASOCIAR_CLAVE, {"grupo_id": self._grupo_id, "endpoint": endpoint, "clave": clave, "venta_id": venta_id}
        )

    def venta_de_clave(self, endpoint: str, clave: str) -> uuid.UUID | None:
        f = self._sesion.execute(
            _VENTA_DE_CLAVE, {"grupo_id": self._grupo_id, "endpoint": endpoint, "clave": clave}
        ).first()
        return None if f is None else f.transaccion_id

    def liberar_clave(self, endpoint: str, clave: str) -> None:
        self._sesion.execute(_LIBERAR_CLAVE, {"grupo_id": self._grupo_id, "endpoint": endpoint, "clave": clave})

    def emitir(self, tipo: str, pedido_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(
            _EMITIR,
            {
                "grupo_id": self._grupo_id,
                "tipo": tipo,
                "pedido_id": pedido_id,
                "payload": json.dumps({"pedido_id": str(pedido_id)}),
                "ahora": ahora,
            },
        )

    # --- Cargo y participación

    def cargo_de(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> Cargo | None:
        f = self._sesion.execute(_CARGO_DE_BLOQUEAR if bloquear else _CARGO_DE, {"pedido_id": pedido_id}).first()
        return None if f is None else _cargo(f)

    def cargo(self, cargo_id: uuid.UUID, *, bloquear: bool = False) -> Cargo | None:
        f = self._sesion.execute(_CARGO_ID_BLOQUEAR if bloquear else _CARGO_ID, {"cargo_id": cargo_id}).first()
        return None if f is None else _cargo(f)

    def crear_cargo(self, cargo: Cargo, ahora: datetime) -> None:
        self._sesion.execute(
            _CREAR_CARGO, {"id": cargo.id, "pedido_id": cargo.pedido_id, "estado": cargo.estado.value, "ahora": ahora}
        )

    def guardar_cargo(self, cargo: Cargo) -> None:
        self._sesion.execute(
            _GUARDAR_CARGO,
            {
                "id": cargo.id,
                "estado": cargo.estado.value,
                "cobrado": cargo.monto_cobrado,
                "devuelto": cargo.monto_devuelto,
            },
        )

    def participacion(self, participacion_id: uuid.UUID) -> Participacion | None:
        f = self._sesion.execute(_PARTICIPACION_ID, {"id": participacion_id}).first()
        return None if f is None else _participacion(f)

    def participacion_de(self, cargo_id: uuid.UUID, usuario_id: uuid.UUID) -> Participacion | None:
        f = self._sesion.execute(_PARTICIPACION_DE, {"cargo_id": cargo_id, "usuario_id": usuario_id}).first()
        return None if f is None else _participacion(f)

    def crear_participacion(self, participacion: Participacion) -> None:
        self._sesion.execute(
            _CREAR_PARTICIPACION,
            {
                "id": participacion.id,
                "cargo_id": participacion.cargo_id,
                "usuario_id": participacion.usuario_id,
                "estado": participacion.estado.value,
            },
        )

    def guardar_participacion(self, participacion: Participacion) -> None:
        self._sesion.execute(
            _GUARDAR_PARTICIPACION,
            {
                "id": participacion.id,
                "estado": participacion.estado.value,
                "cobrado": participacion.monto_cobrado,
                "devuelto": participacion.monto_devuelto,
            },
        )

    # --- Ventas y anulaciones

    def ventas(self, cargo_id: uuid.UUID) -> list[Venta]:
        return [_venta(f) for f in self._sesion.execute(_VENTAS, {"cargo_id": cargo_id})]

    def venta(self, venta_id: uuid.UUID, *, bloquear: bool = False) -> Venta | None:
        f = self._sesion.execute(_VENTA_ID_BLOQUEAR if bloquear else _VENTA_ID, {"id": venta_id}).first()
        return None if f is None else _venta(f)

    def insertar_venta(self, venta: Venta, clave_pasarela: str) -> None:
        self._sesion.execute(
            _INSERTAR_VENTA,
            {
                "id": venta.id,
                "participacion_id": venta.participacion_id,
                "cargo_id": venta.cargo_id,
                "proveedor": PROVEEDOR,
                "buy_order": venta.buy_order,
                "session_id": venta.session_id,
                "token": venta.token,
                "monto": venta.monto,
                "estado": venta.estado.value,
                "clave": clave_pasarela,
                "total_confirmado_en": venta.total_confirmado_en,
                "ahora": venta.creado_en,
            },
        )

    def guardar_venta(self, venta: Venta) -> None:
        self._sesion.execute(
            _GUARDAR_VENTA,
            {
                "id": venta.id,
                "estado": venta.estado.value,
                "cerrada_en": venta.cerrada_en,
                "motivo_cierre": None if venta.motivo_cierre is None else venta.motivo_cierre.value,
                "tipo_tarjeta": None if venta.tipo_tarjeta is None else venta.tipo_tarjeta.value,
                "ultimos4": venta.ultimos4,
                "cuotas": venta.cuotas,
                "codigo": venta.codigo_autorizacion,
                "anulacion_total": venta.anulacion_total,
                "retorno": venta.retorno_recibido_en,
                "commit": venta.commit_intentado_en,
            },
        )

    def anulaciones(self, cargo_id: uuid.UUID) -> list[Anulacion]:
        return [_anulacion(f) for f in self._sesion.execute(_ANULACIONES, {"cargo_id": cargo_id})]

    def anulacion(self, anulacion_id: uuid.UUID, *, bloquear: bool = False) -> Anulacion | None:
        consulta = _ANULACION_ID_BLOQUEAR if bloquear else _ANULACION_ID
        f = self._sesion.execute(consulta, {"id": anulacion_id}).first()
        return None if f is None else _anulacion(f)

    def insertar_anulacion(self, anulacion: Anulacion, clave_pasarela: str) -> None:
        self._sesion.execute(
            _INSERTAR_ANULACION,
            {
                "id": anulacion.id,
                "participacion_id": anulacion.participacion_id,
                "cargo_id": anulacion.cargo_id,
                "proveedor": PROVEEDOR,
                "buy_order": anulacion.buy_order,
                "monto": anulacion.monto,
                "estado": anulacion.estado.value,
                "clave": clave_pasarela,
                "venta_id": anulacion.venta_id,
                "motivo": anulacion.motivo.value,
                "linea_id": anulacion.pedido_linea_id,
                "ahora": anulacion.solicitada_en,
            },
        )

    def guardar_anulacion(self, anulacion: Anulacion) -> None:
        self._sesion.execute(
            _GUARDAR_ANULACION,
            {
                "id": anulacion.id,
                "estado": anulacion.estado.value,
                "hecha_en": anulacion.hecha_en,
                "intentos": anulacion.intentos,
            },
        )
