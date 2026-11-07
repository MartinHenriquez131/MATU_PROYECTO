"""Puertos del módulo consumption (ADR-021)."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.modules.care_circle.domain.personas import AutorizacionGuardada
from app.modules.consumption.domain.alerta import EstadoAlerta
from app.modules.consumption.domain.perfil import Perfil, UnidadConsumo
from app.modules.consumption.events import QuiebreProximo


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
        """Borra la fila. Sus reposiciones y alertas caen por ON DELETE CASCADE (decisión 69)."""
        ...


class ConservacionConsumo(Protocol):
    """Llama a consumo_conservar (migración 0009) con app.rol = 'operacion'."""

    def conservar(self, limite: datetime, ahora: datetime) -> int:
        """Devuelve cuántos perfiles borró."""
        ...


# --- MATU-37: alertas de quiebre ------------------------------------------------------------------------


@dataclass(frozen=True)
class AlertaLeida:
    """Una fila de alerta_quiebre. Solo identificadores, fechas y estado."""

    id: uuid.UUID
    perfil_id: uuid.UUID
    fecha_prevista: date
    estado: EstadoAlerta
    creada_en: datetime
    notificada_en: datetime | None
    cerrada_en: datetime | None


@dataclass(frozen=True)
class InsumoEnVentana:
    """Un perfil activo en su ventana de aviso, con la alerta de su fecha estimada actual si existe."""

    leido: PerfilLeido
    alerta: AlertaLeida | None


@dataclass(frozen=True)
class PaginaAlertas:
    items: list[AlertaLeida]
    # La última fila de la página, si hay más: (fecha_prevista, id)
    siguiente: tuple[date, uuid.UUID] | None


class RepositorioAlertas(Protocol):
    """alerta_quiebre en la transacción del contexto de grupo (políticas de la migración 0011).

    Implementación: RepositorioAlertasSQL (infrastructure/repositorio_alertas.py).
    """

    def en_ventana(self, persona_id: uuid.UUID, hoy: date) -> list[InsumoEnVentana]:
        """Perfiles activos con fecha_quiebre_estimada - hoy <= dias_aviso, por fecha y después por id."""
        ...

    def listar(
        self,
        persona_id: uuid.UUID,
        estados: frozenset[EstadoAlerta],
        despues_de: tuple[date, uuid.UUID] | None,
        limite: int,
    ) -> PaginaAlertas: ...

    def obtener(self, persona_id: uuid.UUID, alerta_id: uuid.UUID) -> AlertaLeida | None:
        """La alerta si es de un perfil de la persona, bloqueada para escribir (FOR UPDATE)."""
        ...

    def de_la_fecha(self, perfil_id: uuid.UUID, fecha: date) -> AlertaLeida | None:
        """La alerta del perfil para esa fecha prevista (alerta_quiebre_uq), bloqueada."""
        ...

    def cerrar(self, alerta_id: uuid.UUID, estado: EstadoAlerta, ahora: datetime) -> AlertaLeida: ...

    def insertar_cerrada(
        self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, fecha: date, estado: EstadoAlerta, ahora: datetime
    ) -> AlertaLeida:
        """Una alerta ya cerrada para un insumo cuya alerta el trabajo diario aún no creó (decisión 76)."""
        ...

    def declarar_reposicion(
        self, reposicion_id: uuid.UUID, perfil_id: uuid.UUID, cantidad: int, ocurrida_en: date, usuario_id: uuid.UUID
    ) -> None:
        """Una reposicion origen 'declarada', registrada_por = usuario_id (decisión 79)."""
        ...

    def abiertas_del_perfil(self, perfil_id: uuid.UUID) -> list[AlertaLeida]:
        """Las alertas pendiente y notificada del perfil, bloqueadas (FOR UPDATE), por fecha y id (MATU-51)."""
        ...


@dataclass(frozen=True)
class InsumoDelTrabajo:
    """Lo que lee el trabajo diario de un perfil activo, con la autorización de su persona."""

    perfil_id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    fecha_quiebre_estimada: date
    dias_aviso: int
    autorizacion: AutorizacionGuardada | None
    hay_alerta_de_la_fecha: bool


class RepositorioQuiebres(Protocol):
    """El trabajo diario en un grupo, con app.rol = 'sistema' y app.grupo_id (arquitectura 8.5).

    Implementación: RepositorioQuiebresSQL (infrastructure/tarea_quiebres.py).
    """

    def insumos(self) -> list[InsumoDelTrabajo]: ...

    def abiertas(self) -> list[AlertaLeida]: ...

    def materializar(self, alerta_id: uuid.UUID, perfil_id: uuid.UUID, fecha: date, ahora: datetime) -> bool:
        """Inserta la alerta pendiente. False si ya existía una para el perfil y la fecha."""
        ...

    def descartar(self, alerta_id: uuid.UUID, ahora: datetime) -> None: ...

    def publicar(self, evento: QuiebreProximo, ahora: datetime) -> None:
        """Inserta el evento en evento_outbox, en la misma transacción."""
        ...


class ConservacionQuiebres(Protocol):
    """Llama a quiebre_conservar (migraciones 0011, 0014 y 0017) con app.rol = 'operacion'."""

    def conservar(
        self, limite_alertas: datetime, limite_eventos: datetime, ahora: datetime
    ) -> tuple[int, int, int, int]:
        """(alertas, eventos, notificaciones, reposiciones declaradas) borrados (decisión 145)."""
        ...
