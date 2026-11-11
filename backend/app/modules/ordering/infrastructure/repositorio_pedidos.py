"""Adaptador SQL de RepositorioPedidos (MATU-61, migración 0023).

Con la sesión del contexto de grupo (sesion_de_grupo): RLS acota pedido, líneas, reglas, entrega, transiciones y
partes por comercio al grupo, y solo admin y cuidador escriben (app_escribe_pedido). El filtro por grupo es además
explícito. La entrega no la ve el observador (app_ve_entrega): para él, la consulta no la trae.

Nada del pedido va a los logs: ni productos, ni cantidades, ni montos, ni la dirección, ni el teléfono. Las ofertas
se leen como en el catálogo (MATU-59): publicadas, de un comercio activo y de un producto activo sin receta.
"""

import secrets
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.modules.care_circle.domain.personas import FINALIDAD_DESPACHO, EstadoAutorizacion, estado_autorizacion
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion
from app.modules.ordering.application.ports import Autorizacion, DireccionPersona, Transicion
from app.modules.ordering.domain.estados import SIN_PAGAR, Estado
from app.modules.ordering.domain.pedido import (
    ESTADO_LINEA_PENDIENTE,
    ESTADO_LINEA_SALIO,
    REGLA_POR_OMISION,
    Comercio,
    Entrega,
    Linea,
    LineaDelCarrito,
    Oferta,
    Pedido,
    Producto,
    Regla,
)
from app.shared.celular import normalizar_celular

_SIN_PAGAR = ", ".join(f"'{e.value}'" for e in sorted(SIN_PAGAR))
# Referencia opaca de cada parte por comercio (C22): aleatoria, nunca derivada del pedido ni del grupo
BYTES_REFERENCIA = 16

