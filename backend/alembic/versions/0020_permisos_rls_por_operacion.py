"""MATU-47 y MATU-66: permisos de matu_app acotados y RLS separada por operación y por rol.

Cadena: 0019 (MATU-59) -> 0020. down_revision = "0019".

MATU-47 · indice_token (sin RLS, excepción declarada de 02_rls.sql)
a) matu_app queda con SELECT e INSERT, más UPDATE solo de revocado_en (decisión de Jorge del 09-11), y sin
   DELETE. Las únicas escrituras de hoy son las de la API: el INSERT de compartir (MATU-18) y del refresh
   (MATU-02), y el UPDATE de revocado_en al cortar un relevo (MATU-20) o revocar un refresh. La conservación
   de iam_conservar (0008) borra como matu_owner, SECURITY DEFINER, y no cambia.
b) Trigger token_vida_fija (BEFORE UPDATE, también en acceso_relevo): un token revocado no se reabre ni cambia
   su instante de corte, y expira_en nunca se alarga. Alcanza a todo rol, también al dueño y al superusuario.
   Acortar sigue permitido.

MATU-66 · RLS por operación y por rol
c) acceso_relevo: acceso_familia (ALL) se divide en acceso_familia_leer (SELECT: quien ve el plan, también el
   pagador con permiso), acceso_familia_crear (INSERT) y acceso_familia_cortar (UPDATE), que exigen
   app_escribe_plan() de la 0013: admin o cuidador activo. Sin política de DELETE: cero filas. matu_app pasa a
   UPDATE solo de revocado_en (cortar), nombre_pila_persona (anonimizar al retirar o borrar, MATU-44 y
   MATU-72) y los contadores del relevo (pin_intentos_fallidos, usos, ultimo_uso_en; acceso_relevo_contar y el
   trigger de la 0007 no cambian). Así nadie alarga un acceso ni le cambia el PIN, los campos o el teléfono
   desde la aplicación. matu_app pierde además el DELETE de la tabla (defensa en profundidad, como
   indice_token). El borrado futuro del teléfono a los 30 días va por una función SECURITY DEFINER con una
   política TO matu_owner, sin volver a FOR ALL.
d) clave_datos: clave_familia (ALL) se divide en clave_familia_leer (SELECT: quien ve el plan), clave_familia_crear
   (INSERT) y clave_familia_destruir (UPDATE, y la fila nueva debe quedar sin DEK). Las dos escrituras exigen
   app_escribe_plan(). El DELETE sigue revocado (0003). La rotación de la KEK, cuando exista, va por una función
   SECURITY DEFINER.
e) consentimiento_familia_crear exige además app_retira_autorizacion() de la 0016 (admin o cuidador activo):
   los mismos que dan de alta y autorizan (puede_dar_de_alta). La lectura sigue siendo de todo el grupo.
f) usuario: usuario_operacion (ALL) pasa a usuario_operacion_leer (SELECT). Operación sigue leyendo el email y
   el celular para soporte (política de privacidad, sección 6), y ya no inserta, cambia ni borra cuentas.
g) usuario.password_hash y usuario.mfa_secreto_cifrado: matu_app pierde el SELECT de esas dos columnas (GRANT
   por columna de las demás). RLS es por fila y no las puede ocultar. El login lee el hash con
   iam_credencial(usuario_id), SECURITY DEFINER, que devuelve una fila solo si el id es el de app.usuario_id y
   app.rol no es 'operacion'. Ningún rol de la aplicación, ni operación ni un comiembro, lee el hash de otra
   cuenta. El UPDATE de la contraseña propia (MATU-57) no cambia: SET password_hash no exige leerla.
   iam_credencial confía en el contexto que fija la propia aplicación (app.usuario_id y app.rol), como el resto
   de RLS: quien controle matu_app y fije otro app.usuario_id lee esa fila, igual que con usuario_propio.
h) usuario_propio (ALL) se separa en usuario_propio_leer (SELECT), usuario_propio_crear (INSERT, el registro de
   MATU-04, y nunca con es_operacion) y usuario_propio_editar (UPDATE), sobre la propia fila. Sin política de
   DELETE, y matu_app pierde el DELETE de usuario. matu_app pasa a UPDATE solo de las columnas que la
   aplicación cambia hoy: password_hash (recuperación, MATU-57), telefono (la semilla de MATU-64; el trigger
   de la 0012 deja el celular sin verificar), celular_verificado_en y celular_canal (verificación, MATU-57) y
   actualizado_en. Nunca
   es_operacion, estado, email, nombre ni eliminado_en: ningún flujo los cambia, y una cuenta no se hace
   operación, no se desbloquea ni se borra desde su propio contexto.

Lo que no cambia: las políticas TO matu_owner (*_conservacion, *_destruccion, *_conservacion_borrar), las
funciones SECURITY DEFINER de MATU-74 y anteriores, grupo_operacion, y las tablas de consumo y del plan, que ya
estaban por operación y por rol (0009, 0011, 0013, 0016 y 0017).

Las políticas FOR ALL que quedan en tablas de negocio, con su destino:
- Capa 3 (pedido, entrega y cargo, con sus hijas: pedido_familia, pedido_operacion, entrega_familia,
  entrega_operacion, linea_hereda, regla_hereda, transicion_hereda, cargo_familia, cargo_operacion,
  participacion_hereda, transaccion_hereda e idempotencia_familia): MATU-61, MATU-62 y MATU-63.
- care_circle (membresia_familia, membresia_operacion, invitacion_familia, direccion_familia,
  direccion_operacion y grupo_familia): MATU-42. grupo_operacion queda igual (condición 4 del analista).
- Notificaciones (notificacion_sistema): MATU-79.
- Catálogo (categoria_operacion, producto_operacion, comercio_operacion, convenio_operacion, oferta_operacion,
  usuario_comercio_operacion) y Product Backlog (asignacion_*, oferta_asig_*, evidencia_hereda,
  repartidor_operacion, consumo_comercio_*, liquidacion_operacion, plan_repo_familia, plan_repo_linea_hereda,
  ocurrencia_hereda, medio_pago_propio): se quedan.
- Datos propios: dispositivo_propio, sesion_propia y preferencia_propia se quedan, acotados a app_usuario().
  usuario_propio queda separado aquí (h).

backend/db/*.sql no se tocan: son el esquema de 0001.

downgrade() deja el esquema como en 0019. Lo verifica tests/test_migraciones.py.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


VE_PLAN = "grupo_id = app_grupo() AND (SELECT app_puede_ver_plan())"
ESCRIBE_PLAN = "grupo_id = app_grupo() AND (SELECT app_escribe_plan())"

# usuario sin password_hash ni mfa_secreto_cifrado
COLUMNAS_USUARIO = (
    "id, email, telefono, nombre, es_operacion, estado, email_verificado_en, creado_en, actualizado_en,"
    " eliminado_en, celular_verificado_en, celular_canal"
)
COLUMNAS_ACCESO = "revocado_en, nombre_pila_persona, pin_intentos_fallidos, usos, ultimo_uso_en"
# Lo que la aplicación cambia de una cuenta. Nunca es_operacion, estado, email, nombre ni eliminado_en
COLUMNAS_USUARIO_EDITABLES = "password_hash, telefono, celular_verificado_en, celular_canal, actualizado_en"
PROPIA = "id = app_usuario()"

UPGRADE = f"""
-- (a) indice_token: SELECT, INSERT y UPDATE de revocado_en. Sin DELETE
REVOKE UPDATE, DELETE ON indice_token FROM matu_app;
GRANT UPDATE (revocado_en) ON indice_token TO matu_app;

