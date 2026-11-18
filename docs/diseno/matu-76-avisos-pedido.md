# MATU-76 · Avisos de tus pedidos · Especificación de diseño

**Versión 1.0 · 18-11-2026 · agente 6 UI/UX.** Se escribió antes de construir.

**Las bases son estas:**
- las decisiones de Jorge D-76-1 a D-76-6 y las condiciones C14 a C16 de la revisión previa de MATU-76 (18-11);
- `Demo/DISENO.md`, con la regla de MATU-93: **ningún texto bajo 17 px (`text-base`)**, salvo el rótulo de la barra inferior;
- `docs/lenguaje.md`, secciones 17, 20, 33, 35 y 36;
- la especificación de MATU-55 v1.3 (`docs/diseno/matu-55-donde-entraste.md`, 3.3 y 3.4), que esta reutiliza sin cambiar su comportamiento;
- la de MATU-54 (`docs/diseno/matu-54-mis-datos.md`) para «Tus datos».

**Sin tokens nuevos ni componentes nuevos.** Todo se arma con `Nota`, `Etiqueta`, `Boton`, `MensajeError`, `Anunciado`, la casilla de DISENO 6 y las superficies que ya usan `Cuenta.tsx` y `TusDatos.tsx` (`bg-hoja rounded-xl ring-1 ring-linea`, `SUPERFICIE` y `Bloque`).

**Cómo se leen las marcas de los textos:**
- **[L 33]** y las demás: el texto ya está aprobado en esa sección de `lenguaje.md`.
- **[D-76-1]**: el texto ya lo aprobó Jorge con esa decisión, pero todavía no está en `lenguaje.md`.
- **[NUEVO]**: lo propone esta especificación y lo aprueba Jorge.
- **[AJUSTE]**: cambia un borrador del analista o un texto aprobado. Se explica por qué.

---

## 1. Para quién y qué

- **Carmen pagó el pedido de pañales de su mamá.** Quiere saber cuándo llega, y sobre todo si le devuelven plata. No quiere tres correos por cada pedido, y puede apagarlos.
- **Lo que no puede apagar es el correo sobre su dinero** (D-76-3): una devolución, un producto que faltó o una cancelación. La pantalla se lo dice **antes** de que lo apague, en una frase que se lee al lado de la casilla, y no con una casilla gris que parezca rota.
- **El aviso no cuenta nada en la pantalla bloqueada** (D-76-1): ni qué pedido, ni qué productos, ni cuánto. Es el mismo texto para todo lo que MATU avisa.
- **Solo le llega a quien pagó** (D-76-2). El bloque se ve en «Tu cuenta» de todas las cuentas, porque cualquiera puede pagar un pedido, y la ayuda dice «que pagaste» para que quien no paga entienda que no le aplica.

---

## 2. «Tu cuenta» (`/cuenta`): los avisos en tres tarjetas

### 2.1 Qué cambia y por qué

Hoy hay una sola tarjeta de avisos: el `fieldset` de los insumos, con «Este teléfono» metido bajo «En tus teléfonos» y la nota del piloto al final. Con un segundo tipo de aviso, «Este teléfono» deja de ser de los insumos: la inscripción del navegador es una sola y sirve para los dos tipos. Por eso se separa en su propia tarjeta.

| Tarjeta | Qué es | Origen |
|---|---|---|
| A | «Avisos cuando un insumo se está acabando»: el `fieldset` de hoy, **sin** «Este teléfono» y **sin** la nota del piloto | MATU-55, 3.3 |
| B | «Avisos de tus pedidos»: un `fieldset` nuevo, igual al A, con la nota fija del dinero bajo «Por correo» | Nueva (C14) |
| C | «Este teléfono»: el bloque `EsteTelefono` de hoy, en su propia tarjeta y con su `h2` | MATU-55, 3.4 |
| Nota | «En el piloto los avisos se prueban sin enviarse: no te llegará nada.» una sola vez, después de la última tarjeta de avisos | MATU-55, 3.3 |

**La regla E4 de MATU-55 se amplía:** la tarjeta C se ve si **al menos una** de las dos casillas «En tus teléfonos» (A o B) está marcada. Si las dos están desmarcadas, la tarjeta C se oculta (`hidden`) y la inscripción no se borra. Mientras la preferencia carga o falla, la tarjeta C no se muestra.

