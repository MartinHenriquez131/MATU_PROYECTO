"""Dependencias del consumo: quién puede, sobre qué persona y con qué autorización (MATU-36).

Corren antes de validar el cuerpo, en el orden del contrato:

1. Access token válido (usuario_actual). Si no, 401.
2. X-Grupo-Id y membresía activa (sesion_de_grupo). Si no, 404.
3. El rol alcanza: leen admin, cuidador, pagador y observador; escriben admin y cuidador (decisión 71).
   Si no, 404, nunca 403.
4. persona_id es una persona del grupo. Si no, 404.
5. Autorización vigente para ``consumo``, con el puerto Reloj: 403 sin-consentimiento o
   revision-vencida, con el miembro de extensión ``finalidad: consumo``. Se evalúa antes de leer nada
   del consumo.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path

from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.domain.personas import FINALIDAD_CONSUMO, EstadoAutorizacion, estado_autorizacion
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion
from app.modules.consumption.application.ports import RepositorioAlertas, RepositorioPerfiles
from app.modules.consumption.domain.perfil import puede_escribir, puede_leer
from app.modules.consumption.infrastructure.repositorio_alertas import RepositorioAlertasSQL
from app.modules.consumption.infrastructure.repositorio_perfiles import RepositorioPerfilesSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import RegistroAuditoria, Reloj

# Los path params se declaran str: un valor que no es UUID responde 404, no 422
PersonaIdRuta = Annotated[str, Path(json_schema_extra={"format": "uuid"})]
PerfilIdRuta = Annotated[str, Path(json_schema_extra={"format": "uuid"})]
AlertaIdRuta = Annotated[str, Path(json_schema_extra={"format": "uuid"})]

_EXTENSION = {"finalidad": FINALIDAD_CONSUMO}


@dataclass(frozen=True)
class ConsumoAutorizado:
    contexto: ContextoGrupo
    persona_id: uuid.UUID


def uuid_o_404(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _autorizar(contexto: ContextoGrupo, persona_id: str, reloj: Reloj) -> ConsumoAutorizado:
    persona = persona_con_autorizacion(contexto.sesion, contexto.grupo_id, uuid_o_404(persona_id), FINALIDAD_CONSUMO)
    if persona is None:
        raise ErrorMATU(404)
    estado = estado_autorizacion(persona.autorizacion, reloj.ahora())
    if estado is EstadoAutorizacion.SIN_CONSENTIMIENTO:
        raise ErrorMATU(
            403,
            tipo="sin-consentimiento",
            detalle="Falta la autorización para calcular los insumos de esta persona",
            extension=_EXTENSION,
        )
    if estado is EstadoAutorizacion.REVISION_VENCIDA:
        raise ErrorMATU(
            403,
            tipo="revision-vencida",
            titulo="Autorización por renovar",
            detalle="Venció la revisión anual de la autorización para calcular los insumos de esta persona",
            extension=_EXTENSION,
        )
    return ConsumoAutorizado(contexto=contexto, persona_id=persona.id)


def consumo_para_leer(
    contexto: SesionDeGrupo, persona_id: PersonaIdRuta, reloj: Annotated[Reloj, Depends(obtener_reloj)]
) -> ConsumoAutorizado:
    if not puede_leer(contexto.rol):
        raise ErrorMATU(404)
    return _autorizar(contexto, persona_id, reloj)


def consumo_para_escribir(
    contexto: SesionDeGrupo, persona_id: PersonaIdRuta, reloj: Annotated[Reloj, Depends(obtener_reloj)]
) -> ConsumoAutorizado:
    if not puede_escribir(contexto.rol):
        raise ErrorMATU(404)
    return _autorizar(contexto, persona_id, reloj)


def obtener_repositorio_perfiles(contexto: SesionDeGrupo) -> RepositorioPerfiles:
    return RepositorioPerfilesSQL(contexto.sesion, contexto.grupo_id)


def obtener_repositorio_alertas(contexto: SesionDeGrupo) -> RepositorioAlertas:
    return RepositorioAlertasSQL(contexto.sesion, contexto.grupo_id)


def obtener_registro_auditoria_consumo(
    contexto: SesionDeGrupo, reloj: Annotated[Reloj, Depends(obtener_reloj)]
) -> RegistroAuditoria:
    """El registro de auditoría en la transacción de la petición. Las pruebas lo pueden sobreescribir."""
    return RegistroAuditoriaSql(contexto.sesion, reloj)


ParaLeer = Annotated[ConsumoAutorizado, Depends(consumo_para_leer)]
ParaEscribir = Annotated[ConsumoAutorizado, Depends(consumo_para_escribir)]
Repositorio = Annotated[RepositorioPerfiles, Depends(obtener_repositorio_perfiles)]
Auditoria = Annotated[RegistroAuditoria, Depends(obtener_registro_auditoria_consumo)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]
RepositorioDeAlertas = Annotated[RepositorioAlertas, Depends(obtener_repositorio_alertas)]
