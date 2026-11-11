# MATU-62 · Pago con Webpay Plus del total exacto confirmado · Especificación de diseño

**Versión 1.0 · 11/11/2026** · agente 6 (UI/UX) · para el frontend
**Historia:** MATU-62, el pago del total confirmado con Webpay Plus en venta normal (ADR-027, RF-22, capa 3). Carmen, o Rodrigo como pagador, ve el total exacto, acepta las condiciones, paga una sola vez en la página de Transbank, vuelve a MATU y ve un comprobante que le dice cuánto pagó, con qué tarjeta y qué le garantizamos.
**Dónde se construye:** `web/`, en la app de la familia, React 19, TypeScript y Tailwind CSS v4, mobile first.
**Empieza donde termina MATU-61:** en el resumen «Antes de pagar» (`docs/diseno/matu-61-pedido.md` v1.3, sección 9), donde la 9.9 dejó el lugar de «Pagar `{total}`». Esta especificación construye ese botón, lo que pasa antes de ir a Webpay, la vuelta, el comprobante y los estados del pago. El seguimiento de la preparación y la entrega es de MATU-63.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · la segunda revisión previa del analista (`docs/legal/revision-previa-matu-62-segunda.md` del repositorio MATU), con las decisiones D-62-1 a D-62-17 tomadas el 11-11 (sección 7), las condiciones del pedido 0.2 (su 5.3) y los textos de su 5.4 · `lenguaje.md` secciones 2, 3, 8, 11 y 31 · `matu-61-pedido.md` v1.3 · las escenas 22, 23, 28, 32 y 33 de `Demo/ESPEC-ADR-027.md` · la arquitectura 8.4 (el flujo del pago con retorno).

**Cómo se lee:** los textos entre comillas latinas «» van tal cual en pantalla. Marcas de origen:
- **[A5.4]** texto de la tabla 5.4 del analista, que entra a `lenguaje.md` con esta especificación;
- **[D-62-n]** texto que fija esa decisión;
- **[L 31]** texto ya escrito en la sección 31 de `lenguaje.md` (MATU-61);
- **[AJUSTE]** un texto de [A5.4] o de [L 31] que cambio, con el porqué;
- **[NUEVO]** un texto mío, que Jorge aprueba antes de construir.

Las llaves son datos de la API: `{total}` y `{monto}` en pesos enteros con punto de miles (`$57.460`), `{producto}` el `nombre` del producto, `{pila}` el nombre de pila de la persona cuidada, `{ultimos4}` los cuatro dígitos que entrega Transbank, `{DD/MM/AAAA}` y `{HH:MM}` en hora de Chile, 24 horas.

**Tokens:** **ningún token nuevo**, ningún color nuevo y ninguna regla nueva en la capa base. Todo sale de los componentes que ya existen (`Boton`, `Nota`, `Etiqueta`, `MensajeError`, `Pestanas`, `Acciones`, `Anunciado`, `EnlaceEnFrase`, `AvisoPiloto`, `UnaColumna`, la boleta y el diálogo de cancelar de MATU-61, y la hoja para imprimir de MATU-60). Un solo cambio de componente, con tokens que ya existen: `UnaColumna` suma el tono `ok` (`bg-ok-fondo text-ok`, el mismo par de `Etiqueta tono="ok"`), para la baldosa de «Pagaste tu pedido» (7.4).

**IVA (JC-IVA de MATU-61):** en Chile todos los precios llevan el IVA incluido. El total se llama «Total» o «Total pagado», nunca «Total con IVA», y ningún texto presenta el IVA como algo que se suma.

---

## 0. Puntos abiertos

Lo que la pantalla necesita y que no decido yo. El orquestador lo lleva al backend o a Jorge. Mi propuesta va en la columna de la derecha.

| # | Qué | Para quién | Propuesta |
|---|---|---|---|
| P1 | **Cómo llega la vuelta de Webpay a la app.** Transbank vuelve a la `return_url` con `token_ws`, o con `TBK_TOKEN`, `TBK_ORDEN_COMPRA` y `TBK_ID_SESION` si la persona anuló o se le acabó el tiempo. El analista anota que `token_ws` llega por GET (punto 11) | Backend | La `return_url` es la ruta de la app `/insumos/pedido/pago` (2.1). La pantalla lee lo que trajo la dirección, **lo borra de inmediato con `history.replaceState`** (como el `#token` del relevo) y lo envía en el cuerpo de `POST /v1/pagos/retorno` (arquitectura 8.4). Si Transbank vuelve por POST en algún caso, el backend lo recibe y responde con un 303 a la misma ruta. La pantalla no cambia con una u otra forma, siempre que nada quede en la dirección ni en el historial |
| P2 | **Volver a ver el comprobante después de recargar.** Las rutas no llevan ids (MATU-61, C18), y `pedido-en-curso` devuelve solo pedidos sin pagar | Backend | Una lectura del último pedido pagado de la persona, por ejemplo `GET …/personas-cuidadas/{persona_id}/pedido-pagado`, con la vista de cada rol (D-62-2). La usa el bloque «Pedido pagado» de la pestaña «Pedido» (8) y la ruta del comprobante al recargar. MATU-63 la reemplaza por el seguimiento |
| P3 | **La vuelta sin la sesión de la app.** El retorno es público y se valida por el token (punto 16). Si la app no logra recuperar la sesión al volver, no hay rol ni se sabe quién pagó | Backend | El retorno responde siempre el `resultado` (3.3), sin montos ni tarjeta. La pantalla muestra el resultado y «Entrar» para ver el comprobante (7.10) |
| P4 | **Las condiciones de la versión aceptada.** El comprobante dice «Condiciones aceptadas: versión `{v}`». Si después se publica la 0.3, `/condiciones-pedido` muestra la nueva | Backend | Que `GET /v1/condiciones-pedido` acepte la versión (`?version=0.2`) y el comprobante enlace a esa. Sin eso, el enlace del comprobante no va |
| P5 | **Cuotas.** Con crédito, Webpay puede ofrecer cuotas. El cobro de MATU es uno solo, pero la persona puede haber elegido 3 cuotas con su banco | Analista y backend | Si el `commit` trae cuotas mayores que 1, el comprobante lo dice junto a la tarjeta («en 3 cuotas», 7.5). Que el analista confirme que el texto «Se cobra una sola vez este total» de la boleta sigue siendo cierto con cuotas (MATU cobra una vez; el banco reparte) |
| P6 | **«Avisar a quien armó el pedido»** (D-62-14) | Orquestador | No va en esta historia. Queda para MATU-41 o MATU-63, como dice la decisión. Aquí el pagador ve el texto de 9.11 de MATU-61, sin botón |
| P7 | **Cancelar después de pagar** (solo el admin, condiciones 0.2 §6) | Orquestador | No va en esta historia: es parte del seguimiento (MATU-63). El comprobante dice la garantía con el texto de [A5.4], y nada más |

---

## 1. Para quién y qué

**Carmen (admin)** ve el total, marca que acepta las condiciones y toca «Pagar $57.460». Paga en Webpay con su tarjeta de débito, vuelve a MATU y ve «Pagaste tu pedido», con el comprobante. Lo hace con una mano, en el teléfono.

**Rodrigo (pagador)** abre el resumen del pedido que armó Carmen y lo paga él. No puede cambiar el pedido ni volver a confirmar el total (C3 de MATU-61): si el total vence, se lo pide a Carmen.

**Un cuidador** ve el mismo resumen sin la casilla ni el botón, y sabe quién paga (D-62-8).

**El observador** solo sabe que el pedido está pagado (D-62-2).

**Lo que estas pantallas nunca hacen:**
- Cobrar un total distinto del que se mostró. La bajada, la boleta, «Pagar `{total}`» y «Total pagado» muestran la misma cifra (ESPEC-ADR-027, 2).
- Mostrar o pedir datos de la tarjeta. Se escriben solo en la página de Transbank. MATU muestra el tipo y los últimos 4 dígitos que devuelve Transbank, y solo a quien pagó (D-62-2).
- Abrir Webpay dentro de MATU (un `iframe`) ni en una ventana nueva. Es una navegación de página completa, y la persona ve la dirección de Transbank.
- Dejar el token de Transbank, la orden de compra ni nada del pago en la URL, el historial, `localStorage` ni `sessionStorage` (C18, punto 11).
- Decir que algo «falló», fue «rechazado» o es «inválido» (`lenguaje.md` 3.2). Se dice qué pasó y que no se cobró nada.
- Mostrar una cuenta regresiva. Los plazos se dicen como hora.
- Presentar el comprobante como una boleta: en pantalla se llama «Comprobante», y lleva el sello del piloto (D-62-7).

---

## 2. Navegación, rutas y quién ve qué

### 2.1 Ruta nueva

| Ruta | Pantalla | Quién | Sección |
|---|---|---|---|
| `/insumos/pedido/pago` | La vuelta de Webpay y el comprobante | admin, cuidador y pagador (el observador llega a `/insumos/pedido`) | 7 |

- Se agrega a `Ruta` y `RUTAS` de `ruteo.ts`. `seccionDe` ya la reconoce por el prefijo `/insumos`, y muestra las pestañas con «Pedido» activa, como el resumen.
- **Es también la `return_url`** que el backend le da a Transbank (P1). Se llega a ella de tres maneras:
  1. **desde Webpay**, con los parámetros de Transbank en la dirección: es la vuelta (7.1 a 7.10);
  2. **desde la app**, con el pedido pagado en la memoria de la página («Ver el comprobante», 8): es el comprobante (7.4);
  3. **al recargar**, sin parámetros y sin nada en memoria: pide el pedido pagado (P2) y muestra el comprobante. Si no hay, lleva a `/insumos/pedido`.
- **`<title>`**: el `h1` de cada estado más « · MATU». Por ejemplo, «Estamos confirmando tu pago · MATU» y «Pagaste tu pedido · MATU» **[NUEVO]**.
- **Foco:** al llegar, al `h1`. Cuando el estado cambia en la misma ruta (de «Estamos confirmando tu pago» a «Pagaste tu pedido»), el `h1` cambia, el `<title>` también y el foco va al `h1` nuevo, que se lee. No hace falta otra región viva para el resultado.

### 2.2 Cambiar de persona

Desde `/insumos/pedido/pago`, cambiar de persona en el encabezado lleva a `/insumos/pedido` de la otra persona, como el resumen (MATU-61, 2.3). **Mientras dice «Estamos confirmando tu pago», el cambio de persona sigue disponible**: la confirmación la hace el servidor aunque la pantalla se cierre.

### 2.3 Quién ve qué (D-62-2 y D-62-8)

