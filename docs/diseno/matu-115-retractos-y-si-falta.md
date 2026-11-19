# MATU-115 · Lo que se pidió devolver en «Datos de» y «Si falta antes de pagar» · Especificación de diseño

**Versión 1.0 · 18/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Viene de:** la tarjeta MATU-115; los motivos de rechazo de `lenguaje.md` 38 (C24 de MATU-81, decisión 468); el bloque «Lo que pediste devolver» de MATU-116 (`matu-116-pagos-propios.md` 2.3, textos N2 a N6), con el que se coordina; y MATU-54 3.4.8 («Sus pedidos» de «Datos de»), que esta especificación amplía.

**Es frontend y textos.** No hay tokens nuevos y `Demo/DISENO.md` no cambia. Se usa lo que ya existe: `bg-hoja`, `ring-linea`, `border-linea`, `text-tinta`, `text-tenue`, `cifras`, `Etiqueta` (tonos `neutro` y `ok`), y el patrón de la subsección «Lo que pasó con tu pedido» de `DatosPersona.tsx` (MATU-81).

**Se construye en:**
- `web/src/familia/DatosPersona.tsx`: dentro de `Pedido`, una subsección nueva (1.4) y la frase de la devolución por arrepentimiento (1.6);
- `web/src/familia/textosMisDatos.ts`: los textos de 1.7; los de las etiquetas y los motivos se importan de `textosTusPedidos.ts` (`devolucionPedida`, `devueltoEl`, `noSeAcepto`, `MOTIVO_RECHAZO_FAMILIA`), nunca se copian;
- `web/src/familia/textosPedido.ts`: `siFaltaOtro` (2).

**Marcas:** **[L n]** ya está en `lenguaje.md`, sección n. **[116 Nn]** es un texto de MATU-116 que se usa igual. **[AJUSTE]** es un texto de MATU-116 o de `lenguaje.md` con un cambio de forma, que aprueba Jorge. **[NUEVO]** lo propongo yo, entra a `lenguaje.md` 35 y lo aprueba Jorge.

**En la interfaz nunca se dice** «retracto», «rechazado», «rechazo», «solicitud» ni «sello roto». La familia lee «devolver», «arrepentirse de la compra» y «No se aceptó la devolución» [L 38].

---

## 0. Lo que hay hoy (leído en el código de la rama `matu-115-si-falta-y-retractos`, 18-11)

No levanté la pantalla para esta especificación: lo que falta es una parte que no existe. La revisión visual (sección 5) se hace con la pantalla funcionando.

| # | Dónde | Qué pasa hoy | Qué implica |
|---|---|---|---|
| **H1** | `DatosPersona.tsx`, `Pedido` | `PedidoCopia.retractos` (`RetractoCopia[]`, desde MATU-63) llega en la respuesta y en el archivo, y **la pantalla no lo muestra**. «Datos de» dice «Todo lo que MATU guarda de {nombre_pila}» y no lo cumple | Es el alcance de esta tarjeta (1) |
| **H2** | `RetractoCopia` en `docs/api/openapi.json` | Trae `estado`, `solicitado_en`, `plazo_hasta`, `incluye_envio`, `resuelto_en`, `motivo_rechazo` y `lineas` (`producto`, `cantidad`). **No trae quién lo pidió.** `RetractoCuentaCopia` tampoco, pero ahí no hace falta: es siempre «tú» | En el resto de «Datos de», quien hizo algo se nombra con `PersonaNombrada` («La registró Carmen…», «Lo pagó Rodrigo…», «Lo cambió por última vez…»). Sin el campo, la línea no puede decir quién. **No elijo yo:** lo informo al orquestador (6, P1). Mientras tanto, la pantalla funciona sin él (1.5) |
| **H3** | `textosMisDatos.ts`, `devolucion` | `DevolucionCopia.motivo` tiene cuatro valores y el texto cubre tres: con `motivo: retracto`, la línea cae en el `else` y dice **«Se devolvieron $X porque se canceló el pedido.»**, que es falso | Defecto de texto que se ve justo cuando hay un arrepentimiento. Se corrige en esta tarjeta (1.6). **P1 para el frontend:** dice una cosa que no pasó, sobre dinero |
| H4 | `DatosPersona.tsx`, `LoQuePaso` | Sus `li` llevan `items-start`, que MATU-54 3.4 (1.2, P1-1) prohíbe en las filas de la copia | No es de esta tarjeta. La subsección nueva no lo copia (1.4), y lo reviso en la sección 5 (criterio 8) |
| H5 | `textosPedido.ts`, `siFaltaOtro` | Lo usan tres pantallas: el carrito de quien paga y de quien administra con el total confirmado (`Pedido.tsx` ~1278), el carrito de «Se informa» (`Pedido.tsx` ~1170, MATU-113) y el resumen antes de pagar (`Resumen.tsx` ~556) | Un solo cambio de texto cambia las tres (2) |

