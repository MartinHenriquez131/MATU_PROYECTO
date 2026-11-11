"""La vuelta de Webpay (MATU-62; decisiones 231 a 235 y 241). **No se apaga con la capa 3** (D-62-17): app/main.py la
monta siempre que el paquete exista (ROUTERS_PAGO_SIEMPRE).

    POST /v1/pagos/retorno        pública; la sesión es opcional. 200 o 404
    POST /insumos/pedido/pago     fuera de /v1 y de openapi.json: Transbank vuelve por POST; 303 a la pantalla

La app llama a POST /v1/pagos/retorno desde la pantalla /insumos/pedido/pago (la return_url), con lo que trajo la
dirección y **después de borrarlo** con history.replaceState. Nunca responde 401: un token de acceso inválido cuenta
como «sin sesión». Con la sesión de un admin, cuidador o pagador del grupo del pedido, suma grupo_id,
persona_cuidada_id y pedido_id; si no, van en null.

Logs (decisión 235): ni el cuerpo, ni el buy_order, ni el token, ni la respuesta de Transbank. La línea de la petición
lleva la plantilla, el estado y ``caso`` (commit, repetido, usuario_salio, formulario_vencido o desconocido).
"""

import re
import uuid
from datetime import timedelta
from typing import Annotated, Any
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.modules.care_circle.infrastructure.membresia import membresia_activa
from app.modules.iam.api.dependencias import obtener_emisor_tokens, obtener_reloj
from app.modules.iam.application.ports import EmisorTokens
from app.modules.iam.application.sesion import leer_acceso
from app.modules.iam.domain.sesion import TokenInvalido
from app.modules.payments.api.esquemas import ResultadoRetorno, SolicitudRetorno
from app.modules.payments.application import retorno as casos
from app.modules.payments.application.ports import AbrirGrupo, PasarelaWebpay, ResolverVenta
from app.modules.payments.application.retorno import VentaDesconocida, Vuelta
from app.modules.payments.domain.venta import CasoRetorno
from app.modules.payments.infrastructure.pasarela import RUTA_RETORNO, obtener_pasarela
from app.modules.payments.infrastructure.sistema import AbrirGrupoSQL, ResolverVentaSQL
from app.shared.puertos import Reloj

router = APIRouter(tags=["retorno"])
router_formulario = APIRouter()

ROLES_CON_CONTEXTO = frozenset({"admin", "cuidador", "pagador"})

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}

_bearer_opcional = HTTPBearer(auto_error=False)


def obtener_resolver(fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)]) -> ResolverVenta:
    return ResolverVentaSQL(fabrica)