| Qué | admin | cuidador | pagador | observador |
|---|---|---|---|---|
| La casilla de las condiciones y «Pagar `{total}`» | sí | **no**: «Pagan quien administra el grupo y quien paga.» | sí | no llega al resumen |
| El aviso de los 2 minutos | con «Volver a confirmar» | con «Volver a confirmar» | **sí, sin botón** (D-62-14) | — |
| Pago en curso | 6.1 en el pedido, 6.2 en el resumen | 6.1 | 6.2 | nada |
| La vuelta de Webpay | quien pagó (admin o pagador) | — | quien pagó | — |
| El comprobante: estado, productos, montos, condiciones y garantías | sí | sí | sí | **no** |
| El comprobante: tipo de tarjeta, últimos 4, cuotas y código de autorización | **solo si pagó él** | no | **solo si pagó él** | no |
| El correo del comprobante | solo quien pagó | no | solo quien pagó | no |
| Las devoluciones: estado y monto | sí | sí | sí | no |
| Las devoluciones: «a tu tarjeta terminada en `{ultimos4}`» | solo quien pagó. El resto lee «a la tarjeta con que se pagó» | | | no |
| El bloque «Pedido pagado» de la pestaña «Pedido» | con monto y «Ver el comprobante» | igual | igual | **solo «Pagado»** |

La pantalla decide con lo que trae la vista de cada rol. **Nunca oculta en la pantalla un dato que llegó**: si la vista de un rol trae la tarjeta, es un defecto del contrato, y lo reviso así (criterio 9).

---

## 3. Lo que las pantallas necesitan del contrato

El backend escribe el contrato en paralelo en `docs/api/`. Uso nombres de trabajo. **Si el backend nombra distinto, manda el contrato y la pantalla no cambia.**

### 3.1 Pagar

| Dato | Dónde se usa |
|---|---|
| `POST /v1/pedidos/{id}/pagar` (D-62-11) con `Idempotency-Key` (D-62-12) y `If-Match`. Cuerpo: la versión y la huella de las condiciones que vio quien paga (`condiciones.version` y `condiciones.huella` del resumen), que la casilla marcada acepta | «Pagar `{total}`» (5) |
| Respuesta: la `url` de Webpay y el `token` que va en el formulario | La navegación a Webpay (5.3) |
| 409 `estado-pedido` con `estado: vencido` (D-62-15), u otro estado | 5.4 |
| 409 `pago-en-curso` (D-62-4) | 6.2 |
| 409 `idempotencia-en-curso`, 422 `idempotencia-reutilizada`, 428 (D-62-12) | 5.4 |
| 403 `sin-autorizacion-pedidos` y `revision-vencida` (D-62-8) | Los de MATU-61, 11.2 |
| **Que Webpay no responde** al crear la venta: un `type` propio (por ejemplo 503 `pasarela-no-disponible`), distinto de una caída de MATU | 5.4 |
| **Las condiciones cambiaron** entre que se abrió el resumen y se tocó «Pagar»: un `type` propio (por ejemplo 409 `condiciones-cambiaron`) | 5.4 |

### 3.2 El pedido sin pagar

| Dato | Dónde se usa |
|---|---|
| En `PedidoVista` (y en `pedido-en-curso`), **si hay un pago en curso** (`pago_en_curso`: una venta `iniciada` o `autorizando`). Así la pantalla lo muestra al abrir, sin esperar un 409 | 6.1 y 6.2 |

### 3.3 La vuelta

| Dato | Dónde se usa |
|---|---|
| `POST /v1/pagos/retorno`, público, idempotente por token (D-62-12). Cuerpo: lo que trajo la dirección (P1) | 7.1 |
| `resultado`, una lista cerrada: `aprobado` · `aprobado_tardio` (D-62-4, regla 2) · `no_aprobado` · `abandonado` (la persona anuló en Webpay) · `tiempo_agotado` · `pendiente` (no hay respuesta de Transbank todavía, o el `commit` no se pudo hacer y lo hará la conciliación, D-62-5) · `anulado` (D-62-4, regla 3) | 7.2 a 7.9 |
| `ya_registrado`: el retorno ya se había procesado (retorno repetido) | 7.8 |
| Para `anulado`: si la anulación ya se hizo o está en curso (D-62-6) | 7.9 |
| `persona_cuidada_id` y `pedido_id`, para volver a leer el pedido y fijar la persona en la memoria de la app | 7.1 |
| Una forma de volver a preguntar mientras es `pendiente` (repetir el mismo retorno, o leer el pago del pedido) | 7.3 |

### 3.4 El comprobante

| Dato | Para quién | Dónde se usa |
|---|---|---|
| `referencia` del pedido, corta y legible («4821») | admin, cuidador, pagador | Encabezado (7.5) |
| `pagado_en` | los tres | Encabezado |
| `lineas[]`: `producto.nombre`, `cantidad`, `precio_unitario`, `subtotal` | los tres | Productos |
| `costo_envio`, `total` | los tres | Boleta |
| `pagaste_tu`: si quien mira es quien pagó | los tres | 2.3 |
| `tarjeta.tipo` (`debito` o `credito`), `tarjeta.ultimos4`, `tarjeta.cuotas`, `codigo_autorizacion` | **solo quien pagó** (D-62-2) | La tarjeta (7.5) |
| `vendedor`, `ventana_entrega`, `canal_reclamo` (los de `resumen` de MATU-61) | los tres | Datos del pedido |
| `condiciones`: `version`, `aceptadas_en`, `enlace` (P4) | los tres | Condiciones aceptadas |
| `tardio`: se respetó un pago que llegó con el total vencido | los tres | 7.6 |
| `devoluciones[]`: `monto`, `producto` (o el pedido entero), `estado` (`hecha` o `en_curso`), `hecha_en` | los tres | 7.7 |
| `correo`: el correo de quien pagó y si se envió | **solo quien pagó** | 7.5 |
| `precios_de_ejemplo` | los tres | El aviso del piloto |
| Vista del observador: solo `estado: pagado` | observador | 8 |

**Lo que las pantallas no usan y no deben recibir:** el número completo de la tarjeta, la fecha de vencimiento, el `buy_order`, el `session_id`, el token y la respuesta cruda de Transbank (`payload_respuesta`, D-62-9).

---

## 4. Quién paga en el resumen: la parte de decisión

Cambia la parte de decisión del resumen de MATU-61 (9.8, 9.9 y 9.11). La parte de lectura no cambia.

**Objetivo:** quien paga sabe que va a pagar en Transbank y no en MATU, acepta las condiciones y paga el total que ve, con un toque.

**Jerarquía de la parte de decisión:**
1. La boleta con el total y su hora.
2. «Pagar `{total}`».
3. Las condiciones, la casilla y la frase de Webpay, justo antes del botón. La salida sin costo, después.

### 4.1 Esquema a 360 px (admin y pagador)

```
│ ┌ Tu pedido ─────────────────────┐ │  la boleta (MATU-61, 9.4), sin cambios
│ │ Productos (3)          $53.470 │ │
│ │ Envío (uno por pedido)  $3.990 │ │
│ │ ══════════════════════════════ │ │
│ │ Total                  $57.460 │ │
│ │ Este total vale hasta las      │ │
│ │ 16:45.                         │ │
│ │ Se cobra una sola vez este     │ │
│ │ total, con crédito o con débito│ │
│ │ No hay reserva ni cobros       │ │
│ │ después.                       │ │
│ └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │
│ (aviso de los 2 minutos, 9.5)      │
│ Condiciones del pedido (se abre en │  enlace solo, min-h-12
│ otra pestaña)                      │
│ [ ] Leí y acepto las condiciones   │  casilla size-6, etiqueta min-h-12
│     del pedido.                    │
│ Te llevamos a Webpay, la página de │  p text-base text-tenue max-w-prose
│ pago de Transbank. MATU no ve los  │  id="pagar-ayuda"
│ datos de tu tarjeta.               │
│ [ 🔒 Pagar $57.460 ]               │  principal. Único turquesa macizo
│ No pagar no tiene costo.           │  text-base
│ Cancelar pedido                    │  textoPeligro (solo admin)
```

### 4.2 Esquema a 360 px (cuidador)

```
│ (la boleta, igual)                 │
│ (aviso de los 2 minutos, con       │
│  «Volver a confirmar»)             │
│ Condiciones del pedido (se abre en │
│ otra pestaña)                      │
│ Pagan quien administra el grupo y  │  p text-base max-w-prose
│ quien paga.                        │
│ No pagar no tiene costo.           │
│ Cancelar pedido                    │  textoPeligro
```

Sin casilla, sin la frase de Webpay y sin «Pagar». **No hay ningún elemento en `turquesa` macizo** con el total vigente: el cuidador no tiene una acción principal aquí, y dibujar un botón deshabilitado le haría creer que le falta algo.

### 4.3 Pantalla ancha (1280 y 1920 px)

La de MATU-61, 9.10, sin cambios de composición: la parte de decisión es la columna derecha, `sticky top-6`, con `max-h-[calc(100dvh-3rem)] overflow-y-auto [scrollbar-width:thin]`. La frase de Webpay va entre la casilla y «Pagar», en la misma columna.

```
│ Productos                                  ┌ Tu pedido ──────────────────┐ │
│ ┌ Pañal adulto M x30 ─────────────────┐    │ Total               $57.460 │ │
│ └─────────────────────────────────────┘    │ Este total vale hasta las … │ │
│ Si cambias algo, antes de pagar …          └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │
│ [ Cambiar el pedido ]                      Condiciones del pedido (…)     │
│ Entrega …                                  [ ] Leí y acepto las condicio… │
│ Si falta un producto …                     Te llevamos a Webpay, la págin…│
│ Quién vende …                              [ 🔒 Pagar $57.460 ]           │
│                                            No pagar no tiene costo.       │
│                                            Cancelar pedido  (sticky top-6)│
```

A 1280 px la columna mide unos 346 px: «Pagar $57.460» con su ícono mide unos 190 px y cabe en un renglón. «Pagar $1.234.560» también (unos 230 px).

### 4.4 Las partes

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Frase de Webpay | `p id="pagar-ayuda" max-w-prose text-base text-tenue`, después de la casilla y antes del botón, en el `aria-describedby` de «Pagar» | Te llevamos a Webpay, la página de pago de Transbank. MATU no ve los datos de tu tarjeta. | [A5.4] |
| Pagar | `Boton` principal, `self-start`, con `Lock` `size-5` `aria-hidden` antes del texto. Sin flecha. **Nunca deshabilitado**: se valida al tocarlo | Pagar `{total}`, con el total en `cifras` | [L 31] |
| Cuidador, en lugar de la casilla, la frase y el botón | `p max-w-prose text-base` | Pagan quien administra el grupo y quien paga. | [A5.4], [D-62-8] |

- **Por qué la frase de Webpay va antes del botón y no después:** se lee antes de decidir, y el lector la oye con el botón. Dice dos cosas que bajan la duda de Carmen: que la página que viene es de Transbank (no es un engaño) y que MATU no ve su tarjeta.
- **El candado** dice «pago», no «seguridad garantizada»: es el ícono que la demo validó en la escena 21. No se agrega otro ícono ni el logo de Transbank (no se descarga nada de afuera).
- **El cuidador conserva** el enlace de las condiciones (puede leerlas), «No pagar no tiene costo.» y «Cancelar pedido» (MATU-61, JC3).

### 4.5 Al tocar «Pagar»

