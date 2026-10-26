# MATU · Demo navegable

Demo de MATU para la presentación del viernes 30 de octubre de 2026. Es una **web app de escritorio**, pensada para proyectarse desde un computador entre 1280 y 1920 px de ancho. Muestra las tres capas del semestre (ficha de relevo, consumo y predicción, pedido y pago con un solo pagador) como tres apps distintas: la de la familia, la página pública del relevo y la consola de la farmacia, más un panel discreto para el presentador.

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
- En modo simulado, "Entrar" viene con la cuenta sintética de ejemplo (`carmen@correo.ejemplo`), que ya tiene su grupo y a María. Si el presentador salta a una escena real sin haber creado la cuenta, la pantalla lo dice y ofrece seguir en modo simulado con esa cuenta.
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

### Las tres apps

- **La familia (Carmen).** Antes de tener cuenta, el alta va en dos paneles: el de MATU a la izquierda, con los pasos, y el formulario a la derecha. Después, una barra lateral persistente con **Inicio, Ficha de relevo, Insumos, Pedidos y Grupo familiar**, cada una con una pista de estado ("1 de 3", "Pronto", "En curso"), y un encabezado con la persona cuidada y quien está conectada. El contenido va en dos columnas: la ficha al lado de la hoja como la verá el relevo, la lista de insumos al lado del detalle y la predicción, el pedido al lado de la boleta. Ficha e Insumos tienen pestañas para sus vistas hermanas.
- **El relevo (Rosa, `/r#<token>`).** Una página pública, sin cuenta y sin navegación: primero el PIN, después la hoja centrada con el vencimiento al lado. El token se borra de la dirección con `history.replaceState` después del canje. Al quinto PIN incorrecto el enlace se bloquea (MATU-19).
- **El comercio (Farmacia Los Aromos).** Una consola de trabajo: la cola de pedidos del día a la izquierda y el pedido elegido a la derecha, con sus tres pasos: preparar (con un faltante que se reemplaza), el monto real dentro del tope y el código de retiro.
- La **pasarela de pago** es una página aparte, en grises, rotulada "Pasarela de pago simulada".

### El panel del presentador

- Una **franja delgada arriba**: el distintivo "Demo con datos simulados" (siempre visible), el rol (Familia, Relevo, Comercio), la escena actual con anterior y siguiente y su etiqueta Real o Simulado, y las ayudas de la escena: el PIN que dictó Carmen, "Rodrigo guarda este campo", "Abrir como Rosa", "Ver qué hace la farmacia", el código de retiro. Con el rol relevo muestra la dirección: `/r#…` y, después del canje, `/r`.
- Un **cajón lateral**, la guía, que se abre con el botón "Guía" o con `?`. No tapa la app: la angosta y la app se reacomoda. Tiene el estado del backend, la escena actual con su nota, las 35 escenas por capa, "Texto al 200%", el tema (sistema, claro u oscuro), el modo presentación, los atajos y "Reiniciar demo".
- **Modo presentación** (`p`): oculta la franja; queda solo el distintivo en la esquina inferior izquierda, con un botón para abrir la guía.
- **Atajos:** `?` guía, `]` o `Av Pág` escena siguiente (sirve con un control de presentación), `[` o `Re Pág` anterior, `p` modo presentación, `Esc` cierra la guía. No actúan dentro de un campo de texto y se pueden apagar desde la guía.
- Dentro de cada app todo funciona al hacer clic: se puede recorrer cada flujo de punta a punta sin usar el panel.

### Accesibilidad

- Todo se ordena con container queries. "Texto al 200%" aplica `zoom: 2` solo a la app, que se reacomoda a la mitad del ancho; con el zoom del navegador al 400% en 1280 px (320 px efectivos) todo fluye a una columna, sin desplazamiento horizontal.
- Texto base de 17 px en `rem`, foco visible, "Saltar al contenido", foco al título de cada página al navegar, etiquetas en todos los controles, estado dicho con palabra y con forma, y `prefers-reduced-motion`.

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
- El relevo es la misma pestaña: la franja cambia a Rosa y la URL pasa a `/r#<token>`. Después del canje, el token se limpia con `history.replaceState`. Como el estado vive en memoria, un enlace abierto en otra ventana no existe ahí y muestra "Este enlace ya no está disponible".
- El PIN se bloquea al quinto intento fallido (MATU-19).
- La pasarela de pago es una pantalla propia rotulada "Pasarela de pago simulada"; no se mueve dinero ni se piden datos de tarjeta.
- **Crédito:** se reserva el estimado más 15% y se cobra solo el monto real; el resto se libera. **Débito:** se cobra el estimado al confirmar y, si el pedido sale por menos, se devuelve la diferencia; cómo y en qué plazo, todavía por definir.
- Fuera del semestre y fuera de la demo: el pago dividido, el prorrateo, la reposición programada y la app de repartidor.

## Archivos

- `src/demo/`: estado en memoria, datos sintéticos, cálculos (predicción y dinero en pesos enteros) y escenas
- `src/datos/`: la capa de datos (`api.ts` con la interfaz, `real.ts` con Axios, `simulado.ts` con la cuenta de ejemplo, `contrato.ts` con los tipos copiados de los esquemas Pydantic)
- `src/familia/`: la app de la familia (marco con barra lateral, alta, inicio, ficha, insumos, pedidos, pasarela y grupo familiar)
- `src/relevo/`: la página pública del relevo
- `src/comercio/`: la consola de la farmacia
- `src/presentador/`: la franja, la guía, los atajos y el modo presentación
- `src/components/`: piezas de interfaz, la hoja de la ficha y la URL del relevo
- `src/Escenario.tsx`: compone la franja, la app del rol actual, el aviso y la guía
- `DISENO.md`: el plan de diseño y su revisión (del diseñador)
- `scripts/generar-iconos.mjs`: dibuja los íconos PNG del manifiesto (corazón blanco en un círculo de marca) sin dependencias
