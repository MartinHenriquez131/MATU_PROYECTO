"""Adaptador SQL del puerto RepositorioClaves: la fila de clave_datos de cada persona (MATU-11).

Trabaja con la sesión de la petición (sesion_tenant), con el contexto ya fijado: RLS acota cada
consulta al grupo en contexto (política clave_familia) o al acceso de relevo vigente
(clave_relevo). Nunca abre su propia sesión ni fija contexto.

No borra claves: matu_app no tiene DELETE sobre clave_datos, y una clave destruida no vuelve a tener DEK
(trigger clave_datos_destruida_fija, migración 0003). Puede tener una clave nueva para contenido nuevo
después de una autorización nueva (MATU-44, P8, migración 0016). Desde MATU-44 la destruye en un caso: al volver a
autorizar la ficha 90 días o más después del retiro (decisión 128). La tarea de los 90 días usa la función
plan_destruir_claves (migración 0016), no este adaptador.
"""

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session

from app.modules.care_plan.application.ports import DekEnvuelta
from app.modules.care_plan.domain.cifrado import ClaveGuardada

# La clave actual de la persona (MATU-44, P8, decisión 130): la vigente si la hay. Si no, la última destruida,
# salvo que haya una autorización para plan_cuidado otorgada después de esa destrucción: entonces la ficha
# empieza de nuevo y la persona queda en "todavía no existe" hasta la próxima escritura, que crea una clave
# nueva (el trigger clave_datos_nueva_tras_autorizacion de 0016 lo vuelve a exigir). Una clave destruida
# nunca vuelve a tener DEK.
_OBTENER = (
    "SELECT k.dek_cifrada_con_kek, k.kek_version FROM clave_datos k WHERE k.persona_cuidada_id = :persona_id"
    " AND (k.destruida_en IS NULL OR NOT EXISTS (SELECT 1 FROM consentimiento c"
    " WHERE c.persona_cuidada_id = k.persona_cuidada_id AND c.finalidad = 'plan_cuidado'"
    " AND c.revocado_en IS NULL AND c.otorgado_en >= k.destruida_en)"
    # Y solo si ya no queda ninguna sección cifrada con la clave anterior (se descartan al volver a autorizar):
    # con secciones viejas la clave sigue contando como destruida y la ficha responde 404, nunca 500
    " OR EXISTS (SELECT 1 FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
    " WHERE p.persona_cuidada_id = k.persona_cuidada_id))"
    " ORDER BY (k.destruida_en IS NULL) DESC, k.destruida_en DESC LIMIT 1"
)
_LEER = text(_OBTENER)
# Bloqueo compartido: dos escrituras de la misma ficha no se esperan entre sí, pero una
# destrucción concurrente (UPDATE) espera a que la escritura termine.
_LEER_PARA_ESCRIBIR = text(_OBTENER + " FOR SHARE OF k")

# Sin RETURNING, como el resto de los repositorios. Si la persona ya tiene una fila (vigente o
# destruida), el UNIQUE de persona_cuidada_id hace que no se escriba nada. Si otra transacción la
# está creando, esta espera a que termine y después decide.
_CREAR = text(
    "INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
    " VALUES (:grupo_id, :persona_id, :dek_cifrada, :kek_version)"
    " ON CONFLICT (persona_cuidada_id) WHERE destruida_en IS NULL DO NOTHING"
)


# MATU-44: el borrado criptográfico, en la misma sentencia (CHECK clave_datos_destruccion)
_DESTRUIR = text(
    "UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = :ahora"
    " WHERE persona_cuidada_id = :persona_id AND destruida_en IS NULL RETURNING id, grupo_id"
)


class RepositorioClavesSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener(self, persona_cuidada_id: uuid.UUID, *, para_escribir: bool = False) -> ClaveGuardada | None:
        sentencia = _LEER_PARA_ESCRIBIR if para_escribir else _LEER
        fila = self._sesion.execute(sentencia, {"persona_id": persona_cuidada_id}).one_or_none()
        if fila is None:
            return None
        dek_cifrada, kek_version = fila
        return ClaveGuardada(
            kek_version=kek_version, dek_cifrada=bytes(dek_cifrada) if dek_cifrada is not None else None
        )

    def crear(self, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, envuelta: DekEnvuelta) -> bool:
        resultado = cast(
            CursorResult[Any],
            self._sesion.execute(
                _CREAR,
                {
                    "grupo_id": grupo_id,
                    "persona_id": persona_cuidada_id,
                    "dek_cifrada": envuelta.dek_cifrada,
                    "kek_version": envuelta.kek_version,
                },
            ),
        )
        return resultado.rowcount == 1

    def destruir(self, persona_cuidada_id: uuid.UUID, ahora: datetime) -> uuid.UUID | None:
        """Destruye la clave vigente de la persona. Devuelve su id, o None si no había o ya estaba destruida."""
        fila = self._sesion.execute(_DESTRUIR, {"persona_id": persona_cuidada_id, "ahora": ahora}).first()
        return None if fila is None else fila.id