---

## 1. «Datos de {nombre_pila}»: lo que se pidió devolver

### 1.1 Objetivo

Carmen abre «Datos de María» y ve, en cada pedido, si alguien del grupo pidió devolver productos, cuáles, cómo terminó y, si no se aceptó, por qué.

### 1.2 Dónde va

**Dentro de cada pedido de «Sus pedidos»** (MATU-54 3.4.8), no como un bloque aparte:
- `RetractoCopia` vive dentro de `PedidoCopia`: el pedido es su contexto (el número, los productos, lo devuelto).
- La frase de la devolución en dinero («Se devolvieron {monto} porque…», 1.6) ya está en el mismo pedido. Separarlas obligaría a cruzarlas por el número.
- No cambia el índice ni el orden de los bloques de MATU-54 3.1.

Es la diferencia con «Tus datos» (MATU-116 2.3), donde va un bloque propio: ahí los retractos llegan sueltos (`RetractoCuentaCopia`, con su `referencia` y su `grupo`) porque la cuenta no tiene un bloque de pedidos.

**Orden dentro del pedido** (MATU-54 3.4.8 más lo nuevo):
1. Título, estado y «Lo armaron el…»
2. Líneas y montos
3. Pago, devoluciones (con la frase nueva de 1.6) y «Pago de prueba…»
4. Entrega
5. **Lo que se pidió devolver** (nuevo, solo si `retractos` trae al menos uno)
6. Lo que pasó con tu pedido (MATU-81)

Va antes de «Lo que pasó con tu pedido» porque es algo que pidió la familia; lo que sigue es lo que anotó el equipo de MATU.

### 1.3 Jerarquía, dentro del pedido

1. **Primero:** el título de la subsección, «Lo que se pidió devolver».
2. **Segundo:** en cada pedido de devolución, la `Etiqueta` con el estado (palabra e ícono).
3. **Tercero:** cuándo se pidió, quién (si llega, 1.5), los productos con su cantidad, si incluye el envío, y, si no se aceptó, cuándo se respondió y por qué.

No hay acción: es una copia que se lee. Ningún botón, ningún enlace.