1. **Sin la casilla marcada:** `MensajeError` bajo la casilla, «Marca que leíste y aceptas las condiciones para pagar.» [L 31], y el foco a la casilla. No se llama a la API.
2. **Con la casilla marcada:** el botón pasa a «Pagando…» [L 31] con `aria-busy`, mismo ancho, y bajo el botón aparece `p role="status" text-base`: «Abriendo Webpay…» **[NUEVO]**. La pantalla genera una `Idempotency-Key` nueva (`crypto.randomUUID()`), que vive solo en la memoria de ese toque.
3. **Con la `url` y el `token`:** la pantalla arma un `form` oculto con `method="post"`, `action={url}` y un `input type="hidden" name="token_ws"`, y lo envía. **Es una navegación de página completa**, en la misma pestaña. El token no se guarda en ningún lado ni se escribe en la dirección de MATU.
4. **Si la persona vuelve con el botón Atrás** del navegador antes de terminar en Webpay, la página puede volver desde la memoria del navegador con «Pagando…» congelado. Al recibir `pageshow` con `persisted`, la pantalla deja el botón como estaba y vuelve a pedir el pedido: si el servidor dice que hay un pago en curso, muestra 6.2.

### 4.6 Errores al tocar «Pagar»

Todos van **sobre el botón**, en la parte de decisión, y el botón vuelve a «Pagar `{total}`». El foco va a la `Nota` (`enfocable`), que se anuncia una vez. Ninguno es `pronto`: nada se perdió y nada se cobró.

| Caso | `type` | Dónde y cómo | Texto | Origen |
|---|---|---|---|---|
| Webpay no responde | el `type` de 3.1 (`pasarela-no-disponible`) | `Nota tono="atenta"` con `CloudOff`, `rol="alert"` | Webpay no responde ahora. No se cobró nada. Inténtalo en unos minutos. | [A5.4] |
| MATU no responde (red o 5xx) | — | Igual | No pudimos abrir Webpay. Revisa tu conexión y vuelve a intentarlo. No se cobró nada. | **[NUEVO]**, con la forma de [L 8] |
| El total venció | 409 `estado-pedido`, `estado: vencido` (D-62-15) | El estado vencido de MATU-61, 9.6: admin con «Volver a confirmar»; pagador con 9.11 (sección 5) | Los de 9.6 y 9.11 | [L 31] |
| El pedido cambió o se canceló | 409 `estado-pedido` con otro estado, o 412 | La fila de MATU-61, 11.2: `Nota tono="rocio"` bajo la bajada y se vuelve a leer el pedido | Este pedido cambió mientras lo revisabas. Te mostramos cómo quedó. | [L 31] |
| Ya hay un pago en curso | 409 `pago-en-curso` | 6.2 | Ya hay un pago en curso para este pedido. Espera su resultado antes de intentar de nuevo. | [A5.4] |
| Las condiciones cambiaron | el `type` de 3.1 (`condiciones-cambiaron`) | La casilla se desmarca. `MensajeError` bajo la casilla y el foco a la casilla. La pantalla vuelve a leer el resumen, que trae la versión nueva | Las condiciones del pedido cambiaron. Léelas de nuevo y marca la casilla para pagar. | **[NUEVO]** |
| La misma petición sigue en curso | 409 `idempotencia-en-curso` | Sin texto: «Pagando…» sigue, y la pantalla repite **una vez**, a los 2 segundos, con la misma clave. Si vuelve el mismo 409, la fila de «MATU no responde» | — | — |
| Clave reutilizada o sin clave | 422 `idempotencia-reutilizada`, 428 | Es un defecto de la pantalla, no de la persona. La fila de «MATU no responde» | — | — |
| Sin la autorización de pedidos | 403 `sin-autorizacion-pedidos`, `revision-vencida` | MATU-61, 4, 4.4 y 4.5 | Los de MATU-61 | [L 31] |

---

## 5. El pagador y los 15 minutos (D-62-14)

Sin cambios respecto de MATU-61, 9.11, y ahora con «Pagar»:
- el aviso de los 2 minutos le llega igual que a Carmen, **sin «Volver a confirmar»**: «Quedan 2 minutos para pagar este total.» [L 31];
- con el total vencido desaparecen la casilla, la frase de Webpay y «Pagar», y en su lugar va «Pasaron 15 minutos y el total venció. Pídele a quien armó el pedido que lo vuelva a confirmar.» [L 31], sin botón macizo.

Martín mide en la usabilidad si un pagador alcanza a pagar en 15 minutos (D-62-14). Para que se pueda medir, la pantalla no agrega nada que lo apure: ni cuenta regresiva ni cambio de color al acercarse.

---

## 6. Pago en curso (D-62-4, regla 1)

Mientras hay una venta `iniciada` o `autorizando`, **nadie del grupo puede cambiar el pedido**, y **cancelar siempre se puede**. La pantalla lo sabe al abrir (`pago_en_curso`, 3.2) o por un 409 `pago-en-curso` al intentar algo.

### 6.1 Para quien quiere cambiar (admin y cuidador)

**Objetivo:** Carmen entiende por qué no puede cambiar el pedido ahora, que no es un error y qué hacer.

**En el pedido (`/insumos/pedido`):** el carrito **sin controles**, como con el total confirmado (MATU-61, 7.9): la cantidad como texto, «Si falta: …» como frase, sin «Sacar del pedido», sin «Cambiar dirección» ni «Cambiar teléfono», sin «Cambiar el pedido». En lugar de la nota «Ya confirmaste el total…», bajo la bajada:

```
│ ┃ (💳) Hay un pago en curso para   │  Nota atenta borde, CreditCard
│ ┃ este pedido. Espera su resultado │
│ ┃ antes de cambiarlo.              │
│ ┃ Si alguien salió de Webpay sin   │
│ ┃ terminar, se cierra solo en menos│
│ ┃ de 15 minutos.                   │
│ ┃ [ Revisar de nuevo ]             │  Boton secundario
```

En el pie: «Productos: `{precio}`», `Boton variante="secundario"` «Ver el resumen» [L 31] (lleva al resumen sin confirmar) y «Cancelar pedido». **Sin «Ver el total»**: volver a confirmar respondería 409. No hay ningún elemento en `turquesa` macizo.

**En el resumen, para el cuidador:** el aviso de los 2 minutos y el vencido van **sin «Volver a confirmar»**, y la misma `Nota` va en la parte de decisión, en el lugar de la frase «Pagan quien administra…».

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Aviso | `Nota tono="atenta" borde` con `CreditCard` `aria-hidden`. Al abrir, sin `rol` (es el estado de la página, y el foco va al `h1`). Después de un 409, `rol="alert"` y recibe el foco (`enfocable`) | Hay un pago en curso para este pedido. Espera su resultado antes de cambiarlo. | [A5.4] |
| Segunda frase | En la misma `Nota`, otro `p` | Si alguien salió de Webpay sin terminar, se cierra solo en menos de 15 minutos. | **[NUEVO]**: sin ella, Carmen no sabe si espera un minuto o un día. Los 15 minutos son los del retorno que tarda (7.3) |
| Botón | `Boton variante="secundario"` dentro de la `Nota` (`Acciones`). Vuelve a pedir el pedido | Revisar de nuevo · mientras pide: Revisando… | **[NUEVO]** |
| Sigue en curso | `anunciar(…, 'status')` | Todavía hay un pago en curso. | **[NUEVO]** |
| Ya terminó | La pantalla se redibuja con lo que corresponda (pagado: 8; sin pagar: el carrito de antes) y `anunciar(…, 'status')` | El pago terminó. Te mostramos cómo quedó el pedido. | **[NUEVO]** |

**Por qué `atenta` y no `rocio`:** es algo que impide hacer lo que Carmen vino a hacer, por un tiempo. `rocio` es para explicar el producto (DISENO.md 3, «Rótulos del piloto»). No es `pronto`: nada se perdió.

### 6.2 Para quien quiere pagar (admin y pagador)

En el resumen, **desaparecen la casilla, la frase de Webpay y «Pagar»**, y en su lugar va:

```
│ ┃ (💳) Ya hay un pago en curso     │  Nota atenta borde, CreditCard
│ ┃ para este pedido. Espera su      │
│ ┃ resultado antes de intentar de   │
│ ┃ nuevo.                           │
│ ┃ Si saliste de Webpay sin         │
│ ┃ terminar, se cierra solo en menos│
│ ┃ de 15 minutos.                   │
│ ┃ [ Revisar de nuevo ]             │
│ No pagar no tiene costo.           │
│ Cancelar pedido                    │  (solo admin)
```

| Parte | Texto | Origen |
|---|---|---|
| Aviso | Ya hay un pago en curso para este pedido. Espera su resultado antes de intentar de nuevo. | [A5.4] |
| Segunda frase | Si saliste de Webpay sin terminar, se cierra solo en menos de 15 minutos. | **[NUEVO]**, en tú: quien paga puede ser quien salió |
| Botón y anuncios | Los de 6.1 | — |

- **El admin ve este aviso en el resumen y el de 6.1 en el pedido:** en el resumen viene a pagar, en el pedido viene a cambiar.
- **Con pago en curso no se muestra el aviso de los 2 minutos ni «Volver a confirmar»**, aunque el total esté por vencer o vencido: volver a confirmar respondería 409, y si Transbank aprueba un pago que empezó con el total vigente, se respeta (D-62-4, regla 2). La boleta sigue con su hora o con «Venció».
- **Sin elemento en `turquesa` macizo.**

### 6.3 Cancelar con un pago en curso

Cancelar siempre se puede (D-62-4). El diálogo de MATU-61, 10, suma un párrafo **solo si hay un pago en curso**:

```
┌──────────────────────────────────┐
│ ¿Cancelar este pedido?           │  h2 text-xl font-bold
│ No tiene costo.                  │  p text-base
│ Hay un pago en curso. Si Transbank│  p text-base font-bold
│ lo aprueba, lo anulamos completo │
│ el mismo día, a la misma tarjeta.│
│ [ Cancelar pedido ] Seguir con   │  peligroPrincipal · texto
│                     el pedido    │
└──────────────────────────────────┘
```

| Parte | Texto | Origen |
|---|---|---|
| Párrafo | Hay un pago en curso. Si Transbank lo aprueba, lo anulamos completo el mismo día, a la misma tarjeta. | **[NUEVO]**, con las condiciones 0.2 §3 y la política §10 [A5.1] |
| Hecho | Cancelamos el pedido. Si el pago en curso se aprueba, lo anulamos completo el mismo día. | **[NUEVO]**: «No se cobró nada.» [L 31] no es seguro todavía |

En negrita porque es lo único del diálogo que dice que puede moverse dinero.

### 6.4 Retirar la autorización de pedidos

En la confirmación de MATU-61, 12.2, después del punto «Cancelamos sin costo los pedidos sin pagar…», va un punto nuevo, **siempre** (no depende de que haya un pago en curso, para no pedir otra lectura):

> Si hay un pago en curso y se aprueba, lo anulamos completo el mismo día. [A5.4]

---

## 7. La vuelta de Webpay y el comprobante (`/insumos/pedido/pago`)

**Objetivo:** quien pagó sabe, en una sola lectura, si se cobró o no, cuánto, y qué hacer ahora.

### 7.1 Al llegar desde Webpay

