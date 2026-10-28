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

---

## 6. Ajustes del 27/10 (relevo, compartir y "Quién la vio")

**Del diseñador, 27/10/2026.** Cinco ajustes chicos que Jorge aprobó el 27/10. No son del ADR-027, pero son para la misma demo. Los textos marcados **(aprobado)** son exactos y no se cambian. Lo marcado **(propuesta)** es mío, y Jorge lo puede quitar sin afectar lo demás. Todo usa tokens y componentes que ya existen: **no hace falta ningún token nuevo.**

**Términos prohibidos:** `docs/lenguaje.md` todavía no existe en el repo MATU, así que revisé contra la lista del backlog (MATU-30: diagnóstico, conducta, incidente, deterioro, incontinencia) y la de la sección 2 de este documento. Ningún texto de esta sección los usa.

### 6.1 Preguntas guía de la ficha, con el nombre y sin femenino

**Objetivo:** Carmen lee una pregunta que nombra a su mamá, y la misma pregunta sirve para cualquier persona cuidada.

**Textos (aprobado):**
- Su día: "¿Cómo es un día normal para {pila}? Puedes contar un día bueno o uno difícil."
- Si se altera: "¿Qué calma a {pila} cuando se angustia?"
- A quién llamar: sin cambios ("¿A quién llamar si algo pasa y no te ubican?").
- `{pila}` es `nombrePila(s)` de `demo/logica.ts`, que ya devuelve "María" si el estado no tiene nombre de pila. "María" no se escribe a mano en ningún otro lugar.

**Construcción:**
- `demo/datos.ts`: la `pregunta` de `TEXTO_CAMPO` deja de ser un texto fijo y pasa a ser una función `(pila: string) => string` (o se agrega `preguntaPara(campo, pila)`). Los ejemplos y los dictados no cambian, porque describen a María y no le preguntan nada a Carmen.
- Los dos lugares que muestran la pregunta la llaman con `nombrePila(s)`: `familia/Ficha.tsx`, en la lista de campos (cerca de la línea 112, el texto `text-tenue` de un campo vacío), y en "Editar un campo" (cerca de la 187, `#campo-pregunta`).
- `familia/Alta.tsx:126`, primera tarjeta de "MATU ordena lo que hoy está en tu cabeza", con la propuesta del orquestador: "Su día, qué hacer si se altera y a quién llamar. Tres campos cortos, para que quien te reemplace sepa qué hacer." En esa pantalla todavía no hay nombre, por eso no se usa `{pila}`.

**Criterios verificables:**
- `grep -rn "para ella\|Qué la calma\|qué la calma" src/` no encuentra nada.
- Si en el alta se escribe "Teresa" como nombre de pila, las dos preguntas dicen "Teresa".
- En "Editar un campo", la pregunta sigue en `text-base`, bajo el título `titular text-3xl`. En la lista de campos sigue cortada a dos líneas (`line-clamp-2`) y no desborda a 360 px.

### 6.2 Ayuda del teléfono al compartir

**Texto (aprobado):** la `ayuda` del `CampoTexto` "Su teléfono" en `Compartir` (`familia/Ficha.tsx`, cerca de la línea 358) pasa de "Para enviarle el enlace." a **"Para enviarle el enlace y poder contactarle."**

**Criterio:** la ayuda conserva el estilo de ayuda de `CampoTexto` (el componente no cambia). En pantalla ancha, con los dos campos en columnas (`@lg:grid-cols-2`), puede ocupar dos renglones sin desalinear los campos: los dos `input` quedan a la misma altura porque la ayuda va debajo.

### 6.3 Motivo obligatorio y recordatorio al crear el enlace

**Objetivo:** Carmen dice para qué comparte con un toque, sin escribir, y sabe qué contarle a Rosa cuando la llame para dictarle el PIN.

**Jerarquía en "Compartir"** (el orden de la columna no cambia): nombre y teléfono, "¿Qué puede ver?", "¿Hasta cuándo?", **"¿Para qué lo compartes?"** y el botón "Crear enlace".

**Esquema a 360 px:**

```
¿Para qué lo compartes?
( ◉ Salgo unas horas )  ( ○ Fin de semana fuera )
( ○ Turno de noche )    ( ○ Otro motivo )

[ Crear enlace ]
```

En pantalla ancha es el mismo grupo en `flex flex-wrap gap-2`: los cuatro caben en una o dos filas, según el ancho de la columna.

**Textos (aprobado):** la leyenda "¿Para qué lo compartes?" y las opciones "Salgo unas horas", "Fin de semana fuera", "Turno de noche" y "Otro motivo". Sin texto libre y sin "si quieres".

**Comportamiento:**
- **Siempre hay exactamente una opción elegida.** De partida, "Salgo unas horas", la misma de hoy y la que usa `accesoPorDefecto`. Tocar la elegida no la desmarca. Como el grupo nunca queda vacío, no hay mensaje de error.
- Las opciones viven en una constante de `demo/datos.ts` (por ejemplo `MOTIVOS`), y el tipo de `motivo` en `DatosCompartir` pasa a ser la unión de esos cuatro textos.
- En "Enlaces" la línea queda igual: "Ve su día, si se altera y a quién llamar. Otro motivo." Se lee bien porque cada opción es una frase.

**Semántica y forma (chip de opción única):**
- Un `fieldset` con su `legend` (`mb-2 font-bold`, igual que "¿Qué puede ver?" y "¿Hasta cuándo?"). Dentro van cuatro `label`, cada uno con un `input type="radio" name="motivo" className="sr-only"`. Sin `aria-pressed`: es un grupo de radio nativo, así que Tab entra a la opción elegida y las flechas la cambian.
- Cada `label` tiene la piel del `Chip` actual: `inline-flex min-h-12 max-w-full items-center gap-2 rounded-full px-4 py-2 font-bold ring-2 ring-inset`. Elegido: `bg-rocio text-pino ring-pino`. Sin elegir: `bg-hoja text-tenue ring-borde hover:ring-pino/40`. Nunca `pino` macizo, porque ese lugar es del botón "Crear enlace".
- **Indicador redondo, no cuadrado:** `size-5 rounded-full ring-2 ring-inset` (`ring-pino` si está elegido, `ring-tenue` si no) y, en la opción elegida, un punto `size-2.5 rounded-full bg-pino`. El cuadrado con check queda para los chips de varias opciones, como "¿Qué puede ver?". El estado se ve en la figura (punto lleno o círculo vacío), no solo en el color.
- **Foco:** el mismo de `GrupoOpciones`, con `has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pino` sobre el `label`: un contorno de 3 px en `pino`, con más de 3:1 sobre `papel` y `hoja` en los dos temas.
- **Área táctil:** `min-h-12`, que con la raíz de 17 px son 51 px, y todo el `label` se puede tocar.
- **Dónde se construye:** recomiendo una variante de `GrupoOpciones` en `components/Ui.tsx` (por ejemplo `forma="chips"`, con `flex flex-wrap gap-2` en vez de la grilla), para no repetir el patrón de foco.

