"""Las escrituras de las fábricas, en SQL explícito sobre una conexión de superusuario.

Separadas de fabrica.py para que los conftest que siembran a mano (tests/modules/care_circle) usen
las mismas sentencias. Todas reciben los identificadores ya generados: ningún INSERT usa RETURNING.
"""

import uuid
from typing import Any

INSERTAR_USUARIO = "INSERT INTO usuario (id, email, nombre, password_hash, estado) VALUES (%s, %s, %s, %s, %s)"
INSERTAR_INDICE = "INSERT INTO indice_credencial (email_hash, usuario_id) VALUES (%s, %s)"
INSERTAR_GRUPO = "INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES (%s, %s, %s)"
INSERTAR_MEMBRESIA = (
    "INSERT INTO membresia (id, grupo_id, usuario_id, rol, puede_ver_plan, estado, invitado_por)"
    " VALUES (%s, %s, %s, %s, %s, %s, %s)"
)
INSERTAR_DIRECCION = (
    "INSERT INTO direccion (id, grupo_id, calle, numero, comuna, region) VALUES (%s, %s, %s, %s, %s, %s)"
)
INSERTAR_PERSONA = (
    "INSERT INTO persona_cuidada (id, grupo_id, nombre, nombre_pila, nivel_apoyo, direccion_entrega_id)"
    " VALUES (%s, %s, %s, %s, %s, %s)"
)
INSERTAR_CONSENTIMIENTO = (
    "INSERT INTO consentimiento (id, grupo_id, persona_cuidada_id, usuario_id, calidad_otorgante, finalidad,"
    " version_politica, evidencia, referencia_documento, otorgado_en, revision_vence_en)"
    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)"
)
INSERTAR_PLAN = (
    "INSERT INTO plan_cuidado (id, grupo_id, persona_cuidada_id, modo, actualizado_por)"
    " VALUES (%s, %s, %s, 'ficha_relevo', %s)"
)


# Las secciones de la ficha, siempre cifradas (MATU-12): la fábrica nunca escribe texto en claro
INSERTAR_SECCION = (
    "INSERT INTO plan_seccion (plan_id, tipo, contenido_cifrado, nonce, tag_auth, kek_version, version,"
    " actualizado_por) VALUES (%s, %s, %s, %s, %s, %s, 1, %s)"
)
ACTUALIZAR_COMPLETITUD = "UPDATE plan_cuidado SET completitud_pct = %s WHERE id = %s"
LEER_CLAVE = "SELECT dek_cifrada_con_kek, kek_version FROM clave_datos WHERE persona_cuidada_id = %s"
CREAR_CLAVE = (
    "INSERT INTO clave_datos (grupo_id, persona_cuidada_id, dek_cifrada_con_kek, kek_version)"
    " VALUES (%s, %s, %s, %s) ON CONFLICT (persona_cuidada_id) DO NOTHING"
)
CLAVE_DE_PERSONA = "SELECT id FROM clave_datos WHERE persona_cuidada_id = %s"


def insertar_grupo(cx: Any, grupo_id: uuid.UUID, nombre: str, creado_por: uuid.UUID) -> None:
    """Solo la fila de grupo_familiar. La membresía admin del creador va aparte (insertar_membresia)."""
    cx.execute(INSERTAR_GRUPO, (grupo_id, nombre, creado_por))


def insertar_membresia(
    cx: Any,
    grupo_id: uuid.UUID,
    usuario_id: uuid.UUID,
    rol: str,
    *,
    estado: str = "activa",
    puede_ver_plan: bool = False,
    invitado_por: uuid.UUID | None = None,
    membresia_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Una membresía. puede_ver_plan solo vale con rol pagador (CHECK membresia_permiso_plan)."""
    nuevo = membresia_id or uuid.uuid4()
    cx.execute(INSERTAR_MEMBRESIA, (nuevo, grupo_id, usuario_id, rol, puede_ver_plan, estado, invitado_por))
    return nuevo


# Lo que una prueba puede haber escrito dentro de un grupo de las fábricas, en orden de borrado.
# La auditoría no está: es de solo inserción (trigger auditoria_solo_insercion) y solo lleva
# identificadores, sin llave foránea al grupo.
BORRAR_CONTENIDO_DE_GRUPOS = (
    "DELETE FROM plan_seccion WHERE plan_id IN (SELECT id FROM plan_cuidado WHERE grupo_id = ANY(%s::uuid[]))",
    "DELETE FROM acceso_relevo WHERE grupo_id = ANY(%s::uuid[])",
    "DELETE FROM plan_cuidado WHERE grupo_id = ANY(%s::uuid[])",
    "DELETE FROM clave_datos WHERE grupo_id = ANY(%s::uuid[])",
    "DELETE FROM consentimiento WHERE grupo_id = ANY(%s::uuid[])",
    "DELETE FROM persona_cuidada WHERE grupo_id = ANY(%s::uuid[])",
    "DELETE FROM direccion WHERE grupo_id = ANY(%s::uuid[])",
    "DELETE FROM membresia WHERE grupo_id = ANY(%s::uuid[])",
)
