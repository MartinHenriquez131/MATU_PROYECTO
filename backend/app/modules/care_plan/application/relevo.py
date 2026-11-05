"""Casos de uso del acceso de relevo: compartir la ficha y listar los accesos (MATU-18, RF-05) y
revocar un acceso (MATU-20, RF-07).

Llegan aquí solo peticiones que ya pasaron por el token (401), la membresía, el rol y la persona
(404) y, para compartir, el consentimiento vigente y la revisión anual (403). Lo hacen las
dependencias de la API antes de leer el cuerpo.

- Se comparte aunque la ficha esté incompleta o vacía: si el plan no existe, se crea con modo
  'ficha_relevo' (sin clave de datos ni secciones).
- El token y el PIN se generan aquí y salen una sola vez, en AccesoEntregado. Al repositorio solo
  llegan sus huellas. Ni el token ni el PIN aparecen en el repr.
- El acceso copia el nombre de pila de la persona y el de quien comparte, para que el relevo nunca
  lea persona_cuidada ni usuario (decisión 28).
- Desde MATU-50 (ADR-028) los tres campos base van siempre, y las secciones complementarias solo si se
  piden y ya están agregadas (SeccionNoAgregada si no). El servidor nunca agrega una por su cuenta.
  secciones_permitidas guarda los tres campos base más las secciones pedidas.
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
from app.modules.care_plan.domain.relevo import MotivoAcceso, debe_revocar, nombre_pila, vigencia
from app.modules.care_plan.domain.secciones import (
    SeccionComplementaria,
    secciones_a_compartir,
    secciones_permitidas,
)
from app.shared.puertos import Reloj


@dataclass(frozen=True)
class SolicitudCompartir:
    nombre_relevo: str
    telefono_relevo: str = field(repr=False)  # ya normalizado: +569XXXXXXXX
    # Las secciones complementarias pedidas (MATU-50). Los tres campos base van siempre
    secciones: tuple[SeccionComplementaria, ...]
    motivo: MotivoAcceso
    expira_en: datetime | None


@dataclass(frozen=True)
class AccesoEntregado:
    id: uuid.UUID
    token: str = field(repr=False)  # base64url sin relleno, 43 caracteres
    pin: str = field(repr=False)
    campos: tuple[CampoFicha, ...]
    secciones: tuple[SeccionComplementaria, ...]
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
    """Crea el acceso. VigenciaInvalida si expira_en no cabe; SeccionNoAgregada si se pide compartir una
    sección que no está agregada; PlanNoDisponible si no hay plan ni se crea."""
    ahora = reloj.ahora()
    expira_en = vigencia(ahora, solicitud.expira_en)
    nombre_persona = accesos.nombre_pila_persona(peticion.persona_cuidada_id)
    nombre_comparte = accesos.nombre_usuario(peticion.usuario_id)
    if nombre_persona is None or nombre_comparte is None:
        raise PlanNoDisponible
    # Antes de crear el plan: sin plan no hay secciones agregadas, y pedir una es un 422
    plan = fichas.obtener_plan(peticion.persona_cuidada_id)
    agregadas = set() if plan is None else fichas.tipos_agregados(plan.id)
    secciones = secciones_a_compartir(solicitud.secciones, agregadas)
    plan_id = _plan_id(peticion, fichas, ahora)
    acceso_id = uuid.uuid4()
    token = generador.token()
    pin = generador.pin()
    # Los tres campos base van siempre, en el orden de la ficha (MATU-50)
    campos = CAMPOS_FICHA
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
            campos=secciones_permitidas(secciones),
            motivo=solicitud.motivo.value,
            token_hash=huellas.huella_token(token),
            pin_hash=huellas.huella_pin(acceso_id, pin),
            creado_en=ahora,
            expira_en=expira_en,
            # La declaración de aviso la exige el esquema (decisión 34); se fecha con el reloj
            relevo_informado_en=ahora,
            request_id=peticion.request_id,
        )
    )
    return AccesoEntregado(
        id=acceso_id,
        token=codificar_token(token),
        pin=pin,
        campos=campos,
        secciones=secciones,
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


class AccesoNoEncontrado(LookupError):
    """El acceso no existe, es de otro grupo o RLS no lo muestra: la API responde 404."""


@dataclass(frozen=True)
class PeticionRevocar:
    grupo_id: uuid.UUID
    usuario_id: uuid.UUID
    acceso_id: uuid.UUID
    request_id: str | None


def revocar(peticion: PeticionRevocar, accesos: RepositorioAccesos, reloj: Reloj) -> bool:
    """Revoca el acceso. Devuelve si el estado cambió.

    Idempotente: uno ya revocado conserva su primer revocado_en (C15) y uno vencido queda sin
    revocado_en; en los dos casos no se escribe nada ni se audita (C16). No exige consentimiento
    vigente (decisión 18): cortar un acceso siempre es posible. AccesoNoEncontrado si no hay acceso.
    """
    vida = accesos.vida_para_revocar(peticion.acceso_id)
    if vida is None:
        raise AccesoNoEncontrado
    ahora = reloj.ahora()
    if not debe_revocar(vida, ahora):
        return False
    accesos.revocar(peticion.acceso_id, ahora, peticion.usuario_id, peticion.request_id)
    return True
