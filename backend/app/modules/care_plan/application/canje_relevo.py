"""Antes del PIN: presentar el acceso y canjear el enlace con el PIN (MATU-19, RF-06).

Contrato: docs/api/propuestos/relevo.openapi.yaml, POST /v1/relevo/presentacion y /v1/relevo/canje.

Condición C2 del analista normativo: estos casos de uso solo leen y escriben acceso_relevo (por
RepositorioAccesoRelevo) e insertan auditoría. No importan ni llaman nada de plan_seccion, clave_datos
ni del cifrador: antes del PIN no se toca la ficha. tests/test_arquitectura.py lo verifica.

El orden de evaluación es el del contrato, con la decisión 33 de Martín (28-10) agregada:

1. indice_token (verificar_indice): sin entrada → 410 no-disponible; revocado → 410 revocado;
   vencido según el Reloj → 410 vencido.
2. Con la sesión de relevo: si RLS no muestra el acceso (now() de la base ya lo dio por vencido),
   410 vencido (condición C5), nunca 500 ni otro rol.
3. Bloqueado (5 PIN incorrectos) → 423.
4. Autorización de la persona no vigente → 410 relevo-pausado, sin revelar el motivo. No cuenta como
   intento y no crea sesión.
5. Solo en el canje: el PIN.

Un PIN incorrecto no lanza: devuelve el resultado, para que la transacción confirme el contador y la
fila de auditoría antes de responder 401 o 423 (condición C6). sesion_tenant deshace ante excepciones.
"""

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.modules.care_plan.application.ports import (
    AccesoDelRelevo,
    EntradaIndice,
    HuellasRelevo,
    RepositorioAccesoRelevo,
    SesionesRelevo,
)
from app.modules.care_plan.domain.relevo import (
    EstadoAcceso,
    VidaAcceso,
    bloqueado,
    estado_acceso,
    segundos_de_sesion,
    tras_intento,
)
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


class TipoNoDisponible(StrEnum):
    NO_DISPONIBLE = "relevo-no-disponible"
    VENCIDO = "relevo-vencido"
    REVOCADO = "relevo-revocado"
    PAUSADO = "relevo-pausado"


class RelevoNoDisponible(Exception):
    """410. ``tipo`` dice cuál, para que la página muestre su texto. Pausado no dice por qué."""

    def __init__(self, tipo: TipoNoDisponible) -> None:
        super().__init__(tipo.value)
        self.tipo = tipo


class RelevoBloqueado(Exception):
    """423: el acceso acumuló 5 PIN incorrectos."""


class PinNoVerificable(Exception):
    """Falta PEPPER_PIN: el canje no puede comparar el PIN y falla cerrado (503)."""


def verificar_indice(entrada: EntradaIndice | None, ahora: datetime) -> uuid.UUID:
    """El id del acceso si indice_token lo da por vigente. Si no, RelevoNoDisponible (paso 1)."""
    if entrada is None:
        raise RelevoNoDisponible(TipoNoDisponible.NO_DISPONIBLE)
    estado = estado_acceso(VidaAcceso(entrada.expira_en, entrada.revocado_en, 0), ahora)
    if estado is EstadoAcceso.REVOCADO:
        raise RelevoNoDisponible(TipoNoDisponible.REVOCADO)
    if estado is EstadoAcceso.VENCIDO:
        raise RelevoNoDisponible(TipoNoDisponible.VENCIDO)
    return entrada.acceso_id


def acceso_utilizable(accesos: RepositorioAccesoRelevo, reloj: Reloj, *, bloquear: bool = False) -> AccesoDelRelevo:
    """Pasos 2 a 4, en la sesión de relevo. No escribe nada. ``bloquear``: FOR UPDATE (canje)."""
    acceso = accesos.leer(bloquear=bloquear)
    if acceso is None:
        raise RelevoNoDisponible(TipoNoDisponible.VENCIDO)
    if bloqueado(acceso.pin_intentos_fallidos):
        raise RelevoBloqueado
    if not accesos.autorizacion_vigente(reloj.ahora()):
        raise RelevoNoDisponible(TipoNoDisponible.PAUSADO)
    return acceso