def obtener_abrir_grupo(
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> AbrirGrupo:
    return AbrirGrupoSQL(fabrica, reloj)


def usuario_opcional(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_opcional)],
    emisor: Annotated[EmisorTokens, Depends(obtener_emisor_tokens)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> uuid.UUID | None:
    """La cuenta de la sesión, o None. Un token inválido o vencido cuenta como sin sesión: la vuelta no responde 401."""
    if credenciales is None:
        return None
    try:
        return leer_acceso(credenciales.credentials, emisor, reloj).sub
    except TokenInvalido:
        return None


def _con_contexto(
    fabrica: sessionmaker[Session], usuario_id: uuid.UUID | None, grupo_id: uuid.UUID
) -> bool:
    if usuario_id is None:
        return False
    with sesion_tenant(fabrica, usuario_id=usuario_id, grupo_id=grupo_id) as sesion:
        membresia = membresia_activa(sesion, usuario_id, grupo_id)
    return membresia is not None and membresia.rol in ROLES_CON_CONTEXTO


@router.post(
    "/pagos/retorno",
    response_model=ResultadoRetorno,
    responses={
        404: {"description": "Los valores no son de ninguna venta de MATU", **_PROBLEMA},
        422: {"description": "No trae ninguno de los cuatro campos, o uno no tiene la forma de Transbank", **_PROBLEMA},
    },
    openapi_extra={"security": [{}, {"HTTPBearer": []}]},
    summary="La vuelta de Webpay que manda la app; hace el commit y responde el resultado",
    description=(
        "MATU-62 (decisiones 231 a 235). Pública e idempotente por token; la sesión es opcional y la vuelta nunca"
        " responde 401. token_ws de una venta iniciada: commit. Retorno repetido: no llama a Transbank (ya_registrado)."
        " TBK_TOKEN: sin commit, status y abandonado. Solo TBK_ORDEN_COMPRA y TBK_ID_SESION: tiempo_agotado. Valores"
        " que"
        " no son de MATU: 404. Sin montos ni tarjeta. No se apaga con la capa 3 (decisión 241)"
    ),
)
def retorno(
    request: Request,
    response: Response,
    solicitud: SolicitudRetorno,
    resolver: Annotated[ResolverVenta, Depends(obtener_resolver)],
    abrir: Annotated[AbrirGrupo, Depends(obtener_abrir_grupo)],
    pasarela: Annotated[PasarelaWebpay | None, Depends(obtener_pasarela)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    usuario_id: Annotated[uuid.UUID | None, Depends(usuario_opcional)],
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
) -> ResultadoRetorno:
    vuelta = Vuelta(
        token_ws=solicitud.token_ws,
        tbk_token=solicitud.tbk_token,
        tbk_orden_compra=solicitud.tbk_orden_compra,
        tbk_id_sesion=solicitud.tbk_id_sesion,
    )
    vida = timedelta(minutes=obtener_configuracion().vida_venta_webpay_minutos)
    try:
        resultado = casos.procesar(vuelta, resolver, abrir, pasarela, reloj.ahora(), vida)
    except VentaDesconocida:
        request.state.caso = CasoRetorno.DESCONOCIDO.value
        raise ErrorMATU(404) from None
    request.state.caso = resultado.caso.value
    response.headers["Cache-Control"] = "no-store"
    contexto = _con_contexto(fabrica, usuario_id, resultado.grupo_id)
    return ResultadoRetorno(
        resultado=resultado.resultado.value,  # type: ignore[arg-type]
        ya_registrado=resultado.ya_registrado,
        anulacion=None if resultado.anulacion is None else resultado.anulacion.value,
        volver_a_preguntar_en=resultado.volver_a_preguntar_en,
        grupo_id=resultado.grupo_id if contexto else None,
        persona_cuidada_id=resultado.persona_id if contexto else None,
        pedido_id=resultado.pedido_id if contexto else None,
    )


# --- POST /insumos/pedido/pago: Transbank vuelve por POST a la return_url (decisión 231) ---------------------------

# Los cuatro campos de Transbank, con su largo máximo. Cualquier otro campo o valor se descarta
CAMPOS_FORMULARIO: dict[str, int] = {"token_ws": 128, "TBK_TOKEN": 128, "TBK_ORDEN_COMPRA": 26, "TBK_ID_SESION": 61}
_VALOR = re.compile(r"^[A-Za-z0-9_-]+$")
# Lo que se lee del cuerpo como mucho: los cuatro campos caben de sobra
TOPE_CUERPO = 4096

CABECERAS_VUELTA = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


def fragmento_de(cuerpo: bytes) -> str:
    """Los campos de Transbank válidos del formulario, como fragmento (#campo=valor&...). Vacío si no hay ninguno."""
    try:
        campos = parse_qs(cuerpo[:TOPE_CUERPO].decode("ascii"), keep_blank_values=False, max_num_fields=20)
    except (UnicodeDecodeError, ValueError):
        return ""
    validos: list[tuple[str, str]] = []
    for nombre, largo in CAMPOS_FORMULARIO.items():
        valores = campos.get(nombre)
        if valores and len(valores) == 1 and len(valores[0]) <= largo and _VALOR.match(valores[0]):
            validos.append((nombre, valores[0]))
    return "#" + urlencode(validos) if validos else ""



@router_formulario.post(RUTA_RETORNO, include_in_schema=False, status_code=303)
async def retorno_por_formulario(request: Request) -> Response:
    """No llama a Transbank ni escribe nada: el commit lo hace POST /v1/pagos/retorno. No registra el cuerpo. No se
    apaga con la capa 3."""
    cuerpo = b""
    async for parte in request.stream():
        cuerpo += parte
        if len(cuerpo) > TOPE_CUERPO:
            break
    return Response(status_code=303, headers={"Location": RUTA_RETORNO + fragmento_de(cuerpo), **CABECERAS_VUELTA})