### 2.2 Jerarquía

1. **Primero**, los títulos de las dos tarjetas de preferencias, que dicen de qué es cada aviso.
2. **Segundo**, las casillas «Por correo» y «En tus teléfonos» de cada una, y la nota fija del dinero bajo «Por correo» de la B.
3. **Tercero**, «Este teléfono», con su estado (Activados o Sin activar) y su botón, y la nota del piloto.

**Ninguna de estas tarjetas tiene acción principal.** Las casillas se guardan solas y los botones son secundarios, como hoy. «Tu cuenta» sigue sin un botón en `pino` macizo.

### 2.3 Esquema a 360 px

```
┌────────────────────────────────────┐
│ … «Tu cuenta», «Dónde entraste» y  │  sin cambios
│   «Tus datos», como hoy            │
│                                    │
│ ┌────────────────────────────────┐ │  A · fieldset bg-hoja rounded-xl ring-1 ring-linea
│ │ Avisos cuando un insumo se     │ │  legend = h2 text-xl font-bold
│ │ está acabando                  │ │
│ │ Te avisamos cuando un insumo se│ │  text-base text-tenue
│ │ esté acabando. El aviso no dice│ │
│ │ cuál ni de quién.              │ │
│ │ Vale para todos tus grupos.    │ │  text-base font-bold
│ │ [✓] Por correo                 │ │  casilla size-6, etiqueta min-h-12
│ │ [✓] En tus teléfonos           │ │
│ │ Guardamos tus avisos.          │ │  role=status, solo en la tarjeta que se tocó
│ └────────────────────────────────┘ │
│                                    │  mt-6
│ ┌────────────────────────────────┐ │  B · fieldset, mismas clases que A
│ │ Avisos de tus pedidos          │ │  legend = h2 text-xl font-bold
│ │ Te avisamos cuando hay una     │ │  text-base text-tenue
│ │ novedad en un pedido que       │ │
│ │ pagaste. El aviso no dice qué  │ │
│ │ pedido ni qué productos.       │ │
│ │ Vale para todos tus grupos.    │ │  text-base font-bold
│ │ [ ] Por correo                 │ │  casilla
│ │     Si es sobre tu dinero, como│ │  nota fija · text-base text-tenue, ps-9
│ │     una devolución, un producto│ │  (alineada con el texto de la etiqueta)
│ │     que faltó o una cancelación│ │
│ │     el correo te llega igual.  │ │
│ │ [✓] En tus teléfonos           │ │  casilla
│ └────────────────────────────────┘ │
│                                    │  mt-6
│ ┌────────────────────────────────┐ │  C · section bg-hoja rounded-xl ring-1 ring-linea
│ │ Este teléfono                  │ │  h2 text-xl font-bold (antes h3 text-lg)
│ │ Aquí te llegan los avisos que  │ │  text-base text-tenue
│ │ marcaste «En tus teléfonos», si│ │
│ │ los activas.                   │ │
│ │ (✓ Activados)                  │ │  Etiqueta tono ok, como hoy
│ │ [ Desactivar en este teléfono ]│ │  Boton secundario, angosto:self-stretch
│ └────────────────────────────────┘ │
│                                    │  mt-6
│ ⓘ En el piloto los avisos se       │  Nota tono atenta con Info, max-w-xl
│   prueban sin enviarse: no te      │
│   llegará nada.                    │
│                                    │
│ Para cambiar tu nombre o tu correo…│  ComoPedir, sin cambios
└────────────────────────────────────┘
```

**En la tarjeta C desaparecen** el `border-l-4 border-linea` y la sangría `ps-4`: eran para colgar el bloque de la casilla, y ahora es una tarjeta propia. Adentro quedan el mismo `flex flex-col items-start gap-3`, los mismos estados A a G de MATU-55 (3.4) y MATU-107, y los mismos textos.

### 2.4 Pantalla ancha (1280 y 1920 px)

La misma columna de `max-w-xl`, alineada a la izquierda, con las tres tarjetas una bajo otra. **No van lado a lado:** con A y B en dos columnas, la nota del dinero quedaría en una columna más angosta que la del texto que explica, y la tarjeta C no sabría a cuál pertenece. Los botones de la tarjeta C no son de ancho completo (`self-start`), como hoy.

