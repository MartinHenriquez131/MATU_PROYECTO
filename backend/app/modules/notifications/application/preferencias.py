"""La preferencia propia de avisos de quiebre: GET y PUT /v1/yo/avisos (MATU-41, decisión 111).

La elección es de la persona y vale para todos sus grupos, por canal. Un canal sin fila guardada está «sin
elegir»: en cada grupo se usa el valor por omisión del rol (admin y cuidador sí, pagador y observador no,
decisión 78). El pagador y el observador la usan para activar; el admin y el cuidador, para apagar.

- GET: por canal, lo guardado; sin fila, activo si la persona es admin o cuidador en algún grupo donde su
  membresía está activa.
- PUT (decisión de Jorge del 04-11, tras la revisión de cierre): guarda un canal solo si su valor difiere del
  que muestra el GET, o si ese canal ya tenía una fila. Así, quien es admin en un grupo y observador en otro y
  solo apaga el push no queda con el correo activado en el grupo donde es observador.
"""

import uuid
from dataclasses import dataclass

from app.modules.consumption.domain.alerta import avisa_por_defecto
from app.modules.notifications.application.ports import RepositorioPreferencias
from app.modules.notifications.domain.aviso import TIPO_EVENTO_QUIEBRE, Canal, canal_activo, canales_por_guardar


@dataclass(frozen=True)
class PreferenciaAvisos:
    correo: bool
    push: bool


def _por_defecto(repositorio: RepositorioPreferencias, usuario_id: uuid.UUID) -> bool:
    return any(avisa_por_defecto(rol) for rol in repositorio.roles_activos(usuario_id))


def leer_preferencia(repositorio: RepositorioPreferencias, usuario_id: uuid.UUID) -> PreferenciaAvisos:
    guardadas = repositorio.guardadas(usuario_id, TIPO_EVENTO_QUIEBRE)
    por_defecto = _por_defecto(repositorio, usuario_id)
    return PreferenciaAvisos(
        correo=canal_activo(por_defecto=por_defecto, preferencia=guardadas.get(Canal.CORREO)),
        push=canal_activo(por_defecto=por_defecto, preferencia=guardadas.get(Canal.PUSH)),
    )


def guardar_preferencia(
    repositorio: RepositorioPreferencias, usuario_id: uuid.UUID, preferencia: PreferenciaAvisos
) -> PreferenciaAvisos:
    guardadas = repositorio.guardadas(usuario_id, TIPO_EVENTO_QUIEBRE)
    pedidos = {Canal.CORREO: preferencia.correo, Canal.PUSH: preferencia.push}
    cambios = canales_por_guardar(
        pedidos=pedidos, guardadas=guardadas, por_defecto=_por_defecto(repositorio, usuario_id)
    )
    if cambios:
        repositorio.guardar(usuario_id, TIPO_EVENTO_QUIEBRE, cambios)
    return leer_preferencia(repositorio, usuario_id)
