# Especificación de pantallas · ADR-027 (precios exactos y un solo cobro)

**Del diseñador, 26/10/2026.** Fuentes: `MATU/docs/arquitectura.md` sección 14 (ADR-027, aprobado el 26/10) y `MATU/docs/legal/revision-previa-adr-027.md` ("Qué debe ver la familia antes de pagar"). Reemplaza lo que `DISENO.md` dice de la lista de reposición, el pedido, el pago, la consola del comercio y "Pedido entregado". Todo lo demás de `DISENO.md` sigue vigente: tokens, tipografía, distintivo "Piloto académico con datos de prueba", `PreciosDeEjemplo`, "(comercio ficticio)" y los estados de la sección 6.

Lo marcado **[DECIDE JORGE]** o **[CONSULTA LEGAL]** no lo decidí yo: la pantalla muestra un texto provisional, rotulado, hasta que se resuelva (lista completa en la sección 4).

---

## 1. Qué cambia en la guía del presentador

**Decisiones de estructura:**

- **Se fusiona "Crédito o débito" (escena 22) con "Tu pedido".** Con el ADR-027 crédito y débito funcionan igual, así que preguntarlo antes de pagar es una pantalla sin decisión. "Tu pedido" dice "Pagas con crédito o débito en Transbank" y el botón es uno solo, "Pagar $57.460". La tarjeta se elige en la pasarela, como en Webpay.
- **Se quita "Comercio: monto real"** (escena 27): el paso no existe.
- **Se agregan tres escenas:** la falla al retirar con reenvío simulado (camino principal), "El total venció" y "Un producto no llegó" (casos borde).
- **Se fusionan "Exportar" y "Compartir"** en una sola escena, porque son las dos salidas gratuitas de la lista.
- La guía pasa de 35 a **36 escenas**. Las escenas 1 a 18 no cambian.

| # | Escena | Rol | Real o simulado | Nota para el presentador |
|---|---|---|---|---|
| 19 | Lista de reposición | Familia | Simulado | Precios exactos de un comercio, envío desde la lista y tres salidas. Exportar y compartir son gratis |
| 20 | Exportar o compartir la lista | Familia | Simulado | Copiar, descargar, enviar a Rodrigo (del grupo) o compartir desde el teléfono. Sin pedir en MATU |
| 21 | Tu pedido, antes de pagar | Familia | Simulado | Stock confirmado: las toallitas salieron y el suplemento bajó de precio. Todo lo que exige la ley, antes de pagar |
| 22 | Pasarela simulada | Familia | Simulado | Crédito o débito de prueba, el mismo monto. "Pago de prueba. No se cobra dinero real." |
| 23 | Seguimiento | Familia | Simulado | Pagado una sola vez, con su comprobante |
| 24 | Comercio: pedidos del día | Comercio | Simulado | Lo apartado sin pagar se ve solo como referencia opaca. El pedido pagado no lleva nombres ni dirección |
| 25 | Comercio: preparar | Comercio | Simulado | El suplemento "ya no está": MATU lo busca en otro local |
| 26 | Comercio: código de retiro | Comercio | Simulado | Sin paso de monto real |
| 27 | Cambio de local | Familia | Simulado | Mismo producto en otro local, la familia paga lo mismo y MATU pone la diferencia. Reenvío simulado (fase 2) |
| 28 | Entregado | Familia | Simulado | Cobrado = total que viste: $57.460 |
| 29 | Todavía no hay nada | Familia | Simulado | Sin cambios (antes 30) |
| 30 | Dos versiones | Familia | Simulado | Sin cambios (antes 31) |
| 31 | El total venció | Familia | Simulado | Pasaron 15 minutos (plazo de ejemplo): se confirma de nuevo, sin costo |
| 32 | El pago no pasó | Familia | Simulado | No se cobró nada; el pedido sigue apartado hasta que vence |
| 33 | Un producto no llegó | Familia | Simulado | Nadie lo tenía: se devuelve su precio a la misma tarjeta. Plazo por definir |
| 34 | Relevo: PIN incorrecto | Relevo | Simulado | Sin cambios (antes 33) |
| 35 | Relevo: enlace no disponible | Relevo | Simulado | Sin cambios (antes 34) |
| 36 | Texto al 200% | Familia | Simulado | Sin cambios (antes 35) |

**Datos sintéticos del recorrido** (todos los precios son de ejemplo, con IVA incluido):

| Producto | En la lista (Farmacia Los Aromos) | Al confirmar el stock | Después de pagar |
|---|---|---|---|
| Pañal adulto talla M x30 × 2 | $13.990 c/u, $27.980 | Igual | Se entrega |
| Toallitas húmedas x80 × 1 | $4.990 | **Sale del pedido**: ningún comercio en convenio la tiene hoy | — |
| Suplemento vainilla x12 × 1 | $27.030 | **Cambia el precio**: $26.490 | Ya no está en Los Aromos; se retira el mismo producto en **Farmacia Piedra Azul (comercio ficticio)** a $27.590. MATU pone $1.100 |
| Envío único | $2.990 | $2.990 | — |
| **Total** | **$62.990** si todo está disponible | **$57.460** | Cobrado: **$57.460** |

