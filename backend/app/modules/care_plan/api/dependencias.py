"""Dependencias de la ficha de relevo: quién puede, sobre qué persona, con qué autorización y con qué
custodia (MATU-12, RF-02).

Son dependencias, no código de la ruta, para que corran antes de validar el cuerpo y en el orden del
contrato (docs/api/propuestos/ficha.openapi.yaml, "Orden de evaluación"):

1. Access token válido (usuario_actual, de iam). Si no, 401.
2. X-Grupo-Id y membresía activa (sesion_de_grupo, de care_circle). Si no, 404.
3. El rol alcanza: leer admin, cuidador y pagador con puede_ver_plan; escribir admin y cuidador. Si
   no, 404, nunca 403.
4. persona_id es un UUID de una persona del grupo y, al escribir, el campo es uno de los tres. Si
   no, 404.
5. Consentimiento vigente para plan_cuidado, con el puerto Reloj. Si no hay, 403
   /errores/sin-consentimiento; si lo dio un cuidador de hecho y venció la revisión anual, 403
   /errores/revision-vencida (decisión D-B de Jorge, 28-10).
6. La custodia de la KEK está configurada. Si no, 503: la ficha falla cerrada (decisión D-A).

Recién después FastAPI valida el cuerpo (422) y corre la ruta. Así, sin consentimiento no se lee
nada del plan, no se descifra, no se crea ni el plan ni la clave de datos y no se valida el texto
(analista normativo, condición 1). Un 403 o un 404 deshacen la transacción de sesion_de_grupo.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Path

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.domain.personas import EstadoAutorizacion, estado_autorizacion
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion
from app.modules.care_plan.application.ports import (
    AuditoriaFicha,
    CifradorSecciones,
    CustodiaClaves,
    GeneradorCredencialesRelevo,
    HuellasRelevo,
    RepositorioAccesos,
    RepositorioFicha,
)
from app.modules.care_plan.domain.ficha import CAMPOS_FICHA, CampoFicha, campo_de, puede_escribir, puede_leer
from app.modules.care_plan.infrastructure.auditoria_ficha import AuditoriaFichaPendiente
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from app.modules.care_plan.infrastructure.credenciales_relevo import GeneradorSecrets, HuellasHmac
from app.modules.care_plan.infrastructure.custodia_kek_entorno import CustodiaKekEntorno
from app.modules.care_plan.infrastructure.repositorio_accesos import RepositorioAccesosSQL
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from app.modules.care_plan.infrastructure.repositorio_ficha import RepositorioFichaSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.puertos import Reloj

# Los path params se declaran str, no UUID ni enum: un valor inválido responde 404, no 422. El
# esquema de OpenAPI igual dice lo que el contrato (formato uuid y los tres campos).
PersonaIdRuta = Annotated[str, Path(json_schema_extra={"format": "uuid"})]
CampoRuta = Annotated[str, Path(json_schema_extra={"enum": [c.value for c in CAMPOS_FICHA]})]


# --- Custodia de la KEK (decisión D-A) ----------------------------------------------------------------


@lru_cache
def custodia_configurada() -> CustodiaClaves | None:
    """La custodia de la configuración, o None si está apagada.

    Solo CUSTODIA_KEK=entorno_sintetico la enciende, y la configuración exige KEK_ENTORNO con ella.
    Nunca genera una KEK ni usa el doble de pruebas: apagada, None, y las rutas de la ficha
    responden 503. Se construye una vez, al arrancar (preparar_custodia): ahí CustodiaKekEntorno
    registra su WARNING y rechaza un entorno que no esté en su lista permitida.
    """
    config = obtener_configuracion()
    if config.custodia_kek != "entorno_sintetico" or config.kek_entorno is None:
        return None
    return CustodiaKekEntorno(config.kek_entorno, kek_version=config.kek_version, entorno=config.entorno)


def preparar_custodia() -> None:
    """Construye la custodia al arrancar la API (app.main): si no se puede, la API no arranca."""
    custodia_configurada()


def obtener_custodia() -> CustodiaClaves | None:
    """Dependencia de la custodia. Las pruebas la sobreescriben con CustodiaEnMemoria."""
    return custodia_configurada()


def obtener_auditoria_ficha() -> AuditoriaFicha:
    """Punto de enganche de la auditoría plan.leer y plan.editar. TODO(MATU-14): el adaptador real."""
    return AuditoriaFichaPendiente()


# --- Rol, persona, campo y autorización ---------------------------------------------------------------


@dataclass(frozen=True)
class FichaAutorizada:
    """El contexto de grupo y la persona, con el rol y la autorización ya verificados."""

    contexto: ContextoGrupo
    persona_id: uuid.UUID


@dataclass(frozen=True)
class CampoAutorizado:
    ficha: FichaAutorizada
    campo: CampoFicha


def _contexto_que_lee(contexto: SesionDeGrupo) -> ContextoGrupo:
    if not puede_leer(contexto.rol, contexto.puede_ver_plan):
        raise ErrorMATU(404)
    return contexto


def _contexto_que_escribe(contexto: SesionDeGrupo) -> ContextoGrupo:
    if not puede_escribir(contexto.rol):
        raise ErrorMATU(404)
    return contexto


def _uuid_o_404(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _autorizar(contexto: ContextoGrupo, persona_id: uuid.UUID, reloj: Reloj) -> FichaAutorizada:
    persona = persona_con_autorizacion(contexto.sesion, contexto.grupo_id, persona_id)
    if persona is None:
        raise ErrorMATU(404)
    estado = estado_autorizacion(persona.autorizacion, reloj.ahora())
    if estado is EstadoAutorizacion.SIN_CONSENTIMIENTO:
        raise ErrorMATU(
            403, tipo="sin-consentimiento", detalle="Falta la autorización para usar la ficha de esta persona"
        )
    if estado is EstadoAutorizacion.REVISION_VENCIDA:
        raise ErrorMATU(
            403,
            tipo="revision-vencida",
            titulo="Autorización por renovar",
            detalle="Venció la revisión anual de la autorización para usar la ficha de esta persona",
        )
    return FichaAutorizada(contexto=contexto, persona_id=persona_id)


def ficha_para_leer(
    contexto: Annotated[ContextoGrupo, Depends(_contexto_que_lee)],
    persona_id: PersonaIdRuta,
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> FichaAutorizada:
    return _autorizar(contexto, _uuid_o_404(persona_id), reloj)


def campo_para_escribir(
    contexto: Annotated[ContextoGrupo, Depends(_contexto_que_escribe)],
    persona_id: PersonaIdRuta,
    campo: CampoRuta,
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> CampoAutorizado:
    persona = _uuid_o_404(persona_id)
    campo_valido = campo_de(campo)
    if campo_valido is None:
        raise ErrorMATU(404)
    return CampoAutorizado(ficha=_autorizar(contexto, persona, reloj), campo=campo_valido)


# --- Cifrador y repositorio de la petición ---------------------------------------------------------------


def _cifrador(contexto: ContextoGrupo, custodia: CustodiaClaves | None) -> CifradorSecciones:
    if custodia is None:
        raise ErrorMATU(503, detalle="La ficha no está disponible en este momento. Cita el request_id si lo reportas")
    # Con la sesión de la petición: crear la DEK y escribir la primera sección van en la misma transacción
    return CifradorAesGcm(custodia, RepositorioClavesSQL(contexto.sesion))


def cifrador_para_leer(
    ficha: Annotated[FichaAutorizada, Depends(ficha_para_leer)],
    custodia: Annotated[CustodiaClaves | None, Depends(obtener_custodia)],
) -> CifradorSecciones:
    return _cifrador(ficha.contexto, custodia)


def cifrador_para_escribir(
    campo: Annotated[CampoAutorizado, Depends(campo_para_escribir)],
    custodia: Annotated[CustodiaClaves | None, Depends(obtener_custodia)],
) -> CifradorSecciones:
    return _cifrador(campo.ficha.contexto, custodia)


def obtener_repositorio_ficha(contexto: SesionDeGrupo) -> RepositorioFicha:
    return RepositorioFichaSQL(contexto.sesion, contexto.grupo_id)


# --- Acceso de relevo (MATU-18) ---------------------------------------------------------------------------


def acceso_para_compartir(
    contexto: Annotated[ContextoGrupo, Depends(_contexto_que_escribe)],
    persona_id: PersonaIdRuta,
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> FichaAutorizada:
    """Comparten admin y cuidador (si no, 404), con consentimiento vigente y la revisión al día (403).

    Es la misma regla que escribir la ficha: la decisión 33 vale también para compartir.
    """
    return _autorizar(contexto, _uuid_o_404(persona_id), reloj)


def persona_para_listar(
    contexto: Annotated[ContextoGrupo, Depends(_contexto_que_lee)],
    persona_id: PersonaIdRuta,
) -> FichaAutorizada:
    """Listan admin, cuidador y pagador con puede_ver_plan. No exige consentimiento (decisión 18)."""
    persona = _uuid_o_404(persona_id)
    if persona_con_autorizacion(contexto.sesion, contexto.grupo_id, persona) is None:
        raise ErrorMATU(404)
    return FichaAutorizada(contexto=contexto, persona_id=persona)


def obtener_pepper_pin() -> bytes | None:
    """El pepper del HMAC del PIN, o None si falta. Las pruebas la sobreescriben."""
    pepper = obtener_configuracion().pepper_pin
    return None if pepper is None else pepper.get_secret_value().encode("utf-8")


def huellas_para_compartir(
    autorizado: Annotated[FichaAutorizada, Depends(acceso_para_compartir)],
    pepper: Annotated[bytes | None, Depends(obtener_pepper_pin)],
) -> HuellasRelevo:
    """Sin PEPPER_PIN compartir falla cerrado con 503, después del 403 y antes del 422."""
    if pepper is None:
        raise ErrorMATU(
            503, detalle="No se puede compartir la ficha en este momento. Cita el request_id si lo reportas"
        )
    return HuellasHmac(pepper)


def obtener_generador_credenciales() -> GeneradorCredencialesRelevo:
    return GeneradorSecrets()


def obtener_repositorio_accesos(contexto: SesionDeGrupo) -> RepositorioAccesos:
    return RepositorioAccesosSQL(contexto.sesion, contexto.grupo_id)
