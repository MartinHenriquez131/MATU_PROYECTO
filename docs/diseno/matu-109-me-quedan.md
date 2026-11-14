# MATU-109 · «Me quedan» con envases cerrados y sueltos, y el total con el envío · Especificación de diseño

**Versión 1.0 · 13/11/2026** · Agente 6, UI/UX. Especifica y no construye. Por aprobar por Jorge (decisiones D1 a D5).

**Viene de:** la ronda 2 de usabilidad (`docs/usabilidad/ronda-2-informe.md` del repositorio MATU, 12/11/2026):
- **H1 (P2):** en U3, declarar lo que queda cuando hay envases cerrados y unidades sueltas a la vez fue lo que más costó. P1 confundió unidades con envases cerrados y necesitó una aclaración.
- **H4 (P3):** P1 dudó en el total del pedido con el envío y necesitó una ayuda.

**Es solo frontend y textos.** No cambia el cálculo (`total = envases × u + sueltos`, MATU-84 4.4), ni el contrato, ni la API, ni los datos. Ningún token nuevo. `Demo/DISENO.md` no cambia.

**Se construye en:** `web/src/familia/Insumos.tsx` (panel de «Me quedan» y campo de lo que queda del formulario), `textosInsumos.ts` (`EN_ENVASES` y la ayuda del modo sueltos), `Resumen.tsx` (`Boleta` y la bajada) y `textosPedido.ts`.

**Marcas:** **[L n]** ya está en `lenguaje.md`, sección n · **[NUEVO]** entra a `lenguaje.md` · **[CAMBIA]** reemplaza un texto aprobado. `{u}` son las unidades por envase.

---

## 0. Lo que vi funcionando (13-11, `npm run dev` en `web/`, doble del contrato)

Capturas con Chrome a 360 px (claro), 1280 px (oscuro), 1920 px (oscuro) y 320 px con el texto al 200 %, con `carmen@example.com` y `pedido@example.com`. Ninguna tiene desplazamiento horizontal (`scrollWidth` igual al ancho en los cuatro casos).

| Dónde | Lo que vi | Por qué confunde |
|---|---|---|
| «Me quedan», todos los insumos de Carmen | Ninguno tiene envase anotado, así que **todos abren en modo sueltos**: la pregunta, «Reemplaza lo que calculábamos. Si no queda nada, escribe 0.», el campo y, a 360 px, el sufijo «unidades» **baja de renglón** bajo el campo. «Contar en envases» queda debajo, como enlace | Frente a 2 paquetes cerrados y uno abierto, nada dice que el campo pide unidades y no paquetes. El único indicio, «unidades», queda separado del número. Escribir «2» o «3» es lo esperable. Es el error de P1 |
| Alta de un insumo, modo sueltos | La pregunta y el campo **sin ayuda**, con «unidades» y «Contar en envases» debajo | El mismo de arriba, en la anotación del consumo inicial |
| Modo envases (tras «Contar en envases») | «Envases enteros» y «Unidades sueltas», cada uno sin ayuda propia. El total en vivo funciona bien | «Enteros» no es la palabra de quien mira la repisa: ella dice «cerrados» (así lo anotó el moderador). Un paquete abierto pero casi lleno, ¿es entero? Y «sueltas» no dice si incluye las del paquete abierto |
| Pedido, borrador | «Productos: $42.140» y «El envío y el total los ves al confirmar que haya cada producto.» | — |
| Pedido, «Antes de pagar» | Arriba: «El total es $46.130.» A 360 px, la boleta («Productos (3) $42.140 · Envío (uno por pedido) $3.990 · Total $46.130») queda **varias pantallas más abajo**, después de los tres productos, la entrega y «Si falta» | La cifra sube $3.990 respecto del borrador y, donde se ve el salto, no se dice por qué. Nada dice que el IVA ya está dentro, así que cabe la duda de si se agregará después |

---

## 1. «Me quedan» y el campo de lo que queda (H1)

### 1.1 Objetivo y jerarquía

**Objetivo:** Carmen, mirando la repisa, sabe a la primera qué número va en cada campo: los paquetes que no ha abierto por un lado y lo suelto por otro.

1. La pregunta de siempre, «¿Cuántos quedan hoy, más o menos?» [L 18].
2. La ayuda, que ahora dice primero **qué se cuenta**.
3. Los campos, cada uno con una ayuda corta propia en modo envases.
4. El total en vivo y el botón de confirmar, sin cambios.

