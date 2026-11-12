"""«Tus datos»: GET /v1/yo/datos (MATU-54, Ley 21.719, acceso y portabilidad; decisiones 345 y 358 a 360).

- Cualquier cuenta, con solo app.usuario_id: X-Grupo-Id se ignora y no hay parámetros. Lo que se ve lo deciden las
  políticas de lo propio, no un WHERE (C1).
- Orden: 401, 503 (límite), 429 ``tope-copias`` (el mismo contador de «Datos de»), el registro de
  ``cuenta.datos_descargar`` y la copia, en una sola transacción REPEATABLE READ (C8, decisión 348).
- ``Content-Disposition: inline; filename="matu-cuenta-AAAA-MM-DD.json"`` y ``Cache-Control: no-store`` (middleware
  de /v1/yo/, repetido aquí).
- Logs: la línea de la petición lleva la ruta, el estado y el usuario. Nunca la copia (C29).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.core.limite_ip import ContadorVentana, contar_por_cuenta, obtener_contador_ventana, obtener_pepper_limites
from app.modules.iam.api.dependencias import UsuarioActual, obtener_reloj, usuario_actual
from app.modules.iam.api.esquemas_copia import CopiaDatosCuenta
from app.modules.iam.infrastructure import copia_cuenta as copia
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.copia_datos import ARCHIVO_CUENTA, AVISO_COPIA, FORMATO, LIMITE_COPIAS, content_disposition, en_chile
from app.shared.puertos import Reloj

router = APIRouter(tags=["mis-datos"])

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_NO_STORE = {"description": "no-store", "schema": {"type": "string"}}
_DISPOSICION = {
    "description": 'inline; filename="matu-cuenta-AAAA-MM-DD.json": el nombre con que la pantalla guarda el archivo',
    "schema": {"type": "string"},
}


@router.get(
    "/yo/datos",
    response_model=CopiaDatosCuenta,
    operation_id="verDatosPropios",
    summary="«Tus datos»: todo lo que MATU guarda de la propia cuenta",
    description=(
        "MATU-54 (D-54-2 a, D-54-16 a). Cualquier cuenta. La copia completa de la cuenta, para la pantalla y para el"
        " archivo (Content-Disposition inline). Nada de una persona cuidada. 10 copias por hora por cuenta, sumando"
        " «Datos de» (429 tope-copias). Registra cuenta.datos_descargar. Orden: 401, 503, 429 y 200"
    ),
    responses={
        200: {"headers": {"Cache-Control": _NO_STORE, "Content-Disposition": _DISPOSICION}},
        401: {"description": "no-autenticado o token-invalido", **_PROBLEMA},
        429: {"description": "tope-copias: 10 copias por hora por cuenta, con Retry-After", **_PROBLEMA},
        503: {"description": "Sin Redis o sin PEPPER_LIMITES: el límite falla cerrado", **_PROBLEMA},
    },
)
def ver_datos_propios(
    request: Request,
    respuesta: Response,
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    pepper: Annotated[bytes | None, Depends(obtener_pepper_limites)],
    contador: Annotated[ContadorVentana, Depends(obtener_contador_ventana)],
) -> Any:
    respuesta.headers["Cache-Control"] = "no-store"
    contar_por_cuenta(LIMITE_COPIAS, str(usuario.id), pepper, contador)
    ahora = reloj.ahora()
    with sesion_tenant(fabrica, usuario_id=usuario.id, aislamiento="REPEATABLE READ") as sesion:
        # Primero el registro, en la misma transacción: si falla, no se entrega nada (C19)
        RegistroAuditoriaSql(sesion, reloj).registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario.id,
                accion=AccionAuditoria.CUENTA_DATOS_DESCARGAR,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario.id,
                request_id=getattr(request.state, "request_id", None),
            )
        )
        ctx = copia.ContextoCopiaCuenta(sesion=sesion, usuario_id=usuario.id, ahora=ahora)
        try:
            datos_cuenta = copia.cuenta(ctx)
        except copia.CuentaNoEncontrada:
            raise ErrorMATU(401, tipo="token-invalido", headers={"WWW-Authenticate": "Bearer"}) from None
        grupos = copia.bloque_cuenta(copia.BLOQUE_GRUPOS)
        avisos = copia.bloque_cuenta(copia.BLOQUE_AVISOS)
        pagos = copia.bloque_cuenta(copia.BLOQUE_PAGOS)
        assert grupos is not None and avisos is not None
        de_avisos = avisos(ctx)
        # Los pagos al final: fijan y limpian app.grupo_id dentro de la transacción (decisión 371)
        de_pagos = None if pagos is None else pagos(ctx)
        cuerpo = CopiaDatosCuenta.model_validate(
            {
                "formato": FORMATO,
                "tipo": "cuenta",
                "generado_en": en_chile(ahora),
                "aviso": AVISO_COPIA,
                "cuenta": datos_cuenta,
                "politica": copia.politica(ctx),
                "grupos": grupos(ctx),
                "dispositivos": copia.dispositivos(ctx),
                "preferencia_avisos": de_avisos["preferencia_avisos"],
                "eventos": copia.eventos(ctx),
                "avisos_enviados": de_avisos["avisos_enviados"],
                "envio_simulado": de_avisos["envio_simulado"],
                "pagos": None if de_pagos is None else de_pagos["pagos"],
                "condiciones_aceptadas": None if de_pagos is None else de_pagos["condiciones_aceptadas"],
            }
        )
    respuesta.headers["Content-Disposition"] = content_disposition(ARCHIVO_CUENTA, ahora)
    return cuerpo