Cuentas: 27.980 + 26.490 = 54.470; 54.470 + 2.990 = 57.460. En la variante de la escena 33 se devuelven $26.490 y queda cobrado $30.970.

---

## 2. Reglas comunes a estas pantallas

- **Se prohíben estas palabras en la interfaz:** "reserva", "reservar", "monto real", "tope", "estimado", "aprox.", "se liberará", "captura". Un `grep` sobre `src/familia`, `src/comercio` y `src/demo` no debe encontrarlas en textos al usuario.
- **Un mismo total en todas partes:** el botón "Pagar", la boleta de "Tu pedido", la pasarela, el comprobante y "Entregado" muestran **$57.460**.
- **`PreciosDeEjemplo`** una vez por pantalla con precios: en la lista, en "Tu pedido" (bajo la boleta), en el seguimiento, en "Entregado" y en la consola del comercio (bajo el detalle del pedido, porque muestra "Tus productos"). El envío también es de ejemplo y queda cubierto por el mismo rótulo.
- **"(comercio ficticio)"** la primera vez que aparece cada comercio en cada pantalla.
- **La boleta** (el componente actual, con el borde cortado) solo tiene renglones de dinero exacto: productos, envío, total. Nada "por saber" ni "por elegir".
- Dinero en pesos enteros con `cifras` solo sobre la cifra suelta. Fechas `DD/MM/AAAA`, horas de 24 h.
- Un solo botón `pino` macizo por pantalla.

---

## 3. Especificación por pantalla

### Escena 19 · Lista de reposición

**Objetivo:** Carmen ve cuánto comprar, cuánto cuesta en un comercio y elige cómo seguir: llevarse la lista, pasarla a alguien o pedirla.

**Jerarquía:**
1. El total con envío y el botón para pedir.
2. Las líneas, con precio exacto y comercio.
3. Las dos salidas gratuitas y el rótulo de precios de ejemplo.

**Esquema, pantalla ancha** (dos columnas desde 48 rem):

```
Insumos
Cuánto comprar para que María quede cubierta unas 3 semanas.
[Qué se acaba | Lista de reposición]
┌ Precios de Farmacia Los Aromos (comercio ficticio) ─┐  ┌ Si pides en MATU ─────────────────┐
│ Pañal adulto talla M x30           [−] 2 [+] $27.980│  │ Productos ............... $60.000 │
│ $13.990 el paquete. Sugerimos 2.                    │  │ Envío, uno por pedido ..... $2.990│
│ Toallitas húmedas x80              [−] 1 [+]  $4.990│  │ ───────────────────────────────── │
│ Suplemento vainilla x12            [−] 1 [+] $27.030│  │ Total con IVA ........... $62.990 │
└─────────────────────────────────────────────────────┘  │ Antes de que pagues confirmamos   │
La lista sirve aunque compres en otra parte.             │ que haya stock.                   │
(i) Precios de ejemplo. …                                │ [Pedir a domicilio por $62.990]   │
                                                         │ [Exportar o compartir]            │
                                                         │ Exportarla o compartirla es gratis│
                                                         └───────────────────────────────────┘
```

**Esquema a 360 px:** título, pestañas, la lista (cada línea en dos renglones: nombre y precio; stepper y subtotal), el recuadro del total con los dos botones apilados, la frase "La lista sirve…" y el rótulo.

**Componentes y tokens:**
- La lista actual: `bg-hoja`, `ring-linea`, `divide-linea`.
- El encabezado de la lista, "Precios de…", va en `font-bold`.
- Subtotal con `cifras ml-auto`: corrige el P2 de la vuelta 5.
- Recuadro del total con `Renglon` (el total `fuerte`).
- Botones: `Boton` `primario` ("Pedir…") y `secundario` ("Exportar o compartir").
- `PreciosDeEjemplo`.

**Estados:**
- **Vacío:** si no hay productos sugeridos, la escena 29 ("Todavía no hay nada"), sin cambios.
- **Cantidad en cero:** la línea queda con $0 y sigue en la lista. Si todas quedan en cero, "Pedir a domicilio" se deshabilita con la frase "Elige al menos un producto para pedir".

**Textos exactos:**
- Encabezado de la lista: "Precios de Farmacia Los Aromos (comercio ficticio)".
- Título del recuadro: "Si pides en MATU".
- Renglones: "Productos", "Envío, uno por pedido", "Total con IVA".
- Nota bajo el total: "Antes de que pagues confirmamos que haya stock."
- Botones: "Pedir a domicilio por $62.990" y "Exportar o compartir".
- Al pie del recuadro: "Exportarla o compartirla es gratis y no necesitas pedir en MATU."

**Criterios verificables:**
- El total del botón es igual al renglón "Total con IVA".
- El envío aparece en esta pantalla, antes de pedir.
- "aprox." no aparece.
- A 1280, los subtotales quedan alineados al borde derecho de la lista.

---

### Escena 20 · Exportar o compartir la lista

**Objetivo:** Carmen se lleva la lista para comprar donde quiera, o se la pasa a alguien, sin pedir en MATU.

**Jerarquía:**
1. La lista tal como sale.
2. Copiar.
3. Las otras formas de sacarla.

**Esquema, pantalla ancha:** la lista de la escena 19 a la izquierda. A la derecha, el recuadro se reemplaza por este panel:

```
┌ Exportar o compartir ────────────────────────────┐
│ ┌ Lista de María, 30/10/2026 ──────────────────┐ │
│ │ - Pañal adulto talla M x30: 2 paquetes       │ │
│ │   ($13.990 c/u en Farmacia Los Aromos)       │ │
│ │ - Toallitas húmedas x80: 1 paquete (…)       │ │
│ │ - Suplemento vainilla x12: 1 paquete (…)     │ │
│ │ Precios de ejemplo.                          │ │
│ └──────────────────────────────────────────────┘ │
│ [Copiar la lista] [Descargar]                    │
│ Pasársela a alguien                              │
│ [Enviar a Rodrigo]  [Compartir desde tu teléfono]│
│ Volver a la lista                                │
└──────────────────────────────────────────────────┘
```

**Esquema a 360 px:** el panel va después de la lista, con los botones apilados.

**Componentes y tokens:**
- La vista previa en `<pre>` con fondo `papel` (ya hereda la cara del texto).
- `Boton` `primario` "Copiar la lista"; los demás `secundario`; "Volver a la lista" `texto`.
- El subtítulo "Pasársela a alguien" con `Subtitulo`.

**Estados:**
- **Éxito:** aviso breve con el verbo del botón (ver textos).
- **Error al copiar:** "Este navegador no deja copiar. Usa Descargar." (el aviso actual).
- **Sin otros miembros en el grupo:** no aparece "Enviar a…". Queda solo "Compartir desde tu teléfono".

**Textos exactos:**
- Botones: "Copiar la lista", "Descargar", "Enviar a Rodrigo", "Compartir desde tu teléfono", "Volver a la lista".
- Avisos: "Lista copiada. Pégala donde quieras." · "Lista descargada." · "Lista enviada a Rodrigo. La verá en su MATU." · "Lista compartida."
- Ayuda bajo "Enviar a Rodrigo": "Solo puedes enviarla a alguien de tu grupo familiar. A otras personas, compártela desde tu teléfono."

**Criterios verificables:**
- "Enviar a…" solo ofrece miembros del grupo (legal 5g): en la demo, Rodrigo.
- La vista previa incluye "Precios de ejemplo."
- Hay un solo botón `pino` macizo.

---

### Escena 21 · Tu pedido, antes de pagar

**Objetivo:** antes de pagar, Carmen sabe exactamente qué llega, cuánto paga una sola vez, quién lo prepara, cuándo llega y qué pasa si algo falla, y puede no pedir sin costo.

**Jerarquía:**
1. La frase de resumen y lo que cambió desde la lista.
2. Los productos con su total, y el botón "Pagar $57.460".
3. Las condiciones: entrega, si falta algo, vigencia, quién emite la boleta y la salida sin costo.

**Estado previo, "Confirmando el stock":**
- Al tocar "Pedir a domicilio…" la página muestra el título "Tu pedido" y una sola línea con `aria-busy="true"`: "Confirmando el stock con los comercios…".
- En la demo dura menos de un segundo. No hay esqueletos ni animación de carga más allá de esa frase.
- Si la confirmación falla: "No pudimos confirmar el stock. No se cobró nada." con el botón "Intentar de nuevo".

**Esquema, pantalla ancha:**

```
‹ Volver a la lista de reposición
Tu pedido
Confirmamos el stock. El total quedó en $57.460.

┌ (rocio) Lo que cambió desde tu lista ──────────┐   ┌ Pedido #4821 ─────────────────────┐
│ · Toallitas húmedas x80: nadie la tiene hoy.   │   │ Productos ............... $54.470 │
│   Salió del pedido y sigue en tu lista.        │   │ Envío, uno por pedido ..... $2.990│
│ · Suplemento vainilla x12: bajó de $27.030 a   │   │ ───────────────────────────────── │
│   $26.490.                                     │   │ Total con IVA ........... $57.460 │
│ El total bajó de $62.990 a $57.460.            │   │ Se cobra una sola vez.            │
└────────────────────────────────────────────────┘   │ Este total vale hasta las 14:38.  │
Productos                                            │ (15 minutos, plazo de ejemplo)    │
┌────────────────────────────────────────────────┐   └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘
│ Pañal adulto talla M x30   2 × $13.990  $27.980│   (i) Precios de ejemplo. …
│ Farmacia Los Aromos (comercio ficticio)        │
│ Suplemento vainilla x12    1 × $26.490  $26.490│
│ Farmacia Los Aromos  [Cambió el precio]        │
│ Envío, uno por pedido                    $2.990│
│ Total con IVA                           $57.460│
└────────────────────────────────────────────────┘
No está disponible hoy
  Toallitas húmedas x80 · 1 × $4.990 · [Salió del pedido]

Entrega          Llega hoy entre 17:00 y 18:00 a Los Aromos 123, La Reina.
Boleta           Quién vende y emite la boleta: por definir.
Si falta algo    (Nota) …
[ ] Leí y acepto las condiciones del pedido.   Ver las condiciones
Pagas con crédito o débito en Transbank. Se cobra una sola vez este total.
No hay reserva ni cobros después.
[Pagar $57.460]   No pedir por ahora
```

