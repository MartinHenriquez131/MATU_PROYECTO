"""Adaptador SQL del puerto RepositorioPersonas (MATU-07, RF-01).

Trabaja con la sesión del contexto de grupo (sesion_de_grupo): app.usuario_id y app.grupo_id ya
están fijados y RLS acota cada consulta al grupo. Nunca abre su propia sesión ni fija contexto.

Los INSERT no usan RETURNING: los identificadores los generó el caso de uso, y así las escrituras no
dependen de qué política SELECT muestra cada fila.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.modules.care_circle.application.ports import (
    AltaPersona,
    ConsentimientoVigente,
    DatosDireccion,
    PersonaCompleta,
    PersonaNombreYDireccion,
    PersonaSoloNombre,
)

_INSERTAR_DIRECCION = text(
    "INSERT INTO direccion (id, grupo_id, etiqueta, calle, numero, depto, comuna, region, referencia, creado_en)"
    " VALUES (:id, :grupo_id, :etiqueta, :calle, :numero, :depto, :comuna, :region, :referencia, :creado_en)"
)

_INSERTAR_PERSONA = text(
    "INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo, direccion_entrega_id,"
    " creado_en, actualizado_en)"
    " VALUES (:id, :grupo_id, :nombre, :nombre_pila, :nivel_apoyo, :direccion_id, :creado_en, :creado_en)"
)

_INSERTAR_CONSENTIMIENTO = text(
    "INSERT INTO consentimiento (id, grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
    " version_politica, evidencia, referencia_documento, otorgado_en, revision_vence_en)"
    " VALUES (:id, :grupo_id, :persona_id, :usuario_id, :calidad_otorgante, :finalidad,"
    " :version_politica, CAST(:evidencia AS jsonb), :referencia_documento, :otorgado_en, :revision_vence_en)"
)

# Solo identificadores: sin nombre, sin IP y sin motivo
_INSERTAR_AUDITORIA = text(
    "INSERT INTO auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, request_id, ocurrido_en)"
    " VALUES (:grupo_id, 'usuario', :usuario_id, 'consentimiento.otorgar', 'consentimiento', :consentimiento_id,"
    " :request_id, :ocurrido_en)"
)

_COLUMNAS_DIRECCION = "d.etiqueta, d.calle, d.numero, d.depto, d.comuna, d.region, d.referencia"

# El filtro por grupo es explícito además de RLS. Solo personas no eliminadas
_DESDE_PERSONAS = " FROM persona_cuidada p"
_DIRECCION = " LEFT JOIN direccion d ON d.id = p.direccion_entrega_id"
_FILTRO = " WHERE p.grupo_id = :grupo_id AND p.eliminado_en IS NULL ORDER BY p.creado_en, p.id"

_LISTAR_COMPLETAS = text(
    "SELECT p.id, p.nombre, p.nombre_pila, p.nivel_apoyo, p.direccion_entrega_id, " + _COLUMNAS_DIRECCION + ","
    " c.id AS c_id, c.calidad_otorgante, c.finalidad, c.version_politica, c.otorgado_en, c.revision_vence_en"
    + _DESDE_PERSONAS
    + _DIRECCION
    + " LEFT JOIN consentimiento c ON c.persona_cuidada_id = p.id"
    " AND c.finalidad = 'plan_cuidado' AND c.revocado_en IS NULL"
    + _FILTRO
)

_LISTAR_NOMBRE_Y_DIRECCION = text(
    "SELECT p.id, p.nombre, p.direccion_entrega_id, " + _COLUMNAS_DIRECCION + _DESDE_PERSONAS + _DIRECCION + _FILTRO
)

_LISTAR_SOLO_NOMBRE = text("SELECT p.id, p.nombre" + _DESDE_PERSONAS + _FILTRO)


def _utc(instante: datetime | None) -> datetime | None:
    # La API responde siempre en UTC (arquitectura 9.1), sea cual sea la zona de la sesión de la base
    return None if instante is None else instante.astimezone(UTC)


def _direccion(fila: Row[Any]) -> DatosDireccion | None:
    if fila.direccion_entrega_id is None or fila.calle is None:
        return None
    return DatosDireccion(
        etiqueta=fila.etiqueta,
        calle=fila.calle,
        numero=fila.numero,
        depto=fila.depto,
        comuna=fila.comuna,
        region=fila.region,
        referencia=fila.referencia,
    )


class RepositorioPersonasSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id

    def guardar_alta(self, alta: AltaPersona) -> None:
        # Las cuatro escrituras van en la transacción de sesion_de_grupo. Si una falla, la excepción
        # sigue, sesion_tenant hace rollback y no queda nada.
        if alta.direccion is not None:
            self._insertar_direccion(alta)
        self._insertar_persona(alta)
        self._insertar_consentimiento(alta)
        self._insertar_auditoria(alta)

    def listar_completas(self) -> list[PersonaCompleta]:
        filas = self._sesion.execute(_LISTAR_COMPLETAS, {"grupo_id": self._grupo_id}).all()
        return [
            PersonaCompleta(
                id=f.id,
                nombre=f.nombre,
                nombre_pila=f.nombre_pila,
                nivel_apoyo=f.nivel_apoyo,
                direccion=_direccion(f),
                consentimiento=None
                if f.c_id is None
                else ConsentimientoVigente(
                    id=f.c_id,
                    calidad_otorgante=f.calidad_otorgante,
                    finalidad=f.finalidad,
                    version_politica=f.version_politica,
                    otorgado_en=f.otorgado_en.astimezone(UTC),
                    revision_vence_en=_utc(f.revision_vence_en),
                ),
            )
            for f in filas
        ]

    def listar_nombre_y_direccion(self) -> list[PersonaNombreYDireccion]:
        filas = self._sesion.execute(_LISTAR_NOMBRE_Y_DIRECCION, {"grupo_id": self._grupo_id}).all()
        return [PersonaNombreYDireccion(id=f.id, nombre=f.nombre, direccion=_direccion(f)) for f in filas]

    def listar_solo_nombre(self) -> list[PersonaSoloNombre]:
        filas = self._sesion.execute(_LISTAR_SOLO_NOMBRE, {"grupo_id": self._grupo_id}).all()
        return [PersonaSoloNombre(id=f.id, nombre=f.nombre) for f in filas]

    def _insertar_direccion(self, alta: AltaPersona) -> None:
        assert alta.direccion is not None
        d = alta.direccion
        self._sesion.execute(
            _INSERTAR_DIRECCION,
            {
                "id": alta.direccion_id,
                "grupo_id": alta.grupo_id,
                "etiqueta": d.etiqueta,
                "calle": d.calle,
                "numero": d.numero,
                "depto": d.depto,
                "comuna": d.comuna,
                "region": d.region,
                "referencia": d.referencia,
                "creado_en": alta.otorgado_en,
            },
        )

    def _insertar_persona(self, alta: AltaPersona) -> None:
        self._sesion.execute(
            _INSERTAR_PERSONA,
            {
                "id": alta.persona_id,
                "grupo_id": alta.grupo_id,
                "nombre": alta.nombre,
                "nombre_pila": alta.nombre_pila,
                "nivel_apoyo": alta.nivel_apoyo,
                "direccion_id": alta.direccion_id,
                "creado_en": alta.otorgado_en,
            },
        )

    def _insertar_consentimiento(self, alta: AltaPersona) -> None:
        self._sesion.execute(
            _INSERTAR_CONSENTIMIENTO,
            {
                "id": alta.consentimiento_id,
                "grupo_id": alta.grupo_id,
                "persona_id": alta.persona_id,
                "usuario_id": alta.usuario_id,
                "calidad_otorgante": alta.calidad_otorgante,
                "finalidad": alta.finalidad,
                "version_politica": alta.version_politica,
                "evidencia": json.dumps(alta.evidencia, ensure_ascii=False, sort_keys=True),
                "referencia_documento": alta.referencia_documento,
                "otorgado_en": alta.otorgado_en,
                "revision_vence_en": alta.revision_vence_en,
            },
        )

    def _insertar_auditoria(self, alta: AltaPersona) -> None:
        self._sesion.execute(
            _INSERTAR_AUDITORIA,
            {
                "grupo_id": alta.grupo_id,
                "usuario_id": alta.usuario_id,
                "consentimiento_id": alta.consentimiento_id,
                "request_id": alta.request_id,
                "ocurrido_en": alta.otorgado_en,
            },
        )
