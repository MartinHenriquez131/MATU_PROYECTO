"""Arranque de la API detrás de un proxy, en staging (MATU-25, decisión de Jorge en el PR #27, P2-1).

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

El log de acceso de Uvicorn queda apagado (access_log=False y sin log_config): registra el query
string. Lo reemplaza la línea "peticion" de app/core/logs.py.
"""

import ipaddress
import os
from collections.abc import Mapping
from typing import Any

IPS_POR_OMISION = "127.0.0.1"
PUERTO_POR_OMISION = 8000


class ConfiguracionProxyInvalida(ValueError):
    """FORWARDED_ALLOW_IPS no es una lista de IP o redes acotadas. El mensaje nunca repite el valor."""


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
        "proxy_headers": True,
        "forwarded_allow_ips": ips_de_confianza(entorno.get("FORWARDED_ALLOW_IPS")),
        "access_log": False,
        "log_config": None,
        "server_header": False,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", **parametros_uvicorn(os.environ))


if __name__ == "__main__":
    main()
