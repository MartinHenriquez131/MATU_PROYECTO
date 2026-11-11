# MATU-61 · Pedido: carrito y qué hacer si falta un producto · Especificación de diseño

**Versión 1.2 · 11/11/2026** · agente 6 (UI/UX) · para el frontend
**Cambios de la 1.2** (después de la revisión visual del 11-11, con las decisiones del orquestador): «No hay reserva ni cobros después.» queda como única excepción de «reserva» (secciones 1, 14 y criterio 19); el teléfono abierto tiene un solo rótulo, el `h3` (7.8.1, criterio 27); la nota «El envío y el total los ves al confirmar…» va solo en `borrador` (7.9, criterio 24).
**Cambios de la 1.1:** las decisiones de Jorge del 11-11 sobre el contrato. Se citan **JC1** a **JC7** (en su mensaje, C1 a C7) para no confundirlas con las condiciones C1 a C25 del analista, y **JC-IVA** la del IVA: en Chile todos los precios llevan el IVA incluido, y nunca se presenta como algo que se suma. Cierra los puntos O1 a O11 (sección 0), agrega «Cambiar el pedido» (9.12) y «Vaciar la dirección» (8.7), y abre O12.
**Historia:** MATU-61, el pedido de la familia hasta el total confirmado (RF-21, ADR-027, capa 3). Carmen junta productos del catálogo o de su lista de insumos, dice cuántos quiere y qué hacer si falta cada uno, deja la dirección una vez y ve el total confirmado antes de pagar. **La historia termina en el resumen con el total confirmado.** El botón «Pagar» es de **MATU-62**: aquí se dice dónde va y cómo se ve, nada más.
**Dónde se construye:** `web/`, en la app de la familia, React 19, TypeScript y Tailwind CSS v4, mobile first.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · la revisión previa del analista (`docs/legal/revision-previa-matu-61.md` del repositorio MATU) con las decisiones D1 a D12 de Jorge del 11-11, en especial C1, C2, C7, C9, C14, C15, C18, C23, C24 y C25, los textos de su sección 4 y las condiciones del pedido v0.1 (su sección 6) · `lenguaje.md` secciones 3, 8, 11, 18, 21, 22, 25.4, 26 y 27 · el informe de usabilidad de la ronda 1, hallazgo U4 · la escena 21 y la 31 de `Demo/ESPEC-ADR-027.md` (el pedido y el total vencido validados en la demo) · las especificaciones `matu-36-insumos.md`, `matu-44-retirar-autorizacion.md`, `matu-59-catalogo.md`, `matu-60-lista-insumos.md` y `matu-68-ajustes.md` de esta carpeta · el código de `web/src/familia/` (`ui.tsx`, `insumosComun.tsx`, `Shell.tsx`, `ruteo.ts`) y `web/src/compartido/ui/`.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual en pantalla. Marcas de origen:
- **[A4]** texto propuesto por el analista en su sección 4, que entra a `lenguaje.md` 31 con esta especificación;
- **[D8]**, **[D9]**, **[D10]** texto que fijó Jorge en esa decisión;
- **[JC-IVA]** texto que cambia por la decisión del IVA;
- **[L nn]** texto ya aprobado en esa sección de `lenguaje.md`;
- **[AJUSTE]** un texto de [A4] o de [L nn] que cambio, con el porqué;
- **[NUEVO]** un texto mío, que Jorge aprueba antes de construir.

Las llaves son datos de la API: `{producto}` es el `nombre` del producto, `{comercio}` el `nombre_fantasia`, `{pila}` el nombre de pila de la persona cuidada, `{precio}` en pesos enteros con punto de miles (`$12.990`), `{HH:MM}` en 24 horas, hora de Chile.

**Tokens:** **ningún token nuevo**, ningún color nuevo y ninguna regla nueva en la capa base. Todo sale de los componentes que ya existen (`Boton`, `Nota`, `Etiqueta`, `GrupoOpciones`, `CampoTexto`, `Stepper` de `insumosComun.tsx`, `MensajeError`, `Pestanas`, `Volver`, `Acciones`, `Anunciado`, `EnlaceEnFrase`) más dos piezas que el frontend arma con tokens existentes: la **boleta** (de la demo, 9.4) y el **diálogo de cancelar** (el patrón de MATU-44, 4.1).

---

## 0. Puntos abiertos y cómo se resolvieron

O1 a O11 quedaron **resueltos** el 11-11 con las decisiones de Jorge (JC1 a JC7). La columna de la derecha dice qué se decidió y dónde cambió la especificación. Queda abierto O12.

| # | Qué | Para quién | Resolución |
|---|---|---|---|
| O1 | **Quién arma, quién ve y quién confirma.** Lo fija la arquitectura 11.2, y el contrato propuesto la sigue (`docs/api/propuestos/pedido.openapi.yaml`, P5) | Jorge | **Resuelto (JC3)**, como lo proponía: **admin y cuidador** arman el carrito, eligen la regla, cambian la dirección y el teléfono, confirman el total, usan «Cambiar el pedido» y **cancelan sin pagar** (10). **El pagador** ve el carrito y el resumen sin cambiar nada, **no confirma** y no cancela. **El observador** ve el carrito sin la entrega y sin el resumen (`PedidoVistaObservador`). **Para MATU-62:** si el pagador paga, un total vencido lo tiene que volver a confirmar quien armó el pedido (9.11) |
| O2 | **Cómo entra un producto desde el catálogo.** El carrito tiene que mostrar un precio, y el cambio de precio se marca contra el precio que vio la familia (C15). Ese precio es de un comercio | Jorge y backend | **Resuelto (JC7), como lo proponía.** **«Agregar al pedido» en cada fila de comercio que dice «Hay»** (sección 5). La familia elige el comercio igual que hoy lee su precio, sin que la pantalla recomiende ninguno. Al confirmar, MATU puede moverlo a otro comercio, y el resumen lo marca |
| O3 | **Cómo pasa la lista de insumos al pedido** (D10). Hoy `LineaListaInsumos` no trae el producto del catálogo, una línea puede no estar en el catálogo (`nombre_libre`, o agregada a mano) y el envase que anotó la familia puede no ser el del catálogo (20 unidades contra «x30») | Backend y Jorge | **Resuelto (JC7), como lo proponía.** Pasan **solo las líneas con producto del catálogo**, con la cantidad que se ve en pantalla convertida a envases del catálogo y redondeada hacia arriba (6.3). El comercio de cada una es la primera oferta con «Hay» en el orden del catálogo (por `nombre_fantasia`, nunca por precio). Las que no están en el catálogo se nombran al llegar al carrito. El contrato propuesto ya suma `producto_id` a la lista (`CambioLineaListaInsumos`) y crea el pedido con los `oferta_id` que arma la pantalla |
| O4 | **Un producto de la lista que ya estaba en el carrito** | Jorge | **Resuelto (JC7), como lo proponía.** Queda **una sola línea, con la cantidad de la lista**, y se dice al llegar (6.4). Sumar daría de más: la lista ya calcula lo que falta |
| O5 | **Cambiar la dirección con el total ya confirmado.** La dirección se copia al pedido al confirmar (D4) | Backend | **Resuelto (JC1).** `confirmar` acepta también el total **vigente** y da 15 minutos nuevos. Al guardar una dirección nueva desde el resumen, la pantalla vuelve a confirmar sin cancelar y muestra la hora nueva (8.6) |
| O6 | **Dónde se leen las condiciones del pedido.** El resumen las enlaza (D6). El contrato propuesto trae `GET /v1/condiciones-pedido`, pública | Orquestador | **Resuelto (JC7), como lo proponía.** Página pública `/condiciones-pedido` de la app, con el mismo armado de `/privacidad` (MATU-75), que se abre en otra pestaña para no perder el resumen |
| O7 | **La dirección de la persona al retirar la autorización de pedidos.** D1 dice que se cancelan los pedidos sin pagar y se borra su entrega. No dice qué pasa con `persona_cuidada.direccion_entrega_id` | Analista | **Resuelto (JC6).** La dirección de la persona **se conserva** al retirar la autorización, y la confirmación del retiro lo dice (12.2). Admin y cuidador la pueden **vaciar** desde «¿Dónde lo entregamos?», con su confirmación (8.7). Cómo se llega a esa pantalla con la autorización retirada queda en O12 |
| O8 | **«Pedir estos productos» en la lista: ¿principal o secundario?** La lista ya tiene su acción principal («Compartir la lista» o «Imprimir…») y una sola cabe por pantalla | Jorge | **Resuelto (JC7), como lo proponía.** **Secundario**, en un bloque propio después de los botones de la lista (6.1). La lista sirve sin la capa 3, y sacarla no debe cambiar cuál es la acción principal |
| O9 | **«Nunca lo cambiamos por otra marca ni por otro producto»: ¿en cada línea?** El analista lo pone en el bloque «RF-21, en cada línea» | Jorge | **Resuelto (JC7), como lo proponía.** **Se ve una vez**, sobre las líneas, y **se lee en cada línea**: cada grupo «Si falta este producto» la lleva en su `aria-describedby` (7.6). Repetida en cada línea, con cuatro productos son cuatro renglones iguales en el teléfono **[AJUSTE]** |
| O10 | **El envío en el carrito.** El contrato propuesto entrega `costo_envio` ya en `borrador` (P12, por aprobar) | Jorge | **Resuelto (JC5).** El carrito **no** muestra el envío ni un total: «El envío y el total los ves al confirmar…» (7.9). Sin renglón de envío en el carrito |
| O11 | **Datos que el contrato propuesto no traía** | Backend | **Resuelto (JC1, JC4 y JC7).** El pedido se lee con `GET …/personas-cuidadas/{persona_id}/pedido-en-curso`, uno por persona (JC4, sección 3.1 y 7.2). (a) los segundos que quedan al responder (`vigencia_segundos`), para el aviso de los 2 minutos (9.5): si el contrato final no los trae, la pantalla calcula con `vence_en` y la cabecera `Date` de la respuesta, nunca con el reloj del teléfono solo. (b) `unidad` y `unidades_por_envase` en `ProductoPedido`, para el sufijo de la cantidad (7.5): si no vienen, el sufijo es «envases» («envase» con 1). (c) `ventana_entrega` también en `borrador` (JC7): el carrito muestra «Llega entre…» (7.8). (d) `confirmar` acepta `total_confirmado` vigente y da 15 minutos nuevos (JC1): «Volver a confirmar» del aviso de los 2 minutos (9.5) y cambiar la dirección desde el resumen (8.6) vuelven a confirmar sin cancelar. **El bloqueante de C23 queda resuelto** |
| O12 | **Vaciar la dirección con la autorización de pedidos retirada.** Con JC6 la dirección se conserva al retirar, pero `/insumos/pedido` muestra la autorización (4) en vez del carrito, y la entrega con «Cambiar dirección» no se ve | Jorge y backend | **Abierto.** Propongo: en Grupo familiar, en el bloque «Permiso para pedir sus insumos», cuando hay una dirección guardada, `Boton variante="texto"` «Ver la dirección de entrega» que lleva a `/insumos/pedido/direccion` (12.1), y que leer y vaciar la dirección **no pidan** la autorización `despacho` vigente (borrar lo propio no puede depender de un permiso retirado). Si el contrato las exige, nadie puede vaciarla después de retirar |

**Lo que este documento no decide:** los textos de las tres declaraciones `declaracion_pedidos_<calidad>` (los redacta el analista en la política 0.12), el texto completo de las condiciones (v0.1, aprobado), el flujo del pago, la pasarela y el comprobante (MATU-62), y el seguimiento después de pagar (MATU-63).

---

## 1. Para quién y qué

**Carmen** ve en la lista de insumos que los pañales se acaban en 6 días. Toca «Pedir estos productos», revisa cuántos, deja marcado que si faltan los busquen en otro comercio, y ve cuánto paga en total antes de decidir. Lo hace con una mano, en el teléfono, en pocos minutos.

**Rodrigo, pagador**, abre el pedido que armó Carmen, lo revisa y ve el total. En MATU-62 lo paga.

**Lo que estas pantallas nunca hacen:**
- Cambiar un producto por otra marca u otro producto, ni ofrecerlo (RF-21, ADR-027).
- Recomendar un comercio o el precio más barato, ni ordenar por precio (MATU-59, D6).
- Guardar algo del pedido en `localStorage`, `sessionStorage` ni la URL (C18). El carrito vive en el servidor como borrador. Las rutas no llevan ids ni nombres.
- Pedir sin la autorización de pedidos vigente (D1, C21).
- Comprar solas: ni el aviso de Insumos, ni «Compré», ni la lista hacen un pedido (D10).
- Presentar el IVA como algo que se suma o que aparece después (JC-IVA). Todos los precios lo llevan incluido: el total es «Total», y «IVA» solo aparece en «Precio de ejemplo · IVA incluido».
- Mostrar un contador que corre hacia atrás. El plazo se dice como hora (`Este total vale hasta las 16:45.`), y el aviso llega una vez, a los 2 minutos (10.5).
- Decir «stock», «reserva», «reservar», «monto real», «tope», «estimado», «aprox.», «carro» ni «carrito». En pantalla es «tu pedido». **La única excepción** es la frase de la boleta «No hay reserva ni cobros después.» (9.4, [A4]), que niega la reserva para que quien paga sepa que no la hay. Así la exceptúa también `lenguaje.md` 31 (decisión del orquestador del 11-11, v1.2).

---

## 2. Navegación y rutas

### 2.1 Rutas nuevas

| Ruta | Pantalla | Quién | Sección |
|---|---|---|---|
| `/insumos/pedido` | Tu pedido (el carrito). Sin la autorización, la autorización de pedidos en su lugar | admin, cuidador, pagador y observador (los dos últimos sin cambiar nada, O1) | 4 y 7 |
| `/insumos/pedido/direccion` | ¿Dónde lo entregamos? | admin, cuidador | 8 |
| `/insumos/pedido/resumen` | Antes de pagar | admin, cuidador, pagador | 9 |
| `/grupo/autorizar-pedidos` | Volver a autorizar los pedidos, desde Grupo familiar | admin, cuidador | 12.4 |
| `/condiciones-pedido` | Condiciones del pedido, pública (O6) | cualquiera | 9.8 |

Se agregan a `Ruta` y `RUTAS` de `ruteo.ts`. `seccionDe` ya reconoce las tres primeras por el prefijo `/insumos`: la sección activa de la barra es Insumos. Quien no puede ver una ruta llega a `/insumos/pedido`.

**`<title>`**, con la convención de `tituloDe` en `AppFamilia.tsx`: «Tu pedido · MATU», «¿Dónde lo entregamos? · MATU», «Antes de pagar · MATU», «Permiso para pedir sus insumos · MATU», «Condiciones del pedido · MATU». **Al llegar a cada ruta, el foco va al `h1`** (la regla de la app).

### 2.2 La cuarta pestaña de Insumos

| Pestaña | Ruta | Texto |
|---|---|---|
| 1 | `/insumos` | «Insumos» [M36] |
| 2 | `/insumos/lista` | «Lista de insumos» [L 21] |
| 3 | `/insumos/catalogo` | «Catálogo» [L 27] |
| 4 | `/insumos/pedido` | «Pedido» **[NUEVO]** |

- **Por qué una pestaña y no una sección de la barra:** cinco secciones no caben en la barra del teléfono (MATU-59, 2.1, medido). «Pedido» va al final, junto al catálogo, que es la otra pestaña de la capa 3: **sacar la capa 3 quita las dos últimas pestañas y deja las de antes como estaban.**
- **Cuándo se ve:** con la capa 3 encendida (el catálogo no responde 404), para los cuatro roles (O1). Se ve también en los estados de `/insumos` que hoy muestran solo «Insumos» y «Catálogo» (el permiso de los insumos, «Falta el permiso», «Hay que renovar»): el pedido no depende de la autorización de los insumos.
- **Las rutas `/insumos/pedido/direccion` y `/insumos/pedido/resumen` muestran las pestañas** con «Pedido» activa. Así, desde el resumen se vuelve al catálogo con un toque.
- **Medidas** (con las de MATU-59 2.2: «Insumos» 96 px, «Lista de insumos» 163 px y «Catálogo» 97 px, en negrita a `text-base` con `px-3`). «Pedido» mide unos 82 px. A 360 px el ancho útil es 328 px: primer renglón «Insumos» y «Lista de insumos» (263 px), segundo renglón «Catálogo» y «Pedido» (183 px). Son los mismos dos renglones de hoy, sin uno nuevo. Desde unos 450 px de contenido van en una fila. `Pestanas` ya envuelve: no se cambia el componente.
- **Sin número en la pestaña.** Un contador en una pestaña es una insignia de plantilla, y el número de productos no le sirve a Carmen para nada fuera del carrito.

### 2.3 Cambiar de persona

El pedido es de una persona cuidada (`pedido.persona_cuidada_id`). Al cambiar de persona en el encabezado:
- desde `/insumos/pedido`, se queda en `/insumos/pedido` y muestra el pedido de la otra persona;
- desde `/insumos/pedido/direccion` o `/insumos/pedido/resumen`, va a `/insumos/pedido`.

`Persona.cambiar` en `Shell.tsx` hoy lleva a `/insumos`, y necesita estos dos casos además del del catálogo.

---

## 3. Lo que las pantallas necesitan del contrato

El backend escribió en paralelo el contrato propuesto, `docs/api/propuestos/pedido.openapi.yaml` de esta rama, con sus decisiones 188 a 215 y las preguntas P1 a P16 en `docs/api/README.md`. Esta tabla usa sus nombres, con las decisiones de Jorge del 11-11 (JC1 a JC7). Si el backend nombra distinto una ruta nueva, manda el contrato y la pantalla no cambia.