**Recordatorio al crear el enlace.** La demo **no tiene** hoy un recordatorio parecido. Lo más cercano es "Díctaselo a {nombre} por teléfono. No lo mandes junto con el enlace. Solo lo verás ahora.", que habla del PIN y no cambia. El recordatorio nuevo va justo después, porque Carmen lo cumple en esa misma llamada.
- **Dónde:** en `EnlacePin` (`familia/Ficha.tsx`), dentro de la sección "PIN para abrir la ficha" (`bg-rocio`), después del párrafo "Díctaselo…".
- **Forma:** `<p className="flex gap-2 border-t border-linea pt-4 text-base">` con el ícono `Phone` de lucide (`aria-hidden mt-0.5 size-5 shrink-0 text-pino`). No usa `Nota`, porque ya está sobre `rocio` y una nota `rocio` adentro no se distinguiría.
- **Texto (aprobado):** "Cuéntale a {a.nombre} que anotaste su nombre y su teléfono en MATU, y que cada vez que abra el enlace o la ficha queda registrado."

```
┌ (llave) PIN para abrir la ficha ────────────┐
│        [ 4 ] [ 8 ] [ 2 ] [ 1 ]              │
│ Díctaselo a Rosa por teléfono. No lo mandes │
│ junto con el enlace. Solo lo verás ahora.   │
│ ─────────────────────────────────────────── │
│ (tel) Cuéntale a Rosa que anotaste su       │
│   nombre y su teléfono en MATU, y que cada  │
│   vez que abra el enlace o la ficha queda   │
│   registrado.                               │
└─────────────────────────────────────────────┘
```

**Criterios verificables:**
- Con el teclado, Tab llega a "Salgo unas horas", la flecha derecha elige "Fin de semana fuera" y el punto se mueve. No hay manera de dejar el grupo sin elección.
- Un lector de pantalla anuncia "¿Para qué lo compartes?, grupo" y cada opción como "botón de opción, 1 de 4, marcado".
- En la pantalla del PIN, el único `pino` macizo sigue siendo "Enviar el enlace por WhatsApp".
- Con texto al 200% a 320 px, los chips pasan a una columna y nada se corta.

### 6.4 Aviso al relevo en la pantalla del PIN

**Objetivo:** Rosa, que no tiene cuenta, sabe qué guarda MATU de ella antes de escribir el PIN, sin que eso le estorbe para entrar.

**Jerarquía** (`RelevoPin`, en `relevo/Relevo.tsx`):
1. El título "Carmen te compartió la ficha de María" y el campo del PIN.
2. "Ver la ficha", el único `pino` macizo, y "No necesitas cuenta ni instalar nada…", que se queda donde está.
3. El aviso, debajo y separado por una línea.

**Esquema a 360 px:**

```
          [llave]
 Carmen te compartió la ficha de María
 Escribe el PIN de cuatro números…
             PIN
         [ _ _ _ _ ]
        [ Ver la ficha ]
 No necesitas cuenta ni instalar nada…
 ─────────────────────────────────────
 (escudo) Tus datos en MATU
 MATU guarda tu nombre y tu teléfono, que
 anotó quien te compartió la ficha, para
 enviarte el enlace y poder contactarte. Tu
 teléfono se borra 30 días después de que el
 enlace vence o se corta.

 También registra cada vez que abres el
 enlace o la ficha y cada PIN incorrecto, y
 guarda ese registro 3 años, para saber a
 quién se compartió.

 Responsables de tus datos: Jorge Espinoza y
 Martín Henríquez. Puedes pedir ver, corregir
 o borrar tus datos.

 (hoja) Política de privacidad
```

En pantalla ancha se ve igual: la página del PIN es una sola columna centrada (`max-w-xl`), y el aviso usa el mismo ancho que el párrafo de arriba (`max-w-md`).

**Construcción:**
- Un `section` con `aria-labelledby`, después del párrafo "No necesitas cuenta…", con `flex w-full max-w-md flex-col gap-3 border-t border-linea pt-5 text-start`. Va **alineado a la izquierda** aunque la página esté centrada, porque tres párrafos centrados no se leen.
- Título (propuesta): un `h2` "Tus datos en MATU", con `flex items-center gap-2 text-base font-bold` y el ícono `ShieldCheck` (`aria-hidden size-5 shrink-0 text-pino`). Le da nombre a la región para el lector de pantalla y permite saltarla.
- **El texto aprobado, sin cambiar una palabra, en tres párrafos.** El corte es solo de presentación:
  1. "MATU guarda tu nombre y tu teléfono, que anotó quien te compartió la ficha, para enviarte el enlace y poder contactarte. Tu teléfono se borra 30 días después de que el enlace vence o se corta."
  2. "También registra cada vez que abres el enlace o la ficha y cada PIN incorrecto, y guarda ese registro 3 años, para saber a quién se compartió."
  3. "Responsables de tus datos: Jorge Espinoza y Martín Henríquez. Puedes pedir ver, corregir o borrar tus datos."
- Los párrafos van en **`text-base text-tenue leading-relaxed`**, no en `text-sm`. La escala (DISENO.md, sección 2) deja `text-sm` para datos secundarios que el público no lee, y este aviso se va a mostrar en el proyector. `tenue` sobre `papel` da más de 6:1 en el tema claro y más de 8:1 en el oscuro.
- **Sin acordeón.** Es lo que Rosa tiene que poder leer antes de entrar, y esconderlo detrás de "Ver más" lo convierte en letra chica. No compite con el PIN, porque va después del botón y con menos peso.
- **"Política de privacidad".** Hoy la demo **no enlaza a la política** en ninguna parte: el alta y "Grupo familiar" solo la nombran ("con la política de privacidad 0.9"), y la demo no tiene una página de la política. Para no inventar una ruta:
  - En la demo es un `Boton variante="texto"` con el ícono `FileText`, en su propio renglón (`self-start`, con su `min-h-12`). Al tocarlo muestra un aviso de la demo, igual que "Enviar el enlace por WhatsApp": "En la app se abre la política de privacidad, versión 0.9. En la demo no se abre ninguna página."
  - En la aplicación de `web/` será un `<a>` a la página pública de la política. Eso no es parte de esta demo.
- Sin `whitespace-nowrap` ni anchos fijos: con texto al 200% (el `zoom: 2` del escenario) a 320 px, el bloque baja de renglón y la página solo crece hacia abajo.

**Estados:** el aviso es igual en todos los estados de `RelevoPin` (normal, PIN incompleto y PIN incorrecto). No aparece en `NoDisponible` ni en la ficha.

