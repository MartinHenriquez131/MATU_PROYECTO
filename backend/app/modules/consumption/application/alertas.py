"""Casos de uso de la predicción de quiebre y de las alertas (MATU-37, RF-12).

La autorización para ``consumo``, el rol y la persona ya los verificó la API (api/dependencias.py).

- «Se acaban pronto» sale de perfil_consumo, no de alerta_quiebre (decisión 53): se ve aunque el
  trabajo diario no haya corrido. Cada insumo trae ``avisando`` y el id de la alerta de su fecha
  estimada actual (decisión 74).
- Descartar una alerta y «Ya lo resolví» sin cantidad la pasan a ``descartada`` y registran
  ``alerta.descartar``. «Ya lo resolví» con cantidad suma lo comprado al stock estimado de hoy, anota
  la reposición y deja la alerta ``resuelta`` (decisión 79). La auditoría lleva solo identificadores.
- Ninguna alerta genera un pedido.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from app.modules.consumption.application.perfiles import (
    PerfilInactivo,
    PerfilNoEncontrado,
    PeticionConsumo,
    VersionDesactualizada,
)
from app.modules.consumption.application.ports import (
    AlertaLeida,
    InsumoEnVentana,
    PaginaAlertas,
    PerfilLeido,
    RepositorioAlertas,
    RepositorioPerfiles,
)
from app.modules.consumption.domain.alerta import EstadoAlerta, avisa_hoy, exigir_abierta, reponer
from app.modules.consumption.domain.perfil import coincide, exigir_if_match, hoy_en_chile
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


class AlertaNoEncontrada(Exception):
    """La alerta no existe o no es de un perfil de la persona del path. 404."""


@dataclass(frozen=True)
class InsumoAvisado:
    leido: PerfilLeido
    avisando: bool
    alerta_id: uuid.UUID | None


def _avisado(insumo: InsumoEnVentana, hoy: date) -> InsumoAvisado:
    estado = None if insumo.alerta is None else insumo.alerta.estado
    return InsumoAvisado(
        leido=insumo.leido,
        avisando=avisa_hoy(insumo.leido.perfil, estado, hoy),
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


def _auditar(
    auditoria: RegistroAuditoria,
    peticion: PeticionConsumo,
    accion: AccionAuditoria,
    entidad: EntidadAuditoria,
    entidad_id: uuid.UUID,
) -> None:
    auditoria.registrar(
        EntradaAuditoria(
            grupo_id=peticion.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=peticion.usuario_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            request_id=peticion.request_id,
        )
    )


def resolver(
    peticion: PeticionConsumo,
    perfil_id: uuid.UUID,
    cantidad: int | None,
    if_match: str | None,
    reloj: Reloj,
    perfiles: RepositorioPerfiles,
    alertas: RepositorioAlertas,
    auditoria: RegistroAuditoria,
) -> InsumoAvisado | VersionDesactualizada:
    """«Ya lo resolví» por insumo (decisiones 76 y 79), aunque el trabajo diario no haya creado la alerta.

    Condicional, como el PATCH (decisión 80): exige If-Match con el ETag del perfil. Orden: 404 (perfil),
    428 (FaltaVersion), 409 perfil-inactivo, 412 (VersionDesactualizada, sin sumar ni cerrar nada), 409
    alerta-cerrada (la de la fecha estimada actual) y 422 cobertura_maxima. Así un reintento o una segunda
    pestaña con el mismo ETag nunca suman dos veces: la primera suma sube la versión.

    La alerta de la fecha actual (o una nueva, ya cerrada, si no existía) queda:

    - sin cantidad: descartada. El perfil no cambia. Registra alerta.descartar.
    - con cantidad: resuelta. El stock pasa a lo que MATU estima que queda hoy (nunca negativo) más la
      cantidad, medido hoy, con la fecha recalculada y la versión + 1; se anota una reposicion declarada a
      nombre del usuario. Registra reposicion.declarar y alerta.resolver, sin la cantidad.

    Todo en la transacción de la petición. Nunca crea un pedido.
    """
    leido = perfiles.obtener(peticion.persona_id, perfil_id, para_escribir=True)
    if leido is None:
        raise PerfilNoEncontrado()
    perfil = leido.perfil
    valor = exigir_if_match(if_match)
    if not perfil.activo:
        raise PerfilInactivo()
    if not coincide(valor, perfil.version):
        return VersionDesactualizada(actual=leido)
    ahora = reloj.ahora()
    hoy = hoy_en_chile(ahora)
    alerta = alertas.de_la_fecha(perfil.id, perfil.fecha_quiebre_estimada)
    if alerta is not None:
        exigir_abierta(alerta.estado)
    repuesto = None if cantidad is None else reponer(perfil, cantidad, hoy, peticion.usuario_id)

    estado = EstadoAlerta.DESCARTADA if repuesto is None else EstadoAlerta.RESUELTA
    if alerta is None:
        cerrada = alertas.insertar_cerrada(uuid.uuid4(), perfil.id, perfil.fecha_quiebre_estimada, estado, ahora)
    else:
        cerrada = alertas.cerrar(alerta.id, estado, ahora)

    if repuesto is None or cantidad is None:
        _auditar(auditoria, peticion, AccionAuditoria.ALERTA_DESCARTAR, EntidadAuditoria.ALERTA_QUIEBRE, cerrada.id)
        return _avisado(InsumoEnVentana(leido=leido, alerta=cerrada), hoy)

    perfiles.actualizar(repuesto)
    reposicion_id = uuid.uuid4()
    alertas.declarar_reposicion(reposicion_id, perfil.id, cantidad, hoy, peticion.usuario_id)
    _auditar(auditoria, peticion, AccionAuditoria.REPOSICION_DECLARAR, EntidadAuditoria.REPOSICION, reposicion_id)
    _auditar(auditoria, peticion, AccionAuditoria.ALERTA_RESOLVER, EntidadAuditoria.ALERTA_QUIEBRE, cerrada.id)
    nuevo = perfiles.obtener(peticion.persona_id, perfil.id)
    if nuevo is None:  # pragma: no cover - recién escrito en la misma transacción
        raise PerfilNoEncontrado()
    # La alerta cerrada es de la fecha anterior: para la fecha nueva todavía no hay ninguna
    return _avisado(InsumoEnVentana(leido=nuevo, alerta=None), hoy)
