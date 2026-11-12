"""MATU-54: la auditoría sabe a qué persona cuidada se refiere cada fila, para su copia de datos (D-54-7 a).

Cadena: 0027 (MATU-46) -> 0028. Revisión previa del analista normativo (docs/legal/revision-previa-matu-54.md,
sección 2), decisiones 342 a 365 de docs/api/README.md («Plan de la 0028») y las respuestas del orquestador desde la
366. Todo el SQL de restricciones, índices y funciones va aquí; backend/db/*.sql no se toca.

Upgrade:

a) auditoria.persona_cuidada_id uuid, nula y SIN relleno de las filas anteriores: auditoria_solo_insercion rechaza
   todo UPDATE y no se apaga.
b) La persona es del grupo de la fila, en la base: persona_cuidada_id_grupo_uq UNIQUE (id, grupo_id) y la clave
   foránea compuesta auditoria_persona_fk (persona_cuidada_id, grupo_id) -> persona_cuidada (id, grupo_id), MATCH
   SIMPLE y sin ON DELETE. La integridad referencial no pasa por RLS: vale también para el relevo y para matu_app,
   sin abrirles lecturas. La persona no se borra, solo se anonimiza (MATU-72).
c) CHECK auditoria_persona_con_grupo: persona_cuidada_id IS NULL OR grupo_id IS NOT NULL (con MATCH SIMPLE, una
   fila con persona y sin grupo escaparía a la FK).
d) CHECK auditoria_persona_obligatoria NOT VALID, a propósito y sin VALIDATE: toda fila NUEVA de una acción de
   persona (ACCIONES_DE_PERSONA de app/shared/auditoria.py) lleva su persona. Las anteriores no la tienen y no se
   pueden actualizar.
e) CHECK auditoria_cuenta_acotada (0025) con 15 acciones: las 14 de la 0025 más cuenta.datos_descargar.
f) Índice auditoria_persona_ix (persona_cuidada_id, ocurrido_en DESC, id DESC) WHERE persona_cuidada_id IS NOT NULL.
g) plan_destruir_claves (0016) escribe clave.destruir con persona_cuidada_id. CREATE OR REPLACE conserva el dueño,
   SECURITY DEFINER y los permisos (EXECUTE solo matu_scheduler, 0022).

Sin políticas ni permisos nuevos: matu_app tiene INSERT y SELECT de tabla sobre auditoria, que cubren la columna, y
ninguna política mira la columna (D-54-6 a).

downgrade() deja el esquema como la 0027 sin borrar nunca un registro de auditoría: se detiene si alguna fila ya
tiene persona (lo decide un CHECK temporal, que valida todas las filas sin pasar por RLS), y el CHECK de la cuenta
vuelve a las 14 acciones, NOT VALID si ya hay filas cuenta.datos_descargar.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


# Las 14 acciones de la cuenta de la 0025, y la de MATU-54
ACCIONES_DE_CUENTA_0025 = (
    "sesion.iniciar",
    "sesion.inicio_fallido",
    "sesion.reutilizacion_detectada",
    "sesion.cerrar",
    "dispositivo.sacar",
    "dispositivo.push_registrar",
    "dispositivo.push_borrar",
    "cuenta.recuperar_solicitar",
    "cuenta.recuperar_verificar_fallido",
    "cuenta.contrasena_cambiar",  # pragma: allowlist secret
    "cuenta.celular_solicitar",
    "cuenta.celular_verificar",
    "cuenta.celular_verificar_fallido",
    "avisos.preferencia",
)
ACCIONES_DE_CUENTA_0028 = (*ACCIONES_DE_CUENTA_0025, "cuenta.datos_descargar")

# Las acciones que llevan siempre la persona (ACCIONES_DE_PERSONA). tests/test_migraciones.py verifica que coinciden
ACCIONES_DE_PERSONA_0028 = (
    "plan.leer",
    "plan.editar",
    "plan.quitar_seccion",
    "consentimiento.otorgar",
    "consentimiento.revocar",
    "relevo.compartir",
    "relevo.revocar",
    "relevo.presentar",
    "relevo.canje",
    "relevo.pin_incorrecto",
    "relevo.bloqueo",
    "relevo.abrir",
    "consumo.crear",
    "consumo.editar",
    "consumo.desactivar",
    "consumo.activar",
    "consumo.eliminar",
    "alerta.materializar",
    "alerta.descartar",
    "alerta.resolver",
    "reposicion.declarar",
    "clave.destruir",
    "persona.borrar",
    "persona.datos_descargar",
    "direccion.cambiar",
    "pedido.crear",
    "pedido.confirmar",
    "pedido.cancelar",
    "pedido.regla_faltante",
    "pago.iniciar",
    "pago.aprobar",
    "pago.anular",
)


def _lista(acciones: Sequence[str]) -> str:
    return ", ".join(f"'{accion}'" for accion in acciones)


# El cuerpo de la 0016; la 0028 solo cambia el INSERT de la auditoría
_DESTRUIR = """
CREATE OR REPLACE FUNCTION plan_destruir_claves(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    n integer := 0;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'plan_destruir_claves exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '90 days' THEN
        RAISE EXCEPTION 'la ficha se conserva 90 días después del retiro' USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH destruidas AS (
        UPDATE public.clave_datos k SET dek_cifrada_con_kek = NULL, destruida_en = ahora
         WHERE k.destruida_en IS NULL
           AND NOT EXISTS (
                   SELECT 1 FROM public.consentimiento c
                    WHERE c.persona_cuidada_id = k.persona_cuidada_id AND c.finalidad = 'plan_cuidado'
                      AND c.revocado_en IS NULL)
           AND (SELECT max(c.revocado_en) FROM public.consentimiento c
                 WHERE c.persona_cuidada_id = k.persona_cuidada_id AND c.finalidad = 'plan_cuidado') <= limite
        RETURNING k.id, k.grupo_id, k.persona_cuidada_id),
    -- CL-6: lo cifrado con la clave destruida no se queda en la base, ni sus metadatos
    borradas AS (
        DELETE FROM public.plan_seccion s USING public.plan_cuidado p, destruidas d
         WHERE s.plan_id = p.id AND p.persona_cuidada_id = d.persona_cuidada_id
        RETURNING s.id),
    en_blanco AS (
        UPDATE public.plan_cuidado p SET completitud_pct = 0, actualizado_en = ahora
          FROM destruidas d WHERE p.persona_cuidada_id = d.persona_cuidada_id
        RETURNING p.id)
    INSERT INTO public.auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, ocurrido_en{columna})
    SELECT d.grupo_id, 'sistema', NULL, 'clave.destruir', 'clave_datos', d.id, ahora{valor} FROM destruidas d;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END