### 1.4 Componentes y tokens

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Subsección | `section aria-labelledby` con `flex w-full max-w-prose flex-col gap-2 border-t border-linea pt-3`, igual que `LoQuePaso` | — | — |
| Título | `h4 font-bold` | Lo que se pidió devolver | **[AJUSTE]** de [116 N2] «Lo que pediste devolver»: en «Datos de» no lo pidió necesariamente quien lee |
| Lista | `ul flex flex-col gap-3`; si hay más de uno, `divide-y divide-linea` y cada `li` con `pt-3` salvo el primero (`first:pt-0`) | — | — |
| Cada uno | `li flex min-w-0 flex-col gap-1`, **sin `items-start`** (MATU-54 3.4, P1-1) | — | — |
| Estado | `Etiqueta` con `self-start`, ícono `size-3.5 shrink-0 aria-hidden` y palabra en `span min-w-0` | `solicitado`: Devolución pedida (`neutro`, `Clock`) · `devuelto`: Devuelto el {fecha de `resuelto_en`} (`ok`, `CircleCheck`), la fecha en `cifras` · `rechazado`: No se aceptó la devolución (`neutro`, `CircleX`) | [L 38], los mismos tonos e íconos de MATU-116 2.3 |
| Cuándo y quién | `p text-base text-tenue break-words` | Sin quién (hoy): Se pidió el {fecha}. · Con quién (si el contrato lo trae, 1.5): Lo pidió {nombre} el {fecha}. | **[AJUSTE]** de [116 N4] «Lo pediste el {fecha}.» · **[NUEVO]** con el molde de «Lo pagó {nombre} el {fecha}.» [L 35] |
| Productos | `ul list-disc ps-5 text-base marker:text-tenue`, un `li break-words` por línea | {producto} × {cantidad}, la cantidad en `cifras` | El formato de las líneas de MATU-54 3.4.8 (1.3, con el espacio no separable) |
| El envío, solo con `incluye_envio: true` | `p text-base` | También se pidió devolver el envío. | **[NUEVO]** |
| Cuándo se respondió, solo `rechazado` con `resuelto_en` | `p text-base text-tenue` | Respondimos el {fecha}. | [116 N5] |
| Por qué no se aceptó, solo `rechazado` con `motivo_rechazo` | `p max-w-prose text-base` | `sello_abierto`: El producto volvió con el sello abierto. · `producto_no_recibido`: No recibimos el producto de vuelta. | [L 38] (`MOTIVO_RECHAZO_FAMILIA`, importado) |

Reglas:
- **Las fechas son días** (`DD/MM/AAAA`), sin la hora, como en «Tus datos» (MATU-116 2.3) y como «Devuelto el {fecha}» de «Tus pedidos». Van en `<time dateTime>` con `cifras`, con el desfase de Chile, con el mismo componente que usa la copia para los días (`DiaDeInstante`). **Nunca «hoy» ni «ayer»** (MATU-54 3.4).
- **Sin montos.** `RetractoCopia` no trae lo devuelto: está arriba, en «Devuelto: {monto}» y en la frase de 1.6.
- **`plazo_hasta` no se muestra.** Es la fecha hasta la que se podía pedir, ya pasó o no cambia nada de lo que se pidió, y va en el archivo. Es el mismo criterio de `etiqueta` en la dirección (MATU-54 3.4.1).
- **Sin el grupo (N6) ni T4.** La copia es de una persona de un grupo: el grupo es siempre el mismo, y los productos siempre se ven.
- **Sin nombre de la persona cuidada** en esta parte: ya está en el título de la página.
- **Orden:** el del servidor. El cliente no reordena.
- **Un `estado` o un `motivo_rechazo` que el cliente no conoce** no rompe la fila: se omite esa palabra o esa línea, y el resto se ve (MATU-54 3.4, «Los enumerados»).
- **`devuelto` con `resuelto_en: null`** (no debería pasar): la etiqueta dice «Devuelto» **[NUEVO, la palabra de [L 38] sin la fecha]**.
- **`lineas` vacía:** no se muestra la lista, y el resto sí.

### 1.5 Quién lo pidió (H2)

En «Datos de», todo lo que hizo una persona dice quién (MATU-54 3.4: «La registró…», «Lo escribió…», «Lo pagó…»), y quien salió del grupo se nombra «alguien que ya no está en el grupo». Nunca el correo.

- **Hoy** el contrato no lo trae. La línea dice **«Se pidió el {fecha}.»**, y quién lo pidió está en «Quién abrió o editó la ficha», en el hecho 28 (`pidio_un_retracto`): «Pidió arrepentirse de la compra del pedido {referencia}», con «a las {HH:MM} · {nombre}» [L 35]. Con eso la persona puede saberlo en la misma página.
- **Si el orquestador decide agregar** `pedido_por: PersonaNombrada | null` a `RetractoCopia` (es lo que propongo, sección 6), la línea pasa a **«Lo pidió {nombre} el {fecha}.»**, con `nombreDe()` como «Lo pagó…»: con `nombre: null` y `activo: false`, «Lo pidió alguien que ya no está en el grupo el {fecha}.».
- El frontend construye solo la variante que el contrato permita. **No deduce quién lo pidió del historial** (cruzar por número y fecha es frágil y, si se equivoca, nombra a otra persona).

