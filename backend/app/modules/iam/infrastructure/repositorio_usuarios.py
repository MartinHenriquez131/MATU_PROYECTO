"""Adaptador SQL del puerto RepositorioUsuarios."""

from psycopg import errors
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.iam.application.ports import CredencialGuardada, NuevoUsuario
from app.modules.iam.domain.credenciales import EmailYaRegistrado
from app.modules.iam.infrastructure.modelos import IndiceCredencialORM, UsuarioORM


class RepositorioUsuariosSQL:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def crear(self, usuario: NuevoUsuario) -> None:
        try:
            # La política usuario_propio_crear solo deja insertar la fila del usuario en contexto.
            # El registro es el único caso en que la API fija app.usuario_id sin un token:
            # el usuario aún no existe.
            with sesion_tenant(self._fabrica, usuario_id=usuario.id) as sesion:
                sesion.add(
                    UsuarioORM(
                        id=usuario.id,
                        email=usuario.email,
                        nombre=usuario.nombre,
                        password_hash=usuario.password_hash,
                        telefono=usuario.telefono,
                    )
                )
                sesion.flush()
                sesion.add(IndiceCredencialORM(email_hash=usuario.email_hash, usuario_id=usuario.id))
        except IntegrityError as exc:
            # usuario_email_uq o la llave de indice_credencial: el email ya tiene cuenta.
            # Se lanza sin encadenar: el mensaje de la base trae el email.
            if isinstance(exc.orig, errors.UniqueViolation):
                raise EmailYaRegistrado() from None
            raise

    def buscar_credencial(self, email_hash: bytes) -> CredencialGuardada | None:
        # Paso 1. indice_credencial no tiene RLS: es la única forma de pasar de email a usuario sin
        # contexto. Solo guarda el HMAC del email, nunca el email.
        with self._fabrica() as sesion, sesion.begin():
            usuario_id = sesion.execute(
                select(IndiceCredencialORM.usuario_id).where(IndiceCredencialORM.email_hash == email_hash)
            ).scalar_one_or_none()
        if usuario_id is None:
            return None
        # Paso 2. La fila de usuario sí tiene RLS (usuario_propio_leer: id = app_usuario()). Se lee con
        # el contexto del usuario recién resuelto, en su propia transacción.
        with sesion_tenant(self._fabrica, usuario_id=usuario_id) as sesion:
            # matu_app no lee usuario.password_hash (migración 0020, MATU-66): iam_credencial, SECURITY
            # DEFINER, devuelve el hash y el estado solo de la cuenta del contexto, y nunca a operación.
            fila = sesion.execute(
                text("SELECT password_hash, estado FROM iam_credencial(:id)"), {"id": usuario_id}
            ).one_or_none()
            if fila is None:
                return None
            return CredencialGuardada(usuario_id=usuario_id, password_hash=fila.password_hash, estado=fila.estado)
