"""Casos de uso de la ficha de relevo: leerla y guardar un campo (MATU-12, RF-02).

Llegan aquí solo peticiones que ya pasaron, en este orden, por el token (401), la membresía, el rol,
la persona y el campo (404) y el consentimiento vigente para plan_cuidado (403): lo hacen las
dependencias de la API antes de que se lea el cuerpo. Por eso, sin consentimiento, ningún caso de
uso corre y no se crea ni el plan ni la clave de datos (analista normativo, condición 1).

- El texto entra y sale en claro solo dentro de la llamada: se cifra con CifradorSecciones antes de
  llegar al repositorio, y se descifra al leer. No se registra ni se guarda en otra parte.
- El plan nace en la primera escritura con texto, con modo 'ficha_relevo'. Leer no lo crea.
- Toda escritura es condicional (MATU-13, RF-04, ADR-015). La API ya decidió el 428 y el 422 de las
  cabeceras con domain.ficha.precondicion_de; aquí llega SiCoincide (If-Match) o SiNoExiste
  (If-None-Match: *). La comparación es atómica en la base (UPDATE … WHERE version / INSERT … ON
  CONFLICT DO NOTHING): si no se cumple, nada se escribe y se devuelve CampoEnConflicto con el
  contenido actual descifrado, que se audita como plan.leer. No hay fusión automática.
- If-None-Match: * con texto vacío no crea nada (VacioSinCrear, 422), sin leer la base: ni el plan,
  ni la clave de datos, ni una versión (contrato, decisión 6).
- If-Match sobre un campo (o un plan) que nunca se escribió: CampoEnConflicto con el campo nunca
  escrito (etag null), sin crear el plan ni la clave.
- La auditoría (MATU-14) se llama por el puerto AuditoriaFicha, dentro de la misma transacción.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.care_plan.application.ports import (
    AuditoriaFicha,
    CifradorSecciones,
    EventoFicha,
    RepositorioFicha,
)
from app.modules.care_plan.domain.ficha import (
    CAMPO_NUNCA_ESCRITO,
    CAMPOS_FICHA,
    CampoFicha,
    EstadoCampo,
    Precondicion,
    SiCoincide,
    SiNoExiste,
    completitud,
    normalizar_texto,
    texto_visible,
)
from app.shared.puertos import Reloj


class VacioSinCrear(Exception):
    """If-None-Match: * con texto vacío: no hay nada que crear (contrato, decisión 6). Responde 422."""


class PlanNoDisponible(Exception):
    """El plan no se pudo crear ni leer en esta transacción. No debería ocurrir."""


@dataclass(frozen=True)
class PeticionFicha:
    """Quién pide, en qué grupo y sobre qué persona. Ya verificado por la API."""

    grupo_id: uuid.UUID
    usuario_id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    request_id: str | None = None


@dataclass(frozen=True)
class Ficha:
    persona_cuidada_id: uuid.UUID
    completitud: int
    # La última escritura de cualquier campo, o None si nadie ha escrito
    actualizado_en: datetime | None
    campos: dict[CampoFicha, EstadoCampo]


@dataclass(frozen=True)
class CampoGuardado:
    campo: CampoFicha
    estado: EstadoCampo
    completitud: int
    # True si el campo se escribió por primera vez (201), False si se actualizó (200)
    creado: bool


@dataclass(frozen=True)
class CampoEnConflicto:
    """La precondición no se cumplió (412): nada se escribió. ``actual`` es el campo vigente, descifrado.

    Para la pantalla que muestra el conflicto (docs/lenguaje.md, 6.2). Su lectura ya quedó auditada.
    """

    campo: CampoFicha
    actual: EstadoCampo


def _evento(
    peticion: PeticionFicha, plan_id: uuid.UUID | None, campo: CampoFicha | None, ahora: datetime
) -> EventoFicha:
    return EventoFicha(
        grupo_id=peticion.grupo_id,
        usuario_id=peticion.usuario_id,
        persona_cuidada_id=peticion.persona_cuidada_id,
        plan_id=plan_id,
        campo=None if campo is None else campo.value,
        request_id=peticion.request_id,
        ocurrido_en=ahora,
    )


def leer_ficha(
    peticion: PeticionFicha,
    repositorio: RepositorioFicha,
    cifrador: CifradorSecciones,
    auditoria: AuditoriaFicha,
    reloj: Reloj,
) -> Ficha:
    """Los tres campos de la ficha, descifrados, con su versión y su autor.

    Si nadie ha escrito todavía, la ficha vacía con completitud 0, sin crear el plan. Los errores del
    cifrado (ClaveDestruida, ClaveNoDisponible, SeccionIlegible, ...) siguen hacia la API, que los
    traduce sin el texto.
    """
    plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
    campos: dict[CampoFicha, EstadoCampo] = dict.fromkeys(CAMPOS_FICHA, CAMPO_NUNCA_ESCRITO)
    if plan is not None:
        for seccion in repositorio.secciones(plan.id):
            campo = CampoFicha(seccion.tipo)
            texto = cifrador.descifrar(
                persona_cuidada_id=peticion.persona_cuidada_id, plan_id=plan.id, tipo=campo.value,
                seccion=seccion.cifrada,
            )
            campos[campo] = EstadoCampo(
                texto=texto_visible(texto),
                version=seccion.version,
                actualizado_por=seccion.actualizado_por,
                actualizado_en=seccion.actualizado_en,
            )
    escritos = [c.actualizado_en for c in campos.values() if c.actualizado_en is not None]
    ficha = Ficha(
        persona_cuidada_id=peticion.persona_cuidada_id,
        completitud=completitud(sum(1 for c in campos.values() if c.con_texto)),
        actualizado_en=max(escritos) if escritos else None,
        campos=campos,
    )
    auditoria.registrar_lectura(_evento(peticion, None if plan is None else plan.id, None, reloj.ahora()))
    return ficha


def _estado_guardado(
    peticion: PeticionFicha, plan_id: uuid.UUID, campo: CampoFicha, repositorio: RepositorioFicha,
    cifrador: CifradorSecciones,
) -> EstadoCampo:
    seccion = repositorio.seccion(plan_id, campo.value)
    if seccion is None:
        return CAMPO_NUNCA_ESCRITO
    texto = cifrador.descifrar(
        persona_cuidada_id=peticion.persona_cuidada_id, plan_id=plan_id, tipo=campo.value, seccion=seccion.cifrada
    )
    return EstadoCampo(
        texto=texto_visible(texto),
        version=seccion.version,
        actualizado_por=seccion.actualizado_por,
        actualizado_en=seccion.actualizado_en,
    )


def _conflicto(
    peticion: PeticionFicha, plan_id: uuid.UUID | None, campo: CampoFicha, repositorio: RepositorioFicha,
    cifrador: CifradorSecciones, auditoria: AuditoriaFicha, ahora: datetime,
) -> CampoEnConflicto:
    """El contenido vigente del campo, leído y auditado como plan.leer (contrato, decisión 8)."""
    actual = CAMPO_NUNCA_ESCRITO if plan_id is None else _estado_guardado(
        peticion, plan_id, campo, repositorio, cifrador
    )
    auditoria.registrar_lectura(_evento(peticion, plan_id, None, ahora))
    return CampoEnConflicto(campo=campo, actual=actual)


def guardar_campo(
    peticion: PeticionFicha,
    campo: CampoFicha,
    texto: str,
    precondicion: Precondicion,
    repositorio: RepositorioFicha,
    cifrador: CifradorSecciones,
    auditoria: AuditoriaFicha,
    reloj: Reloj,
) -> CampoGuardado | CampoEnConflicto:
    """Cifra y guarda un campo si se cumple la precondición, y recalcula la completitud del plan.

    - SiNoExiste (If-None-Match: *): crea el campo en versión 1 (creado=True). Si es la primera
      escritura de la ficha, crea el plan ('ficha_relevo') y, al cifrar, la clave de datos. Con texto
      vacío, VacioSinCrear antes de tocar la base. Si otro creó el campo antes: CampoEnConflicto.
    - SiCoincide (If-Match): actualiza a versión + 1 solo si el campo sigue en esa versión. Texto
      vacío lo vacía. Si el campo cambió o nunca se escribió: CampoEnConflicto.

    El texto ya llega validado (largo y caracteres) por el esquema de la API; aquí se normaliza otra
    vez, lo que no cambia un texto ya normalizado.
    """
    texto = normalizar_texto(texto)
    if isinstance(precondicion, SiNoExiste) and not texto:
        raise VacioSinCrear()
    ahora = reloj.ahora()

    plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
    if isinstance(precondicion, SiCoincide):
        if plan is None or precondicion.version is None:
            return _conflicto(
                peticion, None if plan is None else plan.id, campo, repositorio, cifrador, auditoria, ahora
            )
    elif plan is None:
        repositorio.crear_plan(
            uuid.uuid4(), peticion.grupo_id, peticion.persona_cuidada_id, peticion.usuario_id, ahora
        )
        # Si otra escritura lo creó primero, crear_plan no escribió y se usa el de ella
        plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
        if plan is None:
            raise PlanNoDisponible()

    cifrada = cifrador.cifrar(
        grupo_id=peticion.grupo_id,
        persona_cuidada_id=peticion.persona_cuidada_id,
        plan_id=plan.id,
        tipo=campo.value,
        texto=texto,
    )

    if isinstance(precondicion, SiNoExiste):
        creado = repositorio.insertar_seccion(plan.id, campo.value, cifrada, peticion.usuario_id, ahora)
        if not creado:
            return _conflicto(peticion, plan.id, campo, repositorio, cifrador, auditoria, ahora)
        version = 1
    else:
        assert precondicion.version is not None
        nueva = repositorio.actualizar_seccion_si_version(
            plan.id, campo.value, cifrada, precondicion.version, peticion.usuario_id, ahora
        )
        if nueva is None:
            return _conflicto(peticion, plan.id, campo, repositorio, cifrador, auditoria, ahora)
        creado, version = False, nueva

    pct = completitud(repositorio.campos_con_texto(plan.id))
    repositorio.actualizar_plan(plan.id, pct, peticion.usuario_id, ahora)
    autor = repositorio.autor(peticion.usuario_id)
    if autor is None:
        # La cuenta de quien escribe siempre es visible para ella misma (política usuario_propio)
        raise PlanNoDisponible()

    auditoria.registrar_edicion(_evento(peticion, plan.id, campo, ahora))
    return CampoGuardado(
        campo=campo,
        estado=EstadoCampo(texto=texto_visible(texto), version=version, actualizado_por=autor, actualizado_en=ahora),
        completitud=pct,
        creado=creado,
    )