**Esquema a 360 px**, en una columna y en este orden:
1. Volver y título.
2. El resumen.
3. "Lo que cambió".
4. Productos.
5. "No está disponible hoy".
6. La boleta.
7. `PreciosDeEjemplo`.
8. Entrega, boleta y "Si falta algo".
9. La casilla.
10. La frase de pago.
11. "Pagar $57.460".
12. "No pedir por ahora".

Los botones al ancho de su texto.

**Componentes y tokens:**
- `Pagina` con `volver`.
- "Lo que cambió": `Nota` `tono="rocio"` con el ícono `RefreshCw` en `pino`. Va solo si hubo cambios.
- Tabla de productos: la lista actual (`bg-hoja`, `ring-linea`, `divide-linea`). La cantidad por precio unitario va en `tenue` y el subtotal en `cifras ml-auto`. El comercio va en `text-sm text-tenue` bajo el nombre.
- Marcas de cambio:
  - `Etiqueta tono="atenta"` con el ícono `ArrowDownUp` y la palabra "Cambió el precio";
  - `Etiqueta tono="atenta"` con el ícono `Store` y la palabra "Otro comercio", para cuando la confirmación mueve un producto de local (en la demo no ocurre en esta escena, pero el componente lo soporta).
- "No está disponible hoy": un `Subtitulo` y una lista en `tenue`, sin subtotal sumado, con `Etiqueta tono="neutro"` "Salió del pedido".
- Boleta: el componente actual, con renglones exactos. "Total con IVA" va `fuerte`.
- Entrega, boleta y "Si falta algo": una lista de definiciones (`dl`) en dos columnas desde `@md` (término en negrita, definición en `text-base`). "Si falta algo" usa `Nota tono="rocio"` dentro de la definición.
- Casilla: la de "Leí el aviso y lo acepto" del alta (borde `borde`, foco base).
- "Ver las condiciones": `Boton variante="texto"`. Abre un panel en la misma página (un `details` o una sección que se expande, sin ventana modal) con el texto de las condiciones.
- `Boton` `primario` "Pagar $57.460" con el ícono `Lock`. `Boton variante="texto"` "No pedir por ahora".
- `PreciosDeEjemplo` bajo la boleta.

**Estados:**
- **Confirmando:** ver arriba.
- **Sin cambios desde la lista:** no aparece "Lo que cambió". El resumen dice "Confirmamos el stock: está todo."
- **Nada disponible:** "Ningún comercio en convenio tiene estos productos hoy. No se cobró nada y tu lista sigue igual." con el botón primario "Volver a la lista". No hay botón de pago.
- **Casilla sin marcar:** "Pagar" se deshabilita (opacidad 50 %) y al lado dice "Acepta las condiciones del pedido para pagar."
- **Total vencido:** escena 31.
- **Pago rechazado:** escena 32.

**Textos exactos:**
- Título: "Tu pedido".
- Resumen: "Confirmamos el stock. El total quedó en $57.460."
- "Lo que cambió desde tu lista":
  - "Toallitas húmedas x80: nadie la tiene hoy. Salió del pedido y sigue en tu lista."
  - "Suplemento vainilla x12: bajó de $27.030 a $26.490."
  - "El total bajó de $62.990 a $57.460."
- Bloques de la tabla: "Productos" · "No está disponible hoy" · "Salió del pedido".
- Entrega: "Llega hoy entre 17:00 y 18:00 a Los Aromos 123, La Reina."
- Boleta: "Prepara tu pedido Farmacia Los Aromos (comercio ficticio). Quién vende y quién emite la boleta: por definir." **[CONSULTA LEGAL]**
- Si falta algo: "Si al retirar falta un producto, lo buscamos en otro comercio en convenio. Es el mismo producto, no otra marca, y pagas lo mismo: la diferencia la pone MATU. Si nadie lo tiene, te devolvemos su precio a la misma tarjeta, y también el envío si no llega nada. Plazo de la devolución: por definir." **[CONSULTA LEGAL: plazo]**
- Vigencia en la boleta: "Este total vale hasta las 14:38." y debajo, en `tenue`: "15 minutos, plazo de ejemplo." **[DECIDE JORGE: N minutos]**
- Casilla: "Leí y acepto las condiciones del pedido." · Enlace: "Ver las condiciones".
- Frase de pago: "Pagas con crédito o débito en Transbank. Se cobra una sola vez este total. No hay reserva ni cobros después."
- Botones: "Pagar $57.460" · "No pedir por ahora".
- Al tocar "No pedir por ahora": vuelve a la lista con el aviso "No pediste. No se cobró nada y tu lista sigue igual."
- Condiciones (panel, borrador del diseñador para que lo redacte el analista): "Pagas una sola vez el total que ves, con IVA incluido. El precio queda fijo al pagar. Si un producto falta al retirar, lo traemos de otro comercio en convenio sin costo para ti, o te devolvemos su precio a la misma tarjeta. No cambiamos un producto por otra marca. Recibes un comprobante del pago." **[DECIDE JORGE con el analista: texto final y retracto]**

