"""Casos de uso de la política de privacidad (MATU-75): la vigente y la aceptación de la propia cuenta."""

import uuid
from collections.abc import Callable
from datetime import date

from app.modules.iam.application.ports import DatosCuenta, UnidadIam
from app.modules.iam.domain.politica import (
    AceptacionPolitica,
    PoliticaNoDisponible,
    PoliticaVigente,
    armar_politica,
)


def politica_vigente(
    *,
    version: str | None,
    actualizada_en: date | None,
    correo: str | None,
    texto_de: Callable[[str], str],
) -> PoliticaVigente:
    """La política que se muestra y se acepta: la versión configurada, su fecha, su texto tal cual y el correo de
    contacto (CORREO_PRIVACIDAD, o None).

    Lanza PoliticaNoDisponible si falta la versión o la fecha, si la versión no tiene un texto publicado (texto_de),
    o si el texto todavía tiene un marcador. Así no se muestra una política incompleta ni se crea una cuenta con ella.
    """
    if version is None:
        raise PoliticaNoDisponible("falta POLITICA_VERSION")
    if actualizada_en is None:
        raise PoliticaNoDisponible("falta POLITICA_ACTUALIZADA_EN")
    return armar_politica(version=version, actualizada_en=actualizada_en, texto=texto_de(version), correo=correo)


def leer_cuenta_y_aceptacion(
    *, usuario_id: uuid.UUID, unidad: UnidadIam
) -> tuple[DatosCuenta, AceptacionPolitica | None]:
    """La cuenta propia y la última política que aceptó, en una sola transacción. None: sin registro (las cuentas
    creadas antes de MATU-75 no se completan, decisión D2)."""
    with unidad.transaccion(usuario_id) as tx:
        datos = tx.cuenta.datos()
        aceptacion = tx.cuenta.ultima_aceptacion()
    if datos is None:
        raise LookupError("la cuenta del token no existe")
    return datos, aceptacion
