"""Adaptador SQL de RepositorioAlertas (MATU-37).

Sesión del contexto de grupo (sesion_de_grupo). RLS de la migración 0011: leen los cuatro roles,
cierran admin y cuidador (alerta_cerrar y alerta_cerrar_sin_aviso), y el trigger alerta_transicion
fija las transiciones. El filtro por grupo y persona es además explícito. Nada de este archivo
escribe en los logs.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.modules.consumption.application.ports import AlertaLeida, InsumoEnVentana, PaginaAlertas
from app.modules.consumption.domain.alerta import EstadoAlerta
from app.modules.consumption.infrastructure.repositorio_perfiles import COLUMNAS_PERFIL, perfil_leido

_ALERTA = "a.id, a.perfil_id, a.fecha_prevista, a.estado, a.creada_en, a.notificada_en, a.cerrada_en"
_DE_LA_PERSONA = (
    " FROM alerta_quiebre a JOIN perfil_consumo p ON p.id = a.perfil_id"
    " WHERE p.grupo_id = :grupo_id AND p.persona_cuidada_id = :persona_id"
)

_EN_VENTANA = text(
    "SELECT q.*, a.id AS a_id, a.estado AS a_estado, a.creada_en AS a_creada_en,"
    " a.notificada_en AS a_notificada_en, a.cerrada_en AS a_cerrada_en"
    " FROM (" + COLUMNAS_PERFIL + " AND p.activo AND p.fecha_quiebre_estimada - CAST(:hoy AS date) <= p.dias_aviso) q"
    " LEFT JOIN alerta_quiebre a ON a.perfil_id = q.id AND a.fecha_prevista = q.fecha_quiebre_estimada"
    " ORDER BY q.fecha_quiebre_estimada, q.id"
)

_LISTAR = text(
    "SELECT " + _ALERTA + _DE_LA_PERSONA + " AND a.estado = ANY(:estados)"
    " AND (CAST(:desde_fecha AS date) IS NULL"
    " OR (a.fecha_prevista, a.id) > (CAST(:desde_fecha AS date), CAST(:desde_id AS uuid)))"
    " ORDER BY a.fecha_prevista, a.id LIMIT :limite"
)

_OBTENER = text("SELECT " + _ALERTA + _DE_LA_PERSONA + " AND a.id = :alerta_id FOR UPDATE OF a")

_DE_LA_FECHA = text(
    "SELECT " + _ALERTA + " FROM alerta_quiebre a WHERE a.perfil_id = :perfil_id AND a.fecha_prevista = :fecha"
    " FOR UPDATE"
)

_CERRAR = text(
    "UPDATE alerta_quiebre SET estado = :estado, cerrada_en = :ahora"
    " WHERE id = :id AND estado IN ('pendiente', 'notificada')"
)

_INSERTAR_CERRADA = text(
    "INSERT INTO alerta_quiebre (id, perfil_id, fecha_prevista, estado, creada_en, cerrada_en)"
    " VALUES (:id, :perfil_id, :fecha, :estado, :ahora, :ahora)"
)

_DECLARAR = text(
    "INSERT INTO reposicion (id, perfil_id, cantidad_unidades, origen, ocurrida_en, registrada_por)"
    " VALUES (:id, :perfil_id, :cantidad, 'declarada', :ocurrida_en, :usuario_id)"
)

_UNA = text("SELECT " + _ALERTA + " FROM alerta_quiebre a WHERE a.id = :id")


class AlertaNoEscrita(RuntimeError):
    """La base no aplicó el cambio. Mensaje fijo, sin datos."""


def alerta_leida(fila: Row[Any], prefijo: str = "") -> AlertaLeida:
    return AlertaLeida(
        id=getattr(fila, prefijo + "id"),
        perfil_id=fila.perfil_id if not prefijo else fila.id,
        fecha_prevista=fila.fecha_prevista if not prefijo else fila.fecha_quiebre_estimada,
        estado=EstadoAlerta(getattr(fila, prefijo + "estado")),
        creada_en=getattr(fila, prefijo + "creada_en"),
        notificada_en=getattr(fila, prefijo + "notificada_en"),
        cerrada_en=getattr(fila, prefijo + "cerrada_en"),
    )


class RepositorioAlertasSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def en_ventana(self, persona_id: uuid.UUID, hoy: date) -> list[InsumoEnVentana]:
        filas = self._sesion.execute(
            _EN_VENTANA, {"grupo_id": self._grupo_id, "persona_id": persona_id, "hoy": hoy}
        ).all()
        return [
            InsumoEnVentana(leido=perfil_leido(f), alerta=None if f.a_id is None else alerta_leida(f, prefijo="a_"))
            for f in filas
        ]

    def listar(
        self,
        persona_id: uuid.UUID,
        estados: frozenset[EstadoAlerta],
        despues_de: tuple[date, uuid.UUID] | None,
        limite: int,
    ) -> PaginaAlertas:
        filas = self._sesion.execute(
            _LISTAR,
            {
                "grupo_id": self._grupo_id,
                "persona_id": persona_id,
                "estados": sorted(e.value for e in estados),
                "desde_fecha": None if despues_de is None else despues_de[0],
                "desde_id": None if despues_de is None else despues_de[1],
                "limite": limite + 1,
            },
        ).all()
        items = [alerta_leida(f) for f in filas[:limite]]
        siguiente = None
        if len(filas) > limite and items:
            siguiente = (items[-1].fecha_prevista, items[-1].id)
        return PaginaAlertas(items=items, siguiente=siguiente)

    def obtener(self, persona_id: uuid.UUID, alerta_id: uuid.UUID) -> AlertaLeida | None:
        fila = self._sesion.execute(
            _OBTENER, {"grupo_id": self._grupo_id, "persona_id": persona_id, "alerta_id": alerta_id}
        ).first()
        return None if fila is None else alerta_leida(fila)

    def de_la_fecha(self, perfil_id: uuid.UUID, fecha: date) -> AlertaLeida | None:
        fila = self._sesion.execute(_DE_LA_FECHA, {"perfil_id": perfil_id, "fecha": fecha}).first()
        return None if fila is None else alerta_leida(fila)

    def _una(self, alerta_id: uuid.UUID) -> AlertaLeida:
        fila = self._sesion.execute(_UNA, {"id": alerta_id}).first()
        if fila is None:  # pragma: no cover - recién escrita en la misma transacción
            raise AlertaNoEscrita("la alerta no se escribió")
        return alerta_leida(fila)

    def cerrar(self, alerta_id: uuid.UUID, estado: EstadoAlerta, ahora: datetime) -> AlertaLeida:
        resultado = self._sesion.execute(_CERRAR, {"id": alerta_id, "estado": estado.value, "ahora": ahora})
        if getattr(resultado, "rowcount", 0) != 1:
            raise AlertaNoEscrita("la alerta no se cerró")
        return self._una(alerta_id)

    def insertar_cerrada(
        self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, fecha: date, estado: EstadoAlerta, ahora: datetime
    ) -> AlertaLeida:
        self._sesion.execute(
            _INSERTAR_CERRADA,
            {"id": alerta_id, "perfil_id": perfil_id, "fecha": fecha, "estado": estado.value, "ahora": ahora},
        )
        return self._una(alerta_id)

    def declarar_reposicion(
        self, reposicion_id: uuid.UUID, perfil_id: uuid.UUID, cantidad: int, ocurrida_en: date, usuario_id: uuid.UUID
    ) -> None:
        self._sesion.execute(
            _DECLARAR,
            {
                "id": reposicion_id,
                "perfil_id": perfil_id,
                "cantidad": cantidad,
                "ocurrida_en": ocurrida_en,
                "usuario_id": usuario_id,
            },
        )
