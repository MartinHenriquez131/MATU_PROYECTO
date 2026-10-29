"""Casos de uso de la ficha de relevo: leerla y guardar un campo (MATU-12, RF-02).

Llegan aquí solo peticiones que ya pasaron, en este orden, por el token (401), la membresía, el rol,
la persona y el campo (404) y el consentimiento vigente para plan_cuidado (403): lo hacen las
dependencias de la API antes de que se lea el cuerpo. Por eso, sin consentimiento, ningún caso de
uso corre y no se crea ni el plan ni la clave de datos (analista normativo, condición 1).

- El texto entra y sale en claro solo dentro de la llamada: se cifra con CifradorSecciones antes de
  llegar al repositorio, y se descifra al leer. No se registra ni se guarda en otra parte.
- El plan nace en la primera escritura con texto, con modo 'ficha_relevo'. Leer no lo crea.
- Escribir texto vacío en un campo que nunca se escribió no crea nada (VacioSinCrear, 422): ni el
  plan, ni la clave de datos, ni una versión (contrato, decisión 6).
- La exigencia de If-Match / If-None-Match (412 y 428) es de MATU-13. Hasta entonces, dos escrituras
  del mismo campo se ordenan por el bloqueo de la fila y gana la última.
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
    completitud,
    normalizar_texto,
    texto_visible,
)
from app.shared.puertos import Reloj


class VacioSinCrear(Exception):
    """Texto vacío en un campo que nunca se escribió: no hay nada que crear (contrato, decisión 6)."""


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


def guardar_campo(
    peticion: PeticionFicha,
    campo: CampoFicha,
    texto: str,
    repositorio: RepositorioFicha,
    cifrador: CifradorSecciones,
    auditoria: AuditoriaFicha,
    reloj: Reloj,
) -> CampoGuardado:
    """Cifra y guarda un campo, y recalcula la completitud del plan.

    - Primera escritura de la ficha: crea el plan ('ficha_relevo') y, al cifrar, la clave de datos.
    - Primera escritura del campo: versión 1 (creado=True). Si ya existía: versión + 1.
    - Texto vacío: vacía el campo si ya existía; si nunca se escribió, VacioSinCrear y no escribe nada.

    El texto ya llega validado (largo y caracteres) por el esquema de la API; aquí se normaliza otra
    vez, lo que no cambia un texto ya normalizado.
    """
    texto = normalizar_texto(texto)
    ahora = reloj.ahora()

    plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
    if plan is None:
        if not texto:
            raise VacioSinCrear()
        repositorio.crear_plan(
            uuid.uuid4(), peticion.grupo_id, peticion.persona_cuidada_id, peticion.usuario_id, ahora
        )
        # Si otra escritura lo creó primero, crear_plan no escribió y se usa el de ella
        plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
        if plan is None:
            raise PlanNoDisponible()

    version_actual = repositorio.version_para_escribir(plan.id, campo.value)
    if version_actual is None and not texto:
        raise VacioSinCrear()

    cifrada = cifrador.cifrar(
        grupo_id=peticion.grupo_id,
        persona_cuidada_id=peticion.persona_cuidada_id,
        plan_id=plan.id,
        tipo=campo.value,
        texto=texto,
    )

    creado = False
    if version_actual is None:
        creado = repositorio.insertar_seccion(plan.id, campo.value, cifrada, peticion.usuario_id, ahora)
        if not creado:
            # Otra escritura creó el campo entre la lectura y el INSERT: se actualiza sobre la suya
            version_actual = repositorio.version_para_escribir(plan.id, campo.value)
            if version_actual is None:
                raise PlanNoDisponible()
    if creado:
        version = 1
    else:
        assert version_actual is not None
        version = version_actual + 1
        repositorio.actualizar_seccion(plan.id, campo.value, cifrada, version, peticion.usuario_id, ahora)

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
