"""MATU-02 · El helper sesion_tenant (arquitectura, sección 7.7; ADR-013).

Las pruebas de validación y de orden usan una sesión falsa que anota lo que se ejecuta: no tocan
la base. Las demás corren contra PostgreSQL real como matu_app (DATABASE_URL), con un engine de
una sola conexión para que dos transacciones seguidas usen de verdad la misma conexión. Los datos
se siembran y se borran como superusuario (MATU_TEST_DSN).
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, cast

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import sesion_tenant
from tests.base_datos import DSN, requiere_base

# --- Sesión falsa --------------------------------------------------------------------------


@dataclass
class SesionFalsa:
    """Anota cada set_config y si la transacción terminó en commit o en rollback."""

    fijado: list[tuple[str, str]] = field(default_factory=list)
    final: str | None = None

    def __enter__(self) -> "SesionFalsa":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def begin(self) -> "TransaccionFalsa":
        return TransaccionFalsa(self)

    def execute(self, _sentencia: Any, parametros: dict[str, str]) -> None:
        self.fijado.append((parametros["clave"], parametros["valor"]))


@dataclass
class TransaccionFalsa:
    sesion: SesionFalsa

    def __enter__(self) -> None:
        return None

    def __exit__(self, tipo: type[BaseException] | None, *exc: object) -> None:
        self.sesion.final = "commit" if tipo is None else "rollback"


def _fabrica_falsa(sesion: SesionFalsa) -> sessionmaker[Session]:
    return cast(sessionmaker[Session], lambda: sesion)


def _fabrica_que_falla() -> sessionmaker[Session]:
    def fallar() -> None:
        raise AssertionError("no debía abrir una sesión")

    return cast(sessionmaker[Session], fallar)


U = uuid.UUID("00000000-0000-0000-0000-0000000002a1")
G = uuid.UUID("00000000-0000-0000-0000-0000000002a2")
OTRO = uuid.UUID("00000000-0000-0000-0000-0000000002a3")


# --- Validación y orden, sin base ----------------------------------------------------------


@pytest.mark.rf("ADR-013")
def test_fija_usuario_primero_y_grupo_despues() -> None:
    sesion = SesionFalsa()

    with sesion_tenant(_fabrica_falsa(sesion), grupo_id=G, usuario_id=U):
        pass

    assert sesion.fijado == [("app.usuario_id", str(U)), ("app.grupo_id", str(G))]
    assert sesion.final == "commit"


def test_fija_todas_las_variables_en_orden_y_solo_las_que_llegan() -> None:
    sesion = SesionFalsa()

    with sesion_tenant(_fabrica_falsa(sesion), rol="sistema", repartidor_id=OTRO, comercio_id=G, usuario_id=U):
        pass

    assert sesion.fijado == [
        ("app.usuario_id", str(U)),
        ("app.comercio_id", str(G)),
        ("app.repartidor_id", str(OTRO)),
        ("app.rol", "sistema"),
    ]


@pytest.mark.rf("ADR-013")
def test_acepta_relevo_con_acceso_y_sin_grupo() -> None:
    sesion = SesionFalsa()

    with sesion_tenant(_fabrica_falsa(sesion), acceso_relevo_id=OTRO, rol="relevo"):
        pass

    assert sesion.fijado == [("app.acceso_relevo_id", str(OTRO)), ("app.rol", "relevo")]


@pytest.mark.rf("ADR-013")
@pytest.mark.parametrize(
    "contexto",
    [
        {"acceso_relevo_id": OTRO, "grupo_id": G},
        {"acceso_relevo_id": OTRO, "grupo_id": G, "rol": "relevo"},
        {"rol": "relevo", "grupo_id": G},
    ],
)
def test_relevo_con_grupo_se_rechaza(contexto: dict[str, Any]) -> None:
    # Hallazgo 2 del modelo de datos (sección 5.4): el relevo nunca fija app.grupo_id
    with pytest.raises(ValueError), sesion_tenant(_fabrica_que_falla(), **contexto):
        pass


@pytest.mark.parametrize("rol", ["admin", "matu_owner", "OPERACION", ""])
def test_rol_no_permitido_se_rechaza(rol: str) -> None:
    with pytest.raises(ValueError), sesion_tenant(_fabrica_que_falla(), usuario_id=U, rol=rol):
        pass


def test_excepcion_hace_rollback_y_sigue() -> None:
    sesion = SesionFalsa()

    with pytest.raises(RuntimeError), sesion_tenant(_fabrica_falsa(sesion), usuario_id=U):
        raise RuntimeError("falla de la ruta")

    assert sesion.final == "rollback"


# --- Contra PostgreSQL ---------------------------------------------------------------------


@dataclass(frozen=True)
class Semilla:
    usuario_id: uuid.UUID
    grupo_id: uuid.UUID


@pytest.fixture
def fabrica_una_conexion() -> Iterator[sessionmaker[Session]]:
    """Un pool de una sola conexión: dos transacciones seguidas usan la misma."""
    url = obtener_configuracion().database_url
    assert url
    engine = create_engine(url, pool_size=1, max_overflow=0)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def semilla() -> Iterator[Semilla]:
    """Un usuario, su grupo con membresía activa y una notificación del grupo, como superusuario."""
    usuario_id, grupo_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "INSERT INTO usuario (id, email, nombre, password_hash) VALUES (%s, %s, 'Familiar Sintético', 'x')",
            (usuario_id, f"familiar.{usuario_id.hex[:12]}@ejemplo.cl"),
        )
        cx.execute(
            "INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES (%s, 'Familia Sintética', %s)",
            (grupo_id, usuario_id),
        )
        cx.execute("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (%s, %s, 'admin')", (grupo_id, usuario_id))
        cx.execute(
            "INSERT INTO notificacion (usuario_id, grupo_id, evento_id, canal, plantilla)"
            " VALUES (%s, %s, 1, 'correo', 'prueba')",
            (usuario_id, grupo_id),
        )
    try:
        yield Semilla(usuario_id=usuario_id, grupo_id=grupo_id)
    finally:
        with psycopg.connect(DSN, autocommit=True) as cx:
            cx.execute("DELETE FROM notificacion WHERE usuario_id = %s", (usuario_id,))
            cx.execute("DELETE FROM membresia WHERE usuario_id = %s", (usuario_id,))
            cx.execute("DELETE FROM grupo_familiar WHERE creado_por = %s", (usuario_id,))
            cx.execute("DELETE FROM usuario WHERE id = %s", (usuario_id,))


def _valor(sesion: Session, sql: str, **parametros: Any) -> Any:
    return sesion.execute(text(sql), parametros).scalar_one()


def _contexto(sesion: Session, variable: str) -> Any:
    return _valor(sesion, "SELECT current_setting(:v, true)", v=variable)


@requiere_base
@pytest.mark.rf("ADR-013")
def test_contexto_no_se_filtra_entre_peticiones(fabrica_una_conexion: sessionmaker[Session], semilla: Semilla) -> None:
    # Dada una transacción con el contexto del usuario y su grupo
    with sesion_tenant(fabrica_una_conexion, usuario_id=semilla.usuario_id, grupo_id=semilla.grupo_id) as sesion:
        conexion = _valor(sesion, "SELECT pg_backend_pid()")
        assert _contexto(sesion, "app.grupo_id") == str(semilla.grupo_id)
        assert _valor(sesion, "SELECT count(*) FROM grupo_familiar WHERE id = :g", g=semilla.grupo_id) == 1

    # Cuando la siguiente transacción, en la misma conexión del pool, no fija contexto
    with sesion_tenant(fabrica_una_conexion) as sesion:
        assert _valor(sesion, "SELECT pg_backend_pid()") == conexion

        # Entonces no hereda nada: sin variables y cero filas en tablas con RLS
        assert _contexto(sesion, "app.usuario_id") in (None, "")
        assert _contexto(sesion, "app.grupo_id") in (None, "")
        assert _valor(sesion, "SELECT count(*) FROM grupo_familiar") == 0
        assert _valor(sesion, "SELECT count(*) FROM membresia") == 0
        assert _valor(sesion, "SELECT count(*) FROM notificacion") == 0


@requiere_base
@pytest.mark.rf("ADR-013")
def test_contexto_no_se_filtra_tras_un_rollback(fabrica_una_conexion: sessionmaker[Session], semilla: Semilla) -> None:
    with (
        pytest.raises(RuntimeError),
        sesion_tenant(fabrica_una_conexion, usuario_id=semilla.usuario_id, grupo_id=semilla.grupo_id),
    ):
        raise RuntimeError("falla de la ruta")

    with sesion_tenant(fabrica_una_conexion) as sesion:
        assert _contexto(sesion, "app.grupo_id") in (None, "")
        assert _valor(sesion, "SELECT count(*) FROM grupo_familiar") == 0


@requiere_base
@pytest.mark.rf("ADR-013")
def test_sistema_sin_grupo_cero_filas(fabrica_una_conexion: sessionmaker[Session], semilla: Semilla) -> None:
    # Dado el rol sistema sin grupo (el worker antes de tomar un job)
    with sesion_tenant(fabrica_una_conexion, rol="sistema") as sesion:
        # Entonces no alcanza ninguna fila de negocio
        for tabla in ("notificacion", "grupo_familiar", "membresia", "persona_cuidada", "pedido"):
            assert _valor(sesion, f"SELECT count(*) FROM {tabla}") == 0, tabla

    # Y con el grupo fijado alcanza la notificación de ese grupo: el cero de arriba no es vacío
    with sesion_tenant(fabrica_una_conexion, grupo_id=semilla.grupo_id, rol="sistema") as sesion:
        assert _valor(sesion, "SELECT count(*) FROM notificacion WHERE grupo_id = :g", g=semilla.grupo_id) == 1


@requiere_base
def test_commit_al_salir_y_rollback_ante_excepcion(
    fabrica_una_conexion: sessionmaker[Session], semilla: Semilla
) -> None:
    confirmado, revertido = uuid.uuid4(), uuid.uuid4()
    insertar = "INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES (:id, 'Familia Sintética', :u)"

    # Dado un INSERT que termina bien y otro seguido de una excepción
    with sesion_tenant(fabrica_una_conexion, usuario_id=semilla.usuario_id) as sesion:
        sesion.execute(text(insertar), {"id": confirmado, "u": semilla.usuario_id})
    with pytest.raises(RuntimeError), sesion_tenant(fabrica_una_conexion, usuario_id=semilla.usuario_id) as sesion:
        sesion.execute(text(insertar), {"id": revertido, "u": semilla.usuario_id})
        raise RuntimeError("falla de la ruta")

    # Entonces el primero quedó guardado y el segundo no
    with psycopg.connect(DSN) as cx:
        filas = cx.execute("SELECT id FROM grupo_familiar WHERE id = ANY(%s)", ([confirmado, revertido],)).fetchall()
    assert [fila[0] for fila in filas] == [confirmado]
