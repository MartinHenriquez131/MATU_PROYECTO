# MATU-107 · Correcciones del 12/11 · Especificación de diseño

**Versión 3 · 12/11/2026** · diseñador (agente 6). La versión 2 viene de la revisión visual y suma el `iconoEnLinea` de la nota G (2.2) y las secciones 4 y 5. La versión 3 suma la sección 6, que decidió el orquestador por delegación de Jorge. Puntos:

1. la barra inferior de la app de la familia (hallazgo 42-H2 de Martín, P3);
2. «Recibir avisos en este teléfono» cuando la cuenta no puede activarlos (C14, `permitido: false`);
4. las colas con «·» (54-H4);
5. la ayuda del límite de copias (54-H3);
6. la `Etiqueta` sin figura en el modo `angosto`.

Fuentes: `Demo/DISENO.md` (secciones 2, 3 y 4), `docs/diseno/matu-39-app-familia.md` (2.1), `docs/diseno/matu-55-donde-entraste.md` (3.4) y el contrato `docs/api/openapi.json` (`GET` y `PUT /v1/dispositivos/actual/push`).

---

## 1. La barra inferior del teléfono (42-H2)

### 1.1 Lo que se midió

Medido con la app funcionando (`npm run dev` de `web/`, cuenta `carmen@example.com`, `/grupo`, Chrome 360 × 760 y 320 × 760, temas claro y oscuro):

| Qué | Claro | Oscuro |
|---|---|---|
| Rótulo, tamaño calculado | 14,875 px (`telefono:text-sm`) | 14,875 px |
| «Grupo» activo: color calculado sobre fondo calculado | `rgb(8 103 100)` sobre `rocio` (`#e3eceb`): **5,57:1** | `rgb(82 204 195)` sobre `rocio` (`#1d3537`): **6,67:1** |
| Celda a 360 / 320 px | 85 / 75 px de ancho, 59,5 px de alto | igual |

**El 3,13:1 no se reproduce con los colores calculados.** El fondo `rocio` es un `color-mix` en `oklab`, y lo más probable es que la herramienta lo haya leído mal o haya tomado un píxel suavizado del borde de la letra de 14,9 px. No importa cuál de las dos fue: el arreglo de abajo deja el rótulo activo en `tinta` (más de 10:1), así que ninguna herramienta puede volver a marcarlo.

**El tamaño sí es un hallazgo real.** A 17 px, «Compartir» mide 76 px en regular y 81 px en negrita. Con los rellenos de hoy, la celda deja 77 px de texto a 360 px y 67 px a 320 px. Por eso la negrita del estado activo es lo que no cabe, más que el tamaño.

### 1.2 Decisión

- **El rótulo pasa a 17 px (`text-base`) en toda pantalla de 21 rem o más.** Son 357 px con el texto normal, así que cubre los 360 px de diseño y todo teléfono más ancho.
- **Bajo 21 rem queda en `text-sm`.** Son los teléfonos de 320 a 356 px, o uno de 360 px con el texto agrandado entre 101 % y 199 %. Con el texto agrandado, ese `text-sm` ya mide 16,4 px o más, porque escala con el `rem`. Con el texto al 200 %, la app pasa a `angosto` y la barra vuelve arriba en `text-base`, como hoy.
- **El estado activo deja la negrita y suma una forma.** El rótulo pasa a `tinta` en peso regular, y se agrega un indicador `turquesa` en el borde superior de la celda. La negrita era lo que no cabía (5 px más en «Compartir»), y el indicador es una señal de forma, más clara que un cambio de peso.
- **La barra lleva como máximo 4 secciones.** Con 5, cada celda mide 69 px a 360 px y «Compartir» no cabe ni en 15 px. Si alguna vez hace falta una quinta, se vuelve a especificar. Una pestaña «Más» queda descartada, porque agrega un paso.

**Lo que se descartó:**
- **17 px a 320 px.** «Compartir» deja 0,5 px por lado y se rompe con cualquier aumento del texto.
- **Partir el rótulo en dos líneas** («Compar-tir»). Cuesta más leerlo cansada y sin anteojos.
- **Cambiar «Compartir» por una palabra más corta.** El rótulo tiene que decir lo mismo que el título de la página. Además, el término es de lenguaje, y no es una decisión del diseñador.
- **Una barra de dos filas.** Ocuparía 120 px fijos de una pantalla de 760 px.

### 1.3 Variante nueva: `estrecho`

