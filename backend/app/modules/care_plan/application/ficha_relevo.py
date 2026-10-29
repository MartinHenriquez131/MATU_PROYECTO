"""Leer la ficha como relevo, con la sesión del canje (MATU-19, RF-06).

GET /v1/relevo/ficha. La API ya resolvió la cookie (401 sin-sesion-relevo) y el estado en indice_token
(410 revocado o vencido). Aquí, en la sesión de relevo y en una sola transacción:

- Acceso invisible por RLS → 410 vencido (C5); bloqueado → 423 (C4); autorización no vigente → 410
  pausado (decisión 33).
- Solo las secciones habilitadas (RLS seccion_relevo y, además, el filtro del dominio). Un campo vacío
  o nunca escrito sale como None. Nada más del grupo: ni el nombre completo, ni autores.
- relevo.abrir en la misma transacción que la lectura (C7): si el registro falla, la excepción sube,
  sesion_tenant deshace y no se devuelve texto. Suma usos y fija ultimo_uso_en.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.modules.care_plan.application.canje_relevo import acceso_utilizable, entrada_relevo
from app.modules.care_plan.application.ports import CifradorSecciones, RepositorioAccesoRelevo, SeccionesRelevo
from app.modules.care_plan.domain.relevo import campos_para_relevo
from app.shared.auditoria import AccionAuditoria, EntidadAuditoria
from app.shared.puertos import RegistroAuditoria, Reloj


class PlanDelRelevoNoDisponible(Exception):
    """El plan del acceso no es visible: no debería pasar con un acceso vigente."""


@dataclass(frozen=True)
class FichaDelRelevo:
    nombre_pila: str
    nombre_pila_comparte: str
    vence_en: datetime
    campos: dict[str, str | None] = field(repr=False)


def leer_ficha_relevo(
    accesos: RepositorioAccesoRelevo,
    secciones: SeccionesRelevo,
    cifrador: CifradorSecciones,
    registro: RegistroAuditoria,
    reloj: Reloj,
    request_id: str | None,
) -> FichaDelRelevo:
    acceso = acceso_utilizable(accesos, reloj)
    persona = secciones.persona_del_plan(acceso.plan_id)
    if persona is None:
        raise PlanDelRelevoNoDisponible
    textos: dict[str, str] = {}
    for tipo, cifrada in secciones.secciones(acceso.plan_id):
        if tipo in acceso.campos:
            textos[tipo] = cifrador.descifrar(
                persona_cuidada_id=persona, plan_id=acceso.plan_id, tipo=tipo, seccion=cifrada
            )
    registro.registrar(
        entrada_relevo(
            acceso, AccionAuditoria.RELEVO_ABRIR, request_id,
            entidad=EntidadAuditoria.PLAN_CUIDADO, entidad_id=acceso.plan_id,
        )
    )
    accesos.registrar_uso(reloj.ahora())
    return FichaDelRelevo(
        nombre_pila=acceso.nombre_pila_persona,
        nombre_pila_comparte=acceso.nombre_pila_comparte,
        vence_en=acceso.expira_en,
        campos=campos_para_relevo(acceso.campos, textos),
    )