### 3.1 El pedido

| Dato del contrato propuesto | Dónde se usa |
|---|---|
| `GET …/personas-cuidadas/{persona_id}/pedido-en-curso` (JC4): el pedido en curso de la persona, uno por persona, o que no hay ninguno. La ruta de la app no lleva el id del pedido: vive en la memoria de la página | Abrir `/insumos/pedido` (7.2) y volver a pedirlo después de un 409 o un 412 (11.2) |
| `confirmar` acepta `borrador`, `vencido` y también `total_confirmado` **vigente**, y da 15 minutos nuevos (JC1) | «Ver el total» (7.9), «Volver a confirmar» (9.5 y 9.6) y la dirección cambiada desde el resumen (8.6) |
| La vuelta de `total_confirmado` a `borrador` sin perder las líneas (JC2) | «Cambiar el pedido» (9.12) |
| Cancelar sin pagar, para admin y cuidador (JC3) | «Cancelar pedido» (10) |
| `estado` (`borrador`, `total_confirmado`, `vencido`, `cancelado`) y `etag` para `If-Match` | Qué se muestra en 7 y 9, y el 409 de 11 |
| `lineas[]`: `id`, `producto` (`id`, `nombre`, `presentacion`), `cantidad` (1 a 99), `comercio` (`nombre_fantasia`, `ficticio`), `precio_unitario`, `subtotal`, `regla_faltante` (`otro_comercio` o `quitar`) y `retracto_pierde_al_abrir`. En `borrador`, el precio y el comercio son los del carrito | La línea del carrito (7.4 a 7.6) |
| `lineas[].cambio` (`precio_antes`, `comercio_antes`), desde `total_confirmado` | El resumen (9.3) y sus marcas (9.2) |
| `salieron[]` (`producto`, `cantidad`, `comercio`) | «Ya no hay `{producto}`. Salió del pedido.» (9.2) |
| `subtotal_productos`, `costo_envio`, `total`, en pesos enteros | «Productos: …» del carrito (7.9) y la boleta (9.4) |
| `vence_en` (y los segundos que quedan, O11 a) | La hora (9.4) y el aviso de los 2 minutos (9.5) |
| `ventana_entrega`, también en `borrador` (JC7) | «Llega entre…» del carrito (7.8) y «Entrega: …» del resumen (9.7) |
| `entrega` (la dirección y `telefono_contacto` copiados al confirmar) | El resumen (9.7) |
| `resumen`: `vendedor`, `boleta`, `ventana_entrega`, `canal_reclamo` y `condiciones` (`version`, `huella`, `enlace`) | El resumen (9.7 y 9.8) |
| `precios_de_ejemplo` | El aviso del piloto, solo si es `true` |
| 409 de `confirmar`: `sin-direccion`, `pedido-vacio`, `nada-disponible`, `estado-pedido` | 11.2 |

### 3.2 Lo demás

| Dato | Dónde se usa |
|---|---|
| `ficticio` en `OfertaCatalogo` y en el comercio del pedido (D9) | «`{comercio}` (comercio ficticio)», solo si es `true` |
| `producto_id` (o `null`) en cada `LineaListaInsumos` (O3) | «Pedir estos productos» (6) |
| La autorización `despacho` en `GET …/consentimientos`, con los mismos campos que `plan_cuidado` y `consumo` | 4, 7.2 y 12 |
| Las declaraciones `declaracion_pedidos_<calidad>`, por el mismo camino que las de consumo | 4 |
| Vaciar la dirección de la persona, con `If-Match` (JC6). Se conserva al retirar la autorización de pedidos | «Vaciar la dirección» (8.7) |
| `DireccionVista` de la persona con `etag`, para `If-Match` (o `If-None-Match` la primera vez) | 7.8 y 8. **`etiqueta` y `region` no se muestran ni se piden**: tienen valor por omisión en el contrato (ver 8.2) |
| `celular_verificado` y `celular_enmascarado` de `GET /v1/cuenta` | El teléfono del carrito antes de confirmar (7.8) |
| `type` de los errores: 403 `sin-autorizacion-pedidos` y `revision-vencida` (con `finalidad: despacho`), 404, 409, 412 de la dirección, y los 422 con `errores[].campo` | 11 |
| `GET /v1/condiciones-pedido` | La página de las condiciones (9.8) |

**Lo que las pantallas no usan y no deben recibir:** `lat` y `lng` (C8), la cantidad en stock de un comercio, el RUT, la razón social, la dirección y el teléfono del comercio, y la referencia opaca que va a los comercios (C22).

---

## 4. La autorización de pedidos

**Objetivo:** Carmen entiende que pedir necesita un permiso aparte y lo da en un paso, sin perder lo que quería pedir.

**Cuándo aparece (D1):** la primera vez que se toca «Agregar al pedido» en el catálogo o «Pedir estos productos» en la lista, y cada vez que se abre `/insumos/pedido` sin la autorización vigente. Lo que se quería hacer queda **en la memoria de la página** (qué producto y de qué comercio, o qué líneas de la lista) y se hace solo al autorizar. Nunca va a la URL ni al almacenamiento del navegador.

**Jerarquía:** 1) el título y para qué sirve · 2) en qué calidad se da · 3) el aviso del cuidador de hecho si corresponde, la declaración y «Autorizar los pedidos».

### 4.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (encabezado de la app)             │
├────────────────────────────────────┤
│ Insumos   Lista de insumos         │  Pestanas, «Pedido» activa
│ Catálogo  Pedido                   │
│ ‹ Volver al catálogo               │  Volver, solo si llegó desde el catálogo o la lista
│ Antes de pedir, un permiso         │  h1 titular text-3xl
│ Para pedir desde MATU, primero     │  text-lg max-w-prose
│ autoriza los pedidos. Sin esta     │
│ autorización igual puedes imprimir │
│ o compartir la lista.              │
│ Es un permiso aparte del de su     │  text-lg max-w-prose
│ ficha y del de sus insumos.        │
│ Lee la política de privacidad…     │  LeePoliticaAntesDeAutorizar, como en el alta
│                                    │
│ Doy este permiso porque…           │  legend font-bold
│ ┌────────────────────────────────┐ │  GrupoOpciones forma="lista"
│ │ ( ) María lo autoriza y yo lo  │ │
│ │     registro                   │ │
│ ├────────────────────────────────┤ │
│ │ ( ) Soy su representante legal │ │
│ ├────────────────────────────────┤ │
│ │ (•) Cuido a esta persona, pero │ │  la del alta, preseleccionada
│ │     no soy su representante    │ │
│ └────────────────────────────────┘ │
│ ┃ Aviso: tu autorización tiene un │  AvisoCuidadorDeHecho
│ ┃ límite …                        │
│ ┃ [ ] Leí el aviso y lo acepto    │
│ ┌ Lo que declaras ───────────────┐ │  Nota rocio
│ │ (declaracion_pedidos_<calidad>)│ │
│ └────────────────────────────────┘ │
│ [ Autorizar los pedidos ]          │  único turquesa macizo
└────────────────────────────────────┘
```

**Pantalla ancha:** una columna de `max-w-3xl`, alineada a la izquierda, con las tres opciones en columnas desde `@2xl/main` (`GrupoOpciones columnas`). Es la pantalla del permiso de los insumos (MATU-36, 3.1.1) con otros textos: el frontend la reutiliza, no la copia.

### 4.2 Componentes y reglas

Los mismos de MATU-36 3.1: `GrupoOpciones`, `AvisoCuidadorDeHecho`, `CampoTexto` de la referencia del documento, `Nota` en `rocio` con la declaración de la calidad elegida y `Boton` principal. Las reglas de `validar_otorgamiento` son las mismas, y la validación ocurre al tocar el botón, que nunca está deshabilitado. La finalidad que se envía es `despacho` (D1).

### 4.3 Textos

| Parte | Texto | Origen |
|---|---|---|
| `Volver` | «Volver al catálogo» o «Volver a la lista de insumos», según desde dónde llegó. Sin `Volver` si se abrió la pestaña | **[NUEVO]** el segundo; el primero sigue el patrón de «Volver a Grupo familiar» |
| Título | Antes de pedir, un permiso | **[NUEVO]**, paralelo a «Antes de calcular, un permiso» [L 18] |
| Explicación | Para pedir desde MATU, primero autoriza los pedidos. Sin esta autorización igual puedes imprimir o compartir la lista. | [A4] |
| Segunda frase | Es un permiso aparte del de su ficha y del de sus insumos. | **[NUEVO]**, paralelo a «Es un permiso aparte del de su ficha.» [L 18] |
| Leyenda, opciones, referencia, aviso | Los del permiso de los insumos | [L 18], [L 25.4] |
| Nota | Título «Lo que declaras». Cuerpo: `declaracion_pedidos_<calidad>`, tal cual | [L 25.4] el título, la política 0.12 el cuerpo |
| Botón | Autorizar los pedidos · mientras envía: Autorizando… | [A4] · [L 22] |
| Hecho | Lleva a `/insumos/pedido` con la `Nota` de 7.3 | — |
| Errores de validación | Los de MATU-36 3.1.2 | [L 18], [L 25.4] |
| 422 u otro error | No pudimos guardar la autorización. Revisa lo que elegiste y vuelve a intentarlo. | [L 22] |
| 409 `autorizacion-vigente` | Sin texto: otra persona ya la dio. Se sigue igual que con el 201 | — |

### 4.4 Pagador u observador sin la autorización

El pagador o el observador que abre `/insumos/pedido` sin la autorización y sin un pedido abierto ve el patrón «una sola columna» de MATU-36 3.1.3, con la baldosa `bg-tinta/7 text-tenue` y el ícono `Lock`, sin botones:

> **Falta la autorización de pedidos para `{pila}`.** Sin ella no se pueden hacer pedidos desde MATU. Pídele a quien administra el grupo o a quien cuida a `{pila}` que la dé. **[NUEVO]**, con el patrón de [L 18]

### 4.5 Autorización por renovar (403 `revision-vencida`)

Patrón de MATU-36 3.1.4: baldosa `bg-atenta-fondo text-atenta` con `Hourglass`, sin `role="alert"` y sin rojo.

> **Hay que renovar la autorización de los pedidos de `{pila}`.** Se renueva una vez al año. Mientras tanto no se pueden hacer pedidos, pero tu pedido sigue guardado. **[NUEVO]**, con el patrón de [L 18]

- Admin y cuidador: debajo, el botón principal «Renovar la autorización» **[NUEVO]**, que muestra la pantalla de 4.1 en el lugar. Al autorizar, vuelve el carrito como estaba.
- Pagador: debajo, «Pídele a quien administra el grupo o a quien cuida a `{pila}` que la renueve.» **[NUEVO]**.

---

## 5. El catálogo: «Agregar al pedido» (cambio en MATU-59)

**Objetivo:** Carmen, mirando el precio de un comercio, lo suma a su pedido con un toque, sin salir del catálogo.

### 5.1 Dónde va

En cada **fila de comercio que dice «Hay en `{comercio}`»** (MATU-59 4.3), después de esa línea, `mt-2`. Solo para admin y cuidador, y solo con la capa 3 encendida. En una fila «No hay en `{comercio}` por ahora» no hay botón: lo que no hay no se puede apartar.

```
│ Almacén El Ejemplo (comercio ficticio)    │
│ $12.990  Precio de ejemplo                │
│ IVA incluido                              │
│ (✓) Hay en Almacén El Ejemplo             │
│ [ + Agregar al pedido ]                   │  Boton secundario, icono Plus
```

Después de agregar, en lugar del botón:

```
│ (✓) Hay en Almacén El Ejemplo             │
│ (✓) En tu pedido · Ver tu pedido          │  CircleCheck text-ok + texto + enlace
```

### 5.2 Componentes y estados

| Estado | Qué se ve | Texto |
|---|---|---|
| Normal | `Boton variante="secundario"`, ícono `Plus` `size-5` `aria-hidden`, `self-start`. `aria-label` que empieza con el texto visible: «Agregar al pedido: `{producto}`, de `{comercio}`» | «Agregar al pedido» **[NUEVO]** |
| Agregando | Mismo ancho, gerundio, `aria-busy` | «Agregando…» **[NUEVO]** |
| Ya está en el pedido, de este comercio | `p flex flex-wrap gap-x-2 text-base`: `CircleCheck` `size-5 text-ok` `aria-hidden`, el texto en `tinta`, y el enlace `EnlaceEnFrase` | «En tu pedido» **[NUEVO]** · «Ver tu pedido» **[NUEVO]** |
| Ya está en el pedido, de **otro** comercio | Ninguna de las filas de esa tarjeta lleva botón. La fila del comercio que está en el pedido lleva «En tu pedido» | — |
| Error | `MensajeError` bajo el botón | «No pudimos agregarlo. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]** |

- **Un producto, una línea.** Para pedir más, se cambia la cantidad en el carrito. Para cambiar de comercio, se saca del pedido y se agrega desde la otra fila. Así cada producto tiene una sola regla de RF-21.
- **Al agregar:** se anuncia por la región `status` «Agregamos «`{producto}`» a tu pedido.» **[NUEVO]** (mismo verbo que el botón), y el foco va al enlace «Ver tu pedido» de esa fila. La cantidad es 1 y la regla, «Buscarlo en otro comercio».
- **Sin la autorización:** el toque lleva a 4 con la intención en memoria. Al autorizar, se agrega y se llega a `/insumos/pedido` con la `Nota` de 7.3. No vuelve al catálogo: Carmen ya decidió pedir, y en el carrito ve que quedó.
- **El pagador y el observador** ven el catálogo como en MATU-59, sin botones.

### 5.3 Lo que cambia de MATU-59

- Su criterio 1 («no hay ningún elemento en `turquesa` macizo») **sigue igual**: el botón es secundario.
- Su criterio 2 («no hay ningún control dentro de las tarjetas») **cambia** para admin y cuidador: con Tab se pasa por cada «Agregar al pedido». Para el pagador y el observador sigue igual.
- La bajada «Mirar no te compromete a nada.» sigue siendo cierta: agregar no cobra nada.
- En pantalla ancha, cada comercio mide unos 267 px a 1280 px (MATU-59 4.7) y «Agregar al pedido» con su ícono y relleno, unos 200 px: cabe.

---

## 6. La lista de insumos: «Pedir estos productos» (cambio en MATU-60)

**Objetivo:** Carmen, con la lista ya ajustada, la convierte en un pedido sin escribir nada de nuevo.

### 6.1 Dónde va

Un bloque propio **después de los botones de la lista** y de sus mensajes («Copiamos la lista…»), separado: `mt-8 border-t border-linea pt-6`, `flex flex-col items-start gap-3`. En pantalla ancha, en la misma columna derecha de los botones (MATU-60 4.2).

```
│ [ Compartir la lista ]             │  principal de la lista, sin cambios
│ [ Imprimir o guardar en PDF ]      │
│ [ Copiar la lista ]                │
│ ────────────────────────────────── │  border-t border-linea
│ Los productos de esta lista que    │  p text-base text-tenue max-w-prose
│ están en el catálogo se pueden     │
│ pedir con MATU. Antes de pagar ves │
│ el total.                          │
│ [ Pedir estos productos ]          │  Boton secundario, icono ShoppingBasket
```

| Parte | Texto | Origen |
|---|---|---|
| Frase | Los productos de esta lista que están en el catálogo se pueden pedir con MATU. Antes de pagar ves el total. | **[NUEVO]** |
| Botón | Pedir estos productos | [D10] |
| En curso | Agregando a tu pedido… | **[NUEVO]** |

- **Quién lo ve:** admin y cuidador, con la capa 3 encendida, y solo si al menos una línea en pantalla tiene producto del catálogo. **Con o sin la autorización:** sin ella, el toque lleva a 4 y después sigue (D1 y D10). El pagador y el observador no lo ven.
- **Secundario (O8).** El aviso fijo de la lista («La lista no lleva el nombre…») sigue justo encima de los botones de la lista, y no se mueve. No describe al botón de pedir: lo que se pide no sale de MATU.
- **Validación:** si una cantidad de la lista está fuera de rango, se muestra el error de MATU-60 4.4 y no se pide nada, igual que al compartir.

### 6.2 Qué pasa al tocarlo

1. Si no hay autorización, 4.
2. Se agregan al pedido en curso las líneas con producto del catálogo, con la cantidad de 6.3 y la regla «Buscarlo en otro comercio». Si no había pedido, se crea el borrador.
3. Se llega a `/insumos/pedido` con la `Nota` de 6.4.

### 6.3 La cantidad que pasa (O3)

Es una función pura del frontend, con sus pruebas, que convierte la cantidad **que se ve en pantalla** (la sugerida o la que Carmen cambió) a envases del catálogo:
- unidades de la línea: `n × u` si la línea va en envases de `u` unidades, o `n` si va en unidades, sobres, ml o g;
- envases del catálogo: esas unidades divididas por `unidades_por_envase` del producto del catálogo, **redondeado hacia arriba**, entre 1 y 99;
- si el producto del catálogo no tiene `unidades_por_envase`, o la unidad no coincide (por ejemplo, ml contra unidades), pasa **1**, y la línea del carrito lo muestra con «En tu lista: …» para que Carmen lo ajuste (7.4).

### 6.4 Al llegar al carrito

`Nota tono="ok"` con `rol="status"`, bajo la bajada, que se queda hasta salir de la pantalla. El foco va al `h1` (regla de la ruta) y la nota se anuncia.

| Caso | Texto | Origen |
|---|---|---|
| Pasaron `{n}` productos | Agregamos `{n}` productos de tu lista a tu pedido. (Con 1: «Agregamos 1 producto de tu lista a tu pedido.») | **[NUEVO]** |
| Alguno ya estaba (O4) | Segundo párrafo: `{producto}` ya estaba en tu pedido: dejamos la cantidad de la lista. (Uno por producto) | **[NUEVO]** |
| Alguno no está en el catálogo | Último párrafo: No están en el catálogo y no van en el pedido: `{nombres, separados por coma}`. (Con uno: «`{nombre}` no está en el catálogo y no va en el pedido.») | **[NUEVO]** |

Lo agregado a mano en la lista se nombra igual que lo de MATU que no tiene producto: no está en el catálogo.

---

## 7. Tu pedido (el carrito)

**Objetivo:** Carmen revisa qué va, ajusta cuántos con el pulgar, dice qué hacer si falta cada uno y deja lista la entrega, para ver el total.

**Jerarquía:**
1. Las líneas: el **producto**, su **cantidad** y su **subtotal**.
2. «Ver el total», con la entrega justo encima.
3. Qué hacer si falta cada uno, el retracto, el comercio, el aviso del piloto y «Cancelar pedido».

### 7.1 Esquema a 360 px (admin o cuidador)

```
┌────────────────────────────────────┐
│ Insumos   Lista de insumos         │
│ Catálogo  Pedido                   │  Pestanas, «Pedido» activa
│ Tu pedido                          │  h1 titular text-3xl
│ Revisa los productos y cuántos     │  bajada text-base text-tenue max-w-prose
│ quieres. Antes de pagar confirmamos│
│ que haya.                          │
│ ┃(i) Precios de ejemplo.           │  Nota atenta borde, Info. Una vez
│ ┃ MATU todavía no tiene convenio…  │
│ Nunca lo cambiamos por otra marca  │  p text-base font-bold, id="nunca-otra-marca"
│ ni por otro producto.              │
│ ┌────────────────────────────────┐ │  li: rounded-xl bg-hoja ring-1 ring-linea px-4 py-4
│ │ Pañal adulto M x30             │ │  h2 text-xl font-bold
│ │ Paquete de 30 unidades         │ │  text-base text-tenue (si no repite el nombre)
│ │ De Almacén El Ejemplo          │ │  text-base
│ │ (comercio ficticio)            │ │
│ │ $12.990 cada uno               │ │  cifra text-lg font-bold + texto text-lg
│ │ Precio de ejemplo · IVA incluido│ │  text-base text-tenue
│ │ Cantidad                       │ │  Stepper, label font-bold
│ │ [ − ] [  2  ] [ + ]            │ │  botones size-12, campo w-24 text-xl
│ │ envases de 30 unidades         │ │  sufijo text-base text-tenue
│ │ En tu lista: 6 envases de 20   │ │  solo si vino de la lista, text-base text-tenue
│ │ unidades                       │ │
│ │ Subtotal: $25.980              │ │  text-lg, la cifra font-bold
│ │ ────────────────────────────── │ │
│ │ Si falta este producto         │ │  legend font-bold
│ │ ┌────────────────────────────┐ │ │  GrupoOpciones forma="lista"
│ │ │ (•) Buscarlo en otro       │ │ │
│ │ │     comercio               │ │ │
│ │ │     El mismo producto.     │ │ │  detalle text-base text-tenue
│ │ │     Pagas lo mismo.        │ │ │
│ │ ├────────────────────────────┤ │ │
│ │ │ ( ) Sacarlo del pedido y   │ │ │
│ │ │     devolverme su precio   │ │ │
│ │ └────────────────────────────┘ │ │
│ │ ────────────────────────────── │ │
│ │ Derecho a retracto: tienes 10  │ │  text-lg, «Derecho a retracto:» font-bold
│ │ días desde que lo recibes. No  │ │
│ │ aplica si abres el sello del   │ │
│ │ producto.                      │ │
│ │               Sacar del pedido │ │  textoPeligro, justify-self-end
│ └────────────────────────────────┘ │
│ ┌ (otra línea) ──────────────────┐ │
│ └────────────────────────────────┘ │
│                                    │
│ Entrega                            │  h2 titular text-2xl
│ Dirección                          │  h3 text-lg font-bold
│ Los Aromos 123, depto 4, La Reina  │  text-base
│ Portón verde                       │  text-base text-tenue
│ Cambiar dirección                  │  Boton texto
│ Teléfono de contacto               │  h3 text-lg font-bold
│ +56 9 •••• ••37 (tu celular)       │  cifras + text-tenue
│ Cambiar teléfono                   │  Boton texto
│ Llega entre 24 y 48 horas hábiles. │  text-base
│                                    │
│ Productos: $38.970                 │  text-xl, la cifra font-bold
│ El envío y el total los ves al     │  text-base text-tenue
│ confirmar que haya cada producto.  │
│ [ Ver el total ]                   │  principal. Único turquesa macizo
│ Cancelar pedido                    │  textoPeligro
└────────────────────────────────────┘
  (barra de secciones fija abajo: el main ya trae telefono:pb-36)
