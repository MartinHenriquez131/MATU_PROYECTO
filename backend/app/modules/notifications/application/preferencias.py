"""La preferencia propia de avisos de quiebre: GET y PUT /v1/yo/avisos (MATU-41, decisión 111).

Es de la persona, no del grupo: vale para todos sus grupos y por canal. El pagador y el observador la usan
para activar los avisos; el admin y el cuidador, para apagarlos (decisión 78).

Sin fila guardada para un canal, lo que se ve es lo que se aplicaría: activo si la persona es admin o
cuidador en algún grupo donde su membresía está activa, e inactivo si no. Guardar fija los dos canales.
"""

import uuid
from dataclasses import dataclass

from app.modules.consumption.domain.alerta import avisa_por_defecto
from app.modules.notifications.application.ports import RepositorioPreferencias
from app.modules.notifications.domain.aviso import TIPO_EVENTO_QUIEBRE, Canal, canal_activo


@dataclass(frozen=True)
class PreferenciaAvisos:
    correo: bool
    push: bool


def leer_preferencia(repositorio: RepositorioPreferencias, usuario_id: uuid.UUID) -> PreferenciaAvisos:
    guardadas = repositorio.guardadas(usuario_id, TIPO_EVENTO_QUIEBRE)
    por_defecto = any(avisa_por_defecto(rol) for rol in repositorio.roles_activos(usuario_id))
    return PreferenciaAvisos(
        correo=canal_activo(por_defecto=por_defecto, preferencia=guardadas.get(Canal.CORREO)),
        push=canal_activo(por_defecto=por_defecto, preferencia=guardadas.get(Canal.PUSH)),
    )


def guardar_preferencia(
    repositorio: RepositorioPreferencias, usuario_id: uuid.UUID, preferencia: PreferenciaAvisos
) -> PreferenciaAvisos:
    repositorio.guardar(
        usuario_id, TIPO_EVENTO_QUIEBRE, {Canal.CORREO: preferencia.correo, Canal.PUSH: preferencia.push}
    )
    return preferencia
