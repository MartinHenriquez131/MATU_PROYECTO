"""La conciliación de los pagos (D-62-5, D-62-6; arquitectura 8.4, defensa 2, y 12.4, casos 6 y 7).

Corre cada 5 minutos desde el programador de tareas (MATU-74), **también con la capa 3 apagada** (D-62-17): un pago que
el banco ya aprobó se registra o se anula igual.

- Una venta autorizando (el commit no tuvo respuesta): otro commit. Transbank no cobra dos veces (prueba del 10-11) y
  la venta se cierra con las mismas reglas de la vuelta.
- Una venta iniciada hace más de VIDA_VENTA_WEBPAY (la vuelta nunca llegó): D-62-5 (a), el job hace el commit. Si
  Transbank no la reconoce o no está pagada, se cierra con formulario_vencido.
- Una anulación que no terminó: se reintenta sin devolver dos veces (devoluciones.reintentar).

Con eso, una vuelta perdida se cierra en menos de 15 minutos (5 de la conciliación más 10 de la vida de la venta). Lo
que sigue sin respuesta después de 15 minutos es una alerta a operación (cobro.alertar). Cada venta va en su propia
transacción: una que falla no detiene a las demás. El resultado son solo cantidades.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.modules.payments.application import cobro, devoluciones
from app.modules.payments.application.ports import AbrirGrupo, ListarPorConciliar, PasarelaWebpay
from app.modules.payments.domain.venta import EstadoVenta, MotivoCierre, ResultadoPago

log = logging.getLogger("matu.payments.conciliacion")

# Cuántas transacciones revisa una corrida (pagos_por_conciliar admite de 1 a 500)
LOTE = 200


@dataclass(frozen=True)
class ResultadoConciliacion:
    revisadas: int = 0
    cerradas: int = 0
    pendientes: int = 0
    anulaciones_hechas: int = 0
    fallidas: int = 0


def conciliar_una(
    transaccion_id: uuid.UUID,
    grupo_id: uuid.UUID,
    abrir: AbrirGrupo,
    pasarela: PasarelaWebpay,
    ahora: datetime,
    vida: timedelta,
) -> str:
    """Una transacción. Devuelve cerrada, pendiente, anulada o nada."""
    with abrir(grupo_id) as unidad:
        repo = unidad.repositorio
        venta = repo.venta(transaccion_id, bloquear=True)
        if venta is not None:
            vencida = venta.estado is EstadoVenta.INICIADA and ahora - venta.creado_en >= vida
            if venta.token is None or not (venta.estado is EstadoVenta.AUTORIZANDO or vencida):
                return "nada"
            motivo = MotivoCierre.FORMULARIO_VENCIDO if vencida else MotivoCierre.NO_APROBADA
            cierre = cobro.confirmar(unidad, pasarela, venta, ahora, vida, motivo)
            return "pendiente" if cierre.resultado is ResultadoPago.PENDIENTE else "cerrada"
        estado = devoluciones.reintentar(unidad, pasarela, transaccion_id, ahora)
        if estado is cobro.EstadoAnulacion.HECHA:
            return "anulada"
        return "pendiente" if estado is not None else "nada"


def conciliar(
    listar: ListarPorConciliar,
    abrir: AbrirGrupo,
    pasarela: PasarelaWebpay | None,
    ahora: datetime,
    vida: timedelta,
) -> ResultadoConciliacion:
    if pasarela is None:
        return ResultadoConciliacion()
    revisadas = cerradas = pendientes = anuladas = fallidas = 0
    for transaccion_id, grupo_id in listar(ahora - vida, LOTE):
        revisadas += 1
        try:
            resultado = conciliar_una(transaccion_id, grupo_id, abrir, pasarela, ahora, vida)
        except Exception as error:  # noqa: BLE001 - una venta que falla no detiene a las demás
            # Solo el tipo: el mensaje puede traer valores de la base
            log.warning("conciliacion fallo", extra={"tipo_error": type(error).__name__})
            fallidas += 1
            continue
        if resultado == "cerrada":
            cerradas += 1
        elif resultado == "pendiente":
            pendientes += 1
        elif resultado == "anulada":
            anuladas += 1
    return ResultadoConciliacion(
        revisadas=revisadas,
        cerradas=cerradas,
        pendientes=pendientes,
        anulaciones_hechas=anuladas,
        fallidas=fallidas,
    )
