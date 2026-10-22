"""Fixtures y consultas de apoyo de iam. El entorno de la API (EntornoIam, entorno_iam) vive en
tests/modules/conftest.py, que comparte con care_circle."""

import uuid
from typing import Any

import psycopg

from tests.base_datos import DSN, requiere_base
from tests.modules.conftest import EntornoIam

__all__ = ["DSN", "EntornoIam", "requiere_base"]


def fila_usuario(usuario_id: uuid.UUID) -> dict[str, Any] | None:
    with psycopg.connect(DSN) as cx, cx.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT id, email, nombre, password_hash FROM usuario WHERE id = %s", (usuario_id,))
        return cur.fetchone()


def filas_indice(usuario_id: uuid.UUID) -> list[dict[str, Any]]:
    with psycopg.connect(DSN) as cx, cx.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT email_hash, usuario_id FROM indice_credencial WHERE usuario_id = %s", (usuario_id,))
        return cur.fetchall()


def contar_usuarios_con_email(email: str) -> int:
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT count(*) FROM usuario WHERE lower(email) = lower(%s)", (email,)).fetchone()
        assert fila is not None
        return int(fila[0])


def fijar_estado(usuario_id: uuid.UUID, estado: str) -> None:
    """Cambia el estado de una cuenta como superusuario: la API aún no bloquea cuentas."""
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE usuario SET estado = %s WHERE id = %s", (estado, usuario_id))