```
llega a /insumos/pedido/pago con parámetros de Transbank
  ├─ lee los parámetros y los borra con history.replaceState (antes de cualquier otra cosa)
  ├─ recupera la sesión de la app como al recargar (si no puede: 7.10)
  ├─ muestra 7.2 «Estamos confirmando tu pago»
  └─ POST /v1/pagos/retorno
        ├─ aprobado ─────────► 7.4 Pagaste tu pedido
        ├─ aprobado_tardio ──► 7.4 con la nota de 7.6
        ├─ no_aprobado ──────► 7.11 El pago no se hizo
        ├─ abandonado ───────► 7.12 Saliste de Webpay sin pagar
        ├─ tiempo_agotado ───► 7.12 (variante)
        ├─ pendiente ────────► 7.3 La respuesta tarda
        ├─ anulado ──────────► 7.9 Anulamos tu pago
        ├─ ya_registrado ────► el estado que corresponda, con la nota de 7.8
        └─ red o 5xx ────────► 7.3 (se reintenta: el retorno es idempotente)
```

- **Lo primero que hace la pantalla es limpiar la dirección**, para que el token no quede en el historial, en una captura ni en una pestaña compartida.
- **Fija la persona** con `persona_cuidada_id` de la respuesta: después de una navegación completa, la persona elegida en memoria se perdió.
- **Las pestañas se ven** con «Pedido» activa. No hay `Volver`: no hay de dónde volver dentro de la app.

### 7.2 Estamos confirmando tu pago

**Jerarquía:** el título y nada más que hacer.

```
┌────────────────────────────────────┐
│ Insumos   Lista de insumos         │
│ Catálogo  Pedido                   │
│ ┌────┐                             │  baldosa size-16 rounded-2xl bg-rocio
│ │ 💳 │                             │  CreditCard size-9 text-turquesa, aria-hidden
│ └────┘                             │
│ Estamos confirmando tu pago        │  h1 titular text-3xl
│ No cierres esta pantalla.          │  p text-lg, en la región aria-busy
└────────────────────────────────────┘
```

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Baldosa | `UnaColumna tono="rocio"`, `CreditCard` | — | — |
| Título | `h1 titular text-3xl @2xl/main:text-4xl` | Estamos confirmando tu pago | [A5.4] |
| Texto | `p text-lg max-w-prose`. La región lleva `aria-busy="true"` | No cierres esta pantalla. | [A5.4] |

- **Sin animación de espera.** Ni rueda que gira ni puntos que laten: el texto dice qué pasa. Con el retorno normal dura menos de un segundo.
- **Pantalla ancha:** igual, una columna alineada a la izquierda de `max-w-3xl`. Sin columna derecha.
- **Sin elemento en `turquesa` macizo.**

### 7.3 La respuesta tarda

**Cuándo:** el retorno responde `pendiente`, o no responde en 10 segundos, o falla la red. También si Transbank no respondió al `commit` y lo hará la conciliación (D-62-5).

```
│ ┌────┐                             │  baldosa bg-atenta-fondo, Clock text-atenta
│ └────┘                             │
│ Estamos confirmando tu pago        │  h1, el mismo
│ ┃ Todavía no tenemos la respuesta │  Nota atenta borde, Clock, rol="status"
│ ┃ de Transbank. Si pagaste, no    │
│ ┃ pagues de nuevo: te avisamos    │
│ ┃ aquí apenas la tengamos, en     │
│ ┃ menos de 15 minutos.            │
│ [ Revisar ahora ]  Ir a tu pedido  │  secundario · texto
```

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Título | El mismo `h1`: el foco no se mueve | Estamos confirmando tu pago | [A5.4] |
| Aviso | `Nota tono="atenta" borde` con `Clock`, `rol="status"`, en lugar de «No cierres esta pantalla.» | Todavía no tenemos la respuesta de Transbank. Si pagaste, no pagues de nuevo: te avisamos aquí apenas la tengamos, en menos de 15 minutos. | [A5.4] |
| Revisar | `Boton variante="secundario"` | Revisar ahora · Revisando… | **[NUEVO]** |
| Salida | `Boton variante="texto"`, lleva a `/insumos/pedido` (donde verá 6.1 o 6.2) | Ir a tu pedido | [L 31] |
| Sigue igual | `anunciar(…, 'status')` | Todavía no tenemos la respuesta. | **[NUEVO]** |

- **«Te avisamos aquí» se cumple:** mientras la pantalla está visible (`document.visibilityState`), vuelve a preguntar sola cada 15 segundos, sin decirlo y sin números que cambien. Cuando llega el resultado, cambia el `h1` y el foco va a él (2.1). Pasados 15 minutos deja de preguntar sola y queda «Revisar ahora».
- **No es un error.** `atenta`, nunca `pronto`. No hay botón de pagar en esta pantalla: es lo que evita el doble pago.
- **Sin elemento en `turquesa` macizo.**

### 7.4 Pagaste tu pedido (el comprobante)

**Objetivo:** Carmen ve que pagó una sola vez el total que vio, guarda el comprobante y sabe qué le garantizamos.

**Jerarquía:**
1. «Pagaste tu pedido» y «Pagaste `{total}` una sola vez».
2. El comprobante: total pagado, la tarjeta y el sello del piloto.
3. Lo que te garantizamos, el correo, imprimir.

