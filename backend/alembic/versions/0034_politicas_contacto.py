"""MATU-79 (parte 3, PR A): el contacto de cada cuenta y del relevo, solo para quien lo usa (Ley 21.719).

Cadena: 0033 (MATU-122) -> 0034. down_revision = "0033".

Revisión previa del analista normativo del 18-11 (hallazgos a y b, y notificacion_sistema; condiciones A1 a A10) y
decisiones de Jorge D1 (permisos por columna y funciones SECURITY DEFINER), D2 (también celular_verificado_en y
celular_canal) y D3 (el sistema actualiza en notificacion solo estado, error y enviada_en, y nunca borra). Cierra
MATU-102. backend/db/*.sql y el contrato OpenAPI no se tocan, y ninguna respuesta de la API cambia (A10).

El contacto de las cuentas (A1, A2 y A3, hallazgo a)
a) matu_app pierde SELECT sobre usuario.email, telefono, celular_verificado_en y celular_canal. Desde la 0020 los
   leía por columna, y con usuario_comiembro un miembro leía el correo y el celular de los demás desde la base. Las
   demás columnas (nombre, estado, eliminado_en, es_operacion, ...) siguen legibles: las usan los listados.
b) cuenta_contacto_propia(): SECURITY DEFINER (matu_owner), sin parámetro, devuelve id, email, telefono,
   celular_verificado_en y celular_canal solo de la cuenta de app_usuario(), y nada sin cuenta en el contexto. Ve la
   fila por usuario_propio_leer (TO public), sin marcador, y por eso es STABLE.
c) aviso_correo(p_usuario): SECURITY DEFINER (matu_owner), VOLATILE porque fija app.funcion = 'aviso_correo' con
   set_config y al salir devuelve el valor con que entró. Devuelve el correo solo con app.rol = 'sistema', sin cuenta
   y con grupo en el contexto, si la cuenta tiene una membresía activa en ese grupo y está activa y no eliminada; si
   no, NULL, sin decir por qué. No depende de usuario_comiembro: lee con usuario_aviso_correo (SELECT, TO matu_owner,
   con su marcador). La membresía la ve por membresia_familia_leer (TO public, grupo del contexto y activa).

El teléfono del relevo (A4, A5 y A6, hallazgo b)
d) matu_app pierde el SELECT de tabla sobre acceso_relevo y recibe SELECT de todas sus columnas menos
   otorgado_a_telefono. Con acceso_familia_leer (VE_PLAN), el pagador con permiso lo leía desde la base, aunque la
   API no se lo muestra (puede_ver_telefono).
e) acceso_relevo_telefono(p_acceso): SECURITY DEFINER (matu_owner), STABLE (sin set_config). Devuelve el teléfono
   solo con cuenta y grupo en el contexto, en un contexto de familia (ni operación, ni sistema, ni relevo, ni
   app.acceso_relevo_id), si el acceso es del grupo del contexto y app_escribe_plan() (admin o cuidador activos). Ve
   la fila por acceso_familia_leer (TO public). Después de los 30 días relevo_conservar ya vació el teléfono: NULL.
f) efecto_retiro.py (A6) deja de leer otorgado_a_telefono en su WHERE: usa telefono_borrado_en IS NULL, equivalente
   por el CHECK acceso_relevo_telefono_borrado de la 0027. Sin ese cambio, el borrado de la persona falla con 42501.

El registro de avisos (A7, D3)
g) Sale notificacion_sistema (FOR ALL, TO public). Entran notificacion_sistema_leer (SELECT), _crear (INSERT, WITH
   CHECK) y _editar (UPDATE, USING y WITH CHECK), TO matu_app, con app.rol = 'sistema', sin cuenta y con el grupo del
   contexto. Sin DELETE: matu_app pierde DELETE en notificacion, y UPDATE queda solo en estado, error y enviada_en.
   Antes, el sistema con un grupo podía borrar el registro de avisos antes de los 90 días. La conservación sigue con
   notificacion_conservacion y notificacion_conservacion_borrar (TO matu_owner), que no cambian.

Recorrido (A8): quién leía cada cosa y por qué no se rompe
- usuario.email, telefono, celular_verificado_en y celular_canal como matu_app (grep en backend/app, infra, scripts
  y las pruebas que corren como matu_app):
  - iam/infrastructure/copia_cuenta.py (_CUENTA, «Tus datos» de la cuenta) y iam/infrastructure/repositorio_sesiones.py
    (_DATOS_CUENTA, /v1/cuenta, recuperación y celular): pasan a cuenta_contacto_propia(), unida a usuario por id
    para el nombre, el estado y el alta.
  - payments/infrastructure/repositorio_pagos.py (_CORREO, el correo de quien paga para Webpay) y
    ordering/infrastructure/repositorio_pedidos.py (_CELULAR, el celular verificado para la entrega): pasan a
    cuenta_contacto_propia(); el segundo filtra por celular_verificado_en en la función.
  - notifications/infrastructure/repositorio_avisos.py (_CORREO): pasa a aviso_correo(:usuario). Corre con
    sesion_tenant(grupo_id, rol='sistema') y sin cuenta (repositorio_avisos.py, abrir), y solo pide el correo de un
    miembro activo con el canal activo (avisos.py y avisos_pedido.py), así que la respuesta no cambia.
  - infra/semillas/demo.py (_TELEFONO, en la semilla y en --restablecer): corre con sesion_tenant(usuario_id=...) de
    la propia cuenta; pasa a cuenta_contacto_propia().
  - Las demás lecturas de usuario (repositorio_miembros.py, copia_datos.py, copia_ficha.py, repositorio_ficha.py,
    repositorio_accesos.py, repositorio_invitaciones.py, copia_insumos.py, repositorio_perfiles.py, copia_pagos.py,
    las dependencias de iam y backoffice, y _MIEMBROS de los avisos) leen id, nombre, estado, eliminado_en o
    es_operacion, que siguen. El alta (repositorio_usuarios.py) inserta sin RETURNING: INSERT no cambia. Los UPDATE
    de telefono, celular_verificado_en y celular_canal (repositorio_sesiones.py y demo.py) filtran por id, y UPDATE
    por columna no cambia.
  - En pg_proc: las funciones que leen esas columnas (relevo_conservar, quiebre_conservar y las de la invitación y
    las cuentas) son SECURITY DEFINER de matu_owner, que conserva sus permisos. El trigger invoker
    usuario_celular_cambia lee NEW y OLD, sin permisos por columna; lo prueba test_aislamiento.py.
- acceso_relevo.otorgado_a_telefono como matu_app:
  - care_plan/infrastructure/repositorio_accesos.py (_LISTAR): pasa a acceso_relevo_telefono(a.id). La API ya lo
    mostraba solo a admin y cuidador (puede_ver_telefono en router_relevo.py), los mismos que app_escribe_plan().
  - care_plan/infrastructure/efecto_retiro.py: (f). El INSERT del acceso (repositorio_accesos.py) y el
    UPDATE ... SET otorgado_a_telefono = NULL siguen: INSERT y UPDATE por columna no cambian.
  - repositorio_relevo.py, enlaces_otorgados.py, copia_ficha.py, repositorio_aperturas.py, copia_datos.py y la semilla
    (_RELEVO_VIGENTE) no leen el teléfono. RETURNING de _REVOCAR_ACCESO devuelve token_hash y plan_id, que siguen.
  - En pg_proc: relevo_conservar es SECURITY DEFINER de matu_owner. Los triggers invoker
    acceso_relevo_telefono_solo_se_borra, token_vida_fija y acceso_relevo_limitar_relevo leen NEW y OLD; los prueba
    test_aislamiento.py.
- notificacion como matu_app con rol sistema: solo repositorio_avisos.py, que hace INSERT ... ON CONFLICT DO NOTHING,
  SELECT, SELECT ... FOR UPDATE y UPDATE de estado, error y enviada_en filtrando por id y grupo_id. Nadie borra.
  «Tus datos» (copia_avisos.py) lee las propias con notificacion_propia, que no cambia. En pg_proc, solo
  quiebre_conservar toca notificacion, como matu_owner con notificacion_conservacion_*.

downgrade() deja el catálogo igual al de la 0033: devuelve los permisos de tabla y de columna, recrea
notificacion_sistema FOR ALL como estaba y quita las funciones y las políticas nuevas. No borra filas.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


DEFINER = "SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp"
CONTACTO = "email, telefono, celular_verificado_en, celular_canal"
# Todas las columnas de acceso_relevo menos otorgado_a_telefono (01_esquema.sql y las migraciones 0009 a 0027)
ACCESO_SIN_TELEFONO = (
    "id, grupo_id, plan_id, otorgado_por, otorgado_a_nombre, nombre_pila_persona, secciones_permitidas, motivo,"
    " token_hash, pin_hash, pin_intentos_fallidos, creado_en, expira_en, revocado_en, usos, ultimo_uso_en,"
    " nombre_pila_comparte, relevo_informado_en, telefono_borrado_en"
)
SISTEMA = "app_rol() = 'sistema' AND app_usuario() IS NULL AND grupo_id = app_grupo()"

CUENTAS = f"""
-- (a) A1: matu_app ya no lee el contacto de ninguna cuenta
REVOKE SELECT ({CONTACTO}) ON usuario FROM matu_app;