**Criterios verificables:**
- El aviso está en el DOM debajo de "Ver la ficha" y su texto, sin contar los cortes de párrafo, es idéntico al aprobado.
- Ningún texto del aviso está bajo 1 rem.
- A 360 px y con texto al 200% no hay desplazamiento horizontal (`document.documentElement.scrollWidth <= innerWidth`).
- "Ver la ficha" se ve sin hacer scroll a 1280 × 720 en el proyector. El aviso puede quedar más abajo.

### 6.5 "Quién la vio" con "abrió el enlace"

**Objetivo:** Carmen ve si Rosa llegó al enlace, aunque todavía no haya escrito el PIN.

**El evento nuevo (aprobado):** "{nombre} abrió el enlace".
- **Cuándo se genera:** en `abrirRelevo` (`demo/logica.ts`), cuando el relevo entra a la página del PIN y antes de que lo escriba. En la guía pasa en la escena "Relevo: escribe el PIN", al cambiar al rol Relevo con el selector y con "Abrir como Rosa".
- **Sin duplicados:** no se registra de nuevo si el estado ya está en el rol relevo, con el mismo token y en la fase `pin`. Así, pasar de "Relevo: escribe el PIN" a "Relevo: la ficha" deja una sola línea "Rosa abrió el enlace" y una "Rosa abrió la ficha". Volver a entrar después de ver la ficha sí suma otra línea, porque es otra apertura.
- **Se registra aunque el enlace esté vencido o cortado:** también es una apertura, y a Carmen le sirve saber que Rosa intentó entrar (escena "Relevo: enlace no disponible").
- **Historia previa:** donde se siembra el fin de semana pasado (`demo/logica.ts`, cerca de la línea 267), se agrega "Rosa abrió el enlace" en el minuto −8897, antes de "Rosa abrió la ficha" (−8895). Así la escena "Quién la vio" muestra los dos tipos aunque se salte el relevo.
- **El tipo del evento:** `Evento` (`demo/tipos.ts`) suma el campo `tipo: 'enlace' | 'ficha' | 'otro'`, que `registrar` recibe como parámetro. "abrió la ficha" es `ficha`, "abrió el enlace" es `enlace`, y el resto (PIN mal escrito, bloqueo, vencimiento) es `otro`. Distinguirlos buscando palabras en el texto es frágil.

**Cómo se distingue de "abrió la ficha"** (componente `Eventos` de `familia/Ficha.tsx`):

| Evento | Ícono (lucide) | Círculo | Texto |
|---|---|---|---|
| Abrió el enlace | `Link2` | `bg-rocio text-pino` | "Rosa abrió el enlace" |
| Abrió la ficha | `UserRound` (el de hoy) | `bg-rocio text-pino` | "Rosa abrió la ficha" |
| PIN mal escrito y bloqueo | `CircleAlert` (el de hoy) | `bg-atenta-fondo text-atenta` | Sin cambios |

La diferencia está en la **figura** del ícono (un eslabón frente a una persona) y en el **verbo con su objeto**, no en el color: las dos aperturas usan el mismo círculo `rocio`. El color solo marca lo que pide atención, como hoy.

```
(persona)  Rosa abrió la ficha
           hace un momento
───────────────────────────────
(eslabón)  Rosa abrió el enlace
           hace un momento
───────────────────────────────
(persona)  Rosa abrió la ficha
           el sábado pasado
```

**Textos:**
- Bajada de "Quién la vio" (aprobado): "Una línea por cada vez que alguien abre el enlace o la ficha, o escribe mal el PIN. Es un respaldo para ti, no una vigilancia."
- Lista vacía de `Eventos`, para que diga lo mismo que la bajada (propuesta): "Todavía nadie ha abierto el enlace ni la ficha. Cuando alguien lo haga, aparece aquí."

**"Inicio" (`familia/Inicio.tsx:54`):** debe seguir mostrando la **última apertura de la ficha**, no la del enlace. A Carmen le importa si Rosa ya leyó la ficha, y "abrió el enlace" queda en "Quién la vio". Hay que cambiar `s.eventos.find((e) => e.texto.includes('abrió'))` por `s.eventos.find((e) => e.tipo === 'ficha')`. Si Rosa solo abrió el enlace, Inicio muestra la apertura anterior de la ficha, o nada.

**Guía del presentador (`demo/escenas.ts`):** ninguna nota repite "abrió la ficha" con esas palabras, pero dos narran lo que cambia (propuesta):
- `relevo-pin`: "Rosa abre sin cuenta y ve qué guarda MATU de sus datos. El token viaja en el fragmento /r#… y se borra al entrar. Abrir el enlace ya queda en «Quién la vio»."
- `quien-vio`: "Una línea cada vez que alguien abre el enlace o la ficha, o escribe mal el PIN. Respaldo, no vigilancia."
- `compartir` puede quedar igual. Si el presentador quiere nombrar el motivo: "Quién reemplaza, qué campos ve, hasta cuándo y para qué. 24 horas por defecto."

**Criterios verificables:**
- Después de las escenas "Relevo: escribe el PIN" y "Relevo: la ficha", "Quién la vio" muestra exactamente una línea nueva "Rosa abrió el enlace" y una "Rosa abrió la ficha", con la de la ficha arriba.
- Las dos líneas se distinguen en escala de grises, por la figura del ícono y por el texto.
- Inicio dice "Rosa abrió la ficha", nunca "Rosa abrió el enlace".

### 6.6 Archivos que toca el frontend

| Ajuste | Archivos |
|---|---|
| 6.1 Preguntas | `src/demo/datos.ts`, `src/familia/Ficha.tsx` (líneas ~112 y ~187), `src/familia/Alta.tsx:126` |
| 6.2 Teléfono | `src/familia/Ficha.tsx` (~358) |
| 6.3 Motivo y recordatorio | `src/familia/Ficha.tsx` (`Compartir`, ~398, y `EnlacePin`), `src/components/Ui.tsx` (variante de `GrupoOpciones`), `src/demo/datos.ts` (`MOTIVOS`), `src/demo/tipos.ts` (tipo de `motivo`) |
| 6.4 Aviso al relevo | `src/relevo/Relevo.tsx` (`RelevoPin`) |
| 6.5 Quién la vio | `src/demo/tipos.ts` (`Evento.tipo`), `src/demo/logica.ts` (`registrar`, `abrirRelevo`, `canjear` y la historia previa), `src/familia/Ficha.tsx` (`Eventos` y `QuienVio`), `src/familia/Inicio.tsx:54`, `src/demo/escenas.ts` (notas) |

**Fuera de lo aprobado, para que decida el orquestador:** en la misma pantalla, "¿Hasta cuándo?" también es de una sola opción, pero usa el `Chip` de varias (cuadrado con check y `aria-pressed`). Con 6.3 quedan dos grupos de una sola opción con figuras distintas, uno debajo del otro. Pasarlo a la misma variante es un cambio de una línea. Lo recomiendo (P3), pero no está en lo que aprobó Jorge.

---