#### 7.4.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Insumos   Lista de insumos         │
│ Catálogo  Pedido                   │
│ ┌────┐                             │  baldosa bg-ok-fondo, CircleCheck text-ok
│ └────┘                             │
│ Pagaste tu pedido                  │  h1 titular text-3xl
│ Pagaste $57.460 una sola vez. Es el│  bajada text-lg max-w-prose, cifra font-bold
│ total que viste antes de pagar.    │
│ ┃(i) Precios de ejemplo. …         │  AvisoPiloto, una vez
│ ┌ Comprobante ───────────────────┐ │  section aria-labelledby, la boleta
│ │ Pedido 4821                    │ │  h2 text-xl font-bold, ReceiptText
│ │ 11/11/2026 a las 16:41         │ │  text-base, dos cifras
│ │ ┃(i) Pago de prueba. No se     │ │  Nota atenta, Info: el sello (7.5.2)
│ │ ┃ cobró dinero real. Este      │ │
│ │ ┃ comprobante no es una boleta.│ │
│ │ Pañal adulto M x30             │ │  text-lg font-bold
│ │ 2 × $12.990            $25.980 │ │  text-lg tabular-nums, cifra a la derecha
│ │ Suplemento vainilla x12        │ │
│ │ 1 × $26.490            $26.490 │ │
│ │ Toallitas húmedas x80          │ │
│ │ 1 × $1.000              $1.000 │ │
│ │ Envío (uno por pedido)  $3.990 │ │  text-lg
│ │ ══════════════════════════════ │ │  hr border-t-2 border-tinta
│ │ Total pagado           $57.460 │ │  text-2xl font-bold
│ │ [✓ Pagado]                     │ │  Etiqueta ok, Check
│ │ Tarjeta de débito terminada en │ │  text-base
│ │ 4051                           │ │
│ │ Código de autorización 123456  │ │  text-base
│ └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │  borde cortado
│ Datos del pedido                   │  h2 titular text-2xl
│ Vende: MATU, piloto académico, sin │  text-base
│ persona jurídica.                  │
│ Entrega: Entre 24 y 48 horas       │
│ hábiles                            │
│ Condiciones aceptadas: versión 0.2,│
│ el 11/11/2026                      │
│ Condiciones del pedido, versión 0.2│  enlace solo min-h-12 (P4)
│ (se abre en otra pestaña)          │
│ Lo que te garantizamos             │  h2 titular text-2xl
│ · Derecho a retracto: tienes 10    │  ul text-base max-w-prose
│   días desde que lo recibes.       │
│ · Si un producto no llega, te      │
│   devolvemos su precio el mismo    │
│   día, a la misma tarjeta. Cuándo  │
│   lo ves en tu cuenta depende de   │
│   tu banco.                        │
│ · Quien administra el grupo puede  │
│   cancelar sin costo mientras el   │
│   comercio no empiece a preparar.  │
│ · ¿Algo no está bien? Escríbenos a │
│   cuidaconmatu@gmail.com.          │  EnlaceEnFrase mailto
│ En el piloto, el comprobante no se │  p text-base text-tenue (7.5.4)
│ envía por correo. Imprímelo o      │
│ guárdalo en PDF si lo necesitas.   │
│ [ Imprimir o guardar en PDF ]      │  Boton secundario, Printer
│ Ir a tu pedido                     │  Boton texto
└────────────────────────────────────┘
```

**Orden del DOM, el mismo en todos los anchos:** título y bajada, aviso del piloto, comprobante, datos del pedido, garantías, correo y acciones.

#### 7.4.2 Pantalla ancha (1280 y 1920 px)

```
┌───────────────┬───────────────────────────────────────────────────────────────────────────┐
│ (M) MATU      │ Insumos   Lista de insumos   Catálogo   Pedido                            │
│               │ (✓) Pagaste tu pedido                                                     │
│               │ Pagaste $57.460 una sola vez. Es el total que viste antes de pagar.       │
│               │ ┃(i) Precios de ejemplo. …                                                │
│               │ Datos del pedido                           ┌ Comprobante ────────────────┐│
│               │ Vende: MATU, piloto académico, …           │ Pedido 4821                 ││
│               │ Entrega: Entre 24 y 48 horas hábiles       │ 11/11/2026 a las 16:41      ││
│               │ Condiciones aceptadas: versión 0.2, …      │ ┃ Pago de prueba. No se … ││
│               │ Lo que te garantizamos                     │ Pañal adulto M x30          ││
│               │ · Derecho a retracto: …                    │ 2 × $12.990        $25.980  ││
│               │ · Si un producto no llega, …               │ …                           ││
│               │ · Quien administra el grupo puede …        │ Total pagado       $57.460  ││
│               │ · ¿Algo no está bien? Escríbenos a …       │ [✓ Pagado]                  ││
│               │ En el piloto, el comprobante no se envía…  │ Tarjeta de débito … 4051    ││
│               │ [ Imprimir o guardar en PDF ]  Ir a tu ped…│ Código de autorización …    ││
│               │                                            └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘│
└───────────────┴───────────────────────────────────────────────────────────────────────────┘
```

- **Dos columnas desde `@3xl/main`**, como el resumen: `grid grid-cols-1 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-x-10`. A la derecha el comprobante, `@3xl/main:sticky @3xl/main:top-6` con `max-h-[calc(100dvh-3rem)] overflow-y-auto [scrollbar-width:thin]`. **El orden del DOM no cambia**: el comprobante va antes que los datos en el DOM, y se ubica a la derecha con `@3xl/main:col-start-2 @3xl/main:row-start-1 @3xl/main:row-span-3`, como la línea de MATU-61 (7.11). Así el lector y el Tab leen primero el comprobante, como en el teléfono.
- **El título, la bajada y el aviso del piloto van arriba, a todo el ancho.** La baldosa va a la izquierda del título desde `@xl/main` (`@xl/main:flex-row @xl/main:items-center`), y encima en el teléfono.
- **A 1920 px** el `main` llega a `max-w-7xl` y el comprobante mide unos 470 px: no se estira.

### 7.5 Las partes del comprobante

#### 7.5.1 El encabezado y los renglones

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Baldosa | `UnaColumna tono="ok"` (el tono nuevo del componente, ver «Tokens» al inicio) con `CircleCheck` `size-9` `aria-hidden` | — | — |
| Título | `h1 titular` | Pagaste tu pedido | [A5.4] |
| Bajada | `p text-lg max-w-prose`, la cifra en `cifras font-bold` | Pagaste `{total}` una sola vez. Es el total que viste antes de pagar. | **[NUEVO]**, de la escena 28 de la demo («Se cobró $57.460 una sola vez. Es el total que viste antes de pagar.»), en tú y con «Pagaste» para no decir «se cobró» junto a «No se cobró dinero real» |
| Contenedor | La boleta de MATU-61 (9.4): `section aria-labelledby`, `rounded-t-lg bg-hoja px-4 @3xl/main:px-7 angosto:px-2 pt-5 pb-8 ring-1 ring-linea` y la máscara del borde cortado | — | — |
| Título del comprobante | `h2 text-xl font-bold` con `ReceiptText` `size-5 text-turquesa` `aria-hidden`. **Nunca «Boleta»** | Comprobante | **[NUEVO]**. En el `aria-labelledby` del `section`, también la referencia: el lector dice «Comprobante, Pedido 4821» |
| Referencia | `p text-lg font-bold` | Pedido `{referencia}` | [A5.4] |
| Fecha | `p text-base`, dos `cifras` | `{DD/MM/AAAA}` a las `{HH:MM}` | [A5.4] |
| Sello del piloto | 7.5.2 | — | — |
| Producto | Por línea, un `div`: el nombre en `p text-lg font-bold break-words`, y debajo un renglón `flex justify-between gap-4 text-lg tabular-nums` con «`{cantidad}` × `{precio}`» a la izquierda y el subtotal en `cifras` a la derecha | `{producto}` · `{cantidad}` × `{precio}` · `{subtotal}` | [A5.4] («productos con cantidad y precio»), con la forma de [L 31] |
| Envío | Renglón `flex justify-between gap-4 text-lg` | Envío (uno por pedido) | [L 31] |
| Separador | `hr border-0 border-t-2 border-tinta` | — | — |
| Total pagado | Renglón `text-2xl font-bold`, la cifra en `cifras` | Total pagado | [A5.4] |
| Marca | `Etiqueta tono="ok"` con `Check` `size-4` `aria-hidden` | Pagado | **[NUEVO]**: el estado con palabra y forma (DISENO.md 4.3) |
| Tarjeta, solo quien pagó | `p text-base`, los cuatro dígitos en `cifras` | Tarjeta de débito terminada en `{ultimos4}` · Tarjeta de crédito terminada en `{ultimos4}` · con cuotas: Tarjeta de crédito terminada en `{ultimos4}`, en `{n}` cuotas | **[AJUSTE]** de «`{Débito/Crédito}` terminada en `{últimos 4}`» [A5.4]: «Débito terminada» no concuerda. «Tarjeta de…» lo arregla y es la palabra de la demo (escena 22). Las cuotas, P5 |
| Código, solo quien pagó | `p text-base`, el código en `cifras` | Código de autorización `{codigo}` | [A5.4] |
| Quien no pagó, en lugar de los dos anteriores | `p text-base` | Lo pagó otra persona de tu grupo. | **[NUEVO]** (D-62-2: no ve la tarjeta). Sin el nombre: el contrato no lo trae y no hace falta para entender el comprobante |

- **Sin la dirección de entrega ni el teléfono** en el comprobante: se imprime y se puede reenviar. Están en el resumen y en el seguimiento (MATU-63).
- **Sin el comercio en cada línea:** quien vende es MATU («Vende: …»). El comercio que prepara es parte del seguimiento.
- **Con el texto al 200 %** (modo `angosto`), los renglones de dinero pasan a `angosto:flex-col angosto:items-start`, como la boleta de MATU-61 (13.7): la cifra baja bajo su texto, alineada a la izquierda.

#### 7.5.2 El sello del piloto (D-62-7)

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Sello | `Nota tono="atenta"` **sin `borde`**, con `Info` `aria-hidden`, **dentro del comprobante**, después de la fecha y antes de los productos. La primera frase en `font-bold` | **Pago de prueba. No se cobró dinero real.** Este comprobante no es una boleta. | [D-62-7] |

- **Por qué dentro del comprobante y no arriba de la página:** es parte del documento. Si Carmen lo imprime, le saca una captura o lo reenvía, el sello va con él. El aviso «Precios de ejemplo.» de arriba es de la pantalla (`lenguaje.md` 11) y no viaja con el comprobante.
- **Por qué van los dos:** dicen cosas distintas. El de arriba, que los precios son de ejemplo y no hay convenio. El sello, que este pago no movió dinero y que el papel no sirve como boleta. Los dos en `atenta`, uno sin borde y dentro de la boleta, para que no se lean como el mismo aviso repetido.
- **Antes de los productos y no al pie:** se lee antes de ver la cifra. Nunca junto a un botón.
- **«Boleta» aparece aquí por única vez fuera de «En este piloto no se emite boleta»**, y la niega (D-62-7, `lenguaje.md` 31 la admite).

#### 7.5.3 Datos del pedido y garantías

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Título | `h2 titular text-2xl` | Datos del pedido | **[NUEVO]** |
| Vendedor | `p text-base max-w-prose` | Vende: MATU, piloto académico, sin persona jurídica. | [A5.4] |
| Entrega | `p text-base` | Entrega: `{ventana_entrega}` → «Entrega: Entre 24 y 48 horas hábiles» | [A5.4], [L 31] |
| Condiciones | `p text-base`, la fecha en `cifras` | Condiciones aceptadas: versión `{v}`, el `{DD/MM/AAAA}` | [A5.4] |
| Enlace | Enlace solo, `inline-flex min-h-12`, `target="_blank" rel="noopener"`, a la versión aceptada (P4). Sin P4, no va | Condiciones del pedido, versión `{v}` (se abre en otra pestaña) | **[NUEVO]**, con la forma de [L 31] |
| Título | `h2 titular text-2xl` | Lo que te garantizamos | **[NUEVO]** |
| Garantías | `ul max-w-prose text-base` con `list-disc ps-5`, un `li` por frase. «Derecho a retracto:» en `font-bold` | Derecho a retracto: tienes 10 días desde que lo recibes. · Si un producto no llega, te devolvemos su precio el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco. · Quien administra el grupo puede cancelar sin costo mientras el comercio no empiece a preparar. · ¿Algo no está bien? Escríbenos a `{correo}`. | [A5.4] |
| Correo de reclamos | `EnlaceEnFrase` `mailto:` con `canal_reclamo` | — | — |

- **El retracto en el comprobante va una vez**, en la forma general de [A5.4]. El de cada producto (con «No aplica si abres el sello del producto», [L 27]) está en el resumen, que es donde se decide. Si el analista pide la regla del sello por producto también aquí, va como una frase bajo el nombre del producto, en `text-base`.
- Todo visible sin abrir nada: ni `details` ni «Ver más».

#### 7.5.4 El correo (D-62-3)

| Caso | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Se envió (después del piloto) | `p text-base text-tenue max-w-prose`, solo para quien pagó | Te enviamos este comprobante a `{correo}`. | [A5.4] |
| En el piloto | Igual | En el piloto, el comprobante no se envía por correo. Imprímelo o guárdalo en PDF si lo necesitas. | **[AJUSTE]** de «En el piloto, el correo se prueba sin enviarse.» [A5.4]: «se prueba» es una frase del equipo, y Carmen no sabe qué hacer con ella. La nueva dice qué pasa y cómo guardar el comprobante |

Quien no pagó no ve ninguna de las dos: el correo es de otra persona.

#### 7.5.5 Las acciones

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Imprimir | `Boton variante="secundario"` con `Printer` `size-5` `aria-hidden`. Llama a `window.print()` | Imprimir o guardar en PDF | [L 21] (el de la lista) |
| Salida | `Boton variante="texto"`, lleva a `/insumos/pedido` | Ir a tu pedido | [L 31] |

- **Sin elemento en `turquesa` macizo.** El pago terminó: no hay una acción que Carmen tenga que hacer. Imprimir es útil pero no obligatorio.
- **La hoja impresa** usa el patrón de MATU-60 (`HojaImpresa`, `data-impresion`, `hidden print:block`, en un portal): solo el comprobante, en una columna, `bg-hoja text-tinta`, con el título «Comprobante · Pedido `{referencia}`», la fecha, **el sello del piloto en negrita**, los renglones, el total pagado, la tarjeta (si la ve quien imprime), los datos del pedido y las garantías. Sin las pestañas, sin el aviso de arriba y sin botones. El sello va arriba de la hoja, antes de los productos.

### 7.6 Pago tardío respetado (D-62-4, regla 2)

El comprobante de 7.4, con una `Nota` entre la bajada y el aviso del piloto:

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Nota | `Nota tono="rocio"` con `Info`, sin `rol` (se lee después del `h1`, que recibe el foco) | Tu pago llegó después de que venció el total, y lo respetamos: pagaste `{total}`, el precio que aceptaste. | [A5.4] |

- `rocio` porque explica, no advierte: no hay nada que hacer y nada salió mal.
- La ven también admin, cuidador y pagador que no pagaron, al abrir el comprobante: es parte de lo que pasó con el pedido.

### 7.7 Devoluciones

Pueden aparecer en el comprobante cuando un producto no se pudo entregar (la anulación parcial, ADR-027). Aquí se especifica cómo se ven. Cuándo se hacen es del backend y del seguimiento (MATU-63).

**Una `Nota` por devolución**, entre la bajada y el aviso del piloto, y **renglones en el comprobante**, después de «Total pagado»:

```
│ ┃ (↶) Devolvimos $26.490 a tu      │  Nota ok borde, Undo2
│ ┃ tarjeta terminada en 4051, por   │
│ ┃ Suplemento vainilla x12. Cuándo  │
│ ┃ lo ves en tu cuenta depende de tu│
│ ┃ banco.                           │
…
│ │ Total pagado           $57.460 │ │
│ │ Devolvimos: Suplemento         │ │  text-lg, cifra a la derecha
│ │ vainilla x12          −$26.490 │ │
│ │ ══════════════════════════════ │ │
│ │ Pagaste en total       $30.970 │ │  text-2xl font-bold
```

| Caso | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Hecha, para quien pagó | `Nota tono="ok" borde` con `Undo2` `aria-hidden` | Devolvimos `{monto}` a tu tarjeta terminada en `{ultimos4}`, por `{producto}`. Cuándo lo ves en tu cuenta depende de tu banco. | [A5.4] |
| Hecha, para quien no pagó | Igual | Devolvimos `{monto}` a la tarjeta con que se pagó, por `{producto}`. Cuándo se ve en la cuenta depende del banco. | **[AJUSTE]** de [A5.4], sin la tarjeta (D-62-2) |
| En curso, para quien pagó | `Nota tono="atenta" borde` con `Undo2` | Estamos devolviendo `{monto}` a tu tarjeta. Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje. | [A5.4] |
| En curso, para quien no pagó | Igual | Estamos devolviendo `{monto}` a la tarjeta con que se pagó. Si no se completa hoy, le escribimos a quien pagó. MATU nunca pide los datos de un banco por mensaje. | **[AJUSTE]** de [A5.4], sin la tarjeta y sin «te escribimos», que sería falso |
| Renglón, solo las hechas | `flex justify-between gap-4 text-lg`, la cifra en `cifras` con el signo menos (U+2212) | Devolvimos: `{producto}` · −`{monto}` | **[NUEVO]**, de la escena 33 de la demo, en pasado porque ya se hizo |
| Total después de devolver | Un segundo separador `border-t-2 border-tinta`, `text-2xl font-bold` | Pagaste en total | **[NUEVO]**, de «Pagas en total» de la escena 33, en pasado |

- **Las devoluciones en curso no restan** en el comprobante: todavía no volvió el dinero. Solo lo dice su `Nota`.
- **La devolución de todo el pedido** usa los mismos textos con «por tu pedido completo» en lugar de «por `{producto}`» **[NUEVO]**.
- **El dinero que vuelve no va en `turquesa` ni en verde suelto:** la `Nota ok` lleva palabra («Devolvimos») e ícono, y el renglón lleva el signo menos.

### 7.8 Retorno repetido

Si el retorno responde `ya_registrado` (la persona volvió dos veces desde Webpay, o recargó desde el historial), la pantalla muestra el estado que corresponde y suma, **arriba de todo lo demás**, bajo la bajada:

| Caso | Componente y tokens | Texto | Origen |
|---|---|---|---|
| El pago estaba aprobado | `Nota tono="rocio"` con `Info`, sin `rol` | Este pago ya está registrado. No se cobró dos veces. | [A5.4] |
| El pago no se había hecho | Sin nota: 7.11 o 7.12 ya dicen que no se cobró nada | — | — |

### 7.9 Pago tardío anulado (D-62-4, regla 3)

**Cuándo:** Transbank aprobó un pago de un total que ya no es el del pedido (se volvió a confirmar, se cambió o se canceló mientras se pagaba, o se retiró la autorización). MATU lo anula completo el mismo día.

```
│ ┌────┐                             │  baldosa bg-atenta-fondo, Undo2 text-atenta
│ └────┘                             │
│ Anulamos tu pago                   │  h1 titular text-3xl
│ El pedido cambió o se canceló      │  p text-lg max-w-prose
│ mientras pagabas. Anulamos tu pago │
│ de $57.460 completo, a tu tarjeta  │
│ terminada en 4051. Cuándo lo ves en│
│ tu cuenta depende de tu banco.     │
│ Pago de prueba. No se cobró dinero │  p text-base text-tenue (el sello, sin comprobante)
│ real.                              │
│ [ Ir a tu pedido ]                 │  secundario
```

| Caso | Título | Texto | Origen |
|---|---|---|---|
| La anulación ya se hizo | Anulamos tu pago | El pedido cambió o se canceló mientras pagabas. Anulamos tu pago de `{total}` completo, a tu tarjeta terminada en `{ultimos4}`. Cuándo lo ves en tu cuenta depende de tu banco. | [A5.4] el texto · **[NUEVO]** el título, mismo verbo |
| La anulación está en curso (D-62-6) | Estamos anulando tu pago | El pedido cambió o se canceló mientras pagabas. Estamos devolviendo `{total}` a tu tarjeta terminada en `{ultimos4}`. Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje. | **[NUEVO]**, con las frases de [A5.4] de la devolución en curso |
| Sello | — | Pago de prueba. No se cobró dinero real. | [D-62-7], la primera frase del sello. Aquí no hay comprobante, así que no va «no es una boleta» |
| Botón | `Boton variante="secundario"`, a `/insumos/pedido` | Ir a tu pedido | [L 31] |

- **Baldosa `atenta` con `Undo2`**, nunca `pronto`: MATU hizo lo correcto, y el dinero vuelve.
- **Sin elemento en `turquesa` macizo.** En el pedido, Carmen ve cómo quedó (el carrito de nuevo, el total nuevo o el pedido cancelado).

### 7.10 La vuelta sin la sesión de la app (P3)

Si la app no logra recuperar la sesión al volver (por ejemplo, porque pasó mucho tiempo en Webpay), la pantalla igual envía el retorno y muestra el resultado, **sin montos ni tarjeta**, y en lugar de las acciones:

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Título | El del resultado: «Pagaste tu pedido», «El pago no se hizo», «Saliste de Webpay sin pagar», «Anulamos tu pago» o «Estamos confirmando tu pago» | — | 7.2 a 7.12 |
| Texto | `p text-lg max-w-prose` | Para ver el comprobante y tu pedido, entra a MATU. | **[NUEVO]** |
| Botón | `Boton` principal, a `/entrar`. Al entrar, va a `/insumos/pedido` | Entrar | **[NUEVO]**, el de la pantalla de entrar |

Es el único estado de la vuelta con un `turquesa` macizo además de «Intentar de nuevo»: sin entrar no hay nada más que hacer.

### 7.11 El pago no se hizo

**Cuándo:** Transbank no aprobó el pago (`no_aprobado`).

```
│ ┌────┐                             │  baldosa bg-tinta/7 text-tenue, CreditCard
│ └────┘                             │
│ El pago no se hizo                 │  h1 titular text-3xl
│ Transbank no lo aprobó y no se     │  p text-lg max-w-prose
│ cobró nada. Puedes intentarlo con  │
│ otra tarjeta mientras el total siga│
│ vigente.                           │
│ Este total vale hasta las 16:45.   │  p text-base, la hora en cifras
│ [ Intentar de nuevo ]              │  principal. Único turquesa macizo
│ Ir a tu pedido                     │  texto
```

| Parte | Texto | Origen |
|---|---|---|
| Título | El pago no se hizo | [A5.4], la primera frase |
| Texto | Transbank no lo aprobó y no se cobró nada. Puedes intentarlo con otra tarjeta mientras el total siga vigente. | [A5.4] |
| Plazo, vigente | Este total vale hasta las `{HH:MM}`. | [L 31] |
| Botón, vigente | Intentar de nuevo (`Boton` principal) | [A5.4] |
| Salida | Ir a tu pedido (`texto`) | [L 31] |

- **«Intentar de nuevo» lleva al resumen** (`/insumos/pedido/resumen`), con la casilla **sin marcar**: vivía en la memoria de la página, que se perdió al ir a Webpay, y tocarla de nuevo es lo que registra la aceptación (D-62-16). El foco va al `h1` del resumen, como en toda ruta.
- **Baldosa neutra con `CreditCard`**, sin `pronto`: no se perdió nada y no es culpa de nadie. No se dice por qué no se aprobó: MATU no lo sabe, y adivinar («el cupo») confunde.
- **Si el total ya venció** al volver:

| Quién | En lugar del plazo y del botón | Origen |
|---|---|---|
| admin | «Este total venció a las `{HH:MM}`.» y el principal «Volver a confirmar», que confirma y lleva al resumen con la hora nueva (MATU-61, 9.6) | [L 31] |
| pagador | «Pasaron 15 minutos y el total venció. Pídele a quien armó el pedido que lo vuelva a confirmar.», sin botón macizo, y «Ir a tu pedido» | [L 31] |

### 7.12 Saliste de Webpay sin pagar

**Cuándo:** la persona tocó «Anular compra» en Webpay (`abandonado`), o se le acabó el tiempo allá (`tiempo_agotado`).

| Parte | `abandonado` | `tiempo_agotado` | Origen |
|---|---|---|---|
| Título | Saliste de Webpay sin pagar | Se acabó el tiempo para pagar en Webpay | [A5.4] · **[NUEVO]** |
| Texto | No se cobró nada. | No se cobró nada. | [A5.4] |
| Plazo, botón y salida | Los de 7.11, también con el total vencido | Igual | — |

Misma composición y tokens que 7.11. «Intentar de nuevo» es el único `turquesa` macizo.

---

## 8. El pedido pagado en la pestaña «Pedido»

**Objetivo:** después de pagar, cualquiera del grupo encuentra el comprobante sin buscarlo, y el observador sabe que está pagado.

Hasta que MATU-63 traiga el seguimiento, `/insumos/pedido` muestra **al final** (después del carrito o del vacío de MATU-61, 7.10), si hay un pedido pagado de la persona (P2):

```
│ ────────────────────────────────── │  mt-10 border-t border-linea pt-6
│ Pedido pagado                      │  h2 titular text-2xl
│ [✓ Pagado]                         │  Etiqueta ok, Check
│ Pedido 4821 · 11/11/2026 a las     │  text-base, cifras
│ 16:41                              │
│ Total pagado: $57.460              │  text-lg, la cifra font-bold
│ [ Ver el comprobante ]             │  Boton secundario
```

| Parte | admin, cuidador y pagador | observador | Origen |
|---|---|---|---|
| Título | Pedido pagado | Pedido pagado | **[NUEVO]** |
| Marca | `Etiqueta tono="ok"` «Pagado» con `Check` | Igual | **[NUEVO]** |
| Datos | Pedido `{referencia}` · `{DD/MM/AAAA}` a las `{HH:MM}` · Total pagado: `{total}` | Ninguno (D-62-2) | [A5.4] |
| Acción | `secundario` «Ver el comprobante», que lleva a `/insumos/pedido/pago` con el pedido en memoria | Ninguna | **[NUEVO]** |

- **Por qué al final y no arriba:** el pedido nuevo (el carrito) es lo que Carmen viene a hacer. El pagado ya terminó.
- **Sin `turquesa` macizo** en el bloque: no compite con «Ver el total» del carrito.
- Para el observador, el bloque es su única noticia del pago: «Pedido pagado» y «Pagado», nada más.

---

## 9. Lo que cambia en `matu-61-pedido.md`

Al fusionar, la especificación de MATU-61 se actualiza así (lo hago yo en `docs/diseno/` si el orquestador lo pide):
- **9.9:** «Pagar `{total}`» se construye (4 de este documento), con la frase de Webpay antes y los errores de 4.6.
- **9.11:** el pagador ve la casilla y «Pagar» (D-62-8). El cuidador no, y ve «Pagan quien administra el grupo y quien paga.».
- **10:** el párrafo del pago en curso (6.3).
- **12.2:** el punto nuevo de 6.4.
- **13.1:** el cuidador no tiene `turquesa` macizo en el resumen vigente, y con pago en curso nadie lo tiene (10.1).

---

## 10. Accesibilidad visual

### 10.1 Elementos en `turquesa` macizo, por pantalla y estado

| Pantalla y estado | Único macizo |
|---|---|
| Resumen vigente, admin y pagador (4) | «Pagar `{total}`» |
| Resumen vigente, cuidador (4.2) | Ninguno |
| Resumen vencido, admin y cuidador | «Volver a confirmar» (MATU-61, 9.6) |
| Resumen vencido, pagador | Ninguno |
| Pago en curso, en el pedido y en el resumen (6) | Ninguno («Revisar de nuevo» y «Ver el resumen» son secundarios) |
| Diálogo de cancelar con pago en curso (6.3) | Ninguno en `turquesa`: «Cancelar pedido» es macizo `pronto` |
| Estamos confirmando tu pago (7.2) y la respuesta tarda (7.3) | Ninguno |
| Pagaste tu pedido (7.4), con o sin 7.6, 7.7 y 7.8 | Ninguno |
| Anulamos tu pago (7.9) | Ninguno |
| Sin sesión (7.10) | «Entrar» |
| El pago no se hizo y salió sin pagar (7.11 y 7.12), vigente | «Intentar de nuevo» |
| Lo mismo con el total vencido | admin: «Volver a confirmar» · pagador: ninguno |
| Bloque «Pedido pagado» (8) | Ninguno |

### 10.2 Áreas táctiles de 48 × 48 px

Todo lo que se toca mide `min-h-12` (51 px): «Pagar», la casilla con su etiqueta, el enlace de las condiciones (enlace solo, `inline-flex min-h-12`), «Revisar de nuevo», «Revisar ahora», «Intentar de nuevo», «Ir a tu pedido», «Imprimir o guardar en PDF», «Ver el comprobante», «Entrar» y el `mailto` de reclamos (enlace en frase con el `::after`, DISENO.md 6). Entre la casilla y «Pagar» está la frase de Webpay: el pulgar no toca uno por el otro.

### 10.3 Contraste (valores de DISENO.md, sin colores nuevos)

| Elemento | Colores | Contraste |
|---|---|---|
| Comprobante: texto y cifras | `tinta` sobre `hoja` | 14:1 o más en los dos temas |
| Frase de Webpay, el correo | `tenue` sobre `papel` o `hoja` | 6,4:1 o más en claro, 8,1:1 o más en oscuro |
| Sello del piloto, pago en curso, tarda, anulado, devolución en curso | `tinta` sobre `atenta-fondo`, ícono `atenta` | 5,9:1 el semántico sobre su fondo; el texto en `tinta`, más |
| «Pagado», devolución hecha, baldosa de «Pagaste» | `ok` sobre `ok-fondo` | 5,9:1 en claro. En oscuro lo mido en la revisión (`#8FD9A8` sobre `#13301F`) |
| Baldosa neutra de «El pago no se hizo» | `tenue` sobre `tinta/7` | Decorativa: el título dice el estado. Igual la mido (3:1 o más, por ser un ícono con significado) |
| Candado de «Pagar» | `papel` sobre `turquesa` | 6,0:1 en claro, 9,4:1 en oscuro |

