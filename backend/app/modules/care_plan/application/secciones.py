"""Casos de uso de las secciones complementarias de la ficha: agregar, editar y quitar (MATU-50, ADR-028,
RF-03). Contrato: docs/api/propuestos/ficha-ampliada.openapi.yaml (MATU-49).

Llegan aquí solo peticiones que ya pasaron, en este orden, por el token (401), la membresía, el rol, la
persona y la sección (404), el consentimiento vigente (403) y la custodia (503): lo hacen las
dependencias de la API. Después la API validó el cuerpo y el texto (422) y las cabeceras (422 o 428).

Mismo patrón que un campo base (application/ficha.py, MATU-13):
- El texto se cifra con CifradorSecciones (AES-256-GCM, clave de la persona, AAD plan_id ‖ tipo) antes de
  llegar al repositorio. No se registra ni se guarda en otra parte.
- La comparación con la versión es atómica en la base (INSERT … ON CONFLICT DO NOTHING, UPDATE o DELETE
  … WHERE version). Si no se cumple, nada se escribe y se devuelve SeccionEnConflicto con la sección
  actual descifrada (o None si no está), que se audita como plan.leer. No hay fusión automática.
- La primera escritura crea el plan ('ficha_relevo') y, al cifrar, la clave de datos, como un campo base.
- Las secciones no cuentan para la completitud: guardarlas o quitarlas no la toca.

Lo que no es igual a un campo base:
- Una sección no se vacía: el texto vacío ya lo rechazó la API (422 ``vacio``).
- Quitar borra la fila: el texto cifrado deja de existir. Una sección quitada y vuelta a agregar es otra
  fila, con otro creado_en, y un acceso de relevo anterior no la ve (decisión de Jorge del 03-11).
- La auditoría lleva el tipo de la sección (plan.editar y plan.quitar_seccion), nunca el texto.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.care_plan.application.ficha import PeticionFicha, PlanNoDisponible
from app.modules.care_plan.application.ports import (
    AuditoriaFicha,
    CifradorSecciones,
    EventoFicha,
    RepositorioFicha,
)
from app.modules.care_plan.domain.ficha import EstadoCampo, Precondicion, SiCoincide, SiNoExiste
from app.modules.care_plan.domain.secciones import SeccionComplementaria
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class SeccionGuardadaEnFicha:
    seccion: SeccionComplementaria
    estado: EstadoCampo
    # True si la sección se agregó (201), False si se editó (200)
    creada: bool


@dataclass(frozen=True)
class SeccionEnConflicto:
    """La precondición no se cumplió (412): nada se escribió ni se borró.

    ``actual`` es la sección vigente, descifrada, o None si no está (nunca agregada o ya quitada). Su
    lectura ya quedó auditada como plan.leer.
    """

    seccion: SeccionComplementaria
    actual: EstadoCampo | None


def _evento(
    peticion: PeticionFicha, plan_id: uuid.UUID | None, seccion: SeccionComplementaria | None, ahora: datetime
) -> EventoFicha:
    return EventoFicha(
        grupo_id=peticion.grupo_id,
        usuario_id=peticion.usuario_id,
        persona_cuidada_id=peticion.persona_cuidada_id,
        plan_id=plan_id,
        campo=None if seccion is None else seccion.value,
        request_id=peticion.request_id,
        ocurrido_en=ahora,
    )


def _actual(
    peticion: PeticionFicha, plan_id: uuid.UUID, seccion: SeccionComplementaria, repositorio: RepositorioFicha,
    cifrador: CifradorSecciones,
) -> EstadoCampo | None:
    guardada = repositorio.seccion(plan_id, seccion.value)
    if guardada is None:
        return None
    texto = cifrador.descifrar(
        persona_cuidada_id=peticion.persona_cuidada_id, plan_id=plan_id, tipo=seccion.value, seccion=guardada.cifrada
    )
    return EstadoCampo(
        texto=texto,
        version=guardada.version,
        actualizado_por=guardada.actualizado_por,
        actualizado_en=guardada.actualizado_en,
    )


def _conflicto(
    peticion: PeticionFicha, plan_id: uuid.UUID | None, seccion: SeccionComplementaria, repositorio: RepositorioFicha,
    cifrador: CifradorSecciones, auditoria: AuditoriaFicha, ahora: datetime,
) -> SeccionEnConflicto:
    """La sección vigente, leída y auditada como plan.leer (contrato, decisión 8)."""
    actual = None if plan_id is None else _actual(peticion, plan_id, seccion, repositorio, cifrador)
    auditoria.registrar_lectura(_evento(peticion, plan_id, None, ahora))
    return SeccionEnConflicto(seccion=seccion, actual=actual)


def guardar_seccion(
    peticion: PeticionFicha,
    seccion: SeccionComplementaria,
    texto: str,
    precondicion: Precondicion,
    repositorio: RepositorioFicha,
    cifrador: CifradorSecciones,
    auditoria: AuditoriaFicha,
    reloj: Reloj,
) -> SeccionGuardadaEnFicha | SeccionEnConflicto:
    """Cifra y guarda la sección si se cumple la precondición. ``texto`` ya viene validado y normalizado
    por domain.secciones.validar_texto_seccion (no vacío, dentro del máximo).

    - SiNoExiste (If-None-Match: *): la agrega en versión 1 (creada=True). Si es la primera escritura de
      la ficha, crea el plan y, al cifrar, la clave. Si otra persona la agregó antes: SeccionEnConflicto.
    - SiCoincide (If-Match): la reemplaza en versión + 1 solo si sigue en esa versión. Si cambió, no está
      o el ETag no es de MATU: SeccionEnConflicto, sin crear el plan ni la clave.
    """
    ahora = reloj.ahora()
    plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
    if isinstance(precondicion, SiCoincide):
        if plan is None or precondicion.version is None:
            return _conflicto(
                peticion, None if plan is None else plan.id, seccion, repositorio, cifrador, auditoria, ahora
            )
    elif plan is None:
        repositorio.crear_plan(
            uuid.uuid4(), peticion.grupo_id, peticion.persona_cuidada_id, peticion.usuario_id, ahora
        )
        plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
        if plan is None:
            raise PlanNoDisponible()

    cifrada = cifrador.cifrar(
        grupo_id=peticion.grupo_id,
        persona_cuidada_id=peticion.persona_cuidada_id,
        plan_id=plan.id,
        tipo=seccion.value,
        texto=texto,
    )
    if isinstance(precondicion, SiNoExiste):
        if not repositorio.insertar_seccion(plan.id, seccion.value, cifrada, peticion.usuario_id, ahora):
            return _conflicto(peticion, plan.id, seccion, repositorio, cifrador, auditoria, ahora)
        creada, version = True, 1
    else:
        assert precondicion.version is not None
        nueva = repositorio.actualizar_seccion_si_version(
            plan.id, seccion.value, cifrada, precondicion.version, peticion.usuario_id, ahora
        )
        if nueva is None:
            return _conflicto(peticion, plan.id, seccion, repositorio, cifrador, auditoria, ahora)
        creada, version = False, nueva

    autor = repositorio.autor(peticion.usuario_id)
    if autor is None:
        raise PlanNoDisponible()
    auditoria.registrar_edicion_seccion(_evento(peticion, plan.id, seccion, ahora))
    return SeccionGuardadaEnFicha(
        seccion=seccion,
        estado=EstadoCampo(texto=texto, version=version, actualizado_por=autor, actualizado_en=ahora),
        creada=creada,
    )


def quitar_seccion(
    peticion: PeticionFicha,
    seccion: SeccionComplementaria,
    precondicion: SiCoincide,
    repositorio: RepositorioFicha,
    cifrador: CifradorSecciones,
    auditoria: AuditoriaFicha,
    reloj: Reloj,
) -> SeccionEnConflicto | None:
    """Borra la fila de la sección si sigue en la versión de ``If-Match``. None si se quitó (204).

    Si no está (nunca agregada, ya quitada, o sin plan), si el ETag no es de MATU o si cambió:
    SeccionEnConflicto (412), sin borrar nada. Nunca crea el plan ni la clave.
    """
    ahora = reloj.ahora()
    plan = repositorio.obtener_plan(peticion.persona_cuidada_id)
    if plan is None or precondicion.version is None:
        return _conflicto(peticion, None if plan is None else plan.id, seccion, repositorio, cifrador, auditoria, ahora)
    borrada = repositorio.borrar_seccion_si_version(plan.id, seccion.value, precondicion.version)
    if borrada is None:
        return _conflicto(peticion, plan.id, seccion, repositorio, cifrador, auditoria, ahora)
    auditoria.registrar_quitar_seccion(_evento(peticion, plan.id, seccion, ahora), borrada)
    return None
