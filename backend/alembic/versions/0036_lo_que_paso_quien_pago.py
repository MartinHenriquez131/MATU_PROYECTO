"""MATU-128: quien pagó un pedido ve «Lo que pasó con tu pedido» en ese pedido (Ley 21.719, minimización).

Cadena: 0034 (MATU-79) -> 0036, por ahora. La 0035 es de MATU-124, que se construye en paralelo: cuando suba,
down_revision pasa a "0035" (decisión R7 del orquestador). Mientras tanto test_cadena_migraciones.py marca el hueco.

Revisión previa del analista normativo del 19-11 (condiciones C1 a C10) y decisiones R1 a R5, E4 y E5 del orquestador
con el mandato de Jorge del 19-11. Decisión 484 de docs/api/README.md. backend/db/*.sql no se tocan.

La invariante de MATU-124 ya se cumple aquí:
- las dos políticas nuevas son TO matu_owner y exigen el marcador app.funcion = 'lo_que_paso' y el rol de una sesión
  de familia (app_rol() = 'ninguno');
- la función que fija el marcador es VOLATILE, lo fija antes de su primera lectura y al salir devuelve el valor con
  que entró.

La función (C1, C2 y C3)
a) pedido_lo_que_paso(p_pedido): SECURITY DEFINER, dueño matu_owner, search_path fijo, VOLATILE, REVOKE ALL FROM
   PUBLIC y EXECUTE solo para matu_app. Primero llama a app_pago_el_pedido(p_pedido) (0032), que responde true solo
   si quien llama, miembro activo de app_grupo(), pagó ese pedido; si no, devuelve 0 filas sin fijar nada. La llamada
   va antes del marcador porque app_pago_el_pedido responde false si ya hay uno de los suyos. Así falla cerrada sin
   cuenta o sin grupo, con operación, sistema o relevo, con una sesión de comercio o de repartidor, para quien no
   pagó (también el pagador y el admin que no pagaron) y para quien salió del grupo. Después fija 'lo_que_paso', lee
   y devuelve el valor anterior.
b) Columnas fijas: id (solo para el AAD del descifrado; la API nunca lo entrega), tipo, estado, creada_en,
   resuelta_en, descripcion, clave_notas_id, resolucion y resolucion_clave_id, y por cada una de las dos claves su
   dek_cifrada_con_kek y su kek_version, solo de las claves que usan las incidencias de ese pedido y con
   grupo_id = app_grupo(). Una clave destruida sale con la DEK en NULL y su kek_version; una que no se ve, con las dos
   en NULL (la aplicación falla cerrada con 503). Nunca creada_por, asignada_a ni version. Ordenadas por creada_en e
   id (E5).
c) incidencia_lo_que_paso (SELECT, TO matu_owner): el marcador, una sesión de familia, el pedido del grupo del
   contexto y app_pago_el_pedido(incidencia.pedido_id). La base vuelve a exigir que haya pagado, aunque otra función
   fijara el marcador.
d) clave_notas_lo_que_paso (SELECT, TO matu_owner): el marcador, una sesión de familia, grupo_id = app_grupo() y que
   la clave la use una incidencia que la sesión ve (la de (c), con el mismo marcador). Ninguna política con marcador va
   TO matu_app (O2, test_aislamiento.py).

Lo que no cambia (C4)
- incidencia_familia (0033, con app_escribe_plan()) y clave_notas_familia_leer (0031, igual) no cambian: un SELECT
  directo de quien pagó sigue leyendo 0 filas. «Datos de» (copia_pagos.py) los sigue usando.
- Nadie más fija 'lo_que_paso'. Ninguna política existente cambia.

Recorrido: quién lee incidencia y clave_notas después de la 0036
- operación: incidencia_operacion_* y clave_notas_operacion_*, sin cambios (la consola).
- admin y cuidador activos: incidencia_familia y clave_notas_familia_leer, sin cambios («Datos de»).
- quien pagó, activo en el grupo: solo por pedido_lo_que_paso, con (c) y (d). GET
  /v1/grupos/{grupo_id}/pedidos/{pedido_id}/lo-que-paso decide además con pagados_por, nunca con el rol (C5).
- clave_notas_destruir (0030), con su marcador 'clave_notas_destruir', sin cambios.
- El comercio, el repartidor, el relevo, sistema y los roles de las tareas: nada.

downgrade() quita la función y las dos políticas, sin borrar filas, y deja el catálogo como en la 0034.

Revision ID: 0036
Revises: 0034
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036"
# Por ahora: con la 0035 de MATU-124 en la rama, pasa a "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


MARCADOR = "current_setting('app.funcion', true) = 'lo_que_paso'"
# El rol de una sesión de familia: ni operación, ni sistema, ni relevo
FAMILIA = "app_rol() = 'ninguno'"

POLITICAS = f"""
-- (c) Las incidencias de un pedido que pagó quien llama, solo con el marcador
CREATE POLICY incidencia_lo_que_paso ON incidencia FOR SELECT TO matu_owner USING (
    {MARCADOR} AND {FAMILIA}
    AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = incidencia.pedido_id AND p.grupo_id = app_grupo())
    AND app_pago_el_pedido(incidencia.pedido_id));
