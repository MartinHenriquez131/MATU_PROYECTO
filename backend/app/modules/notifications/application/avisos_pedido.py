"""Los consumidores de los eventos del pedido: avisan a quien pagó (MATU-76; D-76-1 a D-76-5; C1 a C8 y C13).

Uno por evento, cada uno con su nombre en ``evento_consumido``: ``PagoAnulado``, ``ProductoFaltante``,
``PedidoCanceladoConDevolucion``, ``PedidoEntregado`` y ``PedidoNoEntregado``. ``PedidoPagado`` no avisa. Los llama el
publicador del outbox, nunca un flujo de negocio: que falle un aviso no revierte el pedido ni la devolución.

1. Antes de las 09:00 de Chile pospone el evento hasta las 09:00, sin sumar un intento (C8).
2. Si el evento ya se consumió, termina.
3. El destinatario es solo quien pagó (D-76-2): las cuentas de la venta aprobada del pedido. No el admin ni quien
   cuida, salvo que hayan pagado. Por cada una se crea una fila pendiente por canal activo, con ``ON CONFLICT DO
   NOTHING`` sobre ``notificacion_uq``: un reintento no duplica.
   - La preferencia es ``tipo_evento = 'pedido'``, activa por omisión para todos (C3).
   - El correo de ``PagoAnulado``, ``ProductoFaltante`` y ``PedidoCanceladoConDevolucion`` es sobre su dinero y va
     aunque la persona haya apagado el correo (D-76-3). El push y los avisos de «Entregado» y «No entregado» siguen la
     preferencia.
4. Por cada fila por intentar, en su propia transacción y con la fila bloqueada, revisa de nuevo el miembro (quien
   salió del grupo queda ``miembro_inactivo``, D-76-4), el canal y el destino. **No** revisa la autorización de
   pedidos: un aviso del pedido nunca queda ``sin_autorizacion`` (C2). El destino solo se lee si el miembro sigue
   activo y el canal también.
5. El correo es ``pedido_novedad`` (C6 y C7), igual para todos los eventos, y se arma al enviar. El push va sin
   contenido (C5): el texto genérico lo pone el service worker.
6. Si un proveedor no estuvo disponible, pide reintentar; si no, marca el evento consumido.

El envío sigue simulado (C13). El log lleva solo ids, canal, estado y código.
"""

import logging
import uuid
from collections.abc import Callable

from app.modules.notifications.application.avisos import _registrar, _sin_excepcion
from app.modules.notifications.application.ports import (
    EnviadorCorreo,
    EnviadorPush,
    EnvioCorreo,
    EnvioPush,
    NotificacionLeida,
    RepositorioAvisos,
    UnidadAvisos,
)
from app.modules.notifications.domain.aviso import (
    CANALES,
    EVENTOS_DE_DINERO,
    EVENTOS_DEL_PEDIDO,
    PLANTILLA_PEDIDO,
    TIPO_EVENTO_PEDIDO,
    Canal,
    CodigoAviso,
    Desenlace,
    EstadoNotificacion,
    ResultadoEnvio,
    canal_del_pedido_activo,
    canales_del_pedido,
    desenlace,
    motivo_omision_pedido,
    por_intentar,
)
from app.modules.notifications.domain.horario import disponible_desde
from app.modules.notifications.domain.mensaje import correo_pedido
from app.shared.outbox import EventoTomado, Hecho, Posponer, Reintentar, ResultadoConsumo
from app.shared.puertos import Reloj

log = logging.getLogger("matu.notifications.avisos_pedido")


def nombre_consumidor(tipo: str) -> str:
    """El nombre propio de cada consumidor en ``evento_consumido`` (C1)."""
    return f"notifications.pedido.{tipo}"


def _pedido_id(evento: EventoTomado) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(evento.payload["pedido_id"]))
    except (KeyError, ValueError):
        return None