-- (b) Un token revocado no se reabre y su vencimiento no se alarga
CREATE FUNCTION token_vida_fija() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF OLD.revocado_en IS NOT NULL AND NEW.revocado_en IS DISTINCT FROM OLD.revocado_en THEN
        RAISE EXCEPTION 'un token revocado no se reabre ni cambia su revocación'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.expira_en > OLD.expira_en THEN
        RAISE EXCEPTION 'el vencimiento de un token no se alarga'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER indice_token_vida_fija BEFORE UPDATE ON indice_token
    FOR EACH ROW EXECUTE FUNCTION token_vida_fija();
CREATE TRIGGER acceso_relevo_vida_fija BEFORE UPDATE ON acceso_relevo
    FOR EACH ROW EXECUTE FUNCTION token_vida_fija();

-- (c) acceso_relevo: leen quienes ven el plan; crean y cortan admin y cuidador
DROP POLICY acceso_familia ON acceso_relevo;
CREATE POLICY acceso_familia_leer ON acceso_relevo FOR SELECT USING ({VE_PLAN});
CREATE POLICY acceso_familia_crear ON acceso_relevo FOR INSERT WITH CHECK ({ESCRIBE_PLAN});
CREATE POLICY acceso_familia_cortar ON acceso_relevo FOR UPDATE USING ({ESCRIBE_PLAN}) WITH CHECK ({ESCRIBE_PLAN});
REVOKE UPDATE, DELETE ON acceso_relevo FROM matu_app;
GRANT UPDATE ({COLUMNAS_ACCESO}) ON acceso_relevo TO matu_app;

