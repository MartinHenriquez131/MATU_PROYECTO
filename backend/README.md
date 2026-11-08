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
| `destruccion_fichas` | Destruye las claves de las fichas retiradas hace 90 días (MATU-44) | 03:10, diario | ver `borrados` |
| `conservacion_consumo` | Borra los perfiles de consumo 90 días después de terminar la autorización (MATU-36) | 03:10, diario | ver `borrados` |
| `conservacion_sesiones` | Borra sesiones y dispositivos vencidos (MATU-38) | 03:10, diario | ver `borrados` |
| `quiebres` | Recalcula los quiebres de cada grupo y conserva alertas, eventos, notificaciones y compras (MATU-37 y MATU-51) | 04:30 en horario de verano, 03:30 en invierno | `30 7 * * *` |
| `avisos` | Publica el outbox y envía los avisos de quiebre (MATU-41) | cada 15 minutos | `*/15 * * * *` |
| `borrados` | Las tres de borrado, una tras otra | 03:10, diario | `10 6,7 * * *` |
| `todas_diarias` | `borrados` y después `quiebres`, en ese orden | a mano | — |

Cada tarea corre en su propio `try`: una que falla no detiene a las demás. El proceso sale con `0` si
todas terminaron, `1` si alguna falló y `2` si el nombre no existe. Todas son idempotentes: correrlas dos
veces el mismo día no repite nada.

Cada corrida deja una línea JSON por tarea en stdout, con `tarea`, `resultado` (`ok`, `fallo` o
`apagada`), `corrida` (también es el `request_id`), `inicio`, `fin`, `duracion_ms` y `contadores`. De un
error queda solo `tipo_error`, nunca su mensaje ni su traza. El log nunca lleva ids de usuario, persona o
grupo, correos, teléfonos, tokens, texto de la ficha ni nombres de insumos.

### Horarios: el cron de Railway se evalúa en UTC

Chile cambia entre UTC-3 (horario de verano, de septiembre a abril) y UTC-4 (invierno, de abril a
septiembre), y el cron de Railway no sabe de zonas horarias. Una misma hora UTC cae una hora antes o
después según la temporada, así que ninguna expresión cae siempre en la misma media hora de Chile. La
propuesta:

- **Borrados**, `python -m app.tareas borrados`, con `10 6,7 * * *`. Corre dos veces al día: en verano
  a las 03:10 y 04:10 de Chile, en invierno a las 02:10 y 03:10. Una de las dos cae siempre a las 03:10,
  dentro de la ventana de 03:00 a 03:30. La otra nunca repite un borrado: solo alcanza lo que cumplió su
  plazo en esa hora. Las dos corren antes que los quiebres.
- **Quiebres**, `python -m app.tareas quiebres`, con `30 7 * * *`: 04:30 en verano y 03:30 en invierno.
  Siempre entre 03:00 y 05:00, y siempre después de los borrados del día. Si se quiere las 04:00 exactas
  en verano, `0 7 * * *` da 04:00 y 03:00, pero en invierno quedaría antes de la corrida de las 03:10.
- **Avisos**, `python -m app.tareas avisos`, con `*/15 * * * *`. Railway no admite intervalos de menos de
  5 minutos. Los avisos no salen antes de las 09:00 de Chile: el consumidor los pospone solo.

`todas_diarias` sirve para correr a mano o con un solo servicio si se acepta perder la ventana de los
borrados: con `30 7 * * *` corre borrados y quiebres seguidos, a las 04:30 o a las 03:30 de Chile.

Railway no lanza una corrida si la anterior sigue viva, y el proceso termina solo al acabar.

### Variables

Las tareas leen la misma configuración que la API (`app/core/config.py`). Solo los nombres:

- Todas: `DATABASE_URL` (como `matu_app`, nunca el dueño ni un superusuario), `ENTORNO`,
  `POLITICA_VERSION` (obligatoria fuera de pruebas) y, opcional, `LOG_NIVEL`.
- `avisos`, además: `ENVIADOR_AVISOS`, `REGISTRO_AVISOS` y `ORIGEN_WEB`. Sin `ENVIADOR_AVISOS` la tarea
  no toma ningún evento y su corrida queda `apagada`, con código `0`.

### Antes de activar el cron en la demostración

- Revisa las fechas de la semilla (`infra/semillas/demo.py`): los borrados y la conservación usan la hora
  real, y una fila sembrada con fechas viejas se borra en la primera corrida.
- `ENVIADOR_AVISOS=simulado` solo carga con `ENTORNO` `local`, `pruebas` o `staging`. El simulado no envía
  nada: escribe una línea por aviso en `REGISTRO_AVISOS` (por omisión `.dev/avisos.jsonl`), nunca en
  stdout. En un contenedor de cron ese archivo se pierde al terminar la corrida.
