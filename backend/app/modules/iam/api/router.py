"""Rutas de iam: crear una cuenta (MATU-04)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.config import obtener_configuracion
from app.core.db import fabrica_sesiones
from app.core.errores import ErrorMATU
from app.modules.iam.api.esquemas import CuentaCreadaRespuesta, SolicitudRegistro
from app.modules.iam.application.ports import HasherContrasenas, RepositorioUsuarios
from app.modules.iam.application.registro import registrar_usuario
from app.modules.iam.domain.credenciales import EmailYaRegistrado
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id
from app.modules.iam.infrastructure.repositorio_usuarios import RepositorioUsuariosSQL

router = APIRouter(tags=["usuarios"])


def obtener_pepper_email() -> bytes:
    pepper = obtener_configuracion().pepper_email
    if pepper is None:
        raise RuntimeError("Falta PEPPER_EMAIL. Copia .env.example a .env y complétalo.")
    return pepper.get_secret_value().encode("utf-8")


def obtener_hasher() -> HasherContrasenas:
    return HasherArgon2id()


def obtener_repositorio_usuarios() -> RepositorioUsuarios:
    return RepositorioUsuariosSQL(fabrica_sesiones())


@router.post("/usuarios", status_code=status.HTTP_201_CREATED, response_model=CuentaCreadaRespuesta)
def crear_cuenta(
    solicitud: SolicitudRegistro,
    pepper: Annotated[bytes, Depends(obtener_pepper_email)],
    hasher: Annotated[HasherContrasenas, Depends(obtener_hasher)],
    repositorio: Annotated[RepositorioUsuarios, Depends(obtener_repositorio_usuarios)],
) -> CuentaCreadaRespuesta:
    try:
        cuenta = registrar_usuario(
            nombre=solicitud.nombre,
            email=solicitud.email,
            contrasena=solicitud.contrasena,
            pepper=pepper,
            hasher=hasher,
            repositorio=repositorio,
        )
    except EmailYaRegistrado:
        # Riesgo aceptado en el backlog: el 409 revela que el email existe. Se mitiga con el
        # límite por IP de MATU-25. El detalle nunca repite el email.
        raise ErrorMATU(
            409, tipo="email-registrado", detalle="Ese email ya tiene una cuenta. Inicia sesión"
        ) from None
    return CuentaCreadaRespuesta(id=cuenta.id, nombre=cuenta.nombre, email=cuenta.email)