### 1.6 La devolución en dinero por arrepentimiento (H3)

En «Sus pedidos», la frase de cada `devoluciones[]` (MATU-54 3.4.8) suma el cuarto motivo:

| `motivo` | Texto | Origen |
|---|---|---|
| `retracto`, con `producto` | Se devolvieron {monto} porque se pidió devolver {producto}. | **[NUEVO]** |
| `retracto`, sin `producto` | Se devolvieron {monto} porque se pidió devolver productos de este pedido. | **[NUEVO]** |
| `producto_no_entregado`, `pago_tardio`, `cancelacion` | Sin cambios | [L 35] |
| Un `motivo` que el cliente no conoce | Se devolvieron {monto}. | **[NUEVO]**. Nunca un «porque» que no corresponde: el `else` que hoy cae en «se canceló el pedido» desaparece |

- Con `estado: en_curso`, «Se devolvieron» cambia por «Se están devolviendo», como las demás [L 35].
- Mismo componente y tokens que hoy: `p max-w-prose text-base text-tenue break-words`, el monto en `cifras`.
- Se usa «se pidió devolver», el verbo de la subsección de abajo y de «Productos para devolver» [L 38], y no «se arrepintió», que se lee como un juicio sobre la persona.

### 1.7 Esquema a 360 px

Un pedido con dos pedidos de devolución, uno aceptado y uno no:

```
│ Sus pedidos                        │  h2 (MATU-54 3.4.8)
│ ┌────────────────────────────────┐ │  ul, bg-hoja rounded-xl ring-1 ring-linea
│ │ Pedido 4790                    │ │  h3 text-lg font-bold
│ │ (○ Entregado)                  │ │  Etiqueta
│ │ Lo armaron el 08/11/2026 a las │ │  text-base text-tenue
│ │ 11:02.                         │ │
│ │ Suplemento vainilla, caja × 2  │ │  dl de líneas (sin cambios)
│ │   $26.490                      │ │
│ │ …                              │ │
│ │ Total                 $57.460  │ │
│ │ Lo pagó Rodrigo el 08/11/2026  │ │  text-base
│ │ a las 11:24.                   │ │
│ │ Cobrado: $57.460 · Devuelto:   │ │
│ │ $26.490.                       │ │
│ │ Se devolvieron $26.490 porque  │ │  text-base text-tenue (1.6, nuevo)
│ │ se pidió devolver Suplemento   │ │
│ │ vainilla.                      │ │
│ │ Entrega: Los Aromos 123, …     │ │  text-base text-tenue
│ │ ────────────────────────────── │ │  border-t border-linea pt-3
│ │ Lo que se pidió devolver       │ │  h4 font-bold
│ │ (✓ Devuelto el 15/11/2026)     │ │  Etiqueta ok, self-start
│ │ Se pidió el 12/11/2026.        │ │  text-base text-tenue
│ │ • Suplemento vainilla × 1      │ │  ul list-disc
│ │ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │ │  divide-linea
│ │ (⊗ No se aceptó la devolución) │ │  Etiqueta neutro
│ │ Se pidió el 13/11/2026.        │ │
│ │ • Pañal adulto M × 1           │ │
│ │ Respondimos el 16/11/2026.     │ │  text-base text-tenue
│ │ El producto volvió con el sello│ │  text-base
│ │ abierto.                       │ │
│ │ ────────────────────────────── │ │
│ │ Lo que pasó con tu pedido      │ │  h4 (MATU-81, sin cambios)
│ └────────────────────────────────┘ │
```

**En el modo `angosto`** (320 px con el texto al 200 %): la tarjeta ya está en `px-2` (MATU-54 3.2). La `Etiqueta` oculta su ícono y queda la palabra (MATU-107, 6), que parte entre palabras y no se sale (`span min-w-0`); las viñetas de `ps-5` caben; los nombres de producto parten con `break-words`. Nada nuevo.

### 1.8 Pantalla ancha (1280 y 1920 px)