```
┌──────────────────────────────────────────────────────────────────┐
│ [barra]  Tu cuenta                                               │
│          ┌──────────────────────────────┐                        │
│          │ A · Avisos cuando un insumo  │                        │
│          │ se está acabando             │                        │
│          └──────────────────────────────┘                        │
│          ┌──────────────────────────────┐                        │
│          │ B · Avisos de tus pedidos    │   (espacio libre a la  │
│          │ [ ] Por correo               │    derecha, como hoy)  │
│          │     Si es sobre tu dinero…   │                        │
│          │ [✓] En tus teléfonos         │                        │
│          └──────────────────────────────┘                        │
│          ┌──────────────────────────────┐                        │
│          │ C · Este computador          │                        │
│          │ (✓ Activados)                │                        │
│          │ [ Desactivar en este         │                        │
│          │   computador ]               │                        │
│          └──────────────────────────────┘                        │
│          ⓘ En el piloto…                                         │
└──────────────────────────────────────────────────────────────────┘
```

En el modo `angosto`, las tres tarjetas pasan a `px-2`, la casilla alinea arriba (`angosto:items-start`, `angosto:mt-0.5`) y la nota del dinero mantiene `ps-9` (24 px de la casilla más 12 de `gap-3`).

### 2.5 La tarjeta B, parte por parte

Es un `fieldset` con la misma estructura que la A. Su `legend` lleva el estilo de un `h2`.

| Parte | Texto | Componente y tokens |
|---|---|---|
| Título (`legend`) | Avisos de tus pedidos **[NUEVO]** | `h2 text-xl font-bold leading-snug`, dentro del `legend pb-3` |
| Ayuda | Te avisamos cuando hay una novedad en un pedido que pagaste. El aviso no dice qué pedido ni qué productos. **[NUEVO]** | `p text-base text-tenue max-w-prose`, en el `aria-describedby` del `fieldset` |
| Alcance | Vale para todos tus grupos. **[L 33]** | `p text-base font-bold`, también en el `aria-describedby`. **Condición:** solo si la preferencia `pedido` es de la cuenta y no del grupo (C3 dice que es una preferencia por persona; el backend lo confirma en el contrato) |
| Casilla 1 | Por correo **[L 20]** | La casilla de DISENO 6: `size-6 accent-turquesa`, etiqueta `min-h-12 font-bold`, como en la A |
| Nota del dinero | Si es sobre tu dinero, como una devolución, un producto que faltó o una cancelación, el correo te llega igual. **[NUEVO]** | `p text-base text-tenue max-w-prose ps-9`, justo bajo la etiqueta de «Por correo», **siempre visible**, con la casilla marcada o no. La casilla la tiene en su `aria-describedby`, para que el lector de pantalla la lea al llegar a ella |
| Casilla 2 | En tus teléfonos **[L 33]** | Igual que la casilla 1 |
| Guardando, guardado y error | Guardando… · Guardamos tus avisos. · No pudimos guardar. Revisa tu conexión y vuelve a intentarlo. **[L 17] · [L 33]** | Los mismos de la A (MATU-55, 3.3), bajo las casillas de la B |

**Por qué una nota fija y no un interruptor deshabilitado.** Un tercer control «Correo sobre tu dinero» siempre marcado y gris se lee como un error o como algo que se puede activar en otro lado. La frase dice lo que pasa, con las palabras de Carmen, en el lugar donde toma la decisión. No lleva ícono ni color: es información, no un aviso, y se lee igual en los dos temas. Tampoco cambia al desmarcar: si apareciera recién al desmarcar, sonaría a reproche.

**Por qué «un producto que faltó» y no «faltante».** «Faltante» es la palabra del comercio. La sección 39 de `lenguaje.md` ya dice «Faltó un producto».

**Por qué nunca «te devolvimos».** El evento de la cancelación se emite aunque la devolución haya fallado (H3). La nota habla de «una devolución», sin decir que ya se hizo.

### 2.6 Estados de las tres tarjetas

Las dos preferencias llegan en el mismo `GET /v1/yo/avisos` y se guardan con el mismo `PUT`. Por eso los estados son comunes.

