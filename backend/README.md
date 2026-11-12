# Backend de MATU

La API (FastAPI) y las tareas programadas. Cómo levantar todo está en el `README.md` de la raíz y en
`infra/railway/README.md`. Este archivo explica solo el programador de tareas.

## Programador de tareas (MATU-74)

Las tareas de borrado, el trabajo diario de los quiebres y el publicador de avisos corren con un solo punto
de entrada, desde `backend/`:

```
python -m app.tareas <tarea>
```

| Tarea | Qué hace | Horario propuesto (Chile) | Cron en UTC |
|---|---|---|---|
| `destruccion_fichas` | Destruye las claves de las fichas retiradas hace 90 días (MATU-44) | ver `borrados` | ver `borrados` |
| `conservacion_consumo` | Borra los perfiles de consumo 90 días después de terminar la autorización (MATU-36) | ver `borrados` | ver `borrados` |
| `conservacion_sesiones` | Borra sesiones y dispositivos vencidos (MATU-38) | ver `borrados` | ver `borrados` |
| `conservacion_pedidos` | Borra los pedidos no pagados 30 días después de su último cambio y las claves de idempotencia vencidas (MATU-61, D5). Corre siempre, también con `CAPA3_HABILITADA` apagada (decisión 220) | ver `borrados` | ver `borrados` |
| `borrados` | Las cuatro de borrado, una tras otra | 03:00 en horario de verano, 02:00 en invierno | `0 6 * * *` |
| `quiebres` | Recalcula los quiebres de cada grupo y conserva alertas, eventos, notificaciones y compras (MATU-37 y MATU-51) | 05:00 en horario de verano, 04:00 en invierno | `0 8 * * *` |
| `avisos` | Publica el outbox y envía los avisos de quiebre (MATU-41) | cada 5 minutos | `*/5 * * * *` |
| `conciliacion_pagos` | Cierra las ventas de Webpay sin respuesta y reintenta las anulaciones que no terminaron (MATU-62, D-62-5 y D-62-6). Corre siempre, también con `CAPA3_HABILITADA` apagada (D-62-17). Sin `PASARELA_PAGO` no llama a nadie | cada 5 minutos | `*/5 * * * *` |
| `todas_diarias` | `borrados` y después `quiebres`, en ese orden | a mano | — |

Los horarios viven en `HORARIOS` de `app/tareas.py`, y `tests/test_tareas.py` verifica cada día de un año que
caen donde dice esta sección y que este archivo y `infra/railway/README.md` los repiten.

Cada tarea corre en su propio `try`: una que falla no detiene a las demás. El proceso sale con `0` si
todas terminaron, `1` si alguna falló y `2` si el nombre no existe. En `quiebres`, un grupo que falla no
detiene a los demás, pero la corrida queda `fallo` (con sus contadores, entre ellos `grupos_fallidos`) y
sale con `1`, para que Railway la muestre como fallida. Todas son idempotentes: correrlas dos
veces el mismo día no repite nada.

Cada corrida deja una línea JSON por tarea en stdout, con `tarea`, `resultado` (`ok`, `fallo` o
`apagada`), `corrida` (también es el `request_id`), `inicio`, `fin`, `duracion_ms` y `contadores`. De un
error queda solo `tipo_error`, nunca su mensaje ni su traza. El log nunca lleva ids de usuario, persona o
grupo, correos, teléfonos, tokens, texto de la ficha ni nombres de insumos.

### Horarios: el cron de Railway se evalúa en UTC

Chile cambia entre UTC-3 (horario de verano, de septiembre a abril) y UTC-4 (invierno, de abril a
septiembre), y el cron de Railway no sabe de zonas horarias: una misma hora UTC cae una hora antes o después
según la temporada. Los horarios (hallazgos H3 y H5 de Martín, 09-11) caen siempre de madrugada, entre las
00:00 y las 06:59 de Chile, y separan los borrados de los quiebres por dos horas:

- **Borrados**, `python -m app.tareas borrados`, con `0 6 * * *`: 03:00 de Chile en verano y 02:00 en
  invierno, una vez al día.
- **Quiebres**, `python -m app.tareas quiebres`, con `0 8 * * *`: 05:00 en verano y 04:00 en invierno. Dos
  horas después de los borrados, así que no se cruzan aunque un borrado tarde, y con dos horas (verano) o tres
  (invierno) para terminar antes de las 07:00. Si un borrado no corrió, los quiebres igual no crean una alerta
  ni un evento para una persona borrada o con la autorización retirada: el trabajo diario lee solo las personas
  no borradas y las autorizaciones no revocadas (condición C9 del analista).
- **Avisos**, `python -m app.tareas avisos`, con `*/5 * * * *`, el mínimo de Railway. Si una corrida pasa de 5
  minutos y la siguiente toma el mismo evento (el arriendo del outbox dura 5 minutos), ninguna notificación se
  envía dos veces: el consumidor bloquea cada fila y no reenvía una `enviada` (condición C15). Los avisos no
  salen antes de las 09:00 de Chile: el consumidor los pospone solo.