**Una sola acción principal**, sin cambios: «Anotar lo que queda» o «Guardar».

### 1.2 Decisiones para Jorge

| # | Qué | Propuesta | Por qué |
|---|---|---|---|
| D1 | El modo sueltos dice qué se cuenta | La ayuda empieza con «Cuenta unidades, no envases.» y nombra el enlace: «Si tienes envases cerrados, toca «Contar en envases».». También en el alta y la edición, que hoy no tienen ayuda en modo sueltos | Hoy quien no tiene el envase anotado (todos los insumos de la demo) ve un campo único sin aviso. La salida («Contar en envases») existe, pero nada la vincula con su situación |
| D2 | «Envases enteros» pasa a «Envases cerrados» | Etiqueta del contador, los nombres de «−» y «+» para el lector, y la ayuda del modo envases. **[CAMBIA]** L 30 | Es la palabra de la persona frente a la repisa y la del hallazgo. Además, evita el choque con «la lista sugiere envases enteros» (L 21), que habla de paquetes para comprar, no de lo que queda |
| D3 | Cada contador lleva una ayuda de una línea | «Envases cerrados»: «Los que todavía no abres.» · «Unidades sueltas»: «Las del envase abierto y las que están fuera de su envase.» | Resuelve los dos casos dudosos: el paquete abierto va a sueltos, y lo suelto incluye lo que queda en él |
| D4 | Sin ejemplo fijo bajo el campo | El total en vivo («En total, quedan unas 45 unidades.») ya es el ejemplo, con los números reales de la persona | Un ejemplo con cifras inventadas («2 envases de 20…») compite con el total real y alarga el panel, que a 360 px ya ocupa más de una pantalla |

**Si Jorge no aprueba D2**, D1 y D3 se aplican igual con «Envases enteros». La ayuda de ese contador sigue siendo «Los que todavía no abres.».

**Alternativa descartada, la de pedir el envase antes:** abrir siempre en modo envases y pedir de entrada cuántas unidades trae cada envase. Obliga a escribir un dato más a quien solo tiene sueltos, y deja sin efecto la decisión D6 de MATU-84 y el camino corto del alta.

### 1.3 Esquemas a 360 px

**Panel, modo sueltos (insumo sin envase):**

```
│ │ ¿Cuántos quedan hoy, más o     │ │  [L 18], font-bold
│ │ menos?                         │ │
│ │ Cuenta unidades, no envases.   │ │  ayuda text-base text-tenue  [CAMBIA]
│ │ Si tienes envases cerrados,    │ │
│ │ toca «Contar en envases».      │ │
│ │ Reemplaza lo que calculábamos. │ │
│ │ Si no queda nada, escribe 0.   │ │
│ │ [ − ] [     ] [ + ]            │ │  Stepper de hoy, foco en el campo
│ │ unidades                       │ │
│ │ Contar en envases              │ │  enlace de hoy, sin cambios
│ │ [ Anotar lo que queda ]        │ │
│ │ [ Volver ]                     │ │
```

**Panel, modo envases:**

```
│ │ ¿Cuántos quedan hoy, más o     │ │
│ │ menos?                         │ │
│ │ Cuenta los envases cerrados y, │ │  ayuda  [CAMBIA]
│ │ a ojo, lo suelto. Reemplaza lo │ │
│ │ que calculábamos.              │ │
│ │ (campo del envase si falta)    │ │  sin cambios (MATU-84 4.2)
│ │ Envases cerrados               │ │  etiqueta font-bold  [CAMBIA]
│ │ Los que todavía no abres.      │ │  ayuda text-base text-tenue  [NUEVO]
│ │ [ − ] [  2  ] [ + ]            │ │
│ │ envases de 20 unidades         │ │
│ │ Unidades sueltas               │ │  [L 30]
│ │ Las del envase abierto y las   │ │  ayuda text-base text-tenue  [NUEVO]
│ │ que están fuera de su envase.  │ │
│ │ [ − ] [  5  ] [ + ]            │ │
│ │ unidades                       │ │
│ │ En total, quedan unas 45       │ │  sin cambios
│ │ unidades.                      │ │
│ │ [ Anotar lo que queda ]        │ │
│ │ [ Volver ]                     │ │
│ │ Contar sueltos                 │ │
```

**Alta y edición:** igual al panel, sin «Reemplaza lo que calculábamos.» (como hoy en MATU-84 5.1). En la edición, la ayuda del modo sueltos va después de la de hoy [L 18].