### 10.4 Foco

- El foco base (contorno de 3 px en `turquesa`, 2 px de separación) en todo lo que se toca.
- Al llegar a `/insumos/pedido/pago` y cada vez que cambia el resultado, al `h1` (2.1).
- Después de un error al pagar (4.6) y de un 409 `pago-en-curso`, a la `Nota` del aviso (`enfocable`, sin contorno). Con la casilla sin marcar o las condiciones cambiadas, a la casilla.
- Después de «Revisar de nuevo» o «Revisar ahora», el foco **no se mueve** si nada cambió (se anuncia), y va al `h1` si cambió el resultado.
- El diálogo de cancelar, como en MATU-61, 10.
- **Lo fijo abajo no tapa el foco:** el `scroll-padding-bottom` de la capa base ya cubre la barra de secciones (DISENO.md 3).

### 10.5 Regiones vivas

| Qué | Región |
|---|---|
| «Abriendo Webpay…» | `p role="status"` junto al botón, con `aria-busy` en el botón |
| El resultado de la vuelta (7.2 a 7.12) | Ninguna aparte: el `h1` recibe el foco y el `<title>` cambia |
| «Estamos confirmando tu pago» mientras espera | `aria-busy` en la región del texto |
| La respuesta tarda (7.3) | `Nota` `rol="status"`, una vez |
| Revisar, sin cambios | `anunciar(…, 'status')` |
| Errores al pagar (4.6) y el 409 `pago-en-curso` | `rol="alert"`, una vez |
| Pago en curso al abrir, pago tardío, retorno repetido, devoluciones | Sin `rol`: son el estado de la página y se leen después del `h1` |

