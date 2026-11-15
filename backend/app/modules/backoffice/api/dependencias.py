"""Las puertas del comercio y de operación (MATU-63; arquitectura 11.2; D-63-2, D-63-5 y D-63-14).

- sesion_de_comercio: la cuenta entra por /v1/sesiones como cualquier otra (O1). Si tiene una cuenta activa en un
  comercio activo, la sesión fija app.usuario_id y app.comercio_id, nunca app.grupo_id (D-63-14). Sin cuenta de
  comercio: 404, como si la ruta no existiera para ella. Con la cuenta o el comercio inactivos: 403 comercio-inactivo.
- operador: la cuenta con usuario.es_operacion. Las rutas de operación abren sus transacciones con app.rol =
  'operacion' y sin cuenta, como pide el trigger pedido_escritura_del_pago. Otra cuenta: 404.
  [PENDIENTE: MFA de operación (arquitectura 11.6), con la pantalla de MATU-81]
- el secreto del código (CODIGO_RETIRO_SECRETO) y el límite por cuenta de comercio en Redis (D-63-4).
"""

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.core.errores import ErrorMATU
from app.core.limite_ip import (
    DETALLE_503,
    ContadorNoDisponible,
    ContadorVentana,
    clave_de,
    obtener_contador_ventana,
    obtener_pepper_limites,
)
from app.modules.iam.api.dependencias import UsuarioActual, usuario_actual
from app.shared.limite_ip import LimitePorIp, excedido, huella, retry_after

log = logging.getLogger("matu.backoffice")

_CUENTA_COMERCIO = text(
    "SELECT uc.comercio_id, uc.activo, c.id IS NOT NULL AS comercio_activo FROM usuario_comercio uc"
    " LEFT JOIN comercio c ON c.id = uc.comercio_id AND c.estado = 'activo'"
    " WHERE uc.usuario_id = app_usuario() ORDER BY uc.activo DESC, uc.comercio_id"
)
_ES_OPERACION = text("SELECT es_operacion FROM usuario WHERE id = app_usuario() AND estado = 'activo'")

# D-63-4: intentos de código por cuenta de comercio, en una ventana fija de una hora
LIMITE_CODIGO_COMERCIO = LimitePorIp("codigo-comercio", 20)


@dataclass(frozen=True)
class ContextoComercio:
    usuario_id: uuid.UUID
    comercio_id: uuid.UUID
    sesion: Session


def comercio_de_la_cuenta(fabrica: sessionmaker[Session], usuario_id: uuid.UUID) -> uuid.UUID | None:
    """El comercio activo de la cuenta. None si no es de un comercio; ErrorMATU 403 si su cuenta o su comercio no
    están activos."""
    with sesion_tenant(fabrica, usuario_id=usuario_id) as sesion:
        fila = sesion.execute(_CUENTA_COMERCIO).first()
    if fila is None:
        return None
    if not fila.activo or not fila.comercio_activo:
        raise ErrorMATU(
            403,
            tipo="comercio-inactivo",
            detalle="Tu cuenta de comercio no está activa en MATU. Avisa a MATU",
        )
    return uuid.UUID(str(fila.comercio_id))


def sesion_de_comercio(
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
) -> Iterator[ContextoComercio]:
    comercio_id = comercio_de_la_cuenta(fabrica, usuario.id)
    if comercio_id is None:
        raise ErrorMATU(404)
    with sesion_tenant(fabrica, usuario_id=usuario.id, comercio_id=comercio_id) as sesion:
        yield ContextoComercio(usuario.id, comercio_id, sesion)


SesionDeComercio = Annotated[ContextoComercio, Depends(sesion_de_comercio, scope="function")]


def operador(
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
) -> uuid.UUID:
    with sesion_tenant(fabrica, usuario_id=usuario.id) as sesion:
        es = sesion.execute(_ES_OPERACION).scalar()
    if not es:
        raise ErrorMATU(404)
    return usuario.id


Operador = Annotated[uuid.UUID, Depends(operador)]


def obtener_secreto_codigo() -> bytes | None:
    """CODIGO_RETIRO_SECRETO, o None (generar y validar responden 503). Las pruebas lo sobreescriben."""
    secreto = obtener_configuracion().codigo_retiro_secreto
    return None if secreto is None else secreto.get_secret_value().encode("utf-8")


def secreto_codigo(secreto: Annotated[bytes | None, Depends(obtener_secreto_codigo)]) -> bytes:
    if secreto is None:
        log.error("falta CODIGO_RETIRO_SECRETO: el código de retiro falla cerrado")
        raise ErrorMATU(503, detalle=DETALLE_503)
    return secreto


SecretoCodigo = Annotated[bytes, Depends(secreto_codigo)]


def contar_intento_de_codigo(
    usuario_id: uuid.UUID, pepper: bytes | None, contador: ContadorVentana, limite: LimitePorIp = LIMITE_CODIGO_COMERCIO
) -> None:
    """Suma un intento de la cuenta del comercio. 503 sin PEPPER_LIMITES o sin Redis (falla cerrado); 429 con
    Retry-After si pasó del tope. La clave es la huella HMAC de la cuenta: el id no llega a Redis."""
    if pepper is None:
        raise ErrorMATU(503, detalle=DETALLE_503)
    clave = clave_de(limite, huella(pepper, limite.prefijo, str(usuario_id)))
    try:
        resultado = contador.sumar(clave, limite.ventana_segundos)
    except ContadorNoDisponible:
        raise ErrorMATU(503, detalle=DETALLE_503) from None
    if excedido(resultado.conteo, limite):
        raise ErrorMATU(
            429,
            tipo="demasiados-intentos",
            detalle="Hubo muchos intentos con códigos en poco tiempo",
            headers={"Retry-After": str(retry_after(resultado.ttl_segundos, limite))},
        )


PepperLimites = Annotated[bytes | None, Depends(obtener_pepper_limites)]
Contador = Annotated[ContadorVentana, Depends(obtener_contador_ventana)]
