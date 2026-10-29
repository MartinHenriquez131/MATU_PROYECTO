"""MATU-14 · RegistroAuditoriaSql contra PostgreSQL como matu_app (RF-08).

Los grupos los siembran las fábricas de MATU-30 (superusuario). El registro corre como matu_app
dentro de sesion_tenant, con el contexto del admin del grupo, igual que lo hará el caso de uso de
la ficha en MATU-12. Lo que quedó en la base se revisa como superusuario.

Limpieza: la fixture ``fabrica`` borra grupos y cuentas. Las filas de auditoría se quedan, igual que
las del alta de MATU-07 (tests/fabricas/sql.py): la tabla es de solo inserción y solo lleva
identificadores sintéticos. Cada prueba las encuentra por un request_id único.

Las pruebas test_lectura_queda_auditada y test_escritura_queda_auditada llegan con MATU-12, que
crea los endpoints de la ficha.
"""

import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Any

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import sesion_tenant
from app.shared.auditoria import (
    AccionAuditoria,
    ActorTipo,
    EntidadAuditoria,
    EntradaAuditoria,
    MotivoAuditoria,
)
from app.shared.auditoria_sql import RegistroAuditoriaSql
from tests.base_datos import DSN, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import Fabrica, GrupoCreado

pytestmark = [requiere_base, pytest.mark.rf("RF-08")]


@pytest.fixture
def sesiones() -> Iterator[sessionmaker[Session]]:
    """Sesiones como matu_app (DATABASE_URL), nunca como dueño ni superusuario."""
    url = obtener_configuracion().database_url
    assert url
    engine = create_engine(url, pool_size=1, max_overflow=0)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def grupo(fabrica: Fabrica) -> GrupoCreado:
    return fabrica.grupo()


@pytest.fixture
def otro_grupo(fabrica: Fabrica) -> GrupoCreado:
    return fabrica.grupo()


def _como_admin(sesiones: sessionmaker[Session], grupo: GrupoCreado) -> AbstractContextManager[Session]:
    """La transacción de una petición del admin: matu_app con app.usuario_id y app.grupo_id."""
    return sesion_tenant(sesiones, usuario_id=grupo.admin_id, grupo_id=grupo.id)


def _request_id() -> str:
    return f"req-matu14-{uuid.uuid4().hex}"


def _entrada(grupo: GrupoCreado, request_id: str, **cambios: Any) -> EntradaAuditoria:
    campos: dict[str, Any] = {
        "grupo_id": grupo.id,
        "actor_tipo": ActorTipo.USUARIO,
        "actor_ref": grupo.admin_id,
        "accion": AccionAuditoria.PLAN_LEER,
        "entidad": EntidadAuditoria.PLAN_CUIDADO,
        "entidad_id": uuid.uuid4(),
        "request_id": request_id,
    }
    campos.update(cambios)
    return EntradaAuditoria(**campos)


def _filas(request_id: str) -> list[tuple[Any, ...]]:
    """Las filas de auditoría de la petición, vistas como superusuario."""
    with psycopg.connect(DSN) as cx:
        return cx.execute(
            "SELECT id, grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, motivo, ip, request_id,"
            " ocurrido_en FROM auditoria WHERE request_id = %s ORDER BY id",
            (request_id,),
        ).fetchall()


def _registrar_una(sesiones: sessionmaker[Session], grupo: GrupoCreado, reloj: RelojFijo) -> tuple[Any, ...]:
    request_id = _request_id()
    with _como_admin(sesiones, grupo) as sesion:
        RegistroAuditoriaSql(sesion, reloj).registrar(_entrada(grupo, request_id))
    [fila] = _filas(request_id)
    return fila


# --- Camino feliz -----------------------------------------------------------------------------


def test_registrar_deja_una_fila_con_los_campos_de_la_entrada(
    sesiones: sessionmaker[Session], grupo: GrupoCreado, reloj_fijo: RelojFijo
) -> None:
    # Dada una entrada con motivo, como la de compartir la ficha
    request_id = _request_id()
    acceso_id = uuid.uuid4()
    entrada = _entrada(
        grupo,
        request_id,
        accion=AccionAuditoria.RELEVO_COMPARTIR,
        entidad=EntidadAuditoria.ACCESO_RELEVO,
        entidad_id=acceso_id,
        motivo=MotivoAuditoria.FIN_DE_SEMANA_FUERA,
    )

    # Cuando se registra en la transacción de una petición del admin
    with _como_admin(sesiones, grupo) as sesion:
        RegistroAuditoriaSql(sesion, reloj_fijo).registrar(entrada)

    # Entonces queda exactamente una fila, con el instante del Reloj y sin IP
    filas = _filas(request_id)
    assert len(filas) == 1
    _, grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, motivo, ip, req, ocurrido_en = filas[0]
    assert (grupo_id, actor_tipo, actor_ref) == (grupo.id, "usuario", grupo.admin_id)
    assert (accion, entidad, entidad_id) == ("relevo.compartir", "acceso_relevo", acceso_id)
    assert (motivo, req) == ("fin_de_semana_fuera", request_id)
    assert ip is None
    assert ocurrido_en == reloj_fijo.ahora()


