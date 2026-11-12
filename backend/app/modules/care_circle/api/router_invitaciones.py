"""Invitar a alguien al grupo y lo que usa la persona invitada (MATU-42 y MATU-53, RF-38).
Contrato: docs/api/propuestos/invitar-familiar.openapi.yaml.

Del grupo, solo admin (los demás roles, 404):

    POST   /v1/grupos/{grupo_id}/invitaciones                   crea; url y codigo salen una sola vez
    GET    /v1/grupos/{grupo_id}/invitaciones                   las sin usar
    DELETE /v1/grupos/{grupo_id}/invitaciones/{invitacion_id}   anula

De la persona invitada, sin X-Grupo-Id (el grupo sale del token):

    POST /v1/invitaciones/presentacion   sin sesión: quién invita, el rol y el vencimiento. 30 por hora por IP
    POST /v1/invitaciones/verificacion   sin sesión, con el código. 20 por hora por IP (contador de canje)
    POST /v1/invitaciones/aceptacion     con sesión, token y código otra vez: se une. El mismo contador de canje

Un código incorrecto y el bloqueo vuelven como resultado: la transacción confirma el intento y la auditoría y recién
después se responde 422 o 423, como el canje del relevo. El token, el código, sus huellas y la IP nunca van a un log, a
un error ni a la auditoría (C24). Las cabeceras no-store, no-referrer y noindex de /v1/invitaciones/ las pone
app.main (C23).
"""

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request, Response, status
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.core.limite_ip import (
    DETALLE_503,
    RESPUESTAS_LIMITE,
    ContadorNoDisponible,
    ContadorVentana,
    clave_de,
    limite_por_ip,
    obtener_contador_ventana,
    obtener_pepper_limites,
)
from app.modules.care_circle.api.dependencias_grupo import ActorAdmin, PepperCodigo, PuertosDelGrupo
from app.modules.care_circle.api.esquemas_grupo import (
    InvitacionCreada,
    InvitacionVista,
    InvitadaPor,
    ListaInvitaciones,
    PresentacionInvitacion,
    SolicitudCanjeInvitacion,
    SolicitudInvitacion,
    SolicitudPresentacionInvitacion,
    Union,
    VerificacionInvitacion,
)
from app.modules.care_circle.application.invitaciones import (
    CodigoNoVerificable,
    InvitacionCerrada,
    NoEncontrado,
    aceptar,
    anular_invitacion,
    crear_invitacion,
    listar_invitaciones,
    presentar,
    verificar,
)
from app.modules.care_circle.domain.grupos import ve_el_plan
from app.modules.care_circle.domain.invitaciones import (
    TIPO_410,
    TOPE_INVITACIONES,
    VENTANA_TOPE,
    ResultadoCanje,
    tope_superado,
    url_invitacion,
)
from app.modules.care_circle.infrastructure.canje_invitaciones import CanjeInvitacionesSQL
from app.modules.care_circle.infrastructure.credenciales_invitacion import CredencialesInvitacionHmac, huella_de_texto
from app.modules.iam.api.dependencias import UsuarioActual, obtener_reloj, usuario_actual
from app.shared.limite_ip import (
    LIMITE_CANJE_INVITACION,
    LIMITE_PRESENTACION_INVITACION,
    LimitePorIp,
    huella,
    retry_after,
)
from app.shared.puertos import Reloj

log = logging.getLogger("matu.care_circle.invitaciones")

router = APIRouter(tags=["invitaciones"])
router_publico = APIRouter(prefix="/invitaciones", tags=["invitacion-publica"])

# C31, P9: 20 por admin y grupo en 24 horas, con la huella HMAC de la cuenta y el grupo
TOPE = LimitePorIp("invitaciones-admin", TOPE_INVITACIONES, VENTANA_TOPE)

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_404: dict[int | str, dict[str, Any]] = {
    401: {"description": "no-autenticado o token-invalido", **_PROBLEMA},
    404: {"description": "Grupo ajeno, rol que no es admin o invitación inexistente o de otro grupo", **_PROBLEMA},
}
_EXITO: dict[str, Any] = {
    "headers": {"Cache-Control": {"description": "no-store", "schema": {"type": "string"}}}
}
_DE_LA_INVITACION: dict[int | str, dict[str, Any]] = {
    410: {"description": "invitacion-no-disponible, invitacion-usada o invitacion-vencida", **_PROBLEMA},
    422: {"description": "Cuerpo inválido (no cuenta como intento), o codigo-incorrecto", **_PROBLEMA},
    423: {"description": "invitacion-bloqueada por 5 códigos incorrectos", **_PROBLEMA},
}