| Estado | Qué se ve |
|---|---|
| Cargando | A y B con su `legend`, su ayuda y su alcance, y en lugar de las casillas «Cargando…» **[L 26]** con `role="status"` (la misma espera de `useDemora`). La nota del dinero no se ve: va pegada a su casilla. La tarjeta C no se ve |
| Error al cargar o sin red | En A y en B, `Nota tono="pronto" rol="alert"` con «No pudimos traer tus avisos. Revisa tu conexión e inténtalo de nuevo.» **[L 33]** y «Volver a intentar» **[L 26]**, sin casillas. Cualquiera de los dos botones vuelve a pedir la lectura de las dos. Un solo anuncio para el lector de pantalla: la `Nota` de la A lleva `rol="alert"` y la de la B va sin `rol`, para que no se lea dos veces la misma frase. La tarjeta C no se ve |
| Listo | Las cuatro casillas con lo que dice el `GET`. Por omisión, la B viene marcada para quien pagó (C3). La pantalla no lo explica |
| Guardando | **Mientras se guarda una casilla, las cuatro quedan con `aria-disabled`**, no `disabled`, porque el `PUT` lleva las dos preferencias juntas. La que se tocó lleva `aria-busy`. «Guardando…» aparece solo en la tarjeta de la casilla que se tocó. Opacidad: `aria-disabled:not-focus-visible:opacity-60` (MATU-55 v1.3) |
| Guardado | «Guardamos tus avisos.» en la tarjeta de la casilla tocada. Se borra al tocar otra casilla, en cualquiera de las dos tarjetas, y al activar o desactivar en la C (regla P3 de MATU-55). El foco vuelve a la casilla después del render |
| Error al guardar | `MensajeError` bajo las casillas de esa tarjeta. La casilla vuelve a lo de antes y el foco se queda en ella |
| 412 | **No aplica.** `PUT /v1/yo/avisos` no lleva versión ni `If-Match`. Si el backend la agrega en MATU-76, se vuelve a especificar |
| 422 | Solo por un defecto. Se trata como el error al guardar |

**La tarjeta C** conserva todos sus estados (cargando, error, A a G) y sus textos, sin cambios. Solo cambian su contenedor, su título (de `h3 text-lg` a `h2 text-xl`) y su ayuda nueva.

### 2.7 La tarjeta C, lo que cambia

| Parte | Texto | Componente |
|---|---|---|
| Contenedor | — | `section aria-labelledby` con `max-w-xl rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea`, como las de «Dónde entraste» y «Tus datos» en `Cuenta.tsx` |
| Título | Este teléfono · Este computador · Este navegador **[L 33]** | `h2 text-xl font-bold leading-snug`. Mientras no se sabe la clase (E1), sin título, como hoy. El `aria-labelledby` va solo cuando el título está |
| Ayuda | Aquí te llegan los avisos que marcaste «En tus teléfonos», si los activas. **[NUEVO]** | `p text-base text-tenue max-w-prose`, bajo el título, en todos los estados salvo G (la cuenta fuera del equipo del piloto), donde la nota G ya lo dice todo. No usa el sustantivo, así que vale para teléfono, computador o navegador |
| Lo demás | Los estados A a G y sus textos | Sin cambios (MATU-55, 3.4, y MATU-107) |

---

## 3. El aviso en el teléfono (D-76-1 a, C15)

### 3.1 El texto

| Parte | Texto | Marca |
|---|---|---|
| Título | MATU | [L 20] |
| Cuerpo | Tienes una novedad. Abre la app para verla. | **[D-76-1]** |

Es el mismo para un insumo, un pedido o lo que MATU avise después. Lo pone `web/public/sw.js`, con `tag: 'matu-novedad'`, el ícono `/icono-192.png` y `lang: 'es-CL'`, como hoy. Tocarlo abre la app en su inicio, sin identificadores (sin cambios).

**Criterio de lectura.** En la pantalla bloqueada de un Android a 360 px, el título y el cuerpo entran en dos líneas sin cortarse con «…». Lo verifica Martín en su teléfono, porque el envío es simulado y no se puede capturar en la demo.

### 3.2 Qué cambia en la pantalla