-- (b) A2: el contacto de la propia cuenta
CREATE FUNCTION cuenta_contacto_propia()
    RETURNS TABLE (id uuid, email text, telefono text, celular_verificado_en timestamptz, celular_canal text)
    LANGUAGE sql STABLE {DEFINER} AS
$$
    SELECT u.id, u.email, u.telefono, u.celular_verificado_en, u.celular_canal FROM public.usuario u
     WHERE public.app_usuario() IS NOT NULL AND u.id = public.app_usuario()
$$;
REVOKE ALL ON FUNCTION cuenta_contacto_propia() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION cuenta_contacto_propia() TO matu_app;

-- (c) A3: el correo de un miembro activo, para los avisos del grupo del contexto
CREATE POLICY usuario_aviso_correo ON usuario FOR SELECT TO matu_owner
    USING (current_setting('app.funcion', true) = 'aviso_correo');
CREATE FUNCTION aviso_correo(p_usuario uuid) RETURNS text
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
    v_correo text;
BEGIN
    IF p_usuario IS NULL OR public.app_rol() IS DISTINCT FROM 'sistema' OR public.app_usuario() IS NOT NULL
       OR public.app_grupo() IS NULL THEN
        RETURN NULL;
    END IF;
    PERFORM set_config('app.funcion', 'aviso_correo', true);
    SELECT u.email INTO v_correo FROM public.usuario u
     WHERE u.id = p_usuario AND u.estado = 'activo' AND u.eliminado_en IS NULL
       AND EXISTS (SELECT 1 FROM public.membresia m WHERE m.usuario_id = u.id AND m.grupo_id = public.app_grupo()
                      AND m.estado = 'activa');
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN v_correo;
END $$;
REVOKE ALL ON FUNCTION aviso_correo(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION aviso_correo(uuid) TO matu_app;
"""

CUENTAS_BAJADA = f"""
DROP FUNCTION aviso_correo(uuid);
DROP POLICY usuario_aviso_correo ON usuario;
DROP FUNCTION cuenta_contacto_propia();
GRANT SELECT ({CONTACTO}) ON usuario TO matu_app;
"""

RELEVO = f"""
-- (d) A4: acceso_relevo sin el teléfono del relevo
REVOKE SELECT ON acceso_relevo FROM matu_app;
GRANT SELECT ({ACCESO_SIN_TELEFONO}) ON acceso_relevo TO matu_app;

-- (e) A5: el teléfono, solo para admin y cuidador activos del grupo del acceso
CREATE FUNCTION acceso_relevo_telefono(p_acceso uuid) RETURNS text
    LANGUAGE sql STABLE {DEFINER} AS
$$
    SELECT a.otorgado_a_telefono FROM public.acceso_relevo a
     WHERE a.id = p_acceso
       AND public.app_usuario() IS NOT NULL AND public.app_grupo() IS NOT NULL
       AND public.app_rol() NOT IN ('operacion', 'sistema', 'relevo') AND public.app_acceso_relevo() IS NULL
       AND a.grupo_id = public.app_grupo() AND public.app_escribe_plan()
$$;
REVOKE ALL ON FUNCTION acceso_relevo_telefono(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION acceso_relevo_telefono(uuid) TO matu_app;
"""

RELEVO_BAJADA = f"""
DROP FUNCTION acceso_relevo_telefono(uuid);
REVOKE SELECT ({ACCESO_SIN_TELEFONO}) ON acceso_relevo FROM matu_app;
GRANT SELECT ON acceso_relevo TO matu_app;
"""

AVISOS = f"""
-- (g) A7 y D3: el sistema lee, crea y actualiza el estado; nunca borra
DROP POLICY notificacion_sistema ON notificacion;
CREATE POLICY notificacion_sistema_leer ON notificacion FOR SELECT TO matu_app USING ({SISTEMA});
CREATE POLICY notificacion_sistema_crear ON notificacion FOR INSERT TO matu_app WITH CHECK ({SISTEMA});
CREATE POLICY notificacion_sistema_editar ON notificacion FOR UPDATE TO matu_app
    USING ({SISTEMA}) WITH CHECK ({SISTEMA});
REVOKE DELETE, UPDATE ON notificacion FROM matu_app;
GRANT UPDATE (estado, error, enviada_en) ON notificacion TO matu_app;
"""

AVISOS_BAJADA = """
REVOKE UPDATE (estado, error, enviada_en) ON notificacion FROM matu_app;
GRANT DELETE, UPDATE ON notificacion TO matu_app;
DROP POLICY notificacion_sistema_editar ON notificacion;
DROP POLICY notificacion_sistema_crear ON notificacion;
DROP POLICY notificacion_sistema_leer ON notificacion;
CREATE POLICY notificacion_sistema ON notificacion FOR ALL USING (app_rol() = 'sistema' AND grupo_id = app_grupo());
"""

UPGRADE = CUENTAS + RELEVO + AVISOS
DOWNGRADE = AVISOS_BAJADA + RELEVO_BAJADA + CUENTAS_BAJADA


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)