## 7. Reflujo, P3 del 27/10 y vista de app en el teléfono

**Del diseñador, 27/10/2026.** Jorge decidió tres cosas:
- corregir ahora los P3 de mi revisión del 27/10;
- exigir el reflujo con el criterio literal de `CLAUDE.md`;
- que la demo se vea como app en un teléfono.

La parte "llenar el proyector" (escalar la raíz en pantallas grandes) **quedó fuera** por decisión de Jorge: la demo se proyecta con la vista de escritorio tal como está.

**Orden de entrega, por prioridad.** El frontend puede entregar por partes, y cada una se revisa sola.

| Parte | Qué | Tamaño |
|---|---|---|
| 7.3 | Reflujo: 0 escenas con desplazamiento horizontal a 320 px con el texto al 200% | **Media**: unas 30 clases en 9 archivos y una pieza chica, sin lógica. De 2 a 3 horas con la verificación |
| 7.4 | Áreas táctiles bajo 48 px que encontré al medir | **Chica**: 4 clases. Media hora |
| 7.5 | Los tres P3 | **Chica**: 2 cambios y una confirmación. Media hora |
| 7.6 | Vista de app en el teléfono | **Media**: la barra inferior, la franja compacta y dos desplazamientos. De 3 a 4 horas. Lo que conviene dejar para después está en 7.6.5 |

**Lo que ya hice yo**, en este mismo commit y en `src/index.css` (capa `base` y variantes):
- **`overflow-wrap: break-word` en `body`.** Si una palabra no cabe sola en su renglón, se parte en vez de salirse.
  - Es `break-word` y no `anywhere` a propósito. Lo probé con `anywhere`, y en la barra de secciones "Ficha de relevo" quedaba en una columna de una letra por renglón, porque `anywhere` achica el ancho mínimo de todo.
  - `break-word` no cambia ningún ancho mínimo: a 1280 y 1920 px no mueve una sola caja.
- **Dos variantes nuevas**, justificadas en `DISENO.md`, sección 3:
  - `angosto:` se activa cuando la app mide menos de 16 rem. Solo pasa con "Texto al 200%" en una pantalla de menos de 544 px. Ahí se quitan rellenos y se apila lo que va lado a lado.
  - `telefono:` se activa cuando la pantalla mide menos de 40 rem (640 px) **y** la app no está en modo angosto. Es la vista de app móvil.
- **Las dos miran el contenedor `app` del escenario.** Lo que está fuera de la app (la franja y el distintivo del presentador) usa `max-sm:` de Tailwind, que es el mismo corte de 40 rem, medido sobre la pantalla.
- **Ninguna de las dos se activa a 1280 px**, tampoco con "Texto al 200%": ahí la app mide 640 px y la pantalla 1280. Lo verifiqué compilando:
  - `angosto:px-2` sale como `@container app not (width>=16rem)`;
  - `telefono:fixed` sale como `@media not all and (width>=40rem)` con `@container app (width>=16rem)` adentro.

### 7.1 Cómo medí

- **El script.** Usé el del QA (`qa2710c.mjs`), extendido para decir **qué elemento** provoca el desborde: el que se sale cuando su padre todavía cabe.
  - Ancho de 320 px y "Texto al 200%" desde la guía. Es el `zoom: 2` sobre la app, o sea **160 px efectivos**.
  - Las 36 escenas.
  - Desborde = `document.documentElement.scrollWidth - innerWidth`.
- **Una aclaración para el informe.** 320 px con el texto al 200% es más exigente que WCAG, que pide **o** 320 px de ancho (1.4.10, que equivale a 1280 px al 400%) **o** texto al 200% (1.4.4), no las dos cosas a la vez. Es lo que pide `CLAUDE.md` y lo que decidió Jorge, así que se cumple tal cual.
- **La medición de hoy (HEAD `752f541`).** A 320 px con el texto al 200%, **23 de 36 escenas desbordan**, igual que en la medición del QA. Con el mismo método y el texto al 200%:
  - a 360 px desbordan 16;
  - a 400 px, 13;
  - a 480 px, 1;
  - desde 540 px, ninguna.
- **El prototipo.** Antes de escribir esta sección probé todas las correcciones inyectando su CSS equivalente en la demo, sin tocar componentes:
  - Con el texto al 200%, a 320, 360, 400, 480, 540 y 600 px: **0 de 36** escenas desbordan.
  - Sin zoom, a 320, 360, 390 y 430 px, con la vista de teléfono puesta: **0 de 36**.
  - A 1280 × 800, 1366 × 768 y 1920 × 1080, y a 1280 px con el texto al 200%, comparé la caja de cada elemento de la app en las 36 escenas, con y sin el prototipo. **Ninguna caja cambia.** Las únicas diferencias fueron ruido de la medición: el aviso flotante, y la guía, que quedó abierta en una de las dos tomas de la escena 7.

### 7.2 Escenas que desbordan hoy y por qué

El desborde está en px de pantalla, a 320 px con el texto al 200%. Los patrones (R1 a R11) están en 7.3.

| # | Escena | Desborde | Elemento que se sale | Patrón |
|---|---|---|---|---|
| 1 | Bienvenida | +13 | Los textos de las tres tarjetas, junto a su ícono de 44 px | R10 |
| 4 | ¿A quién cuidas? | +54 | Las opciones de apoyo: la grilla tiene una pista `auto` que no baja del ancho de su contenido | R1, R10 |
| 5 | Permiso | +107 | Las tres opciones del permiso, igual que en la escena 4 | R1, R10 |
| 6 | Inicio | +66 | "24/10/2026, 10:05" en un solo `cifras` y la etiqueta "Pronto" | R3, R2 |
| 10 | Enlace y PIN | +95 | Los cuatro dígitos `w-17` (289 px en total). Además, "Vence el 31/10/2026" va junto al ícono de 64 px, que le deja 41 px | R6, R7, R8 |
| 12 | Relevo: la ficha | +20 | La grilla de la página del relevo, que tiene una pista `auto` | R1 |
| 13 | Quién la vio | +126 | "25/10/2026, 23:59" en un solo `cifras`, con 75 px disponibles | R3 |
| 14 | Cortar un acceso | +195 | La etiqueta "Activo, vence en 23 h" con `shrink-0` y las fechas de los eventos | R2, R3 |
| 16 | Qué se está acabando | +129 | "6 días · Pronto" sin `flex-wrap`, las etiquetas y "05/11/2026" en `text-2xl` | R2, R4, R7 |
| 17 | Declarar consumo | +129 | Lo mismo de la 16, más "hasta el 05/11/2026", que queda dentro de dos rellenos y junto a un ícono | R2, R4, R8 |
| 18 | Ya lo compré | +129 | "6 días · Pronto" y las etiquetas | R2, R4 |
| 19 | Lista de reposición | +156 | El nombre con `min-w-48` (204 px de mínimo) y el selector de paquetes sin `flex-wrap` | R5 |
| 20 | Exportar o compartir la lista | +156 | Lo mismo de la 19 | R5 |
| 21 | Tu pedido, antes de pagar | +111 | Las etiquetas "Cambió el precio" y "Salió del pedido" | R2 |
| 22 | Pasarela simulada | +140 | La lista de dos columnas `[auto_1fr]`, con los montos alineados a la derecha | R9, R10 |
| 24 | Comercio: pedidos del día | +37 | La grilla de la consola (pista `auto`), la etiqueta "Por preparar" y el paso "2 Preparar" con su conector | R1, R2, R11 |
| 25 | Comercio: preparar | +49 | La grilla de la consola y los pasos | R1, R11 |
| 26 | Comercio: código de retiro | +91 | La etiqueta "Listo para retiro" y los pasos | R2, R11 |
| 27 | Cambio de local | +5 | "Suplemento", dentro de una `Nota` con ícono que le deja 58 px al texto | R10 |
| 28 | Entregado | +36 | "Llegó a las 15:58" en `text-3xl`, junto al círculo de 56 px | R7 |
| 30 | Dos versiones | +16 | La grilla de las dos versiones (pista `auto`) y el aviso | R1, R10 |
| 31 | El total venció | +111 | La etiqueta "Cambió el precio" | R2 |
| 33 | Un producto no llegó | +36 | "Llegó a las 17:00", igual que en la 28 | R7 |

