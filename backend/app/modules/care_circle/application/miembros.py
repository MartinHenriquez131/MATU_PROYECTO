"""Casos de uso de quiénes forman el grupo (MATU-42, RF-38, decisiones 302 a 307).

Ver la lista, cambiar el rol y el permiso del pagador, sacar a alguien y salir. Todo con la sesión del grupo y en una
sola transacción: los enlaces de relevo se cortan y las invitaciones se anulan **antes** de degradar o retirar la
membresía, mientras quien actúa todavía tiene el permiso que RLS pide (decisión 305).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.care_circle.application.invitaciones import Actor, NoEncontrado, anular_las_de, exigir_admin
from app.modules.care_circle.application.ports_grupo import (
    EnlacesDeRelevo,
    MiembroGuardado,
    RepositorioInvitaciones,
    RepositorioMiembros,
    UltimoAdminEnBase,
)
from app.modules.care_circle.domain.miembros import (
    ROL_ADMIN,
    ROL_PAGADOR,
    NoPuedeSalir,
    RolYPermiso,
    aplicar_cambio,
    deja_de_compartir,
    deja_de_ser_admin,
    deja_sin_admin,
    no_puede_salir,
    permiso_visible,
    sin_cambios,
    ve_enlaces,
    version_de_if_match,
)
from app.shared.auditoria import AccionAuditoria
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class MiembroVisto:
    """Un miembro como lo ve quien pregunta. Sin email, celular ni usuario_id (C9)."""

    id: uuid.UUID
    nombre: str
    rol: str
    puede_ver_plan: bool | None
    unido_en: datetime
    eres_tu: bool
    version: int
    enlaces_vigentes: int | None


class VersionDesactualizada(Exception):
    """El If-Match no es la versión vigente: 412 con la membresía en actual (decisión 303)."""

    def __init__(self, actual: MiembroVisto) -> None:
        super().__init__("la membresía cambió")
        self.actual = actual


class UltimoAdmin(Exception):
    """El cambio dejaría al grupo sin nadie que lo administre: 409 ultimo-admin (C11, C12)."""


class NoPuedeSalirDelGrupo(Exception):
    """409 ultimo-admin o unica-persona (C12, P14)."""

    def __init__(self, motivo: NoPuedeSalir) -> None:
        super().__init__(motivo.value)
        self.motivo = motivo


@dataclass(frozen=True)
class Puertos:
    miembros: RepositorioMiembros
    enlaces: EnlacesDeRelevo
    invitaciones: RepositorioInvitaciones
    reloj: Reloj


def _vista(m: MiembroGuardado, actor: Actor, conteos: dict[uuid.UUID, int]) -> MiembroVisto:
    eres_tu = m.usuario_id == actor.usuario_id
    return MiembroVisto(
        id=m.id,
        nombre=m.nombre,
        rol=m.rol,
        puede_ver_plan=permiso_visible(m.rol, m.puede_ver_plan),
        unido_en=m.unido_en,
        eres_tu=eres_tu,
        version=m.version,
        enlaces_vigentes=conteos.get(m.usuario_id, 0) if ve_enlaces(actor.rol == ROL_ADMIN, eres_tu) else None,
    )


def listar_miembros(actor: Actor, puertos: Puertos) -> list[MiembroVisto]:
    """Los miembros activos, por unido_en (C6, D-42-10 a). Todo miembro activo los ve."""
    conteos = puertos.enlaces.vigentes_por_persona(puertos.reloj.ahora())
    return [_vista(m, actor, conteos) for m in puertos.miembros.activos()]


def _destino(membresia_id: uuid.UUID, puertos: Puertos) -> MiembroGuardado:
    destino = puertos.miembros.activo(membresia_id, bloquear=True)
    if destino is None:
        raise NoEncontrado()
    return destino


def _visto_ahora(membresia_id: uuid.UUID, actor: Actor, puertos: Puertos) -> MiembroVisto:
    guardado = puertos.miembros.activo(membresia_id)
    if guardado is None:
        raise NoEncontrado()
    return _vista(guardado, actor, puertos.enlaces.vigentes_por_persona(puertos.reloj.ahora()))


def destino_del_cambio(membresia_id: uuid.UUID, actor: Actor, puertos: Puertos) -> MiembroGuardado:
    """El 404 de PATCH, antes de mirar If-Match y el cuerpo: rol que no alcanza y membresía inexistente, retirada o
    de otro grupo. La deja bloqueada hasta el final de la transacción."""
    exigir_admin(actor)
    return _destino(membresia_id, puertos)


def cambiar_miembro(
    destino: MiembroGuardado,
    if_match: str | None,
    rol: str | None,
    puede_ver_plan: bool | None,
    actor: Actor,
    puertos: Puertos,
) -> tuple[MiembroVisto, int]:
    """Cambia el rol, el permiso del pagador o los dos. Devuelve cómo quedó y cuántos enlaces se cortaron.

    Orden después del 404: FaltaVersion (428), PermisoSoloPagador (422), VersionDesactualizada (412), UltimoAdmin (409).
    Sin cambios reales: 200 con 0 cortados, sin subir la versión ni auditar.
    """
    version = version_de_if_match(if_match)
    actual = RolYPermiso(rol=destino.rol, puede_ver_plan=destino.puede_ver_plan)
    nuevo = aplicar_cambio(actual, rol, puede_ver_plan)
    if version != destino.version:
        raise VersionDesactualizada(_visto_ahora(destino.id, actor, puertos))
    if sin_cambios(actual, nuevo):
        return _visto_ahora(destino.id, actor, puertos), 0
    admins = sum(1 for m in puertos.miembros.activos() if m.rol == ROL_ADMIN)
    if deja_sin_admin(actual.rol, nuevo.rol, admins):
        raise UltimoAdmin()
    ahora = puertos.reloj.ahora()
    cortados = 0
    if deja_de_compartir(actual.rol, nuevo.rol):
        cortados = puertos.enlaces.cortar_de(destino.usuario_id, ahora, actor.usuario_id, actor.request_id)
    if deja_de_ser_admin(actual.rol, nuevo.rol):
        anular_las_de(destino.usuario_id, actor, puertos.invitaciones, ahora)
    try:
        cambiado = puertos.miembros.cambiar(destino.id, destino.version, nuevo.rol, nuevo.puede_ver_plan)
    except UltimoAdminEnBase:
        raise UltimoAdmin() from None
    if not cambiado:
        raise VersionDesactualizada(_visto_ahora(destino.id, actor, puertos))
    if nuevo.rol != actual.rol:
        puertos.miembros.auditar(
            AccionAuditoria.MEMBRESIA_CAMBIAR_ROL, destino.id, nuevo.rol, actor.usuario_id, actor.request_id
        )
    # Decisión 330: el permiso se audita cuando cambia y el rol que queda es pagador. Al dejar de ser pagador el
    # permiso vuelve a false solo, y lo dice membresia.cambiar_rol
    if nuevo.puede_ver_plan != actual.puede_ver_plan and nuevo.rol == ROL_PAGADOR:
        puertos.miembros.auditar(
            AccionAuditoria.MEMBRESIA_PERMISO_FICHA, destino.id, ROL_PAGADOR, actor.usuario_id, actor.request_id
        )
    return _visto_ahora(destino.id, actor, puertos), cortados


def _retirar(destino: MiembroGuardado, accion: AccionAuditoria, actor: Actor, puertos: Puertos) -> int:
    activos = puertos.miembros.activos()
    admins = sum(1 for m in activos if m.rol == ROL_ADMIN)
    motivo = no_puede_salir(destino.rol, admins, len(activos))
    if motivo is not None:
        raise NoPuedeSalirDelGrupo(motivo)
    ahora = puertos.reloj.ahora()
    cortados = 0
    if deja_de_compartir(destino.rol, None):
        cortados = puertos.enlaces.cortar_de(destino.usuario_id, ahora, actor.usuario_id, actor.request_id)
    if deja_de_ser_admin(destino.rol, None):
        anular_las_de(destino.usuario_id, actor, puertos.invitaciones, ahora)
    try:
        rol = puertos.miembros.retirar(destino.id, ahora)
    except UltimoAdminEnBase:
        raise NoPuedeSalirDelGrupo(NoPuedeSalir.ULTIMO_ADMIN) from None
    if rol is None:
        raise NoEncontrado()
    puertos.miembros.auditar(accion, destino.id, rol, actor.usuario_id, actor.request_id)
    return cortados


def salir_del_grupo(actor: Actor, puertos: Puertos) -> int:
    """Salir por cuenta propia (D-42-13): corta sus enlaces, anula sus invitaciones si era admin y deja la membresía
    retirada. Devuelve cuántos enlaces se cortaron."""
    propia = next((m for m in puertos.miembros.activos() if m.usuario_id == actor.usuario_id), None)
    if propia is None:
        raise NoEncontrado()
    # Sin FOR UPDATE: RLS solo deja bloquear membresías a quien administra (membresia_admin_editar). La bloquea
    # membresia_retirar, que además vuelve a mirar que siga activa
    return _retirar(propia, AccionAuditoria.MEMBRESIA_SALIR, actor, puertos)


def sacar_miembro(membresia_id: uuid.UUID, actor: Actor, puertos: Puertos) -> int:
    """Sacar a alguien (solo admin). La propia membresía es salir (decisión 306). No es idempotente: una membresía ya
    retirada es 404."""
    exigir_admin(actor)
    destino = _destino(membresia_id, puertos)
    if destino.usuario_id == actor.usuario_id:
        return _retirar(destino, AccionAuditoria.MEMBRESIA_SALIR, actor, puertos)
    return _retirar(destino, AccionAuditoria.MEMBRESIA_SACAR, actor, puertos)