_PEDIDO = (
    "SELECT p.id, p.grupo_id, p.persona_cuidada_id, p.estado, p.version, p.costo_envio, p.total_confirmado_en,"
    " p.total_vence_en, p.creado_en, p.actualizado_en"
    " FROM pedido p JOIN persona_cuidada pc ON pc.id = p.persona_cuidada_id AND pc.grupo_id = p.grupo_id"
    " WHERE p.id = :pedido_id AND p.grupo_id = :grupo_id AND pc.eliminado_en IS NULL"
)
_CARGAR = text(_PEDIDO)
_CARGAR_BLOQUEADO = text(_PEDIDO + " FOR UPDATE OF p")
_LINEAS = text(
    "SELECT l.id, l.cantidad, l.precio_carrito, l.precio_unitario, l.estado_linea,"
    " l.retracto_pierde_al_abrir AS retracto_copiado, l.oferta_id, l.oferta_carrito_id,"
    " pr.id AS producto_id, pr.nombre, pr.presentacion, pr.unidad, pr.unidades_por_envase,"
    " pr.retracto_pierde_al_abrir,"
    " c.id AS comercio_id, c.nombre_fantasia, c.ficticio,"
    " cc.id AS carrito_comercio_id, cc.nombre_fantasia AS carrito_nombre, cc.ficticio AS carrito_ficticio,"
    " r.accion"
    " FROM pedido_linea l"
    " JOIN producto pr ON pr.id = l.producto_id"
    " JOIN oferta o ON o.id = l.oferta_id JOIN comercio c ON c.id = o.comercio_id"
    " JOIN oferta oc ON oc.id = l.oferta_carrito_id JOIN comercio cc ON cc.id = oc.comercio_id"
    " LEFT JOIN regla_sustitucion r ON r.pedido_id = l.pedido_id AND r.producto_id = l.producto_id"
    " WHERE l.pedido_id = :pedido_id ORDER BY l.creado_en, l.id"
)
_ENTREGA = text(
    "SELECT calle, numero, depto, comuna, region, referencia, telefono_contacto, telefono_origen"
    " FROM pedido_entrega WHERE pedido_id = :pedido_id"
)
_EN_CURSO = text(
    "SELECT id FROM pedido WHERE grupo_id = :grupo_id AND persona_cuidada_id = :persona_id"
    f" AND estado IN ({_SIN_PAGAR}) ORDER BY creado_en DESC, id LIMIT 1"
)
_SIN_PAGAR_DE = text(
    "SELECT id FROM pedido WHERE grupo_id = :grupo_id AND persona_cuidada_id = :persona_id"
    f" AND estado IN ({_SIN_PAGAR}) ORDER BY id FOR UPDATE"
)
_PERSONA = text(
    "SELECT 1 FROM persona_cuidada WHERE id = :persona_id AND grupo_id = :grupo_id AND eliminado_en IS NULL"
)
_OFERTAS = (
    "SELECT o.id AS oferta_id, o.precio, p.id AS producto_id, p.nombre, p.presentacion, p.unidad,"
    " p.unidades_por_envase, p.retracto_pierde_al_abrir, co.id AS comercio_id, co.nombre_fantasia, co.ficticio"
    " FROM oferta o JOIN producto p ON p.id = o.producto_id JOIN categoria_cuidado c ON c.id = p.categoria_id"
    " JOIN comercio co ON co.id = o.comercio_id"
    " WHERE o.disponible AND p.activo AND NOT p.requiere_receta AND c.activa AND co.estado = 'activo'"
)
_OFERTAS_POR_ID = text(_OFERTAS + " AND o.id = ANY(:ids)")
_OFERTAS_POR_PRODUCTO = text(_OFERTAS + " AND p.id = ANY(:ids)")
_INSERTAR_PEDIDO = text(
    "INSERT INTO pedido (id, grupo_id, persona_cuidada_id, estado, version, subtotal_productos, costo_envio, total,"
    " creado_por, creado_en, actualizado_en)"
    " VALUES (:id, :grupo_id, :persona_id, 'borrador', 1, :subtotal, :costo_envio, :total, :usuario_id, :ahora, :ahora)"
    f" ON CONFLICT (persona_cuidada_id) WHERE estado IN ({_SIN_PAGAR}) DO NOTHING RETURNING id"
)
_INSERTAR_LINEA = text(
    "INSERT INTO pedido_linea (id, pedido_id, oferta_id, producto_id, cantidad, precio_unitario, precio_carrito,"
    " oferta_carrito_id, creado_en)"
    " VALUES (:id, :pedido_id, :oferta_id, :producto_id, :cantidad, :precio, :precio, :oferta_id, :creado_en)"
)
_ACTUALIZAR_CARRITO = text(
    "UPDATE pedido_linea SET oferta_id = :oferta_id, oferta_carrito_id = :oferta_id, precio_unitario = :precio,"
    " precio_carrito = :precio, cantidad = :cantidad, estado_linea = 'pendiente', retracto_pierde_al_abrir = NULL,"
    " pedido_comercio_id = NULL WHERE id = :id AND pedido_id = :pedido_id"
)
_BORRAR_LINEAS_FUERA = text("DELETE FROM pedido_linea WHERE pedido_id = :pedido_id AND NOT (id = ANY(:ids))")
_BORRAR_REGLAS_FUERA = text(
    "DELETE FROM regla_sustitucion WHERE pedido_id = :pedido_id AND NOT (producto_id = ANY(:productos))"
)
_INSERTAR_REGLA = text(
    "INSERT INTO regla_sustitucion (pedido_id, producto_id, accion) VALUES (:pedido_id, :producto_id, :accion)"
    " ON CONFLICT (pedido_id, producto_id) DO NOTHING"
)
_GUARDAR_REGLA = text(
    "INSERT INTO regla_sustitucion (pedido_id, producto_id, accion) VALUES (:pedido_id, :producto_id, :accion)"
    " ON CONFLICT (pedido_id, producto_id) DO UPDATE SET accion = EXCLUDED.accion"
    " WHERE regla_sustitucion.accion IS DISTINCT FROM EXCLUDED.accion"
)
_ENCABEZADO = text(
    "UPDATE pedido SET estado = :estado, version = :version, subtotal_productos = :subtotal,"
    " costo_envio = :costo_envio, total = :total, total_confirmado_en = :confirmado_en, total_vence_en = :vence_en"
    " WHERE id = :pedido_id AND grupo_id = :grupo_id"
)
_TOTALES_BORRADOR = text(
    "UPDATE pedido SET version = version + 1, subtotal_productos = :subtotal, total = :subtotal + costo_envio"
    " WHERE id = :pedido_id AND grupo_id = :grupo_id"
)
_LINEA = text(
    "UPDATE pedido_linea SET oferta_id = :oferta_id, precio_unitario = :precio, estado_linea = :estado_linea,"
    " retracto_pierde_al_abrir = :retracto WHERE id = :id AND pedido_id = :pedido_id"
)
_LINEA_PARTE = text("UPDATE pedido_linea SET pedido_comercio_id = :parte WHERE id = :id AND pedido_id = :pedido_id")
_BORRAR_PARTES = text("DELETE FROM pedido_comercio WHERE pedido_id = :pedido_id AND grupo_id = :grupo_id")
_INSERTAR_PARTE = text(
    "INSERT INTO pedido_comercio (id, grupo_id, pedido_id, comercio_id, referencia, creado_en)"
    " VALUES (:id, :grupo_id, :pedido_id, :comercio_id, :referencia, :ahora)"
)
_BORRAR_ENTREGA = text("DELETE FROM pedido_entrega WHERE pedido_id = :pedido_id")
_GUARDAR_ENTREGA = text(
    "INSERT INTO pedido_entrega (pedido_id, calle, numero, depto, comuna, region, referencia, telefono_contacto,"
    " telefono_origen) VALUES (:pedido_id, :calle, :numero, :depto, :comuna, :region, :referencia, :telefono,"
    " :origen)"
    " ON CONFLICT (pedido_id) DO UPDATE SET calle = EXCLUDED.calle, numero = EXCLUDED.numero, depto = EXCLUDED.depto,"
    " comuna = EXCLUDED.comuna, region = EXCLUDED.region, referencia = EXCLUDED.referencia,"
    " telefono_contacto = EXCLUDED.telefono_contacto, telefono_origen = EXCLUDED.telefono_origen"
)
_TRANSICION = text(
    "INSERT INTO pedido_transicion (pedido_id, desde, hacia, actor_tipo, actor_ref, motivo, ocurrido_en)"
    " VALUES (:pedido_id, :desde, :hacia, :actor_tipo, :actor_ref, :motivo, :ocurrido_en)"
)
_DIRECCION = text(
    "SELECT d.calle, d.numero, d.depto, d.comuna, d.region, d.referencia"
    " FROM persona_cuidada p JOIN direccion d ON d.id = p.direccion_entrega_id AND d.grupo_id = p.grupo_id"
    " WHERE p.id = :persona_id AND p.grupo_id = :grupo_id AND p.eliminado_en IS NULL"
)
_CELULAR = text("SELECT telefono FROM usuario WHERE id = app_usuario() AND celular_verificado_en IS NOT NULL")