Sin cambios de composición: la grilla del índice de MATU-54 3.3, con «Sus pedidos» en la columna derecha. La subsección es una sola columna con `max-w-prose`, como «Lo que pasó con tu pedido»; la etiqueta no se estira (`self-start`). A 1920 px sigue el ancho máximo del `main`.

### 1.9 Estados

| Estado | Qué se ve |
|---|---|
| Pedido sin pedidos de devolución (`retractos: []`) | Ni la subsección ni su título. Lo normal |
| Capa 3 quitada (`pedidos: null`) | Sin «Sus pedidos» (MATU-54 3.4.8), así que tampoco esto |
| Autorización de pedidos retirada o capa apagada | Igual que hoy: «Sus pedidos» se ve, con la subsección si hay datos |
| Pedido de devolución en curso (`solicitado`) | «Devolución pedida», cuándo y los productos. Sin «Respondimos» ni motivo |
| Devuelto | «Devuelto el {fecha}», cuándo se pidió y los productos. La plata está arriba, en la frase de 1.6 |
| No aceptado, con motivo | Etiqueta, cuándo se pidió, productos, «Respondimos el…» y el motivo |
| No aceptado, sin motivo (`motivo_rechazo: null`) | Lo mismo, sin la línea del motivo |
| Cargando, error, límite de 10 por hora, autorización retirada | Los de la página, sin cambios (MATU-54 3.6 y MATU-107) |

No hay vacío propio, ni carga, ni error, ni 412: la parte llega con la página, es de solo lectura y no pide nada.

### 1.10 Accesibilidad

- **El estado no depende del color:** cada `Etiqueta` lleva palabra e ícono distinto (`Clock`, `CircleCheck`, `CircleX`); el tono `ok` es un refuerzo. En el modo `angosto` el ícono se oculta y queda la palabra, que basta sola (MATU-107, 6).
- **Contraste:** `text-tenue` sobre `bg-hoja` y las etiquetas `neutro` y `ok` ya están medidos en `DISENO.md` con al menos 4,5:1 en los dos temas. No hay combinaciones nuevas.
- **Lector:** el `h4` deja saltar por títulos: «Pedido 4790» (h3) → «Lo que se pidió devolver» (h4) → «Lo que pasó con tu pedido» (h4). Cada `li` se lee en el orden del esquema: estado, cuándo, productos, respuesta y motivo. El ícono es `aria-hidden`.
- **Nada se toca:** sin áreas táctiles nuevas. Nada se anuncia.
- **Impresión** (MATU-54 3.8): la subsección se imprime como el resto, sin reglas propias.

### 1.11 Textos

| # | Dónde | Texto | Va a |
|---|---|---|---|
| R1 | Título de la subsección | Lo que se pidió devolver | L 35, «Sus pedidos» (**[AJUSTE]** de 116 N2) |
| R2 | Cuándo, sin quién | Se pidió el {fecha}. | L 35 (**[AJUSTE]** de 116 N4) |
| R3 | Cuándo, con quién (solo si el contrato lo trae) | Lo pidió {nombre} el {fecha}. · Lo pidió alguien que ya no está en el grupo el {fecha}. | L 35 **[NUEVO]** |
| R4 | El envío | También se pidió devolver el envío. | L 35 **[NUEVO]** |
| R5 | Devuelto sin fecha | Devuelto | L 35 **[NUEVO]** |
| R6 | Devolución en dinero, `retracto` | Se devolvieron {monto} porque se pidió devolver {producto}. · Se devolvieron {monto} porque se pidió devolver productos de este pedido. | L 35, «Las devoluciones» **[NUEVO]** |
| R7 | Devolución en dinero, motivo desconocido | Se devolvieron {monto}. | L 35, «Las devoluciones» **[NUEVO]** |

Se usan sin cambios: «Devolución pedida», «Devuelto el {fecha}», «No se aceptó la devolución», «El producto volvió con el sello abierto.» y «No recibimos el producto de vuelta.» [L 38]; «Respondimos el {fecha}.» [116 N5].

---

## 2. «Si falta antes de pagar: lo buscamos en otro comercio.»

### 2.1 El cambio