**Criterios verificables:**
1. Se ven los diez puntos de la revisión legal (1b): productos con cantidad, precio y subtotal; los que salieron; los que cambiaron; envío aparte; total con IVA; "Se cobra una sola vez…"; la devolución con medio y plazo; quién vende y quién emite la boleta; la entrega; las condiciones con su casilla; y la salida sin costo.
2. Ningún cambio se comunica solo con color: cada uno tiene palabra e ícono.
3. "Pagar $57.460" es el único elemento `pino` macizo. Su monto es igual al "Total con IVA" de la boleta.
4. Ninguna palabra prohibida de la sección 2.
5. El producto que salió no suma al total.
6. Con "Texto al 200%" todo queda en una columna, sin desplazamiento horizontal, y la casilla y el botón siguen tocables (48 px).

---

### Escena 22 · Pasarela simulada

**Objetivo:** Carmen paga en Transbank, con crédito o débito, el mismo total que vio.

**Jerarquía:**
1. Que es un pago de prueba.
2. El monto.
3. Elegir la tarjeta y pagar.

**Esquema** (una columna centrada de 36 rem en todos los anchos, como hoy):

```
┌ (pasarela-tinta) Pasarela de pago simulada ───────┐
│ Transbank, ambiente de prueba.                    │
└───────────────────────────────────────────────────┘
│ (i) Pago de prueba. No se cobra dinero real.      │
┌ Comercio  MATU · Orden 4821 · Monto a pagar $57.460┐
Elige una tarjeta de prueba
( ) Tarjeta de crédito de prueba, terminada en 6623
( ) Tarjeta de débito de prueba, terminada en 4051
[Pagar]  [Simular que el banco lo rechaza]
Volver a MATU sin pagar
Los datos de la tarjeta solo existen en Transbank. MATU recibe el resultado, nunca la tarjeta.
```

**Componentes y tokens:**
- Solo tokens `pasarela-*`.
- Las tarjetas son opciones de radio con la misma anatomía que `GrupoOpciones`, pero en grises: borde `pasarela-tenue`, la elegida con anillo `pasarela-tinta`.
- "Pagar" en `pasarela-tinta` macizo. El botón de rechazo con `pasarela-rechazo` y `pasarela-rechazo-fondo` al presionar.

**Estados:**
- **Sin tarjeta elegida:** "Pagar" deshabilitado, con "Elige una tarjeta de prueba". En la demo, la de crédito viene elegida.
- **Procesando:** "Pagando…" con `aria-busy`, menos de un segundo.
- **Rechazo:** escena 32.

**Textos exactos:**
- "Pasarela de pago simulada" · "Transbank, ambiente de prueba." · "Pago de prueba. No se cobra dinero real."
- "Comercio", "Orden", "Monto a pagar".
- "Elige una tarjeta de prueba" · "Tarjeta de crédito de prueba" · "Tarjeta de débito de prueba" · "terminada en 6623" · "terminada en 4051".
- Botones: "Pagar" · "Simular que el banco lo rechaza" · "Volver a MATU sin pagar".

**Criterios verificables:**
- El monto es el mismo con crédito y con débito ($57.460).
- No aparecen "reservar" ni "Monto a reservar".
- Cero tokens de la marca en esta pantalla.

---

### Escena 23 · Seguimiento

**Objetivo:** Carmen confirma que pagó una sola vez, guarda el comprobante y ve en qué va el pedido.

**Jerarquía:**
1. "Pagado $57.460" y el comprobante.
2. Los pasos.
3. El código de retiro.

**Esquema, pantalla ancha:**

```
Pedido de María
Lo prepara Farmacia Los Aromos (comercio ficticio). Llega hoy entre 17:00 y 18:00.
(✓) Pagado                                         ┌ Pedido #4821 ───────────────┐
    $57.460 una sola vez, a las 14:24              │ Pañal adulto … × 2   $27.980│
    [Descargar el comprobante]                     │ Suplemento … × 1     $26.490│
(2) La farmacia lo prepara      Pendiente          │ Envío                 $2.990│
(3) Listo para retiro           Pendiente          │ ─────────────────────────── │
(4) En camino                   Pendiente          │ Pagado               $57.460│
(5) Entregado                   Pendiente          └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘
Código de retiro. Lo muestra quien retira.   4729  (i) Precios de ejemplo. …
```

**Esquema a 360 px:** título, pasos, código, boleta y rótulo, en ese orden.

**Componentes y tokens:**
- Los pasos actuales (círculo `pino` con check si está hecho, anillo `tinta/15` si está pendiente).
- "Descargar el comprobante" como `Boton` `secundario` con el ícono `Download`. No hay botón principal en esta pantalla.
- La boleta con renglones exactos, el último "Pagado" `fuerte`.

**Textos exactos:**
- "Pagado" · "$57.460 una sola vez, a las 14:24" · "Descargar el comprobante".
- Aviso al descargar: "Comprobante descargado." (simulado: en la demo no se descarga nada).
- El aviso al volver de la pasarela, en reemplazo del actual: "Pago aprobado por $57.460. Avisamos a la farmacia."

**Criterios verificables:**
- Ningún paso ni renglón dice "Monto reservado", "Reservado" ni "por saber".
- La boleta suma exactamente $57.460.

---

### Escenas 24 a 26 · Comercio

**Objetivo:** quien atiende el mostrador ve qué apartar, qué preparar y a quién entregar, solo con productos y cantidades, sin datos de la familia.

