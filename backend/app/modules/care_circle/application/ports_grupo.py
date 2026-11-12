"""Puertos de las invitaciones y los miembros del grupo (MATU-42, RF-38).

Implementaciones SQL en infrastructure/repositorio_invitaciones.py, repositorio_miembros.py y canje_invitaciones.py.
Los enlaces de relevo son de care_plan, que care_circle no importa: el puerto EnlacesDeRelevo lo implementa care_plan
y app.main lo registra (infrastructure/enlaces_relevo.py), como los efectos del retiro de MATU-44.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.care_circle.domain.invitaciones import ResultadoCanje, VidaInvitacion


@dataclass(frozen=True)
class NuevaInvitacion:
    id: uuid.UUID
    grupo_id: uuid.UUID
    rol: str
    invitado_por: uuid.UUID
    nombre_pila_invita: str
    token_hash: bytes
    codigo_hash: bytes
    creada_en: datetime
    expira_en: datetime
    request_id: str | None


@dataclass(frozen=True)
class InvitacionListada:
    id: uuid.UUID
    rol: str
    vida: VidaInvitacion
    creada_en: datetime
    invitado_por: uuid.UUID
    nombre_pila_invita: str
    # Si quien la creó sigue como miembro activo del grupo
    autor_activo: bool


@dataclass(frozen=True)
class InvitacionParaAnular:
    id: uuid.UUID
    rol: str
    vida: VidaInvitacion


class RepositorioInvitaciones(Protocol):
    """invitacion e indice_token en la sesión del grupo. RLS deja leer y escribir solo a admin (0026)."""

    def nombre_usuario(self, usuario_id: uuid.UUID) -> str | None: ...

    def crear(self, invitacion: NuevaInvitacion) -> None:
        """Inserta la invitación, su indice_token y la auditoría invitacion.crear, en la transacción en curso."""
        ...

    def listar(self, ahora: datetime) -> list[InvitacionListada]:
        """Las no usadas, no anuladas y no vencidas del grupo, de la más nueva a la más antigua (hasta 200)."""
        ...

    def para_anular(self, invitacion_id: uuid.UUID) -> InvitacionParaAnular | None:
        """La invitación del grupo, bloqueada con FOR UPDATE, o None si no existe o es de otro grupo."""
        ...

    def anular(
        self, invitacion: InvitacionParaAnular, ahora: datetime, actor_id: uuid.UUID, request_id: str | None
    ) -> None:
        """Fija revocada_en en la invitación y en su indice_token, y registra invitacion.anular con el rol."""
        ...

    def sin_usar_de(self, invitado_por: uuid.UUID, ahora: datetime) -> list[InvitacionParaAnular]:
        """Las invitaciones pendientes o bloqueadas que creó esa persona, bloqueadas con FOR UPDATE (decisión 307)."""
        ...


@dataclass(frozen=True)
class MiembroGuardado:
    id: uuid.UUID
    usuario_id: uuid.UUID
    nombre: str
    rol: str
    puede_ver_plan: bool
    unido_en: datetime
    version: int


class UltimoAdminEnBase(Exception):
    """El trigger membresia_nunca_sin_admin rechazó el cambio (C11). La API responde 409 ultimo-admin."""


class RepositorioMiembros(Protocol):
    """membresia en la sesión del grupo: RLS deja ver solo las activas (D-42-10 a)."""

    def activos(self) -> list[MiembroGuardado]:
        """Los miembros activos del grupo, por unido_en."""
        ...

    def activo(self, membresia_id: uuid.UUID, *, bloquear: bool = False) -> MiembroGuardado | None: ...

    def cambiar(self, membresia_id: uuid.UUID, version: int, rol: str, puede_ver_plan: bool) -> bool:
        """Cambia rol y permiso y sube la versión, solo si la versión sigue siendo esa. False si cambió.
        UltimoAdminEnBase si el trigger lo rechaza."""
        ...

    def retirar(self, membresia_id: uuid.UUID, ahora: datetime) -> str | None:
        """Deja la membresía retirada (membresia_retirar, 0026). Devuelve el rol que tenía, o None si no estaba
        activa. UltimoAdminEnBase si el trigger lo rechaza."""
        ...

    def auditar(
        self,
        accion: str,
        membresia_id: uuid.UUID,
        rol: str,
        actor_id: uuid.UUID,
        request_id: str | None,
    ) -> None: ...


class EnlacesDeRelevo(Protocol):
    """Los accesos de relevo que cada persona compartió en el grupo (care_plan, acceso_relevo.otorgado_por)."""

    def vigentes_por_persona(self, ahora: datetime) -> dict[uuid.UUID, int]:
        """Cuántos accesos no cortados y no vencidos compartió cada usuario. Solo los que RLS deja ver."""
        ...

    def cortar_de(self, otorgado_por: uuid.UUID, ahora: datetime, actor_id: uuid.UUID, request_id: str | None) -> int:
        """Corta los accesos vigentes que esa persona compartió, cada uno con relevo.revocar. Devuelve cuántos."""
        ...


@dataclass(frozen=True)
class Presentacion:
    resultado: ResultadoCanje
    nombre_pila_invita: str | None = None
    rol: str | None = None
    expira_en: datetime | None = None


@dataclass(frozen=True)
class Verificacion:
    resultado: ResultadoCanje
    nombre_pila_invita: str | None = None
    grupo: str | None = None
    personas: tuple[str, ...] = ()
    rol: str | None = None
    expira_en: datetime | None = None
    intentos_restantes: int | None = None


@dataclass(frozen=True)
class Aceptacion:
    resultado: ResultadoCanje
    nombre_pila_invita: str | None = None
    grupo_id: uuid.UUID | None = None
    membresia_id: uuid.UUID | None = None
    grupo: str | None = None
    rol: str | None = None
    intentos_restantes: int | None = None


class CanjeInvitaciones(Protocol):
    """Las funciones SECURITY DEFINER de la 0026, sin app.grupo_id. La aceptación, con app.usuario_id."""

    def invitacion_de(self, token_hash: bytes) -> uuid.UUID | None:
        """El id de la invitación por la huella del token (indice_token, sin RLS), para el HMAC del código."""
        ...

    def presentar(self, token_hash: bytes, ahora: datetime) -> Presentacion: ...

    def verificar(self, token_hash: bytes, codigo_hash: bytes, ahora: datetime, request_id: str | None) -> Verificacion:
        ...

    def aceptar(self, token_hash: bytes, codigo_hash: bytes, ahora: datetime, request_id: str | None) -> Aceptacion:
        ...


class CredencialesInvitacion(Protocol):
    """El token (256 bits) y el código (4 dígitos), y sus huellas. Implementación: infrastructure/credenciales.py."""

    def token(self) -> bytes: ...

    def codigo(self) -> str: ...

    def huella_token(self, token: bytes) -> bytes: ...

    def huella_codigo(self, invitacion_id: uuid.UUID, codigo: str) -> bytes: ...
