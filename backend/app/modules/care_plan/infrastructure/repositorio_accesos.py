"""Adaptador SQL del puerto RepositorioAccesos: acceso_relevo e indice_token (MATU-18, RF-05).

Trabaja con la sesión del contexto de grupo (sesion_de_grupo): la política acceso_familia acota
acceso_relevo al grupo y a quien puede ver el plan, y el filtro por grupo es explícito además de RLS.
indice_token no tiene RLS (02_rls.sql, excepciones declaradas) y no guarda nada sensible: la huella del
token, el grupo, el acceso y su vencimiento.

La auditoría relevo.compartir guarda solo identificadores y el motivo enumerado: sin el nombre ni el
teléfono del relevo, sin IP, sin el token y sin el PIN.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.care_plan.application.ports import AccesoListado, AccesoNuevo, Posicion
from app.modules.care_plan.domain.ficha import Autor
from app.modules.care_plan.domain.relevo import INTENTOS_PIN_MAXIMOS
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria, MotivoAuditoria
from app.shared.puertos import RegistroAuditoria

_NOMBRE_PILA_PERSONA = text(
    "SELECT nombre_pila FROM persona_cuidada"
    " WHERE id = :persona_id AND grupo_id = :grupo_id AND eliminado_en IS NULL"
)

_NOMBRE_USUARIO = text("SELECT nombre FROM usuario WHERE id = :usuario_id AND eliminado_en IS NULL")

_INSERTAR_ACCESO = text(
    "INSERT INTO acceso_relevo (id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, otorgado_a_telefono,"
    " nombre_pila_persona, nombre_pila_comparte, secciones_permitidas, motivo, token_hash, pin_hash,"
    " creado_en, expira_en, relevo_informado_en)"
    " VALUES (:id, :grupo_id, :plan_id, :otorgado_por, :nombre, :telefono, :nombre_persona, :nombre_comparte,"
    " :campos, :motivo, :token_hash, :pin_hash, :creado_en, :expira_en, :informado_en)"
)

_INSERTAR_INDICE = text(
    "INSERT INTO indice_token (token_hash, tipo, grupo_id, referencia_id, expira_en, creado_en)"
    " VALUES (:token_hash, 'relevo', :grupo_id, :id, :expira_en, :creado_en)"
)

# El estado en el orden del contrato: revocado, vencido, bloqueado y vigente
_ESTADO = (
    "CASE WHEN a.revocado_en IS NOT NULL THEN 'revocado'"
    " WHEN a.expira_en <= :ahora THEN 'vencido'"
    f" WHEN a.pin_intentos_fallidos >= {INTENTOS_PIN_MAXIMOS} THEN 'bloqueado'"
    " ELSE 'vigente' END"
)

# Quien compartió: su id y el nombre de pila copiado en el acceso, nunca el nombre completo ni el email
# (decisión 35). Una cuenta eliminada o que RLS no muestra queda en null
_LISTAR = text(
    "SELECT a.id, a.otorgado_a_nombre, a.otorgado_a_telefono, a.secciones_permitidas, a.motivo, a.creado_en,"
    " a.expira_en, a.revocado_en, a.pin_intentos_fallidos, a.usos, a.ultimo_uso_en,"
    " u.id AS autor_id, a.nombre_pila_comparte AS autor_nombre"
    " FROM acceso_relevo a LEFT JOIN usuario u ON u.id = a.otorgado_por AND u.eliminado_en IS NULL"
    " WHERE a.plan_id = :plan_id AND a.grupo_id = :grupo_id"
    f" AND (CAST(:estado AS text) IS NULL OR {_ESTADO} = CAST(:estado AS text))"
    " AND (CAST(:despues_en AS timestamptz) IS NULL"
    "      OR (a.creado_en, a.id) < (CAST(:despues_en AS timestamptz), CAST(:despues_id AS uuid)))"
    " ORDER BY a.creado_en DESC, a.id DESC LIMIT :limite"
)


def _utc(instante: datetime | None) -> datetime | None:
    return None if instante is None else instante.astimezone(UTC)


class RepositorioAccesosSQL:
    def __init__(self, sesion: Session, grupo_id: uuid.UUID, registro: RegistroAuditoria) -> None:
        self._sesion = sesion
        self._grupo_id = grupo_id
        self._registro = registro

    def nombre_pila_persona(self, persona_cuidada_id: uuid.UUID) -> str | None:
        fila = self._sesion.execute(
            _NOMBRE_PILA_PERSONA, {"persona_id": persona_cuidada_id, "grupo_id": self._grupo_id}
        ).one_or_none()
        return None if fila is None else str(fila.nombre_pila)

    def nombre_usuario(self, usuario_id: uuid.UUID) -> str | None:
        fila = self._sesion.execute(_NOMBRE_USUARIO, {"usuario_id": usuario_id}).one_or_none()
        return None if fila is None else str(fila.nombre)

    def crear(self, acceso: AccesoNuevo) -> None:
        parametros = {
            "id": acceso.id,
            "grupo_id": acceso.grupo_id,
            "plan_id": acceso.plan_id,
            "otorgado_por": acceso.otorgado_por,
            "nombre": acceso.nombre_relevo,
            "telefono": acceso.telefono_relevo,
            "nombre_persona": acceso.nombre_pila_persona,
            "nombre_comparte": acceso.nombre_pila_comparte,
            "campos": list(acceso.campos),
            "motivo": acceso.motivo,
            "token_hash": acceso.token_hash,
            "pin_hash": acceso.pin_hash,
            "creado_en": acceso.creado_en,
            "expira_en": acceso.expira_en,
            "informado_en": acceso.relevo_informado_en,
            "request_id": acceso.request_id,
        }
        self._sesion.execute(_INSERTAR_ACCESO, parametros)
        self._sesion.execute(_INSERTAR_INDICE, parametros)
        # relevo.compartir con el instante del acceso: RegistroAuditoriaSql lo toma del mismo Reloj
        self._registro.registrar(
            EntradaAuditoria(
                grupo_id=acceso.grupo_id,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=acceso.otorgado_por,
                accion=AccionAuditoria.RELEVO_COMPARTIR,
                entidad=EntidadAuditoria.ACCESO_RELEVO,
                entidad_id=acceso.id,
                motivo=MotivoAuditoria(acceso.motivo),
                request_id=acceso.request_id,
            )
        )

    def listar(
        self, plan_id: uuid.UUID, ahora: datetime, estado: str | None, despues_de: Posicion | None, limite: int
    ) -> list[AccesoListado]:
        filas = self._sesion.execute(
            _LISTAR,
            {
                "plan_id": plan_id,
                "grupo_id": self._grupo_id,
                "ahora": ahora,
                "estado": estado,
                "despues_en": None if despues_de is None else despues_de.creado_en,
                "despues_id": None if despues_de is None else despues_de.id,
                "limite": limite,
            },
        ).all()
        return [
            AccesoListado(
                id=f.id,
                nombre_relevo=f.otorgado_a_nombre,
                telefono_relevo=f.otorgado_a_telefono,
                campos=tuple(f.secciones_permitidas),
                motivo=f.motivo,
                creado_en=f.creado_en.astimezone(UTC),
                expira_en=f.expira_en.astimezone(UTC),
                revocado_en=_utc(f.revocado_en),
                pin_intentos_fallidos=f.pin_intentos_fallidos,
                usos=f.usos,
                ultimo_uso_en=_utc(f.ultimo_uso_en),
                otorgado_por=None if f.autor_id is None else Autor(id=f.autor_id, nombre=f.autor_nombre),
            )
            for f in filas
        ]