**Cambios generales en la consola:**
- Los pasos pasan a **1 Apartado · 2 Preparar · 3 Retiro**. El paso "Monto real" desaparece.
- "Tope autorizado" se reemplaza por **"Tus productos $54.470"**: lo que este comercio vende en el pedido.
- **Se quita "Para María".** El pedido se identifica solo por su número. **[DECIDE JORGE]**: la revisión legal (5c) marca el nombre de pila como no declarado. Propongo quitarlo y no lo doy por decidido.
- La barra dice "Farmacia Los Aromos (comercio ficticio)", como ya está.

**Escena 24 · Pedidos del día.** Esquema, pantalla ancha:

```
Pedidos de hoy                       ┌ Pedido #4821 ─────────────────── Tus productos $54.470 ┐
┌ #4821 ● Por preparar ───────┐      │ Retiro hoy entre 17:00 y 18:00                         │
│ 2 productos · Retiro 17–18  │      │ (✓) Apartado ─ (2) Preparar ─ (3) Retiro               │
└─────────────────────────────┘      │ Apartado a las 14:23 y pagado a las 14:24.             │
┌ Ref. K41M ◐ Apartado ───────┐      │ Pañal adulto talla M x30 × 2                           │
│ 2 productos · sin pagar     │      │ Suplemento vainilla x12 × 1                            │
│ Se libera a las 14:51       │      │ Ves solo productos y cantidades. No ves nombres ni     │
└─────────────────────────────┘      │ direcciones.                                           │
┌ #4819 ○ Retirado ───────────┐      │ [Empezar a preparar]                                   │
└─────────────────────────────┘      └────────────────────────────────────────────────────────┘
```

La fila "Ref. K41M" muestra lo que el comercio ve **antes** del pago: una referencia opaca, productos y cantidades. No es un pedido ni tiene acciones. Al elegirla, el detalle dice: "Apartado para una familia que todavía no paga. Si no paga antes de las 14:51, se libera solo."

**Escena 25 · Preparar.** Cada línea tiene dos acciones: "Listo" y "Ya no está".
- En la demo, el suplemento se marca "Ya no está". La línea queda con `Etiqueta tono="neutro"` "Ya no está" y debajo: "Lo buscamos en otro local. La familia no paga más."
- "Marcar listo para retiro" se habilita cuando todas las líneas están en "Listo" o en "Ya no está". Si no, al lado dice: "Marca cada producto para seguir."
- Desaparecen "Reemplazar por otra marca" y "Marcar como no disponible".

**Escena 26 · Código de retiro.** Igual que hoy, sin el paso de monto real. "Tus productos" baja a **$27.980**, porque el suplemento ya no sale de este local.

**Estados:**
- **Cola vacía:** "No hay pedidos hoy."
- **Código incorrecto:** "Ese código no es. Revisa los cuatro números." en `pronto`.
- **Apartado vencido:** la fila desaparece de la cola.

**Textos exactos:**
- Pasos: "Apartado", "Preparar", "Retiro".
- "Tus productos" · "Apartado a las 14:23 y pagado a las 14:24." · "Ves solo productos y cantidades. No ves nombres ni direcciones."
- Estados de la cola: "Por preparar", "Apartado", "Preparando", "Listo para retiro", "Retirado".
- Botones: "Empezar a preparar" · "Listo" · "Ya no está" · "Marcar listo para retiro" · "Validar código".
- Aviso al marcar "Ya no está": "Avisamos a MATU. Lo buscamos en otro local."
- Aviso al marcar listo: "Listo para retiro. Avisamos a la familia."

**Criterios verificables:**
- Ninguna pantalla del comercio muestra "María", "Carmen" ni la dirección.
- Desaparecen "Monto real", "Tope autorizado" y "N° de boleta".
- La fila apartada sin pagar no tiene número de pedido ni acciones.

---

### Escena 27 · Cambio de local

**Objetivo:** Carmen se entera, en el momento, de que un producto se retiró en otro local, y de que no paga más.

**Jerarquía:**
1. El aviso del cambio, con "pagas lo mismo".
2. Los pasos, que siguen.
3. La boleta, sin cambios en el total.

**Esquema:** el seguimiento de la escena 23, con la `Nota` del cambio entre el título y los pasos:

```
┌ (rocio) ⟳ Cambiamos de local un producto ─────────────────────────────┐
│ Suplemento vainilla x12 ya no estaba en Farmacia Los Aromos. Lo       │
│ retiramos en Farmacia Piedra Azul (comercio ficticio): es el mismo    │
│ producto. Pagas lo mismo; la diferencia de $1.100 la pone MATU.       │
│ En esta demo, el cambio de local es simulado.                         │
└───────────────────────────────────────────────────────────────────────┘
```

**Componentes y tokens:**
- `Nota tono="rocio"` con el ícono `RefreshCw` en `pino`. Es una buena noticia, no un error: nunca `pronto`.
- La última línea, "En esta demo…", va en `text-sm text-tenue`.
- En la boleta, el suplemento muestra "Farmacia Piedra Azul" bajo su nombre, y su precio y el total siguen iguales ($26.490 y $57.460).

**Textos exactos:** los del esquema. Título de la nota: "Cambiamos de local un producto".