class ConsumidorAvisoPedido:
    """Consumidor del outbox para un evento del pedido. Idempotente: el evento puede llegar más de una vez."""

    def __init__(
        self,
        *,
        tipo: str,
        unidad: UnidadAvisos,
        correo: EnviadorCorreo,
        push: EnviadorPush,
        reloj: Reloj,
        origen_web: str,
        push_permitido: Callable[[uuid.UUID], bool],
    ) -> None:
        if tipo not in EVENTOS_DEL_PEDIDO:
            raise ValueError("no es un evento del pedido que avise")
        self.tipo = tipo
        self.nombre = nombre_consumidor(tipo)
        self._dinero = tipo in EVENTOS_DE_DINERO
        self._unidad = unidad
        self._correo = correo
        self._push = push
        self._reloj = reloj
        self._origen_web = origen_web
        # MATU-107 (C-107-5): como en el aviso del insumo, el push solo a las cuentas que pueden recibirlo
        self._push_permitido = push_permitido

    def __repr__(self) -> str:
        return f"ConsumidorAvisoPedido({self.tipo})"

    def consumir(self, evento: EventoTomado) -> ResultadoConsumo:
        desde = disponible_desde(self._reloj.ahora())
        if desde is not None:
            return Posponer(desde)
        pedido_id = _pedido_id(evento)
        if evento.grupo_id is None or pedido_id is None:
            log.warning("evento sin identificadores", extra={"evento_id": evento.id})
            return Hecho()
        grupo_id = evento.grupo_id

        with self._unidad.abrir(grupo_id) as repo:
            if repo.ya_consumido(evento.id, self.nombre):
                return Hecho()
            filas: list[tuple[uuid.UUID, Canal]] = []
            for usuario_id in repo.quienes_pagaron(pedido_id):
                miembro = repo.miembro(usuario_id, TIPO_EVENTO_PEDIDO)
                preferencias = {} if miembro is None else miembro.preferencias
                filas.extend(
                    (usuario_id, canal) for canal in canales_del_pedido(dinero=self._dinero, preferencias=preferencias)
                )
            repo.crear(evento.id, filas, PLANTILLA_PEDIDO, self._reloj.ahora())
            pendientes = [n for n in repo.notificaciones(evento.id) if por_intentar(n.estado, n.codigo)]

        reintentar = False
        for fila in sorted(pendientes, key=lambda n: CANALES.index(n.canal)):
            with self._unidad.abrir(grupo_id) as repo:
                actual = repo.bloquear(fila.id)
                if actual is None or not por_intentar(actual.estado, actual.codigo):
                    continue
                d = self._intentar(repo, actual)
                _registrar(actual, evento.id, d)
                reintentar = reintentar or d.reintentar

        if reintentar:
            return Reintentar()
        with self._unidad.abrir(grupo_id) as repo:
            repo.marcar_consumido(evento.id, self.nombre, self._reloj.ahora())
        return Hecho()

    def _intentar(self, repo: RepositorioAvisos, fila: NotificacionLeida) -> Desenlace:
        ahora = self._reloj.ahora()
        miembro = repo.miembro(fila.usuario_id, TIPO_EVENTO_PEDIDO)
        miembro_activo = miembro is not None and miembro.activo
        canal = miembro is not None and canal_del_pedido_activo(
            fila.canal, dinero=self._dinero, preferencia=miembro.preferencias.get(fila.canal)
        )
        # El destino solo se lee si quien pagó sigue en el grupo y el canal sigue activo
        leer = miembro_activo and canal
        correo = repo.correo(fila.usuario_id) if leer and fila.canal is Canal.CORREO else None
        push = leer and fila.canal is Canal.PUSH and self._push_permitido(fila.usuario_id)
        destinos = repo.destinos_push(fila.usuario_id) if push else []
        codigo = motivo_omision_pedido(
            miembro_activo=miembro_activo,
            canal_activo=canal,
            con_destino=bool(correo) if fila.canal is Canal.CORREO else bool(destinos),
        )
        if codigo is not None:
            omitida = Desenlace(EstadoNotificacion.OMITIDA, codigo, reintentar=False)
            repo.actualizar(fila.id, omitida.estado, omitida.codigo, None)
            return omitida

        resultados: list[ResultadoEnvio] = []
        if fila.canal is Canal.CORREO:
            if not correo:
                # No debería pasar (la revisión ya lo omite), pero nunca se envía a un correo que falta, ni con -O
                sin_correo = Desenlace(EstadoNotificacion.OMITIDA, CodigoAviso.SIN_DESTINO, reintentar=False)
                repo.actualizar(fila.id, sin_correo.estado, sin_correo.codigo, None)
                return sin_correo
            mensaje = correo_pedido(self._origen_web, dinero=self._dinero)
            envio = EnvioCorreo(fila.id, fila.usuario_id, PLANTILLA_PEDIDO, correo, mensaje)
            resultados.append(_sin_excepcion(self._correo.enviar, envio, fila))
        else:
            # Sin contenido (decisión 50 y C5): el texto genérico lo pone el service worker
            for destino in destinos:
                envio_push = EnvioPush(fila.id, fila.usuario_id, PLANTILLA_PEDIDO, destino.push_token)
                resultado = _sin_excepcion(self._push.enviar, envio_push, fila)
                if resultado is ResultadoEnvio.EXPIRADO:
                    repo.expirar_push(destino.dispositivo_id)
                resultados.append(resultado)

        d = desenlace(resultados)
        repo.actualizar(fila.id, d.estado, d.codigo, ahora if d.estado is EstadoNotificacion.ENVIADA else None)
        return d
