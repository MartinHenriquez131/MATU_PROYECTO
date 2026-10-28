"""Casos de uso del acceso de relevo: compartir la ficha y listar los accesos (MATU-18, RF-05).

Llegan aquí solo peticiones que ya pasaron por el token (401), la membresía, el rol y la persona
(404) y, para compartir, el consentimiento vigente y la revisión anual (403). Lo hacen las
dependencias de la API antes de leer el cuerpo.

- Se comparte aunque la ficha esté incompleta o vacía: si el plan no existe, se crea con modo
  'ficha_relevo' (sin clave de datos ni secciones).
- El token y el PIN se generan aquí y salen una sola vez, en AccesoEntregado. Al repositorio solo
  llegan sus huellas. Ni el token ni el PIN aparecen en el repr.
- El acceso copia el nombre de pila de la persona y el de quien comparte, para que el relevo nunca
  lea persona_cuidada ni usuario (decisión 28).
"""

import base64
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.modules.care_plan.application.ficha import PeticionFicha, PlanNoDisponible
from app.modules.care_plan.application.ports import (
    AccesoListado,
    AccesoNuevo,
    GeneradorCredencialesRelevo,
    HuellasRelevo,
    Posicion,
    RepositorioAccesos,
    RepositorioFicha,
)
from app.modules.care_plan.domain.ficha import CAMPOS_FICHA, CampoFicha
from app.modules.care_plan.domain.relevo import MotivoAcceso, nombre_pila, vigencia
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class SolicitudCompartir:
    nombre_relevo: str
    telefono_relevo: str = field(repr=False)  # ya normalizado: +569XXXXXXXX
    campos: tuple[CampoFicha, ...]
    motivo: MotivoAcceso
    expira_en: datetime | None


@dataclass(frozen=True)
class AccesoEntregado:
    id: uuid.UUID
    token: str = field(repr=False)  # base64url sin relleno, 43 caracteres
    pin: str = field(repr=False)
    campos: tuple[CampoFicha, ...]
    expira_en: datetime
    nombre_relevo: str
    nombre_pila_persona: str


def codificar_token(token: bytes) -> str:
    return base64.urlsafe_b64encode(token).rstrip(b"=").decode("ascii")


def _plan_id(peticion: PeticionFicha, fichas: RepositorioFicha, ahora: datetime) -> uuid.UUID:
    plan = fichas.obtener_plan(peticion.persona_cuidada_id)
    if plan is None:
        fichas.crear_plan(uuid.uuid4(), peticion.grupo_id, peticion.persona_cuidada_id, peticion.usuario_id, ahora)
        plan = fichas.obtener_plan(peticion.persona_cuidada_id)
    if plan is None:
        raise PlanNoDisponible
    return plan.id


def compartir(
    peticion: PeticionFicha,
    solicitud: SolicitudCompartir,
    fichas: RepositorioFicha,
    accesos: RepositorioAccesos,
    generador: GeneradorCredencialesRelevo,
    huellas: HuellasRelevo,
    reloj: Reloj,
) -> AccesoEntregado:
    """Crea el acceso. VigenciaInvalida si expira_en no cabe; PlanNoDisponible si no hay plan ni se crea."""
    ahora = reloj.ahora()
    expira_en = vigencia(ahora, solicitud.expira_en)
    nombre_persona = accesos.nombre_pila_persona(peticion.persona_cuidada_id)
    nombre_comparte = accesos.nombre_usuario(peticion.usuario_id)
    if nombre_persona is None or nombre_comparte is None:
        raise PlanNoDisponible
    plan_id = _plan_id(peticion, fichas, ahora)
    acceso_id = uuid.uuid4()
    token = generador.token()
    pin = generador.pin()
    # En el orden de la ficha, sin importar el orden pedido
    campos = tuple(c for c in CAMPOS_FICHA if c in solicitud.campos)
    accesos.crear(
        AccesoNuevo(
            id=acceso_id,
            grupo_id=peticion.grupo_id,
            plan_id=plan_id,
            otorgado_por=peticion.usuario_id,
            nombre_relevo=solicitud.nombre_relevo,
            telefono_relevo=solicitud.telefono_relevo,
            nombre_pila_persona=nombre_persona,
            nombre_pila_comparte=nombre_pila(nombre_comparte),
            campos=tuple(c.value for c in campos),
            motivo=solicitud.motivo.value,
            token_hash=huellas.huella_token(token),
            pin_hash=huellas.huella_pin(acceso_id, pin),
            creado_en=ahora,
            expira_en=expira_en,
            request_id=peticion.request_id,
        )
    )
    return AccesoEntregado(
        id=acceso_id,
        token=codificar_token(token),
        pin=pin,
        campos=campos,
        expira_en=expira_en,
        nombre_relevo=solicitud.nombre_relevo,
        nombre_pila_persona=nombre_persona,
    )


@dataclass(frozen=True)
class PaginaAccesos:
    accesos: list[AccesoListado]
    siguiente: Posicion | None


def listar(
    peticion: PeticionFicha,
    fichas: RepositorioFicha,
    accesos: RepositorioAccesos,
    reloj: Reloj,
    estado: str | None,
    despues_de: Posicion | None,
    limite: int,
) -> PaginaAccesos:
    """Una página de accesos. Sin plan no hay accesos: listar nunca crea el plan."""
    plan = fichas.obtener_plan(peticion.persona_cuidada_id)
    if plan is None:
        return PaginaAccesos(accesos=[], siguiente=None)
    filas = accesos.listar(plan.id, reloj.ahora(), estado, despues_de, limite + 1)
    pagina = filas[:limite]
    siguiente = None
    if len(filas) > limite:
        ultimo = pagina[-1]
        siguiente = Posicion(creado_en=ultimo.creado_en, id=ultimo.id)
    return PaginaAccesos(accesos=pagina, siguiente=siguiente)
