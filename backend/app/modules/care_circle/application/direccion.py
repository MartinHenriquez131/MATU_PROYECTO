"""Casos de uso de la dirección de entrega de la persona (MATU-61, D4, C6 y C8; decisiones 189 a 191, 216 y 219).

- guardar_direccion: PUT …/direccion. Crea la primera o cambia la de esa persona y solo de ella: si su fila la
  comparte otra persona del grupo, crea una nueva.
- vaciar_direccion: DELETE …/direccion (C6). La persona queda sin dirección y la fila se borra si nadie más la usa.

Los dos registran direccion.cambiar, sin el contenido (D12), y no piden la autorización de pedidos (C8). Un
pedido ya confirmado no cambia: su dirección es la copia de pedido_entrega.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.care_circle.application.ports import DatosDireccion
from app.modules.care_circle.domain.direccion import (
    DireccionDesactualizada,
    Precondicion,
    exigir_precondicion_guardar,
    exigir_precondicion_vaciar,
    puede_cambiar_direccion,
)
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


class PersonaSinAcceso(LookupError):
    """El rol no cambia la dirección, o la persona no es del grupo, no existe o está eliminada (404)."""


class Desactualizada(Exception):
    """412 con la dirección vigente en ``actual``."""

    def __init__(self, actual: DatosDireccion) -> None:
        super().__init__("la dirección cambió")
        self.actual = actual


@dataclass(frozen=True)
class DireccionDePersona:
    """La persona del grupo, bloqueada, con su dirección (o None)."""

    persona_id: uuid.UUID
    direccion_id: uuid.UUID | None
    direccion: DatosDireccion | None


class RepositorioDireccion(Protocol):
    """Implementación: RepositorioDireccionSQL (infrastructure/repositorio_direccion.py)."""

    def bloquear(self, persona_id: uuid.UUID) -> DireccionDePersona | None:
        """La persona no eliminada del grupo, con FOR UPDATE, y su dirección. None si no es del grupo."""
        ...

    def compartida(self, direccion_id: uuid.UUID, persona_id: uuid.UUID) -> bool:
        """Si otra persona del grupo usa la misma fila de direccion."""
        ...

    def crear(self, persona_id: uuid.UUID, datos: DatosDireccion, ahora: datetime) -> uuid.UUID:
        """Inserta una fila nueva (version 1) y la deja como la dirección de la persona."""
        ...

    def actualizar(self, direccion_id: uuid.UUID, datos: DatosDireccion) -> int:
        """Reemplaza los campos y sube la versión. Devuelve la versión nueva."""
        ...

    def vaciar(self, persona_id: uuid.UUID, direccion_id: uuid.UUID) -> None:
        """La persona queda sin dirección, y la fila se borra si ninguna otra persona la usa."""
        ...


@dataclass(frozen=True)
class SolicitudDireccion:
    usuario_id: uuid.UUID
    grupo_id: uuid.UUID
    rol: str
    persona_id: uuid.UUID
    request_id: str | None = None


def _persona(solicitud: SolicitudDireccion, repositorio: RepositorioDireccion) -> DireccionDePersona:
    if not puede_cambiar_direccion(solicitud.rol):
        raise PersonaSinAcceso()
    persona = repositorio.bloquear(solicitud.persona_id)
    if persona is None:
        raise PersonaSinAcceso()
    return persona


def _auditar(solicitud: SolicitudDireccion, direccion_id: uuid.UUID, registro: RegistroAuditoria) -> None:
    registro.registrar(
        EntradaAuditoria(
            grupo_id=solicitud.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=solicitud.usuario_id,
            accion=AccionAuditoria.DIRECCION_CAMBIAR,
            entidad=EntidadAuditoria.DIRECCION,
            entidad_id=direccion_id,
            request_id=solicitud.request_id,
        )
    )


def guardar_direccion(
    solicitud: SolicitudDireccion,
    precondicion: Precondicion,
    datos: DatosDireccion,
    reloj: Reloj,
    repositorio: RepositorioDireccion,
    registro: RegistroAuditoria,
) -> DatosDireccion:
    """La dirección guardada, con su versión nueva. Orden: 404, 428, 422 y 412."""
    persona = _persona(solicitud, repositorio)
    actual = persona.direccion
    try:
        exigir_precondicion_guardar(precondicion, None if actual is None else actual.version)
    except DireccionDesactualizada:
        if actual is None:  # pragma: no cover - If-Match sin dirección: el mismo 412, sin actual que mostrar
            raise
        raise Desactualizada(actual) from None
    if persona.direccion_id is None or repositorio.compartida(persona.direccion_id, persona.persona_id):
        direccion_id = repositorio.crear(persona.persona_id, datos, reloj.ahora())
        version = 1
    else:
        direccion_id = persona.direccion_id
        version = repositorio.actualizar(direccion_id, datos)
    _auditar(solicitud, direccion_id, registro)
    return DatosDireccion(
        etiqueta=datos.etiqueta,
        calle=datos.calle,
        numero=datos.numero,
        depto=datos.depto,
        comuna=datos.comuna,
        region=datos.region,
        referencia=datos.referencia,
        version=version,
    )


def vaciar_direccion(
    solicitud: SolicitudDireccion,
    if_match: str | None,
    repositorio: RepositorioDireccion,
    registro: RegistroAuditoria,
) -> None:
    """Deja a la persona sin dirección. Orden: 404, 428, 404 (sin dirección) y 412."""
    persona = _persona(solicitud, repositorio)
    actual = persona.direccion
    try:
        exigir_precondicion_vaciar(if_match, None if actual is None else actual.version)
    except DireccionDesactualizada:
        assert actual is not None
        raise Desactualizada(actual) from None
    assert persona.direccion_id is not None
    repositorio.vaciar(persona.persona_id, persona.direccion_id)
    _auditar(solicitud, persona.direccion_id, registro)
