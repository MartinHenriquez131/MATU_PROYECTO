# MATU · Demo navegable

Demo de MATU para la presentación del viernes 30 de octubre de 2026. Muestra las tres capas del semestre (ficha de relevo, consumo y predicción, pedido y pago con un solo pagador) y se siente como una app: en el celular va a pantalla completa y se puede instalar en la pantalla de inicio; en el proyector va dentro de un marco de teléfono, con un panel para el presentador al lado.

Todos los datos son sintéticos: Carmen cuida a María, Rosa la reemplaza y Rodrigo es su hijo.

## Cómo correrla

Requiere Node 22. Desde `Demo/`:

```
npm install
npm run dev          # desarrollo, en http://localhost:5173
npm run build        # versión de producción en dist/
npm run preview      # sirve dist/ en http://localhost:4173
npm run typecheck    # tsc --noEmit
npm run build:single # un solo HTML autocontenido en dist-single/index.html
```

`build:single` genera un archivo que se abre con doble clic o se publica como enlace. Lleva las fuentes adentro y funciona sin conexión. Corre siempre en modo simulado, sin backend.

## Real y simulado

La demo usa el backend real donde ya existe y simula el resto.

| Parte | Modo |
|---|---|
| Crear cuenta (`POST /v1/usuarios`), iniciar sesión (`POST /v1/sesiones`) | Real si hay backend |
| Crear o elegir el grupo (`POST /v1/grupos`, `GET /v1/grupos`) | Real si hay backend |
| Alta de la persona con su consentimiento (`POST` y `GET /v1/grupos/{grupo_id}/personas-cuidadas`) | Real si hay backend |
| Ficha, compartir, relevo, consumo, predicción, pedido, pago y comercio | Simulado, en memoria |

- Al arrancar, la demo consulta `GET /v1/salud`. Si responde, usa el modo real; si no, pasa sola al modo simulado.
- Si una llamada real falla por red o por un error del servidor, la pantalla lo dice con calma y ofrece **Seguir en modo simulado**, sin perder lo escrito.
- El panel del presentador muestra "Backend conectado" o "Modo simulado", y cada escena dice si es Real o Simulado. En una escena real se ven las últimas respuestas: método, ruta y código HTTP. Nunca el cuerpo ni el token.
- El token JWT vive solo en memoria. Nada se guarda en `localStorage`, `sessionStorage` ni cookies, y al recargar se parte de cero.
- El email y la contraseña de la cuenta de prueba se generan en cada sesión (`carmen.NNNN@correo.ejemplo`), para que repetir la demo no choque con un 409. Para ver el 409 a propósito, vuelve a "Crear cuenta" y escribe el mismo email.
- Las llamadas van a `/v1` en el mismo origen. El proxy de Vite (`server.proxy` y `preview.proxy`) las lleva a `http://127.0.0.1:8000`, sin CORS.

### Levantar el modo real

Desde la raíz del repositorio, con Git Bash, siguiendo el README del repositorio:

```
cp .env.example .env    # solo la primera vez, y completar las contraseñas
docker compose --env-file .env -f infra/docker-compose.yml up -d --wait
cd backend
python -m venv .venv               # solo la primera vez
source .venv/Scripts/activate
pip install -e ".[dev]"            # solo la primera vez
alembic upgrade head
uvicorn app.main:app --reload
```

`http :8000/v1/salud` responde `{"estado": "ok"}`. Después, en otra terminal, desde `Demo/`: `npm run dev` (o `npm run build` y `npm run preview`). El panel debe decir "Backend conectado".

Ojo: el modo real escribe cuentas, grupos y personas sintéticas en la base local. Las pruebas del backend la vacían antes de sembrar las suyas.

## Cómo se navega

- **En el proyector (≥ 900 px):** el panel de la derecha tiene las escenas por capa, el selector de rol (familia, relevo, comercio), el estado del backend, "Texto al 200%" y "Reiniciar demo". La nota de cada escena dice en una línea qué demuestra.
- **En el celular:** el panel está detrás del botón "Guía", arriba a la derecha. El distintivo "Demo con datos simulados" está siempre visible.
- Dentro de la app todo funciona al tocarlo: se puede recorrer cada flujo sin usar el panel.