Hoy no desbordan las escenas 2, 3, 7, 8, 9, 11, 15, 23, 29, 32, 34, 35 y 36.

### 7.3 Patrones y su corrección

Son once patrones. Los cuatro primeros están en componentes compartidos y arreglan la mitad de las escenas. Todo usa clases de Tailwind y tokens que ya existen, más las variantes `angosto:` y `telefono:`. **Nada cambia a 1280 ni a 1920 px**, salvo donde lo digo.

**R1 · Grillas de una columna sin `grid-cols-1`.** Una grilla sin columnas declaradas crea una pista `auto`, que nunca es más angosta que su contenido más ancho. `grid-cols-1` es `repeat(1, minmax(0, 1fr))`, que sí puede achicarse. Se agrega **además** de la variante que ya tiene cada grilla, que la sigue reemplazando en pantalla ancha:
- `familia/Shell.tsx`, `Columnas`: `grid grid-cols-1 items-start …`. Sirve a todas las páginas de la familia.
- `familia/Pedidos.tsx`, `DosZonas`: `grid grid-cols-1 items-start …`.
- `relevo/Relevo.tsx`, `RelevoFicha`: `mx-auto grid max-w-6xl grid-cols-1 …`.
- `comercio/Comercio.tsx`, cerca de la línea 360: `mx-auto grid max-w-7xl grid-cols-1 …`.
- `familia/Ficha.tsx`, en dos lugares: "Dos versiones" (`mt-6 grid …`, cerca de la línea 291) y los datos del enlace (`grid gap-4 @lg:grid-cols-2`, cerca de la 353).
- `components/Ui.tsx`, `GrupoOpciones` en forma de lista: `grid grid-cols-1 gap-2 …`.
- **Regla para lo que venga:** toda grilla declara sus columnas también en el ancho más chico.

**R2 · Etiquetas de estado que no se pueden achicar.** `Etiqueta` y `EtiquetaNivel` (`components/Ui.tsx`) tienen `shrink-0` y ningún tope, así que "Activo, vence en 23 h" mide lo que mide aunque no quepa.
- Se agrega **`max-w-full`** a las dos y se deja `shrink-0`. Así la palabra que no cabe pasa al renglón siguiente dentro de la píldora.
- La figura (● ◐ ○) no se mueve, porque es otro elemento del `flex`.

**R3 · Fecha y hora en un solo `cifras`.** `cifras` no deja cortar, así que "24/10/2026, 10:05" es un bloque de 155 px en una columna de 75.
- **Pieza nueva en `components/Ui.tsx`: `Cuando({ texto, className })`.**
  - Recibe lo que ya devuelve `fmtCuando` ("Hoy, 10:05" o "24/10/2026, 10:05").
  - Lo corta en ", " y pone cada parte en su propio `cifras`, con la coma pegada a la primera parte y un espacio normal entre las dos.
  - El envoltorio lleva `tabular-nums` y la `className` que se le pase.
- Así puede pasar al renglón siguiente **entre la fecha y la hora, nunca dentro de "30/10/2026"**. No cambia `fmtCuando` ni ningún dato.
- Se usa en dos lugares:
  - `familia/Ficha.tsx`, en `Eventos` (cerca de la línea 600), con `className="text-base text-tenue"`;
  - `familia/Inicio.tsx:180`, con `className="text-tenue"`. Ese `p` deja de tener `cifras`.
- La regla de `DISENO.md`, sección 2, queda así: `cifras` envuelve una sola cifra, fecha **u** hora. Una fecha con su hora son dos `cifras`.

**R4 · "6 días · Pronto" sin `flex-wrap`.** En `familia/Insumos.tsx`, cerca de la línea 85, `flex items-center gap-3` pasa a **`flex flex-wrap items-center gap-x-3 gap-y-1`**. La etiqueta baja debajo de los días solo si no cabe al lado.

**R5 · Anchos fijos en la lista de reposición** (`familia/Insumos.tsx`, cerca de las líneas 312 a 345):
- **El nombre:** `min-w-48 flex-1` pasa a **`min-w-0 grow basis-48`**.
  - En pantalla ancha se comporta igual: la base de 12 rem decide cuándo baja de renglón, y el nombre toma el resto del espacio.
  - La diferencia es que, cuando queda solo en su renglón, ahora puede medir menos de 12 rem.
- **El selector de paquetes** (`role="group"`): `flex items-center gap-2` pasa a **`flex flex-wrap items-center gap-2`**.
- **Cada fila:** `px-4` pasa a **`px-4 angosto:px-2`**.
- **El subtotal:** `w-26` pasa a **`w-26 angosto:w-auto`**.
- Los botones − y + se corrigen en 7.4.

**R6 · Los dígitos del PIN** (`familia/Ficha.tsx`, `EnlacePin`, cerca de las líneas 483 a 494). No se tocan, así que no necesitan 48 px. En pantalla ancha quedan exactamente igual:
- El `p`: `flex justify-center gap-3` pasa a **`flex justify-center gap-3 angosto:gap-1.5`**.
- **Cada dígito** suma **`angosto:h-16 angosto:w-auto angosto:min-w-0 angosto:flex-1 angosto:text-3xl`**.
  - Los cuatro se reparten el ancho en partes iguales.
  - El número baja de `text-6xl` a `text-3xl`. Con el zoom de 200%, en la pantalla sigue midiendo 64 px.