`estrecho` se activa cuando la pantalla mide menos de 40 rem y la app está entre 16 y 21 rem. Va en `web/src/index.css`, después de `telefono`. Ese archivo no está dentro de mi perímetro en esta tarea, así que lo pega el frontend tal cual:

```css
/*   estrecho  la barra inferior del teléfono no deja 17 px a «Compartir»: app entre 16 y 21 rem
 *             (320 a 356 px con el texto normal). Solo la usa el rótulo de la barra (MATU-107). */
@custom-variant estrecho {
  @media (width < 40rem) {
    @container app (16rem <= width < 21rem) {
      @slot;
    }
  }
}
```

No es un token de color, de tamaño ni de espacio. Es una condición de composición, igual que `angosto` y `telefono`, y queda justificada en `Demo/DISENO.md`, secciones 2 y 3.

### 1.4 Clases de la barra (`web/src/familia/Shell.tsx`, `Navegacion`)

| Parte | Hoy | Pasa a |
|---|---|---|
| `nav` (teléfono) | `telefono:px-1 telefono:py-1` | `telefono:px-1 telefono:py-1` (sin cambio) |
| `ul` (teléfono) | `telefono:gap-1` | `telefono:gap-0.5` |
| `a` (teléfono), tamaño | `telefono:text-sm` | **sin clase de tamaño** (hereda `text-base`) y `estrecho:text-sm` |
| `a` (teléfono), relleno | `telefono:px-1` | `telefono:px-0.5` y `relative` |
| `a` activo | `bg-hoja font-bold text-turquesa ring-1 ring-linea telefono:bg-rocio telefono:ring-0` | `bg-hoja font-bold text-turquesa ring-1 ring-linea telefono:bg-rocio telefono:font-normal telefono:text-tinta telefono:ring-0` |
| Ícono activo | `strokeWidth={2.4}`, color heredado | `strokeWidth={2.4}` y `text-turquesa` |
| Indicador (nuevo, solo activo y solo en el teléfono) | — | `<span aria-hidden className="hidden telefono:block absolute top-0 left-1/2 h-1 w-8 -translate-x-1/2 rounded-b-full bg-turquesa" />` como primer hijo del `a` |

**Tokens:** `tinta`, `turquesa`, `rocio`, `hoja` y `linea`. Las medidas `h-1` (0,25 rem), `w-8` (2 rem), `gap-0.5` y `px-0.5` son de la escala de Tailwind. No hay ningún valor escrito a mano.

**La vista ancha y el modo `angosto` no cambian.** La barra lateral sigue en `text-base`, con el activo en `turquesa` y negrita sobre `hoja` (6,7:1 en claro y 8,2:1 en oscuro).

**La prueba `web/pruebas/textoMinimo17.test.ts`.** La lista blanca cambia de `['telefono:text-sm']` a `['estrecho:text-sm']`. Es del frontend.

### 1.5 Esquema

```
360 px (21 rem o más): rótulos a 17 px
┌──────────────────────────────────────────────┐
│                                   ▔▔▔▔       │ ← indicador turquesa, 2 rem × 0,25 rem
│   [▤]       [▣]        [⋔]      ┌[👥]──┐     │
│  Ficha    Insumos   Compartir   │Grupo │     │ ← tinta regular; activo sobre rocio
└──────────────────────────────────────────────┘
320 px (bajo 21 rem): igual, rótulos en text-sm (14,9 px con el texto normal)
```

### 1.6 Contrastes (calculados con los tokens y verificados en Chrome)

| Elemento | Claro | Oscuro | Mínimo |
|---|---|---|---|
| Rótulo inactivo, `tinta` sobre `hoja` | 15,8:1 | 13,5:1 | 4,5:1 |
| Rótulo activo, `tinta` sobre `rocio` | 13,2:1 | 11,0:1 | 4,5:1 |
| Ícono e indicador activos, `turquesa` sobre `rocio` | 5,6:1 | 6,7:1 | 3:1 |
| Foco, `turquesa` de 3 px sobre `hoja` | 6,7:1 | 8,2:1 | 3:1 |

**El activo se reconoce sin color de cuatro maneras:** el indicador (una forma que solo tiene la sección activa), la píldora `rocio`, el trazo 2,4 del ícono y `aria-current="page"`.

### 1.7 Criterios verificables