def test_registrar_sin_motivo_ni_entidad_id_deja_nulos(
    sesiones: sessionmaker[Session], grupo: GrupoCreado, reloj_fijo: RelojFijo
) -> None:
    request_id = _request_id()

    with _como_admin(sesiones, grupo) as sesion:
        RegistroAuditoriaSql(sesion, reloj_fijo).registrar(_entrada(grupo, request_id, entidad_id=None))

    [fila] = _filas(request_id)
    assert (fila[6], fila[7], fila[8]) == (None, None, None)  # entidad_id, motivo, ip


# --- Solo inserción -----------------------------------------------------------------------------


def test_auditoria_no_se_modifica(sesiones: sessionmaker[Session], grupo: GrupoCreado, reloj_fijo: RelojFijo) -> None:
    # Dada una fila registrada por el adaptador
    fila = _registrar_una(sesiones, grupo, reloj_fijo)
    fila_id = fila[0]

    # Cuando matu_app intenta cambiarla, en el contexto de su propio grupo, entonces falla
    with pytest.raises(ProgrammingError) as actualizar, _como_admin(sesiones, grupo) as sesion:
        sesion.execute(text("UPDATE auditoria SET accion = 'plan.editar' WHERE id = :id"), {"id": fila_id})
    assert isinstance(actualizar.value.orig, InsufficientPrivilege)

    # Y cuando intenta borrarla, también falla
    with pytest.raises(ProgrammingError) as borrar, _como_admin(sesiones, grupo) as sesion:
        sesion.execute(text("DELETE FROM auditoria WHERE id = :id"), {"id": fila_id})
    assert isinstance(borrar.value.orig, InsufficientPrivilege)

    # Y la fila sigue intacta
    assert _filas(fila[9]) == [fila]


def test_auditoria_no_se_modifica_ni_como_superusuario(
    sesiones: sessionmaker[Session], grupo: GrupoCreado, reloj_fijo: RelojFijo
) -> None:
    # La segunda capa: el trigger auditoria_solo_insercion alcanza también a quien no tiene límites de permiso
    fila = _registrar_una(sesiones, grupo, reloj_fijo)

    with pytest.raises(InsufficientPrivilege, match="solo inserción"), psycopg.connect(DSN) as cx:
        cx.execute("UPDATE auditoria SET accion = 'plan.editar' WHERE id = %s", (fila[0],))
    with pytest.raises(InsufficientPrivilege, match="solo inserción"), psycopg.connect(DSN) as cx:
        cx.execute("DELETE FROM auditoria WHERE id = %s", (fila[0],))

    assert _filas(fila[9]) == [fila]


# --- Camino de error ------------------------------------------------------------------------------


def test_registrar_en_el_grupo_de_otra_familia_falla_por_rls(
    sesiones: sessionmaker[Session], grupo: GrupoCreado, otro_grupo: GrupoCreado, reloj_fijo: RelojFijo
) -> None:
    # Dado el contexto de una petición del admin de un grupo, y una entrada con el grupo de otra familia
    request_id = _request_id()
    ajena = _entrada(otro_grupo, request_id)

    # Cuando se registra, entonces la política auditoria_insertar la rechaza
    with pytest.raises(ProgrammingError) as error, _como_admin(sesiones, grupo) as sesion:
        RegistroAuditoriaSql(sesion, reloj_fijo).registrar(ajena)
    assert isinstance(error.value.orig, InsufficientPrivilege)

    # Y no queda fila
    assert _filas(request_id) == []


def test_si_registrar_falla_la_accion_completa_se_deshace(
    sesiones: sessionmaker[Session],
    fabrica: Fabrica,
    grupo: GrupoCreado,
    otro_grupo: GrupoCreado,
    reloj_fijo: RelojFijo,
) -> None:
    # Dada una petición que primero escribe (renombra el grupo y registra su propia auditoría)
    # y después intenta auditar en el grupo de otra familia
    request_id = _request_id()
    with pytest.raises(ProgrammingError), _como_admin(sesiones, grupo) as sesion:
        sesion.execute(
            text("UPDATE grupo_familiar SET nombre = :nombre WHERE id = :id"),
            {"nombre": "Familia renombrada", "id": grupo.id},
        )
        registro = RegistroAuditoriaSql(sesion, reloj_fijo)
        registro.registrar(_entrada(grupo, request_id, accion=AccionAuditoria.PLAN_EDITAR))
        registro.registrar(_entrada(otro_grupo, request_id))

    # Entonces no queda nada: ni la escritura previa ni su auditoría (sin la fila no hay respuesta)
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT nombre FROM grupo_familiar WHERE id = %s", (grupo.id,)).fetchone()
    assert fila == (grupo.nombre,)
    assert _filas(request_id) == []
