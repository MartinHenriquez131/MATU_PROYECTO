"""Adaptador SQL del puerto RepositorioUsuarios."""

from psycopg import errors
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.modules.iam.application.ports import CredencialGuardada, NuevoUsuario
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

    def buscar_credencial(self, email_hash: bytes) -> CredencialGuardada | None:
        with self._fabrica() as sesion, sesion.begin():
            # indice_credencial no tiene RLS: es la única forma de pasar de email a usuario sin
            # contexto. Solo guarda el HMAC del email, nunca el email.
            usuario_id = sesion.execute(
                select(IndiceCredencialORM.usuario_id).where(IndiceCredencialORM.email_hash == email_hash)
            ).scalar_one_or_none()
            if usuario_id is None:
                return None
            # La fila de usuario sí tiene RLS (usuario_propio: id = app_usuario()). Se fija el
            # contexto del usuario recién resuelto, local a la transacción (sección 7.7).
            # TODO(MATU-02): reemplazar por sesion_tenant cuando esté en main.
            sesion.execute(text("SELECT set_config('app.usuario_id', :id, true)"), {"id": str(usuario_id)})
            # Con SQL explícito y no con UsuarioORM: mapear estado en el ORM cambiaría el INSERT
            # del registro, que hoy deja ese valor a la base.
            fila = sesion.execute(
                text("SELECT password_hash, estado FROM usuario WHERE id = :id"), {"id": usuario_id}
            ).one_or_none()
            if fila is None:
                return None
            return CredencialGuardada(usuario_id=usuario_id, password_hash=fila.password_hash, estado=fila.estado)