| Antes | Ahora |
|---|---|
| Si falta: lo buscamos en otro comercio. | **Si falta antes de pagar: lo buscamos en otro comercio.** |

Cambia `PEDIDO.siFaltaOtro`, y con eso las tres pantallas de H5. «Si falta: lo sacamos y te devolvemos su precio.» y «Si falta: lo sacamos del pedido.» (MATU-113) **no cambian**: sacar el producto y devolver su precio vale antes y después de pagar, y buscar en otro comercio solo antes (condiciones 0.3, §5; cambios de la 1.4 de MATU-61).

En «Datos de», «Si falta: buscarlo en otro comercio» (MATU-54 3.4.8) tampoco cambia: nombra la opción que se eligió, con las palabras de la opción [L 31], no lo que se promete.

### 2.2 ¿Rompe la línea del producto?

**No.** El texto va en un `p text-base` sin `nowrap`, que parte entre palabras como cualquier frase. Lo que importa es la palabra más larga, y es la misma de antes: «comercio.» (9 caracteres).

Cálculo con Atkinson Hyperlegible, texto base de 17 px (raíz al 106,25 %):

| Ancho | Ancho útil de la línea | Palabra más larga | Renglones antes → ahora |
|---|---|---|---|
| 360 px, texto al 100 % | 360 − 32 (`main px-4`) − 32 (`li px-4`) = **296 px** | «comercio.» ≈ 76 px | 2 → 2 |
| 320 px, texto al 200 % (`angosto`) | 320 − 16 (`main angosto:px-2`) − 16 (`li angosto:px-2`) = **288 px** | «comercio.» ≈ 152 px a 34 px | 3 → 4 |
| 1280 y 1920 px | La columna derecha de la línea del carrito (`@2xl/linea:grid-cols-2`) o la `li` del resumen: más de 300 px | — | 1 o 2 |

A 360 px la frase entra en los mismos dos renglones («Si falta antes de pagar: lo / buscamos en otro comercio.»). A 320 px con el texto al 200 % suma un renglón y ninguna palabra se corta ni se sale.

**Cómo se parte:** como cae, sin ayuda. No va un espacio no separable ni un `<br>`: un salto fijo quedaría mal en el ancho donde no hace falta, y «antes de pagar» no pierde sentido si se parte. Los contenedores ya tienen `min-w-0` (la columna del carrito) o son una `li` de una columna (el resumen y «Se informa»).

Esto es un cálculo sobre el código, no una revisión: **la confirmo con la pantalla funcionando** (sección 5, criterios 9 a 11).

### 2.3 Lo que se actualizó en las especificaciones

- `docs/diseno/matu-61-pedido.md`, versión 1.5: 7.6 (pagador y observador), el esquema de 9.3, la tabla de 9.3 y la tabla de textos.
- `docs/diseno/matu-113-observador-sin-montos.md`: el esquema, la tabla de la línea, la lista de textos usados y el criterio 5, que citaban el texto viejo. La fila O5 queda como está: es el registro de una decisión.
- `docs/diseno/matu-54-mis-datos.md`, 3.4.8: una línea que remite a esta especificación.

**Para el orquestador, en `lenguaje.md`** (no lo edito yo): sección 31, fila «Si falta, pagador y resumen»; sección 31, «Se informa (MATU-113)», fila «Si falta»; y sección 35, R1 a R7.

---

## 3. Tokens y componentes

Ningún token nuevo. Ningún valor escrito a mano. Lo que se usa:
- Superficies y bordes: `bg-hoja`, `ring-linea`, `border-linea`, `divide-linea`.
- Texto: `text-tinta` (por omisión), `text-tenue`, `text-base`, `font-bold`, `cifras`, `marker:text-tenue`.
- Composición: `max-w-prose`, `min-w-0`, `break-words`, `ps-5`, `gap-1`, `gap-2`, `gap-3`, `pt-3`, `self-start`.
- Componentes: `Etiqueta` (`neutro`, `ok`), `DiaDeInstante`, `nombreDe`.
- Íconos de `lucide-react`: `Clock`, `CircleCheck`, `CircleX` (los de MATU-116 2.3).