_TEXTOS_410: dict[ResultadoCanje, str] = {
    ResultadoCanje.NO_DISPONIBLE: "Esta invitación no sirve. Pide una nueva a quien te invitó",
    ResultadoCanje.USADA: "Esta invitación ya se usó. Pide una nueva a quien te invitó",
    ResultadoCanje.VENCIDA: "Esta invitación venció. Pide una nueva a quien te invitó",
}

Fabrica = Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)]
RelojDep = Annotated[Reloj, Depends(obtener_reloj)]


def _sin_servicio() -> ErrorMATU:
    return ErrorMATU(503, detalle=DETALLE_503)


def _id_de(valor: str) -> uuid.UUID:
    try:
        return uuid.UUID(valor)
    except ValueError:
        raise ErrorMATU(404) from None


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


# --- Del grupo -----------------------------------------------------------------------------------------


@router.post(
    "/grupos/{grupo_id}/invitaciones",
    status_code=status.HTTP_201_CREATED,
    response_model=InvitacionCreada,
    operation_id="crearInvitacion",
    responses={
        201: _EXITO,
        **_404,
        422: {"description": "Cuerpo inválido", **_PROBLEMA},
        429: {"description": "tope-invitaciones: 20 por admin y grupo en 24 horas, con Retry-After", **_PROBLEMA},
        503: {"description": "Sin Redis, sin PEPPER_LIMITES o sin PEPPER_PIN. No se creó nada", **_PROBLEMA},
    },
    summary="Crear una invitación con un rol",
    description=(
        "MATU-42 (decisiones 294 a 297). Solo admin. Vence a los 7 días. url y codigo salen una sola vez. Sin"
        " Idempotency-Key. Registra invitacion.crear con el rol."
    ),
)
def crear(
    solicitud: SolicitudInvitacion,
    actor: ActorAdmin,
    puertos: PuertosDelGrupo,
    reloj: RelojDep,
    pepper_codigo: PepperCodigo,
    pepper_limites: Annotated[bytes | None, Depends(obtener_pepper_limites)],
    contador: Annotated[ContadorVentana, Depends(obtener_contador_ventana)],
) -> InvitacionCreada:
    if pepper_limites is None:
        log.error("falta PEPPER_LIMITES: crear invitaciones falla cerrado")
        raise _sin_servicio()
    clave = clave_de(TOPE, huella(pepper_limites, TOPE.prefijo, f"{actor.usuario_id}:{actor.grupo_id}"))
    try:
        conteo = contador.sumar(clave, TOPE.ventana_segundos)
    except ContadorNoDisponible:
        log.error("Redis no responde: crear invitaciones falla cerrado")
        raise _sin_servicio() from None
    if tope_superado(conteo.conteo):
        raise ErrorMATU(
            429,
            tipo="tope-invitaciones",
            detalle="Ya creaste muchas invitaciones hoy. Anula las que no uses o espera",
            headers={"Retry-After": str(retry_after(conteo.ttl_segundos, TOPE))},
        )
    if pepper_codigo is None:
        log.error("falta PEPPER_PIN: crear invitaciones falla cerrado")
        raise _sin_servicio()
    try:
        creada = crear_invitacion(
            solicitud.rol, actor, puertos.invitaciones, CredencialesInvitacionHmac(pepper_codigo), reloj
        )
    except NoEncontrado:
        raise ErrorMATU(404) from None
    return InvitacionCreada(
        id=creada.id,
        rol=solicitud.rol,
        url=url_invitacion(obtener_configuracion().origen_web, creada.token),
        codigo=creada.codigo,
        creada_en=creada.creada_en,
        expira_en=creada.expira_en,
    )