### 10.6 Estado nunca solo por color

| Estado | Palabra | Forma |
|---|---|---|
| Pagado | «Pagaste tu pedido», «Pagado», «Total pagado» | `CircleCheck`, `Check` |
| No se hizo, salió sin pagar | El título y «No se cobró nada.» | `CreditCard` en baldosa neutra |
| Confirmando | «Estamos confirmando tu pago» | `CreditCard` en baldosa `rocio` |
| Tarda | «Todavía no tenemos la respuesta…» | `Clock` |
| Pago en curso | «Hay un pago en curso…» | `CreditCard` en la `Nota` |
| Anulado, devolución | «Anulamos», «Devolvimos», «Estamos devolviendo» | `Undo2`, y el signo menos en el renglón |
| Sello del piloto | «Pago de prueba…» | `Info` |

### 10.7 Texto al 200 % a 320 px (160 px de app, modo `angosto`)

- Todo en una columna. El comprobante, las notas y la boleta pasan a `px-2`.
- Los renglones de dinero del comprobante pasan a `angosto:flex-col angosto:items-start` (la cifra bajo su texto). «$57.460», «−$26.490», «16:41» y «4051» van en `cifras` y no se parten.
- «Pagar $57.460» cabe en dos renglones del botón si hace falta: el texto del botón envuelve, el relleno es el de su variante (`angosto:px-3`), y el monto va en `cifras` para no partirse.
- Los botones de las notas («Revisar de nuevo») van a todo el ancho, uno bajo otro (DISENO.md 3, `angosto:`).
- La baldosa va encima del título en todos los anchos menores que `@xl/main`.
- `document.documentElement.scrollWidth` igual a `clientWidth`.

### 10.8 Movimiento

Sin transiciones al llegar ni al cambiar de estado. Sin animación de espera. Las notas que aparecen después de una acción usan el fundido `aparecer` de 180 ms, y con `prefers-reduced-motion` aparecen de inmediato (ya en la capa base).

### 10.9 Tema oscuro, proyector e impresión

Solo tokens. En la revisión miro la `Etiqueta ok` y la baldosa `ok` en oscuro, el sello `atenta` dentro de la boleta y la máscara del borde cortado. Ningún texto de estas pantallas usa `text-sm`. **La hoja impresa** se revisa con la vista previa del navegador en los dos temas: tiene que salir en tinta oscura sobre blanco, con el sello legible.

---

## 11. Lo que el frontend no debe hacer

- Guardar el token de Transbank, la `url` de Webpay, la `Idempotency-Key`, el resultado o el comprobante en `localStorage`, `sessionStorage`, la URL o el historial (C18). Los parámetros de la vuelta se borran antes de todo con `history.replaceState`.
- Abrir Webpay en un `iframe`, en una ventana emergente o en otra pestaña.
- Deshabilitar «Pagar». Se valida al tocarlo.
- Mostrar «Pagar» con el total vencido, con un pago en curso o al cuidador.
- Mostrar un botón de pagar mientras la respuesta tarda (7.3).
- Calcular el total, lo devuelto o «Pagaste en total» por su cuenta: los montos vienen del servidor. La resta de 7.7 la entrega el contrato o se calcula solo con montos del servidor, en pesos enteros.
- Ocultar en pantalla un dato de tarjeta que la vista de un rol trajo (2.3): si llega, es un defecto del contrato.
- Escribir «Boleta» como título del comprobante, «Total con IVA», «rechazado», «fallido», «inválido», «token», «reserva» o «monto real».
- Mostrar una cuenta regresiva o animar la espera.
- Escribir colores, tamaños o sombras a mano.

---

## 12. Textos para `lenguaje.md`, sección nueva «Pago (MATU-62)»

**Regla de la sección.** Se paga en Webpay, la página de Transbank, y MATU no ve la tarjeta. Se dice «no se hizo», «saliste sin pagar» y «no se cobró nada», nunca «rechazado» ni «fallido». El documento se llama «Comprobante», nunca «Boleta», y lleva el sello «Pago de prueba. No se cobró dinero real. Este comprobante no es una boleta.» mientras dure el piloto. Todos los precios llevan el IVA incluido: «Total» y «Total pagado», nunca «con IVA». El detalle de la tarjeta lo ve solo quien pagó. No se repite lo que ya está en la sección 31.

**Ajustes a la sección 31:**
- La regla de «Boleta» admite «Este comprobante no es una boleta.» (D-62-7).
- El pagador también ve «Quedan 2 minutos para pagar este total.», sin «Volver a confirmar» (D-62-14).
- En «Retirar», después de «Cancelamos sin costo los pedidos sin pagar…», el punto «Si hay un pago en curso y se aprueba, lo anulamos completo el mismo día.».

