"""Adaptador SQL de RepositorioPerfiles (MATU-36).

Trabaja con la sesión del contexto de grupo (sesion_de_grupo): app.usuario_id y app.grupo_id ya
están fijados. RLS acota la lectura al grupo y la escritura a admin y cuidador (migración 0009); el
filtro por grupo es además explícito. Los INSERT no usan RETURNING. Nada de este archivo escribe en
los logs: ni nombre_libre, ni cantidades, ni los errores de la base.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.modules.consumption.application.ports import Pagina, PerfilLeido, ProductoAdmitido
from app.modules.consumption.domain.perfil import Perfil, UnidadConsumo, nombre_de_pila

_COLUMNAS = (
    "SELECT p.id, p.persona_cuidada_id, p.producto_id, p.nombre_libre, p.unidad, p.tasa_unidades, p.tasa_dias,"
    " p.stock_unidades, p.stock_medido_en, p.dias_aviso, p.fecha_quiebre_estimada, p.activo, p.version,"
    " p.actualizado_por, pr.nombre AS producto_nombre, pr.presentacion AS producto_presentacion,"
    " u.nombre AS autor_nombre"
    " FROM perfil_consumo p"
    " LEFT JOIN producto pr ON pr.id = p.producto_id"
    " LEFT JOIN usuario u ON u.id = p.actualizado_por AND u.eliminado_en IS NULL"
    " WHERE p.grupo_id = :grupo_id AND p.persona_cuidada_id = :persona_id"
)

_OBTENER = text(_COLUMNAS + " AND p.id = :perfil_id")
# FOR UPDATE OF p: bloquea solo el perfil, no el producto ni la cuenta
_OBTENER_PARA_ESCRIBIR = text(_COLUMNAS + " AND p.id = :perfil_id FOR UPDATE OF p")

_LISTAR = (
    _COLUMNAS
    + " AND (CAST(:activo AS boolean) IS NULL OR p.activo = CAST(:activo AS boolean))"
    " AND (CAST(:desde_fecha AS date) IS NULL"
    " OR (p.fecha_quiebre_estimada, p.id) > (CAST(:desde_fecha AS date), CAST(:desde_id AS uuid)))"
    " ORDER BY p.fecha_quiebre_estimada, p.id LIMIT :limite"
)

_PRODUCTO = text(
    "SELECT id, nombre, presentacion, unidad FROM producto WHERE id = :id AND activo AND NOT requiere_receta"
)

_HAY_ACTIVO = text(
    "SELECT 1 FROM perfil_consumo WHERE grupo_id = :grupo_id AND persona_cuidada_id = :persona_id"
    " AND producto_id = :producto_id AND activo AND (CAST(:salvo AS uuid) IS NULL OR id <> CAST(:salvo AS uuid))"
)

_INSERTAR = text(
    "INSERT INTO perfil_consumo (id, grupo_id, persona_cuidada_id, producto_id, nombre_libre, unidad, tasa_unidades,"
    " tasa_dias, stock_unidades, stock_medido_en, fecha_quiebre_estimada, dias_aviso, activo, version,"
    " actualizado_por)"
    " VALUES (:id, :grupo_id, :persona_id, :producto_id, :nombre_libre, :unidad, :tasa_unidades, :tasa_dias,"
    " :stock_unidades, :stock_medido_en, :fecha_quiebre_estimada, :dias_aviso, :activo, :version,"
    " :actualizado_por)"
)

_ACTUALIZAR = text(
    "UPDATE perfil_consumo SET nombre_libre = :nombre_libre, tasa_unidades = :tasa_unidades,"
    " tasa_dias = :tasa_dias, stock_unidades = :stock_unidades, stock_medido_en = :stock_medido_en,"
    " fecha_quiebre_estimada = :fecha_quiebre_estimada, dias_aviso = :dias_aviso, activo = :activo,"
    " version = :version, actualizado_por = :actualizado_por"
    " WHERE id = :id AND grupo_id = :grupo_id AND version = :version - 1"
)

_DESCARTAR_ALERTAS = text(
    "UPDATE alerta_quiebre SET estado = 'descartada', cerrada_en = :ahora"
    " WHERE perfil_id = :perfil_id AND estado IN ('pendiente', 'notificada')"
)

_ELIMINAR = text("DELETE FROM perfil_consumo WHERE id = :id AND grupo_id = :grupo_id")


class EscrituraRechazada(RuntimeError):
    """La base no aplicó la escritura (otra transacción o RLS). Mensaje fijo, sin datos."""


def _perfil(fila: Row[Any]) -> PerfilLeido:
    producto = (
        None
        if fila.producto_id is None or fila.producto_nombre is None
        else ProductoAdmitido(
            id=fila.producto_id,
            nombre=fila.producto_nombre,
            presentacion=fila.producto_presentacion,
            unidad=UnidadConsumo(fila.unidad),
        )
    )
    return PerfilLeido(
        perfil=Perfil(
            id=fila.id,
            persona_cuidada_id=fila.persona_cuidada_id,
            producto_id=fila.producto_id,
            nombre_libre=fila.nombre_libre,
            unidad=UnidadConsumo(fila.unidad),
            tasa_unidades=int(fila.tasa_unidades),
            tasa_dias=int(fila.tasa_dias),
            stock_unidades=int(fila.stock_unidades),
            stock_medido_en=fila.stock_medido_en,
            dias_aviso=int(fila.dias_aviso),
            fecha_quiebre_estimada=fila.fecha_quiebre_estimada,
            activo=bool(fila.activo),
            version=int(fila.version),
            actualizado_por=fila.actualizado_por,
        ),
        producto=producto,
        actualizado_por_nombre=nombre_de_pila(fila.autor_nombre),
    )


class RepositorioPerfilesSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def listar(
        self, persona_id: uuid.UUID, activo: bool | None, despues_de: tuple[date, uuid.UUID] | None, limite: int
    ) -> Pagina:
        filas = self._sesion.execute(
            text(_LISTAR),
            {
                "grupo_id": self._grupo_id,
                "persona_id": persona_id,
                "activo": activo,
                "desde_fecha": None if despues_de is None else despues_de[0],
                "desde_id": None if despues_de is None else despues_de[1],
                # Una de más para saber si hay otra página
                "limite": limite + 1,
            },
        ).all()
        items = [_perfil(f) for f in filas[:limite]]
        siguiente = None
        if len(filas) > limite and items:
            ultimo = items[-1].perfil
            siguiente = (ultimo.fecha_quiebre_estimada, ultimo.id)
        return Pagina(items=items, siguiente=siguiente)

    def obtener(
        self, persona_id: uuid.UUID, perfil_id: uuid.UUID, *, para_escribir: bool = False
    ) -> PerfilLeido | None:
        consulta = _OBTENER_PARA_ESCRIBIR if para_escribir else _OBTENER
        fila = self._sesion.execute(
            consulta, {"grupo_id": self._grupo_id, "persona_id": persona_id, "perfil_id": perfil_id}
        ).first()
        return None if fila is None else _perfil(fila)

    def producto_admitido(self, producto_id: uuid.UUID) -> ProductoAdmitido | None:
        fila = self._sesion.execute(_PRODUCTO, {"id": producto_id}).first()
        if fila is None:
            return None
        return ProductoAdmitido(
            id=fila.id, nombre=fila.nombre, presentacion=fila.presentacion, unidad=UnidadConsumo(fila.unidad)
        )

    def hay_activo_del_producto(self, persona_id: uuid.UUID, producto_id: uuid.UUID, salvo: uuid.UUID | None) -> bool:
        fila = self._sesion.execute(
            _HAY_ACTIVO,
            {"grupo_id": self._grupo_id, "persona_id": persona_id, "producto_id": producto_id, "salvo": salvo},
        ).first()
        return fila is not None

    def _valores(self, perfil: Perfil) -> dict[str, Any]:
        return {
            "id": perfil.id,
            "grupo_id": self._grupo_id,
            "persona_id": perfil.persona_cuidada_id,
            "producto_id": perfil.producto_id,
            "nombre_libre": perfil.nombre_libre,
            "unidad": perfil.unidad.value,
            "tasa_unidades": perfil.tasa_unidades,
            "tasa_dias": perfil.tasa_dias,
            "stock_unidades": perfil.stock_unidades,
            "stock_medido_en": perfil.stock_medido_en,
            "fecha_quiebre_estimada": perfil.fecha_quiebre_estimada,
            "dias_aviso": perfil.dias_aviso,
            "activo": perfil.activo,
            "version": perfil.version,
            "actualizado_por": perfil.actualizado_por,
        }

    def insertar(self, grupo_id: uuid.UUID, perfil: Perfil) -> None:
        valores = self._valores(perfil)
        valores["grupo_id"] = grupo_id
        self._sesion.execute(_INSERTAR, valores)

    def actualizar(self, perfil: Perfil) -> None:
        resultado = self._sesion.execute(_ACTUALIZAR, self._valores(perfil))
        if getattr(resultado, "rowcount", 0) != 1:
            raise EscrituraRechazada("el perfil no se actualizó")

    def descartar_alertas_abiertas(self, perfil_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(_DESCARTAR_ALERTAS, {"perfil_id": perfil_id, "ahora": ahora})

    def eliminar(self, perfil_id: uuid.UUID) -> None:
        resultado = self._sesion.execute(_ELIMINAR, {"id": perfil_id, "grupo_id": self._grupo_id})
        if getattr(resultado, "rowcount", 0) != 1:
            raise EscrituraRechazada("el perfil no se borró")
