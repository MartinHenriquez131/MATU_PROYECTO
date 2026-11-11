"""La pasarela que configura PASARELA_PAGO (app/core/config.py, MATU-62).

- integracion: PasarelaTransbank con las credenciales públicas de integración del SDK.
- produccion: PasarelaTransbank con WEBPAY_CODIGO_COMERCIO y WEBPAY_LLAVE.
- falsa: una sola PasarelaFalsa por proceso, que aprueba sola (desarrollo local, sin red).
- sin valor: None. pagar responde 503 y la vuelta y la conciliación no llaman a nadie.

Si el SDK no está instalado, la integración y la producción también quedan en None: la API arranca igual.
"""

import logging
from functools import lru_cache

from app.core.config import Configuracion, obtener_configuracion
from app.modules.payments.application.ports import PasarelaWebpay
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa

log = logging.getLogger("matu.payments")

RUTA_RETORNO = "/insumos/pedido/pago"


@lru_cache
def _falsa() -> PasarelaFalsa:
    return PasarelaFalsa(aprueba_sola=True)


def pasarela_desde(config: Configuracion) -> PasarelaWebpay | None:
    if config.pasarela_pago is None:
        return None
    if config.pasarela_pago == "falsa":
        return _falsa()
    try:
        from app.modules.payments.infrastructure.pasarela_transbank import PasarelaTransbank

        if config.pasarela_pago == "produccion":
            assert config.webpay_llave is not None
            return PasarelaTransbank(
                produccion=True,
                codigo_comercio=config.webpay_codigo_comercio,
                llave=config.webpay_llave.get_secret_value(),
            )
        return PasarelaTransbank(produccion=False)
    except ImportError:
        log.warning("pasarela sin sdk", extra={"evento": "pasarela_sin_sdk"})
        return None


def obtener_pasarela() -> PasarelaWebpay | None:
    """Dependencia de FastAPI. Las pruebas la sobreescriben con una PasarelaFalsa."""
    return pasarela_desde(obtener_configuracion())


def url_retorno(config: Configuracion) -> str:
    """La return_url: la pantalla /insumos/pedido/pago de la app, en el origen de ORIGEN_WEB (P1, decisión 231)."""
    return f"{config.origen_web}{RUTA_RETORNO}"
