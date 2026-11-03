"""Puertos del módulo consumption (ADR-021)."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.modules.consumption.domain.perfil import Perfil, UnidadConsumo


@dataclass(frozen=True)
class ProductoAdmitido:
    """Lo mínimo del producto del catálogo, sin precio ni marca."""

    id: uuid.UUID
    nombre: str
    presentacion: str
    unidad: UnidadConsumo


@dataclass(frozen=True)
class PerfilLeido:
    """Un perfil con lo que la vista necesita además de la fila: el producto y el nombre de pila de
    quien guardó la última vez (para el 412)."""

    perfil: Perfil
    producto: ProductoAdmitido | None
    actualizado_por_nombre: str | None


@dataclass(frozen=True)
class Pagina:
    items: list[PerfilLeido]
    # La última fila de la página, si hay más: (fecha_quiebre_estimada, id)
    siguiente: tuple[date, uuid.UUID] | None


class RepositorioPerfiles(Protocol):
    """Persistencia de perfil_consumo en la transacción del contexto de grupo.

    RLS acota todo al grupo y, al escribir, al rol (políticas de la migración 0009). Implementación:
    RepositorioPerfilesSQL (infrastructure/repositorio_perfiles.py).
    """

    def listar(
        self, persona_id: uuid.UUID, activo: bool | None, despues_de: tuple[date, uuid.UUID] | None, limite: int
    ) -> Pagina:
        """Por fecha estimada y después por id. activo None = todos."""
        ...

    def obtener(
        self, persona_id: uuid.UUID, perfil_id: uuid.UUID, *, para_escribir: bool = False
    ) -> PerfilLeido | None:
        """El perfil de la persona, o None. Con para_escribir, lo bloquea (FOR UPDATE)."""
        ...

    def producto_admitido(self, producto_id: uuid.UUID) -> ProductoAdmitido | None:
        """El producto si existe, está activo y no requiere receta (ADR-022). Si no, None."""
        ...

    def hay_activo_del_producto(self, persona_id: uuid.UUID, producto_id: uuid.UUID, salvo: uuid.UUID | None) -> bool:
        """Si la persona ya sigue ese producto en otro perfil activo (perfil_consumo_producto_uq)."""
        ...

    def insertar(self, grupo_id: uuid.UUID, perfil: Perfil) -> None: ...

    def actualizar(self, perfil: Perfil) -> None: ...

    def descartar_alertas_abiertas(self, perfil_id: uuid.UUID, ahora: datetime) -> None:
        """Las alertas pendiente y notificada del perfil pasan a descartada (decisión 46)."""
        ...

    def eliminar(self, perfil_id: uuid.UUID) -> None:
        """Borra la fila. Sus reposiciones y alertas caen por ON DELETE CASCADE (decisión 66)."""
        ...


class ConservacionConsumo(Protocol):
    """Llama a consumo_conservar (migración 0009) con app.rol = 'operacion'."""

    def conservar(self, limite: datetime, ahora: datetime) -> int:
        """Devuelve cuántos perfiles borró."""
        ...
