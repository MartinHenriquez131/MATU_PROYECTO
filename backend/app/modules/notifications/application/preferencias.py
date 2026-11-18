"""La preferencia propia de avisos de quiebre: GET y PUT /v1/yo/avisos (MATU-41, decisión 111).

La elección es de la persona y vale para todos sus grupos, por canal. Un canal sin fila guardada está «sin
elegir»: en cada grupo se usa el valor por omisión del rol (admin y cuidador sí, pagador y observador no,
decisión 78). El pagador y el observador la usan para activar; el admin y el cuidador, para apagar.

- GET: por canal, lo guardado; sin fila, activo si la persona es admin o cuidador en algún grupo donde su
  membresía está activa.
- PUT (decisión de Jorge del 04-11, tras la revisión de cierre): guarda un canal solo si su valor difiere del
  que muestra el GET, o si ese canal ya tenía una fila. Así, quien es admin en un grupo y observador en otro y
  solo apaga el push no queda con el correo activado en el grupo donde es observador.
- MATU-55 (decisión 259): el PUT registra avisos.preferencia en la misma transacción, solo si lo que devuelve el GET
  después es distinto de lo de antes. Actor la persona, entidad su cuenta, sin grupo, sin detalle y sin los valores.
  El GET no se audita.
- MATU-76 (C3): la preferencia de los avisos del pedido (``tipo_evento = 'pedido'``) va aparte, en ``pedido``. Es de
  la persona y vale para todos sus grupos, como la del insumo. Sin fila, activa por los dos canales, sea cual sea el
  rol: no usa ``avisa_por_defecto``. El correo de una devolución o una cancelación llega siempre (D-76-3): apagar
  ``pedido.correo`` apaga solo el de «Entregado» y «No entregado». El PUT trae ``pedido`` como opcional: sin él, esa
  preferencia no cambia. Un solo registro de auditoría por PUT, si cambió cualquiera de las dos.
"""

import uuid
from dataclasses import dataclass

from app.modules.consumption.domain.alerta import avisa_por_defecto
from app.modules.notifications.application.ports import RepositorioPreferencias
from app.modules.notifications.domain.aviso import (
    TIPO_EVENTO_PEDIDO,
    TIPO_EVENTO_QUIEBRE,
    Canal,
    canal_activo,
    canales_por_guardar,
)
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria


@dataclass(frozen=True)
class PreferenciaCanales:
    correo: bool
    push: bool


# MATU-76: sin fila, el aviso del pedido está activo por los dos canales para todos (C3)
PEDIDO_POR_DEFECTO = True


@dataclass(frozen=True)
class PreferenciaAvisos:
    """``correo`` y ``push``: el aviso del insumo (MATU-41). ``pedido``: el aviso del pedido (MATU-76). En el PUT,
    ``pedido`` None deja la preferencia del pedido como estaba."""

    correo: bool
    push: bool
    pedido: PreferenciaCanales | None = None


def canales_del_pedido_leidos(preferencia: PreferenciaAvisos) -> PreferenciaCanales:
    """La preferencia del pedido de una preferencia **leída** (``leer_preferencia`` siempre la trae). Sin ella falla
    de forma controlada, aunque Python corra con ``-O``: un ``assert`` ahí desaparecería. El mensaje no lleva datos."""
    if preferencia.pedido is None:
        raise RuntimeError("la preferencia leída no trae la del pedido")
    return preferencia.pedido


def _por_defecto(repositorio: RepositorioPreferencias, usuario_id: uuid.UUID) -> bool:
    return any(avisa_por_defecto(rol) for rol in repositorio.roles_activos(usuario_id))


def _canales(guardadas: dict[Canal, bool], por_defecto: bool) -> PreferenciaCanales:
    return PreferenciaCanales(
        correo=canal_activo(por_defecto=por_defecto, preferencia=guardadas.get(Canal.CORREO)),
        push=canal_activo(por_defecto=por_defecto, preferencia=guardadas.get(Canal.PUSH)),
    )


def leer_preferencia(repositorio: RepositorioPreferencias, usuario_id: uuid.UUID) -> PreferenciaAvisos:
    insumo = _canales(repositorio.guardadas(usuario_id, TIPO_EVENTO_QUIEBRE), _por_defecto(repositorio, usuario_id))
    pedido = _canales(repositorio.guardadas(usuario_id, TIPO_EVENTO_PEDIDO), PEDIDO_POR_DEFECTO)
    return PreferenciaAvisos(correo=insumo.correo, push=insumo.push, pedido=pedido)


def _guardar(
    repositorio: RepositorioPreferencias,
    usuario_id: uuid.UUID,
    tipo: str,
    pedidos: PreferenciaCanales,
    por_defecto: bool,
) -> None:
    cambios = canales_por_guardar(
        pedidos={Canal.CORREO: pedidos.correo, Canal.PUSH: pedidos.push},
        guardadas=repositorio.guardadas(usuario_id, tipo),
        por_defecto=por_defecto,
    )
    if cambios:
        repositorio.guardar(usuario_id, tipo, cambios)


def guardar_preferencia(
    repositorio: RepositorioPreferencias,
    usuario_id: uuid.UUID,
    preferencia: PreferenciaAvisos,
    auditoria: RegistroAuditoria,
    request_id: str | None = None,
) -> PreferenciaAvisos:
    antes = leer_preferencia(repositorio, usuario_id)
    insumo = PreferenciaCanales(correo=preferencia.correo, push=preferencia.push)
    _guardar(repositorio, usuario_id, TIPO_EVENTO_QUIEBRE, insumo, _por_defecto(repositorio, usuario_id))
    if preferencia.pedido is not None:
        _guardar(repositorio, usuario_id, TIPO_EVENTO_PEDIDO, preferencia.pedido, PEDIDO_POR_DEFECTO)
    despues = leer_preferencia(repositorio, usuario_id)
    if despues != antes:
        auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=AccionAuditoria.AVISOS_PREFERENCIA,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario_id,
                request_id=request_id,
            )
        )
    return despues
