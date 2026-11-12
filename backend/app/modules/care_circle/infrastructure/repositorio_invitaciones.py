"""Adaptador SQL del puerto RepositorioInvitaciones (MATU-42, RF-38).

Con la sesión del grupo (sesion_de_grupo). invitacion_admin_leer, _crear y _anular (0026) dejan leer y escribir solo a
quien administra; el filtro por grupo va explícito además de RLS. indice_token no tiene RLS y guarda solo la huella
del token, el grupo, la invitación y su vencimiento. La auditoría lleva solo el rol (D-42-8 b): nunca el token, el
código ni sus huellas.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_circle.application.ports_grupo import InvitacionListada, InvitacionParaAnular, NuevaInvitacion
from app.modules.care_circle.domain.invitaciones import VidaInvitacion
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria

_NOMBRE_USUARIO = text("SELECT nombre FROM usuario WHERE id = :usuario_id AND eliminado_en IS NULL")

_INSERTAR = text(
    "INSERT INTO invitacion (id, grupo_id, rol, token_hash, codigo_hash, invitado_por, nombre_pila_invita, creada_en,"
    " expira_en) VALUES (:id, :grupo_id, :rol, :token_hash, :codigo_hash, :invitado_por, :nombre_pila, :creada_en,"
    " :expira_en)"
)
_INSERTAR_INDICE = text(
    "INSERT INTO indice_token (token_hash, tipo, grupo_id, referencia_id, expira_en, creado_en)"
    " VALUES (:token_hash, 'invitacion', :grupo_id, :id, :expira_en, :creada_en)"
)

_COLUMNAS = "i.id, i.rol, i.creada_en, i.expira_en, i.aceptada_en, i.revocada_en, i.bloqueada_en"

# Las sin usar: el estado fino (pendiente o bloqueada) lo decide el dominio con el mismo instante
_LISTAR = text(
    f"SELECT {_COLUMNAS}, i.invitado_por, i.nombre_pila_invita,"
    " EXISTS (SELECT 1 FROM membresia m WHERE m.grupo_id = i.grupo_id AND m.usuario_id = i.invitado_por"
    "         AND m.estado = 'activa') AS autor_activo"
    " FROM invitacion i WHERE i.grupo_id = :grupo_id AND i.aceptada_en IS NULL AND i.revocada_en IS NULL"
    " AND i.expira_en > :ahora ORDER BY i.creada_en DESC, i.id DESC LIMIT 200"
)

_PARA_ANULAR = text(f"SELECT {_COLUMNAS} FROM invitacion i WHERE i.id = :id AND i.grupo_id = :grupo_id FOR UPDATE")

_SIN_USAR_DE = text(
    f"SELECT {_COLUMNAS} FROM invitacion i WHERE i.grupo_id = :grupo_id AND i.invitado_por = :usuario_id"
    " AND i.aceptada_en IS NULL AND i.revocada_en IS NULL AND i.expira_en > :ahora ORDER BY i.id FOR UPDATE"
)

_ANULAR = text(
    "UPDATE invitacion SET revocada_en = :ahora WHERE id = :id AND grupo_id = :grupo_id AND revocada_en IS NULL"
)
_ANULAR_INDICE = text(
    "UPDATE indice_token SET revocado_en = :ahora"
    " WHERE tipo = 'invitacion' AND referencia_id = :id AND grupo_id = :grupo_id AND revocado_en IS NULL"
)


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


def _vida(fila: object) -> VidaInvitacion:
    return VidaInvitacion(
        expira_en=fila.expira_en.astimezone(UTC),  # type: ignore[attr-defined]
        aceptada_en=_utc(fila.aceptada_en),  # type: ignore[attr-defined]
        revocada_en=_utc(fila.revocada_en),  # type: ignore[attr-defined]
        bloqueada_en=_utc(fila.bloqueada_en),  # type: ignore[attr-defined]
    )


class RepositorioInvitacionesSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._registro = registro

    def nombre_usuario(self, usuario_id: uuid.UUID) -> str | None:
        fila = self._sesion.execute(_NOMBRE_USUARIO, {"usuario_id": usuario_id}).one_or_none()
        return None if fila is None else str(fila.nombre)

    def crear(self, invitacion: NuevaInvitacion) -> None:
        parametros = {
            "id": invitacion.id,
            "grupo_id": invitacion.grupo_id,
            "rol": invitacion.rol,
            "token_hash": invitacion.token_hash,
            "codigo_hash": invitacion.codigo_hash,
            "invitado_por": invitacion.invitado_por,
            "nombre_pila": invitacion.nombre_pila_invita,
            "creada_en": invitacion.creada_en,
            "expira_en": invitacion.expira_en,
        }
        self._sesion.execute(_INSERTAR, parametros)
        self._sesion.execute(_INSERTAR_INDICE, parametros)
        self._auditar(
            AccionAuditoria.INVITACION_CREAR,
            invitacion.id,
            invitacion.rol,
            invitacion.invitado_por,
            invitacion.request_id,
        )

    def listar(self, ahora: datetime) -> list[InvitacionListada]:
        filas = self._sesion.execute(_LISTAR, {"grupo_id": self._grupo_id, "ahora": ahora}).all()
        return [
            InvitacionListada(
                id=f.id,
                rol=f.rol,
                vida=_vida(f),
                creada_en=f.creada_en.astimezone(UTC),
                invitado_por=f.invitado_por,
                nombre_pila_invita=f.nombre_pila_invita,
                autor_activo=bool(f.autor_activo),
            )
            for f in filas
        ]

    def para_anular(self, invitacion_id: uuid.UUID) -> InvitacionParaAnular | None:
        fila = self._sesion.execute(_PARA_ANULAR, {"id": invitacion_id, "grupo_id": self._grupo_id}).one_or_none()
        return None if fila is None else InvitacionParaAnular(id=fila.id, rol=fila.rol, vida=_vida(fila))

    def anular(
        self, invitacion: InvitacionParaAnular, ahora: datetime, actor_id: uuid.UUID, request_id: str | None
    ) -> None:
        parametros = {"id": invitacion.id, "grupo_id": self._grupo_id, "ahora": ahora}
        self._sesion.execute(_ANULAR, parametros)
        self._sesion.execute(_ANULAR_INDICE, parametros)
        self._auditar(AccionAuditoria.INVITACION_ANULAR, invitacion.id, invitacion.rol, actor_id, request_id)

    def sin_usar_de(self, invitado_por: uuid.UUID, ahora: datetime) -> list[InvitacionParaAnular]:
        filas = self._sesion.execute(
            _SIN_USAR_DE, {"grupo_id": self._grupo_id, "usuario_id": invitado_por, "ahora": ahora}
        ).all()
        return [InvitacionParaAnular(id=f.id, rol=f.rol, vida=_vida(f)) for f in filas]

    def _auditar(
        self, accion: AccionAuditoria, invitacion_id: uuid.UUID, rol: str, actor_id: uuid.UUID, request_id: str | None
    ) -> None:
        self._registro.registrar(
            EntradaAuditoria(
                grupo_id=self._grupo_id,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=actor_id,
                accion=accion,
                entidad=EntidadAuditoria.INVITACION,
                entidad_id=invitacion_id,
                request_id=request_id,
                rol=rol,
            )
        )
