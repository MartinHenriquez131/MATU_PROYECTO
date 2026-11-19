"""La tabla clave_notas (migración 0030, decisión 471): la clave vigente de las notas de una persona y las claves con
que se cifraron las notas que se leen.

Trabaja con la sesión de quien llama, con su contexto ya fijado:
- operación (``app.rol = 'operacion'``) crea y lee claves (clave_notas_operacion_crear y clave_notas_operacion_leer);
- quien es miembro activo del grupo las lee (clave_notas_familia_leer); en la aplicación, solo la copia de sus
  datos (payments/infrastructure/copia_pagos.py).
- quien pagó un pedido no las lee aquí: recibe la de las notas de su pedido por pedido_lo_que_paso (MATU-128, 0036)
  y la abre con abrir_clave (backoffice/infrastructure/lo_que_paso_sql.py).
matu_app no cambia ni borra claves. La destrucción la hace la base (clave_notas_destruir), solo con el borrado de la
persona (decisión de Jorge del 17-11): destruir la clave de la ficha no la toca. Ninguna sentencia lleva el texto de
una nota ni una DEK en claro.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import ARRAY, bindparam, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.shared.notas_operacion import CustodiaNotas, NotasNoDisponibles

_VIGENTE = text(
    "SELECT id, dek_cifrada_con_kek, kek_version FROM clave_notas"
    " WHERE persona_cuidada_id = :persona AND destruida_en IS NULL"
)
_CREAR = text(
    "INSERT INTO clave_notas (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
    " VALUES (:grupo, :persona, :dek, :version)"
    " ON CONFLICT (persona_cuidada_id) WHERE destruida_en IS NULL DO NOTHING RETURNING id"
)
_CLAVES = text("SELECT id, dek_cifrada_con_kek, kek_version FROM clave_notas WHERE id = ANY(:ids)").bindparams(
    bindparam("ids", type_=ARRAY(UUID(as_uuid=True)))
)


@dataclass(frozen=True)
class ClaveNotas:
    """La clave vigente de una persona, desenvuelta. La DEK no sale en el repr."""

    id: uuid.UUID
    dek: bytes = field(repr=False)


def clave_para_cifrar(
    sesion: Session, custodia: CustodiaNotas, grupo_id: uuid.UUID, persona_id: uuid.UUID
) -> ClaveNotas:
    """La clave vigente de la persona, o una nueva si no tiene (nunca la tuvo o se destruyó). Con operación en el
    contexto. NotasNoDisponibles si la vigente no se desenvuelve con esta KEK: nunca se crea otra en su lugar."""
    for _ in range(2):
        fila = sesion.execute(_VIGENTE, {"persona": persona_id}).first()
        if fila is not None:
            dek = custodia.desenvolver(bytes(fila.dek_cifrada_con_kek), int(fila.kek_version))
            if dek is None:
                raise NotasNoDisponibles()
            return ClaveNotas(id=fila.id, dek=dek)
        dek, envuelta = custodia.nueva_dek()
        nueva = sesion.execute(
            _CREAR, {"grupo": grupo_id, "persona": persona_id, "dek": envuelta, "version": custodia.kek_version}
        ).scalar_one_or_none()
        if nueva is not None:
            return ClaveNotas(id=uuid.UUID(str(nueva)), dek=dek)
        # Otra transacción la creó a la vez: se lee la suya
    raise NotasNoDisponibles()


def deks(
    sesion: Session, custodia: CustodiaNotas | None, ids: Iterable[uuid.UUID | None]
) -> dict[uuid.UUID, bytes | None]:
    """La DEK de cada clave pedida, o None si está destruida: solo entonces la nota sale como no disponible.

    Falla cerrada (decisión de Jorge del 17-11) con NotasNoDisponibles, para que la ruta responda 503 y nunca muestre
    una nota que existe como si se hubiera borrado: si una clave vigente no se puede abrir porque falta la custodia (sin
    la KEK) o no se desenvuelve con ella, o si una clave pedida no se ve. Sin claves pedidas no se lee nada, y sin la
    KEK tampoco falla."""
    pedidas = sorted({i for i in ids if i is not None}, key=str)
    if not pedidas:
        return {}
    filas = {f.id: f for f in sesion.execute(_CLAVES, {"ids": pedidas})}
    resultado: dict[uuid.UUID, bytes | None] = {}
    for pedida in pedidas:
        fila = filas.get(pedida)
        if fila is None:
            raise NotasNoDisponibles()
        resultado[pedida] = abrir_clave(custodia, fila.dek_cifrada_con_kek, fila.kek_version)
    return resultado


def abrir_clave(custodia: CustodiaNotas | None, envuelta: bytes | None, kek_version: int | None) -> bytes | None:
    """La DEK de una clave leída, o None si está destruida (envuelta en NULL con su versión). Con las mismas reglas de
    deks(): NotasNoDisponibles si la clave no se vio (sin versión), si falta la custodia o si no se desenvuelve con
    ella. MATU-128: la usa también «Lo que pasó con tu pedido», que lee la clave por pedido_lo_que_paso (0036)."""
    if kek_version is None:
        raise NotasNoDisponibles()
    if envuelta is None:
        return None
    if custodia is None:
        raise NotasNoDisponibles()
    dek = custodia.desenvolver(bytes(envuelta), int(kek_version))
    if dek is None:
        raise NotasNoDisponibles()
    return dek
