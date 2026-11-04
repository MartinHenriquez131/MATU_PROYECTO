"""El consumidor de ``QuiebreProximo``: avisa por correo y push (MATU-41, RF-39, decisiones 106 a 109 y 113).

Lo llama el publicador del outbox (app/shared/outbox.py). Nunca lo llama un flujo de negocio: que falle un
aviso no revierte la alerta (arquitectura 6.4, regla 4).

1. Antes de las 09:00 de Chile pospone el evento hasta las 09:00, sin sumar un intento.
2. Si el evento ya se consumió (``evento_consumido``), termina.
3. Crea, para cada destinatario activo, una fila ``notificacion`` pendiente por canal (correo y push), con
   ``ON CONFLICT DO NOTHING`` sobre ``notificacion_uq``: un reintento no duplica.
4. Por cada fila por intentar, en su propia transacción y con la fila bloqueada, revisa de nuevo la
   autorización de ``consumo`` con el Reloj, la alerta, el miembro y el canal con su destino. Si algo falla,
   la fila queda ``omitida`` con su código y no se envía nada. Si no, arma el mensaje (nunca se guarda) y
   envía. Una fila ``enviada`` nunca se reenvía.
5. Con al menos un envío ``enviada``, la alerta pasa a ``notificada``.
6. Si un proveedor no estuvo disponible, pide reintentar; si no, marca el evento consumido.

El log lleva solo el id de la notificación, el del evento, el canal, el estado y el código.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.modules.care_circle.domain.personas import EstadoAutorizacion, estado_autorizacion
from app.modules.consumption.domain.alerta import avisa_por_defecto
from app.modules.notifications.application.ports import (
    EnviadorCorreo,
    EnviadorPush,
    EnvioCorreo,
    EnvioPush,
    MiembroAviso,
    NotificacionLeida,
    RepositorioAvisos,
    UnidadAvisos,
)
from app.modules.notifications.domain.aviso import (
    CANALES,
    PLANTILLA_QUIEBRE,
    Canal,
    Desenlace,
    EstadoNotificacion,
    ResultadoEnvio,
    Revision,
    canal_activo,
    desenlace,
    es_destinatario,
    motivo_omision,
    por_intentar,
)
from app.modules.notifications.domain.horario import disponible_desde
from app.modules.notifications.domain.mensaje import correo_quiebre
from app.shared.outbox import EventoTomado, Hecho, Posponer, Reintentar, ResultadoConsumo
from app.shared.puertos import Reloj

log = logging.getLogger("matu.notifications.avisos")

CONSUMIDOR_QUIEBRE = "notifications.quiebre_proximo"


@dataclass(frozen=True)
class _Ids:
    alerta_id: uuid.UUID
    perfil_id: uuid.UUID
    persona_id: uuid.UUID


def _ids(evento: EventoTomado) -> _Ids | None:
    try:
        return _Ids(
            alerta_id=uuid.UUID(str(evento.payload["alerta_id"])),
            perfil_id=uuid.UUID(str(evento.payload["perfil_id"])),
            persona_id=uuid.UUID(str(evento.payload["persona_cuidada_id"])),
        )
    except (KeyError, ValueError):
        return None


def _registrar(fila: NotificacionLeida, evento_id: int, d: Desenlace) -> None:
    log.info(
        "aviso",
        extra={
            "notificacion_id": str(fila.id),
            "evento_id": evento_id,
            "canal": fila.canal.value,
            "estado": d.estado.value,
            "codigo": d.codigo.value if d.codigo else None,
        },
    )


class ConsumidorQuiebreProximo:
    """Consumidor del outbox para ``QuiebreProximo``. Idempotente: el evento puede llegar más de una vez."""

    nombre = CONSUMIDOR_QUIEBRE

    def __init__(
        self,
        *,
        unidad: UnidadAvisos,
        correo: EnviadorCorreo,
        push: EnviadorPush,
        reloj: Reloj,
        origen_web: str,
    ) -> None:
        self._unidad = unidad
        self._correo = correo
        self._push = push
        self._reloj = reloj
        self._origen_web = origen_web

    def __repr__(self) -> str:
        return "ConsumidorQuiebreProximo()"

    def consumir(self, evento: EventoTomado) -> ResultadoConsumo:
        desde = disponible_desde(self._reloj.ahora())
        if desde is not None:
            return Posponer(desde)
        ids = _ids(evento)
        if evento.grupo_id is None or ids is None:
            # Un evento sin grupo o sin sus identificadores no tiene a quién avisar: reintentarlo no cambia nada
            log.warning("evento sin identificadores", extra={"evento_id": evento.id})
            return Hecho()
        grupo_id = evento.grupo_id

        with self._unidad.abrir(grupo_id) as repo:
            if repo.ya_consumido(evento.id, self.nombre):
                return Hecho()
            filas = [
                (m.usuario_id, canal)
                for m in repo.miembros()
                if m.activo and es_destinatario(por_defecto=avisa_por_defecto(m.rol), preferencias=m.preferencias)
                for canal in CANALES
            ]
            repo.crear(evento.id, filas, PLANTILLA_QUIEBRE, self._reloj.ahora())
            pendientes = [n for n in repo.notificaciones(evento.id) if por_intentar(n.estado, n.codigo)]

        reintentar = False
        # El correo primero: es el canal garantizado, y no depende de cómo le vaya al push
        for fila in sorted(pendientes, key=lambda n: CANALES.index(n.canal)):
            with self._unidad.abrir(grupo_id) as repo:
                actual = repo.bloquear(fila.id)
                if actual is None or not por_intentar(actual.estado, actual.codigo):
                    continue
                d = self._intentar(repo, actual, ids)
                _registrar(actual, evento.id, d)
                reintentar = reintentar or d.reintentar

        if reintentar:
            return Reintentar()
        with self._unidad.abrir(grupo_id) as repo:
            repo.marcar_consumido(evento.id, self.nombre, self._reloj.ahora())
        return Hecho()

    def _intentar(self, repo: RepositorioAvisos, fila: NotificacionLeida, ids: _Ids) -> Desenlace:
        ahora = self._reloj.ahora()
        contexto = repo.contexto(ids.alerta_id, ids.perfil_id, ids.persona_id)
        miembro = repo.miembro(fila.usuario_id)
        correo = repo.correo(fila.usuario_id) if fila.canal is Canal.CORREO else None
        destinos = repo.destinos_push(fila.usuario_id) if fila.canal is Canal.PUSH else []
        revision = Revision(
            autorizado=estado_autorizacion(contexto.autorizacion, ahora) is EstadoAutorizacion.VIGENTE,
            alerta_abierta=contexto.alerta_abierta,
            miembro_activo=miembro is not None and miembro.activo,
            canal_activo=miembro is not None and _canal_activo(miembro, fila.canal),
            con_destino=bool(correo) if fila.canal is Canal.CORREO else bool(destinos),
        )
        codigo = motivo_omision(revision)
        if codigo is not None:
            omitida = Desenlace(EstadoNotificacion.OMITIDA, codigo, reintentar=False)
            repo.actualizar(fila.id, omitida.estado, omitida.codigo, None)
            return omitida

        resultados: list[ResultadoEnvio] = []
        if fila.canal is Canal.CORREO:
            assert correo is not None
            envio = EnvioCorreo(fila.id, fila.usuario_id, PLANTILLA_QUIEBRE, correo, correo_quiebre(self._origen_web))
            resultados.append(_sin_excepcion(self._correo.enviar, envio, fila))
        else:
            # Sin contenido (decisión 50): el texto fijo lo pone el service worker
            for destino in destinos:
                envio_push = EnvioPush(fila.id, fila.usuario_id, PLANTILLA_QUIEBRE, destino.push_token)
                resultado = _sin_excepcion(self._push.enviar, envio_push, fila)
                if resultado is ResultadoEnvio.EXPIRADO:
                    repo.expirar_push(destino.dispositivo_id)
                resultados.append(resultado)

        d = desenlace(resultados)
        repo.actualizar(fila.id, d.estado, d.codigo, ahora if d.estado is EstadoNotificacion.ENVIADA else None)
        if d.estado is EstadoNotificacion.ENVIADA:
            repo.marcar_alerta_notificada(ids.alerta_id, ahora)
        return d


def _sin_excepcion[E](enviar: Callable[[E], ResultadoEnvio], envio: E, fila: NotificacionLeida) -> ResultadoEnvio:
    """Un adaptador que lanza cuenta como proveedor no disponible: se reintenta y no detiene los demás
    canales. Solo se registra el tipo de la excepción: su mensaje puede traer el destino."""
    try:
        return enviar(envio)
    except Exception as error:  # noqa: BLE001
        log.warning(
            "envio fallo",
            extra={"notificacion_id": str(fila.id), "canal": fila.canal.value, "tipo_error": type(error).__name__},
        )
        return ResultadoEnvio.NO_DISPONIBLE


def _canal_activo(miembro: MiembroAviso, canal: Canal) -> bool:
    return canal_activo(por_defecto=avisa_por_defecto(miembro.rol), preferencia=miembro.preferencias.get(canal))
