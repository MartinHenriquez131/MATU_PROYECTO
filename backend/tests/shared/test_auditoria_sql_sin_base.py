"""MATU-14 · Lo que RegistroAuditoriaSql manda a la base, con una sesión falsa (RF-08).

Sin PostgreSQL: verifica la sentencia y sus parámetros. El comportamiento contra la base (RLS, solo
inserción, rollback) está en test_auditoria_sql.py.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria, MotivoAuditoria
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import RegistroAuditoria
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-08")


@dataclass
class SesionFalsa:
    """Anota cada sentencia con sus parámetros. Con ``error``, lo lanza como lo haría la base."""

    ejecutado: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    error: Exception | None = None

    def execute(self, sentencia: Any, parametros: dict[str, Any]) -> None:
        if self.error is not None:
            raise self.error
        self.ejecutado.append((str(sentencia), parametros))

    def commit(self) -> None:
        raise AssertionError("el adaptador no hace commit: lo hace sesion_tenant")


def _entrada() -> EntradaAuditoria:
    return EntradaAuditoria(
        grupo_id=uuid.uuid4(),
        actor_tipo=ActorTipo.RELEVO,
        actor_ref=uuid.uuid4(),
        accion=AccionAuditoria.RELEVO_COMPARTIR,
        entidad=EntidadAuditoria.ACCESO_RELEVO,
        entidad_id=uuid.uuid4(),
        motivo=MotivoAuditoria.SALGO_UNAS_HORAS,
        request_id="req-sintetico-14",
    )


def test_inserta_una_fila_con_el_instante_del_reloj(reloj_fijo: RelojFijo) -> None:
    # Dado el adaptador sobre una sesión falsa, usado a través del puerto
    sesion = SesionFalsa()
    registro: RegistroAuditoria = RegistroAuditoriaSql(cast(Session, sesion), reloj_fijo)
    entrada = _entrada()

    # Cuando registra una entrada
    registro.registrar(entrada)

    # Entonces ejecuta un solo INSERT en auditoria, con los valores de la entrada y la hora del Reloj
    [(sql, parametros)] = sesion.ejecutado
    assert sql.startswith("INSERT INTO auditoria ")
    assert parametros == {
        "grupo_id": entrada.grupo_id,
        "actor_tipo": "relevo",
        "actor_ref": entrada.actor_ref,
        "accion": "relevo.compartir",
        "entidad": "acceso_relevo",
        "entidad_id": entrada.entidad_id,
        "motivo": "salgo_unas_horas",
        "request_id": "req-sintetico-14",
        "ocurrido_en": reloj_fijo.ahora(),
    }


def test_no_escribe_ip_ni_usa_la_hora_de_la_base(reloj_fijo: RelojFijo) -> None:
    sesion = SesionFalsa()

    RegistroAuditoriaSql(cast(Session, sesion), reloj_fijo).registrar(_entrada())

    [(sql, parametros)] = sesion.ejecutado
    columnas = sql.split("(", 1)[1].split(")", 1)[0]
    assert "ip" not in {c.strip() for c in columnas.split(",")}
    assert "ip" not in parametros
    assert "now()" not in sql.lower()
    assert "returning" not in sql.lower()


def test_motivo_ausente_va_como_nulo(reloj_fijo: RelojFijo) -> None:
    sesion = SesionFalsa()
    sin_motivo = EntradaAuditoria(
        grupo_id=uuid.uuid4(),
        actor_tipo=ActorTipo.USUARIO,
        actor_ref=uuid.uuid4(),
        accion=AccionAuditoria.PLAN_LEER,
        entidad=EntidadAuditoria.PLAN_CUIDADO,
    )

    RegistroAuditoriaSql(cast(Session, sesion), reloj_fijo).registrar(sin_motivo)

    [(_, parametros)] = sesion.ejecutado
    assert (parametros["motivo"], parametros["entidad_id"], parametros["request_id"]) == (None, None, None)


def test_si_la_base_rechaza_la_fila_el_error_sube(reloj_fijo: RelojFijo) -> None:
    # Dada una base que rechaza el INSERT
    sesion = SesionFalsa(error=RuntimeError("la base rechazó la fila"))

    # Cuando se registra, entonces el error sube tal cual: sin la fila no hay respuesta
    with pytest.raises(RuntimeError, match="rechazó"):
        RegistroAuditoriaSql(cast(Session, sesion), reloj_fijo).registrar(_entrada())