```

### 7.2 Al abrir

```
abre /insumos/pedido ─► GET …/consentimientos (despacho) y GET …/pedido-en-curso (JC4)
   ├─ hay un pedido en curso
   │     ├─ autorización vigente o pagador u observador ─► carrito (7.1), con lo de abajo
   │     └─ admin o cuidador sin autorización ─► 4 · revisión vencida ─► 4.5
   └─ no hay pedido en curso
         ├─ sin autorización: admin o cuidador ─► 4 · pagador u observador ─► 4.4
         ├─ revisión vencida ─► 4.5
         └─ vigente ─► vacío (7.10)

 el pedido en curso:
                 ├─ borrador ─► carrito (7.1)
                 ├─ total_confirmado vigente ─► carrito sin controles, con la nota de 7.9 y «Cambiar el pedido»
                 ├─ vencido ─► carrito sin controles, con la nota de 9.6 y «Cambiar el pedido»
                 └─ red o 5xx ─► error al cargar (11.1)
```

Una sola llamada trae el pedido completo: no hace falta un segundo `GET /v1/pedidos/{id}` para abrir la pantalla.

«Cargando…» [L 26] pasados 400 ms, en `text-lg text-tenue`, con `aria-busy` en la región. Sin esqueleto. Las pestañas y el título se ven desde el principio.

**Pagador y observador** ven el carrito sin ningún control: la cantidad como texto (`p text-lg tabular-nums`, «2 envases de 30 unidades»), «Si falta: …» como frase (7.6), sin «Sacar del pedido», sin «Cambiar…», sin «Ver el total» y sin «Cancelar pedido». Debajo de la suma, `p text-base text-tenue`: «Quien administra el grupo o quien cuida a `{pila}` puede cambiar el pedido y ver el total.» **[NUEVO]**. El observador no ve la entrega (no viene en su vista). El pagador ve el enlace «Ver el resumen» **[NUEVO]** (`Boton variante="secundario"`) cuando hay un total confirmado.

### 7.3 Al llegar después de una acción

`Nota tono="ok"` con `rol="status"`, bajo la bajada, hasta salir de la pantalla:

| Desde | Texto | Origen |
|---|---|---|
| Autorizar (4), con un producto del catálogo | Pedidos autorizados. Agregamos «`{producto}`» a tu pedido. | **[NUEVO]**: mismo verbo que «Autorizar los pedidos» y que «Agregar al pedido» |
| Autorizar, desde la lista | Pedidos autorizados. y, en el mismo bloque, los párrafos de 6.4 | **[NUEVO]** |
| Autorizar, desde la pestaña | Pedidos autorizados. Agrega productos desde el catálogo o desde tu lista de insumos. | **[NUEVO]** |
| La lista (6) | 6.4 | — |
| La dirección (8) | Guardamos la dirección. | **[NUEVO]**, mismo verbo que «Guardar la dirección» |
| Vaciar la dirección (8.7) | Vaciamos la dirección. | **[NUEVO]**, mismo verbo que «Vaciar la dirección» |
| «Cambiar el pedido» (9.12) | Ya puedes cambiar tu pedido. Cuando termines, toca «Ver el total» para confirmarlo de nuevo. | **[NUEVO]**, `tono="rocio"` en vez de `ok`: no terminó nada, empieza algo |

### 7.4 La línea

| Parte | Componente y tokens | Texto |
|---|---|---|
| Contenedor | `li` `@container/linea rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea`, `grid grid-cols-1 gap-y-3`. **La línea no es un botón** | — |
| Producto | `h2 text-xl font-bold break-words`, con `id` (lo usan los nombres accesibles) | `{producto}` |
| Presentación | `p text-base text-tenue`. No va si es igual al nombre (MATU-59, N3) | `{presentacion}` |
| Comercio | `p text-base break-words` | «De `{comercio}` (comercio ficticio)» **[AJUSTE]** de «`{nombre}` (comercio ficticio)» [L 27]: en el carrito, «De» dice que el producto viene de ahí. «(comercio ficticio)» solo si `ficticio` es `true`, en cada línea (MATU-59, N2) |
| Precio | `p flex flex-wrap items-baseline gap-x-2`: la cifra en `span cifras text-lg font-bold text-tinta` y el resto en `text-lg`. Nunca en `turquesa` | «`{precio}` cada uno» **[NUEVO]** |
| Bajo el precio | `p text-base text-tenue` | «Precio de ejemplo · IVA incluido» [L 27], las dos frases en un renglón con un punto medio |
| Cantidad | El `Stepper` de `insumosComun.tsx` (7.5) | «Cantidad» [L 21] |
| De la lista | `p text-base text-tenue`, solo en las líneas que vinieron de la lista | «En tu lista: `{cantidad}`» **[NUEVO]**, con el texto completo de MATU-60 4.5 («6 envases de 20 unidades») |
| Subtotal | `p text-lg`, la cifra en `cifras font-bold`. Cambia en cuanto cambia la cantidad, sin región viva (el campo ya dice el número) | «Subtotal: `{precio}`» **[NUEVO]** |
| Si falta | 7.6, separado por `border-t border-linea pt-3` | — |
| Retracto | `p text-lg max-w-prose border-t border-linea pt-3`, «Derecho a retracto:» en `font-bold`, el resto en `text-tinta` | Uno de los dos textos [L 27], por `retracto_pierde_al_abrir` |
| Sacar | `Boton variante="textoPeligro"`, `justify-self-end`. `aria-label` «Sacar del pedido: `{producto}`» | «Sacar del pedido» [A4] |

- **El retracto en cada línea, con letra no menor que la del precio (C2):** los dos en `text-lg` (19 px; 38 px con el texto al 200 %). Siempre visible, nunca en un `details` ni en un «Ver más».
- **Por qué el producto es `h2` y no `h3`:** en el carrito no hay categorías. Así se salta de producto en producto con el lector, y «Entrega» es el `h2` siguiente.
- **Orden dentro de la línea:** qué es, de dónde y cuánto cuesta; después lo que se toca más (la cantidad), lo que se decide una vez (si falta), el derecho, y al final lo que saca la línea, lejos del campo.

### 7.5 La cantidad (U4 y C24)

El hallazgo U4 de la ronda 1: ajustar la cantidad de las toallitas costó. El prototipo contaba unidades sueltas (120 toallitas) y solo tenía − y +. Lo que cambia aquí:

1. **Se cuenta en envases del catálogo, no en unidades.** Los números son chicos (1 a 99) y el sufijo dice qué es cada uno («envases de 80 unidades», con la función de MATU-60 4.5 y los datos del producto del catálogo).
2. **Se escribe.** El campo es de texto numérico (`inputMode="numeric"`, `pattern="[0-9]*"`, `autoComplete="off"`, `enterKeyHint="done"`), y **al recibir el foco se selecciona todo su contenido**, para que escribir «3» reemplace el «12» sin borrar a mano. Es el único cambio al `Stepper`: una prop opcional, `seleccionarAlEnfocar`.
3. **Botones de 48 px** (`size-12`, 51 px) a los dos lados, con nombre accesible propio: − «Quitar uno: `{producto}`» y + «Agregar uno: `{producto}`» **[AJUSTE]** de «Quitar uno» y «Agregar uno» [A4], con el producto para que se distingan entre líneas. Con `textoMenos` y `textoMas`, que el componente ya recibe.
4. **El campo se nombra** con la etiqueta visible y el producto: `aria-labelledby` con el id de «Cantidad» y el del `h2` («Cantidad, Pañal adulto M x30»). Es lo que [A4] llama «Cantidad de `{producto}`», armado como en la lista (MATU-60 4.4).
5. **El subtotal está al lado**, y cambia en cuanto cambia el número.
6. **Rango de 1 a 99.** El − en 1 no baja de 1: para no pedir un producto, «Sacar del pedido». Fuera de rango, al salir del campo o al tocar «Ver el total», bajo el campo con `MensajeError` y `aria-invalid`: «Escribe una cantidad de 1 a 99.» **[NUEVO]**, con la forma de [L 21].
7. **Se guarda solo.** Sin botón «Guardar»: la cantidad se envía 600 ms después del último cambio o al salir del campo, lo que pase primero. Es una acción reversible y no crítica (CLAUDE.md, agente 3, punto 4): la pantalla muestra el número nuevo sin esperar. Si falla, el campo vuelve al último valor guardado y debajo aparece `MensajeError`: «No pudimos guardar la cantidad. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]**. Antes de confirmar el total, «Ver el total» espera a que termine lo pendiente.

**Medidas a 360 px:** el contenido de la línea mide 294 px. − (51) + campo `w-24` (102) + + (51) + dos `gap-2` (16) = 220 px: los tres van en un renglón. El sufijo baja al siguiente, como en la lista. Con el texto al 200 % a 320 px, el campo y los botones bajan de renglón por `flex-wrap` (ya en el componente), sin desplazamiento horizontal.

### 7.6 Si falta este producto (RF-21)

| Parte | Componente y tokens | Texto |
|---|---|---|
| Grupo | `GrupoOpciones forma="lista"`, sin `columnas`: un `fieldset` con `legend font-bold`, una opción por fila, `min-h-12`, indicador `size-6` (DISENO.md 6). `aria-describedby="nunca-otra-marca"` en el `fieldset` (O9) | Leyenda: «Si falta este producto» [A4] |
| Opción 1, elegida por omisión | Con su detalle en `text-base text-tenue` | «Buscarlo en otro comercio» · detalle: «El mismo producto. Pagas lo mismo.» [A4] |
| Opción 2 | Sin detalle | «Sacarlo del pedido y devolverme su precio» [A4] |
| Nota, una vez sobre las líneas | `p id="nunca-otra-marca" max-w-prose text-base font-bold` | «Nunca lo cambiamos por otra marca ni por otro producto.» [A4] |

- **Cada grupo se nombra con el producto:** el `fieldset` lleva `aria-labelledby` con el id de la leyenda y el del `h2`, para que el lector diga «Si falta este producto, Pañal adulto M x30, grupo».
- **El estado nunca solo por color:** la elegida lleva el punto dentro del círculo, el anillo `turquesa` y el fondo `rocio`. Ninguna va en `turquesa` macizo.
- **Se guarda solo**, al cambiar la opción, igual que la cantidad. Si falla, vuelve la opción anterior y aparece bajo el grupo: «No pudimos guardar qué hacer si falta. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]**.
- **Qué hace cada opción (JC5):** con «Buscarlo en otro comercio», si falta, MATU busca el mismo producto en otro comercio al mismo precio. Con «Sacarlo del pedido y devolverme su precio», si falta, **sale sin buscarlo en otro comercio**. Los textos de la opción, del pagador (más abajo) y del resumen (9.3 y 9.7) dicen eso y nada más.
- **«Sacarlo del pedido y devolverme su precio» no es «Sacar del pedido».** La opción dice qué hacer si falta al preparar, el botón saca la línea ahora. Por eso la opción va dentro de su grupo, con la pregunta, y el botón va al final de la línea, separado por el retracto.
- **Con el modo `angosto`:** el indicador arriba y el texto debajo (DISENO.md 6, la regla de MATU-57).
- **Pagador y observador:** en lugar del grupo, `p text-base`: «Si falta: lo buscamos en otro comercio.» o «Si falta: lo sacamos y te devolvemos su precio.» **[NUEVO]** (las mismas frases del resumen, 9.3).

### 7.7 Sacar del pedido

- **Sin confirmación:** se vuelve a agregar desde el catálogo o la lista en un toque, como «Quitar de la lista» (MATU-60 4.10).
- Se anuncia por la región `status`: «Sacamos «`{producto}`» del pedido.» **[NUEVO]**, mismo verbo que el botón.
- **Foco:** al campo «Cantidad» de la línea siguiente, o de la anterior si era la última. Si era la única, al `h1`, y se ve el vacío (7.10).
- Si falla: `MensajeError` bajo el botón, «No pudimos sacarlo. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]**, y la línea se queda.

### 7.8 La entrega

`section aria-labelledby` al `h2` «Entrega» **[NUEVO]**, `titular text-2xl`, `mt-10`. Debajo, tres partes, cada una con su `h3 text-lg font-bold`:

| Parte | Con datos | Sin datos | Origen |
|---|---|---|---|
| **Dirección** | `p text-base`: «`{calle}` `{numero}`, `{depto}`, `{comuna}`» (sin «depto» si no hay), y `p text-base text-tenue` con la referencia si la hay. Debajo, `Boton variante="texto"` «Cambiar dirección», que lleva a 8 | `p text-base`: «Todavía no hay una dirección de entrega.» y `Boton variante="secundario"` «Agregar la dirección», que lleva a 8 | Título «Dirección» **[NUEVO]** · «Cambiar dirección» [A4] · los otros dos **[NUEVO]** |
| **Teléfono de contacto** | Mientras no se cambie: `celular_enmascarado` de `GET /v1/cuenta` en `cifras` (con `angosto:whitespace-normal`, DISENO.md 2) y « (tu celular)» en `text-tenue`. Si se cambió: el número escrito. Debajo, `Boton variante="texto"` «Cambiar teléfono» | Si la cuenta no tiene `celular_verificado`: el campo abierto (7.8.1) | «Teléfono de contacto» [A4] · «(tu celular)» y «Cambiar teléfono» **[NUEVO]** |
| **Cuándo llega** | `p text-base`: «Llega entre 24 y 48 horas hábiles.» con `ventana_entrega`, que el contrato trae también en `borrador` (JC7) | — | **[AJUSTE]** de «Entrega: Entre 24 y 48 horas hábiles» [D8]: aquí ya está bajo el título «Entrega», así que va como frase. En el resumen va la forma de [D8] |

- **Pagador:** ve la dirección sin los botones (D4). No ve el teléfono en el carrito: antes de confirmar es el celular de quien va a confirmar, que no es el suyo. Lo ve en el resumen (9.7).
- **Observador:** no ve la sección «Entrega» (no viene en su vista).
- **Por qué la entrega va en el carrito y no solo en el resumen:** la dirección se pide antes de confirmar el total (C7), y Carmen tiene que verla antes de tocar «Ver el total».

#### 7.8.1 Cambiar el teléfono

Se abre en el lugar, con el patrón de «Agregar otro insumo» (MATU-60 4.7): el botón «Cambiar teléfono» se oculta y aparece un `form noValidate` con:
- El campo, `type="tel"`, `autoComplete="tel"`, `inputMode="tel"`, con la ayuda **antes** del campo: «Para que quien entrega pueda avisarte. Si es el de otra persona, avísale.» [A4]. Vacío al abrir, para no mostrar el celular completo.
- **Un solo rótulo (v1.2).** El `h3` «Teléfono de contacto» [A4] que ya está arriba es el rótulo del campo: el campo **no lleva una etiqueta visible propia**, y se nombra con `aria-labelledby` al `id` del `h3`, y con `aria-describedby` a la ayuda (y al error, si lo hay). Así no se lee dos veces «Teléfono de contacto», una bajo la otra (revisión visual del 11-11, P3-2). El orden de lectura queda: título, ayuda, campo y error.
- `Boton variante="secundario"` «Guardar el teléfono» **[NUEVO]** (gerundio «Guardando…») y `Boton variante="texto"` «Cancelar» [M36].
- Error de formato: «Escribe un celular de Chile, por ejemplo +56 9 5555 0137.» [L 8].
- Al guardar: se cierra, se ve el número nuevo sin «(tu celular)», se anuncia «Guardamos el teléfono.» **[NUEVO]** y el foco vuelve a «Cambiar teléfono». `Esc` o «Cancelar» cierran sin guardar y devuelven el foco al botón.
- **Dónde se guarda, según el contrato propuesto:** antes de confirmar, el número vive en la memoria de la app (nunca en el almacenamiento del navegador) y viaja en el cuerpo de `confirmar` como `telefono_contacto`. En el resumen, «Cambiar teléfono» usa `PUT /v1/pedidos/{id}/contacto` con `If-Match`, sin volver a confirmar. «Guardar el teléfono» dice lo mismo en los dos casos: para Carmen es el mismo gesto.
- El número es del pedido, no de la persona: no se guarda para el próximo pedido. Cada pedido nuevo empieza con el celular de quien confirma (D4).

### 7.9 El pie: productos y «Ver el total»

| Parte | Componente y tokens | Texto |
|---|---|---|
| Suma | `p text-xl`, la cifra en `cifras font-bold` | «Productos: `{precio}`» **[NUEVO]**. Es la suma de los subtotales de la pantalla. **No dice «total»**: el total lleva el envío y se confirma |
| Nota | `p max-w-prose text-base text-tenue`. **Solo con el pedido en `borrador`** (v1.2): con el total confirmado o vencido ya no es cierta, y no se muestra, ni a admin y cuidador ni al pagador ni al observador (revisión visual del 11-11, P3-3) | «El envío y el total los ves al confirmar que haya cada producto.» **[NUEVO]**, sin «con IVA» [JC-IVA]: los precios ya lo llevan. Sin renglón de envío en el carrito (JC5) |
| Principal | `Boton` principal, sin ícono. Único `turquesa` macizo | «Ver el total» [A4] |
| En curso | Gerundio, `aria-busy`, y debajo `p role="status" text-base`: «Estamos confirmando que haya cada producto…» [A4] | «Confirmando…» **[NUEVO]** |
| Salida | `Boton variante="textoPeligro"`, `mt-4`, abre 10. Admin y cuidador (JC3) | «Cancelar pedido» [A4] |

**Validación al tocar «Ver el total»** (el botón nunca está deshabilitado):
- sin dirección: bajo «Dirección», `MensajeError` «Agrega la dirección de entrega para ver el total.» **[NUEVO]**, y el foco va a «Agregar la dirección». Es el mismo texto si el servidor responde 409 `sin-direccion`;
- una cantidad fuera de rango: el error de 7.5 y el foco al primer campo con error;
- sin teléfono: el error de 7.8.1 bajo el campo abierto, con el foco en él.

**Con el total ya confirmado** (abrió la pestaña «Pedido» después de confirmar): el contrato solo deja cambiar las líneas en `borrador`, así que admin y cuidador ven el carrito **sin controles**, como el pagador (7.2): la cantidad como texto, «Si falta: …» como frase, sin «Sacar del pedido» y sin «Cambiar dirección» ni «Cambiar teléfono». Bajo la bajada, `Nota tono="rocio"` sin `rol`: «Ya confirmaste el total. Para cambiar algo, toca «Cambiar el pedido».» **[NUEVO]**. En el pie, «Productos: `{precio}`» sin la nota del envío y el total (ver la fila «Nota»), y después, en este orden:
- «Ver el total», principal: lleva al resumen sin volver a confirmar mientras el total siga vigente;
- «Cambiar el pedido», `Boton variante="secundario"`, con el mismo comportamiento y textos de 9.12;
- «Cancelar pedido», `textoPeligro`.

Con el total **vencido**, la nota es la de 9.6, «Ver el total» confirma de nuevo y «Cambiar el pedido» sigue igual (si el contrato acepta la vuelta a `borrador` desde `vencido`; si no, no se muestra con el total vencido y el carrito se cambia después de volver a confirmar).

### 7.10 Vacío

```
│ Tu pedido                          │
│ Revisa los productos y cuántos…    │
│ ┌────┐                             │  baldosa size-16 rounded-2xl bg-rocio
│ │ 🧺 │                             │  ShoppingBasket size-9 text-turquesa
│ └────┘                             │
│ Tu pedido está vacío. Agrega       │  p text-lg max-w-prose
│ productos desde el catálogo o desde│
│ tu lista de insumos.               │
│ [ Ir al catálogo ]  Ir a la lista  │  secundario · texto
│                     de insumos     │
```

| Rol | Texto | Acciones |
|---|---|---|
| admin, cuidador | «Tu pedido está vacío. Agrega productos desde el catálogo o desde tu lista de insumos.» [A4] | `secundario` «Ir al catálogo» y `texto` «Ir a la lista de insumos» **[NUEVO]**. Sin principal: no hay nada que confirmar |
| pagador, observador | «Todavía no hay un pedido para `{pila}`.» **[NUEVO]** | Ninguna. Baldosa `bg-tinta/7 text-tenue` |

Sin el aviso del piloto, sin la entrega y sin «Ver el total»: no hay precios ni nada que confirmar. Alineado a la izquierda.

### 7.11 Pantalla ancha (1280 y 1920 px)

```
┌───────────────┬──────────────────────────────────────────────────────────────────────────┐
│ (M) MATU      │ Insumos   Lista de insumos   Catálogo   Pedido                           │
│               │ Tu pedido                                                                │
│ Ficha de relevo│ Revisa los productos y cuántos quieres. Antes de pagar confirmamos que…│
│ Insumos  ◄    │ ┃(i) Precios de ejemplo. MATU todavía no tiene convenio…                 │
│ Compartir     │ Nunca lo cambiamos por otra marca ni por otro producto.                  │
│ Grupo familiar│ ┌────────────────────────────────────────────┐  Entrega                  │
│               │ │ Pañal adulto M x30     │ Cantidad          │  Dirección                │
│               │ │ Paquete de 30 unidades │ [−][ 2 ][+]       │  Los Aromos 123, La Reina │
│               │ │ De Almacén El Ejemplo  │ envases de 30 u.  │  Cambiar dirección        │
│               │ │ (comercio ficticio)    │ Subtotal: $25.980 │  Teléfono de contacto     │
│               │ │ $12.990 cada uno       │ Si falta este     │  +56 9 •••• ••37 (tu c.)  │
│               │ │ Precio de ejemplo · IVA│ producto          │  Cambiar teléfono         │
│               │ │ Derecho a retracto: …  │ (•) Buscarlo en … │  Llega entre 24 y 48 h…   │
│               │ │                        │ ( ) Sacarlo del … │  Productos: $38.970       │
│               │ │                        │  Sacar del pedido │  El envío y el total…     │
│               │ └────────────────────────────────────────────┘  [ Ver el total ]         │
│               │ ┌ (otra línea) ──────────────────────────────┐  Cancelar pedido          │
│               │ └────────────────────────────────────────────┘     (columna sticky top-6) │
└───────────────┴──────────────────────────────────────────────────────────────────────────┘
```

- **Dos columnas desde `@3xl/main`**, como la lista (MATU-60 4.2): `grid grid-cols-1 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-x-10`. A la izquierda las líneas; a la derecha la entrega, la suma, «Ver el total» y «Cancelar pedido», en `@3xl/main:sticky @3xl/main:top-6` con `max-h-[calc(100dvh-3rem)] overflow-y-auto [scrollbar-width:thin]` (DISENO.md 3, columnas pegajosas).
- **La línea en dos columnas desde 40 rem de línea** (`@2xl/linea`, se decide por el ancho de la línea y no del `main`, la lección de MATU-60): `@2xl/linea:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-6`. Izquierda: producto, presentación, comercio, precio y retracto. Derecha: cantidad, «En tu lista», subtotal, si falta y «Sacar del pedido». **El orden del DOM no cambia** (el de 7.4): el retracto se ubica con `@2xl/linea:col-start-1 @2xl/linea:row-start-2` y la derecha con `@2xl/linea:col-start-2 @2xl/linea:row-start-1 @2xl/linea:row-span-2`, con `@2xl/linea:grid-rows-[auto_1fr]` para que el retracto quede bajo el precio (MATU-59 4.7, v1.1). El lector y el Tab siguen el orden de 360 px.
- **Medidas a 1280 px:** el `main` mide unos 906 px; la izquierda, unos 520 px, y la línea por dentro, unos 486 px: **no llega a los 40 rem (680 px)**, así que la línea va en una columna, como a 360 px. A 1920 px la izquierda mide unos 700 px y la línea por dentro, unos 666 px: tampoco. **La línea en dos columnas solo aparece si el `main` pasa de unos 1.200 px**, por ejemplo con la barra lateral plegada en un monitor ancho. Lo dejo así a propósito: en una columna el campo de cantidad queda junto a su producto, y la línea no se estira.
- **La derecha a 1280 px** mide unos 346 px: «Ver el total» y la suma caben en un renglón cada uno.

---

## 8. ¿Dónde lo entregamos? (agregar y cambiar la dirección)

**Objetivo:** Carmen escribe una vez dónde vive su mamá y no la vuelve a escribir en el próximo pedido.

**Jerarquía:** 1) el título y para qué se usa · 2) los campos · 3) «Guardar la dirección».

### 8.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Insumos   Lista de insumos         │
│ Catálogo  Pedido                   │
│ ‹ Volver a tu pedido               │  Volver
│ ¿Dónde lo entregamos?              │  h1 titular text-3xl
│ La usamos solo para entregar tus   │  bajada text-base text-tenue max-w-prose
│ pedidos. Ningún comercio la ve.    │
│ La guardamos para los próximos     │
│ pedidos de María.                  │
│ Calle                              │  CampoTexto, label font-bold
│ [                              ]   │
│ Número                             │
│ [          ]                       │  w-40
│ Depto (opcional)                   │
│ [          ]                       │  w-40
│ Comuna                             │
│ [                              ]   │
│ Referencia (opcional)              │
│ Por ejemplo: portón verde. No      │  ayuda text-base text-tenue, ANTES del campo
│ escribas datos de salud.           │
│ [                              ]   │
│ [ Guardar la dirección ]           │  principal. Único turquesa macizo
└────────────────────────────────────┘
```