1. A 360 px y a 390 px, con el texto normal, los cuatro rótulos miden 17 px y cada uno ocupa un solo renglón. «Compartir» no se parte.
2. A 320 px, los rótulos miden 14,875 px, ocupan un renglón y `document.documentElement.scrollWidth` es 320.
3. Con el texto al 200 % a 320 px, no hay barra fija. Las secciones van arriba en `text-base`, y el ancho de desplazamiento sigue en 320.
4. La sección activa es la única con el indicador `turquesa` arriba. Su rótulo está en `tinta`, en peso regular, y nada de la barra está en negrita en el teléfono.
5. El rótulo activo mide 4,5:1 o más en claro y en oscuro con cualquier herramienta. Con los tokens, mide 13,2:1 y 11,0:1.
6. Cada celda mide al menos 56 px de alto y 48 px de ancho, y el foco de 3 px se ve completo.
7. `textoMinimo17.test.ts` pasa con `estrecho:text-sm` como única excepción.

---

## 2. «Recibir avisos en este teléfono» sin permiso del piloto (C14)

Corrige `matu-55-donde-entraste.md`, 3.4. Se agrega el estado **G** y el 409 del `PUT`.

### 2.1 Objetivo

Que Carmen entienda que, en el piloto, su teléfono no recibe avisos por una regla del piloto y no porque su teléfono o su navegador fallen. Que no vea un botón que no sirve.

### 2.2 Estado G · «Solo el equipo de MATU, en el piloto»

| | |
|---|---|
| **Cuándo** | `GET /v1/dispositivos/actual/push` responde `permitido: false` |
| **Prioridad** | **Manda sobre todos los demás** (A a F). Con `permitido: false` no se mira el navegador, y nunca se dice «Este navegador no puede recibir avisos» ni el texto de F |
| **Qué se ve** | El `h3` del bloque («Este teléfono», «Este computador» o «Este navegador», según E1) y, debajo, `Nota tono="rocio" iconoEnLinea` con el ícono propio del tono. **(v2)** Con `iconoEnLinea`, como en el estado E: en el modo `angosto` el ícono va en la línea del texto. Sin él, a 320 px con el texto al 200 % el texto quedaba en una columna de unos 140 px, con una o dos palabras por renglón. **Sin `Etiqueta`** (ni «Sin activar» ni «Activados») y **sin el botón «Activar en este teléfono»** |
| **Texto exacto** | «En el piloto, los avisos en el teléfono solo se prueban en los teléfonos del equipo de MATU.» **[ANALISTA, aprobado]** |
| **E1** | El texto no cambia en un computador ni en otro navegador. Habla de la regla del piloto, no de este dispositivo |
| **Permiso del navegador** | Nunca se pide: no hay botón que lo pida |
| **La nota del piloto** | La nota `atenta` con «En el piloto los avisos se prueban sin enviarse: no te llegará nada.» sigue al final del bloque mientras `envio_simulado` sea `true`, porque vale también para el correo |
| **Las casillas** | «En tus teléfonos» y «Por correo» se pueden guardar igual. La preferencia es de la cuenta, no del teléfono |

**Caso borde: `permitido: false` con `registrado: true`.** Este teléfono quedó inscrito antes de la regla C14. Se ve la misma nota G, y debajo `Boton variante="secundario"` «Desactivar en este teléfono», con el flujo de desactivar de 3.4 tal como está. Al terminar, el `p role="status"` dice «Desactivaste los avisos en este teléfono.», queda solo la nota G y el foco pasa a la nota, que es `enfocable`. La persona siempre puede borrar lo que MATU guardó. Si el backend asegura que este caso no puede pasar, el botón sobra. Lo confirma el orquestador.

### 2.3 El `PUT` responde 409 `push-no-permitido`

Pasa si la regla cambió entre la lectura y el toque, por ejemplo si la pantalla quedó abierta desde antes.

| Momento | Qué se ve | Foco y anuncio |
|---|---|---|
| Activando | «Activando…» con `aria-busy`, como hoy | Se queda en el botón |
| 409 `push-no-permitido` | Igual que cuando falla el `PUT`, el frontend borra la suscripción del navegador para que no quede a medias. La pantalla **pasa al estado G**: desaparecen la etiqueta y el botón, y aparece la nota G. **No hay `MensajeError`**: la persona no hizo nada mal ni tiene que reintentar | El foco va a la nota G (`enfocable`, `tabIndex={-1}`) después de que React pinta, en un efecto (1.2 de MATU-55). Se anuncia una vez el texto de G por `role="status"`, no por `alert` |
| Otro error o sin red | Sin cambio: «No pudimos activar los avisos. Revisa tu conexión y vuelve a intentarlo.» | Sin cambio |