- Los dígitos quedan siempre en **una sola fila de cuatro**, nunca en 2 + 2, porque se dictan como un bloque.
- **La sección del PIN:** `px-6 py-6` pasa a **`px-6 py-6 angosto:px-3`**.

**R7 · Un ícono grande al lado de un título, o una fecha en tamaño de título.**
- **"Enlace creado"** (`familia/Ficha.tsx`, el `div` `flex items-center gap-4` con el ícono `size-16`, cerca de la línea 444) y **"Pedido entregado"** (`familia/Pedidos.tsx`, el `div` con el círculo `size-14`, cerca de la línea 718) suman **`angosto:flex-col angosto:items-start angosto:gap-3`**.
  - El ícono queda arriba y el texto usa todo el ancho.
  - Así "Vence el 31/10/2026" y "Llegó a las 15:58" caben sin partir la fecha.
- **"Le alcanza 6 días, hasta el 05/11/2026"** (`familia/Insumos.tsx:131`, hoy en `text-2xl`) pasa a **`text-2xl angosto:text-xl`**.

**R8 · Rellenos anidados.** Con 160 px de ancho, cada `px-4` se come 34 px. En modo angosto se reducen a `px-2` en el borde de la página y en las superficies que tienen fechas o controles adentro:
- **Los `main`:** se agrega **`angosto:px-2`** a cada uno:
  - `familia/Shell.tsx:164`;
  - `relevo/Relevo.tsx:25`;
  - `comercio/Comercio.tsx:359`;
  - `familia/Alta.tsx:73` (hoy `px-5`);
  - `familia/Pedidos.tsx`, líneas 418 y 433 (la pasarela).
- **El `Detalle` de `familia/Insumos.tsx`** (el `section` `px-4 @3xl:px-7`): **`angosto:px-2`**.
- **El recuadro "Le alcanza…" de "Declarar consumo"** (`border-l-4 border-pino bg-rocio px-4`, cerca de la línea 168): **`angosto:px-2`**. Su ícono `CalendarCheck` lleva **`angosto:hidden`**, porque es decorativo y la frase dice lo mismo.

**R9 · La lista de dos columnas de la pasarela** (`familia/Pedidos.tsx:446`):
- El `dl`: `grid grid-cols-[auto_1fr]` pasa a **`grid grid-cols-[auto_1fr] angosto:grid-cols-1`**.
- Cada `dd`: `text-right` pasa a **`text-right angosto:text-left`**.
- En modo angosto, cada dato va debajo de su nombre: "Monto a pagar" y, abajo, "$57.460".

**R10 · Palabras largas en columnas angostas.** "representación", "Suplemento" y "comprenderlo" no caben en 58 px. Lo cubren R8, que da más ancho, y el `overflow-wrap: break-word` de la capa base, que ya está hecho. No hay que tocar componentes.

**R11 · Los pasos del pedido en la consola** (`comercio/Comercio.tsx`, `Pasos`, línea 116). El conector `h-0.5 w-6` lleva **`angosto:hidden`**: cuando los pasos bajan de renglón, el conector ya no une nada.

### 7.4 Áreas táctiles bajo 48 px (P2)

Al medir encontré cuatro controles de menos de 48 px:
- `size-11` y `min-h-11` son 2,75 rem, que con la raíz de 17 px dan **46,75 px**;
- `min-h-10` da **42,5 px**.

| Dónde | Hoy | Corrección | ¿Se ve a 1280 px? |
|---|---|---|---|
| `familia/Insumos.tsx:312`, botones − y + de la lista | `size-11` (46,75 px) | `size-12` (51 px) | Sí: cada botón crece 4 px |
| `familia/Shell.tsx:109`, secciones de la barra lateral | `min-h-11` (46,75 px) | `min-h-12` | Sí: la barra lateral crece unos 21 px de alto en total |
| `familia/Shell.tsx:205`, "Volver a…" | `min-h-10` (42,5 px) | `min-h-12` | Sí: 9 px más de alto |
| `familia/Pedidos.tsx:371`, "Ver las condiciones" | `min-h-10` (42,5 px) | `min-h-12` | Sí: 9 px más de alto |

**Son los únicos cambios visibles a 1280 px fuera de los P3.** Los recomiendo, porque el mínimo de 48 px no se negocia. Si Jorge prefiere no mover nada a 1280 px, los cuatro se pueden limitar al teléfono con `telefono:size-12` y `telefono:min-h-12`. Lo decide él.

Los controles del presentador (`size-10` y `min-h-10` en la franja) no son parte de MATU. En el teléfono pasan a 48 px (ver 7.6.3).

### 7.5 Los P3

**P3 · "Política de privacidad" alineado con los párrafos** (`relevo/Relevo.tsx`, cerca de la línea 141).
- **Lo que medí a 1280 px:** los párrafos empiezan en x = 402 y el ícono del botón en x = 423,25. En la variante `texto` de `Boton`, el `px-1` pierde contra el `px-5` de la base, así que el relleno real es de 21,25 px. Por eso `-ms-1` no alcanza.
- **La corrección:** `className="self-start ps-0"`. El relleno inicial queda en 0 y el ícono se alinea con el texto.
  - Si `ps-0` no le ganara a `px-5` por el orden del CSS, se usa `-ms-5`. El criterio se mide igual.
  - No cambio `Boton` para todos, porque movería los demás botones de texto de la demo a 1280 px.
- **Criterio:** el borde izquierdo del ícono `FileText` coincide con el de los párrafos del aviso, con 1 px de tolerancia.

**P3 · Los motivos en 2 + 2** (`familia/Ficha.tsx`, `Compartir`, y `components/Ui.tsx`, `GrupoOpciones` en forma de chips).
- **Lo que medí a 1280 px:** la columna mide 419 px y los chips quedan en tres filas: "Salgo unas horas", luego "Fin de semana fuera", y al final "Turno de noche" y "Otro motivo".
- **El `@md` que se propuso no sirve.** `@md` es 28 rem (476 px), más que los 419 px de la columna, así que a 1280 px los motivos quedarían en **una** columna de cuatro filas.
- **La corrección:** `GrupoOpciones` con `forma="chips"` recibe la propiedad `columnas`, que ya existe en la forma de lista. Si viene:
  - el contenedor pasa de `flex flex-wrap gap-2` a **`grid grid-cols-1 gap-2 @xs:grid-cols-2`** (`@xs` es 20 rem, 340 px, medido sobre la `Columna`);
  - cada `label` pasa de `inline-flex … max-w-full` a **`flex w-full …`**. El resto de la piel no cambia.
- Solo "¿Para qué lo compartes?" pasa `columnas`.
- **Cómo se ve, según el ancho:**
  - **A 1280 px** (lo probé): 2 + 2, con cada chip de 205 px. "Fin de semana fuera" ocupa **dos renglones** dentro de su chip, y su vecino toma la misma altura. Es un cambio visible, y es el que se pidió.
  - **A 1920 px**, cada chip cabe en un renglón.
  - **A 360 px**, la columna mide menos de 340 px y los motivos quedan en una columna de cuatro chips de ancho completo.
