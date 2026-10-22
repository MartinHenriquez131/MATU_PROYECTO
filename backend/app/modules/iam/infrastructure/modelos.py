"""Modelos ORM del módulo iam, calzados con las tablas de la migración 0001.

Solo declaran las columnas que el módulo usa hoy. Las demás tienen valor por omisión en la base.
"""

import uuid

from sqlalchemy import ForeignKey, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UsuarioORM(Base):
    __tablename__ = "usuario"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    nombre: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)


class IndiceCredencialORM(Base):
    __tablename__ = "indice_credencial"

    email_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id"), unique=True)