**Criterios verificables:**
- El total pagado no cambia.
- La nota dice "el mismo producto" y "Pagas lo mismo".
- La palabra "simulado" está a la vista (fase 2 del ADR-027).

---

### Escena 28 · Entregado

**Objetivo:** Carmen ve que le cobraron exactamente lo que vio antes de pagar.

**Jerarquía:**
1. "Entregado a las 15:07" y "Se cobró $57.460, el total que viste antes de pagar".
2. Lo que se sumó a los insumos.
3. La boleta final.

**Esquema, pantalla ancha:** como la escena actual, con estos cambios:
- Se quitan la línea "Se cobraron… se liberaron" y los renglones "Estimado", "Reservado en tu tarjeta" y "Liberado".
- Se mantiene la nota "Ya sumamos lo que llegó".
- Se agrega una línea `text-base text-tenue` bajo el resumen: "El suplemento llegó desde Farmacia Piedra Azul (comercio ficticio). No pagaste más."
- La boleta queda así: productos con su comercio, "Envío", y "Cobrado $57.460" `fuerte` con la nota "Es el total que viste antes de pagar."
- `PreciosDeEjemplo` bajo la boleta.

**Textos exactos:**
- Título: "Pedido entregado".
- Línea grande: "Llegó a las 15:07" (resuelve el P3 de los dos títulos).
- Resumen: "Se cobró $57.460 una sola vez. Es el total que viste antes de pagar."
- Botones: "Ver los insumos" (`secundario`) · "Volver al inicio" (`texto`).

**Criterios verificables:**
- El monto "Cobrado" es igual al del botón "Pagar" de la escena 21.
- Ninguna palabra prohibida de la sección 2.

---

### Escena 31 · El total venció

**Objetivo:** Carmen entiende que no pagó a tiempo, que no perdió nada y que puede confirmar de nuevo.

**Esquema:** la escena 21 sin la casilla ni el botón de pago. En su lugar, arriba de los productos:

```
┌ (atenta) ⏱ Este total ya no vale ───────────────────────────────────┐
│ Pasaron 15 minutos y el stock o los precios pueden haber cambiado.  │
│ No se cobró nada.                                                   │
│ [Confirmar de nuevo]   No pedir por ahora                           │
└─────────────────────────────────────────────────────────────────────┘
```

Los productos y la boleta quedan visibles en `tenue`, con el título "Lo que habías visto".

**Componentes y tokens:** `Nota tono="atenta"` con el ícono `Clock`. Es un aviso, no un error. `Boton` `primario` "Confirmar de nuevo"; `texto` "No pedir por ahora".

**Textos exactos:**
- "Este total ya no vale" · "Pasaron 15 minutos y el stock o los precios pueden haber cambiado. No se cobró nada." · "Confirmar de nuevo" · "No pedir por ahora".
- Después de confirmar de nuevo, la escena 21 con el resumen: "Confirmamos de nuevo el stock. El total quedó en $57.460."

**Criterios verificables:**
- Mientras el total está vencido, no existe ningún botón de pago.
- Al confirmar de nuevo, la vigencia muestra una hora nueva.

---

### Escena 32 · El pago no pasó

**Objetivo:** Carmen sabe que no se le cobró nada y qué puede hacer.

**Esquema:** como la escena actual, con la boleta exacta de la escena 21 a la derecha (sin "Se reservará" ni "por saber").

**Textos exactos:**
- Título: "El pago no pasó".
- Aviso (`pronto`, como hoy): "El banco no aprobó el pago" · "Puede ser el cupo o un bloqueo del banco. No se cobró nada."
- Párrafo: "Tu pedido sigue apartado hasta las 14:38. Si no lo pagas, se libera solo y nadie pierde dinero."
- Botones: "Probar de nuevo" (`primario`) · "No pedir por ahora" (`texto`).

**Criterios verificables:**
- La palabra "reservó" no aparece (hoy dice "No se te cobró ni se reservó nada").
- Si la vigencia ya pasó, "Probar de nuevo" lleva a la escena 31.

---

### Escena 33 · Un producto no llegó

**Objetivo:** Carmen sabe, en el momento, que un producto no llegará, cuánto se le devuelve, por qué medio y cuándo.

**Esquema:** "Pedido entregado" de la escena 28, con estos cambios:
- Aparece una `Nota tono="atenta"` con el ícono `Undo2` antes de "Ya sumamos lo que llegó".
- La boleta muestra:
  - el suplemento con `Etiqueta tono="neutro"` "No llegó";
  - "Cobrado $57.460";
  - "Te devolveremos $26.490", en `ok`, con la nota de medio y plazo;
  - "Pagas en total $30.970" `fuerte`.

```
┌ (atenta) ↶ Un producto no llegó ──────────────────────────────────────┐
│ Ningún comercio en convenio tenía Suplemento vainilla x12. Te         │
│ devolveremos $26.490 a la misma tarjeta, por anulación en Transbank.  │
│ Plazo: por definir. El envío no se devuelve porque los pañales sí     │
│ llegaron.                                                             │
└───────────────────────────────────────────────────────────────────────┘
```

**Variante sin nada entregado:** "Ningún producto llegó. Te devolveremos $57.460, con el envío, a la misma tarjeta."