**Pantalla ancha:** una columna de `max-w-2xl`, alineada a la izquierda. «Calle» y «Número» en una fila (`@xl/main:grid-cols-[minmax(0,1fr)_10rem]`), y «Depto» y «Comuna» en otra (`@xl/main:grid-cols-[10rem_minmax(0,1fr)]`), con `grid-cols-1` en el ancho más chico (DISENO.md 3). Sin columna derecha: no hay nada que mostrar al lado.

### 8.2 Campos

| Campo | Construcción | Etiqueta | Origen |
|---|---|---|---|
| Calle | `CampoTexto`, `autoComplete="address-line1"`, `maxLength={120}` | Calle | [A4] |
| Número | `CampoTexto`, `autoComplete="off"`, `inputMode="text"` (admite «S/N»), `maxLength={20}`, `w-40` | Número | [A4] |
| Depto | `CampoTexto`, `autoComplete="address-line2"`, `maxLength={20}`, `w-40` | Depto (opcional) | [A4] |
| Comuna | `CampoTexto`, `autoComplete="address-level2"`, `maxLength={60}`. Texto libre, sin lista de comunas | Comuna | [A4] |
| Referencia | `CampoTexto`, `autoComplete="off"`, `maxLength={200}` (C9, el largo de `DireccionEntrada`). La ayuda va **antes** del campo y en su `aria-describedby` | Referencia (opcional) · ayuda: «Por ejemplo: portón verde. No escribas datos de salud.» | [A4] |

Los largos son los de `DireccionEntrada` del contrato propuesto (los del alta, MATU-07).

- **Sin mapa, sin ubicación, sin «usar mi ubicación»** (D4, C8).
- **Sin región ni nombre de la dirección:** `DireccionEntrada` trae `etiqueta` («Casa») y `region` («Metropolitana») con valor por omisión, así que la pantalla no los pide ni los envía. La comuna basta para el piloto. Al cambiar una dirección guardada, la pantalla reenvía los que vinieron, para no pisarlos con el valor por omisión.
- Al abrir con una dirección guardada, los campos vienen llenos y el título y el botón no cambian: es la misma pregunta.

### 8.3 Validación (al tocar «Guardar la dirección»)

| Caso | Texto | Origen |
|---|---|---|
| Calle vacía | Escribe la calle. | **[NUEVO]** |
| Número vacío | Escribe el número. Si no tiene, escribe S/N. | **[NUEVO]** |
| Comuna vacía | Escribe la comuna. | **[NUEVO]** |
| Referencia sobre el largo (si llega pegada) | La referencia admite hasta 200 caracteres. Acórtala un poco. | **[NUEVO]**, con la forma de [L 18] |
| 422 de otro campo | No pudimos guardar la dirección. Revisa los datos y vuelve a intentarlo. | **[NUEVO]**, con la forma de [L 18] |

`MensajeError` bajo cada campo con `aria-invalid` y `aria-describedby`, y el foco al primero con error.

### 8.4 Estados del botón

«Guardar la dirección» **[NUEVO]** · mientras envía: «Guardando…» [L 23]. Con el 200 vuelve a `/insumos/pedido` con «Guardamos la dirección.» (7.3), o al resumen si llegó desde ahí (8.6).

### 8.5 Otra persona la cambió (412)

**Objetivo:** Carmen no pisa sin saber la dirección que dejó su hermano, y elige en un toque.

```
│ ┃ (⚠) Otra persona de tu grupo     │  Nota atenta borde, rol="alert", recibe el foco
│ ┃ cambió la dirección mientras la  │
│ ┃ cambiabas.                       │
│ ┃ No guardamos la tuya encima de la│
│ ┃ suya. Elige cuál dejar.          │
│ La que guardó                      │  h2 text-lg font-bold
│ Los Aromos 125, La Reina           │  text-base
│ La tuya, sin guardar               │  h2 text-lg font-bold
│ Los Aromos 123, depto 4, La Reina  │  text-base
│ [ Guardar la mía ]  Dejar la que   │  principal · secundario
│                     guardó         │
```

| Parte | Texto | Origen |
|---|---|---|
| Título | Otra persona de tu grupo cambió la dirección mientras la cambiabas. | **[AJUSTE]** de «`{autor}` cambió «`{nombre}`» mientras lo cambiabas» [L 18]: el contrato de la dirección no trae quién la cambió, y no hace falta para decidir. Es la forma de «Otra persona de tu grupo ya…» [L 22] |
| Texto | No guardamos la tuya encima de la suya. Elige cuál dejar. | **[AJUSTE]** de [L 18], con «la tuya» y «la suya» porque es «la dirección» |
| Las dos | La que guardó · La tuya, sin guardar | **[AJUSTE]** de «Lo que guardó» y «Lo tuyo, sin guardar» [L 18] |
| Botones | Guardar la mía · Dejar la que guardó | **[AJUSTE]** de «Guardar lo mío» y «Dejar lo que guardó» [L 18] |
| Después | Con «Guardar la mía»: «Guardamos la dirección.» (7.3). Con «Dejar la que guardó»: vuelve al carrito con «Dejaste la dirección que guardó otra persona de tu grupo.» **[NUEVO]** | — |