def entrada_relevo(
    acceso: AccesoDelRelevo,
    accion: AccionAuditoria,
    request_id: str | None,
    *,
    entidad: EntidadAuditoria = EntidadAuditoria.ACCESO_RELEVO,
    entidad_id: uuid.UUID | None = None,
) -> EntradaAuditoria:
    """Fila de auditoría del relevo (condición C8): actor relevo, actor_ref = el acceso, grupo del acceso
    leído de la base (no de Redis), sin motivo ni IP, sin nombre, teléfono, token, hash ni PIN."""
    return EntradaAuditoria(
        grupo_id=acceso.grupo_id,
        actor_tipo=ActorTipo.RELEVO,
        actor_ref=acceso.id,
        accion=accion,
        entidad=entidad,
        entidad_id=acceso.id if entidad_id is None else entidad_id,
        request_id=request_id,
    )


@dataclass(frozen=True)
class Presentacion:
    nombre_pila_comparte: str
    nombre_pila: str


def presentar(
    accesos: RepositorioAccesoRelevo, registro: RegistroAuditoria, reloj: Reloj, request_id: str | None
) -> Presentacion:
    """Los dos nombres de pila (decisión 28). No cuenta intento, no crea sesión, no suma usos.
    Registra relevo.presentar (decisión 30)."""
    acceso = acceso_utilizable(accesos, reloj)
    registro.registrar(entrada_relevo(acceso, AccionAuditoria.RELEVO_PRESENTAR, request_id))
    return Presentacion(nombre_pila_comparte=acceso.nombre_pila_comparte, nombre_pila=acceso.nombre_pila_persona)


@dataclass(frozen=True)
class CanjeAceptado:
    """PIN correcto. La sesión se crea con abrir_sesion DESPUÉS del commit de la transacción del canje:
    si el commit falla, no queda una sesión sin su fila relevo.canje."""

    acceso_id: uuid.UUID
    max_age: int


@dataclass(frozen=True)
class SesionCreada:
    sesion_id: str
    max_age: int

    def __repr__(self) -> str:
        return f"SesionCreada(max_age={self.max_age})"


@dataclass(frozen=True)
class PinIncorrecto:
    restantes: int


@dataclass(frozen=True)
class AccesoBloqueadoAhora:
    """Este intento fue el 5.º."""


ResultadoCanje = CanjeAceptado | PinIncorrecto | AccesoBloqueadoAhora


def canjear(
    pin: str,
    accesos: RepositorioAccesoRelevo,
    huellas: HuellasRelevo | None,
    registro: RegistroAuditoria,
    reloj: Reloj,
    request_id: str | None,
) -> ResultadoCanje:
    """Pasos 2 a 7 del canje. Lanza solo antes de escribir (410, 423, 503)."""
    acceso = acceso_utilizable(accesos, reloj, bloquear=True)
    if huellas is None:
        raise PinNoVerificable
    if not hmac.compare_digest(huellas.huella_pin(acceso.id, pin), acceso.pin_hash):
        contador = accesos.sumar_intento()
        if contador is None:  # otro canje lo bloqueó primero: este intento no cuenta
            raise RelevoBloqueado
        intento = tras_intento(contador)
        registro.registrar(entrada_relevo(acceso, AccionAuditoria.RELEVO_PIN_INCORRECTO, request_id))
        if intento.bloqueado:
            registro.registrar(entrada_relevo(acceso, AccionAuditoria.RELEVO_BLOQUEO, request_id))
            return AccesoBloqueadoAhora()
        return PinIncorrecto(restantes=intento.restantes)
    segundos = segundos_de_sesion(acceso.expira_en, reloj.ahora())
    if segundos <= 0:
        raise RelevoNoDisponible(TipoNoDisponible.VENCIDO)
    if acceso.pin_intentos_fallidos:
        accesos.reiniciar_intentos()
    registro.registrar(entrada_relevo(acceso, AccionAuditoria.RELEVO_CANJE, request_id))
    return CanjeAceptado(acceso_id=acceso.id, max_age=segundos)


def abrir_sesion(aceptado: CanjeAceptado, sesiones: SesionesRelevo) -> SesionCreada:
    """Paso 7, ya confirmada la transacción: la sesión en el almacén, con TTL = Max-Age."""
    return SesionCreada(sesion_id=sesiones.crear(aceptado.acceso_id, aceptado.max_age), max_age=aceptado.max_age)