**Textos exactos:**
- Título de la nota: "Un producto no llegó".
- La nota, tal como está en el esquema. **[CONSULTA LEGAL: plazo]**
- Renglones: "Cobrado", "Te devolveremos", "Pagas en total".

**Criterios verificables:**
- Es la única pantalla de la demo donde aparece una devolución.
- La devolución está en futuro ("Te devolveremos"), con su medio ("a la misma tarjeta, por anulación en Transbank") y su plazo.
- 57.460 − 26.490 = 30.970.

---

## 3 bis. Reglas que quedaron de la construcción (revisión visual del 26/10)

Las decisiones de Jorge que se aplicaron sobre esta especificación (vigencia de 15 minutos sin rótulo, sin la casilla de equivalentes, sin nombre en la consola, textos de `src/demo/textos-pedido.ts`) mandan sobre lo escrito arriba.

- **La frase de pago** de la escena 21 es: "Pagas con crédito o débito en Transbank. Se cobra una sola vez este total, sin cobros después." La palabra "reserva" no se usa, ni siquiera negada.
- **Dirección que falta.** Si el alta no tuvo dirección, "Entrega" la pide en ese mismo lugar con un `CampoTexto` obligatorio ("¿A dónde lo llevamos?"). El error dice "Escribe la dirección para que el pedido llegue." y "Pagar" no avanza sin ella. Coincide con Grupo familiar: "Sin dirección. Se pide con el primer pedido."
- **Lo apartado sin pagar en la consola** ("Ref. K41M") es el pedido de otra familia, ficticio. Muestra la referencia, cuántos productos tiene y a qué hora se libera, nunca un nombre ni una dirección.
- **Cancelar el pedido** (seguimiento, mientras la farmacia no empiece a preparar):
  - Es un botón de texto con su condición al lado. Al tocarlo, en el mismo lugar, sin ventana modal, aparece una confirmación: "¿Cancelar el pedido? Te devolveremos $57.460 a la misma tarjeta." con los botones "Sí, cancelar el pedido" (`secundario`) y "Seguir con el pedido" (`texto`). Es la única acción del pedido que mueve dinero de vuelta, así que no se ejecuta con un solo toque.
  - La pantalla "Pedido cancelado" usa la misma forma que "Un producto no llegó": una `Nota` con `Undo2` y la boleta con "Pagado" y "Te devolveremos", **en futuro**, con la nota de medio y plazo. Las dos devoluciones del sistema se ven iguales.
  - El aviso dice "Pedido cancelado. Te devolveremos $57.460."
- **El distintivo flotante** aparece abajo a la izquierda cuando la franja sale de la vista. El final de la página tiene un margen inferior de 6 rem para que nunca tape la última acción.

## 4. Lo que no decido yo

> **Al 26/10:** Jorge resolvió los puntos 1 (15 minutos), 2 (te vende MATU, una sola boleta), 3 (el mismo día, a la misma tarjeta), 5 y 6. Quedan abiertos los puntos 4, 7, 8 y 9.

| # | Tema | Qué muestra la demo mientras tanto | Quién decide |
|---|---|---|---|
| 1 | Cuántos minutos vale el total confirmado | "15 minutos, plazo de ejemplo" | **Jorge** |
| 2 | Quién vende y quién emite la boleta | "Quién vende y quién emite la boleta: por definir." Si a Jorge no le parece mostrar "por definir" frente al profesor, que elija un texto y lo valide el analista | **Consulta legal**, luego Jorge |
| 3 | Plazo de la devolución excepcional | "Plazo de la devolución: por definir." | **Consulta legal** y verificación con Transbank |
| 4 | Texto final de las condiciones del pedido y el retracto | Mi borrador de la escena 21, rotulado como borrador | **Analista normativo**, luego Jorge |
| 5 | **Quitar la casilla "Si falta algo, acepto un equivalente hasta 10% más caro"** | No aparece. El ADR prohíbe cambiar de marca sin aceptación previa, y con precio exacto ese margen ya no tiene sentido. Mantenerla obligaría a volver a diseñar el consentimiento | **Jorge** |
| 6 | Quitar el nombre de pila ("Para María") de la consola del comercio | No aparece (legal 5c) | **Jorge** |
| 7 | Costo del envío | $2.990 de ejemplo, cubierto por `PreciosDeEjemplo` | Jorge, cuando haya convenio |
| 8 | Que "Farmacia Piedra Azul" y "Farmacia Los Aromos" no sean comercios reales | Se usan con "(comercio ficticio)" | **Analista normativo**, que lo verifica |
| 9 | Elegir otro comercio para toda la lista | Fuera de la demo: la lista usa un comercio por defecto | Jorge, si lo quiere en el backlog |

## 5. Lo que el frontend necesita de otros

- **Datos de la demo** (`src/demo/`): los precios y comercios de la tabla de la sección 1; el envío de $2.990; la vigencia del total; la referencia opaca "K41M"; el estado "Ya no está" por línea; y la reasignación y la devolución simuladas. No hay endpoint real: todo es simulado, así que no hace falta pedir nada al backend para la demo.
- **Guía del presentador:** la lista de 36 escenas de la sección 1, con sus notas.
- **Íconos nuevos de lucide:** `RefreshCw`, `ArrowDownUp`, `Store`, `Lock`, `Download`, `Clock` y `Undo2`.
