"""Modelos ORM de MATU.

El esquema se define en SQL (backend/db) y se aplica con Alembic. Los modelos se
agregan aquí a medida que cada historia los necesite, siempre calzando con las
tablas que ya existen.

Los roles de la familia (admin, cuidador, pagador, observador) no son una tabla:
son el campo membresia.rol. Los roles matu_owner, matu_app, matu_publisher y
matu_scheduler son roles de PostgreSQL (backend/db/00_roles.sql).
"""

from database import Base

__all__ = ["Base"]
