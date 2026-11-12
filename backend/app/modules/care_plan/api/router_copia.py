"""«Datos de {nombre_pila}»: GET /v1/personas-cuidadas/{persona_id}/datos (MATU-54, Ley 21.719, acceso y portabilidad).

Contrato: docs/api/propuestos/mis-datos.openapi.yaml; decisiones 342 a 357 y 366 en adelante de docs/api/README.md.

- La piden admin y cuidador (D-54-1 a). Pagador, observador, otro grupo, una persona eliminada o con sus datos
  borrados: 404, nunca 403. No exige una autorización vigente (C3).
- Orden: 401, 404, 503 (límite), 429 ``tope-copias``, el registro de ``persona.datos_descargar`` y la copia, en una sola
  transacción REPEATABLE READ (C8, decisión 348). Si el registro falla, no se entrega nada. 503 si la ficha vigente no
  se puede descifrar porque falta la custodia o no desenvuelve la clave.
- Un solo GET para la pantalla y para el archivo (decisiones 343 y 366): ``Content-Disposition: inline`` con
  ``matu-datos-AAAA-MM-DD.json``. ``Cache-Control: no-store``, también en los errores (middleware de
  /v1/personas-cuidadas/).
- Vive en care_plan porque la ficha se descifra con la custodia de care_plan (decisión 367). Lo de care_circle se
  importa; los insumos y los pedidos llegan por el registro de bloques de care_circle (app/main.py).
- Logs: la línea de la petición lleva la plantilla de la ruta, el estado y el usuario. Nunca la copia (C29).
"""

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.core.errores import ErrorMATU
from app.core.limite_ip import ContadorVentana, contar_por_cuenta, obtener_contador_ventana, obtener_pepper_limites
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupoCoherente
from app.modules.care_circle.application.retiro import estado_autorizaciones
from app.modules.care_circle.domain.retiro import FINALIDAD_CONSUMO, FINALIDAD_PLAN_CUIDADO
from app.modules.care_circle.infrastructure import copia_datos as copia
from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL
from app.modules.care_plan.api.dependencias import PersonaIdRuta, obtener_custodia
from app.modules.care_plan.api.esquemas_copia import CopiaDatosPersona
from app.modules.care_plan.application.ports import CustodiaClaves
from app.modules.care_plan.domain.cifrado import ClaveNoDisponible, ErrorCifrado
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from app.modules.care_plan.infrastructure.copia_ficha import SinCustodia, enlaces_relevo, ficha
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.copia_datos import (
    ARCHIVO_PERSONA,
    AVISO_COPIA,
    FORMATO,
    LIMITE_COPIAS,
    content_disposition,
    en_chile,
)
from app.shared.puertos import Reloj

log = logging.getLogger("matu.care_plan.copia")

router = APIRouter(tags=["mis-datos"])

ROLES_QUE_PIDEN = frozenset({"admin", "cuidador"})

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_NO_STORE = {"description": "no-store", "schema": {"type": "string"}}
_DISPOSICION = {
    "description": 'inline; filename="matu-datos-AAAA-MM-DD.json": el nombre con que la pantalla guarda el archivo',
    "schema": {"type": "string"},
}
_DETALLE_503 = "Los datos no están disponibles en este momento. Cita el request_id si lo reportas"