## Escenas

**Capa 1 · Ficha de relevo**
1. Bienvenida
2. Crear cuenta *(real)*
3. Entrar *(real)*
4. ¿A quién cuidas? *(real al aceptar el permiso)*: sin diagnóstico, dirección opcional
5. Permiso *(real)*: titular, representante legal o cuidador de hecho, con el aviso que hay que aceptar
6. Inicio: la ficha como hoja, 1 de 3
7. Completar un campo: pregunta guía, ejemplo y dictado simulado
8. Tu ficha: Listo o Falta
9. Compartir: quién, qué campos y hasta cuándo
10. Enlace y PIN: el PIN de 4 dígitos se ve una sola vez
11. Relevo: escribe el PIN *(Rosa, en `/r#<token>`)*
12. Relevo: la ficha, de solo lectura y con su vencimiento
13. Quién la vio
14. Cortar un acceso
15. Para imprimir: la hoja en pantalla

**Capa 2 · Consumo y predicción**
16. Qué se está acabando: días = stock ÷ consumo diario, sobre el 30/10/2026
17. Declarar consumo, con los pasos − y +
18. Ya lo compré: recalcula la fecha
19. Lista de reposición
20. Exportar la lista: compartir, copiar o descargar

**Capa 3 · Pedido y pago, un solo pagador**
21. Tu pedido
22. Crédito o débito, explicado antes de pagar
23. Pasarela simulada (Transbank, ambiente de prueba)
24. Seguimiento
25. Comercio: pedidos del día *(segundo rol)*
26. Comercio: preparar, con un faltante que se reemplaza
27. Comercio: monto real, dentro del tope
28. Comercio: código de retiro
29. Entregado: reserva $69.000, cobro $51.340, $17.660 liberados

**Casos borde**
30. Todavía no hay nada (estado vacío)
31. Dos versiones: otra persona editó el mismo campo
32. El pago no pasó
33. Relevo: PIN incorrecto, con los intentos que quedan
34. Relevo: enlace no disponible
35. Texto al 200%

## Qué es simulado

- La fecha de la demo es el viernes 30/10/2026 a las 14:20, y avanza unos minutos con cada acción.
- El dictado por voz escribe un ejemplo; WhatsApp no se abre; "Para imprimir" muestra la hoja en pantalla, sin `window.print`.
- El relevo es la misma pestaña: el panel cambia a Rosa y la URL pasa a `/r#<token>`. Después del canje, el token se limpia con `history.replaceState`. Como el estado vive en memoria, un enlace abierto en otra ventana no existe ahí y muestra "Este enlace ya no está disponible".
- El PIN se bloquea al quinto intento fallido (MATU-19).
- La pasarela de pago es una pantalla propia rotulada "Pasarela de pago simulada"; no se mueve dinero ni se piden datos de tarjeta.
- **Crédito:** se reserva el estimado más 15% y se cobra solo el monto real; el resto se libera. **Débito:** se cobra el estimado al confirmar y la diferencia se devuelve cuando la farmacia arma el pedido.
- Fuera del semestre y fuera de la demo: el pago dividido, el prorrateo, la reposición programada y la app de repartidor.

## Archivos

- `src/demo/`: estado en memoria, datos sintéticos, cálculos (predicción y dinero en pesos enteros) y escenas
- `src/datos/`: la capa de datos (`api.ts` con la interfaz, `real.ts` con Axios, `simulado.ts`, `contrato.ts` con los tipos copiados de los esquemas Pydantic)
- `src/pantallas/`: alta, ficha, relevo, consumo, pedido y comercio
- `src/components/`: marco de teléfono, panel del presentador, piezas de interfaz y la URL del relevo
- `DISENO.md`: el plan de diseño y su revisión
- `scripts/generar-iconos.mjs`: dibuja los íconos PNG del manifiesto sin dependencias
