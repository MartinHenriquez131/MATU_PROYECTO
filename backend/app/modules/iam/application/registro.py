"""Caso de uso: crear una cuenta (MATU-04, RF-37), con la aceptación de la política (MATU-75)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.iam.application.ports import HasherContrasenas, NuevoUsuario, RepositorioUsuarios
from app.modules.iam.domain.credenciales import (
    DominioNoPermitido,
    es_dominio_reservado,
    indice_email,
    normalizar_email,
)
from app.modules.iam.domain.politica import PoliticaVigente, aceptar


@dataclass(frozen=True)
class CuentaCreada:
    id: uuid.UUID
    nombre: str
    email: str


def registrar_usuario(
    *,
    nombre: str,
    email: str,
    contrasena: str,
    telefono: str,
    pepper: bytes,
    hasher: HasherContrasenas,
    repositorio: RepositorioUsuarios,
    politica: PoliticaVigente,
    ahora: datetime,
    huella_mostrada: str,
    solo_dominios_reservados: bool = False,
) -> CuentaCreada:
    """Crea la cuenta, su fila de indice_credencial y su aceptación de la política vigente.

    La API ya exigió acepta_politica = true y la huella que se mostró (decisión 182). La versión y la huella las estampa
    el servidor (decisión D2); si la huella mostrada no es la vigente, lanza PoliticaCambio antes de hashear ni de
    tocar el repositorio.

    El identificador se genera aquí y no en la base: la política RLS de usuario exige que la
    fila nueva sea la del usuario en contexto (id = app.usuario_id), y para fijar ese contexto
    hay que conocer el id antes del INSERT.

    Con solo_dominios_reservados (staging, decisión 105), un email que no es de un dominio reservado
    lanza DominioNoPermitido antes de hashear ni de tocar el repositorio.

    Lanza EmailYaRegistrado si el email ya tiene una cuenta.
    """
    email_normalizado = normalizar_email(email)
    if solo_dominios_reservados and not es_dominio_reservado(email_normalizado):
        raise DominioNoPermitido()
    aceptacion = aceptar(politica, huella_mostrada, ahora)
    nuevo = NuevoUsuario(
        id=uuid.uuid4(),
        nombre=nombre.strip(),
        email=email_normalizado,
        password_hash=hasher.hashear(contrasena),
        email_hash=indice_email(pepper, email_normalizado),
        telefono=telefono,
        aceptacion=aceptacion,
    )
    repositorio.crear(nuevo)
    return CuentaCreada(id=nuevo.id, nombre=nuevo.nombre, email=nuevo.email)