-- (d) Las claves de esas incidencias, del grupo del contexto
CREATE POLICY clave_notas_lo_que_paso ON clave_notas FOR SELECT TO matu_owner USING (
    {MARCADOR} AND {FAMILIA} AND grupo_id = app_grupo()
    AND EXISTS (SELECT 1 FROM incidencia i
                 WHERE i.clave_notas_id = clave_notas.id OR i.resolucion_clave_id = clave_notas.id));
"""

FUNCION = """
-- (a) y (b) Lo que el equipo anotó de un pedido, para quien lo pagó. Columnas fijas
CREATE FUNCTION pedido_lo_que_paso(p_pedido uuid) RETURNS TABLE (
    id uuid, tipo text, estado text, creada_en timestamptz, resuelta_en timestamptz, descripcion bytea,
    clave_notas_id uuid, resolucion bytea, resolucion_clave_id uuid,
    nota_dek_cifrada bytea, nota_kek_version integer, resolucion_dek_cifrada bytea, resolucion_kek_version integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
BEGIN
    -- C1: primero si pagó este pedido, activo en el grupo del contexto. Si no, 0 filas y el marcador intacto
    IF p_pedido IS NULL OR NOT public.app_pago_el_pedido(p_pedido) THEN
        RETURN;
    END IF;
    PERFORM set_config('app.funcion', 'lo_que_paso', true);
    RETURN QUERY
        SELECT i.id, i.tipo::text, i.estado::text, i.creada_en, i.resuelta_en, i.descripcion, i.clave_notas_id,
               i.resolucion, i.resolucion_clave_id, kn.dek_cifrada_con_kek, kn.kek_version,
               kr.dek_cifrada_con_kek, kr.kek_version
          FROM public.incidencia i
          LEFT JOIN public.clave_notas kn ON kn.id = i.clave_notas_id AND kn.grupo_id = public.app_grupo()
          LEFT JOIN public.clave_notas kr ON kr.id = i.resolucion_clave_id AND kr.grupo_id = public.app_grupo()
         WHERE i.pedido_id = p_pedido
         ORDER BY i.creada_en, i.id;
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
END $$;
REVOKE ALL ON FUNCTION pedido_lo_que_paso(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pedido_lo_que_paso(uuid) TO matu_app;
"""

BAJADA = """
DROP FUNCTION pedido_lo_que_paso(uuid);
DROP POLICY clave_notas_lo_que_paso ON clave_notas;
DROP POLICY incidencia_lo_que_paso ON incidencia;
"""

UPGRADE = POLITICAS + FUNCION
DOWNGRADE = BAJADA


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)