- En pantalla ancha, «La que guardó» y «La tuya, sin guardar» lado a lado desde `@xl/main` (`grid-cols-1 @xl/main:grid-cols-2`).
- No es un error: `atenta`, nunca `pronto` (DISENO.md 6, «Página»). «Guardar la mía» reenvía con el `ETag` nuevo.

### 8.6 Cambiar la dirección desde el resumen (O5)

«Cambiar dirección» en el resumen (9.7) lleva aquí con `Volver` «Volver a antes de pagar» **[NUEVO]**. Al guardar, la pantalla vuelve a confirmar el total **sin cancelar el pedido ni volverlo a `borrador`** (JC1: `confirmar` acepta el total vigente y da 15 minutos nuevos), con «Estamos confirmando que haya cada producto…» [A4], y llega al resumen con la dirección nueva, la hora nueva y el anuncio de 9.5. Si `Volver` lleva al resumen sin guardar, nada cambia y el total sigue con su hora.

### 8.7 Vaciar la dirección (JC6)

**Objetivo:** Carmen puede borrar de MATU la dirección de su mamá cuando quiera, sin hacer un pedido y aunque haya retirado la autorización.

**Dónde va:** solo cuando hay una dirección guardada, y solo para admin y cuidador. Un bloque propio **después de «Guardar la dirección»**, separado: `mt-10 border-t border-linea pt-6`, `flex flex-col items-start gap-3`. En pantalla ancha, igual, dentro de la misma columna de `max-w-2xl`.

```
│ [ Guardar la dirección ]           │  principal, sin cambios
│ ────────────────────────────────── │  border-t border-linea
│ Si no quieres que MATU la guarde,  │  p text-base text-tenue max-w-prose
│ puedes vaciarla. Para el próximo   │
│ pedido habrá que escribirla de     │
│ nuevo.                             │
│ Vaciar la dirección                │  Boton textoPeligro
```

**Jerarquía:** tercera. Es una salida, no la tarea de la pantalla: va lejos del botón principal, en `textoPeligro` (rojo sin fondo, con palabra), y nunca en `turquesa`.

**La confirmación:** el diálogo de MATU-44 4.1 (el mismo de 10): `<dialog>` modal con `showModal()`, `max-w-md`, el foco inicial en el título, la región de error vacía y sin animación.

```
┌──────────────────────────────────┐
│ ¿Vaciar la dirección de entrega  │  h2 text-xl font-bold, tabIndex -1
│ de María?                        │
│ La borramos de MATU. Para el     │  p text-base
│ próximo pedido habrá que         │
│ escribirla de nuevo.             │
│ [ Vaciar la dirección ] Dejarla  │  peligroPrincipal · texto
│                         como está│
└──────────────────────────────────┘
```

| Parte | Texto | Origen |
|---|---|---|
| Frase antes del botón | Si no quieres que MATU la guarde, puedes vaciarla. Para el próximo pedido habrá que escribirla de nuevo. | **[NUEVO]** |
| Botón | Vaciar la dirección. Nombre accesible: «Vaciar la dirección de entrega de `{pila}`» | **[NUEVO]** |
| Título del diálogo | ¿Vaciar la dirección de entrega de `{pila}`? | **[NUEVO]**, mismo verbo que el botón |
| Texto | La borramos de MATU. Para el próximo pedido habrá que escribirla de nuevo. | **[NUEVO]** |
| Botones | Vaciar la dirección (`peligroPrincipal`, macizo `pronto`: no se deshace) · Dejarla como está (`texto`) | **[NUEVO]** |
| En curso | Vaciando… | **[NUEVO]** |
| Hecho | Cierra el diálogo y vuelve a donde llegó: al carrito, con «Vaciamos la dirección.» (7.3), donde la entrega dice «Todavía no hay una dirección de entrega.»; o a Grupo familiar (O12), con `Nota tono="ok"` «Vaciamos la dirección.». El foco va al `h1` | **[NUEVO]** |
| Error de conexión | En la región de error del diálogo: «No pudimos vaciar la dirección. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.» | **[NUEVO]**, con la forma de [L 22] |
| 412, otra persona la cambió | Cierra el diálogo y muestra la dirección como quedó, con `Nota tono="atenta"` `rol="alert"`: «Otra persona de tu grupo cambió la dirección mientras la revisabas. Revisa cómo quedó antes de vaciarla.» | **[NUEVO]**, con la forma de 8.5 |
| 404, ya vaciada | Cierra el diálogo y hace lo mismo que con el hecho, sin error: lo que Carmen pidió ya pasó | — |

- `Esc` y «Dejarla como está» cierran sin vaciar y devuelven el foco a «Vaciar la dirección».
- **El texto no habla del pedido en curso:** la entrega se copia al pedido al confirmar (D4), y qué pasa con esa copia lo fija el contrato. Si el backend la borra también, se agrega una frase al diálogo y pasa por `lenguaje.md`.
- **Sin el bloque** cuando no hay dirección guardada, para el pagador y para el observador.

---

## 9. Antes de pagar (el resumen con el total confirmado)

**Objetivo:** antes de pagar, Carmen sabe exactamente qué llega, cuánto paga una sola vez, quién lo prepara, cuándo llega, qué pasa si algo falta y hasta qué hora vale el total, y puede no seguir sin costo.

**Jerarquía:**
1. El total y hasta qué hora vale, y lo que cambió desde su pedido.
2. Los productos con su cantidad, precio, subtotal y qué hacer si faltan; la boleta; «Pagar» (MATU-62).
3. «Cambiar el pedido», la entrega, qué pasa si falta, quién vende, reclamos, condiciones y la salida sin costo.

