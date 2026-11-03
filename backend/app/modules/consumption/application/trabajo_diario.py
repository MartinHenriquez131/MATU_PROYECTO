"""El trabajo diario de la predicción de quiebre (MATU-37, RF-12, arquitectura 8.5, ADR-012).

Corre una vez por grupo, con app.rol = 'sistema' y app.grupo_id. Por cada perfil activo:

1. Si la persona no tiene autorización vigente para ``consumo`` (no revocada y, si es de un cuidador
   de hecho, con la revisión al día según el Reloj), no hace nada: ni crea alertas, ni avisa.
2. Descarta las alertas abiertas que ya no corresponden (otra fecha o fuera de la ventana) y
   registra ``alerta.descartar`` con actor sistema.
3. Si el insumo está en su ventana y no hay alerta para su fecha estimada actual, la materializa
   (pendiente), publica ``QuiebreProximo`` en el outbox y registra ``alerta.materializar``, todo en la
   misma transacción. Una corrida doble no crea otra (alerta_quiebre_uq).

No envía avisos (MATU-41) y nunca crea un pedido.
"""

import uuid
from dataclasses import dataclass

from app.modules.care_circle.domain.personas import EstadoAutorizacion, estado_autorizacion
from app.modules.consumption.application.ports import RepositorioQuiebres
from app.modules.consumption.domain.alerta import AlertaAbierta, InsumoEnSeguimiento, planificar
from app.modules.consumption.domain.perfil import hoy_en_chile
from app.modules.consumption.events import QuiebreProximo
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


@dataclass(frozen=True)
class ResultadoTrabajo:
    materializadas: int
    descartadas: int


def _auditar(auditoria: RegistroAuditoria, grupo_id: uuid.UUID, accion: AccionAuditoria, alerta_id: uuid.UUID) -> None:
    auditoria.registrar(
        EntradaAuditoria(
            grupo_id=grupo_id,
            actor_tipo=ActorTipo.SISTEMA,
            actor_ref=None,
            accion=accion,
            entidad=EntidadAuditoria.ALERTA_QUIEBRE,
            entidad_id=alerta_id,
        )
    )


def recalcular_quiebres(
    grupo_id: uuid.UUID, repositorio: RepositorioQuiebres, auditoria: RegistroAuditoria, reloj: Reloj
) -> ResultadoTrabajo:
    ahora = reloj.ahora()
    hoy = hoy_en_chile(ahora)
    abiertas: dict[uuid.UUID, list[AlertaAbierta]] = {}
    for alerta in repositorio.abiertas():
        abiertas.setdefault(alerta.perfil_id, []).append(AlertaAbierta(alerta.id, alerta.fecha_prevista))

    materializadas = descartadas = 0
    for insumo in repositorio.insumos():
        autorizado = estado_autorizacion(insumo.autorizacion, ahora) is EstadoAutorizacion.VIGENTE
        plan = planificar(
            InsumoEnSeguimiento(
                perfil_id=insumo.perfil_id,
                persona_cuidada_id=insumo.persona_cuidada_id,
                fecha_quiebre_estimada=insumo.fecha_quiebre_estimada,
                dias_aviso=insumo.dias_aviso,
                autorizado=autorizado,
                abiertas=tuple(abiertas.get(insumo.perfil_id, ())),
                hay_alerta_de_la_fecha=insumo.hay_alerta_de_la_fecha,
            ),
            hoy,
        )
        for alerta_id in plan.descartar:
            repositorio.descartar(alerta_id, ahora)
            _auditar(auditoria, grupo_id, AccionAuditoria.ALERTA_DESCARTAR, alerta_id)
            descartadas += 1
        if plan.materializar:
            alerta_id = uuid.uuid4()
            if repositorio.materializar(alerta_id, insumo.perfil_id, insumo.fecha_quiebre_estimada, ahora):
                repositorio.publicar(
                    QuiebreProximo(
                        alerta_id=alerta_id, perfil_id=insumo.perfil_id, persona_cuidada_id=insumo.persona_cuidada_id
                    ),
                    ahora,
                )
                _auditar(auditoria, grupo_id, AccionAuditoria.ALERTA_MATERIALIZAR, alerta_id)
                materializadas += 1
    return ResultadoTrabajo(materializadas=materializadas, descartadas=descartadas)