## 4. Criterios visuales verificables

1. En «Datos de María», un pedido con un pedido de devolución muestra, después de «Entrega:» y antes de «Lo que pasó con tu pedido», un separador `border-linea` y el título «Lo que se pidió devolver» en negrita, de la misma medida que «Lo que pasó con tu pedido».
2. Un pedido sin pedidos de devolución no muestra ese título.
3. Cada pedido de devolución tiene una `Etiqueta` con ícono y palabra: «Devolución pedida» (reloj), «Devuelto el {DD/MM/AAAA}» (círculo con visto) o «No se aceptó la devolución» (círculo con cruz). Con el tema en escala de grises, se distinguen por la palabra y el ícono.
4. Los productos van en una lista con viñetas, «{producto} × {n}», y la cantidad no queda sola en un renglón.
5. Un pedido no aceptado con motivo muestra «Respondimos el {fecha}.» y, debajo, exactamente «El producto volvió con el sello abierto.» o «No recibimos el producto de vuelta.».
6. En la subsección no aparece ningún monto, ninguna hora, ningún correo, ni las palabras «retracto», «rechazado» o «rechazo».
7. Una devolución en dinero por arrepentimiento dice «Se devolvieron {monto} porque se pidió devolver {producto}.» y **nunca** «porque se canceló el pedido».
8. A 320 px con el texto al 200 %, ni la subsección ni «Lo que pasó con tu pedido» se salen de la tarjeta: sin desplazamiento horizontal, la `Etiqueta` parte su texto y los nombres largos parten con `break-words`. (Incluye H4.)
9. En el carrito de quien paga, con el total confirmado, cada línea con «Buscarlo en otro comercio» dice «Si falta antes de pagar: lo buscamos en otro comercio.»; a 360 px en dos renglones, sin desbordar la tarjeta.
10. Lo mismo en el resumen antes de pagar y en el carrito de «Se informa».
11. A 320 px con el texto al 200 %, en las tres pantallas, la frase parte entre palabras, ninguna palabra se corta y no hay desplazamiento horizontal.
12. Las líneas con «Sacarlo del pedido…» siguen diciendo «Si falta: lo sacamos y te devolvemos su precio.» (o «Si falta: lo sacamos del pedido.» en «Se informa»).

## 5. Cómo la voy a revisar

Con la pantalla funcionando y datos sintéticos (María, Carmen, Rodrigo): un pedido entregado de María con tres pedidos de devolución, uno por estado, uno de ellos no aceptado por `sello_abierto` y otro sin motivo, y con su devolución en dinero en curso y hecha. Capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %, de «Datos de María» (bloque «Sus pedidos»), del carrito de Rodrigo con el total confirmado, del resumen y del carrito de «Se informa». Se comparan contra la sección 4. Ninguna pantalla se aprueba sin verla.

## 6. Para el orquestador

| # | Severidad | Qué | Propuesta |
|---|---|---|---|
| 1 | **P1** (dinero, texto falso) | H3: hoy una devolución por arrepentimiento se lee «porque se canceló el pedido» | Entra en esta tarjeta (1.6). Pide al QA una prueba del texto con `motivo: retracto` |
| 2 | P2 (decide la persona) | H2: `RetractoCopia` no trae quién lo pidió, y el resto de «Datos de» sí lo dice. La copia de la persona cuidada es la que ven admin y cuidador | Agregar `pedido_por: PersonaNombrada \| null` a `RetractoCopia` (backend y contrato; pasa por el analista, porque suma un dato personal a la copia). Si no se agrega, la pantalla queda con «Se pidió el {fecha}.» y el historial dice quién (1.5). No elijo yo |
| 3 | P3 | R1 a R7 y el texto nuevo de «Si falta» van a `lenguaje.md` 31 y 35 para que Jorge los apruebe | — |
| 4 | P3 | H4: `LoQuePaso` usa `items-start` en sus `li`, contra MATU-54 3.4 | Lo verifico en la revisión (criterio 8). Si desborda a 320 px, es un hallazgo para el frontend |
