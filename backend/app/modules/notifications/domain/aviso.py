"""Reglas puras de los avisos por correo y push (MATU-41, RF-39, decisiones 107 y 108).

Sin I/O y sin reloj del sistema. Lo que viene de otros módulos (si la autorización de ``consumo`` está
vigente, si el rol avisa por defecto) llega ya calculado como booleano: domain/ solo importa la biblioteca
estándar, app.shared y su propio domain/.

- **Destinatarios** (decisión 78 de MATU-37): un canal está activo si la persona lo eligió en
  ``preferencia_notificacion``; si no hay fila, según su rol (admin y cuidador sí, pagador y observador
  no). Es destinataria quien tiene al menos un canal activo.
- **Canales** (decisión de Jorge del 04-11): el correo es el canal garantizado y el push va además. Cada
  uno es su propia fila ``notificacion``. Nunca se busca otro canal (ni SMS ni el celular de MATU-57).
- **Antes de cada envío**, en cada intento y en cada canal, se revisan en este orden la autorización, la
  alerta, el miembro y el canal con su destino. El primero que falla da el código de la fila omitida.
- ``notificacion.error`` es un código de una lista cerrada (CHECK notificacion_error, migración 0014).
  Nunca la respuesta del proveedor.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class Canal(StrEnum):
    CORREO = "correo"
    PUSH = "push"


# El correo primero: es el canal garantizado. El push va además
CANALES: tuple[Canal, ...] = (Canal.CORREO, Canal.PUSH)

# preferencia_notificacion.tipo_evento y notificacion.plantilla del aviso de quiebre
TIPO_EVENTO_QUIEBRE = "quiebre_proximo"
PLANTILLA_QUIEBRE = "quiebre_proximo"


class EstadoNotificacion(StrEnum):
    PENDIENTE = "pendiente"
    ENVIADA = "enviada"
    FALLIDA = "fallida"
    OMITIDA = "omitida"


class CodigoAviso(StrEnum):
    """La lista cerrada de notificacion.error (CHECK notificacion_error)."""

    SIN_AUTORIZACION = "sin_autorizacion"
    ALERTA_CERRADA = "alerta_cerrada"
    MIEMBRO_INACTIVO = "miembro_inactivo"
    SIN_DESTINO = "sin_destino"
    PUSH_EXPIRADO = "push_expirado"
    PROVEEDOR_RECHAZO = "proveedor_rechazo"
    PROVEEDOR_NO_DISPONIBLE = "proveedor_no_disponible"


def canal_activo(*, por_defecto: bool, preferencia: bool | None) -> bool:
    """La preferencia guardada manda; sin fila, lo que corresponde al rol (``avisa_por_defecto``)."""
    return por_defecto if preferencia is None else preferencia


def canales_activos(*, por_defecto: bool, preferencias: Mapping[Canal, bool | None]) -> tuple[Canal, ...]:
    """Los canales por los que la persona recibe el aviso en este grupo, el correo primero. Solo para esos se
    crea una fila: un canal que la persona apagó no tiene fila."""
    return tuple(c for c in CANALES if canal_activo(por_defecto=por_defecto, preferencia=preferencias.get(c)))


def es_destinatario(*, por_defecto: bool, preferencias: Mapping[Canal, bool | None]) -> bool:
    """Si la persona recibe el aviso por al menos un canal. Si no, no se crea ninguna fila para ella."""
    return bool(canales_activos(por_defecto=por_defecto, preferencias=preferencias))


def canales_por_guardar(
    *, pedidos: Mapping[Canal, bool], guardadas: Mapping[Canal, bool], por_defecto: bool
) -> dict[Canal, bool]:
    """Lo que el PUT /v1/yo/avisos persiste (decisión 111): un canal se guarda solo si ya tenía fila, o si el
    valor pedido difiere del que la persona ve (``por_defecto`` sin fila). Un canal sin fila queda «sin
    elegir» y en cada grupo sigue el valor por omisión del rol."""
    return {
        canal: valor
        for canal, valor in pedidos.items()
        if canal in guardadas or valor != canal_activo(por_defecto=por_defecto, preferencia=None)
    }


@dataclass(frozen=True)
class Revision:
    """Lo que se revisa antes de cada envío, ya resuelto contra la base y el Reloj."""

    autorizado: bool  # autorización de consumo VIGENTE (no retirada y con la revisión de 12 meses al día)
    alerta_abierta: bool  # la alerta sigue pendiente o notificada y el perfil existe
    miembro_activo: bool  # membresía activa y usuario activo
    canal_activo: bool  # la persona no apagó este canal
    con_destino: bool  # hay correo, o al menos un dispositivo con push_token


def motivo_omision(revision: Revision) -> CodigoAviso | None:
    """El código con que la fila queda omitida, o None si se puede enviar. Sin canal o sin destino es
    el mismo código: no se busca otro canal."""
    if not revision.autorizado:
        return CodigoAviso.SIN_AUTORIZACION
    if not revision.alerta_abierta:
        return CodigoAviso.ALERTA_CERRADA
    if not revision.miembro_activo:
        return CodigoAviso.MIEMBRO_INACTIVO
    if not (revision.canal_activo and revision.con_destino):
        return CodigoAviso.SIN_DESTINO
    return None


class ResultadoEnvio(StrEnum):
    """Lo que responde un adaptador, ya traducido: nunca la respuesta del proveedor."""

    ENVIADO = "enviado"
    RECHAZADO = "rechazado"  # el proveedor no lo acepta y reintentar no cambia nada
    NO_DISPONIBLE = "no_disponible"  # pasajero: se reintenta con el backoff del outbox
    EXPIRADO = "expirado"  # push 404 o 410: la suscripción ya no existe y el token se borra


@dataclass(frozen=True)
class Desenlace:
    estado: EstadoNotificacion
    codigo: CodigoAviso | None
    reintentar: bool


def desenlace(resultados: Sequence[ResultadoEnvio]) -> Desenlace:
    """El estado de la fila después de enviar a cada destino del canal (el push puede ir a varios
    dispositivos). Con uno que llegó, la fila queda enviada y no se reintenta: reintentar duplicaría."""
    if not resultados:
        return Desenlace(EstadoNotificacion.OMITIDA, CodigoAviso.SIN_DESTINO, reintentar=False)
    if ResultadoEnvio.ENVIADO in resultados:
        return Desenlace(EstadoNotificacion.ENVIADA, None, reintentar=False)
    if ResultadoEnvio.NO_DISPONIBLE in resultados:
        return Desenlace(EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_NO_DISPONIBLE, reintentar=True)
    if ResultadoEnvio.RECHAZADO in resultados:
        return Desenlace(EstadoNotificacion.FALLIDA, CodigoAviso.PROVEEDOR_RECHAZO, reintentar=False)
    return Desenlace(EstadoNotificacion.FALLIDA, CodigoAviso.PUSH_EXPIRADO, reintentar=False)


def por_intentar(estado: EstadoNotificacion, codigo: CodigoAviso | None) -> bool:
    """Si un intento debe tocar la fila: pendiente, o fallida por un proveedor no disponible. Una fila
    enviada nunca se reenvía; omitida, rechazada o expirada ya terminó."""
    if estado is EstadoNotificacion.PENDIENTE:
        return True
    return estado is EstadoNotificacion.FALLIDA and codigo is CodigoAviso.PROVEEDOR_NO_DISPONIBLE