- **"¿Hasta cuándo?" no lo necesita.** Ya queda en 2 + 1: "24 horas" y "Fin de semana", y abajo "Otra cantidad de días". En la grilla, "Otra cantidad de días" se partiría en dos renglones sin ganar nada. Se queda en `flex flex-wrap`.

**P3 · Ayudas en `text-sm`: confirmo que no requieren acción.**
- Las ayudas de `CampoTexto` y `Stepper` (14,9 px) son justo el uso que `DISENO.md` reserva para `text-sm`: la ayuda bajo un campo, que el público no necesita leer.
- El criterio nuevo de reflujo no las afecta. Con el texto al 200% crecen igual que todo lo demás (30 px en pantalla), y ninguna provocó un desborde en la medición.
- Las ayudas que el público sí lee ya están en `text-base`: la de "¿Hasta cuándo?" y el aviso del relevo.

### 7.6 Vista de app en el teléfono

**Objetivo:** quien abre la demo en su teléfono ve MATU como la app móvil que es (ADR-026). Tiene una columna, la barra de secciones abajo, al alcance del pulgar, y los controles de la demo no ocupan media pantalla.

**Lo que medí hoy a 390 × 844:**
- La franja del presentador ocupa **225 px**: distintivo, roles, escena y guía, en cuatro renglones.
- Las cinco secciones de la familia ocupan otros **200 px** arriba, en tres renglones.
- El título de la página empieza cerca de y = 590, así que la primera pantalla casi no muestra contenido.
- El relevo y el comercio ya son de una columna.

**Cuándo se activa:** con la variante `telefono:`, o sea con una pantalla de menos de 640 px y la app de 16 rem o más.
- Con "Texto al 200%" en un teléfono, la app entra en modo angosto. La barra vuelve a su lugar de hoy, arriba, y todo refluye según 7.3. Una barra fija de cinco secciones no cabe en 160 px.
- A 1280 px no se activa nunca.

#### 7.6.1 Barra de secciones abajo (familia)

```
┌────────────────────────────────────┐
│ (M) MATU                           │  aside: solo la marca
├────────────────────────────────────┤
│ Cuidas a                           │
│ María Soto        viernes 30/10…   │
│ …contenido…                        │
│                                    │
├────────────────────────────────────┤  fija, fondo hoja, borde superior linea
│ (⌂)    (▤)•   (□)•   (◫)    (⚇)    │
│Inicio Ficha Insumos Pedidos Grupo  │  5 columnas iguales, mín. 56 px de alto
└────────────────────────────────────┘
```

Se construye en `familia/Shell.tsx`, todo con `telefono:`.

- **`nav`:** `telefono:fixed telefono:inset-x-0 telefono:bottom-0 telefono:z-20 telefono:border-t telefono:border-linea telefono:bg-hoja telefono:px-1 telefono:py-1`.
- **`ul`:** `telefono:grid telefono:grid-cols-5 telefono:gap-1` (hoy es `flex flex-wrap gap-1`).
- **El botón de cada sección:** `telefono:min-h-14 telefono:flex-col telefono:flex-nowrap telefono:justify-center telefono:gap-0.5 telefono:px-1 telefono:text-center telefono:text-sm telefono:leading-tight`.
  - Con `min-h-14` mide 59,5 px de alto, y unos 70 px de ancho a 360 px.
  - **La sección elegida** lleva `telefono:bg-rocio telefono:ring-0`, además del `font-bold`, el trazo más grueso del ícono y el `aria-current="page"` que ya tiene. Se distingue por la píldora de fondo y por el peso, no solo por el color.
  - **`text-sm` en la barra es una excepción.** La barra nunca se ve en el proyector, y ese es el tamaño estándar de una barra de pestañas en un teléfono.
- **Rótulos cortos.** `SECCIONES` suma el campo `corto`: "Inicio", "Ficha", "Insumos", "Pedidos" y "Grupo".
  - Se escriben los dos textos: `<span className="telefono:hidden">{texto}</span>` y `<span className="hidden telefono:inline">{corto}</span>`.
  - El nombre accesible es el que se ve.
- **La pista** ("1 de 3", "Pronto", "En curso") no cabe abajo del rótulo:
  - En el teléfono, su texto pasa a `telefono:sr-only`. El lector de pantalla sigue diciendo "Insumos, Pronto".
  - Sobre el ícono aparece un punto `size-2.5 rounded-full bg-current`, `aria-hidden`, arriba a la derecha (`absolute -top-0.5 -right-1`, con el ícono envuelto en un `span relative`). Es `text-pronto` para "Pronto" y `text-pino` para las otras dos.
  - Es una figura (hay punto o no hay), no solo un color, y la palabra se lee al entrar a la sección.
- **El `aside`** queda solo con la marca: `telefono:py-2`.
- **El espacio para la barra:** el `main` lleva `telefono:pb-36`, para que el último botón de la página no quede debajo de la barra ni del distintivo flotante.

#### 7.6.2 Lo que flota sobre la barra

Dos elementos flotan en la parte de abajo de la pantalla y la barra los taparía. Los dos se suben **solo cuando el rol es familia** (`Escenario.tsx` ya sabe el rol):
- **`DistintivoFlotante`** (`presentador/Presentador.tsx`, hoy `bottom-3`). Sigue siendo obligatorio y siempre visible. Recibe una propiedad `sobreBarra` y suma **`max-sm:bottom-20`**: queda a 85 px del borde, sobre la barra, que mide unos 69 px.
- **El `Aviso`** (`Escenario.tsx`): con el mismo criterio, **`max-sm:bottom-20`** en vez de `bottom-5`.

Usan `max-sm:` porque están fuera del contenedor `app`. Con "Texto al 200%" en el teléfono no hay barra, así que los dos quedan 64 px más arriba de lo necesario, sin tapar nada.

#### 7.6.3 La franja del presentador en el teléfono

**Lo que propongo:** una franja compacta, en el flujo de la página como hoy (no es fija y no tapa la app), en **dos renglones de 48 px**:

```
┌────────────────────────────────────┐
│ (● Piloto académico   )     [📖 ?] │  distintivo (siempre) y guía
│ (  con datos de prueba)            │
│  [‹]  6 de 36  [›]     PIN 4821    │  escena y la ayuda de la escena
└────────────────────────────────────┘
```

Se construye en `presentador/Presentador.tsx`, con `max-sm:`.

- **Se ocultan:**
  - el `SelectorRol` compacto (`max-sm:hidden` en su `fieldset`);
  - la `DireccionRelevo` (`max-sm:hidden`);
  - el título de la escena (`max-sm:sr-only`, para que el lector de pantalla lo siga anunciando);
  - la etiqueta Real o Simulado (`max-sm:hidden`).