**Nada que se vea.** Revisé «Tu cuenta», «Dónde entraste» y «Tus datos»: ningún texto en pantalla repite el cuerpo viejo («Un insumo se está acabando. Abre la app para ver cuál.»). La ayuda de la tarjeta A («El aviso no dice cuál ni de quién.») sigue siendo cierta con el texto genérico y no cambia. El estado B de la tarjeta C habla de la dirección de avisos, no del texto, y tampoco cambia.

**Lo que sí dice el texto viejo, fuera de la pantalla:**
- `web/public/sw.js`, el cuerpo, el `tag` y el comentario de la cabecera (C15, frontend);
- el comentario de la cabecera de `web/src/familia/AvisosCuenta.tsx`, que habla solo de los insumos (frontend);
- `lenguaje.md`, la fila «Push, título y cuerpo» de la 20, la fila «Aviso push (MATU-41)» de la 13.3 y la fila «Aviso por push o correo» de la 36, que mezcla el push con el correo del pedido (documentos);
- la política, §6 (analista).

---

## 4. «Tus datos» (`/cuenta/datos`)

### 4.1 «Tus avisos»: las dos preferencias (C11)

Hoy es un `dl` con dos filas. Pasa a dos grupos, cada uno con su `h3`, dentro del mismo `Bloque`.

```
360 px
┌────────────────────────────────────┐
│ Tus avisos                         │  h2 del Bloque, sin cambios
│ Cuando un insumo se está acabando  │  h3 text-lg font-bold
│ ┌────────────────────────────────┐ │  SUPERFICIE (dl)
│ │ Por correo                     │ │  dt text-base text-tenue
│ │ Sí                             │ │  dd font-bold
│ │ ────────────────────────────── │ │  divide-linea
│ │ En tus teléfonos               │ │
│ │ Sí                             │ │
│ └────────────────────────────────┘ │
│ De tus pedidos                     │  h3 text-lg font-bold
│ ┌────────────────────────────────┐ │  SUPERFICIE (dl)
│ │ Por correo                     │ │
│ │ No                             │ │
│ │ ────────────────────────────── │ │
│ │ En tus teléfonos               │ │
│ │ Sí                             │ │
│ └────────────────────────────────┘ │
│ El correo sobre tu dinero te llega │  p text-base text-tenue, solo si «Por correo»
│ igual.                             │  de pedidos es No
│ Puedes cambiarlos en Tu cuenta.    │  sin cambios
└────────────────────────────────────┘
```

| Parte | Texto | Marca |
|---|---|---|
| Grupo 1 | Cuando un insumo se está acabando | **[NUEVO]**, del título de L 20 |
| Grupo 2 | De tus pedidos | **[NUEVO]** |
| Rótulos y valores | Por correo · En tus teléfonos · Sí · No | [L 35] |
| Dinero | El correo sobre tu dinero te llega igual. | **[NUEVO]**. Solo con «Por correo» de pedidos en No, porque «No» sin más sería falso para esos correos |
| Al pie | Puedes cambiarlos en Tu cuenta. | [L 35] |

En pantalla ancha es la misma columna. El «Sí» y el «No» son palabras, nunca un ícono o un color solos.

### 4.2 «Avisos que te enviamos»: el tipo de cada aviso (D-76-6)

Cada línea suma el tipo, **antes** del canal:

```
⟳ 18/11/2026 a las 09:00 · Aviso de pedido · Por correo · En el piloto no salió
✓ 17/11/2026 a las 09:00 · Aviso de insumo · En tus teléfonos · Salió
```

| Parte | Texto | Marca |
|---|---|---|
| La línea | {fecha} a las {hora} · {tipo} · {canal} · {resultado} | **[AJUSTE]** de [L 35]: suma el tipo |
| El tipo | Aviso de insumo · Aviso de pedido | **[NUEVO]**. «Aviso de» y no solo «Insumo», porque en medio de la línea «Pedido» se confunde con un pedido |
| Tipo desconocido | Se omite esa parte de la línea, como con un canal desconocido | — |

