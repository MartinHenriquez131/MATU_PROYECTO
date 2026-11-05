"""La IP del cliente detrás del proxy de la plataforma (MATU-25, decisión 114, puntos 6 y 7).

``MiddlewareProxy`` fija ``scope["client"]`` y ``scope["scheme"]`` una sola vez, antes de la app. Así el
límite por IP (app/core/limite_ip.py), la demora de la entrada y la recuperación del acceso (MATU-38 y
MATU-57, en iam) leen ``request.client.host`` y ninguno vuelve a leer X-Forwarded-For. Lo arma
app/servidor.py; el ProxyHeadersMiddleware de Uvicorn queda apagado en el servidor, para no reescribir
dos veces.

- **Origen no confiable** (la IP del socket no está en FORWARDED_ALLOW_IPS): se ignoran
  X-Forwarded-For y X-Forwarded-Proto. Cuenta la IP del socket.
- **PROXY_SALTOS = 0** (por omisión): el comportamiento de antes, exacto. Lo resuelve el mismo
  ProxyHeadersMiddleware de Uvicorn con las mismas redes: la última IP de X-Forwarded-For que no es de
  confianza, leída de derecha a izquierda.
- **PROXY_SALTOS = N ≥ 1**: el borde de Railway agrega N IP propias a la derecha de la lista, públicas y
  que se turnan. La IP del cliente es ``xff[-(N+1)]``, la que queda justo a la izquierda de esos N saltos.
  Nunca la primera de la lista: con N=1, ``cliente, borde`` y ``falsa, cliente, borde`` cuentan las dos
  ``cliente``. Solo se valida la cola ``xff[-(N+1):]`` (el cliente y los N saltos): lo que queda a la
  izquierda lo escribe el cliente y se ignora por completo, sea lo que sea, así una basura antepuesta no
  le sirve para elegir el contador compartido del proxy. Si la lista trae menos de N+1 elementos o la
  cola trae algo que no es una IP, cuenta la IP del socket (el proxy): lo más estricto, nunca lo más
  permisivo. X-Forwarded-Proto se trata igual que en Uvicorn.
- **Diagnóstico** (DIAGNOSTICO_PROXY, temporal y apagado por omisión): una línea JSON por petición de
  origen confiable con cuántas cabeceras y cuántos elementos trae X-Forwarded-For y la clase de cada uno
  (``interna``, ``privada``, ``publica`` o ``invalida``). Nunca una IP, el X-Forwarded-For crudo, una IP
  truncada ni una huella, ni usuario_id ni grupo_id. Lleva el request_id de la petición.
"""

import ipaddress
import logging
from collections.abc import Sequence
from typing import Any, cast

from starlette.types import ASGIApp, Receive, Scope, Send
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.logs import request_id_actual

log = logging.getLogger("matu.proxy")

# Tope de PROXY_SALTOS. Railway usa 1; más de 5 saltos propios del proxy no es una configuración real
SALTOS_MAXIMOS = 5

# El espacio compartido de Railway (RFC 6598), desde donde conecta su proxy interno
RED_INTERNA = ipaddress.ip_network("100.64.0.0/10")

# El diagnóstico registra la clase de, a lo más, los primeros elementos de la lista; la cantidad, siempre
CLASES_MAXIMAS = 10

Red = ipaddress.IPv4Network | ipaddress.IPv6Network


def redes_de(valores: Sequence[str]) -> tuple[Red, ...]:
    """Las redes de FORWARDED_ALLOW_IPS ya validadas por app/servidor.py. Una IP suelta es una red /32 o /128."""
    return tuple(ipaddress.ip_network(valor, strict=False) for valor in valores)


def es_de_confianza(host: str | None, redes: Sequence[Red]) -> bool:
    """Si la IP del socket está en una de las redes. Sin socket, o con algo que no es una IP: no."""
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in red for red in redes)


def elementos_xff(valores: Sequence[bytes]) -> list[str]:
    """Los elementos de X-Forwarded-For, en orden. Varias cabeceras se leen como una sola lista unida por
    comas, igual que Uvicorn. Sin cabecera, lista vacía."""
    if not valores:
        return []
    return [parte.strip() for parte in b", ".join(valores).decode("latin-1").split(",")]


