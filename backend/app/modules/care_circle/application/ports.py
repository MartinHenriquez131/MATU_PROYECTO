"""Puertos del módulo care_circle (ADR-021)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class NuevoGrupo:
    id: uuid.UUID
    nombre: str
    creado_por: uuid.UUID


@dataclass(frozen=True)
class GrupoDelUsuario:
    """Un grupo en el que el usuario tiene una membresía activa, con su rol en él."""

    id: uuid.UUID
    nombre: str
    rol: str


class RepositorioGrupos(Protocol):
    """Persistencia de grupo_familiar y membresia.

    Implementación: RepositorioGruposSQL (infrastructure/repositorio_grupos.py).
    """

    def crear(self, grupo: NuevoGrupo) -> None:
        """Guarda el grupo y la membresía admin activa de su creador en una sola transacción.

        Si la membresía falla, no queda el grupo: la excepción sigue y la transacción se deshace.
        """
        ...

    def listar(self, usuario_id: uuid.UUID) -> list[GrupoDelUsuario]:
        """Los grupos donde el usuario tiene una membresía activa, del más antiguo al más nuevo."""
        ...


# --- Persona cuidada y consentimiento (MATU-07, RF-01) ----------------------------------------------


@dataclass(frozen=True)
class DatosDireccion:
    """Una dirección de entrega, sin coordenadas."""

    etiqueta: str
    calle: str
    numero: str
    depto: str | None
    comuna: str
    region: str
    referencia: str | None


@dataclass(frozen=True)
class AltaPersona:
    """Todo lo que el alta escribe, en una sola transacción: la persona, su dirección si llegó, el
    consentimiento para plan_cuidado y la fila de auditoría. Los identificadores y los instantes
    ya vienen fijados por el caso de uso."""

    grupo_id: uuid.UUID
    usuario_id: uuid.UUID
    persona_id: uuid.UUID
    nombre: str
    nombre_pila: str
    nivel_apoyo: str
    direccion_id: uuid.UUID | None
    direccion: DatosDireccion | None
    consentimiento_id: uuid.UUID
    calidad_otorgante: str
    finalidad: str
    version_politica: str
    evidencia: dict[str, Any]
    referencia_documento: str | None
    otorgado_en: datetime
    revision_vence_en: datetime | None
    request_id: str | None


@dataclass(frozen=True)
class ConsentimientoVigente:
    id: uuid.UUID
    calidad_otorgante: str
    finalidad: str
    version_politica: str
    otorgado_en: datetime
    revision_vence_en: datetime | None


@dataclass(frozen=True)
class PersonaCompleta:
    """Vista de admin y cuidador."""

    id: uuid.UUID
    nombre: str
    nombre_pila: str
    nivel_apoyo: str
    direccion: DatosDireccion | None
    consentimiento: ConsentimientoVigente | None


@dataclass(frozen=True)
class PersonaNombreYDireccion:
    """Vista del pagador."""

    id: uuid.UUID
    nombre: str
    direccion: DatosDireccion | None


@dataclass(frozen=True)
class PersonaSoloNombre:
    """Vista del observador."""

    id: uuid.UUID
    nombre: str


class RepositorioPersonas(Protocol):
    """Persistencia de persona_cuidada, direccion, consentimiento y su auditoría.

    Trabaja dentro de la transacción del contexto de grupo (sesion_de_grupo): RLS acota todo al
    grupo en contexto. Implementación: RepositorioPersonasSQL (infrastructure/repositorio_personas.py).
    """

    def guardar_alta(self, alta: AltaPersona) -> None:
        """Escribe la dirección (si llegó), la persona, el consentimiento y la auditoría.

        Si una escritura falla, la excepción sigue y la transacción completa se deshace.
        """
        ...

    def listar_completas(self) -> list[PersonaCompleta]:
        """Las personas del grupo con su dirección y su consentimiento vigente para plan_cuidado."""
        ...

    def listar_nombre_y_direccion(self) -> list[PersonaNombreYDireccion]: ...

    def listar_solo_nombre(self) -> list[PersonaSoloNombre]: ...