- Usa la misma `Cola` y el mismo `break-words` de hoy: a 320 px con el texto al 200 %, la línea se parte entre palabras y no se sale.
- **El ícono sigue diciendo el resultado**, no el tipo. El tipo va solo en palabra.
- **Depende del contrato:** `AvisoEnviadoCopia` necesita un campo con el tipo cerrado (`insumo` o `pedido`). Hoy no lo tiene. Es del backend (C11).
- «Datos de» la persona no lista los avisos del pedido de una cuenta (C12): no cambia.

---

## 5. Accesibilidad

| Regla | Cómo se cumple |
|---|---|
| Áreas de 48 px | Cada etiqueta de casilla tiene `min-h-12` y es toda tocable. Los botones de la tarjeta C usan `Boton`, de 48 px. La nota del dinero no es tocable |
| Foco visible | El anillo del tema en las casillas y en los botones. Mientras espera, la casilla con foco no pierde opacidad (`not-focus-visible`) |
| Estado nunca solo por color | La casilla marcada lleva su tilde. «Activados» y «Sin activar» van con palabra e ícono. En «Tus datos», «Sí» y «No». La nota del dinero es texto |
| Nombres accesibles | Cada `fieldset` tiene su `legend`. Las dos casillas «Por correo» se distinguen por su grupo. La de pedidos tiene la nota del dinero en su `aria-describedby` |
| Un solo anuncio | Guardar, guardado y error se anuncian una vez, en la tarjeta tocada. El error de carga se anuncia una vez (2.6) |
| Sin desplazamiento horizontal | A 320 px con el texto al 200 % (`angosto`), las tarjetas pasan a `px-2`, las etiquetas se parten y la nota del dinero mantiene `ps-9` |
| 17 px | Todos los textos en `text-base` o más. Los `h3` de «Tus datos» en `text-lg` |
| Movimiento | Mostrar y ocultar la tarjeta C es inmediato, sin transición |

---

## 6. Criterios visuales verificables

1. En «Tu cuenta», los avisos son **tres tarjetas** en este orden, con `mt-6` entre ellas: A «Avisos cuando un insumo se está acabando», B «Avisos de tus pedidos» y C «Este teléfono» (o «computador» o «navegador»), y después **una sola** nota del piloto.
2. La tarjeta A ya no contiene «Este teléfono» ni la nota del piloto.
3. Las tarjetas A, B y C tienen la misma superficie: `bg-hoja`, `rounded-xl`, `ring-1 ring-linea`, `px-4 py-4` y `max-w-xl`.
4. El título de las tres es `h2` en `text-xl font-bold`. En C ya no hay `border-l-4` ni sangría `ps-4`.
5. Bajo «Por correo» de la tarjeta B se lee la nota del dinero en `text-tenue`, alineada con el texto de la etiqueta (no con la casilla), con la casilla marcada **y** desmarcada.
6. La nota del dinero no lleva ícono, ni borde, ni fondo, ni color propio.
7. No hay ninguna casilla, interruptor ni control deshabilitado para el correo del dinero.
8. Con las dos «En tus teléfonos» desmarcadas, la tarjeta C no se ve. Con una sola marcada, se ve.
9. Al tocar una casilla de la B, «Guardando…» y «Guardamos tus avisos.» aparecen en la B, y no en la A.
10. Mientras se guarda, las cuatro casillas se ven al 60 % salvo la que tiene el foco, cuyo anillo se ve entero.
11. Cada área de casilla mide al menos 48 px de alto, medida en la etiqueta.
12. A 320 px con el texto al 200 %, no hay desplazamiento horizontal en «Tu cuenta» ni en «Tus datos», y la nota del dinero no se sale de la tarjeta.
13. En los dos temas, la nota del dinero y la ayuda de C tienen al menos 4,5:1 sobre `hoja` (`tenue` ya lo cumple; se mide en la captura).
14. «Tu cuenta» no tiene ningún botón en `pino` macizo.
15. En «Tus datos», «Tus avisos» tiene dos grupos con `h3` y la frase del dinero solo cuando «Por correo» de pedidos es «No».
16. En «Avisos que te enviamos», cada línea dice «Aviso de insumo» o «Aviso de pedido» antes del canal.
17. Ningún texto de estas pantallas nombra el código de retiro, el comercio ni la referencia del pedido (C16), ni dice «te devolvimos».

---

## 7. Lo que necesita del contrato y de otros