def ip_tras_saltos(elementos: Sequence[str], saltos: int) -> str | None:
    """La IP que queda justo a la izquierda de los ``saltos`` del proxy: ``elementos[-(saltos+1)]``.

    Solo se valida la cola ``elementos[-(saltos+1):]``, el cliente y los saltos. Lo que queda a la
    izquierda lo escribe el cliente y se ignora por completo: si invalidara la lista, una basura antepuesta
    le dejaría elegir el contador compartido del proxy. None si la lista trae menos de saltos+1 elementos o
    si un elemento de la cola no es una IP (también una IP con puerto o un elemento vacío): quien llama
    cuenta entonces la IP del socket. La IP vuelve normalizada, así una misma IPv6 escrita de dos formas
    cuenta una sola vez.
    """
    if saltos < 0:
        raise ValueError("saltos no puede ser negativo")
    if len(elementos) < saltos + 1:
        return None
    cola = elementos[len(elementos) - (saltos + 1) :]
    try:
        ips = [ipaddress.ip_address(elemento) for elemento in cola]
    except ValueError:
        return None
    return str(ips[0])


def clase_de(elemento: str) -> str:
    """La clase general de un elemento de X-Forwarded-For, para el diagnóstico. Nunca la IP.

    ``interna``: 100.64.0.0/10. ``publica``: una IP global. ``privada``: cualquier otra IP (redes privadas,
    loopback, enlace local, documentación, reservadas). ``invalida``: no es una IP.
    """
    try:
        ip = ipaddress.ip_address(elemento)
    except ValueError:
        return "invalida"
    if ip.version == 4 and ip in RED_INTERNA:
        return "interna"
    if ip.is_global:
        return "publica"
    return "privada"


def _fijar_esquema(scope: Scope) -> None:
    """X-Forwarded-Proto como en Uvicorn: el último valor, solo http, https, ws o wss."""
    valor: bytes | None = None
    for nombre, contenido in scope["headers"]:
        if nombre == b"x-forwarded-proto":
            valor = contenido
    if valor is None:
        return
    esquema = valor.decode("latin-1").strip()
    if esquema in {"http", "https", "ws", "wss"}:
        scope["scheme"] = esquema.replace("http", "ws") if scope["type"] == "websocket" else esquema


class MiddlewareProxy:
    """Fija la IP del cliente y el esquema desde un proxy de confianza, con PROXY_SALTOS (ver el módulo)."""

    def __init__(self, app: ASGIApp, redes: Sequence[str], saltos: int = 0, diagnostico: bool = False) -> None:
        if not 0 <= saltos <= SALTOS_MAXIMOS:
            raise ValueError(f"saltos debe estar entre 0 y {SALTOS_MAXIMOS}")
        self.app = app
        self.redes = redes_de(redes)
        self.saltos = saltos
        self.diagnostico = diagnostico
        # Con 0 saltos, el mismo middleware de Uvicorn de antes. Recibe las redes ya normalizadas, así
        # confía exactamente en los mismos orígenes que es_de_confianza. Uvicorn y Starlette tipan ASGI
        # distinto: el cast solo lo traduce
        self._uvicorn = cast(
            ASGIApp, ProxyHeadersMiddleware(cast(Any, app), trusted_hosts=[str(red) for red in self.redes])
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        socket = scope.get("client")
        if not es_de_confianza(socket[0] if socket else None, self.redes):
            # Origen no confiable: X-Forwarded-For y X-Forwarded-Proto se ignoran
            await self.app(scope, receive, send)
            return

        valores = [contenido for nombre, contenido in scope["headers"] if nombre == b"x-forwarded-for"]
        elementos = elementos_xff(valores)
        if self.saltos == 0:
            siguiente = self._uvicorn
        else:
            _fijar_esquema(scope)
            ip = ip_tras_saltos(elementos, self.saltos)
            if ip is not None:
                # Uvicorn tampoco conserva el puerto del cliente: ya no se conoce
                scope["client"] = (ip, 0)
            siguiente = self.app

        if not self.diagnostico:
            await siguiente(scope, receive, send)
            return
        # MiddlewareRequestId, más adentro, deja el request_id en este mismo diccionario
        estado = scope.setdefault("state", {})
        try:
            await siguiente(scope, receive, send)
        finally:
            self._registrar(len(valores), elementos, scope.get("client") != socket, estado.get("request_id"))

    def _registrar(self, cabeceras: int, elementos: Sequence[str], desde_xff: bool, request_id: object) -> None:
        # Solo cantidades y clases fijas: ningún texto de la cabecera llega a la línea
        token = request_id_actual.set(request_id if isinstance(request_id, str) else None)
        try:
            log.warning(
                "diagnostico_proxy",
                extra={
                    "xff_cabeceras": cabeceras,
                    "xff_elementos": len(elementos),
                    "xff_clases": [clase_de(elemento) for elemento in elementos[:CLASES_MAXIMAS]],
                    "proxy_saltos": self.saltos,
                    "ip_contada": "xff" if desde_xff else "socket",
                },
            )
        finally:
            request_id_actual.reset(token)