def _uuid_o_404(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


@router.get(
    "/personas-cuidadas/{persona_id}/datos",
    response_model=CopiaDatosPersona,
    operation_id="verDatosPersona",
    summary="«Datos de {nombre_pila}»: todo lo que MATU guarda de la persona cuidada",
    description=(
        "MATU-54 (D-54-1 a D-54-15). Admin y cuidador. La copia completa, para la pantalla y para el archivo"
        " (Content-Disposition inline). Sin la autorización vigente, la ficha y los insumos van solo con su estado."
        " 10 copias por hora por cuenta (429 tope-copias). Registra persona.datos_descargar. Orden: 401, 404, 503, 429"
        " y 200"
    ),
    responses={
        200: {"headers": {"Cache-Control": _NO_STORE, "Content-Disposition": _DISPOSICION}},
        401: {"description": "no-autenticado o token-invalido", **_PROBLEMA},
        404: {"description": "Sin grupo, rol pagador u observador, o persona de otro grupo o borrada", **_PROBLEMA},
        429: {"description": "tope-copias: 10 copias por hora por cuenta, con Retry-After", **_PROBLEMA},
        503: {"description": "Sin Redis o PEPPER_LIMITES, o la ficha vigente no se puede abrir", **_PROBLEMA},
    },
)
def ver_datos_persona(
    request: Request,
    respuesta: Response,
    contexto: SesionDeGrupoCoherente,
    persona_id: PersonaIdRuta,
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    custodia: Annotated[CustodiaClaves | None, Depends(obtener_custodia)],
    pepper: Annotated[bytes | None, Depends(obtener_pepper_limites)],
    contador: Annotated[ContadorVentana, Depends(obtener_contador_ventana)],
) -> Any:
    respuesta.headers["Cache-Control"] = "no-store"
    if contexto.rol not in ROLES_QUE_PIDEN:
        raise ErrorMATU(404)
    persona_uuid = _uuid_o_404(persona_id)
    persona = copia.persona_de_la_copia(contexto.sesion, contexto.grupo_id, persona_uuid)
    if persona is None:
        raise ErrorMATU(404)
    contar_por_cuenta(LIMITE_COPIAS, str(contexto.usuario_id), pepper, contador)

    ahora = reloj.ahora()
    registro = RegistroAuditoriaSql(contexto.sesion, reloj)
    # Primero el registro, en la misma transacción: si falla, no se entrega nada (C19)
    registro.registrar(
        EntradaAuditoria(
            grupo_id=contexto.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=contexto.usuario_id,
            accion=AccionAuditoria.PERSONA_DATOS_DESCARGAR,
            entidad=EntidadAuditoria.PERSONA_CUIDADA,
            entidad_id=persona_uuid,
            request_id=getattr(request.state, "request_id", None),
            persona_cuidada_id=persona_uuid,
        )
    )
    cuerpo = _armar(contexto, persona_uuid, persona, reloj, custodia, ahora, registro)
    respuesta.headers["Content-Disposition"] = content_disposition(ARCHIVO_PERSONA, ahora)
    return cuerpo


def _armar(
    contexto: ContextoGrupo,
    persona_id: uuid.UUID,
    persona: copia.PersonaDeLaCopia,
    reloj: Reloj,
    custodia: CustodiaClaves | None,
    ahora: Any,
    registro: RegistroAuditoriaSql,
) -> CopiaDatosPersona:
    retiros = RepositorioRetirosSQL(contexto.sesion, contexto.grupo_id, registro)
    estados = {
        e.finalidad: e
        for e in estado_autorizaciones(persona_id, reloj, retiros, (FINALIDAD_PLAN_CUIDADO, FINALIDAD_CONSUMO))
    }
    ctx = copia.ContextoCopia(
        sesion=contexto.sesion,
        grupo_id=contexto.grupo_id,
        persona_id=persona_id,
        usuario_id=contexto.usuario_id,
        rol=contexto.rol,
        ahora=ahora,
        estado_ficha=estados[FINALIDAD_PLAN_CUIDADO],
        estado_insumos=estados[FINALIDAD_CONSUMO],
    )
    cifrador = None if custodia is None else CifradorAesGcm(custodia, RepositorioClavesSQL(contexto.sesion))
    try:
        bloque_ficha = ficha(ctx, cifrador)
    except SinCustodia:
        log.error("la custodia no está configurada: la copia con la ficha vigente falla cerrada")
        raise ErrorMATU(503, detalle=_DETALLE_503) from None
    except ClaveNoDisponible:
        log.warning("la ficha no se pudo descifrar para la copia", extra={"tipo_error": "ClaveNoDisponible"})
        raise ErrorMATU(503, detalle=_DETALLE_503) from None
    except ErrorCifrado as error:
        log.warning("la ficha no se pudo descifrar para la copia", extra={"tipo_error": type(error).__name__})
        raise ErrorMATU(500, detalle="No pudimos armar la copia. Cita el request_id si lo reportas") from None
    insumos = copia.bloque(copia.BLOQUE_INSUMOS)
    assert insumos is not None
    pedidos = copia.bloque(copia.BLOQUE_PEDIDOS)
    return CopiaDatosPersona.model_validate(
        {
            "formato": FORMATO,
            "tipo": "persona_cuidada",
            "generado_en": en_chile(ahora),
            "aviso": AVISO_COPIA,
            "persona": persona.datos,
            "autorizaciones": copia.autorizaciones(ctx),
            "ficha": bloque_ficha,
            "enlaces_relevo": enlaces_relevo(ctx, ahora),
            "insumos": insumos(ctx),
            "pedidos": None if pedidos is None else pedidos(ctx),
            "historial": copia.historial(ctx),
        }
    )