Si el navegador ya mostró su aviso de permiso y la persona dijo «Permitir», no se hace nada más con ese permiso.

### 2.4 Esquema a 360 px (estado G)

```
│ ☑ En tus teléfonos                    │
│ ┃ Este teléfono                        │ h3 text-lg font-bold
│ ┃ ┌──────────────────────────────────┐ │
│ ┃ │ ⓘ En el piloto, los avisos en el │ │ Nota tono="rocio", text-base
│ ┃ │   teléfono solo se prueban en los│ │
│ ┃ │   teléfonos del equipo de MATU.  │ │
│ ┃ └──────────────────────────────────┘ │
│ ☐ Por correo                           │
│ ⓘ En el piloto los avisos se prueban…  │ Nota tono="atenta" (sin cambio)
```

**Pantalla ancha:** la misma columna `max-w-xl` de «Tu cuenta», sin cambios.

### 2.5 Estados del bloque

| Estado | Comportamiento |
|---|---|
| Cargando | Sin cambio: «Cargando…» con `role="status"` |
| Error al leer | Sin cambio: la `Nota tono="pronto"` y «Volver a intentar» |
| Vacío | No aplica |
| Éxito | El estado G de 2.2 |
| Conflicto 409 | Lo de 2.3 |
| 412 | No aplica: el `PUT` no lleva versión |

### 2.6 Criterios verificables

1. Con `permitido: false`, el bloque «Este teléfono» no tiene ningún botón (salvo el caso borde de 2.2) ni ninguna `Etiqueta`, y no aparecen las palabras «Este navegador no puede recibir avisos» ni «Por ahora no se pueden activar».
2. El texto de la nota es exactamente «En el piloto, los avisos en el teléfono solo se prueban en los teléfonos del equipo de MATU.», en `text-base`, con `Nota tono="rocio"` y su ícono.
3. Al cargar «Tu cuenta» con `permitido: false`, el navegador no pide el permiso de avisos.
4. Si el `PUT` responde 409 `push-no-permitido`, no hay un `role="alert"`, el foco termina en la nota G y el navegador no conserva la suscripción.
5. A 320 px con el texto al 200 %, la nota no desborda: el ancho de desplazamiento sigue en 320.
6. La nota `atenta` del piloto sigue apareciendo una sola vez al final del bloque.

---

## 4. Las colas con «·» (54-H4)

**Lo que se vio (revisión del 12/11, `datos-admin` y `datos-pagador`).** En «Datos de María» hay 26 «·». En 25 de ellos, el espacio de antes es U+00A0 y el de después es normal. En el modo `angosto` (320 px con el texto al 200 %), varios terminan un renglón: «Anotó», «Llegó con…» y las líneas del historial («a las 18:12 ·⏎Carmen Soto»). «Cobrado · Devuelto» ya tiene U+00A0 a los dos lados, y por eso la cadena «$37.260 · Devuelto:» no se puede partir. A 320 px con el texto al 200 % no cabe en los 252 px de la columna, y `break-words` la corta en medio de la palabra: «Devu⏎elto». Es peor que el punto al final del renglón (**P2**).

**Decisión: una sola regla para toda cola con «·»** (montos, «Anotó», «Llegó con un pedido», «Si falta», historial y cuotas):

| Dónde | Cómo |
|---|---|
| **Fuera del modo `angosto`** | U+00A0 a los dos lados del «·». La cadena más larga que queda es una fecha o un monto más una palabra, y cabe en la columna más angosta sin `angosto` (252 px a 320 px). |
| **En el modo `angosto`** | El «·» y sus dos espacios van en un `span` con `angosto:hidden`, y la cola baja a su propio renglón con `angosto:block`. Ningún renglón empieza ni termina con el punto, y ninguna palabra se corta. |
| Siempre | Se mantiene `break-words` en el párrafo, como red. |

Forma, por ejemplo en el pago:

```tsx
<p className="text-base break-words">
  {T.cobrado}<span className="cifras">{pesos(pago.cobrado)}</span>
  <span className="angosto:hidden">{'\u00a0·\u00a0'}</span>
  <span className="angosto:block">{T.devuelto}<span className="cifras">{pesos(pago.devuelto)}.</span></span>
</p>
```

Para las colas que hoy son texto (`anoto`, `llegoConPedido`, `siFalta`, `cuotas` y la cola del historial), el «·» sale del texto y lo pone el componente, de la forma de arriba. El texto queda sin el punto ni los espacios («Anotó Carmen Soto»). Para el lector de pantalla, en `angosto` el renglón nuevo hace de pausa.

