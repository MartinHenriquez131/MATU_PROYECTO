"""Desde qué direcciones conecta el proxy de Railway a la API (MATU-25). Solo para fijar FORWARDED_ALLOW_IPS.

Se corre a mano dentro del contenedor, en una sesión interactiva, mientras alguien abre la API por HTTPS:

    railway ssh --service matu-api
    python /app/infra/railway/pares_tcp.py

Lee /proc/net/tcp y /proc/net/tcp6 y muestra las direcciones remotas distintas de las conexiones
establecidas al puerto $PORT. Esas conexiones las abre el proxy de la plataforma, nunca una persona: la
API no tiene otra entrada. No escribe en ningún log ni archivo, y no ve el X-Forwarded-For.
"""

import ipaddress
import os
import socket
import struct
from pathlib import Path

ESTABLECIDA = "01"


def _ip(hexadecimal: str) -> str:
    crudo = bytes.fromhex(hexadecimal)
    # El kernel escribe cada palabra de 32 bits en el orden del procesador (little endian en x86 y arm64)
    palabras = struct.unpack("<" + "I" * (len(crudo) // 4), crudo)
    empaquetado = struct.pack(">" + "I" * len(palabras), *palabras)
    familia = socket.AF_INET if len(crudo) == 4 else socket.AF_INET6
    direccion = ipaddress.ip_address(socket.inet_ntop(familia, empaquetado))
    if isinstance(direccion, ipaddress.IPv6Address) and direccion.ipv4_mapped:
        return str(direccion.ipv4_mapped)
    return str(direccion)


def pares(puerto: int) -> set[str]:
    encontrados: set[str] = set()
    for tabla in ("/proc/net/tcp", "/proc/net/tcp6"):
        ruta = Path(tabla)
        if not ruta.exists():
            continue
        for linea in ruta.read_text().splitlines()[1:]:
            campos = linea.split()
            local, remota, estado = campos[1], campos[2], campos[3]
            if estado == ESTABLECIDA and int(local.split(":")[1], 16) == puerto:
                encontrados.add(_ip(remota.split(":")[0]))
    return encontrados


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", "8000"))
    resultado = sorted(pares(puerto))
    print(f"Conexiones establecidas al puerto {puerto}: {len(resultado)} direcciones distintas")
    for direccion in resultado:
        print(f"  {direccion}")
    if not resultado:
        print("  ninguna: abre la API por HTTPS desde el teléfono o el navegador y vuelve a correrlo")