- **Todo eso ya está en el cajón de la guía:** el selector de rol completo, la escena con su nota y su etiqueta, y las ayudas. En el teléfono, el cajón ya ocupa toda la pantalla (`w-full max-w-sm`).
- **Se quedan:**
  - el distintivo;
  - "‹ 6 de 36 ›";
  - las ayudas de la escena ("PIN 4821", "Abrir como Rosa"), que bajan de renglón si no caben;
  - el botón de la guía.
- **48 px:** los botones ‹ y › pasan a `max-sm:size-12`, y el de la guía a `max-sm:min-h-12 max-sm:min-w-12`. A 1280 px siguen como hoy.
- **Lo que medí en el prototipo a 390 px:** la franja baja de 225 a unos 110 px. La marca, el encabezado y el título de la página quedan en la primera pantalla.

**Lo que descarté:**
- **Una franja plegable:** suma un estado y un botón más.
- **El modo presentación en el teléfono:** el distintivo flotante taparía el encabezado.

#### 7.6.4 Relevo y comercio

- **Relevo:** ya es una página de una columna, centrada y sin navegación, que es lo que tiene que ser en un teléfono.
  - Solo le aplican los cambios de 7.3.
  - Con la franja compacta, a 390 × 844 el PIN y "Ver la ficha" quedan en la primera pantalla.
- **Comercio:** es una consola de escritorio. En el teléfono se ve en una columna: la cola y, debajo, el pedido elegido. Al elegir uno, el foco y el scroll ya van al detalle.
  - No le pongo barra inferior, porque tiene una sola sección.
  - Solo le aplican R1, R2, R8 y R11.

#### 7.6.5 Riesgo y qué dejar para después

- **Lo que entra antes del jueves: 7.6.1 a 7.6.3.** Son clases con variantes, dos textos cortos y una propiedad, sin lógica ni estado nuevos, y se revisan con el mismo script de reflujo.
- **Lo que dejaría para después del viernes:**
  - **Compactar el encabezado de la familia en el teléfono.** "Cuidas a / María Soto / viernes…, 14:20 / Carmen" ocupa unos 130 px, y se podría llevar a un renglón con el avatar.
  - **El área segura de los iPhone** (`env(safe-area-inset-bottom)`). Sin `viewport-fit=cover`, Safari ya deja la barra sobre su propia barra de herramientas.
  - **Ocultar la franja al hacer scroll.**
- **Si el plazo aprieta,** el corte natural es **entregar primero 7.3 a 7.5**. La vista de teléfono es independiente y no cambia nada a 1280 px.

### 7.7 Archivos que toca el frontend

| Archivo | Qué |
|---|---|
| `src/components/Ui.tsx` | R1 (`GrupoOpciones` en forma de lista), R2 (`Etiqueta` y `EtiquetaNivel`), R3 (pieza `Cuando`), P3 de los motivos (`columnas` en la forma de chips) |
| `src/familia/Shell.tsx` | R1 (`Columnas`), R8 (`main`), 7.4 (`min-h-12` en las secciones y en "Volver"), 7.6.1 (barra inferior, `corto`, punto de la pista y `pb-36`) |
| `src/familia/Ficha.tsx` | R1 ("Dos versiones" y datos del enlace), R3 (`Eventos`), R6 (PIN), R7 ("Enlace creado"), P3 de los motivos (`columnas`) |
| `src/familia/Insumos.tsx` | R4, R5, R7 (`text-xl`), R8 (`Detalle`, el recuadro y su ícono), 7.4 (`size-12`) |
| `src/familia/Inicio.tsx` | R3 (línea 180) |
| `src/familia/Pedidos.tsx` | R1 (`DosZonas`), R7 ("Pedido entregado"), R8 (los dos `main`), R9 (pasarela), 7.4 ("Ver las condiciones") |
| `src/familia/Alta.tsx` | R8 (`main`) |
| `src/relevo/Relevo.tsx` | R1, R8 y el P3 de la política |
| `src/comercio/Comercio.tsx` | R1, R8 y R11 |
| `src/presentador/Presentador.tsx` | 7.6.2 (`sobreBarra` en `DistintivoFlotante`) y 7.6.3 (franja compacta) |
| `src/Escenario.tsx` | 7.6.2 (pasa `sobreBarra` y sube el `Aviso` cuando el rol es familia) |

`src/index.css` y `DISENO.md` ya quedan hechos en este commit. No se toca nada de `src/demo/` ni de `src/datos/`.

### 7.8 Criterios verificables

1. **Reflujo.** Con el script de 7.1, **0 de 36** escenas tienen `scrollWidth > innerWidth`:
   - a 320 px con el texto al 200%;
   - a 360, 400, 480 y 540 px con el texto al 200%;
   - a 320, 360, 390 y 430 px sin zoom.
2. **Ninguna fecha partida.** En esas medidas, ningún "DD/MM/AAAA" ni "HH:MM" se corta entre dos renglones: cada uno está en su propio `cifras`.
3. **PIN.** A 320 px con el texto al 200%, los cuatro dígitos están en una sola fila, dentro de la sección `rocio`.
4. **Sin cambios a 1280 y 1920 px.** La caja de cada elemento de la app en las 36 escenas, a 1280 × 800, 1366 × 768 y 1920 × 1080, es la misma que en `752f541`. La guía del presentador se cierra antes de cada toma. Las únicas excepciones permitidas son:
   - los dos P3 que se ven (la política y los motivos en 2 + 2);
   - los cuatro controles de 7.4, si Jorge los acepta así.
5. **48 px.** Todo lo que se toca en la app mide 48 px o más de alto y de ancho, a 360 y a 1280 px. Incluye las cinco secciones de la barra inferior, los botones − y + de la lista, y ‹ y › en la franja del teléfono.
6. **Teléfono, a 390 × 844 y en el rol familia:**
   - la barra inferior está fija y tiene cinco secciones con ícono y rótulo;
   - la sección elegida tiene `aria-current="page"` y fondo `rocio`;
   - el título de la página se ve sin hacer scroll;
   - el distintivo flotante y el aviso quedan sobre la barra, sin taparse.
7. **Teléfono con el texto al 200%.** No hay barra fija: las secciones vuelven arriba, como hoy, y se cumple el punto 1.
8. **Distintivo.** "Piloto académico con datos de prueba" se ve completo en todas las escenas a 360 px, con y sin scroll, en los dos temas.
9. **`prefers-reduced-motion`.** Nada de esto agrega animaciones.
10. **Política.** El ícono de "Política de privacidad" empieza en la misma x que los párrafos del aviso, con ±1 px de tolerancia.
11. **Motivos.** A 1280 px, "Salgo unas horas" y "Fin de semana fuera" están en la misma fila, y "Turno de noche" y "Otro motivo" en la siguiente. Siguen siendo un grupo de radio nativo y cumplen los criterios de 6.3.
