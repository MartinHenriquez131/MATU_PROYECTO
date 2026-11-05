"""Arranque de la API detrás de un proxy, en staging (MATU-25, decisión 114, puntos 6 y 7).

Ejecutar desde backend/:

    python -m app.servidor

Lee del entorno:

- PORT: el puerto que asigna la plataforma (Railway). Por omisión 8000.
- FORWARDED_ALLOW_IPS: las IP o redes (CIDR), separadas por comas, desde donde conecta el proxy de
  confianza. Solo de ellas se acepta X-Forwarded-For y X-Forwarded-Proto. Por omisión 127.0.0.1, que
  en un contenedor no calza con ningún proxy: si falta, todas las peticiones cuentan con la IP del
  proxy, que es más estricto, nunca más permisivo. Nunca ``*`` ni una red que lo cubra todo
  (0.0.0.0/0, ::/0): con eso cualquiera elige su IP con un X-Forwarded-For y se salta el límite por IP
  y la demora de la entrada. Un valor así impide arrancar.
- PROXY_SALTOS: cuántas IP propias agrega el borde de la plataforma a la derecha de X-Forwarded-For,
  un entero de 0 a 5. Por omisión 0, el comportamiento de antes. En Railway, 1: la IP del cliente es la
  que queda justo a la izquierda del borde (app/core/proxy.py). Otro valor impide arrancar.
- DIAGNOSTICO_PROXY: el diagnóstico temporal de X-Forwarded-For. Lo lee app/core/config.py, que no
  carga con él encendido y ENTORNO=produccion.

Los errores de configuración nunca repiten el valor recibido.

La IP del cliente la fija MiddlewareProxy (app/core/proxy.py), que envuelve la app. El
ProxyHeadersMiddleware de Uvicorn queda apagado (proxy_headers=False): con los dos, el X-Forwarded-For
se leería dos veces. El log de acceso de Uvicorn también queda apagado (access_log=False y sin
log_config): registra el query string. Lo reemplaza la línea "peticion" de app/core/logs.py.
"""

import ipaddress
import logging
import os
import re
from collections.abc import Mapping
from typing import Any

from starlette.types import ASGIApp

from app.core.proxy import SALTOS_MAXIMOS, MiddlewareProxy

IPS_POR_OMISION = "127.0.0.1"
PUERTO_POR_OMISION = 8000

log = logging.getLogger("matu.api.arranque")


class ConfiguracionProxyInvalida(ValueError):
    """FORWARDED_ALLOW_IPS o PROXY_SALTOS no son válidos. El mensaje nunca repite el valor."""


def ips_de_confianza(valor: str | None) -> list[str]:
    """Las IP o redes de FORWARDED_ALLOW_IPS, validadas. Vacío o ausente: 127.0.0.1."""
    texto = (valor or "").strip() or IPS_POR_OMISION
    resultado: list[str] = []
    for parte in (p.strip() for p in texto.split(",")):
        if not parte:
            continue
        if "*" in parte:
            raise ConfiguracionProxyInvalida("FORWARDED_ALLOW_IPS no admite '*': indica la IP o la red del proxy")
        try:
            red = ipaddress.ip_network(parte, strict=False)
        except ValueError:
            raise ConfiguracionProxyInvalida(
                "FORWARDED_ALLOW_IPS debe ser una lista de IP o redes CIDR separadas por comas"
            ) from None
        if red.prefixlen == 0:
            raise ConfiguracionProxyInvalida("FORWARDED_ALLOW_IPS no admite una red que cubra todas las direcciones")
        resultado.append(parte)
    if not resultado:
        resultado.append(IPS_POR_OMISION)
    return resultado


def saltos_de_proxy(valor: str | None) -> int:
    """PROXY_SALTOS validado: un dígito de 0 a SALTOS_MAXIMOS. Vacío o ausente: 0."""
    texto = (valor or "").strip()
    if not texto:
        return 0
    if not re.fullmatch(r"[0-9]", texto) or int(texto) > SALTOS_MAXIMOS:
        raise ConfiguracionProxyInvalida(f"PROXY_SALTOS debe ser un entero entre 0 y {SALTOS_MAXIMOS}")
    return int(texto)


def puerto(valor: str | None) -> int:
    if not valor:
        return PUERTO_POR_OMISION
    numero = int(valor)
    if not 1 <= numero <= 65535:
        raise ValueError("PORT debe estar entre 1 y 65535")
    return numero


def parametros_uvicorn(entorno: Mapping[str, str]) -> dict[str, Any]:
    """Los parámetros de uvicorn.run, sin la app. Las pruebas arman uvicorn.Config con ellos."""
    return {
        "host": "0.0.0.0",  # dentro del contenedor: la entrada es el proxy de la plataforma
        "port": puerto(entorno.get("PORT")),
        # X-Forwarded-For y X-Forwarded-Proto los lee MiddlewareProxy, una sola vez
        "proxy_headers": False,
        "access_log": False,
        "log_config": None,
        "server_header": False,
    }


def app_detras_del_proxy(app: ASGIApp, entorno: Mapping[str, str], diagnostico: bool = False) -> MiddlewareProxy:
    """La app envuelta en MiddlewareProxy, con FORWARDED_ALLOW_IPS y PROXY_SALTOS del entorno, validados."""
    return MiddlewareProxy(
        app,
        redes=ips_de_confianza(entorno.get("FORWARDED_ALLOW_IPS")),
        saltos=saltos_de_proxy(entorno.get("PROXY_SALTOS")),
        diagnostico=diagnostico,
    )


def main() -> None:
    import uvicorn

    # Primero las variables del proxy: si una no es válida, la API no arranca y no llega a importar la app
    parametros = parametros_uvicorn(os.environ)
    ips_de_confianza(os.environ.get("FORWARDED_ALLOW_IPS"))
    saltos = saltos_de_proxy(os.environ.get("PROXY_SALTOS"))

    from app.core.config import obtener_configuracion
    from app.main import app

    diagnostico = obtener_configuracion().diagnostico_proxy
    # Como "entorno=staging": el arranque deja la marca, sin las redes ni ninguna IP
    log.warning("proxy_saltos=%d diagnostico_proxy=%s", saltos, "encendido" if diagnostico else "apagado")
    uvicorn.run(app_detras_del_proxy(app, os.environ, diagnostico), **parametros)


if __name__ == "__main__":
    main()