def _comercio(id_: uuid.UUID, nombre: str, ficticio: bool) -> Comercio:
    return Comercio(id=id_, nombre_fantasia=nombre, ficticio=ficticio)


def _producto(f: Row[Any]) -> Producto:
    return Producto(
        id=f.producto_id,
        nombre=f.nombre,
        presentacion=f.presentacion,
        unidad=f.unidad,
        unidades_por_envase=f.unidades_por_envase,
        retracto_pierde_al_abrir=f.retracto_pierde_al_abrir,
    )


def _oferta(f: Row[Any]) -> Oferta:
    return Oferta(
        id=f.oferta_id,
        producto=_producto(f),
        comercio=_comercio(f.comercio_id, f.nombre_fantasia, f.ficticio),
        precio=int(f.precio),
    )


def _linea(f: Row[Any]) -> Linea:
    return Linea(
        id=f.id,
        producto=_producto(f),
        cantidad=f.cantidad,
        regla=Regla(f.accion) if f.accion is not None else REGLA_POR_OMISION,
        oferta_carrito_id=f.oferta_carrito_id,
        comercio_carrito=_comercio(f.carrito_comercio_id, f.carrito_nombre, f.carrito_ficticio),
        precio_carrito=int(f.precio_carrito),
        oferta_id=f.oferta_id,
        comercio=_comercio(f.comercio_id, f.nombre_fantasia, f.ficticio),
        precio_unitario=int(f.precio_unitario),
        salio=f.estado_linea == ESTADO_LINEA_SALIO,
        retracto_copiado=f.retracto_copiado,
    )


class RepositorioPedidosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    # --- Lectura

    def autorizacion_despacho(self, persona_id: uuid.UUID, ahora: datetime) -> Autorizacion | None:
        persona = persona_con_autorizacion(self._sesion, self._grupo_id, persona_id, FINALIDAD_DESPACHO, bloquear=True)
        if persona is None:
            return None
        estado = estado_autorizacion(persona.autorizacion, ahora)
        if estado is EstadoAutorizacion.VIGENTE:
            return Autorizacion.VIGENTE
        if estado is EstadoAutorizacion.REVISION_VENCIDA:
            return Autorizacion.REVISION_VENCIDA
        return Autorizacion.SIN_AUTORIZACION

    def persona_del_grupo(self, persona_id: uuid.UUID) -> bool:
        return (
            self._sesion.execute(_PERSONA, {"persona_id": persona_id, "grupo_id": self._grupo_id}).first() is not None
        )

    def en_curso(self, persona_id: uuid.UUID) -> uuid.UUID | None:
        fila = self._sesion.execute(_EN_CURSO, {"persona_id": persona_id, "grupo_id": self._grupo_id}).first()
        return None if fila is None else fila.id

    def sin_pagar_de(self, persona_id: uuid.UUID) -> list[uuid.UUID]:
        filas = self._sesion.execute(_SIN_PAGAR_DE, {"persona_id": persona_id, "grupo_id": self._grupo_id}).all()
        return [f.id for f in filas]

    def cargar(self, pedido_id: uuid.UUID, *, bloquear: bool = False) -> Pedido | None:
        consulta = _CARGAR_BLOQUEADO if bloquear else _CARGAR
        f = self._sesion.execute(consulta, {"pedido_id": pedido_id, "grupo_id": self._grupo_id}).first()
        if f is None:
            return None
        lineas = tuple(_linea(x) for x in self._sesion.execute(_LINEAS, {"pedido_id": pedido_id}))
        e = self._sesion.execute(_ENTREGA, {"pedido_id": pedido_id}).first()
        entrega = (
            None
            if e is None
            else Entrega(
                calle=e.calle,
                numero=e.numero,
                depto=e.depto,
                comuna=e.comuna,
                region=e.region,
                referencia=e.referencia,
                telefono=e.telefono_contacto,
                telefono_origen=e.telefono_origen,
            )
        )
        return Pedido(
            id=f.id,
            grupo_id=f.grupo_id,
            persona_id=f.persona_cuidada_id,
            estado=Estado(f.estado),
            version=f.version,
            costo_envio=int(f.costo_envio),
            total_confirmado_en=f.total_confirmado_en,
            total_vence_en=f.total_vence_en,
            creado_en=f.creado_en,
            actualizado_en=f.actualizado_en,
            lineas=lineas,
            entrega=entrega,
        )

    def ofertas(self, oferta_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Oferta]:
        ids = list(dict.fromkeys(oferta_ids))
        if not ids:
            return {}
        return {f.oferta_id: _oferta(f) for f in self._sesion.execute(_OFERTAS_POR_ID, {"ids": ids})}

    def ofertas_de_productos(self, producto_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, list[Oferta]]:
        ids = list(dict.fromkeys(producto_ids))
        resultado: dict[uuid.UUID, list[Oferta]] = {}
        if not ids:
            return resultado
        for f in self._sesion.execute(_OFERTAS_POR_PRODUCTO, {"ids": ids}):
            resultado.setdefault(f.producto_id, []).append(_oferta(f))
        return resultado

    def direccion_de(self, persona_id: uuid.UUID) -> DireccionPersona | None:
        f = self._sesion.execute(_DIRECCION, {"persona_id": persona_id, "grupo_id": self._grupo_id}).first()
        if f is None:
            return None
        return DireccionPersona(
            calle=f.calle, numero=f.numero, depto=f.depto, comuna=f.comuna, region=f.region, referencia=f.referencia
        )

    def celular_verificado(self) -> str | None:
        f = self._sesion.execute(_CELULAR).first()
        return None if f is None or f.telefono is None else normalizar_celular(f.telefono)

    # --- Escritura

    def crear(self, pedido: Pedido, lineas: list[LineaDelCarrito], usuario_id: uuid.UUID) -> bool:
        subtotal = sum(linea.cantidad * linea.precio_carrito for linea in lineas)
        creado = self._sesion.execute(
            _INSERTAR_PEDIDO,
            {
                "id": pedido.id,
                "grupo_id": pedido.grupo_id,
                "persona_id": pedido.persona_id,
                "subtotal": subtotal,
                "costo_envio": pedido.costo_envio,
                "total": subtotal + pedido.costo_envio,
                "usuario_id": usuario_id,
                "ahora": pedido.creado_en,
            },
        ).first()
        if creado is None:
            return False
        self._insertar_lineas(pedido.id, lineas, pedido.creado_en)
        self.transicion(pedido.id, Transicion(None, Estado.BORRADOR, usuario_id, None, pedido.creado_en))
        return True

    def reemplazar_carrito(self, pedido: Pedido, lineas: list[LineaDelCarrito], ahora: datetime) -> None:
        conservadas = [linea for linea in lineas if linea.id is not None]
        nuevas = [linea for linea in lineas if linea.id is None]
        self._sesion.execute(_BORRAR_LINEAS_FUERA, {"pedido_id": pedido.id, "ids": [x.id for x in conservadas]})
        self._sesion.execute(
            _BORRAR_REGLAS_FUERA, {"pedido_id": pedido.id, "productos": [x.oferta.producto.id for x in lineas]}
        )
        for linea in conservadas:
            self._sesion.execute(
                _ACTUALIZAR_CARRITO,
                {
                    "id": linea.id,
                    "pedido_id": pedido.id,
                    "oferta_id": linea.oferta.id,
                    "precio": linea.precio_carrito,
                    "cantidad": linea.cantidad,
                },
            )
        self._insertar_lineas(pedido.id, nuevas, ahora)
        subtotal = sum(linea.cantidad * linea.precio_carrito for linea in lineas)
        self._sesion.execute(
            _TOTALES_BORRADOR, {"pedido_id": pedido.id, "grupo_id": self._grupo_id, "subtotal": subtotal}
        )

    def guardar(self, pedido: Pedido, *, rehacer_partes: bool = False) -> None:
        self._sesion.execute(
            _ENCABEZADO,
            {
                "pedido_id": pedido.id,
                "grupo_id": self._grupo_id,
                "estado": pedido.estado.value,
                "version": pedido.version,
                "subtotal": pedido.subtotal_productos,
                "costo_envio": pedido.costo_envio,
                "total": pedido.subtotal_productos + pedido.costo_envio,
                "confirmado_en": pedido.total_confirmado_en,
                "vence_en": pedido.total_vence_en,
            },
        )
        partes: dict[uuid.UUID, uuid.UUID] = {}
        if rehacer_partes:
            self._sesion.execute(_BORRAR_PARTES, {"pedido_id": pedido.id, "grupo_id": self._grupo_id})
            if pedido.confirmado:
                for comercio_id in sorted({x.comercio.id for x in pedido.lineas_que_quedan()}, key=str):
                    parte = uuid.uuid4()
                    self._sesion.execute(
                        _INSERTAR_PARTE,
                        {
                            "id": parte,
                            "grupo_id": self._grupo_id,
                            "pedido_id": pedido.id,
                            "comercio_id": comercio_id,
                            "referencia": secrets.token_urlsafe(BYTES_REFERENCIA),
                            "ahora": pedido.total_confirmado_en,
                        },
                    )
                    partes[comercio_id] = parte
        for linea in pedido.lineas:
            self._sesion.execute(
                _LINEA,
                {
                    "id": linea.id,
                    "pedido_id": pedido.id,
                    "oferta_id": linea.oferta_id,
                    "precio": linea.precio_unitario,
                    "estado_linea": ESTADO_LINEA_SALIO if linea.salio else ESTADO_LINEA_PENDIENTE,
                    "retracto": linea.retracto_copiado,
                },
            )
            if rehacer_partes:
                parte_id = None if linea.salio else partes.get(linea.comercio.id)
                self._sesion.execute(_LINEA_PARTE, {"id": linea.id, "pedido_id": pedido.id, "parte": parte_id})
            self._sesion.execute(
                _GUARDAR_REGLA, {"pedido_id": pedido.id, "producto_id": linea.producto.id, "accion": linea.regla.value}
            )
        if pedido.entrega is None:
            self._sesion.execute(_BORRAR_ENTREGA, {"pedido_id": pedido.id})
        else:
            e = pedido.entrega
            self._sesion.execute(
                _GUARDAR_ENTREGA,
                {
                    "pedido_id": pedido.id,
                    "calle": e.calle,
                    "numero": e.numero,
                    "depto": e.depto,
                    "comuna": e.comuna,
                    "region": e.region,
                    "referencia": e.referencia,
                    "telefono": e.telefono,
                    "origen": e.telefono_origen,
                },
            )

    def transicion(self, pedido_id: uuid.UUID, transicion: Transicion) -> None:
        self._sesion.execute(
            _TRANSICION,
            {
                "pedido_id": pedido_id,
                "desde": None if transicion.desde is None else transicion.desde.value,
                "hacia": transicion.hacia.value,
                "actor_tipo": "sistema" if transicion.actor_usuario is None else "usuario",
                "actor_ref": transicion.actor_usuario,
                "motivo": None if transicion.motivo is None else transicion.motivo.value,
                "ocurrido_en": transicion.ocurrido_en,
            },
        )

    def _insertar_lineas(self, pedido_id: uuid.UUID, lineas: list[LineaDelCarrito], desde: datetime) -> None:
        # creado_en ordena las líneas como llegaron: un microsegundo entre cada una, desde el instante del Reloj
        for i, linea in enumerate(lineas):
            self._sesion.execute(
                _INSERTAR_LINEA,
                {
                    "id": uuid.uuid4(),
                    "pedido_id": pedido_id,
                    "oferta_id": linea.oferta.id,
                    "producto_id": linea.oferta.producto.id,
                    "cantidad": linea.cantidad,
                    "precio": linea.precio_carrito,
                    "creado_en": desde + timedelta(microseconds=i),
                },
            )
            self._sesion.execute(
                _INSERTAR_REGLA,
                {"pedido_id": pedido_id, "producto_id": linea.oferta.producto.id, "accion": REGLA_POR_OMISION.value},
            )
