"""Trabajo diario de la predicción de quiebre y conservación de alertas (MATU-37, arquitectura 8.5).

La corre el programador de tareas (MATU-74) una vez al día, a las 05:00 de Chile en verano y a las 04:00 en
invierno, dos horas después de los borrados (backend/README.md), desde backend/. Usa dos conexiones (H2,
migración 0022): SCHEDULER_DATABASE_URL de matu_scheduler para enumerar los grupos y conservar, y
DATABASE_URL de matu_app para el trabajo de cada grupo, que necesita RLS:

    python -m app.tareas quiebres

1. Enumera los grupos activos como matu_scheduler (SELECT (id, estado) y la política grupo_scheduler).
2. Por cada grupo abre su propia transacción como matu_app, con app.grupo_id y app.rol = 'sistema', y corre
   recalcular_quiebres. Si un grupo falla, se deshace solo ese grupo y sigue con el siguiente. Solo ve las
   personas no borradas y las autorizaciones no revocadas (_INSUMOS): una persona borrada o con la autorización
   retirada no tiene alerta ni evento, aunque el borrado no haya corrido (C9).
3. Llama a quiebre_conservar (migraciones 0011, 0014 y 0017) como matu_scheduler, con app.rol = 'operacion'.
   Desde la 0017 (MATU-51, decisión 145) borra también las compras declaradas a los 90 días de registrada_en.

El log lleva solo contadores, nunca un identificador, un nombre ni una cantidad.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.care_circle.domain.personas import AutorizacionGuardada
from app.modules.consumption.application.conservacion import ResultadoConservacionQuiebres, conservar_quiebres
from app.modules.consumption.application.ports import AlertaLeida, InsumoDelTrabajo
from app.modules.consumption.application.trabajo_diario import ResultadoTrabajo, recalcular_quiebres
from app.modules.consumption.events import AGREGADO_ALERTA, QUIEBRE_PROXIMO, QuiebreProximo
from app.modules.consumption.infrastructure.repositorio_alertas import alerta_leida
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import Reloj
from app.shared.reloj_sistema import RelojSistema

log = logging.getLogger("matu.consumption.quiebres")

_GRUPOS = text("SELECT id FROM grupo_familiar WHERE estado = 'activo' ORDER BY id")

# Un solo consentimiento no revocado por persona y finalidad (consentimiento_vigente_uq)
_INSUMOS = text(
    "SELECT p.id, p.persona_cuidada_id, p.fecha_quiebre_estimada, p.dias_aviso,"
    " c.calidad_otorgante, c.revision_vence_en,"
    " EXISTS (SELECT 1 FROM alerta_quiebre a WHERE a.perfil_id = p.id"
    "         AND a.fecha_prevista = p.fecha_quiebre_estimada) AS hay_alerta_de_la_fecha"
    " FROM perfil_consumo p"
    " JOIN persona_cuidada pc ON pc.id = p.persona_cuidada_id AND pc.grupo_id = p.grupo_id AND pc.eliminado_en IS NULL"
    " LEFT JOIN consentimiento c ON c.persona_cuidada_id = p.persona_cuidada_id AND c.grupo_id = p.grupo_id"
    " AND c.finalidad = 'consumo' AND c.revocado_en IS NULL"
    " WHERE p.grupo_id = :grupo_id AND p.activo"
    " ORDER BY p.id"
)

_ABIERTAS = text(
    "SELECT a.id, a.perfil_id, a.fecha_prevista, a.estado, a.creada_en, a.notificada_en, a.cerrada_en"
    " FROM alerta_quiebre a JOIN perfil_consumo p ON p.id = a.perfil_id"
    " WHERE p.grupo_id = :grupo_id AND a.estado IN ('pendiente', 'notificada')"
)

_MATERIALIZAR = text(
    "INSERT INTO alerta_quiebre (id, perfil_id, fecha_prevista, estado, creada_en)"
    " VALUES (:id, :perfil_id, :fecha, 'pendiente', :ahora)"
    " ON CONFLICT ON CONSTRAINT alerta_quiebre_uq DO NOTHING"
)

_DESCARTAR = text(
    "UPDATE alerta_quiebre SET estado = 'descartada', cerrada_en = :ahora"
    " WHERE id = :id AND estado IN ('pendiente', 'notificada')"
)

# Sin RETURNING: matu_app solo inserta en el outbox (03_permisos.sql)
_PUBLICAR = text(
    "INSERT INTO evento_outbox (grupo_id, tipo, agregado_tipo, agregado_id, payload, creado_en, disponible_en)"
    " VALUES (:grupo_id, :tipo, :agregado_tipo, :agregado_id, CAST(:payload AS jsonb), :ahora, :ahora)"
)

_CONSERVAR = text(
    "SELECT alertas, eventos, notificaciones, reposiciones"
    " FROM quiebre_conservar(:limite_alertas, :limite_eventos, :ahora)"
)


class RepositorioQuiebresSQL:
    """El trabajo de un grupo, en la sesión con app.rol = 'sistema' y app.grupo_id."""

    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def insumos(self) -> list[InsumoDelTrabajo]:
        filas = self._sesion.execute(_INSUMOS, {"grupo_id": self._grupo_id}).all()
        return [
            InsumoDelTrabajo(
                perfil_id=f.id,
                persona_cuidada_id=f.persona_cuidada_id,
                fecha_quiebre_estimada=f.fecha_quiebre_estimada,
                dias_aviso=int(f.dias_aviso),
                autorizacion=None
                if f.calidad_otorgante is None
                else AutorizacionGuardada(calidad_otorgante=f.calidad_otorgante, revision_vence_en=f.revision_vence_en),
                hay_alerta_de_la_fecha=bool(f.hay_alerta_de_la_fecha),
            )
            for f in filas
        ]

    def abiertas(self) -> list[AlertaLeida]:
        return [alerta_leida(f) for f in self._sesion.execute(_ABIERTAS, {"grupo_id": self._grupo_id}).all()]

    def materializar(self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, fecha: date, ahora: datetime) -> bool:
        resultado = self._sesion.execute(
            _MATERIALIZAR, {"id": alerta_id, "perfil_id": perfil_id, "fecha": fecha, "ahora": ahora}
        )
        return getattr(resultado, "rowcount", 0) == 1

    def descartar(self, alerta_id: uuid.UUID, ahora: datetime) -> None:
        self._sesion.execute(_DESCARTAR, {"id": alerta_id, "ahora": ahora})

    def publicar(self, evento: QuiebreProximo, ahora: datetime) -> None:
        self._sesion.execute(
            _PUBLICAR,
            {
                "grupo_id": self._grupo_id,
                "tipo": QUIEBRE_PROXIMO,
                "agregado_tipo": AGREGADO_ALERTA,
                "agregado_id": evento.alerta_id,
                "payload": json.dumps(evento.payload()),
                "ahora": ahora,
            },
        )


class ConservacionQuiebresSql:
    """Con la fábrica de matu_scheduler: desde la 0022 matu_app ya no ejecuta quiebre_conservar."""

    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def conservar(
        self, limite_alertas: datetime, limite_eventos: datetime, ahora: datetime
    ) -> tuple[int, int, int, int]:
        with sesion_tenant(self._fabrica, rol="operacion") as sesion:
            fila = sesion.execute(
                _CONSERVAR, {"limite_alertas": limite_alertas, "limite_eventos": limite_eventos, "ahora": ahora}
            ).one()
            return int(fila.alertas), int(fila.eventos), int(fila.notificaciones), int(fila.reposiciones)


@dataclass(frozen=True)
class ResultadoTarea:
    grupos: int
    grupos_fallidos: int
    materializadas: int
    descartadas: int


def grupos_activos(fabrica: sessionmaker[Session]) -> list[uuid.UUID]:
    """Los ids de los grupos activos, con la fábrica de matu_scheduler (política grupo_scheduler, sin contexto)."""
    with sesion_tenant(fabrica) as sesion:
        return [f.id for f in sesion.execute(_GRUPOS).all()]


def recalcular_grupo(fabrica: sessionmaker[Session], grupo_id: uuid.UUID, reloj: Reloj) -> ResultadoTrabajo:
    with sesion_tenant(fabrica, grupo_id=grupo_id, rol="sistema") as sesion:
        return recalcular_quiebres(
            grupo_id, RepositorioQuiebresSQL(sesion, grupo_id), RegistroAuditoriaSql(sesion, reloj), reloj
        )


def recalcular_todos(
    fabrica: sessionmaker[Session], scheduler: sessionmaker[Session], reloj: Reloj
) -> ResultadoTarea:
    """fabrica es la de matu_app (el trabajo de cada grupo) y scheduler la de matu_scheduler (la lista)."""
    grupos = grupos_activos(scheduler)
    fallidos = materializadas = descartadas = 0
    for grupo_id in grupos:
        try:
            resultado = recalcular_grupo(fabrica, grupo_id, reloj)
        except Exception as error:  # noqa: BLE001 - un grupo no detiene a los demás
            fallidos += 1
            # Solo el tipo (MATU-74, R2): el mensaje y la traza pueden traer el grupo_id o valores de las filas
            log.warning("quiebres: fallo un grupo", extra={"tipo_error": type(error).__name__})
            continue
        materializadas += resultado.materializadas
        descartadas += resultado.descartadas
    return ResultadoTarea(
        grupos=len(grupos), grupos_fallidos=fallidos, materializadas=materializadas, descartadas=descartadas
    )


def ejecutar(
    fabrica: sessionmaker[Session], scheduler: sessionmaker[Session], reloj: Reloj | None = None
) -> tuple[ResultadoTarea, ResultadoConservacionQuiebres]:
    """fabrica es la de matu_app y scheduler la de matu_scheduler (app/tareas.py)."""
    reloj = reloj or RelojSistema()
    tarea = recalcular_todos(fabrica, scheduler, reloj)
    log.info(
        "quiebres: %d grupos, %d fallidos, %d alertas creadas, %d descartadas",
        tarea.grupos,
        tarea.grupos_fallidos,
        tarea.materializadas,
        tarea.descartadas,
    )
    conservacion = conservar_quiebres(unidad=ConservacionQuiebresSql(scheduler), reloj=reloj)
    log.info(
        "conservacion de alertas: %d alertas, %d eventos, %d notificaciones y %d compras borrados",
        conservacion.alertas_borradas,
        conservacion.eventos_borrados,
        conservacion.notificaciones_borradas,
        conservacion.reposiciones_borradas,
    )
    return tarea, conservacion