$$;
"""

UPGRADE = f"""
-- (a) La persona de cada fila, sin relleno
ALTER TABLE auditoria ADD COLUMN persona_cuidada_id uuid;
COMMENT ON COLUMN auditoria.persona_cuidada_id IS
    'MATU-54: la persona a quien se refiere la acción, para su copia de datos. Sin relleno de filas anteriores';

-- (b) La persona es del grupo de la fila. La integridad referencial no pasa por RLS
ALTER TABLE persona_cuidada ADD CONSTRAINT persona_cuidada_id_grupo_uq UNIQUE (id, grupo_id);
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_fk FOREIGN KEY (persona_cuidada_id, grupo_id)
    REFERENCES persona_cuidada (id, grupo_id) MATCH SIMPLE;

-- (c) Con MATCH SIMPLE, una fila con persona y sin grupo escaparía a la FK
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_con_grupo
    CHECK (persona_cuidada_id IS NULL OR grupo_id IS NOT NULL);

-- (d) Toda fila nueva de una acción de persona lleva su persona. NOT VALID a propósito: las anteriores no la tienen
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_obligatoria
    CHECK (persona_cuidada_id IS NOT NULL OR accion NOT IN ({_lista(ACCIONES_DE_PERSONA_0028)})) NOT VALID;

-- (e) La copia de la cuenta es una acción de la cuenta (decisión 347)
ALTER TABLE auditoria DROP CONSTRAINT auditoria_cuenta_acotada;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
    CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(ACCIONES_DE_CUENTA_0028)})) NOT VALID;
ALTER TABLE auditoria VALIDATE CONSTRAINT auditoria_cuenta_acotada;

-- (f) El historial de la copia
CREATE INDEX auditoria_persona_ix ON auditoria (persona_cuidada_id, ocurrido_en DESC, id DESC)
    WHERE persona_cuidada_id IS NOT NULL;

-- (g) clave.destruir con su persona
{_DESTRUIR.format(columna=", persona_cuidada_id", valor=", d.persona_cuidada_id")}
"""

DOWNGRADE = f"""
-- (g)
{_DESTRUIR.format(columna="", valor="")}

-- Nunca se borra un registro de auditoría: si alguna fila ya tiene persona, la bajada se detiene. Validar un CHECK ve
-- todas las filas sin pasar por RLS (un SELECT como matu_owner no vería la auditoría, decisión 331)
DO $$ BEGIN
    BEGIN
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_sin_persona_0028 CHECK (persona_cuidada_id IS NULL);
    EXCEPTION WHEN check_violation THEN
        RAISE EXCEPTION 'MATU-54: hay auditoría asociada a personas; la bajada de la 0028 no borra registros';
    END;
    ALTER TABLE auditoria DROP CONSTRAINT auditoria_sin_persona_0028;
END $$;

-- (e) Como la 0025. Con filas cuenta.datos_descargar, vuelve NOT VALID
ALTER TABLE auditoria DROP CONSTRAINT auditoria_cuenta_acotada;
DO $$ BEGIN
    BEGIN
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
            CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(ACCIONES_DE_CUENTA_0025)}));
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'MATU-54: hay copias de la cuenta en la auditoría; el CHECK de la 0025 vuelve NOT VALID';
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
            CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(ACCIONES_DE_CUENTA_0025)})) NOT VALID;
    END;
END $$;

-- (f), (d), (c), (b) y (a)
DROP INDEX auditoria_persona_ix;
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_obligatoria;
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_con_grupo;
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_fk;
ALTER TABLE persona_cuidada DROP CONSTRAINT persona_cuidada_id_grupo_uq;
ALTER TABLE auditoria DROP COLUMN persona_cuidada_id;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)
