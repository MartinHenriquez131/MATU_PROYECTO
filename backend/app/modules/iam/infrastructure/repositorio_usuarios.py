"""Adaptador SQL del puerto RepositorioUsuarios."""

from psycopg import errors
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.modules.iam.application.ports import NuevoUsuario
from app.modules.iam.domain.credenciales import EmailYaRegistrado
from app.modules.iam.infrastructure.modelos import IndiceCredencialORM, UsuarioORM


class RepositorioUsuariosSQL:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def crear(self, usuario: NuevoUsuario) -> None:
        try:
            with self._fabrica() as sesion, sesion.begin():
                # La política usuario_propio solo deja insertar la fila del usuario en contexto.
                # El registro es el único caso en que la API fija app.usuario_id sin un token:
                # el usuario aún no existe. Local a la transacción, como pide la sección 7.7.
                # TODO(MATU-02): reemplazar por sesion_tenant cuando esté en main.
                sesion.execute(
                    text("SELECT set_config('app.usuario_id', :id, true)"), {"id": str(usuario.id)}
                )
                sesion.add(
                    UsuarioORM(
                        id=usuario.id,
                        email=usuario.email,
                        nombre=usuario.nombre,
                        password_hash=usuario.password_hash,
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