### 1.4 Pantalla ancha (1280 y 1920 px)

Sin cambios de forma (MATU-84 4.3 y 5.3): todo de arriba abajo, los sufijos junto al campo. Cada ayuda de contador va **entre su etiqueta y su campo**, nunca a un lado, para que la etiqueta, la ayuda y el número se lean como una unidad.

### 1.5 Componentes y tokens (existentes)

| Parte | Cómo |
|---|---|
| Ayuda del bloque | La de hoy: `text-base text-tenue`, en el `aria-describedby` del campo único o de los dos contadores |
| Ayuda de cada contador | Un `p` `text-base text-tenue` entre la etiqueta y el `Stepper`, con `id` propio en el `aria-describedby` del campo de ese contador (no en los «−» y «+», que ya nombran su campo). Si `Stepper` ya acepta una ayuda, se usa esa prop y no se agrega otro elemento. Nunca `text-sm` |
| Lo demás | Sin cambios (MATU-84 6) |

**Prohibido:** un ícono de paquete o de caja junto a los contadores, un color para la ayuda (es texto, no un estado), una ilustración y valores escritos a mano.

### 1.6 Textos exactos

| Dónde | Texto | Marca |
|---|---|---|
| Panel, ayuda en modo sueltos, en unidades | Cuenta unidades, no envases. Si tienes envases cerrados, toca «Contar en envases». Reemplaza lo que calculábamos. Si no queda nada, escribe 0. | [CAMBIA] L 23 (agrega las dos primeras frases) |
| Panel, ayuda en modo sueltos, en sobres | Cuenta sobres, no envases. Si tienes envases cerrados, toca «Contar en envases». Reemplaza lo que calculábamos. Si no queda nada, escribe 0. | [CAMBIA] L 23 |
| Alta, ayuda en modo sueltos (hoy no hay) | Cuenta unidades, no envases. Si tienes envases cerrados, toca «Contar en envases». (o «Cuenta sobres, …») | [NUEVO] |
| Edición, ayuda en modo sueltos | La de hoy [L 18] + Cuenta unidades, no envases. Si tienes envases cerrados, toca «Contar en envases». | [L 18] + [NUEVO] |
| Panel, ayuda en modo envases | Cuenta los envases cerrados y, a ojo, lo suelto. Reemplaza lo que calculábamos. | [CAMBIA] L 30 |
| Alta y edición, ayuda en modo envases | Cuenta los envases cerrados y, a ojo, lo suelto. | [CAMBIA] L 30 |
| Primer contador | Envases cerrados | [CAMBIA] L 30 |
| Ayuda del primer contador | Los que todavía no abres. | [NUEVO] |
| Segundo contador | Unidades sueltas · Sobres sueltos | [L 30] |
| Ayuda del segundo contador, unidades | Las del envase abierto y las que están fuera de su envase. | [NUEVO] |
| Ayuda del segundo contador, sobres | Los del envase abierto y los que están fuera de su envase. | [NUEVO] |
| Botones − y + (lector) | Uno menos: Envases cerrados · Uno más: Envases cerrados | [CAMBIA] forma de MATU-36 |

**En ml y g:** sin cambios. No hay modo envases ni enlace (MATU-84 D2), así que la ayuda no nombra «Contar en envases».

**Sin cambios:** la pregunta, los sufijos, el total en vivo, la confirmación y todos los errores (MATU-84 7). Los errores van bajo el primer contador, como hoy, aunque cambie su nombre.

**Prohibido:** «stock», «inventario», «exacto», «paquete» (la app dice «envase» en todas partes, L 21 y L 30) y los términos de `lenguaje.md` 3.

### 1.7 Estados

Los de MATU-84 10, sin cambios: enviando, éxito, error, 412 y límites. Las ayudas nuevas se ven siempre, también con error. El error va debajo del campo y la ayuda queda arriba, entre la etiqueta y el campo.

---

## 2. El total del pedido con el envío (H4)

### 2.1 Objetivo y jerarquía

**Objetivo:** quien va a pagar entiende de una mirada por qué el total es mayor que «Productos» y que no se agregará nada después.

1. «Total» y su cifra, sin cambios (`text-2xl font-bold`).
2. **Debajo, la línea de ayuda nueva.**
3. «Este total vale hasta las…» y «Se cobra una sola vez este total…», sin cambios.

### 2.2 Decisiones para Jorge

