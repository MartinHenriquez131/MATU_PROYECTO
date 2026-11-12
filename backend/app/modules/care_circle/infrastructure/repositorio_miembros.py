"""Adaptador SQL del puerto RepositorioMiembros (MATU-42, RF-38).

Con la sesión del grupo. membresia_familia_leer (0026) deja ver solo las membresías activas del grupo, y
usuario_comiembro solo los nombres de los miembros activos. Cambiar el rol o el permiso es un UPDATE de matu_app
(membresia_admin_editar, solo admin); retirar va por membresia_retirar, SECURITY DEFINER, porque la fila retirada ya
no pasa la política de lectura y PostgreSQL exige que la fila nueva de un UPDATE la pase (decisión 327).

El trigger membresia_nunca_sin_admin rechaza con la restricción membresia_ultimo_admin: aquí se traduce a
UltimoAdminEnBase. El error de la base no se registra: puede traer valores de la fila.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modules.care_circle.application.ports_grupo import MiembroGuardado, UltimoAdminEnBase
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria

RESTRICCION_ULTIMO_ADMIN = "membresia_ultimo_admin"

_SELECT = (
    "SELECT m.id, m.usuario_id, u.nombre, m.rol, m.puede_ver_plan, m.unido_en, m.version"
    " FROM membresia m LEFT JOIN usuario u ON u.id = m.usuario_id"
    " WHERE m.grupo_id = :grupo_id AND m.estado = 'activa'"
)
_ACTIVOS = text(f"{_SELECT} ORDER BY m.unido_en, m.id")
_ACTIVO = text(f"{_SELECT} AND m.id = :id")
_ACTIVO_BLOQUEADO = text(f"{_SELECT} AND m.id = :id FOR UPDATE OF m")

_CAMBIAR = text(
    "UPDATE membresia SET rol = :rol, puede_ver_plan = :permiso, version = version + 1"
    " WHERE id = :id AND grupo_id = :grupo_id AND estado = 'activa' AND version = :version"
)
_RETIRAR = text("SELECT membresia_retirar(:id, :ahora) AS rol")


def _es_ultimo_admin(error: DBAPIError) -> bool:
    diagnostico = getattr(error.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None) == RESTRICCION_ULTIMO_ADMIN


def _guardado(fila: object) -> MiembroGuardado:
    return MiembroGuardado(
        id=fila.id,  # type: ignore[attr-defined]
        usuario_id=fila.usuario_id,  # type: ignore[attr-defined]
        nombre=fila.nombre or "",  # type: ignore[attr-defined]
        rol=fila.rol,  # type: ignore[attr-defined]
        puede_ver_plan=bool(fila.puede_ver_plan),  # type: ignore[attr-defined]
        unido_en=fila.unido_en.astimezone(UTC),  # type: ignore[attr-defined]
        version=int(fila.version),  # type: ignore[attr-defined]
    )


class RepositorioMiembrosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._registro = registro

    def activos(self) -> list[MiembroGuardado]:
        return [_guardado(f) for f in self._sesion.execute(_ACTIVOS, {"grupo_id": self._grupo_id}).all()]

    def activo(self, membresia_id: uuid.UUID, *, bloquear: bool = False) -> MiembroGuardado | None:
        sentencia = _ACTIVO_BLOQUEADO if bloquear else _ACTIVO
        fila = self._sesion.execute(sentencia, {"grupo_id": self._grupo_id, "id": membresia_id}).one_or_none()
        return None if fila is None else _guardado(fila)

    def cambiar(self, membresia_id: uuid.UUID, version: int, rol: str, puede_ver_plan: bool) -> bool:
        parametros = {
            "id": membresia_id,
            "grupo_id": self._grupo_id,
            "version": version,
            "rol": rol,
            "permiso": puede_ver_plan,
        }
        try:
            resultado = self._sesion.execute(_CAMBIAR, parametros)
        except DBAPIError as error:
            if _es_ultimo_admin(error):
                raise UltimoAdminEnBase() from None
            raise
        return bool(getattr(resultado, "rowcount", 0))

    def retirar(self, membresia_id: uuid.UUID, ahora: datetime) -> str | None:
        try:
            rol = self._sesion.execute(_RETIRAR, {"id": membresia_id, "ahora": ahora}).scalar_one()
        except DBAPIError as error:
            if _es_ultimo_admin(error):
                raise UltimoAdminEnBase() from None
            raise
        return None if rol is None else str(rol)

    def auditar(
        self, accion: str, membresia_id: uuid.UUID, rol: str, actor_id: uuid.UUID, request_id: str | None
    ) -> None:
        self._registro.registrar(
            EntradaAuditoria(
                grupo_id=self._grupo_id,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=actor_id,
                accion=AccionAuditoria(accion),
                entidad=EntidadAuditoria.MEMBRESIA,
                entidad_id=membresia_id,
                request_id=request_id,
                rol=rol,
            )
        )