-- (d) clave_datos: leen quienes ven el plan; crean y destruyen admin y cuidador
DROP POLICY clave_familia ON clave_datos;
CREATE POLICY clave_familia_leer ON clave_datos FOR SELECT USING ({VE_PLAN});
CREATE POLICY clave_familia_crear ON clave_datos FOR INSERT WITH CHECK ({ESCRIBE_PLAN});
CREATE POLICY clave_familia_destruir ON clave_datos FOR UPDATE USING ({ESCRIBE_PLAN})
    WITH CHECK ({ESCRIBE_PLAN} AND dek_cifrada_con_kek IS NULL);

-- (e) consentimiento: dan la autorización admin y cuidador
DROP POLICY consentimiento_familia_crear ON consentimiento;
CREATE POLICY consentimiento_familia_crear ON consentimiento FOR INSERT
    WITH CHECK (grupo_id = app_grupo() AND (SELECT app_retira_autorizacion()));

-- (f) usuario: operación solo lee
DROP POLICY usuario_operacion ON usuario;
CREATE POLICY usuario_operacion_leer ON usuario FOR SELECT USING (app_rol() = 'operacion');

-- (g) usuario: matu_app no lee password_hash ni mfa_secreto_cifrado; el login usa iam_credencial
REVOKE SELECT ON usuario FROM matu_app;
GRANT SELECT ({COLUMNAS_USUARIO}) ON usuario TO matu_app;

CREATE FUNCTION iam_credencial(p_usuario uuid) RETURNS TABLE (password_hash text, estado text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
    SELECT u.password_hash, u.estado FROM public.usuario u
     -- Explícito además de RLS: usuario_operacion_leer también alcanza a matu_owner
     WHERE u.id = p_usuario AND u.id = public.app_usuario() AND public.app_rol() <> 'operacion'
$$;
REVOKE ALL ON FUNCTION iam_credencial(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION iam_credencial(uuid) TO matu_app;

-- (h) usuario: la propia fila se lee, se crea y se edita, nunca se borra; solo las columnas que cambia la app
DROP POLICY usuario_propio ON usuario;
CREATE POLICY usuario_propio_leer ON usuario FOR SELECT USING ({PROPIA});
CREATE POLICY usuario_propio_crear ON usuario FOR INSERT WITH CHECK ({PROPIA} AND NOT es_operacion);
CREATE POLICY usuario_propio_editar ON usuario FOR UPDATE USING ({PROPIA}) WITH CHECK ({PROPIA});
REVOKE UPDATE, DELETE ON usuario FROM matu_app;
GRANT UPDATE ({COLUMNAS_USUARIO_EDITABLES}) ON usuario TO matu_app;
"""

DOWNGRADE = f"""
REVOKE UPDATE ({COLUMNAS_USUARIO_EDITABLES}) ON usuario FROM matu_app;
GRANT UPDATE, DELETE ON usuario TO matu_app;
DROP POLICY usuario_propio_editar ON usuario;
DROP POLICY usuario_propio_crear ON usuario;
DROP POLICY usuario_propio_leer ON usuario;
CREATE POLICY usuario_propio ON usuario FOR ALL USING (id = app_usuario());

DROP FUNCTION iam_credencial(uuid);
REVOKE SELECT ({COLUMNAS_USUARIO}) ON usuario FROM matu_app;
GRANT SELECT ON usuario TO matu_app;

DROP POLICY usuario_operacion_leer ON usuario;
CREATE POLICY usuario_operacion ON usuario FOR ALL USING (app_rol() = 'operacion');

DROP POLICY consentimiento_familia_crear ON consentimiento;
CREATE POLICY consentimiento_familia_crear ON consentimiento FOR INSERT WITH CHECK (grupo_id = app_grupo());

DROP POLICY clave_familia_destruir ON clave_datos;
DROP POLICY clave_familia_crear ON clave_datos;
DROP POLICY clave_familia_leer ON clave_datos;
CREATE POLICY clave_familia ON clave_datos FOR ALL USING ({VE_PLAN});

REVOKE UPDATE ({COLUMNAS_ACCESO}) ON acceso_relevo FROM matu_app;
GRANT UPDATE, DELETE ON acceso_relevo TO matu_app;
DROP POLICY acceso_familia_cortar ON acceso_relevo;
DROP POLICY acceso_familia_crear ON acceso_relevo;
DROP POLICY acceso_familia_leer ON acceso_relevo;
CREATE POLICY acceso_familia ON acceso_relevo FOR ALL USING ({VE_PLAN});

DROP TRIGGER acceso_relevo_vida_fija ON acceso_relevo;
DROP TRIGGER indice_token_vida_fija ON indice_token;
DROP FUNCTION token_vida_fija();

REVOKE UPDATE (revocado_en) ON indice_token FROM matu_app;
GRANT UPDATE, DELETE ON indice_token TO matu_app;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)
