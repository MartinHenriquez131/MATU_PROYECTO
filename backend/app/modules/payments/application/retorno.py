"""POST /v1/pagos/retorno: la vuelta de Webpay (decisiones 231 a 235; D-62-12 y D-62-17).

Pública e idempotente por token. No confía en nada salvo en un token, o un par buy_order y session_id, que MATU creó;
el resultado lo da Transbank.

| Trae | Qué hace |
|---|---|
| token_ws de una venta iniciada | autorizando y commit (cobro.confirmar) |
| token_ws de una venta que ya no está iniciada | nada, ``ya_registrado``; en autorizando, un commit cada 10 s |
| TBK_TOKEN | sin commit: status y, si no está aprobada, rechazada con usuario_salio (``abandonado``) |
| TBK_ORDEN_COMPRA y TBK_ID_SESION | por los dos juntos, status y formulario_vencido (``tiempo_agotado``) |
| algo que no es de MATU | VentaDesconocida (404), sin llamar a Transbank ni escribir |

Cada vuelta corre en su propia transacción con el grupo de la venta y app.rol = 'sistema'. No se apaga con la capa 3
(decisión 241). Lo que trae nunca va a los logs: el router fija solo ``caso``.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.modules.payments.application import cobro
from app.modules.payments.application.cobro import Cierre, EstadoAnulacion
from app.modules.payments.application.ports import AbrirGrupo, PasarelaWebpay, ResolverVenta, Unidad
from app.modules.payments.domain.venta import (
    VOLVER_A_PREGUNTAR_S,
    CasoRetorno,
    EstadoVenta,
    MotivoCierre,
    ResultadoPago,
    Venta,
    clasificar_retorno,
    puede_reintentar_commit,
    resultado_de,
)


class VentaDesconocida(LookupError):
    """Los valores no son de ninguna venta de MATU (404)."""


@dataclass(frozen=True)
class Vuelta:
    """Lo que trajo la dirección, con los nombres de Transbank."""

    token_ws: str | None = None
    tbk_token: str | None = None
    tbk_orden_compra: str | None = None
    tbk_id_sesion: str | None = None


@dataclass(frozen=True)
class ResultadoVuelta:
    caso: CasoRetorno
    resultado: ResultadoPago
    ya_registrado: bool
    anulacion: EstadoAnulacion | None
    venta_id: uuid.UUID
    grupo_id: uuid.UUID
    pedido_id: uuid.UUID
    persona_id: uuid.UUID

    @property
    def volver_a_preguntar_en(self) -> int | None:
        return VOLVER_A_PREGUNTAR_S if self.resultado is ResultadoPago.PENDIENTE else None


def _guardado(venta: Venta) -> Cierre:
    """El resultado de una venta que ya no está iniciada, sin llamar a Transbank."""
    resultado = resultado_de(venta)
    if resultado is None:  # una venta con error nunca llegó a Webpay
        resultado = ResultadoPago.NO_APROBADO
    anulacion = None
    if resultado is ResultadoPago.ANULADO:
        anulacion = EstadoAnulacion.EN_CURSO
    return Cierre(resultado, anulacion)


def procesar(
    vuelta: Vuelta,
    resolver: ResolverVenta,
    abrir: AbrirGrupo,
    pasarela: PasarelaWebpay | None,
    ahora: datetime,
    vida: timedelta,
) -> ResultadoVuelta:
    caso = clasificar_retorno(vuelta.token_ws, vuelta.tbk_token, vuelta.tbk_orden_compra, vuelta.tbk_id_sesion)
    if caso is CasoRetorno.DESCONOCIDO:
        raise VentaDesconocida()
    if caso is CasoRetorno.FORMULARIO_VENCIDO:
        encontrada = resolver(None, vuelta.tbk_orden_compra, vuelta.tbk_id_sesion)
    else:
        encontrada = resolver(vuelta.tbk_token if caso is CasoRetorno.USUARIO_SALIO else vuelta.token_ws, None, None)
    if encontrada is None:
        raise VentaDesconocida()
    venta_id, grupo_id = encontrada

    with abrir(grupo_id) as unidad:
        repo = unidad.repositorio
        venta = repo.venta(venta_id, bloquear=True)
        if venta is None:
            raise VentaDesconocida()
        cargo = repo.cargo(venta.cargo_id)
        assert cargo is not None
        pedido = repo.pedido(cargo.pedido_id)
        assert pedido is not None
        ya_registrado = venta.estado is not EstadoVenta.INICIADA
        cierre: Cierre | None
        if pasarela is None:
            # Sin pasarela configurada no se llama a nadie: la conciliación cerrará la venta cuando vuelva
            cierre = _guardado(venta) if ya_registrado else Cierre(ResultadoPago.PENDIENTE)
        elif venta.estado is EstadoVenta.INICIADA:
            if venta.retorno_recibido_en is None:
                # La marca del retorno (decisión 245): la primera vuelta que llegó
                venta = replace(venta, retorno_recibido_en=ahora)
                repo.guardar_venta(venta)
            if caso is CasoRetorno.COMMIT:
                cierre = cobro.confirmar(unidad, pasarela, venta, ahora, vida)
            else:
                motivo = (
                    MotivoCierre.USUARIO_SALIO if caso is CasoRetorno.USUARIO_SALIO else MotivoCierre.FORMULARIO_VENCIDO
                )
                cierre = cobro.consultar_y_cerrar(unidad, pasarela, venta, ahora, vida, motivo)
                if cierre is None:
                    # Webpay no responde, y la persona salió o se le acabó el tiempo: no se cobró nada
                    cierre = Cierre(
                        ResultadoPago.ABANDONADO
                        if caso is CasoRetorno.USUARIO_SALIO
                        else ResultadoPago.TIEMPO_AGOTADO
                    )
        elif venta.estado is EstadoVenta.AUTORIZANDO and puede_reintentar_commit(venta.commit_intentado_en, ahora):
            # Decisión 233: un commit sin respuesta se reintenta como mucho cada 10 segundos
            cierre = cobro.confirmar(unidad, pasarela, venta, ahora, vida)
        else:
            cierre = _guardado(venta)
        if ya_registrado and cierre.resultado is ResultadoPago.ANULADO and cierre.anulacion is EstadoAnulacion.EN_CURSO:
            cierre = Cierre(ResultadoPago.ANULADO, _estado_anulacion(unidad, venta))
        return ResultadoVuelta(
            caso=CasoRetorno.REPETIDO if ya_registrado else caso,
            resultado=cierre.resultado,
            ya_registrado=ya_registrado,
            anulacion=cierre.anulacion,
            venta_id=venta.id,
            grupo_id=grupo_id,
            pedido_id=pedido.id,
            persona_id=pedido.persona_id,
        )


def _estado_anulacion(unidad: Unidad, venta: Venta) -> EstadoAnulacion:
    hecha = any(a.venta_id == venta.id and a.hecha for a in unidad.repositorio.anulaciones(venta.cargo_id))
    return EstadoAnulacion.HECHA if hecha else EstadoAnulacion.EN_CURSO