| Dónde | Texto | Origen |
|---|---|---|
| `<title>` | El título de cada estado más « · MATU» | **[NUEVO]** |
| **Antes de pagar** | | |
| Antes de Webpay | Te llevamos a Webpay, la página de pago de Transbank. MATU no ve los datos de tu tarjeta. | [A5.4] |
| Pagar | Pagar {total} · Pagando… · Abriendo Webpay… | [L 31] · **[NUEVO]** |
| Cuidador | Pagan quien administra el grupo y quien paga. | [A5.4] |
| Webpay no responde | Webpay no responde ahora. No se cobró nada. Inténtalo en unos minutos. | [A5.4] |
| Sin conexión | No pudimos abrir Webpay. Revisa tu conexión y vuelve a intentarlo. No se cobró nada. | **[NUEVO]** |
| Condiciones cambiaron | Las condiciones del pedido cambiaron. Léelas de nuevo y marca la casilla para pagar. | **[NUEVO]** |
| **Pago en curso** | | |
| Quien quiere cambiar | Hay un pago en curso para este pedido. Espera su resultado antes de cambiarlo. · Si alguien salió de Webpay sin terminar, se cierra solo en menos de 15 minutos. | [A5.4] · **[NUEVO]** |
| Quien quiere pagar | Ya hay un pago en curso para este pedido. Espera su resultado antes de intentar de nuevo. · Si saliste de Webpay sin terminar, se cierra solo en menos de 15 minutos. | [A5.4] · **[NUEVO]** |
| Revisar | Revisar de nuevo · Revisando… · Todavía hay un pago en curso. · El pago terminó. Te mostramos cómo quedó el pedido. | **[NUEVO]** |
| Cancelar con pago en curso | Hay un pago en curso. Si Transbank lo aprueba, lo anulamos completo el mismo día, a la misma tarjeta. · Cancelamos el pedido. Si el pago en curso se aprueba, lo anulamos completo el mismo día. | **[NUEVO]** |
| **La vuelta** | | |
| Al volver | Estamos confirmando tu pago · No cierres esta pantalla. | [A5.4] |
| La respuesta tarda | Todavía no tenemos la respuesta de Transbank. Si pagaste, no pagues de nuevo: te avisamos aquí apenas la tengamos, en menos de 15 minutos. · Revisar ahora · Revisando… · Todavía no tenemos la respuesta. · Ir a tu pedido | [A5.4] · **[NUEVO]** · [L 31] |
| No se aprobó | El pago no se hizo · Transbank no lo aprobó y no se cobró nada. Puedes intentarlo con otra tarjeta mientras el total siga vigente. · Intentar de nuevo | [A5.4] |
| Salió sin pagar | Saliste de Webpay sin pagar · No se cobró nada. | [A5.4] |
| Se acabó el tiempo | Se acabó el tiempo para pagar en Webpay · No se cobró nada. | **[NUEVO]** |
| Retorno repetido | Este pago ya está registrado. No se cobró dos veces. | [A5.4] |
| Sin sesión | Para ver el comprobante y tu pedido, entra a MATU. · Entrar | **[NUEVO]** |
| **Pagaste** | | |
| Título y bajada | Pagaste tu pedido · Pagaste {total} una sola vez. Es el total que viste antes de pagar. | [A5.4] · **[NUEVO]** |
| Comprobante | Comprobante · Pedido {referencia} · {DD/MM/AAAA} a las {HH:MM} · {cantidad} × {precio} · Envío (uno por pedido) · Total pagado · Pagado · Tarjeta de débito terminada en {ultimos4} · Tarjeta de crédito terminada en {ultimos4} · Tarjeta de crédito terminada en {ultimos4}, en {n} cuotas · Código de autorización {codigo} · Lo pagó otra persona de tu grupo. | **[NUEVO]** · [A5.4] · **[AJUSTE]** la tarjeta |
| Sello del piloto | Pago de prueba. No se cobró dinero real. Este comprobante no es una boleta. | [D-62-7] |
| Datos del pedido | Datos del pedido · Vende: MATU, piloto académico, sin persona jurídica. · Entrega: {ventana} · Condiciones aceptadas: versión {v}, el {DD/MM/AAAA} · Condiciones del pedido, versión {v} (se abre en otra pestaña) | **[NUEVO]** · [A5.4] |
| Garantías | Lo que te garantizamos · Derecho a retracto: tienes 10 días desde que lo recibes. · Si un producto no llega, te devolvemos su precio el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco. · Quien administra el grupo puede cancelar sin costo mientras el comercio no empiece a preparar. · ¿Algo no está bien? Escríbenos a {correo}. | **[NUEVO]** el título · [A5.4] |
| Correo | Te enviamos este comprobante a {correo}. · En el piloto, el comprobante no se envía por correo. Imprímelo o guárdalo en PDF si lo necesitas. | [A5.4] · **[AJUSTE]** |
| Acciones | Imprimir o guardar en PDF · Ir a tu pedido | [L 21] · [L 31] |
| Pago tardío respetado | Tu pago llegó después de que venció el total, y lo respetamos: pagaste {total}, el precio que aceptaste. | [A5.4] |
| **Anulado y devoluciones** | | |
| Pago tardío anulado | Anulamos tu pago · El pedido cambió o se canceló mientras pagabas. Anulamos tu pago de {total} completo, a tu tarjeta terminada en {ultimos4}. Cuándo lo ves en tu cuenta depende de tu banco. · Pago de prueba. No se cobró dinero real. | **[NUEVO]** · [A5.4] · [D-62-7] |
| Anulación en curso | Estamos anulando tu pago · El pedido cambió o se canceló mientras pagabas. Estamos devolviendo {total} a tu tarjeta terminada en {ultimos4}. Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje. | **[NUEVO]** |
| Devolución hecha | Devolvimos {monto} a tu tarjeta terminada en {ultimos4}, por {producto}. Cuándo lo ves en tu cuenta depende de tu banco. · Quien no pagó: Devolvimos {monto} a la tarjeta con que se pagó, por {producto}. Cuándo se ve en la cuenta depende del banco. | [A5.4] · **[AJUSTE]** |
| Devolución en curso | Estamos devolviendo {monto} a tu tarjeta. Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje. · Quien no pagó: Estamos devolviendo {monto} a la tarjeta con que se pagó. Si no se completa hoy, le escribimos a quien pagó. MATU nunca pide los datos de un banco por mensaje. | [A5.4] · **[AJUSTE]** |
| Renglones | Devolvimos: {producto} · Pagaste en total · por tu pedido completo | **[NUEVO]** |
| **Pedido pagado** | Pedido pagado · Pagado · Pedido {referencia} · {DD/MM/AAAA} a las {HH:MM} · Total pagado: {total} · Ver el comprobante | **[NUEVO]** · [A5.4] |

**Ninguno usa** los términos de la sección 3, «rechazado», «fallido», «inválido», «token», «stock», «reserva», «monto real», «estimado» ni «con IVA». «Boleta» aparece solo en «Este comprobante no es una boleta.», que la niega.

---

## 13. Criterios visuales verificables

1. En cada pantalla y estado, **el `turquesa` macizo es el de 10.1**, y nunca hay más de uno. El cuidador no tiene ninguno en el resumen vigente.
2. **La misma cifra** en la bajada del resumen, la boleta, «Pagar `{total}`», «Pagaste `{total}`…» y «Total pagado» (sin devoluciones).
3. «Pagar» **nunca está deshabilitado**. Sin la casilla, muestra «Marca que leíste y aceptas las condiciones para pagar.» y lleva el foco a la casilla, sin llamar a la API.
4. La frase «Te llevamos a Webpay…» está **entre la casilla y «Pagar»**, y está en el `aria-describedby` del botón.
5. Al tocar «Pagar», Webpay se abre **en la misma pestaña**, en una navegación completa. No hay `iframe` ni ventana nueva (lo miro en las herramientas del navegador).
6. Al volver de Webpay, **la dirección es `/insumos/pedido/pago` sin parámetros** antes de que se vea el resultado, y el historial no tiene una entrada con `token_ws` ni `TBK_` (Atrás no lleva a una dirección con el token de MATU).
7. Nada del pago en `localStorage`, `sessionStorage` ni la URL.
8. El cuidador ve «Pagan quien administra el grupo y quien paga.» **en lugar de** la casilla y «Pagar». El pagador ve la casilla, «Pagar» y el aviso de los 2 minutos sin «Volver a confirmar».
9. **La tarjeta y el código de autorización aparecen solo para quien pagó.** Como Carmen, después de que pagó Rodrigo, el comprobante dice «Lo pagó otra persona de tu grupo.» y la respuesta de la API no trae `tarjeta` ni `codigo_autorizacion`. El observador ve solo «Pedido pagado» y «Pagado».
10. **El sello «Pago de prueba. No se cobró dinero real. Este comprobante no es una boleta.» está dentro del comprobante, antes de los productos**, y aparece también en la hoja impresa, arriba.
11. El comprobante se titula «Comprobante», nunca «Boleta». Ningún texto dice «Total con IVA», «rechazado», «fallido» ni «token» (un `grep` sobre los textos de la pantalla).
12. Con un pago en curso, el carrito no tiene controles ni «Ver el total», el resumen no tiene la casilla, «Pagar», el aviso de los 2 minutos ni «Volver a confirmar», **y «Cancelar pedido» sigue** para admin y cuidador. El diálogo de cancelar suma el párrafo de 6.3 en negrita.
13. Un 409 `pago-en-curso` al cambiar la cantidad muestra la `Nota` de 6.1 con el foco en ella, y la pantalla queda sin controles.
14. «Estamos confirmando tu pago» **no tiene animación** ni número que cambie. Pasados 10 segundos sin respuesta aparece la nota de 7.3, sin botón de pagar.
15. «El pago no se hizo» y «Saliste de Webpay sin pagar» dicen «No se cobró nada.», no usan `pronto` y llevan «Intentar de nuevo» al resumen con la casilla sin marcar.
16. Con el total vencido, «El pago no se hizo» no muestra «Intentar de nuevo»: el admin ve «Volver a confirmar» y el pagador «Pídele a quien armó el pedido…».
17. El pago tardío respetado muestra el comprobante con la nota de 7.6 en `rocio`. El anulado muestra «Anulamos tu pago» con baldosa `atenta`, sin comprobante y sin `pronto`.
18. Una devolución hecha resta en el comprobante («Devolvimos: …» con «−» y «Pagaste en total»), y una en curso **no resta**: solo su nota. La resta es exacta en pesos (57.460 − 26.490 = 30.970).
19. Cada estado se entiende **en escala de grises**: cada uno tiene palabra e ícono (10.6).
20. Todo lo que se toca mide 48 × 48 px o más.
21. A 320 px, a 360 px y con el texto al 200 % a 320 px, `document.documentElement.scrollWidth` es igual a `clientWidth` en el resumen (los tres roles), el pago en curso, los siete estados de la vuelta, el comprobante con devoluciones y el bloque «Pedido pagado». Ninguna cifra se parte.
22. Ningún texto de estas pantallas mide menos de 17 px de `font-size` calculado.
23. El aviso «Precios de ejemplo.» aparece **una vez** en el comprobante, arriba, y no aparece en 7.2, 7.3, 7.9, 7.11 ni 7.12 (no hay precios que rotular).
24. En pantalla ancha, el comprobante va a la derecha y es `sticky`, y **el orden de Tab y del lector es el mismo que a 360 px** (el comprobante antes que los datos del pedido).

---

## 14. Cómo la voy a revisar

Capturas a 320 px con el texto al 200 %, 360 px, 1280 px y 1920 px, en tema claro y oscuro, con la semilla del catálogo y un pedido sintético para María Soto (Carmen como admin, Rodrigo como pagador, un cuidador y un observador sintéticos), contra el ambiente de integración de Transbank (tarjetas de prueba) o la `PasarelaFalsa`:

- El resumen como Carmen, como Rodrigo y como el cuidador, vigente, con el aviso de los 2 minutos y vencido.
- «Pagar» sin la casilla, «Pagando…» con «Abriendo Webpay…», y los errores de 4.6 (Webpay detenido, backend detenido, 409 vencido, condiciones cambiadas).
- Un pago con débito y uno con crédito, la vuelta, «Estamos confirmando tu pago» y el comprobante como quien pagó y como Carmen después de que pagó Rodrigo. El bloque «Pedido pagado» como los cuatro roles.
- «Anular compra» en Webpay, el tiempo agotado y una tarjeta de prueba que Transbank no aprueba.
- El retorno repetido (Atrás desde el comprobante hasta Webpay y vuelta).
- La respuesta que tarda (la `PasarelaFalsa` sin responder el `commit`) y «Revisar ahora».
- El pago en curso: Rodrigo en Webpay y Carmen en el pedido y en el resumen, el 409 al cambiar una cantidad, y el diálogo de cancelar con su párrafo.
- El pago tardío respetado (el reloj del servidor de pruebas adelantado con el pago en Webpay) y el anulado (Carmen cancela mientras Rodrigo paga), con la anulación hecha y en curso.
- Un comprobante con una devolución hecha y otra en curso.
- La vista previa de impresión del comprobante, en los dos temas.
- La vuelta con la sesión vencida (7.10).
- Los criterios 1 a 24 de la sección 13, uno por uno.