| # | Qué | Propuesta | Por qué |
|---|---|---|---|
| D5 | Una línea bajo el total de la boleta | «Cada precio ya incluye el IVA. El envío es uno solo, por todo el pedido.» | Responde las dos dudas posibles: el IVA no se suma aparte y el envío no se cobra por producto. Está escrita en positivo y nunca presenta el IVA como algo que se suma |
| D5b | La bajada nombra el envío | «Confirmamos que hay cada producto. El total, con el envío, es $46.130.» **[CAMBIA]** L 31 | A 360 px la bajada es lo primero que se ve, y la boleta queda varias pantallas más abajo. Explica allí mismo el salto desde «Productos: $42.140» del borrador |

**Contradicción con `lenguaje.md` 31, que decide Jorge:** la regla de la sección dice que «"IVA" solo va en "Precio de ejemplo · IVA incluido" (sección 27)». La línea de D5 usa «IVA» en otro lugar. No contradice el fondo de la regla, porque no presenta el IVA como algo que se suma ni dice «con IVA», pero sí su letra. Hay dos caminos:
- **Si Jorge aprueba D5:** la regla de la sección 31 agrega «y en la línea bajo el total: «Cada precio ya incluye el IVA. …»».
- **Si no:** la línea queda sin la palabra: «Son los precios finales. El envío es uno solo, por todo el pedido.». Responde peor la duda del IVA, pero cumple la regla tal como está.

**No se toca:** la etiqueta «Envío (uno por pedido)» ni «Total», que nunca pasa a «Total con IVA». Tampoco se agrega una línea de IVA a la boleta (el IVA va incluido en cada precio y nunca se muestra como una suma).

### 2.3 Esquemas

**360 px, la boleta (`Boleta` de `Resumen.tsx`):**

```
┌──────────────────────────────────┐
│ ▤ Tu pedido                      │
│ Productos (3)          $42.140   │  text-lg
│ Envío (uno por pedido)  $3.990   │  text-lg
│ ──────────────────────────────── │  border-t-2 border-tinta
│ Total                  $46.130   │  text-2xl font-bold
│ Cada precio ya incluye el IVA.   │  text-base text-tenue  [NUEVO]
│ El envío es uno solo, por todo   │
│ el pedido.                       │
│ Este total vale hasta las 23:21. │  sin cambios
│ Se cobra una sola vez este       │  sin cambios
│ total, con crédito o con débito. │
│ No hay reserva ni cobros después.│
└╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┘
```

**360 px, arriba de la pantalla:**

```
│ Antes de pagar                   │  text-3xl
│ Confirmamos que hay cada         │  text-lg  [CAMBIA]
│ producto. El total, con el       │
│ envío, es $46.130.               │  la cifra en cifras font-bold
```

**1280 y 1920 px:** la boleta vive en la columna derecha fija (`2fr`, `sticky`). La línea nueva va igual, bajo el total, de ancho completo de la boleta, en renglones de hasta dos líneas. No se pone a un lado de la cifra.

**320 px con el texto al 200 %:** el renglón del total ya pasa a columna (`angosto:flex-col`). La línea nueva refluye sin cortar la cifra ni salirse de la boleta.

### 2.4 Componentes, tokens y textos

| Parte | Cómo |
|---|---|
| Línea bajo el total | `p` `text-base text-tenue`, dentro del `div` `flex flex-col gap-3` de la boleta, inmediatamente después del renglón «Total». Sin ícono y sin color de estado. Se ve con el total vigente y también vencido |
| Bajada | La de hoy (`text-lg`, la cifra en `cifras font-bold`), con el texto nuevo |

| Dónde | Texto | Marca |
|---|---|---|
| Bajo el total de la boleta | Cada precio ya incluye el IVA. El envío es uno solo, por todo el pedido. | [NUEVO] (D5) · sin IVA: Son los precios finales. El envío es uno solo, por todo el pedido. |
| Bajada de «Antes de pagar» | Confirmamos que hay cada producto. El total, con el envío, es {total}. | [CAMBIA] L 31 (D5b) |

**Aplica igual** al pagador (`pedido-pagador@example.com`), que ve la misma boleta. El comprobante del pago (MATU-62) no cambia: ya se pagó y lleva «Envío (uno por pedido)».

**Estados:** la línea depende solo de que exista la boleta (total confirmado o vencido). Con «Volver a confirmar» o el 412 del pedido no cambia. Sin carga ni error propios.

---

## 3. Accesibilidad visual