@router.get(
    "/grupos/{grupo_id}/invitaciones",
    response_model=ListaInvitaciones,
    operation_id="listarInvitaciones",
    responses={200: _EXITO, **_404},
    summary="Ver las invitaciones sin usar",
    description="MATU-42 (C10, P7). Solo admin. Pendientes y bloqueadas, de la más nueva a la más antigua.",
)
def listar(actor: ActorAdmin, puertos: PuertosDelGrupo, reloj: RelojDep) -> ListaInvitaciones:
    vistas = [
        InvitacionVista(
            id=i.id,
            rol=i.rol,  # type: ignore[arg-type]
            estado=e.value,  # type: ignore[arg-type]
            creada_en=i.creada_en,
            expira_en=i.vida.expira_en,
            invitada_por=InvitadaPor(
                nombre=i.nombre_pila_invita if i.autor_activo else None,
                autor_activo=i.autor_activo,
                eres_tu=i.invitado_por == actor.usuario_id,
            ),
        )
        for i, e in listar_invitaciones(actor, puertos.invitaciones, reloj.ahora())
    ]
    return ListaInvitaciones(invitaciones=vistas)


@router.delete(
    "/grupos/{grupo_id}/invitaciones/{invitacion_id}",
    operation_id="anularInvitacion",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        204: _EXITO,
        **_404,
        409: {"description": "invitacion-cerrada: ya se usó o venció, con estado", **_PROBLEMA},
    },
    summary="Anular una invitación",
    description="MATU-42 (decisión 308). Solo admin. Pendiente o bloqueada: 204 e invitacion.anular. Ya anulada: 204.",
)
def anular(
    actor: ActorAdmin,
    puertos: PuertosDelGrupo,
    reloj: RelojDep,
    invitacion_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
) -> Response:
    try:
        anular_invitacion(_id_de(invitacion_id), actor, puertos.invitaciones, reloj)
    except NoEncontrado:
        raise ErrorMATU(404) from None
    except InvitacionCerrada as error:
        raise ErrorMATU(
            409,
            tipo="invitacion-cerrada",
            detalle="Esta invitación ya no se puede anular",
            extension={"estado": error.estado.value},
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- La persona invitada -------------------------------------------------------------------------------


def _no_sirve(resultado: ResultadoCanje, nombre_pila_invita: str | None) -> ErrorMATU | None:
    """El 410 o el 423 del resultado, o None si no es uno de ellos."""
    if resultado in TIPO_410:
        return ErrorMATU(410, tipo=TIPO_410[resultado], detalle=_TEXTOS_410[resultado])
    if resultado is ResultadoCanje.BLOQUEADA:
        return ErrorMATU(
            423,
            tipo="invitacion-bloqueada",
            detalle="La invitación se bloqueó por código incorrecto. Pide una nueva",
            extension={"nombre_pila_invita": nombre_pila_invita or ""},
        )
    return None


def _codigo_incorrecto(restantes: int | None) -> ErrorMATU:
    return ErrorMATU(
        422,
        tipo="codigo-incorrecto",
        titulo="Código incorrecto",
        detalle="El código no coincide",
        extension={"intentos_restantes": restantes},
    )


@router_publico.post(
    "/presentacion",
    response_model=PresentacionInvitacion,
    operation_id="presentarInvitacion",
    dependencies=[Depends(limite_por_ip(LIMITE_PRESENTACION_INVITACION))],
    responses={
        200: _EXITO,
        410: _DE_LA_INVITACION[410],
        422: {"description": "Cuerpo inválido", **_PROBLEMA},
        423: _DE_LA_INVITACION[423],
        **RESPUESTAS_LIMITE,
    },
    summary="Saber quién invita y para qué rol, antes del código",
    description="MATU-42 (C1, D-42-4 a, P2). Sin sesión. No cuenta como intento, no cambia nada y no se audita.",
)
def presentar_invitacion(
    solicitud: SolicitudPresentacionInvitacion, fabrica: Fabrica, reloj: RelojDep
) -> PresentacionInvitacion:
    with sesion_tenant(fabrica) as sesion:
        vista = presentar(huella_de_texto(solicitud.token), CanjeInvitacionesSQL(sesion), reloj)
    error = _no_sirve(vista.resultado, vista.nombre_pila_invita)
    if error is not None:
        raise error
    assert vista.nombre_pila_invita is not None and vista.rol is not None and vista.expira_en is not None
    return PresentacionInvitacion(
        nombre_pila_invita=vista.nombre_pila_invita,
        rol=vista.rol,  # type: ignore[arg-type]
        expira_en=vista.expira_en,
    )


@router_publico.post(
    "/verificacion",
    response_model=VerificacionInvitacion,
    operation_id="verificarCodigoInvitacion",
    dependencies=[Depends(limite_por_ip(LIMITE_CANJE_INVITACION))],
    responses={200: _EXITO, **_DE_LA_INVITACION, **RESPUESTAS_LIMITE},
    summary="Verificar el código y ver a qué grupo se une, antes de pedir la cuenta",
    description=(
        "MATU-42 (P1, P3, C30). Sin sesión. No une a nadie. El 5.º código incorrecto bloquea. Registra"
        " invitacion.codigo_incorrecto e invitacion.bloqueo con actor sistema."
    ),
)
def verificar_invitacion(
    request: Request,
    solicitud: SolicitudCanjeInvitacion,
    fabrica: Fabrica,
    reloj: RelojDep,
    pepper_codigo: PepperCodigo,
) -> VerificacionInvitacion:
    credenciales = None if pepper_codigo is None else CredencialesInvitacionHmac(pepper_codigo)
    try:
        with sesion_tenant(fabrica) as sesion:
            vista = verificar(
                huella_de_texto(solicitud.token), solicitud.codigo, CanjeInvitacionesSQL(sesion), credenciales, reloj,
                _request_id(request),
            )
    except CodigoNoVerificable:
        log.error("falta PEPPER_PIN: la verificación de la invitación falla cerrado")
        raise _sin_servicio() from None
    # La transacción ya confirmó el intento y la auditoría
    error = _no_sirve(vista.resultado, vista.nombre_pila_invita)
    if error is not None:
        raise error
    if vista.resultado is ResultadoCanje.CODIGO_INCORRECTO:
        raise _codigo_incorrecto(vista.intentos_restantes)
    assert vista.nombre_pila_invita is not None and vista.grupo is not None and vista.expira_en is not None
    return VerificacionInvitacion(
        nombre_pila_invita=vista.nombre_pila_invita,
        grupo=vista.grupo,
        personas=list(vista.personas),
        rol=vista.rol,  # type: ignore[arg-type]
        expira_en=vista.expira_en,
    )


@router_publico.post(
    "/aceptacion",
    status_code=status.HTTP_201_CREATED,
    response_model=Union,
    operation_id="aceptarInvitacion",
    # Antes de todo, la sesión (401); después, el mismo contador de canje que la verificación
    dependencies=[Depends(usuario_actual), Depends(limite_por_ip(LIMITE_CANJE_INVITACION))],
    responses={
        201: _EXITO,
        401: {"description": "Sin sesión o con un access token inválido", **_PROBLEMA},
        409: {"description": "ya-eres-parte, con grupo_id. No consume la invitación", **_PROBLEMA},
        **_DE_LA_INVITACION,
        **RESPUESTAS_LIMITE,
    },
    summary="Unirse al grupo con la invitación y el código",
    description=(
        "MATU-42 (C22, C27). Con sesión y sin X-Grupo-Id. Un solo uso. Inserta la membresía activa con el rol de la"
        " invitación y registra invitacion.aceptar con la cuenta. No crea ni copia autorizaciones (C7)."
    ),
)
def aceptar_invitacion(
    request: Request,
    solicitud: SolicitudCanjeInvitacion,
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    fabrica: Fabrica,
    reloj: RelojDep,
    pepper_codigo: PepperCodigo,
) -> Union:
    credenciales = None if pepper_codigo is None else CredencialesInvitacionHmac(pepper_codigo)
    try:
        with sesion_tenant(fabrica, usuario_id=usuario.id) as sesion:
            union = aceptar(
                huella_de_texto(solicitud.token), solicitud.codigo, CanjeInvitacionesSQL(sesion), credenciales, reloj,
                _request_id(request),
            )
    except CodigoNoVerificable:
        log.error("falta PEPPER_PIN: la aceptación de la invitación falla cerrado")
        raise _sin_servicio() from None
    if union.resultado is ResultadoCanje.YA_ERES_PARTE:
        raise ErrorMATU(
            409,
            tipo="ya-eres-parte",
            detalle="Ya eres parte de este grupo",
            extension={"grupo_id": str(union.grupo_id)},
        )
    error = _no_sirve(union.resultado, union.nombre_pila_invita)
    if error is not None:
        raise error
    if union.resultado is ResultadoCanje.CODIGO_INCORRECTO:
        raise _codigo_incorrecto(union.intentos_restantes)
    assert union.grupo_id is not None and union.membresia_id is not None and union.rol is not None
    return Union(
        grupo_id=union.grupo_id,
        membresia_id=union.membresia_id,
        grupo=union.grupo or "",
        rol=union.rol,  # type: ignore[arg-type]
        puede_ver_plan=ve_el_plan(union.rol, False),
    )