Los cambios de hora de Chile ocurren a las 03:00 o 04:00 UTC, antes de los borrados: ese día los dos cron
quedan en la misma temporada.

`todas_diarias` sirve para correr a mano: los borrados y los quiebres seguidos.

Railway no lanza una corrida si la anterior sigue viva, y el proceso termina solo al acabar. Si la base no
responde, cada tarea deja de esperar la conexión a los 10 segundos (`connect_timeout` del engine de las
tareas, `TIEMPO_CONEXION_S` en `app/tareas.py`) y la corrida falla con código `1`. La API web no cambia.

### Variables

Las tareas leen la misma configuración que la API (`app/core/config.py`). Solo los nombres:

- Todas: `DATABASE_URL` (como `matu_app`, nunca el dueño ni un superusuario), `ENTORNO`,
  `POLITICA_VERSION` (obligatoria fuera de pruebas) y, opcional, `LOG_NIVEL`.
- `borrados` (las tres) y `quiebres`, además: `SCHEDULER_DATABASE_URL`, como `matu_scheduler`.
- `avisos`, además: `PUBLISHER_DATABASE_URL` (como `matu_publisher`), `ENVIADOR_AVISOS`, `ORIGEN_WEB` y,
  solo en local y en pruebas, `REGISTRO_AVISOS` (en staging y en la demo no se carga: ver `infra/railway/README.md`). Sin `ENVIADOR_AVISOS` la tarea no toma ningún evento, no abre ninguna conexión y su corrida
  queda `apagada`, con código `0`.

### Roles de las tareas (hallazgo H2, migración 0022)

Cada tarea usa el rol mínimo para lo que hace, y la API nunca usa estos roles:

| Conexión | Rol | Para qué |
|---|---|---|
| `SCHEDULER_DATABASE_URL` | `matu_scheduler` | Enumera los grupos activos (solo `id` y `estado`) y llama a `plan_destruir_claves`, `consumo_conservar`, `iam_conservar`, `quiebre_conservar` y, desde la 0023, `pedido_conservar` |
| `PUBLISHER_DATABASE_URL` | `matu_publisher` | Llama a `outbox_tomar`, `outbox_publicado`, `outbox_reintentar` y `outbox_posponer`. No lee ni escribe `evento_outbox` ni `evento_consumido` directo: un solo camino, las funciones |
| `DATABASE_URL` | `matu_app` | El trabajo de cada grupo (los quiebres y el consumidor de avisos), con `app.rol = 'sistema'` y `app.grupo_id`, que necesita RLS |

Desde la 0022, `matu_app` ya no ejecuta esas ocho funciones. Las funciones siguen exigiendo `app.rol =
'operacion'`, que la tarea fija: con él, `matu_owner`, el dueño de la función, ve y borra las filas por sus
políticas de conservación. Los dos roles no son `SUPERUSER`, `BYPASSRLS`, `CREATEROLE`, `CREATEDB` ni
`REPLICATION`, no son miembros de otro rol y no tocan la ficha, el relevo, los tokens, las sesiones ni las credenciales
(`tests/test_aislamiento.py`).

Si falta `SCHEDULER_DATABASE_URL` o `PUBLISHER_DATABASE_URL`, o su usuario no es el del rol, la tarea que la
necesita falla con `tipo_error` `FaltaConexion` y `falta` con el nombre de la variable, nunca su valor, y el
proceso sale con `1`. Nunca cae a `matu_app`.

**En local**, los roles existen desde `00_roles.sql`, pero sin contraseña si tu volumen de Docker es anterior a
MATU-74. Fija una con `ALTER ROLE matu_scheduler PASSWORD '…'` (y lo mismo para `matu_publisher`) como
superusuario y agrega las dos URL a tu `.env`, con el formato de `.env.example`. Un volumen nuevo las toma de
`MATU_SCHEDULER_PASSWORD` y `MATU_PUBLISHER_PASSWORD` (`infra/postgres/init/10_matu.sh`).

### Antes de activar el cron en la demostración

- Revisa las fechas de la semilla (`infra/semillas/demo.py`): los borrados y la conservación usan la hora
  real, y una fila sembrada con fechas viejas se borra en la primera corrida.
- `ENVIADOR_AVISOS=simulado` solo carga con `ENTORNO` `local`, `pruebas` o `staging`. El simulado no envía
  nada. El registro de lo enviado es la tabla `notificacion` (estado `enviada` y `enviada_en`), en todo
  entorno (hallazgo H4). El archivo `REGISTRO_AVISOS` (por omisión `.dev/avisos.jsonl`), con una línea por
  aviso, se escribe solo con `ENTORNO` `local` o `pruebas`: en staging no se escribe, porque se perdía con cada
  contenedor del cron. Nunca va a stdout.
