"""La tabla clave_notas (migración 0030, decisión 471): la clave vigente de las notas de una persona y las claves con
que se cifraron las notas que se leen.

Trabaja con la sesión de quien llama, con su contexto ya fijado:
- operación (``app.rol = 'operacion'``) crea y lee claves (clave_notas_operacion_crear y clave_notas_operacion_leer);
- quien es miembro activo del grupo las lee (clave_notas_familia_leer); en la aplicación, solo la copia de sus
  datos (payments/infrastructure/copia_pagos.py).
matu_app no cambia ni borra claves. La destrucción la hace la base (clave_notas_destruir), con la de la ficha o el
borrado de la persona. Ninguna sentencia lleva el texto de una nota ni una DEK en claro.
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
_CLAVES = text(
    "SELECT id, dek_cifrada_con_kek, kek_version FROM clave_notas WHERE id = ANY(:ids)"
).bindparams(bindparam("ids", type_=ARRAY(UUID(as_uuid=True))))


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
    """La DEK de cada clave pedida, o None si está destruida, no se ve, no se desenvuelve o no hay custodia."""
    pedidas = sorted({i for i in ids if i is not None}, key=str)
    if not pedidas:
        return {}
    if custodia is None:
        return dict.fromkeys(pedidas)
    filas = list(sesion.execute(_CLAVES, {"ids": pedidas}))
    resultado: dict[uuid.UUID, bytes | None] = dict.fromkeys(pedidas)
    for f in filas:
        if f.dek_cifrada_con_kek is not None:
            resultado[f.id] = custodia.desenvolver(bytes(f.dek_cifrada_con_kek), int(f.kek_version))
    return resultado
