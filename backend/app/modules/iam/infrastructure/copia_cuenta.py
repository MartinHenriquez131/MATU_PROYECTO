"""«Tus datos»: la copia de los datos de la propia cuenta (MATU-54, Ley 21.719; decisiones 358 a 360 y 367).

iam no importa a nadie (arquitectura 6.4): lo que no es suyo lo traen bloques que registra app/main.py, como los efectos
del retiro (decisión 124).

- ``grupos`` (care_circle) y ``avisos`` (notifications) son obligatorios: sin ellos la ruta falla cerrada (500).
- ``pagos`` (payments) es opcional: con la capa 3 quitada no se registra, y ``pagos`` y ``condiciones_aceptadas``
  van en ``null``.

Lo de iam: la cuenta (con el correo y el celular completos), la última aceptación de la política, los dispositivos y
los eventos de la cuenta (D1 de MATU-55, más la copia). Nunca la contraseña transformada, el secreto del doble factor,
la huella del correo, los hashes de sesión, el push_token ni nada de una persona cuidada. Columnas nombradas (C6), y
lo que se ve lo deciden las políticas de lo propio, no un WHERE (C1).
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import Session

from app.modules.iam.domain.dispositivo import NOMBRE_GENERICO, clase_dispositivo
from app.modules.iam.domain.ingresos import TIPO_POR_ACCION, TIPOS_SIN_DISPOSITIVO
from app.shared.auditoria import AccionAuditoria
from app.shared.copia_datos import en_chile, en_chile_o_nada


@dataclass(frozen=True)
class ContextoCopiaCuenta:
    """La transacción de la copia (REPEATABLE READ, solo app.usuario_id), la cuenta y el instante del Reloj."""

    sesion: Session
    usuario_id: uuid.UUID
    ahora: datetime

    def __repr__(self) -> str:
        return "ContextoCopiaCuenta()"


FuenteBloqueCuenta = Callable[[ContextoCopiaCuenta], Any]

BLOQUE_GRUPOS = "grupos"
BLOQUE_AVISOS = "avisos"
BLOQUE_PAGOS = "pagos"
BLOQUES_OBLIGATORIOS = frozenset({BLOQUE_GRUPOS, BLOQUE_AVISOS})
BLOQUES_CONOCIDOS = frozenset({BLOQUE_GRUPOS, BLOQUE_AVISOS, BLOQUE_PAGOS})

_BLOQUES: dict[str, FuenteBloqueCuenta] = {}


class BloqueCuentaFaltante(RuntimeError):
    """Falta un bloque obligatorio: la copia falla cerrada en vez de salir incompleta. Mensaje fijo."""


def registrar_bloque_cuenta(nombre: str, fuente: FuenteBloqueCuenta) -> None:
    if nombre not in BLOQUES_CONOCIDOS:
        raise ValueError("bloque de copia desconocido")
    _BLOQUES[nombre] = fuente


def quitar_bloque_cuenta(nombre: str) -> None:
    """Solo para las pruebas: simula la capa 3 quitada."""
    _BLOQUES.pop(nombre, None)


def bloque_cuenta(nombre: str) -> FuenteBloqueCuenta | None:
    fuente = _BLOQUES.get(nombre)
    if fuente is None and nombre in BLOQUES_OBLIGATORIOS:
        raise BloqueCuentaFaltante("falta un bloque obligatorio de la copia")
    return fuente


# --- Lo de iam ------------------------------------------------------------------------------------------------

_CUENTA = text(
    "SELECT nombre, email, telefono, celular_verificado_en, celular_canal, creado_en FROM usuario"
    " WHERE id = app_usuario()"
)
_POLITICA = text(
    "SELECT version, huella, aceptada_en FROM aceptacion_politica WHERE usuario_id = app_usuario()"
    " ORDER BY aceptada_en DESC LIMIT 1"
)
_DISPOSITIVOS = text(
    "SELECT nombre, creado_en, ultimo_uso_en, revocado_en, (push_token IS NOT NULL) AS avisos_activos"
    " FROM dispositivo WHERE usuario_id = app_usuario() ORDER BY creado_en DESC, id DESC"
)
# auditoria_cuenta_propia (0025) decide qué filas se ven; el filtro por la lista cerrada va además
_EVENTOS = text(
    "SELECT a.accion, a.ocurrido_en, d.id AS dispositivo_id, d.nombre AS dispositivo_nombre"
    " FROM auditoria a"
    " LEFT JOIN dispositivo d ON a.entidad = 'dispositivo' AND d.id = a.entidad_id"
    " WHERE a.grupo_id IS NULL AND a.accion = ANY(:acciones)"
    " ORDER BY a.ocurrido_en DESC, a.id DESC"
).bindparams(bindparam("acciones", type_=ARRAY(TEXT)))


class CuentaNoEncontrada(LookupError):
    """La cuenta del token ya no se ve (eliminada): la ruta responde 401. Mensaje fijo."""


def cuenta(ctx: ContextoCopiaCuenta) -> dict[str, Any]:
    f = ctx.sesion.execute(_CUENTA).first()
    if f is None:
        raise CuentaNoEncontrada("la cuenta no está")
    return {
        "nombre": f.nombre,
        "correo": f.email,
        "celular": f.telefono,
        "celular_confirmado": f.celular_verificado_en is not None,
        "canal_codigos": f.celular_canal,
        "creada_en": en_chile(f.creado_en),
    }


def politica(ctx: ContextoCopiaCuenta) -> dict[str, Any] | None:
    f = ctx.sesion.execute(_POLITICA).first()
    if f is None:
        return None
    return {"version": f.version, "huella": f.huella, "aceptada_en": en_chile(f.aceptada_en)}


def dispositivos(ctx: ContextoCopiaCuenta) -> list[dict[str, Any]]:
    resultado = []
    for f in ctx.sesion.execute(_DISPOSITIVOS).all():
        nombre = f.nombre or NOMBRE_GENERICO
        resultado.append(
            {
                "nombre": nombre,
                "clase": clase_dispositivo(nombre).value,
                "creado_en": en_chile(f.creado_en),
                "ultimo_uso_en": en_chile_o_nada(f.ultimo_uso_en),
                "cerrado_en": en_chile_o_nada(f.revocado_en),
                "avisos_activos": bool(f.avisos_activos),
            }
        )
    return resultado


# La lista cerrada de «Dónde entraste» (decisión 254) con la copia de la cuenta (decisión 376)
ACCIONES_DE_EVENTOS = frozenset(TIPO_POR_ACCION) | {AccionAuditoria.CUENTA_DATOS_DESCARGAR}


def eventos(ctx: ContextoCopiaCuenta) -> list[dict[str, Any]]:
    filas = ctx.sesion.execute(_EVENTOS, {"acciones": sorted(a.value for a in ACCIONES_DE_EVENTOS)}).all()
    resultado = []
    for f in filas:
        tipo = TIPO_POR_ACCION.get(AccionAuditoria(f.accion))
        if tipo is None:
            continue
        dispositivo = None
        if tipo not in TIPOS_SIN_DISPOSITIVO and f.dispositivo_id is not None:
            nombre = f.dispositivo_nombre or NOMBRE_GENERICO
            dispositivo = {"nombre": nombre, "clase": clase_dispositivo(nombre).value}
        resultado.append({"tipo": tipo.value, "ocurrido_en": en_chile(f.ocurrido_en), "dispositivo": dispositivo})
    return resultado