| Qué | De quién |
|---|---|
| La preferencia `pedido` (correo y push) en `GET` y `PUT /v1/yo/avisos`, con nombre exacto en el OpenAPI | Backend (C3) |
| Confirmar que la preferencia `pedido` vale para todos los grupos de la cuenta, para usar «Vale para todos tus grupos.» | Backend (C3) |
| El tipo cerrado (`insumo` o `pedido`) en `AvisoEnviadoCopia`, y la preferencia `pedido` en `preferencia_avisos` de la copia | Backend (C11) |
| `sw.js` con el cuerpo genérico y `tag: 'matu-novedad'` | Frontend (C15) |
| Las filas de `lenguaje.md` (13.3, 20, 33, 35, 36 y una sección nueva) | Documentos, con Jorge |

---

## 8. Textos para `lenguaje.md`

| Dónde | Texto | Marca |
|---|---|---|
| Push, título y cuerpo | MATU · Tienes una novedad. Abre la app para verla. | [D-76-1] |
| «Tu cuenta», título B | Avisos de tus pedidos | **[NUEVO]** |
| «Tu cuenta», ayuda B | Te avisamos cuando hay una novedad en un pedido que pagaste. El aviso no dice qué pedido ni qué productos. | **[NUEVO]** |
| «Tu cuenta», alcance B | Vale para todos tus grupos. | [L 33] |
| «Tu cuenta», casillas B | Por correo · En tus teléfonos | [L 20] · [L 33] |
| «Tu cuenta», nota del dinero | Si es sobre tu dinero, como una devolución, un producto que faltó o una cancelación, el correo te llega igual. | **[NUEVO]** |
| «Tu cuenta», ayuda de «Este teléfono» | Aquí te llegan los avisos que marcaste «En tus teléfonos», si los activas. | **[NUEVO]** |
| «Tus datos», grupos | Cuando un insumo se está acabando · De tus pedidos | **[NUEVO]** |
| «Tus datos», dinero | El correo sobre tu dinero te llega igual. | **[NUEVO]** |
| «Tus datos», la línea de un aviso | {fecha} a las {hora} · {tipo} · {canal} · {resultado} | **[AJUSTE]** de L 35 |
| «Tus datos», el tipo | Aviso de insumo · Aviso de pedido | **[NUEVO]** |

**Revisión de los borradores del correo** (no son de una pantalla, pero tienen que decir lo mismo que la nota del dinero, C7):

| Dónde | Borrador del analista | Propuesta | Por qué |
|---|---|---|---|
| Asunto | MATU: hay una novedad en un pedido | Sin cambios | — |
| Cuerpo y enlace | Hay una novedad en un pedido. Abre la app para verla. · Abrir MATU | Sin cambios | — |
| Pie, aviso que se puede apagar | Te llega este correo porque pagaste un pedido en MATU. Para dejar de recibir estos avisos por correo, entra a MATU y desactívalos en Tu cuenta. | Sin cambios | Ya dice dónde y con las mismas palabras de la pantalla |
| Pie, aviso de dinero | Te llega este correo porque pagaste un pedido en MATU y es sobre tu dinero. | Te llega este correo porque pagaste un pedido en MATU. Como es sobre tu dinero, te llega aunque hayas desactivado los avisos por correo. **[AJUSTE]** | Quien apagó los correos y recibe uno tiene que entender por qué, sin pensar que la casilla no funcionó. Dice lo mismo que la nota de «Tu cuenta» |

**Ninguno usa** los términos de la sección 3, «faltante», «notificación», «evento», «preferencia», «token», «rechazado» ni «fallido».

---

## 9. Cómo la voy a revisar

- La demo de `web/` levantada, con una cuenta sintética (Carmen) que pagó un pedido y otra (Rodrigo) que no pagó.
- Capturas de «Tu cuenta» y «Tus datos» a 360, 1280 y 1920 px, en tema claro y oscuro, y una a 360 px con el texto al 200 %.
- Los estados: cargando, error de carga, guardando, guardado, error al guardar, las dos «En tus teléfonos» desmarcadas y una sola marcada.
- El recorrido con teclado: el orden del foco por las cuatro casillas y la tarjeta C, y el foco que vuelve a la casilla al guardar.
- Los 17 criterios de la sección 6, uno por uno.
