"""Caso de uso: ver quién abrió la ficha con un acceso de relevo (MATU-45, RF-08).

Llegan aquí solo peticiones que ya pasaron por el token (401) y por la membresía, el rol y la persona
(404): listan admin, cuidador y pagador con puede_ver_plan (dependencia persona_para_listar). No exige
consentimiento vigente, igual que listar accesos (decisión 18): ver lo que pasó siempre es posible.
Sin plan no hay aperturas, y listar nunca crea el plan.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.care_plan.application.ficha import PeticionFicha
from app.modules.care_plan.application.ports import PosicionApertura, RepositorioAperturas, RepositorioFicha
from app.modules.care_plan.domain.aperturas import ACCIONES_DE_APERTURA, TipoApertura, tipo_de_accion


@dataclass(frozen=True)
class Apertura:
    ocurrido_en: datetime
    tipo: TipoApertura
    acceso_id: uuid.UUID
    nombre_relevo: str


@dataclass(frozen=True)
class PaginaAperturas:
    aperturas: list[Apertura]
    siguiente: PosicionApertura | None


def listar_aperturas(
    peticion: PeticionFicha,
    fichas: RepositorioFicha,
    aperturas: RepositorioAperturas,
    despues_de: PosicionApertura | None,
    limite: int,
) -> PaginaAperturas:
    plan = fichas.obtener_plan(peticion.persona_cuidada_id)
    if plan is None:
        return PaginaAperturas(aperturas=[], siguiente=None)
    filas = aperturas.listar(plan.id, ACCIONES_DE_APERTURA, despues_de, limite + 1)
    pagina = filas[:limite]
    siguiente = None
    if len(filas) > limite:
        ultima = pagina[-1]
        siguiente = PosicionApertura(ocurrido_en=ultima.ocurrido_en, id=ultima.id)
    items = []
    for fila in pagina:
        tipo = tipo_de_accion(fila.accion)
        if tipo is not None:  # el repositorio filtra por acción; esto es defensa en profundidad
            items.append(Apertura(fila.ocurrido_en, tipo, fila.acceso_id, fila.nombre_relevo))
    return PaginaAperturas(aperturas=items, siguiente=siguiente)
