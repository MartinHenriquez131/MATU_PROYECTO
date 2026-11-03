"""Casos de uso de la predicción de quiebre y de las alertas (MATU-37, RF-12).

La autorización para ``consumo``, el rol y la persona ya los verificó la API (api/dependencias.py).

- «Se acaban pronto» sale de perfil_consumo, no de alerta_quiebre (decisión 53): se ve aunque el
  trabajo diario no haya corrido. Cada insumo trae ``avisando`` y el id de la alerta de su fecha
  estimada actual (decisión 74).
- Descartar una alerta y «Ya lo resolví» sin cantidad la pasan a ``descartada`` y registran
  ``alerta.descartar`` con solo identificadores. Con cantidad (declarar la compra) no se implementa
  todavía: espera la decisión de Jorge entre MATU-37 y MATU-51.
- Ninguna alerta genera un pedido.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from app.modules.consumption.application.perfiles import PerfilInactivo, PerfilNoEncontrado, PeticionConsumo
from app.modules.consumption.application.ports import (
    AlertaLeida,
    InsumoEnVentana,
    PaginaAlertas,
    PerfilLeido,
    RepositorioAlertas,
    RepositorioPerfiles,
)
from app.modules.consumption.domain.alerta import EstadoAlerta, avisando, en_ventana, exigir_abierta
from app.modules.consumption.domain.perfil import dias_restantes, hoy_en_chile
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


class AlertaNoEncontrada(Exception):
    """La alerta no existe o no es de un perfil de la persona del path. 404."""


class CantidadAunNoDisponible(Exception):
    """«Ya lo resolví» con cantidad: pendiente de decisión (MATU-37 o MATU-51). 422 en cantidad."""


@dataclass(frozen=True)
class InsumoAvisado:
    leido: PerfilLeido
    avisando: bool
    alerta_id: uuid.UUID | None


def _avisado(insumo: InsumoEnVentana, hoy: date) -> InsumoAvisado:
    p = insumo.leido.perfil
    ventana = p.activo and en_ventana(dias_restantes(p.fecha_quiebre_estimada, hoy), p.dias_aviso)
    estado = None if insumo.alerta is None else insumo.alerta.estado
    return InsumoAvisado(
        leido=insumo.leido,
        avisando=avisando(en_su_ventana=ventana, estado_de_la_fecha=estado),
        alerta_id=None if insumo.alerta is None else insumo.alerta.id,
    )


def por_acabarse(peticion: PeticionConsumo, reloj: Reloj, repositorio: RepositorioAlertas) -> list[InsumoAvisado]:
    hoy = hoy_en_chile(reloj.ahora())
    return [_avisado(i, hoy) for i in repositorio.en_ventana(peticion.persona_id, hoy)]


def listar(
    peticion: PeticionConsumo,
    estados: frozenset[EstadoAlerta],
    despues_de: tuple[date, uuid.UUID] | None,
    limite: int,
    repositorio: RepositorioAlertas,
) -> PaginaAlertas:
    return repositorio.listar(peticion.persona_id, estados, despues_de, limite)


def _auditar_descarte(auditoria: RegistroAuditoria, peticion: PeticionConsumo, alerta_id: uuid.UUID) -> None:
    auditoria.registrar(
        EntradaAuditoria(
            grupo_id=peticion.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=peticion.usuario_id,
            accion=AccionAuditoria.ALERTA_DESCARTAR,
            entidad=EntidadAuditoria.ALERTA_QUIEBRE,
            entidad_id=alerta_id,
            request_id=peticion.request_id,
        )
    )


def descartar(
    peticion: PeticionConsumo,
    alerta_id: uuid.UUID,
    reloj: Reloj,
    repositorio: RepositorioAlertas,
    auditoria: RegistroAuditoria,
) -> AlertaLeida:
    """«No avisar esta vez». 404 si no es de la persona; AlertaCerrada (409) si ya está cerrada."""
    alerta = repositorio.obtener(peticion.persona_id, alerta_id)
    if alerta is None:
        raise AlertaNoEncontrada()
    exigir_abierta(alerta.estado)
    cerrada = repositorio.cerrar(alerta.id, EstadoAlerta.DESCARTADA, reloj.ahora())
    _auditar_descarte(auditoria, peticion, alerta.id)
    return cerrada


def resolver(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    cantidad: int | None,
    reloj: Reloj,
    perfiles: RepositorioPerfiles,
    alertas: RepositorioAlertas,
    auditoria: RegistroAuditoria,
) -> InsumoAvisado:
    """«Ya lo resolví» por insumo (decisión 76), aunque el trabajo diario no haya creado la alerta.

    Orden: 404 (perfil), 422 (cantidad, aún no disponible), 409 perfil-inactivo, 409 alerta-cerrada.
    Si hay una alerta abierta para la fecha estimada actual, pasa a descartada; si no hay ninguna, se
    crea ya descartada en la misma transacción, para que el trabajo diario no avise por esa fecha.
    """
    leido = perfiles.obtener(peticion.persona_id, perfil_id, para_escribir=True)
    if leido is None:
        raise PerfilNoEncontrado()
    if cantidad is not None:
        raise CantidadAunNoDisponible()
    perfil = leido.perfil
    if not perfil.activo:
        raise PerfilInactivo()
    ahora = reloj.ahora()
    alerta = alertas.de_la_fecha(perfil.id, perfil.fecha_quiebre_estimada)
    if alerta is None:
        cerrada = alertas.insertar_cerrada(
            uuid.uuid4(), perfil.id, perfil.fecha_quiebre_estimada, EstadoAlerta.DESCARTADA, ahora
        )
    else:
        exigir_abierta(alerta.estado)
        cerrada = alertas.cerrar(alerta.id, EstadoAlerta.DESCARTADA, ahora)
    _auditar_descarte(auditoria, peticion, cerrada.id)
    return _avisado(InsumoEnVentana(leido=leido, alerta=cerrada), hoy_en_chile(ahora))