- **Contraste:** `tenue` sobre `hoja` mide 7,2:1 (claro) y 8,1:1 (oscuro), según DISENO.md y MATU-51 6. Todo el texto nuevo es `text-base` (17 px o más): sirve también en el proyector.
- **Áreas táctiles:** no se agregan controles. Las de hoy siguen en `min-h-12`.
- **Lectores:** cada ayuda de contador se anuncia con su campo, a través de `aria-describedby`. La línea de la boleta se lee en orden, después del total. Ninguna es región viva.
- **Estado nunca solo por color:** no hay estados nuevos.
- **Sin desplazamiento horizontal** a 320 px con el texto al 200 %. Hoy se cumple (medido el 13-11) y las líneas nuevas son texto que refluye.
- **`prefers-reduced-motion`:** nada se anima.

**Hallazgo aparte, fuera del alcance (P3, para que el orquestador decida si va aquí):** a 320 px con el texto al 200 %, el campo del envase (`w-32`, 16 rem efectivos) **se ve cortado por el borde derecho del `li`**. `scrollWidth` no lo detecta porque lo recorta la tarjeta. La corrección propuesta es `angosto:w-full` en `CampoEnvase`, con tokens existentes.

---

## 4. Criterios visuales verificables

1. En «Me quedan» de un insumo en unidades sin envase, la ayuda empieza con «Cuenta unidades, no envases.» y nombra «Contar en envases». En uno en sobres, empieza con «Cuenta sobres, no envases.».
2. En el alta, en modo sueltos y en unidades, bajo la pregunta se lee «Cuenta unidades, no envases. Si tienes envases cerrados, toca «Contar en envases».».
3. En ml o en g, la ayuda no menciona «Contar en envases».
4. En modo envases, el primer contador se llama «Envases cerrados» (o «Envases enteros» si Jorge no aprueba D2) y, entre la etiqueta y el campo, dice «Los que todavía no abres.».
5. El segundo contador dice, entre su etiqueta y su campo, «Las del envase abierto y las que están fuera de su envase.» (en sobres, «Los del envase abierto…»).
6. El lector anuncia cada ayuda de contador al enfocar su campo, y los «−» y «+» dicen «Uno más: Envases cerrados».
7. Con 2 envases cerrados de 20 y 5 sueltas, el total sigue en «En total, quedan unas 45 unidades.» y `recontar` recibe `{"stock_unidades": 45}`, igual que antes.
8. En «Antes de pagar», la bajada dice «… El total, con el envío, es $46.130.».
9. En la boleta, inmediatamente bajo «Total $46.130», se lee la línea de D5 en `text-base text-tenue`, y no hay ningún renglón que sume IVA.
10. «Anotar lo que queda», «Guardar» y «Pagar» siguen siendo el único `turquesa` macizo de su pantalla.
11. A 320 px con el texto al 200 %, en los dos temas, sin desplazamiento horizontal y sin texto cortado en el panel ni en la boleta.
12. Ninguna clase nueva lleva un valor escrito a mano.

---

## 5. Qué revisaré después de construir

Con el doble del contrato: `carmen@example.com` (panel en unidades y en sobres, «Contar en envases», el alta y la edición), un insumo con envase guardado si el doble lo trae, y `pedido@example.com` y `pedido-pagador@example.com` (la boleta vigente y vencida). Capturas a 360, 1280 y 1920 px en claro y oscuro, y a 320 px con el texto al 200 %, más el orden del `Tab` y lo que anuncia el lector en los dos contadores.

---

## 6. Para el orquestador

- **Sin cambios de API, contrato, base ni cálculo.**
- **Textos para `lenguaje.md`:** una sección nueva, «36. MATU-109», con los [NUEVO] y [CAMBIA] de 1.6 y 2.4. Los [CAMBIA] tocan las secciones 23, 30 y 31, y la regla de la 31 si se aprueba D5.
- **Contradicción con la regla de `lenguaje.md` 31** («IVA» solo en «Precio de ejemplo · IVA incluido»): decide Jorge (2.2). Hay una alternativa que cumple la regla tal como está.
- **Datos de la demo (no es de diseño):** en la demo de la ronda 2 ningún insumo tenía envase anotado, así que todas abrieron el modo sueltos. Si un insumo de la demo trae `unidades_por_envase`, «Me quedan» abre directo en envases. Es un cambio de datos sintéticos, que decide el orquestador.
- **MATU-84** queda con una nota que remite a esta especificación en 7 (los textos que cambian). La nota la agrego cuando Jorge apruebe.
