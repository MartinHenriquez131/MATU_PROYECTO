"""Las lecturas y escrituras de la consola de operación (MATU-81), como matu_app con app.rol = 'operacion'.

C34: ninguna consulta de este archivo lee persona_cuidada, direccion, pedido_entrega, consentimiento, plan_* ni
perfil_consumo, y la columna persona_cuidada_id del pedido solo se lee para la auditoría (nunca sale en una vista).
tests/modules/backoffice/test_consola_api.py captura las sentencias de cada ruta y lo verifica.

La nota y la resolución de una incidencia se leen y se escriben cifradas (decisión 471): este archivo nunca ve el
texto.

La línea de tiempo sale de pedido_transicion y de los instantes de las partes, el cobro, las anulaciones, los
retractos y las incidencias. Nunca de auditoria (C6).
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, TEXT, bindparam, text
from sqlalchemy.orm import Session

LIMITE_LISTA = 200

_MARCAS = (
    " EXISTS (SELECT 1 FROM incidencia i WHERE i.pedido_id = p.id AND i.estado <> 'resuelta') AS incidencia_abierta,"
    " EXISTS (SELECT 1 FROM cargo c JOIN transaccion_pasarela t ON t.cargo_id = c.id WHERE c.pedido_id = p.id"
    "  AND t.tipo = 'anulacion' AND t.estado IN ('iniciada', 'autorizando', 'error')) AS devolucion_sin_terminar,"
    " (SELECT count(*) FROM pedido_comercio pc WHERE pc.pedido_id = p.id) AS numero_partes"
)
_LISTA = text(
    "SELECT p.id, p.referencia, p.estado, p.pagado_en, p.entregado_en, p.total," + _MARCAS + " FROM pedido p"
    " WHERE p.pagado_en IS NOT NULL AND (CAST(:todos AS boolean) OR p.estado = ANY(:estados)"
    "  OR (CAST(:con_problema AS boolean) AND (EXISTS (SELECT 1 FROM incidencia i WHERE i.pedido_id = p.id"
    "  AND i.estado <> 'resuelta') OR EXISTS (SELECT 1 FROM cargo c JOIN transaccion_pasarela t ON t.cargo_id = c.id"
    "  WHERE c.pedido_id = p.id AND t.tipo = 'anulacion' AND t.estado IN ('iniciada', 'autorizando', 'error')))))"
    " ORDER BY p.pagado_en DESC, p.id DESC LIMIT :limite"
).bindparams(bindparam("estados", type_=ARRAY(TEXT)))
_BUSCAR = text(
    "SELECT p.id, p.referencia, p.estado, p.pagado_en, p.entregado_en, p.total," + _MARCAS + " FROM pedido p"
    " WHERE p.pagado_en IS NOT NULL AND (upper(p.referencia) = :ref OR EXISTS (SELECT 1 FROM pedido_comercio pc"
    "  WHERE pc.pedido_id = p.id AND upper(pc.referencia) = :ref))"
    " ORDER BY p.pagado_en DESC LIMIT 5"
)
_PEDIDO = text(
    "SELECT p.id, p.grupo_id, p.persona_cuidada_id, p.referencia, p.estado, p.pagado_en, p.entregado_en,"
    " p.subtotal_productos, p.costo_envio, p.total FROM pedido p WHERE p.id = :id AND p.pagado_en IS NOT NULL"
)
_PARTES = text(
    "SELECT pc.id, pc.referencia, pc.estado, co.nombre_fantasia, co.ficticio, pc.enviado_en, pc.preparando_en,"
    " pc.lista_en, pc.retirada_en, pc.cancelada_en, pc.motivo_cancelacion, pc.codigo_generado_en,"
    " pc.codigo_vigente AS con_hash, pc.codigo_expira_en, pc.codigo_usado_en, pc.codigo_bloqueado_en"
    " FROM pedido_comercio pc JOIN comercio co ON co.id = pc.comercio_id WHERE pc.pedido_id = :id"
    " ORDER BY pc.creado_en, pc.id"
)
_LINEAS = text(
    "SELECT l.id, l.pedido_comercio_id AS parte_id, pr.nombre, pr.presentacion, l.cantidad, l.precio_unitario,"
    " l.estado_linea, l.unidades_faltantes, l.monto_devuelto,"
    " EXISTS (SELECT 1 FROM transaccion_pasarela t WHERE t.pedido_linea_id = l.id AND t.tipo = 'anulacion'"
    "  AND t.estado IN ('iniciada', 'autorizando', 'error')) AS en_curso"
    " FROM pedido_linea l JOIN producto pr ON pr.id = l.producto_id WHERE l.pedido_id = :id"
    " ORDER BY l.creado_en, l.id"
)
_TRANSICIONES = text(
    "SELECT t.desde, t.hacia, t.actor_tipo, t.motivo, t.ocurrido_en, co.nombre_fantasia"
    " FROM pedido_transicion t LEFT JOIN comercio co ON t.actor_tipo = 'comercio' AND co.id = t.actor_ref"
    " WHERE t.pedido_id = :id ORDER BY t.ocurrido_en, t.id"
)
_CARGO = text("SELECT c.id, c.estado, c.monto_cobrado, c.monto_devuelto FROM cargo c WHERE c.pedido_id = :id")
_TRANSACCIONES = text(
    "SELECT t.id, t.tipo, t.buy_order, t.monto, t.estado, t.creado_en, t.retorno_recibido_en, t.cerrada_en,"
    " t.actualizado_en, t.motivo_anulacion, pr.nombre AS producto"
    " FROM transaccion_pasarela t LEFT JOIN pedido_linea l ON l.id = t.pedido_linea_id"
    " LEFT JOIN producto pr ON pr.id = l.producto_id WHERE t.cargo_id = :cargo ORDER BY t.creado_en, t.id"
)
_RETRACTOS_DEL_PEDIDO = text(
    "SELECT r.id, r.estado, r.solicitado_en, r.resuelto_en, r.motivo_rechazo FROM retracto r"
    " WHERE r.pedido_id = :id ORDER BY r.solicitado_en, r.id"
)
_INCIDENCIAS_DEL_PEDIDO = text(
    "SELECT i.tipo, i.creada_en, i.resuelta_en FROM incidencia i WHERE i.pedido_id = :id ORDER BY i.creada_en, i.id"
)
_VENTAS_PENDIENTES = text(
    "SELECT p.id AS pedido_id, p.referencia, t.buy_order, t.monto, t.creado_en FROM transaccion_pasarela t"
    " JOIN cargo c ON c.id = t.cargo_id JOIN pedido p ON p.id = c.pedido_id"
    " WHERE t.tipo = 'venta' AND t.estado IN ('iniciada', 'autorizando') AND t.creado_en <= :limite"
    " ORDER BY t.creado_en LIMIT 200"
)
_ANULACIONES_PENDIENTES = text(
    "SELECT p.id AS pedido_id, p.referencia, t.motivo_anulacion, t.monto, t.creado_en, t.intentos, t.estado"
    " FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id JOIN pedido p ON p.id = c.pedido_id"
    " WHERE t.tipo = 'anulacion' AND t.estado IN ('iniciada', 'autorizando', 'error') ORDER BY t.creado_en LIMIT 200"
)
_RETRACTO_DETALLE = text(
    "SELECT p.referencia, r.motivo_rechazo FROM retracto r JOIN pedido p ON p.id = r.pedido_id WHERE r.id = :id"
)
_RETRACTO_LINEAS = text(
    "SELECT rl.pedido_linea_id, pr.nombre, pr.presentacion, rl.cantidad, l.precio_unitario"
    " FROM retracto_linea rl JOIN pedido_linea l ON l.id = rl.pedido_linea_id"
    " JOIN producto pr ON pr.id = l.producto_id WHERE rl.retracto_id = :id ORDER BY l.creado_en, l.id"
)
_MOTIVO_RECHAZO = text(
    "UPDATE retracto SET motivo_rechazo = :motivo WHERE id = :id AND estado = 'rechazado' AND motivo_rechazo IS NULL"
)
# La nota y la resolución salen cifradas, con la clave de cada una (decisión 471): las descifra router_consola
_COLUMNAS_INCIDENCIA = (
    "i.id, i.pedido_id, p.referencia, i.tipo, i.estado, i.descripcion, i.clave_notas_id, i.resolucion,"
    " i.resolucion_clave_id, i.creada_en, i.resuelta_en, i.asignada_a, i.version"
)
_INCIDENCIAS = text(
    "SELECT " + _COLUMNAS_INCIDENCIA + " FROM incidencia i JOIN pedido p ON p.id = i.pedido_id"
    " WHERE (CAST(:estado AS text) IS NULL OR i.estado = :estado) ORDER BY i.creada_en DESC, i.id DESC LIMIT 200"
)
_INCIDENCIA = text(
    "SELECT " + _COLUMNAS_INCIDENCIA + ", p.grupo_id, p.persona_cuidada_id FROM incidencia i"
    " JOIN pedido p ON p.id = i.pedido_id WHERE i.id = :id"
)
# El id lo pone la aplicación: va en el AAD de la nota cifrada
_CREAR_INCIDENCIA = text(
    "INSERT INTO incidencia (id, pedido_id, tipo, descripcion, clave_notas_id, creada_por, asignada_a, creada_en)"
    " VALUES (:id, :pedido, :tipo, :descripcion, :clave, app_usuario(), :asignada, :ahora) RETURNING id"
)
# Sin resolución nueva, la guardada (cifrada) no cambia
_EDITAR_INCIDENCIA = text(
    "UPDATE incidencia SET estado = :estado, asignada_a = :asignada,"
    " resolucion = COALESCE(CAST(:resolucion AS bytea), resolucion),"
    " resolucion_clave_id = COALESCE(CAST(:clave AS uuid), resolucion_clave_id),"
    " resuelta_en = :resuelta_en WHERE id = :id AND version = :version RETURNING id"
)
_CATALOGO = text(
    "SELECT o.id, o.precio, o.stock, o.disponible, o.actualizado_en, co.nombre_fantasia, co.ficticio, pr.nombre,"
    " pr.presentacion FROM oferta o JOIN comercio co ON co.id = o.comercio_id JOIN producto pr ON pr.id = o.producto_id"
    " WHERE co.estado = 'activo' ORDER BY co.nombre_fantasia, pr.nombre, pr.presentacion, o.id"
)
_OFERTA = text(
    "SELECT o.id, o.precio, o.stock, o.disponible, o.actualizado_en, co.nombre_fantasia, co.ficticio, pr.nombre,"
    " pr.presentacion FROM oferta o JOIN comercio co ON co.id = o.comercio_id JOIN producto pr ON pr.id = o.producto_id"
    " WHERE o.id = :id FOR UPDATE OF o"
)
_CAMBIAR_OFERTA = text(
    "UPDATE oferta SET precio = :precio, stock = :stock, disponible = :disponible,"
    " actualizado_en = greatest(:ahora, actualizado_en + interval '1 microsecond')"
    " WHERE id = :id"
)


def lista(sesion: Session, estados: Sequence[str], todos: bool, con_problema: bool) -> list[Any]:
    return list(sesion.execute(_LISTA, {"estados": list(estados), "todos": todos, "con_problema": con_problema,
                                        "limite": LIMITE_LISTA + 1}))


def buscar(sesion: Session, referencia: str) -> list[Any]:
    return list(sesion.execute(_BUSCAR, {"ref": referencia.strip().upper()}))


def pedido(sesion: Session, pedido_id: uuid.UUID) -> Any:
    return sesion.execute(_PEDIDO, {"id": pedido_id}).first()


def partes(sesion: Session, pedido_id: uuid.UUID) -> list[Any]:
    return list(sesion.execute(_PARTES, {"id": pedido_id}))


def lineas(sesion: Session, pedido_id: uuid.UUID) -> list[Any]:
    return list(sesion.execute(_LINEAS, {"id": pedido_id}))


def transiciones(sesion: Session, pedido_id: uuid.UUID) -> list[Any]:
    return list(sesion.execute(_TRANSICIONES, {"id": pedido_id}))


def cargo(sesion: Session, pedido_id: uuid.UUID) -> Any:
    return sesion.execute(_CARGO, {"id": pedido_id}).first()


def transacciones(sesion: Session, cargo_id: uuid.UUID) -> list[Any]:
    return list(sesion.execute(_TRANSACCIONES, {"cargo": cargo_id}))


def retractos_del_pedido(sesion: Session, pedido_id: uuid.UUID) -> list[Any]:
    return list(sesion.execute(_RETRACTOS_DEL_PEDIDO, {"id": pedido_id}))


def incidencias_del_pedido(sesion: Session, pedido_id: uuid.UUID) -> list[Any]:
    return list(sesion.execute(_INCIDENCIAS_DEL_PEDIDO, {"id": pedido_id}))


def ventas_pendientes(sesion: Session, limite: datetime) -> list[Any]:
    return list(sesion.execute(_VENTAS_PENDIENTES, {"limite": limite}))


def anulaciones_pendientes(sesion: Session) -> list[Any]:
    return list(sesion.execute(_ANULACIONES_PENDIENTES))


def retracto_detalle(sesion: Session, retracto_id: uuid.UUID) -> tuple[Any, list[Any]]:
    return (sesion.execute(_RETRACTO_DETALLE, {"id": retracto_id}).first(),
            list(sesion.execute(_RETRACTO_LINEAS, {"id": retracto_id})))


def fijar_motivo_rechazo(sesion: Session, retracto_id: uuid.UUID, motivo: str) -> None:
    sesion.execute(_MOTIVO_RECHAZO, {"id": retracto_id, "motivo": motivo})


def incidencias(sesion: Session, estado: str | None) -> list[Any]:
    return list(sesion.execute(_INCIDENCIAS, {"estado": estado}))


def incidencia(sesion: Session, incidencia_id: uuid.UUID) -> Any:
    return sesion.execute(_INCIDENCIA, {"id": incidencia_id}).first()


def crear_incidencia(sesion: Session, incidencia_id: uuid.UUID, pedido_id: uuid.UUID, tipo: str, descripcion: bytes,
                     clave_id: uuid.UUID, asignada: uuid.UUID | None, ahora: datetime) -> uuid.UUID:
    """``descripcion`` ya cifrada con la clave ``clave_id`` (app/shared/notas_operacion.py)."""
    return uuid.UUID(str(sesion.execute(_CREAR_INCIDENCIA, {
        "id": incidencia_id, "pedido": pedido_id, "tipo": tipo, "descripcion": descripcion, "clave": clave_id,
        "asignada": asignada, "ahora": ahora,
    }).scalar_one()))


def editar_incidencia(sesion: Session, incidencia_id: uuid.UUID, version: int, estado: str,
                      asignada: uuid.UUID | None, resolucion: bytes | None, clave_id: uuid.UUID | None,
                      resuelta_en: datetime | None) -> bool:
    """``resolucion`` ya cifrada con ``clave_id``, o None para dejar la guardada."""
    return sesion.execute(_EDITAR_INCIDENCIA, {
        "id": incidencia_id, "version": version, "estado": estado, "asignada": asignada, "resolucion": resolucion,
        "clave": clave_id, "resuelta_en": resuelta_en,
    }).first() is not None


def catalogo(sesion: Session) -> list[Any]:
    return list(sesion.execute(_CATALOGO))


def oferta(sesion: Session, oferta_id: uuid.UUID) -> Any:
    return sesion.execute(_OFERTA, {"id": oferta_id}).first()


def cambiar_oferta(sesion: Session, oferta_id: uuid.UUID, precio: int, stock: int, disponible: bool,
                   ahora: datetime) -> None:
    sesion.execute(_CAMBIAR_OFERTA, {"id": oferta_id, "precio": precio, "stock": stock, "disponible": disponible,
                                     "ahora": ahora})
