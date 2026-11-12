"""MATU-55 · Genera una clave VAPID nueva para Web Push (decisión 262, Q7).

Uso, desde backend/ y con el entorno virtual activo:

    python scripts/generar_vapid.py

Imprime en la terminal, solo a quien lo corre:

- la clave privada, en el formato que espera VAPID_CLAVE_PRIVADA (el escalar P-256 de 32 bytes en base64url sin
  relleno), para copiarla en el .env o en las variables de Railway;
- la clave pública que derivará la API, para comparar con la que entrega GET /v1/dispositivos/actual/push.

No escribe ningún archivo ni usa logging: la clave privada solo existe en la salida estándar. No la pegues en un chat,
un ticket, un commit ni un PR. Usa una clave distinta en cada entorno. Al rotarla, las suscripciones viejas dejan de
servir y la pantalla vuelve a inscribir el teléfono (decisión 262).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.vapid import clave_publica, generar_clave_privada  # noqa: E402


def main() -> int:
    privada = generar_clave_privada()
    print("Clave VAPID nueva. Copia la privada al .env o a Railway y no la guardes en ningún otro lugar.")
    print(f"VAPID_CLAVE_PRIVADA={privada}")
    print(f"Clave pública (la deriva la API, no se configura): {clave_publica(privada)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