**Criterios:**
1. A 320 px con el texto al 200 %, en «Datos de María» y en «Tus datos», ningún renglón empieza ni termina con «·», y ninguna palabra queda cortada («Devu⏎elto»).
2. A 360 y 1280 px, todas las colas siguen en la misma línea que su dato, con «·» entre U+00A0.
3. El ancho de desplazamiento es igual al ancho de la pantalla en todos los casos.

**«· 3 cuotas» en «Tus datos».** Hoy se ve bien en todos los anchos: «4242 · 3 cuotas» es corto y no se corta. Igual pasa a la regla de arriba, para que todo funcione de la misma manera.

## 5. La ayuda del límite de copias (54-H3)

«Cada vez que abres esta pantalla cuenta como una copia de los datos. Puedes abrirla hasta 10 veces por hora.» va bajo la bajada, en `p text-base text-tenue max-w-prose mt-1.5`, igual que la bajada. **Queda así.**
- Es información de apoyo, constante, y no un estado. Por eso no va en una `Nota`, que se reserva para lo que cambia o pide atención.
- Se ve también cuando la página muestra el 429 («Abriste o descargaste los datos varias veces…»), donde más sirve.
- Medido: `tenue` sobre `papel` da 6,4:1 en claro, y en oscuro supera 7:1. Mide 17 px. A 320 px con el texto al 200 % no desborda.

## 6. La `Etiqueta` sin figura en el modo `angosto`

**Lo que se vio (segunda revisión, 12/11).** En «Datos de María», en la tarjeta del enlace de Pedro, a 320 px con el texto al 200 %, la etiqueta `atenta` corta la palabra: «Bloquead⏎o». El ícono le quita a la palabra el ancho que necesita (**P2**, viene de MATU-54).

**Decisión.** Es una regla general del componente `Etiqueta` (`web/src/familia/ui.tsx`). En el modo `angosto`, la etiqueta oculta su figura y deja solo la palabra.
- Ya se hacía en el estado del celular de «Tu cuenta», y desde ahora vale para todas.
- El estado sigue sin depender del color, porque la palabra queda siempre: toda `Etiqueta` lleva palabra.
- Fuera de `angosto` no cambia nada.

**Cómo:**

| Dónde | Cambio |
|---|---|
| `Etiqueta`, clase del `span` | Se agrega `angosto:[&>svg]:hidden`, que oculta todo ícono que sea hijo directo. Hoy, en las 25 etiquetas de `web/src`, el ícono es hijo directo |
| `Cuenta.tsx`, los dos íconos del estado del celular | Se quita su `angosto:hidden`, que ahora lo hace el componente |
| Una etiqueta futura | Su figura va como hijo directo (un `svg` de `lucide-react`). Si alguna vez tiene que ir envuelta, el envoltorio lleva `angosto:hidden` |

El `gap-1.5` puede quedar: sin el ícono no hay un segundo hijo y no deja espacio. Sin tokens nuevos.

**Criterios verificables:**
1. A 320 px con el texto al 200 %, en «Datos de María» (`datos-admin`, enlaces), la etiqueta dice «Bloqueado» completa en un renglón, sin ícono, en `atenta` sobre `atenta-fondo`.
2. A 320 px con el texto al 200 %, ninguna `Etiqueta` de «Datos de…», «Tus datos», «Dónde entraste», «Tu cuenta», «Compartir», «Insumos» y «Catálogo» muestra su ícono, y ninguna palabra de una etiqueta queda partida.
3. A 360, 1280 y 1920 px, todas las etiquetas siguen con su ícono, igual que antes.
4. El estado del celular de «Tu cuenta» se ve igual que antes en todos los anchos.
5. El ancho de desplazamiento es igual al ancho de la pantalla en todos los casos.

## 3. Para el orquestador

- **`web/src/index.css`.** Hay que agregar la variante `estrecho` (1.3). Queda fuera de lo que me autorizaste editar en esta tarea, así que va como bloque para el frontend. Si prefieres que la agregue yo, dímelo.
- **El caso borde de 2.2** (`permitido: false` con `registrado: true`). Hay que confirmar con el backend si puede pasar.
- **La revisión visual.** Hago la del punto 1 y la del punto 2 cuando el frontend termine, con capturas a 360, 1280 y 1920 px, en claro y en oscuro y con el texto al 200 %.