### 9.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Insumos   Lista de insumos         │
│ Catálogo  Pedido                   │
│ ‹ Volver a tu pedido               │  Volver
│ Antes de pagar                     │  h1 titular text-3xl
│ Confirmamos que hay cada producto. │  bajada text-lg max-w-prose, el total en cifras font-bold
│ El total es $57.460.               │
│ ┃(i) Precios de ejemplo. …         │  Nota atenta borde, Info. Una vez
│ ┌ (↻) Cambió desde tu pedido ────┐ │  Nota rocio, RefreshCw. Solo si hubo cambios
│ │ · Ya no hay Toallitas húmedas  │ │
│ │   x80. Salió del pedido.       │ │
│ │ · Cambió el precio de          │ │
│ │   Suplemento…: antes $27.030,  │ │
│ │   ahora $26.490.               │ │
│ └────────────────────────────────┘ │
│ Productos                          │  h2 titular text-2xl
│ ┌────────────────────────────────┐ │
│ │ Pañal adulto M x30             │ │  h3 text-xl font-bold
│ │ De Almacén El Ejemplo          │ │
│ │ (comercio ficticio)            │ │
│ │ 2 × $12.990                    │ │  text-lg tabular-nums
│ │ Subtotal: $25.980              │ │  text-lg, la cifra font-bold
│ │ [◐ Cambió el precio]           │ │  Etiqueta atenta, solo si cambió
│ │ Si falta: lo buscamos en otro  │ │  text-base
│ │ comercio.                      │ │
│ │ Derecho a retracto: tienes 10  │ │  text-lg
│ │ días… No aplica si abres el    │ │
│ │ sello del producto.            │ │
│ └────────────────────────────────┘ │
│ Si cambias algo, antes de pagar    │  p text-base text-tenue (9.12)
│ confirmamos el total de nuevo.     │
│ [ Cambiar el pedido ]              │  Boton secundario
│ Entrega                            │  h2
│ Entrega: Entre 24 y 48 horas       │  text-base
│ hábiles                            │
│ Los Aromos 123, depto 4, La Reina  │
│ Cambiar dirección                  │  texto
│ Teléfono de contacto: +56 9 ••••…  │
│ Si falta un producto               │  h2
│ Si al retirar falta un producto, … │  text-base max-w-prose
│ Quién vende                        │  h2
│ Vende: MATU, piloto académico, sin │  text-base
│ persona jurídica. En este piloto no│
│ se emite boleta.                   │
│ Reclamos: escríbenos a             │
│ cuidaconmatu@gmail.com.            │  EnlaceEnFrase mailto
│ ┌ Tu pedido ─────────────────────┐ │  la boleta (9.4)
│ │ Productos (3)          $53.470 │ │
│ │ Envío (uno por pedido)  $3.990 │ │
│ │ ══════════════════════════════ │ │
│ │ Total                  $57.460 │ │  text-2xl font-bold
│ │ Este total vale hasta las      │ │
│ │ 16:45.                         │ │
│ │ Se cobra una sola vez este     │ │
│ │ total, con crédito o con débito│ │
│ │ No hay reserva ni cobros       │ │
│ │ después.                       │ │
│ └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │  borde cortado
│ (aviso de los 2 minutos, 9.5)      │
│ Condiciones del pedido (se abre en │  EnlaceSolo
│ otra pestaña)                      │
│ [ ] Leí y acepto las condiciones   │  casilla size-6, etiqueta min-h-12
│     del pedido.                    │
│ [ Pagar $57.460 ]       (MATU-62)  │  principal. Único turquesa macizo
│ No pagar no tiene costo.           │  text-base
│ Cancelar pedido                    │  textoPeligro
└────────────────────────────────────┘
```

**Orden del DOM, el mismo en todos los anchos:** una parte de lectura (cambios, productos, «Cambiar el pedido», entrega, si falta, quién vende) y después la parte de decisión (la boleta, el aviso del plazo, las condiciones, la casilla, «Pagar» y la salida). En el teléfono se lee todo y al final se decide. En pantalla ancha, la parte de decisión es la columna derecha (9.9).

### 9.2 Lo que cambió (C15 y C25)

**Va solo si algo cambió.** Se marca contra el precio y el comercio que la familia vio en su pedido (C15), y en dos lugares: **todo junto arriba**, para leerlo de una vez, y **en cada línea**, para encontrarlo al revisar.

| Dónde | Componente y tokens | Texto |
|---|---|---|
| Arriba | `Nota tono="rocio"` con `RefreshCw` en `turquesa` (`aria-hidden`) y `rol="status"`: se anuncia al llegar (C25). Título en negrita y una `ul` con un `li` por cambio | Título: «Cambió desde tu pedido» **[NUEVO]** |
| Salió | `li` | «Ya no hay `{producto}`. Salió del pedido.» [A4] |
| Otro comercio | `li` | «Ahora `{producto}` lo prepara `{comercio}` (comercio ficticio).» **[AJUSTE]** de «Ahora lo prepara `{comercio}`.» [A4]: arriba hay varios cambios juntos, y sin el producto no se sabe de cuál habla |
| Otro precio | `li`, las cifras en `cifras` | «Cambió el precio de `{producto}`: antes `{precio}`, ahora `{precio}`.» **[AJUSTE]** de «Cambió el precio: antes…» [A4], por la misma razón |
| En la línea, otro precio | `Etiqueta tono="atenta"` con `ArrowDownUp` `size-4` `aria-hidden` | «Cambió el precio» **[NUEVO]**, de la escena 21 de la demo |
| En la línea, otro comercio | `Etiqueta tono="atenta"` con `Store` `size-4` `aria-hidden` | «Otro comercio» **[NUEVO]**, de la escena 21 de la demo |

- **Nunca solo por color:** cada cambio es una frase, y en la línea una palabra con un ícono de forma distinta.
- **Lo que salió no está en «Productos» ni suma en la boleta.** Solo está arriba.
- **No se tacha** el precio de antes: tachado se lee como descuento (MATU-59 4.3).

### 9.3 Los productos

`h2` «Productos» **[NUEVO]**, `titular text-2xl`. Una `ul flex flex-col gap-3`, cada `li` `rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea`:

| Parte | Componente y tokens | Texto |
|---|---|---|
| Producto | `h3 text-xl font-bold break-words` | `{producto}` |
| Comercio | `p text-base break-words` | «De `{comercio}` (comercio ficticio)» (7.4) |
| Cantidad y precio | `p text-lg tabular-nums` | «`{cantidad}` × `{precio}`» **[NUEVO]**, de la demo |
| Subtotal | `p text-lg`, la cifra en `cifras font-bold` | «Subtotal: `{precio}`» (7.4) |
| Cambio | La `Etiqueta` de 9.2, si cambió | — |
| Si falta | `p text-base` | «Si falta: lo buscamos en otro comercio.» o «Si falta: lo sacamos y te devolvemos su precio.» **[NUEVO]** (C1: la elección de RF-21) |
| Retracto | `p text-lg max-w-prose`, «Derecho a retracto:» en negrita | Uno de los dos textos [L 27]. Letra igual a la del precio (C2) |

**Para cambiar algo** (cantidad, regla, sacar, agregar): «Cambiar el pedido», justo después de la lista (9.12). `Volver` «Volver a tu pedido» **[NUEVO]** arriba sigue siendo navegación: lleva al carrito sin cambiar el estado, y el carrito se ve sin controles con la nota de 7.9.

### 9.4 La boleta

Es el componente `Boleta` de la demo (`Demo/src/familia/Pedidos.tsx`), reconstruido en `web/` **solo con renglones de dinero exacto** (ESPEC-ADR-027, 2): `section aria-labelledby`, `rounded-t-lg bg-hoja px-4 @3xl/main:px-7 pt-5 pb-8 ring-1 ring-linea` y el borde cortado con la máscara de la demo (`[mask:radial-gradient(circle_at_50%_100%,transparent_0.42rem,var(--color-tinta)_0.45rem)_bottom/1.1rem_100%_repeat-x]`). La máscara es una medida de composición, no un color: no es un token nuevo.

| Renglón | Construcción | Texto |
|---|---|---|
| Título | `h2 text-xl font-bold`, con `ReceiptText` `size-5 text-turquesa` `aria-hidden` | «Tu pedido» [A4] (el título del carrito: es lo mismo, ahora con total) |
| Productos | Renglón: texto a la izquierda, cifra a la derecha (`flex justify-between gap-4`, la cifra `cifras`), `text-lg` | «Productos (`{n}`)» **[NUEVO]** |
| Envío | Igual | «Envío (uno por pedido)» [A4] |
| Separador | `hr border-0 border-t-2 border-tinta` | — |
| Total | `text-2xl font-bold` | «Total» **[AJUSTE]** de «Total con IVA» [A4], por [JC-IVA]: en Chile todos los precios llevan el IVA incluido, y «con IVA» junto al total se lee como algo que se sumó |
| Plazo | `p text-base`, la hora en `cifras` | «Este total vale hasta las `{HH:MM}`.» [A4] |
| Cobro | `p text-base` | «Se cobra una sola vez este total, con crédito o con débito. No hay reserva ni cobros después.» [A4] |

**El mismo total en todas partes:** la bajada, la boleta y «Pagar `{total}`» muestran la misma cifra (ESPEC-ADR-027, 2).

### 9.5 El aviso antes de que venza (C23, WCAG 2.2.1)

- **Cuándo:** cuando quedan 120 segundos, contados desde que llegó la respuesta con `vigencia_segundos` (3.1). Si al llegar ya quedan menos de 120, aparece de inmediato.
- **Dónde:** justo bajo la boleta, antes de las condiciones y de «Pagar». Es donde está Carmen cuando va a pagar. En pantalla ancha, en la columna derecha, que siempre está a la vista.
- **Cómo:** `Nota tono="atenta"` con `Clock` `aria-hidden` y `rol="status"` (se anuncia una vez, sin mover el foco). **No es una cuenta regresiva:** el texto no cambia cada segundo.

| Parte | Texto | Origen |
|---|---|---|
| Aviso | Quedan 2 minutos para pagar este total. | [A4] |
| Botón dentro del aviso | `Boton variante="secundario"` «Volver a confirmar» | [A4] |

- **«Volver a confirmar» con un toque, sin perder nada:** confirma de nuevo con el mismo pedido, con el total todavía vigente (JC1: el contrato lo acepta y da 15 minutos nuevos, sin cancelar ni volver a `borrador`), y la pantalla se redibuja con la hora nueva y los cambios si los hay. Se anuncia: «Confirmamos de nuevo. Este total vale hasta las `{HH:MM}`.» **[NUEVO]**. Mientras confirma, el botón dice «Confirmando…» y la línea de estado, «Estamos confirmando que haya cada producto…» [A4].
- **La casilla no se desmarca** al volver a confirmar si no cambió nada. Si cambió algo (9.2), se desmarca y el anuncio suma «Revisa lo que cambió antes de pagar.» **[NUEVO]**: aceptó otras cifras.

### 9.6 El total venció

```
│ ┌ Tu pedido ─────────────────────┐ │
│ │ …                              │ │
│ │ Total                  $57.460 │ │
│ │ [⏱ Venció]                     │ │  Etiqueta atenta, Clock
│ │ Este total venció a las 16:45. │ │
│ └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │
│ ┃ (⏱) Pasaron 15 minutos y el     │  Nota atenta borde, rol="status"
│ ┃ total venció. Vuelve a confirmar│
│ ┃ para ver lo que hay y su precio.│
│ [ Volver a confirmar ]             │  principal. Único turquesa macizo
│ No pagar no tiene costo.           │
│ Cancelar pedido                    │
```

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Marca en la boleta | `Etiqueta tono="atenta"` con `Clock`, junto al total | «Venció» **[NUEVO]** | C25: «vencido» con palabra |
| Plazo | Reemplaza la línea del plazo | «Este total venció a las `{HH:MM}`.» **[NUEVO]** | — |
| Aviso | `Nota tono="atenta" borde` con `Clock`, `rol="status"`, en el lugar del aviso de 9.5 | «Pasaron 15 minutos y el total venció. Vuelve a confirmar para ver lo que hay y su precio.» | [A4] |
| Acción | `Boton` principal | «Volver a confirmar» | [A4] |

- **Desaparecen la casilla y «Pagar».** Mientras el total está vencido no existe ningún botón de pago (escena 31 de la demo).
- **Los montos siguen a la vista y en `tinta`**, sin opacidad: Carmen tiene que poder comparar con el total nuevo. La palabra «Venció» dice que ya no vale.
- **Foco:** si estaba en la casilla, en el enlace de las condiciones o en «Pagar» (que desaparecen), pasa a la `Nota` del aviso (`enfocable`). Si estaba en otra parte, no se mueve: un cambio de contexto sin pedirlo desorienta.
- **No es un error:** nada se perdió y nada se cobró. `atenta`, nunca `pronto`.
- **El servidor manda:** si `GET` o `pagar` (MATU-62) dicen `vencido` antes de que la pantalla lo calcule, se muestra este estado igual.

### 9.7 Entrega, si falta, quién vende y reclamos (C1)

Tres `section` con su `h2 titular text-2xl` **[NUEVO]**: «Entrega», «Si falta un producto», «Quién vende». Reclamos va dentro de «Quién vende».

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Cuándo llega | `p text-base` | «Entrega: `{ventana_entrega}`» → «Entrega: Entre 24 y 48 horas hábiles» | [A4], [D8] |
| Dirección | `p text-base`, y la referencia en `text-tenue`. Debajo, para admin y cuidador, `Boton variante="texto"` «Cambiar dirección» (8.6) | La copia de la dirección en el pedido | [A4] |
| Teléfono | `p text-base`, `entrega.telefono_contacto` con el formato «+56 9 5555 0177» y dos `cifras` (DISENO.md 2). Debajo, para admin y cuidador, `Boton variante="texto"` «Cambiar teléfono» (7.8.1, con `PUT …/contacto`) | «Teléfono de contacto: `{telefono}`» | [A4] y 7.8 |
| Si falta | `p text-base max-w-prose` | «Si al retirar falta un producto, lo buscamos en otro comercio y pagas lo mismo. Si nadie lo tiene, o elegiste sacarlo, anulamos su cobro el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.» | [A4] |
| Vendedor | `p text-base max-w-prose` | «Vende: MATU, piloto académico, sin persona jurídica. En este piloto no se emite boleta.» | [A4], [D8] |
| Reclamos | `p text-base`, el correo con `EnlaceEnFrase` `mailto:` | «Reclamos: escríbenos a `{correo}`.» con `resumen.canal_reclamo` (cuidaconmatu@gmail.com) | [A4], [D8] |

- **«En este piloto no se emite boleta» y el componente «boleta».** El componente se llama así en el código y en DISENO.md, pero **en pantalla su título es «Tu pedido»**, nunca «Boleta», para no contradecir al vendedor.
- El vendedor y la boleta se arman con `resumen.vendedor` y `resumen.boleta` dentro de la frase de [A4]; la ventana, con `resumen.ventana_entrega`. Si el contrato los cambiara, la frase de la pantalla no cambia sin pasar por `lenguaje.md`.

### 9.8 Las condiciones y la casilla (D6)

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Enlace, antes de la casilla | Enlace solo, `inline-flex min-h-12` (DISENO.md 6), `target="_blank" rel="noopener"`, a `/condiciones-pedido` (O6) | «Condiciones del pedido (se abre en otra pestaña)» | [A4] y la regla de DISENO.md 6 |
| Casilla | La casilla de DISENO.md 6: `size-6 accent-turquesa` dentro de su etiqueta `min-h-12`. Sin el enlace dentro (para no marcarla al tocarlo) | «Leí y acepto las condiciones del pedido.» | [D6] |
| Sin marcar, al tocar «Pagar» (MATU-62) | `MensajeError` bajo la casilla, foco a la casilla | «Marca que leíste y aceptas las condiciones para pagar.» **[NUEVO]**, con la forma de «Marca que leíste el aviso para seguir.» [L 25.4] |

- **En MATU-61 la casilla se construye y guarda su estado en la memoria de la página.** La aceptación se envía y se registra al pagar, en MATU-62 (D6).
- **Se lee antes de aceptar:** el enlace va antes que la casilla, y en otra pestaña, para no perder el resumen ni el plazo.
- **La página `/condiciones-pedido`** usa el armado de `/privacidad` (`docs/diseno/matu-75-privacidad.md`): título «Condiciones del pedido» **[NUEVO]**, la versión y la fecha arriba, el texto en Markdown, sin índice (son diez secciones cortas). Es pública: se lee sin entrar.

### 9.9 «Pagar» (MATU-62) y la salida

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Pagar **(MATU-62)** | `Boton` principal con `Lock` `size-5` `aria-hidden`. **Único `turquesa` macizo** de la pantalla con el total vigente. Va después de la casilla. En MATU-61 **no se construye**: el lugar queda vacío, y la salida va justo bajo la casilla | «Pagar `{total}`» | ESPEC-ADR-027, escena 21 |
| Pagar, estados | Normal · vencido: no existe (9.6) · casilla sin marcar: el error de 9.8 al tocarlo, nunca deshabilitado · enviando: «Pagando…» **[NUEVO]** | — | MATU-62 |
| Salida | `p text-base`, bajo «Pagar» | «No pagar no tiene costo.» | [A4] |
| Cancelar | `Boton variante="textoPeligro"`, abre 10 | «Cancelar pedido» | [A4] |

**Mientras MATU-62 no está**, el resumen no tiene botón macizo con el total vigente. Es intencional: no se dibuja un botón de pago que no paga.

### 9.10 Pantalla ancha (1280 y 1920 px)

```
┌───────────────┬───────────────────────────────────────────────────────────────────────────┐
│ (M) MATU      │ Insumos   Lista de insumos   Catálogo   Pedido                            │
│               │ ‹ Volver a tu pedido                                                      │
│               │ Antes de pagar                                                            │
│               │ Confirmamos que hay cada producto. El total es $57.460.                   │
│               │ ┃(i) Precios de ejemplo. …                                                │
│               │ ┌ (↻) Cambió desde tu pedido ───────────┐  ┌ Tu pedido ──────────────────┐ │
│               │ │ · Ya no hay Toallitas húmedas x80. …  │  │ Productos (3)       $53.470 │ │
│               │ └───────────────────────────────────────┘  │ Envío (uno por pedido)$3.990│ │
│               │ Productos                                  │ ═══════════════════════════ │ │
│               │ ┌ Pañal adulto M x30 ───────────────────┐  │ Total               $57.460 │ │
│               │ │ … Subtotal: $25.980 · Si falta: …     │  │ Este total vale hasta las   │ │
│               │ │ Derecho a retracto: …                 │  │ 16:45. Se cobra una sola…   │ │
│               │ └───────────────────────────────────────┘  └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │
│               │ Si cambias algo, antes de pagar …          Condiciones del pedido (…)     │
│               │ [ Cambiar el pedido ]                      [ ] Leí y acepto las condicio… │
│               │ Entrega …                                  [ Pagar $57.460 ]  (MATU-62)   │
│               │ Si falta un producto …                     No pagar no tiene costo.       │
│               │ Quién vende …                              Cancelar pedido  (sticky top-6)│
└───────────────┴───────────────────────────────────────────────────────────────────────────┘
```

- **Dos columnas desde `@3xl/main`:** `grid grid-cols-1 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-x-10`. La izquierda es la parte de lectura; la derecha, la de decisión, en `sticky top-6` con `max-h-[calc(100dvh-3rem)] overflow-y-auto [scrollbar-width:thin]`. Es la regla de DISENO.md 3 para el pedido: a la izquierda los productos, a la derecha la boleta.
- **El aviso del piloto va arriba, a todo el ancho**, lejos de «Pagar» (DISENO.md, «Rótulos del piloto»).
- **A 1920 px:** el `main` llega a `max-w-7xl`. La derecha mide unos 470 px: la boleta no se estira de más.

### 9.11 Pagador

Ve el resumen igual, sin «Cambiar el pedido» ni su frase, sin «Cambiar dirección» ni «Cambiar teléfono», y sin «Cancelar pedido». **No confirma ni cancela** (JC3, arquitectura 11.2), así que:
- el aviso de los 2 minutos (9.5) va sin el botón, y dice «Quedan 2 minutos para pagar este total.» [A4] igual;
- con el total vencido (9.6), en lugar de la frase y del botón: «Pasaron 15 minutos y el total venció. Pídele a quien armó el pedido que lo vuelva a confirmar.» **[NUEVO]**, sin ningún botón macizo.

«Pagar» y quién lo ve se deciden en MATU-62. **El observador no llega al resumen:** su vista no trae `resumen`.

### 9.12 Cambiar el pedido (JC2)

**Objetivo:** Carmen ve el total, se da cuenta de que le falta un paquete, y vuelve a su pedido para cambiarlo sin perder nada ni cancelar.

**Qué hace:** devuelve el pedido de `total_confirmado` a `borrador` con las mismas líneas, las mismas reglas de «Si falta» y la misma dirección, y lleva a `/insumos/pedido` con los controles de nuevo. El total confirmado deja de valer: para pagar hay que tocar «Ver el total» otra vez. No cobra nada.

**Dónde va:** en la parte de lectura, **justo después de la lista de «Productos»** y antes de «Entrega». Es donde Carmen está cuando nota que quiere otra cantidad, y queda lejos de «Pagar» y de «Cancelar pedido», en la otra columna en pantalla ancha. Va también en el pie del carrito sin controles (7.9).

**Jerarquía:** segunda del resumen, por debajo de «Pagar» (MATU-62). `Boton variante="secundario"`, sin ícono y sin flecha, `self-start`. Nunca en `turquesa` macizo.

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Frase, antes del botón | `p text-base text-tenue max-w-prose mt-4`, en el `aria-describedby` del botón | Si cambias algo, antes de pagar confirmamos el total de nuevo. | **[NUEVO]** |
| Botón | `Boton variante="secundario"` | Cambiar el pedido | **[NUEVO]**, de JC2 |
| En curso | Mismo ancho, `aria-busy` | Abriendo tu pedido… | **[NUEVO]** |
| Hecho | Lleva a `/insumos/pedido` en `borrador`, con la `Nota tono="rocio"` `rol="status"` de 7.3. Foco al `h1` | Ya puedes cambiar tu pedido. Cuando termines, toca «Ver el total» para confirmarlo de nuevo. | **[NUEVO]** |
| Error de conexión | `MensajeError` bajo el botón. El resumen sigue igual | No pudimos abrir tu pedido para cambiarlo. Revisa tu conexión y vuelve a intentarlo. El total sigue confirmado. | **[NUEVO]** |
| 409 o 412, otra persona lo cambió | La fila de 11.2 | Este pedido cambió mientras lo revisabas. Te mostramos cómo quedó. | 11.2 |

- **Sin confirmación:** no se pierde nada ni se cobra nada, y volver a confirmar es un toque. Si la casilla de las condiciones estaba marcada, se desmarca (vive en la memoria de la página y aceptó otras cifras).
- **No es «Volver a tu pedido».** `Volver` es navegación y deja el total como está; «Cambiar el pedido» es una acción y lo deja sin confirmar. Por eso la acción lleva su frase antes, que dice la consecuencia.
- **Con el total vencido** (9.6): «Cambiar el pedido» sigue en su lugar si el contrato acepta la vuelta a `borrador` desde `vencido`; si no, no se muestra, y la única acción es «Volver a confirmar».
- **Admin y cuidador.** El pagador y el observador no lo ven.

---

## 10. Cancelar el pedido

**Objetivo:** Carmen deja el pedido sin costo, sabiendo que no se cobró nada.

Desde el carrito (7.9) y el resumen (9.9). **Cancelan admin y cuidador**, sin pagar (JC3). El pagador y el observador no ven «Cancelar pedido». Patrón del diálogo de MATU-44 4.1: `<dialog>` modal con `showModal()`, `max-w-md`, el foco inicial en el título, la región de error vacía y sin animación.

```
┌──────────────────────────────────┐
│ ¿Cancelar este pedido?           │  h2 text-xl font-bold, tabIndex -1
│ No tiene costo.                  │  p text-base
│ [ Cancelar pedido ] Seguir con   │  peligroPrincipal · texto
│                     el pedido    │
└──────────────────────────────────┘
```

| Parte | Texto | Origen |
|---|---|---|
| Título | ¿Cancelar este pedido? | [A4], la primera frase de «¿Cancelar este pedido? No tiene costo.» |
| Texto | No tiene costo. | [A4], la segunda frase |
| Botones | Cancelar pedido (`peligroPrincipal`, macizo `pronto`: no se deshace) · Seguir con el pedido (`texto`) | [A4] |
| En curso | Cancelando… | **[NUEVO]** |
| Hecho | Cierra el diálogo, el carrito queda vacío (7.10) y bajo la bajada, `Nota tono="ok"` `rol="status"`: «Cancelamos el pedido. No se cobró nada.» El foco va al `h1` | **[NUEVO]**, mismo verbo que el botón |
| Error de conexión | En la región de error del diálogo: «No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.» | **[NUEVO]**, con la forma de [L 22] |
| 409, ya cancelado por otra persona | Cierra el diálogo y muestra el vacío con `Nota tono="rocio"`: «Otra persona de tu grupo ya canceló este pedido.» | **[NUEVO]**, con la forma de [L 22] |

`Esc` y «Seguir con el pedido» cierran sin cancelar y devuelven el foco a «Cancelar pedido». En MATU-61 solo se cancela antes de pagar (C6).

---

## 11. Errores

Por `type`, nunca por `title`, `detail` ni `status` (`lenguaje.md` 8).

### 11.1 Al cargar el carrito o el resumen (red o 5xx)

Patrón de una sola columna: baldosa `bg-tinta/7 text-tenue` con `CloudOff`, el texto en `Anunciado urgencia="alert"` y el `Boton` principal «Volver a intentar» [L 26], que es el único macizo. Nunca un pedido viejo en su lugar.

> No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo. **[NUEVO]**, con la forma de [L 27]

### 11.2 Por acción

| Cuándo | `type` o caso | Dónde y cómo | Texto | Origen |
|---|---|---|---|---|
| Ver el total o volver a confirmar, sin conexión | red o 5xx | `Nota tono="atenta"` con `CloudOff`, `rol="alert"`, sobre el botón | No pudimos confirmar el total. Revisa tu conexión y vuelve a intentarlo. Tu pedido sigue aquí. | **[NUEVO]** |
| Confirmar, ningún producto disponible | 409 `nada-disponible` | `Nota tono="atenta"` con `PackageX`, `rol="alert"`, sobre «Ver el total». El carrito queda igual | Ahora ningún comercio tiene estos productos. No hay nada que pagar. Tu pedido sigue aquí para intentarlo más tarde. | **[NUEVO]** |
| Confirmar sin dirección | 409 `sin-direccion` | El error de 7.9 bajo «Dirección» | Agrega la dirección de entrega para ver el total. | **[NUEVO]** |
| Confirmar con el carrito vacío | 409 `pedido-vacio` | Vuelve a pedir el pedido y muestra el vacío (7.10) | — | — |
| Agregar desde el catálogo o la lista, y ya hay otro pedido abierto (carrera entre dos personas) | 409 `pedido-abierto` | La pantalla lee ese pedido y agrega ahí, sin preguntar | — | — |
| Cualquier escritura del pedido | 409 `estado-pedido`, o 412 del pedido: otra persona lo canceló, lo confirmó o lo cambió | `Nota tono="rocio"` con `Info`, `rol="status"`, bajo la bajada, y la pantalla vuelve a pedir el pedido | Este pedido cambió mientras lo revisabas. Te mostramos cómo quedó. | **[NUEVO]** |
| Cualquier ruta del pedido | 404 | Patrón de una sola columna, baldosa `bg-tinta/7`, `SearchX`, y `Boton` secundario «Ir a tu pedido» **[NUEVO]** | No encontramos este pedido. | [A4] |
| Cualquier ruta del pedido | 403 `sin-autorizacion-pedidos` (se retiró la autorización mientras tanto) | 4 para admin y cuidador, 4.4 para el pagador y el observador. **Sin `pronto`**: no es culpa de nadie | Los de 4 | — |
| Cualquier ruta del pedido | 403 `revision-vencida` | 4.5 | Los de 4.5 | — |
| La dirección | 412 | 8.5 | — | — |
| La dirección, el teléfono, la cantidad | 422 con `errores[].campo` | Bajo el campo | Los de 7.5, 7.8.1 y 8.3 | — |
| Cualquier otro, sin respuesta | — | Donde ocurrió | No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí. | [L 8] |
| La capa 3 apagada | 404 del catálogo o del pedido | No se muestran la pestaña «Pedido», «Agregar al pedido» ni «Pedir estos productos». Quien abra `/insumos/pedido` ve: | El pedido no está disponible por ahora. | **[NUEVO]**, con la forma de [L 27] |

**Sin conexión, la regla de MATU:** lo que Carmen escribió (la dirección, el teléfono) sigue en su campo. Lo que ya se guardó en el servidor no se pierde. Nada se cobra.

---

## 12. Grupo familiar: el permiso de los pedidos (D1)

Un tercer bloque en Grupo familiar, después de «Permiso para calcular sus insumos», con el mismo contenedor, ícono y botón de MATU-44 3.3 y 3.4. Solo con la capa 3 encendida.

### 12.1 Estados del bloque

| `estado` de `despacho` | Ícono | Frase | Botón (admin y cuidador) | Origen |
|---|---|---|---|---|
| `vigente` | `ShieldCheck` `text-ok` | Autorizado el `{otorgado_en}`. | `peligro` «Retirar la autorización» | [L 22], la forma de los insumos |
| `revision_vencida` | `Hourglass` `text-atenta` | Autorizado el `{otorgado_en}`. Hay que renovarlo desde el `{revision_vence_en}`. | `peligro` «Retirar la autorización» | [L 22] |
| `retirada` | `ShieldOff` `text-tenue` | Autorización retirada el `{revocado_en}`. | `secundario` «Volver a autorizar» | **[AJUSTE]** de [L 22]: sin la frase del borrado a los 90 días. Al retirar, lo sin pagar se cancela y su entrega se borra en el momento (D1), así que no hay nada que vuelva |
| `sin_autorizar` | `ShieldQuestion` `text-tenue` | Sin permiso todavía. Se pide la primera vez que haces un pedido. | Ninguno | **[NUEVO]**, con la forma de [L 22] |

**Propuesta de O12, abierta:** en los estados `vigente`, `revision_vencida` y `retirada`, si hay una dirección guardada, debajo del botón del bloque va `Boton variante="texto"` «Ver la dirección de entrega» **[NUEVO]** (nombre accesible: «Ver la dirección de entrega de `{pila}`»), que lleva a `/insumos/pedido/direccion` con `Volver` «Volver a Grupo familiar» [L 22]. Así se puede vaciar (8.7) aunque se haya retirado la autorización. Solo admin y cuidador.

| Parte | Texto | Origen |
|---|---|---|
| Título del bloque | Permiso para pedir sus insumos | **[NUEVO]**, con la forma de «Permiso para calcular sus insumos» [L 22] |
| Nombres accesibles | Retirar la autorización de los pedidos de `{pila}` · Volver a autorizar los pedidos de `{pila}` | **[NUEVO]**, con la forma de [L 22] |
| Pagador y observador | Los de MATU-44 3.6, sin cambios | [L 22] |

### 12.2 La confirmación de retirar

El diálogo de MATU-44 4.1, con estos puntos en la lista **[NUEVO]**, para que el analista los revise (tocan lo que se borra):

| Parte | Texto |
|---|---|
| Título | ¿Retirar la autorización de los pedidos de `{pila}`? |
| Puntos | Ya no se pueden hacer pedidos para `{pila}` desde MATU, desde ahora. · **Cancelamos sin costo los pedidos sin pagar y borramos la dirección y el teléfono que se copiaron en ellos.** (en negrita: no vuelve) · Los pedidos ya pagados siguen hasta que se entreguen. · La dirección de entrega de `{pila}` queda guardada para cuando vuelvas a autorizar. Puedes vaciarla cuando quieras. · La lista de insumos se puede seguir imprimiendo y compartiendo. · Su ficha, sus insumos y los enlaces de relevo no cambian. |
| Botones, en curso, error de conexión, ya retirada | Los de [L 22], sin cambios |
| Hecho | Autorización retirada. Ya no se pueden hacer pedidos para `{pila}`. |

El punto de los pedidos pagados es cierto desde MATU-62. En MATU-61 no hay pedidos pagados, pero el texto no cambia cuando lleguen.

### 12.3 La dirección de la persona al retirar (O7, JC6)

**La dirección guardada se conserva** al retirar la autorización de pedidos, y la confirmación lo dice en su cuarto punto (12.2): «La dirección de entrega de `{pila}` queda guardada para cuando vuelvas a autorizar. Puedes vaciarla cuando quieras.» **[NUEVO]**, para el analista. Se vacía con 8.7. Cómo se llega a esa pantalla con la autorización retirada es O12 (12.1). El primer punto cambia de «borramos su dirección y teléfono de entrega» a «borramos la dirección y el teléfono que se copiaron en ellos» **[AJUSTE]**, para no decir que se borra la de la persona.

### 12.4 Volver a autorizar (`/grupo/autorizar-pedidos`)

Patrón de MATU-44 5.2: la pantalla de 4.1 con `Volver` «Volver a Grupo familiar» [L 22], sin frase de estado (no hay nada que vuelva). Al autorizar, vuelve a `/grupo` con `Nota tono="ok"`: «Pedidos autorizados. Ya puedes hacer pedidos para `{pila}`.» **[NUEVO]**.

---

## 13. Accesibilidad visual

### 13.1 Elementos en `turquesa` macizo, por pantalla

| Pantalla y estado | Único macizo |
|---|---|
| La autorización (4) | «Autorizar los pedidos» |
| Por renovar (4.5), admin y cuidador | «Renovar la autorización» |
| El catálogo (5) | Ninguno (los «Agregar al pedido» son secundarios) |
| La lista (6) | El de MATU-60, sin cambios («Pedir estos productos» es secundario) |
| El carrito (7) | «Ver el total» |
| El carrito con el total confirmado, sin controles (7.9) | «Ver el total» («Cambiar el pedido» es secundario) |
| El carrito vacío (7.10) | Ninguno |
| La dirección (8) | «Guardar la dirección» («Vaciar la dirección» es `textoPeligro`) |
| El diálogo de vaciar la dirección (8.7) | Ninguno en `turquesa`: «Vaciar la dirección» es macizo `pronto` |
| El conflicto de la dirección (8.5) | «Guardar la mía» |
| El resumen, vigente (9) | «Pagar `{total}`» (MATU-62). En MATU-61, ninguno («Cambiar el pedido» es secundario) |
| El resumen, vencido (9.6) | «Volver a confirmar» |
| Error al cargar (11.1) | «Volver a intentar» |
| El diálogo de cancelar (10) | Ninguno en `turquesa`: «Cancelar pedido» es macizo `pronto` |

### 13.2 Áreas táctiles de 48 × 48 px

Todo lo que se toca mide `min-h-12` (51 px): los botones (`Boton`), el − y el + (`size-12`), el campo de cantidad (`min-h-12`), cada opción de «Si falta este producto», la casilla con su etiqueta, el enlace de las condiciones (enlace solo, `inline-flex min-h-12`), el `mailto` de reclamos (enlace en frase con el `::after`, DISENO.md 6), las pestañas y «Sacar del pedido». Entre el + y el campo hay `gap-2` (8 px); entre la cantidad y «Sacar del pedido» hay dos bloques de texto, lejos del pulgar.

### 13.3 Contraste (valores de DISENO.md, sin colores nuevos)

| Elemento | Colores | Contraste |
|---|---|---|
| Texto de la línea, precio, retracto | `tinta` y `tenue` sobre `hoja` | 7,2:1 o más en claro, 8,1:1 o más en oscuro |
| Aviso del piloto, aviso de los 2 minutos, vencido, conflicto | `tinta` sobre `atenta-fondo`, ícono en `atenta` | 5,9:1 el semántico sobre su fondo; el texto en `tinta`, más |
| «Cambió el precio», «Otro comercio», «Venció» | `Etiqueta tono="atenta"` | La de DISENO.md 6. Lo mido en la revisión, en los dos temas |
| Cambios arriba | `tinta` sobre `rocio`, ícono `turquesa` | 5,6:1 el ícono en claro, 6,7:1 en oscuro |
| «En tu pedido» | Ícono `ok` sobre `hoja` | 6,9:1 en claro, 9,6:1 en oscuro (MATU-59 6) |
| Borde de los campos y las opciones | `borde` | 3,5:1 sobre `hoja` (WCAG 1.4.11) |
| La boleta | `tinta` sobre `hoja`, separador `tinta` | El separador es decoración; el texto, 14:1 o más |

### 13.4 Foco

- El foco base (contorno de 3 px en `turquesa`, 2 px de separación) en todo lo que se toca. El de `textoPeligro` y `peligroPrincipal` va en `pronto`, como en sus variantes.
- Al llegar a cada ruta, el foco va al `h1`.
- **Orden de Tab en la línea:** −, campo, +, el grupo «Si falta» (una parada; las flechas cambian la opción), «Sacar del pedido».
- Las regiones que reciben el foco por una acción (`Nota` del vencido, del conflicto) son `enfocable`, sin contorno: no son controles.
- **Lo fijo abajo no tapa el foco:** el `scroll-padding-bottom` de la capa base ya cubre la barra de secciones del teléfono (DISENO.md 3).

### 13.5 Estado nunca solo por color

| Estado | Palabra | Forma |
|---|---|---|
| Opción de «Si falta» elegida | El texto de la opción | El punto dentro del círculo y el anillo |
| En tu pedido | «En tu pedido» | `CircleCheck` |
| Salió | «Ya no hay `{producto}`. Salió del pedido.» | Va en la lista de cambios, no en «Productos» |
| Cambió el precio | «Cambió el precio» | `ArrowDownUp` |
| Otro comercio | «Otro comercio» | `Store` |
| Venció | «Venció» y «Este total venció a las…» | `Clock`, y sin casilla ni «Pagar» |
| Por renovar, retirada | Las frases de 12.1 | `Hourglass`, `ShieldOff` |

### 13.6 Regiones vivas (C25)

| Qué | Región |
|---|---|
| Agregar, sacar, guardar el teléfono | `anunciar(texto, 'status')` |
| Llegar al carrito después de una acción (7.3, 6.4), incluidos «Cambiar el pedido» y «Vaciar la dirección» | `Nota` `rol="status"` |
| Lo que cambió al confirmar (9.2) | `Nota` `rol="status"` |
| Quedan 2 minutos (9.5) y el vencido (9.6) | `Nota` `rol="status"`: se anuncian sin interrumpir. No son errores |
| Volver a confirmar, hecho | `anunciar(…, 'status')` |
| Errores de conexión y el 412 | `rol="alert"` |
| «Estamos confirmando que haya cada producto…» | `p role="status"` junto al botón, con `aria-busy` en el botón |

### 13.7 Texto al 200 % a 320 px (160 px de app, modo `angosto`)

- Todo en una columna. Las líneas, las notas y la boleta pasan a `px-2` (`angosto:px-2`).
- El −, el campo y el + bajan de renglón por `flex-wrap` si no caben (en 160 px: 102 px de campo más 51 de cada botón no caben juntos, así que el campo queda solo en su renglón, con un botón arriba y otro abajo). Es lo que ya hace el `Stepper` en la lista y en «Compré»: se revisa con captura.
- Las opciones de «Si falta» con el indicador arriba y el texto debajo (DISENO.md 6, MATU-57).
- La boleta: el texto a la izquierda y la cifra a la derecha pasan a `flex-wrap`: la cifra baja bajo su texto, alineada a la izquierda (`angosto:flex-col angosto:items-start`). «$57.460» va en `cifras` y no se parte.
- El retracto sigue en `text-lg`, igual que el precio: con el zoom crecen juntos (C2).
- Los botones de los avisos van uno bajo otro, a todo el ancho, con el relleno de su variante (DISENO.md 3, `angosto:`).
- `document.documentElement.scrollWidth` igual a `clientWidth`.

### 13.8 Movimiento

Sin transiciones al llegar. Las notas aparecen después de una acción con el fundido `aparecer` de 180 ms, y con `prefers-reduced-motion` aparecen de inmediato (ya en la capa base). Nada parpadea al acercarse el vencimiento.

### 13.9 Tema oscuro y proyector

Solo tokens: no hay nada aparte que especificar. En la revisión miro las `Etiqueta` `atenta`, la boleta con su máscara (que la máscara no deje ver el `papel` como una línea clara) y el `rocio` de los cambios. Ningún texto de estas pantallas usa `text-sm`.

---

## 14. Lo que el frontend no debe hacer

- Guardar el carrito, la dirección, el teléfono o la intención de pedir en `localStorage`, `sessionStorage`, la URL o el historial (C18). La intención de 4 vive en la memoria de la página.
- Calcular el total, el envío o el vencimiento por su cuenta. La suma «Productos» del carrito es la única cuenta de la pantalla, y no se llama total.
- Usar el reloj del teléfono para el vencimiento (3.1).
- Mostrar una cuenta regresiva que cambie cada segundo.
- Deshabilitar «Ver el total» o «Pagar». Se valida al tocarlos.
- Mostrar «Pagar» con el total vencido.
- Ordenar los comercios o las líneas por precio.
- Escribir colores, tamaños o sombras a mano. La máscara de la boleta es la única clase arbitraria nueva, y es geometría.
- Usar «stock», «carro», «carrito», «reserva», «monto real», «estimado», «aprox.» o cualquier término de `lenguaje.md` 3. **Excepción:** «No hay reserva ni cobros después.» de la boleta (9.4, [A4]), que la niega, como en la sección 1 y en `lenguaje.md` 31. El `grep` del criterio 19 la descuenta.

---

## 15. Textos para `lenguaje.md`, sección 31 «Pedido (MATU-61)»

**Regla de la sección:** en la app se dice «tu pedido», nunca «carro» ni «carrito». Se dice «lo que hay» y «que haya», nunca «stock». La cantidad es en envases del catálogo. **Todos los precios llevan el IVA incluido** (JC-IVA): el total se llama «Total», nunca «Total con IVA», y ningún texto presenta el IVA como algo que se suma o que aparece después. «IVA» solo va en «Precio de ejemplo · IVA incluido» [L 27]. «Pedir» lo hace solo quien tiene la autorización de pedidos. La lista nunca compra sola, el aviso nunca ofrece comprar y «Compré» nunca hace un pedido (D10).

**Cambios en otras secciones (D10):**
- Sección 21: «La lista nunca ofrece comprar» pasa a «La lista nunca compra sola. Solo quien tiene la autorización de pedidos puede tocar "Pedir estos productos".»
- Sección 23: «la app nunca ofrece comprar» pasa a «"Compré" anota lo que la familia ya compró, y nunca hace un pedido».
- Sección 27: la nota «No tiene botón «Pedir»: llega con MATU-61» pasa a «"Agregar al pedido" está en cada comercio que tiene el producto, para quien administra o cuida».

| Dónde | Texto | Origen |
|---|---|---|
| Pestaña de Insumos | Pedido | **[NUEVO]** |
| `<title>` | Tu pedido · MATU · ¿Dónde lo entregamos? · MATU · Antes de pagar · MATU · Condiciones del pedido · MATU | — |
| **Autorización** | | |
| Título | Antes de pedir, un permiso | **[NUEVO]** |
| Explicación | Para pedir desde MATU, primero autoriza los pedidos. Sin esta autorización igual puedes imprimir o compartir la lista. · Es un permiso aparte del de su ficha y del de sus insumos. | [A4] · **[NUEVO]** |
| Volver | Volver al catálogo · Volver a la lista de insumos | **[NUEVO]** |
| Botón | Autorizar los pedidos · Autorizando… | [A4] · [L 22] |
| Hecho | Pedidos autorizados. Agregamos «{producto}» a tu pedido. · Pedidos autorizados. Agrega productos desde el catálogo o desde tu lista de insumos. | **[NUEVO]** |
| Error | No pudimos guardar la autorización. Revisa lo que elegiste y vuelve a intentarlo. | [L 22] |
| Pagador, sin autorización | Falta la autorización de pedidos para {pila}. Sin ella no se pueden hacer pedidos desde MATU. Pídele a quien administra el grupo o a quien cuida a {pila} que la dé. | **[NUEVO]** |
| Por renovar | Hay que renovar la autorización de los pedidos de {pila}. Se renueva una vez al año. Mientras tanto no se pueden hacer pedidos, pero tu pedido sigue guardado. · Renovar la autorización · Pídele a quien administra el grupo o a quien cuida a {pila} que la renueve. | **[NUEVO]** |
| Declaraciones | `declaracion_pedidos_<calidad>`, de la política 0.12 | Analista |
| **Catálogo** | | |
| Botón | Agregar al pedido · Agregando… · Para el lector: Agregar al pedido: {producto}, de {comercio} | **[NUEVO]** |
| Ya agregado | En tu pedido · Ver tu pedido | **[NUEVO]** |
| Anuncio | Agregamos «{producto}» a tu pedido. | **[NUEVO]** |
| Error | No pudimos agregarlo. Revisa tu conexión y vuelve a intentarlo. | **[NUEVO]** |
| **Lista de insumos** | | |
| Frase y botón | Los productos de esta lista que están en el catálogo se pueden pedir con MATU. Antes de pagar ves el total. · Pedir estos productos · Agregando a tu pedido… | **[NUEVO]** · [D10] · **[NUEVO]** |
| Al llegar al pedido | Agregamos {n} productos de tu lista a tu pedido. (1: «Agregamos 1 producto de tu lista a tu pedido.») · {producto} ya estaba en tu pedido: dejamos la cantidad de la lista. · No están en el catálogo y no van en el pedido: {nombres}. (1: «{nombre} no está en el catálogo y no va en el pedido.») | **[NUEVO]** |
| **Tu pedido** | | |
| Título y bajada | Tu pedido · Revisa los productos y cuántos quieres. Antes de pagar confirmamos que haya. | [A4] |
| Comercio | De {comercio} (comercio ficticio) | **[AJUSTE]** de [L 27] |
| Precio | {precio} cada uno · Precio de ejemplo · IVA incluido | **[NUEVO]** · [L 27] |
| Cantidad | Cantidad · el sufijo de [L 21] · Para el lector: Quitar uno: {producto} · Agregar uno: {producto} | [L 21] · **[AJUSTE]** de [A4] |
| De la lista | En tu lista: {cantidad} | **[NUEVO]** |
| Cantidad fuera de rango | Escribe una cantidad de 1 a 99. | **[NUEVO]** |
| Cantidad, error al guardar | No pudimos guardar la cantidad. Revisa tu conexión y vuelve a intentarlo. | **[NUEVO]** |
| Subtotal | Subtotal: {precio} | **[NUEVO]** |
| Si falta | Si falta este producto · Buscarlo en otro comercio · El mismo producto. Pagas lo mismo. · Sacarlo del pedido y devolverme su precio · Nunca lo cambiamos por otra marca ni por otro producto. (una vez sobre las líneas, O9) | [A4] |
| Si falta, error | No pudimos guardar qué hacer si falta. Revisa tu conexión y vuelve a intentarlo. | **[NUEVO]** |
| Si falta, pagador y resumen | Si falta: lo buscamos en otro comercio. · Si falta: lo sacamos y te devolvemos su precio. | **[NUEVO]** |
| Sacar | Sacar del pedido · Para el lector: Sacar del pedido: {producto} · Sacamos «{producto}» del pedido. · No pudimos sacarlo. Revisa tu conexión y vuelve a intentarlo. | [A4] · **[NUEVO]** |
| Entrega | Entrega · Dirección · Todavía no hay una dirección de entrega. · Agregar la dirección · Cambiar dirección · Teléfono de contacto · (tu celular) · Cambiar teléfono · Llega entre 24 y 48 horas hábiles. | **[NUEVO]** · [A4] · **[AJUSTE]** de [D8] |
| Teléfono | Para que quien entrega pueda avisarte. Si es el de otra persona, avísale. · Guardar el teléfono · Guardamos el teléfono. · Escribe un celular de Chile, por ejemplo +56 9 5555 0137. | [A4] · **[NUEVO]** · [L 8] |
| Pie | Productos: {precio} · El envío y el total los ves al confirmar que haya cada producto. · Ver el total · Confirmando… · Estamos confirmando que haya cada producto… | **[NUEVO]** [JC-IVA] · [A4] |
| Sin dirección | Agrega la dirección de entrega para ver el total. | **[NUEVO]** |
| Total ya confirmado | Ya confirmaste el total. Para cambiar algo, toca «Cambiar el pedido». | **[NUEVO]** (cambia en la 1.1, JC2) |
| Vacío | Tu pedido está vacío. Agrega productos desde el catálogo o desde tu lista de insumos. · Ir al catálogo · Ir a la lista de insumos · Pagador y observador: Todavía no hay un pedido para {pila}. | [A4] · **[NUEVO]** |
| Pagador y observador | Quien administra el grupo o quien cuida a {pila} puede cambiar el pedido y ver el total. · Ver el resumen (solo el pagador) · Pasaron 15 minutos y el total venció. Pídele a quien armó el pedido que lo vuelva a confirmar. | **[NUEVO]** |
| **Dirección** | | |
| Título y ayuda | ¿Dónde lo entregamos? · La usamos solo para entregar tus pedidos. Ningún comercio la ve. · La guardamos para los próximos pedidos de {pila}. | [A4] · **[NUEVO]** |
| Campos | Calle · Número · Depto (opcional) · Comuna · Referencia (opcional) · Por ejemplo: portón verde. No escribas datos de salud. | [A4] |
| Botón y hecho | Guardar la dirección · Guardando… · Guardamos la dirección. | **[NUEVO]** · [L 23] |
| Vaciar (JC6) | Si no quieres que MATU la guarde, puedes vaciarla. Para el próximo pedido habrá que escribirla de nuevo. · Vaciar la dirección · Para el lector: Vaciar la dirección de entrega de {pila} · ¿Vaciar la dirección de entrega de {pila}? · La borramos de MATU. Para el próximo pedido habrá que escribirla de nuevo. · Dejarla como está · Vaciando… · Vaciamos la dirección. · No pudimos vaciar la dirección. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba. · Otra persona de tu grupo cambió la dirección mientras la revisabas. Revisa cómo quedó antes de vaciarla. | **[NUEVO]** |
| Validación | Escribe la calle. · Escribe el número. Si no tiene, escribe S/N. · Escribe la comuna. · La referencia admite hasta 200 caracteres. Acórtala un poco. · No pudimos guardar la dirección. Revisa los datos y vuelve a intentarlo. | **[NUEVO]** |
| Volver | Volver a tu pedido · Volver a antes de pagar | **[NUEVO]** |
| Conflicto (412) | Otra persona de tu grupo cambió la dirección mientras la cambiabas. · No guardamos la tuya encima de la suya. Elige cuál dejar. · La que guardó · La tuya, sin guardar · Guardar la mía · Dejar la que guardó · Dejaste la dirección que guardó otra persona de tu grupo. | **[AJUSTE]** de [L 18] · **[NUEVO]** el último |
| **Antes de pagar** | | |
| Título y bajada | Antes de pagar · Confirmamos que hay cada producto. El total es {total}. | [A4] · **[NUEVO]** [JC-IVA] |
| Cambiar el pedido (JC2) | Si cambias algo, antes de pagar confirmamos el total de nuevo. · Cambiar el pedido · Abriendo tu pedido… · Ya puedes cambiar tu pedido. Cuando termines, toca «Ver el total» para confirmarlo de nuevo. · No pudimos abrir tu pedido para cambiarlo. Revisa tu conexión y vuelve a intentarlo. El total sigue confirmado. | **[NUEVO]** |
| Cambios | Cambió desde tu pedido · Ya no hay {producto}. Salió del pedido. · Ahora {producto} lo prepara {comercio} (comercio ficticio). · Cambió el precio de {producto}: antes {precio}, ahora {precio}. · Cambió el precio · Otro comercio | **[NUEVO]** · [A4] · **[AJUSTE]** de [A4] · **[NUEVO]** |
| Productos | Productos · {cantidad} × {precio} · Subtotal: {precio} | **[NUEVO]** |
| Retracto | Los dos de la sección 27, en cada línea, con letra no menor que el precio | [L 27] |
| Boleta | Tu pedido · Productos ({n}) · Envío (uno por pedido) · Total · Este total vale hasta las {HH:MM}. · Se cobra una sola vez este total, con crédito o con débito. No hay reserva ni cobros después. | [A4] · **[NUEVO]** «Productos ({n})» · **[AJUSTE]** «Total», de «Total con IVA» [A4], por [JC-IVA] |
| Plazo | Quedan 2 minutos para pagar este total. · Volver a confirmar · Confirmamos de nuevo. Este total vale hasta las {HH:MM}. · Revisa lo que cambió antes de pagar. | [A4] · **[NUEVO]** |
| Vencido | Venció · Este total venció a las {HH:MM}. · Pasaron 15 minutos y el total venció. Vuelve a confirmar para ver lo que hay y su precio. · Volver a confirmar | **[NUEVO]** · [A4] |
| Entrega | Entrega: {ventana} · Teléfono de contacto: {telefono} | [A4], [D8] |
| Si falta | Si falta un producto · Si al retirar falta un producto, lo buscamos en otro comercio y pagas lo mismo. Si nadie lo tiene, o elegiste sacarlo, anulamos su cobro el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco. | **[NUEVO]** el título · [A4] |
| Vendedor y reclamos | Quién vende · Vende: MATU, piloto académico, sin persona jurídica. En este piloto no se emite boleta. · Reclamos: escríbenos a {correo}. | **[NUEVO]** el título · [A4], [D8] |
| Condiciones | Condiciones del pedido (se abre en otra pestaña) · Leí y acepto las condiciones del pedido. · Marca que leíste y aceptas las condiciones para pagar. | [A4] · [D6] · **[NUEVO]** |
| Pagar (MATU-62) | Pagar {total} · Pagando… | Demo · **[NUEVO]** |
| Salida | No pagar no tiene costo. · Cancelar pedido | [A4] |
| **Cancelar** | ¿Cancelar este pedido? · No tiene costo. · Cancelar pedido · Seguir con el pedido · Cancelando… · Cancelamos el pedido. No se cobró nada. · No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba. · Otra persona de tu grupo ya canceló este pedido. | [A4] · **[NUEVO]** |
| **Errores** | No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo. · No pudimos confirmar el total. Revisa tu conexión y vuelve a intentarlo. Tu pedido sigue aquí. · Ahora ningún comercio tiene estos productos. No hay nada que pagar. Tu pedido sigue aquí para intentarlo más tarde. · Este pedido cambió mientras lo revisabas. Te mostramos cómo quedó. · No encontramos este pedido. · Ir a tu pedido · El pedido no está disponible por ahora. | **[NUEVO]** · [A4] el 404 |
| **Grupo familiar** | Permiso para pedir sus insumos · Autorizado el {fecha}. · Autorizado el {fecha}. Hay que renovarlo desde el {fecha}. · Autorización retirada el {fecha}. · Sin permiso todavía. Se pide la primera vez que haces un pedido. · Para el lector: Retirar la autorización de los pedidos de {pila} · Volver a autorizar los pedidos de {pila} | [L 22] · **[AJUSTE]** · **[NUEVO]** |
| Ver la dirección (O12, propuesta) | Ver la dirección de entrega · Para el lector: Ver la dirección de entrega de {pila} | **[NUEVO]** |
| Retirar | ¿Retirar la autorización de los pedidos de {pila}? · Ya no se pueden hacer pedidos para {pila} desde MATU, desde ahora. · Cancelamos sin costo los pedidos sin pagar y borramos la dirección y el teléfono que se copiaron en ellos. · Los pedidos ya pagados siguen hasta que se entreguen. · La dirección de entrega de {pila} queda guardada para cuando vuelvas a autorizar. Puedes vaciarla cuando quieras. · La lista de insumos se puede seguir imprimiendo y compartiendo. · Su ficha, sus insumos y los enlaces de relevo no cambian. · Autorización retirada. Ya no se pueden hacer pedidos para {pila}. | **[NUEVO]**, para el analista |
| Volver a autorizar, hecho | Pedidos autorizados. Ya puedes hacer pedidos para {pila}. | **[NUEVO]** |
| Aviso del piloto | El de la sección 11, una vez por pantalla con precios: el carrito y el resumen | [L 11] |

**Ninguno usa** los términos de `lenguaje.md` 3, «stock», «carro», «carrito», «reserva», «tope», «estimado», «aprox.» ni «monto real». «Boleta» aparece solo en «En este piloto no se emite boleta».

---

## 16. Criterios visuales verificables

1. En cada pantalla y estado, **un solo elemento en `turquesa` macizo** como dice 13.1. En el catálogo y en el carrito vacío, ninguno.
2. **Cada línea del carrito y del resumen tiene su retracto con un `font-size` calculado igual o mayor al del precio** (19 px y 19 px; 38 px y 38 px con el texto al 200 %). Lo mido con las herramientas del navegador.
3. Cada línea del carrito tiene «Si falta este producto» con «Buscarlo en otro comercio» elegido por omisión. **Ninguna pantalla ofrece otra marca ni otro producto.**
4. El − y el + de la cantidad miden 48 × 48 px o más, tienen nombre accesible con el producto, y el campo se escribe con el teclado numérico y **selecciona su contenido al recibir el foco**.
5. Ningún botón «Ver el total», «Pagar» ni «Guardar la dirección» está deshabilitado. Sin dirección, «Ver el total» muestra el error y lleva el foco a «Agregar la dirección».
6. «Cambió el precio», «Otro comercio», «Salió del pedido» y «Venció» se entienden **en escala de grises**: cada uno tiene palabra e ícono.
7. Con el total vencido **no existe** la casilla ni «Pagar», y está «Volver a confirmar» como único macizo. La boleta sigue con sus montos en `tinta`.
8. El aviso «Quedan 2 minutos para pagar este total.» aparece una vez, con «Volver a confirmar», y **no hay ningún número que cambie cada segundo** en la pantalla.
9. El resumen muestra los puntos de C1, cada uno visible sin abrir nada: productos con cantidad, precio y subtotal; lo que salió; lo que cambió; la elección de «Si falta» por línea; el envío aparte; el total y su hora; quién vende y «En este piloto no se emite boleta»; la entrega; qué pasa si falta, con el medio y el plazo; el retracto en cada línea; el reclamo; el enlace a las condiciones; y «No pagar no tiene costo.» con «Cancelar pedido».
10. La bajada, la boleta y «Pagar» (MATU-62) muestran **la misma cifra** de total.
11. Ningún comercio aparece sin «(comercio ficticio)» en su línea mientras `ficticio` sea `true`. No aparecen el RUT, la razón social, la dirección ni el teléfono de un comercio.
12. El aviso «Precios de ejemplo.» aparece **exactamente una vez** en el carrito y en el resumen, arriba, lejos del botón principal. No aparece en el vacío ni en los errores.
13. La dirección no tiene mapa, ni «usar mi ubicación», ni región. La ayuda de la referencia dice «No escribas datos de salud.» y va antes del campo.
14. Con la capa 3 apagada no se ven la pestaña «Pedido», «Agregar al pedido» ni «Pedir estos productos».
15. El pagador y el observador no ven «Agregar al pedido», «Pedir estos productos», el − y el +, las opciones de «Si falta», «Sacar del pedido», «Cambiar dirección», «Cambiar teléfono», «Ver el total», «Volver a confirmar», «Cambiar el pedido», «Vaciar la dirección» ni «Cancelar pedido». El observador no ve la entrega ni llega al resumen. El cuidador sí ve y usa «Cancelar pedido» (JC3).
16. A 320 px, a 360 px y con el texto al 200 % a 320 px, `document.documentElement.scrollWidth` es igual a `clientWidth` en las cinco rutas, el diálogo y el conflicto.
17. Ningún texto de estas pantallas mide menos de 17 px de `font-size` calculado.
18. Nada del pedido, la dirección ni el teléfono en `localStorage`, `sessionStorage` ni en la URL: las rutas son las de 2.1, sin parámetros ni fragmento.
19. Ninguna palabra de la lista de 14 aparece en pantalla (un `grep` sobre los textos de la pantalla), salvo «No hay reserva ni cobros después.» de la boleta.
20. En el resumen, el título de la boleta dice «Tu pedido», nunca «Boleta».
21. **«IVA» aparece solo en «Precio de ejemplo · IVA incluido»** (JC-IVA). La boleta dice «Total», la bajada dice «El total es `{total}`.» y el carrito dice «El envío y el total los ves al confirmar…». Ningún texto dice «con IVA», «más IVA» ni «+ IVA» (un `grep` sobre los textos de la pantalla).
22. En el resumen vigente, «Cambiar el pedido» está **después de la lista de productos y antes de «Entrega»**, en `secundario`, con su frase antes. Al tocarlo se llega a `/insumos/pedido` con el − y el + de nuevo, las mismas líneas, las mismas reglas de «Si falta» y la nota «Ya puedes cambiar tu pedido…». No hay ningún diálogo de por medio.
23. «Volver a confirmar» del aviso de los 2 minutos, con el total todavía vigente, deja la pantalla en el resumen con una hora nueva 15 minutos después, sin pasar por el carrito ni por el vacío. Cambiar la dirección desde el resumen hace lo mismo.
24. Con el total confirmado, el carrito no tiene el −, el +, las opciones de «Si falta» ni «Sacar del pedido», y muestra «Ya confirmaste el total. Para cambiar algo, toca «Cambiar el pedido».». Sin la nota «El envío y el total los ves al confirmar…», que va solo en `borrador`, tampoco en la vista del pagador ni del observador.
27. Con el teléfono abierto (7.8.1), «Teléfono de contacto» se lee una sola vez en pantalla: el `h3` nombra el campo.
25. «Vaciar la dirección» está solo con una dirección guardada, en `textoPeligro` y separado de «Guardar la dirección» por el borde. Su diálogo usa el mismo verbo en el título y en el botón macizo `pronto`, y «Dejarla como está» devuelve el foco a «Vaciar la dirección».
26. El carrito no muestra el envío ni un total antes de confirmar (JC5): el único monto del pie es «Productos: `{precio}`».

---

## 17. Cómo la voy a revisar

Capturas a 320 px con el texto al 200 %, 360 px, 1280 px y 1920 px, en tema claro y oscuro, con la semilla del catálogo de MATU-59 y un pedido sintético para María Soto (Carmen como cuidadora, Rodrigo como pagador):

- La autorización, desde el catálogo y desde la lista, con las tres calidades.
- El catálogo con «Agregar al pedido», «Agregando…» y «En tu pedido».
- La lista con «Pedir estos productos», y el carrito al llegar con un producto que ya estaba y otro que no está en el catálogo.
- El carrito con tres productos, una línea venida de la lista, una con «Sacarlo del pedido…» elegido, sin dirección y con dirección, el teléfono abierto y el error de cantidad.
- El carrito vacío, como Carmen y como Rodrigo.
- La dirección, vacía, llena, con errores y con el conflicto (412), y «Vaciar la dirección» con su diálogo, su error y el carrito después.
- «Ver el total» cargando, con un producto que salió, uno que cambió de precio y uno que cambió de comercio.
- El resumen vigente, con el aviso de los 2 minutos (con el reloj del servidor de pruebas adelantado) y «Volver a confirmar» antes de que venza, y vencido.
- «Cambiar el pedido» desde el resumen, el carrito al llegar, y el carrito sin controles abierto desde la pestaña con el total confirmado.
- El diálogo de cancelar como cuidadora (Carmen).
- El diálogo de cancelar y el carrito después.
- Los errores de 11 (backend detenido, 404, 409 y la capa 3 apagada).
- Grupo familiar con el bloque de pedidos en sus cuatro estados y la confirmación de retirar.
- Los criterios 1 a 26 de la sección 16, uno por uno, y el U4: cambiar «Toallitas húmedas x80» de 1 a 3 con un toque en el campo y un dígito, y con el + dos veces.
