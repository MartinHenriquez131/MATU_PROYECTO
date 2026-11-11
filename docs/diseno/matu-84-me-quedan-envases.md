# MATU-84 · «Me quedan» y el alta del insumo, también en envases · Especificación de diseño

**Versión 1.0 · 10/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Viene de:** el hallazgo U3 (P2) de la ronda 1 de usabilidad (`docs/usabilidad/ronda-1-informe.md` del repositorio MATU). A quien controla lo que queda mirando la repisa le cuesta contar unidades sueltas: «tenemos todo guardado en una repisa y ahí vamos revisando».

**Decisión de Jorge del 10-11:** es solo frontend. La API sigue recibiendo unidades (`stock_unidades` en `SolicitudRecuento` y `SolicitudEdicionPerfil`, de 0 a 100.000). Si el insumo tiene `unidades_por_envase`, «Me quedan» y el campo de lo que queda del alta y de la edición aceptan **envases enteros más unos sueltos**, y la pantalla manda `envases × unidades_por_envase + sueltos`. Si no tiene envase, se ofrece anotarlo ahí mismo. Se mantiene el «más o menos».

**Dónde se construye:** `web/src/familia/Insumos.tsx` (el panel de «Me quedan» de `Fila` y el campo de lo que queda de `Formulario`), con textos en `textosInsumos.ts` y `textos.ts`. No hay pantalla, ruta ni endpoint nuevos.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` (**ningún token nuevo**) · la decisión de Jorge del 10-11 · `docs/lenguaje.md` del repositorio MATU, secciones 2, 3, 18, 21 y 23 · las especificaciones de MATU-51 (el patrón de «Compré» con envase, que esta copia), MATU-60 sección 9 (el campo del envase) y MATU-36 (el formulario y el `Stepper`) · el contrato `docs/api/README.md`, decisiones 41, 121 y 139.

**Marcas de los textos:** **[L n]** ya está en `lenguaje.md`, sección n · **[PROPUESTO]** nuevo, lo aprueba Jorge y entra a `lenguaje.md` · **[CAMBIA]** reemplaza algo ya especificado o aprobado. `{nombre}` es el nombre del insumo, `{u}` las unidades por envase, `{n}` una cantidad con punto de miles desde 1.000.

---

## 0. Lo que Jorge tiene que ver

| # | Qué | Propuesta | Por qué |
|---|---|---|---|
| D1 | El resultado en vivo no nombra el producto | «En total, quedan unas 65 unidades.» en vez de «Quedan unas 65 toallitas». | La pantalla no sabe el plural ni el género de un nombre libre («Pañal adulto M», «Crema protectora»). «unidades» y «sobres» son los sufijos aprobados [L 18] y la fila de Insumos ya los usa |
| D2 | ml y g quedan fuera | En insumos que se cuentan en ml o g, «Me quedan» y el formulario siguen como hoy, en la unidad, sin «Contar en envases» | Ver la sección 9 |
| D3 | En el formulario, el campo del envase se mueve cuando se cuenta en envases | Con «Contar en envases», «¿Cuántas unidades trae cada envase?» sube al bloque de lo que queda. Al volver a «Contar sueltos», regresa al final con su valor. **[CAMBIA]** MATU-60 9.1, que lo deja siempre al final | No se puede contar en envases sin saber cuánto trae cada uno, y ese dato tiene que estar a la vista donde se usa. El camino corto del alta no cambia: quien no toca «Contar en envases» ve el formulario de hoy |
| D4 | «Me quedan» con envase conocido abre sin teclado | El foco va al panel, no al campo, como «Compré» con envase. **[CAMBIA]** MATU-51 4, que lleva el foco al campo | Con envases se cuenta con «+» y «−». El teclado del teléfono taparía los dos campos y el botón |
| D5 | Anotar el envase desde «Me quedan» | Si se anota el envase en el panel, se guarda con lo que queda en **una sola petición** (`PATCH`, ver 4.4) | Las dos cosas se guardan juntas o ninguna. No queda un envase guardado con lo que queda sin guardar |
| D6 | Un envase de 1 unidad | Se trata como si no tuviera envase | «1 envase de 1 unidad y 5 sueltas» no ayuda a nadie |

**Contradicción que informo al orquestador:** MATU-51 3.5 dice «Siempre en la unidad del insumo, aunque tenga envase (decisión de Jorge)». La decisión de Jorge del 10-11 la reemplaza. Hay que actualizar esa línea de MATU-51 en el mismo pull request, o anotar que MATU-84 la reemplaza.

---

## 1. Para quién y qué

**Carmen** está frente a la repisa con el teléfono en una mano. Ve dos paquetes de toallitas cerrados y uno abierto. Toca «Me quedan». El panel ya pregunta por envases: toca «+» dos veces en «Envases enteros», calcula a ojo que en el abierto quedan unas 5, las escribe o toca «+» cinco veces, y lee «En total, quedan unas 45 unidades». Toca «Anotar lo que queda». No tuvo que multiplicar.

**Si el insumo no tiene envase anotado,** Carmen ve el campo de hoy y, debajo, «Contar en envases». Lo toca, escribe una vez que cada paquete trae 20, y cuenta igual que arriba. MATU guarda el envase para la próxima vez y para la lista de insumos.

**Lo que nunca hace esta pantalla:** pedir exactitud, mostrar precios u ofrecer comprar, guardar los envases y los sueltos por separado (la API guarda unidades), ni calcular días o fechas (salen de la respuesta).

---

## 2. Objetivo y jerarquía

**Objetivo:** Carmen anota lo que queda contando paquetes, como lo ve en la repisa, y MATU hace la cuenta.

**Jerarquía del panel y del bloque, con envases:**

1. La pregunta de siempre, «¿Cuántos quedan hoy, más o menos?» [L 18].
2. Los dos campos, «Envases enteros» y los sueltos, uno debajo del otro.
3. El resultado, «En total, quedan unas 45 unidades.», que confirma la cuenta antes de guardar.
4. El botón de confirmar y, más abajo y en menor peso, «Contar sueltos».

**Una sola acción principal:** «Anotar lo que queda» en el panel y «Guardar» en el formulario siguen siendo el único `turquesa` macizo. «Contar en envases» y «Contar sueltos» son enlaces de texto, nunca botones macizos ni secundarios.

---

## 3. Los dos modos del campo de lo que queda

El mismo campo tiene dos modos. Los dos existen en el panel «Me quedan» y en el formulario.

| Modo | Cuándo abre así | Qué muestra |
|---|---|---|
| **Sueltos** | El insumo no tiene `unidades_por_envase`, o tiene 1 (D6). Siempre en ml y g (D2) | El `Stepper` de hoy, en la unidad del insumo, y debajo el enlace «Contar en envases» (no en ml ni g) |
| **Envases** | El insumo tiene `unidades_por_envase` mayor que 1, o la persona tocó «Contar en envases» | Dos `Stepper` («Envases enteros» y los sueltos), el resultado y el enlace «Contar sueltos». Si el envase no estaba anotado, también el campo «¿Cuántas unidades trae cada envase?» |

**Cambiar de modo nunca pierde lo escrito:**

- **De sueltos a envases:** si había un número y el envase ya se conoce, se reparte: envases = número dividido por `{u}`, entero hacia abajo, y sueltos = lo que sobra. 65 con envases de 20 son 3 envases y 5 sueltos. Si el envase todavía no se conoce, el número pasa entero a sueltos y «Envases enteros» queda vacío.
- **De envases a sueltos:** el campo único recibe el total. Si los dos estaban vacíos, queda vacío.
- **El modo se cambia solo con los enlaces.** Escribir el envase al final del formulario no cambia el modo del bloque de arriba, porque mover un campo que no se está tocando desorienta.
- El modo no se recuerda: cada vez que se abre el panel o el formulario, se elige con la tabla de arriba.

---

## 4. Panel «Me quedan» (fila de Insumos)

Mismo lugar, misma forma y mismas reglas que MATU-51 3.5 y 3.6: dentro del `li`, uno abierto a la vez, «Volver» y `Escape` cierran y devuelven el foco a «Me quedan».

### 4.1 Con envase conocido, a 360 px

```
│ │ Usa 4 al día. Quedaban 24 el   │ │
│ │ 04/11/2026.                    │ │
│ │ ────────────────────────────── │ │  border-t border-linea
│ │ ¿Cuántos quedan hoy, más o     │ │  etiqueta del grupo, font-bold [L 18]
│ │ menos?                         │ │
│ │ Cuenta los envases enteros y,  │ │  ayuda text-base text-tenue
│ │ a ojo, lo suelto. Reemplaza lo │ │
│ │ que calculábamos.              │ │
│ │                                │ │
│ │ Envases enteros                │ │  Stepper, etiqueta font-bold
│ │ [ − ] [  2  ] [ + ]            │ │  vacío al abrir
│ │ envases de 20 unidades         │ │  sufijo, baja de renglón solo
│ │                                │ │
│ │ Unidades sueltas               │ │  Stepper («Sobres sueltos» en sobres)
│ │ [ − ] [  5  ] [ + ]  unidades  │ │  vacío al abrir
│ │                                │ │
│ │ En total, quedan unas 45       │ │  resultado, text-base font-bold, cifra en cifras
│ │ unidades.                      │ │
│ │                                │ │
│ │ [ Anotar lo que queda ]        │ │  principal
│ │ [ Volver ]                     │ │  secundario
│ │ Contar sueltos                 │ │  enlace de texto, min-h-12
│ │ ────────────────────────────── │ │
│ │ [x] Seguir  [ Cambiar ]   (pap)│ │
```

- **Los dos campos abren vacíos,** como «Me quedan» hoy (MATU-51 3.5): un número precargado invita a confirmar sin contar.
- **Un campo vacío vale 0 si el otro tiene número.** «2 envases» y sueltos vacío son 40. Solo es error si los dos están vacíos.
- **«−» con el campo vacío deja 0,** como el `Stepper` con `min={0}`. Así «no queda nada» son dos toques: «−» en los dos, o uno, si el otro sigue vacío.
- **El resultado** aparece apenas uno de los dos tiene número, y cambia con cada toque. Los textos están en la sección 7.
- **«Contar sueltos» va bajo «Volver»,** no a su lado, para que no compita con las dos acciones del panel y no se toque por error con el pulgar.

### 4.2 Sin envase, a 360 px

```
│ │ ¿Cuántos quedan hoy, más o     │ │  [L 18]
│ │ menos?                         │ │
│ │ Reemplaza lo que calculábamos. │ │  ayuda [L 23]
│ │ Si no queda nada, escribe 0.   │ │
│ │ [ − ] [     ] [ + ]  unidades  │ │  el Stepper de hoy, foco en el campo
│ │ Contar en envases              │ │  enlace de texto, min-h-12
│ │                                │ │
│ │ [ Anotar lo que queda ]        │ │
│ │ [ Volver ]                     │ │
```

Al tocar «Contar en envases»:

```
│ │ ¿Cuántos quedan hoy, más o     │ │
│ │ menos?                         │ │
│ │ Cuenta los envases enteros y,  │ │
│ │ a ojo, lo suelto. Reemplaza lo │ │
│ │ que calculábamos.              │ │
│ │                                │ │
│ │ ¿Cuántas unidades trae cada    │ │  CampoEnvase de MATU-60 9.2, foco aquí
│ │ envase?                        │ │
│ │ Lo guardamos para la próxima   │ │  ayuda nueva (sección 7)
│ │ vez y para la lista.           │ │
│ │ ┌──────────┐                   │ │
│ │ │ 20       │ unidades          │ │  sin − ni +, como en MATU-60
│ │ └──────────┘                   │ │
│ │                                │ │
│ │ Envases enteros                │ │
│ │ [ − ] [     ] [ + ]            │ │
│ │ envases de 20 unidades         │ │  mientras el envase no es válido: «envases»
│ │ Unidades sueltas               │ │
│ │ [ − ] [  5  ] [ + ]  unidades  │ │  recibe lo que estaba en el campo único
│ │ En total, quedan unas 5        │ │
│ │ unidades.                      │ │
│ │ [ Anotar lo que queda ]        │ │
│ │ [ Volver ]                     │ │
│ │ Contar sueltos                 │ │  descarta el envase escrito, que no se guardó
```

- **El foco va al campo del envase,** porque hay que escribirlo una vez. Es el único dato que se escribe: los envases y los sueltos se cuentan con «+» y «−».
- Mientras el envase está vacío o fuera de rango, el sufijo de «Envases enteros» dice solo «envases» y el resultado cuenta solo los sueltos. No se marca error hasta confirmar.
- **«Contar sueltos» en este caso descarta el envase escrito,** que todavía no se guardó, y vuelve al campo único con el total. Con envase ya guardado (4.1), «Contar sueltos» solo cambia la vista: el envase sigue guardado.

### 4.3 Pantalla ancha (1280 y 1920 px)

La fila vive en la columna izquierda (`3fr`), de unos 500 px a 1280 y unos 900 a 1920 (MATU-51 3.2). El panel no cambia de forma: los campos siguen **uno debajo del otro**, también a 1920 px, para que la pregunta, los dos números y el resultado se lean de arriba abajo como una cuenta. Lo único que cambia es que el sufijo cabe junto al campo y que «Anotar lo que queda» y «Volver» quedan lado a lado (`Acciones`, como en MATU-51). «Contar sueltos» sigue en su propio renglón, debajo.

```
│ │ ¿Cuántos quedan hoy, más o menos?                               │ │
│ │ Cuenta los envases enteros y, a ojo, lo suelto. Reemplaza lo…   │ │
│ │ Envases enteros                                                 │ │
│ │ [ − ] [  2  ] [ + ]  envases de 20 unidades                     │ │
│ │ Unidades sueltas                                                │ │
│ │ [ − ] [  5  ] [ + ]  unidades                                   │ │
│ │ En total, quedan unas 45 unidades.                              │ │
│ │ [ Anotar lo que queda ]  [ Volver ]                             │ │
│ │ Contar sueltos                                                  │ │
```

### 4.4 Lo que va a la API

| Caso | Petición | Cuerpo |
|---|---|---|
| Modo sueltos, o envases con el envase ya guardado | `POST …/consumo/{perfil_id}/recontar` (decisión 139), como hoy | `{"stock_unidades": total}` |
| Modo envases, con el envase escrito en el panel | `PATCH …/consumo/{perfil_id}` (decisiones 41 y 121) | `{"stock_unidades": total, "unidades_por_envase": u}` |

- Las dos con `If-Match` y el `etag` de la fila. Las dos responden el perfil recalculado. El `PATCH` responde `PerfilConsumoVista`, sin `avisando`: la marca y el bloque «Se acaban pronto» salen del `refrescarBloque` de hoy, igual que con `recontar`.
- `total = envases × u + sueltos`, con los vacíos en 0. Nunca se manda una fecha, ni los envases ni los sueltos por separado.
- Los errores son los de MATU-51 5.4 y 5.5 (404, 403, 409 `perfil-inactivo`, 412 con «Ver cómo quedó», 428, red), con los textos ya aprobados [L 23]. El `PATCH` puede responder además un 422 en `unidades_por_envase`, que va bajo el campo del envase (sección 7).

### 4.5 Confirmación

La de MATU-51 [L 23], sin cambios: «Anotamos lo que queda de «{nombre}»: {cantidad}. Alcanza para {n} días, hasta el {fecha}.», con `{cantidad}` **en la unidad del insumo** («45 unidades», «12 sobres»). Es lo mismo que dice la fila después («Quedan 45 hoy.»), así que la confirmación y la fila no se contradicen.

Si se anotó el envase en el panel, se agrega al final una frase: «También anotamos que cada envase trae 20 unidades.» [PROPUESTO].

---

## 5. El campo de lo que queda en el formulario (alta y edición)

### 5.1 Alta, a 360 px

El orden del formulario no cambia (MATU-60 9.1): nombre, cómo se cuenta, uso, **lo que queda**, aviso y, al final, el envase.

**Modo sueltos (el de siempre al abrir el alta):**

```
│ ¿Cuántos quedan hoy, más o menos?  │  Stepper de hoy [L 18]
│ [ − ] [     ] [ + ]  unidades      │
│ Contar en envases                  │  enlace de texto, min-h-12, NUEVO
│                                    │
│ ¿Con cuántos días de anticipación  │
│ te avisamos?                       │
│ …                                  │
│ ¿Cuántas unidades trae cada        │  CampoEnvase al final, como hoy
│ envase?                            │
```

**Modo envases, después de tocar «Contar en envases»:**

```
│ ¿Cuántos quedan hoy, más o menos?  │  legend font-bold (fieldset)
│ Cuenta los envases enteros y, a    │  ayuda text-base text-tenue
│ ojo, lo suelto.                    │
│                                    │
│ ¿Cuántas unidades trae cada        │  CampoEnvase, sube aquí (D3), foco aquí
│ envase?                            │
│ Lo guardamos para la próxima vez y │
│ para la lista.                     │
│ ┌──────────┐                       │
│ │          │ unidades              │
│ └──────────┘                       │
│ Envases enteros                    │
│ [ − ] [     ] [ + ]                │
│ envases                            │  «envases de 20 unidades» cuando hay envase
│ Unidades sueltas                   │
│ [ − ] [     ] [ + ]  unidades      │
│ En total, quedan unas 45 unidades. │  solo si uno de los dos tiene número
│ Contar sueltos                     │  enlace de texto
│                                    │
│ ¿Con cuántos días de anticipación  │
│ te avisamos?                       │
│ …                                  │  el campo del envase ya no está al final
│ ┃ Así, alcanza para 11 días, …    │  vista previa, con el total
│ [ Guardar ]   Cancelar             │
```

- **El campo del envase es uno solo,** con un solo valor. En modo envases se dibuja dentro del bloque de lo que queda, y en modo sueltos al final. Nunca aparece dos veces.
- **Al volver a «Contar sueltos»** el envase escrito se queda, y el campo vuelve al final con su valor. En el formulario no se descarta, porque sigue siendo un dato del insumo que sirve a la lista.
- **La vista previa** («Así, alcanza para…») usa el total, nunca solo uno de los dos campos.

### 5.2 Edición, a 360 px

En la edición, lo que queda va primero (MATU-36 3.4).

- **Con envase guardado (mayor que 1):** abre en modo envases, con el campo del envase dentro del bloque y su valor guardado, y los dos `Stepper` vacíos, como el campo único de hoy. La ayuda es la de hoy más la frase de envases: «El 04/11/2026 anotaste 24. Escribe cuántos quedan hoy, o déjalo en blanco si no lo sabes. Cuenta los envases enteros y, a ojo, lo suelto.»
- **Sin envase:** abre en modo sueltos, con «Contar en envases» debajo y el campo del envase al final, como hoy.
- **Los dos vacíos no son error en la edición:** lo que queda no cambia, como hoy con el campo único vacío.

### 5.3 Pantalla ancha

El formulario vive en la columna derecha (`2fr`) o en su marco `bg-hoja` (MATU-36). Los campos van uno debajo del otro, igual que a 360 px. No hay dos columnas dentro del bloque.

### 5.4 Lo que va a la API

- **Alta (`POST …/consumo`):** `stock_unidades` = total. En modo envases, `unidades_por_envase` = el envase. En modo sueltos, el envase se manda solo si se escribió al final, como hoy.
- **Edición (`PATCH`):** `stock_unidades` solo si alguno de los dos tiene número. `unidades_por_envase` solo si cambió, y vacío como `null` en modo sueltos (MATU-60 9.2).
- En modo envases, el envase es **obligatorio** si hay un número en envases enteros: sin él no se puede hacer la cuenta.

---

## 6. Componentes y tokens (todos existentes, ningún token nuevo)

| Parte | Componente y clases |
|---|---|
| Bloque, en el formulario | `fieldset` `flex min-w-0 flex-col gap-4`, con `legend` `font-bold` (la pregunta) y la ayuda en un `span` `text-base text-tenue` en el `aria-describedby` de los dos campos |
| Bloque, en el panel | El panel de MATU-51 3.3: `div` `role="group"` con `aria-labelledby` a la pregunta, `tabIndex={-1}`, `outline-none`, `flex scroll-mb-28 flex-col gap-3 border-t border-linea pt-3`. No se anida otro grupo |
| «Envases enteros» | `Stepper` de `insumosComun.tsx`, `min={0}`, `max={⌊100.000 / u⌋}`, sufijo `sufijoCantidad(n, unidad, u)` de `textoLista.ts` (con vacío, `n = 0`: «envases de 20 unidades»). Sin envase válido, el sufijo es «envases» |
| Sueltos | `Stepper`, `min={0}`, `max={100.000}`, sufijo `INSUMOS.sufijoStock(unidad)` |
| Campo del envase | `CampoEnvase` de MATU-60 9.2, sin cambios de forma: `cifras min-h-12 w-32 rounded-xl bg-hoja px-4 text-xl ring-2 ring-inset ring-borde`, `inputMode="numeric"`, `maxLength={5}`. Solo cambia la ayuda en modo envases (sección 7) |
| Resultado | `p` `text-base font-bold`, con la cifra en `cifras`. Sin color de estado: es una cuenta, no un éxito ni un error. Su `id` va en el `aria-describedby` del botón de confirmar |
| «Contar en envases» y «Contar sueltos» | `button type="button"` con el aspecto del «Cancelar» del formulario: `inline-flex min-h-12 items-center self-start px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa`. Sin ícono |
| Error de un campo | El del `Stepper` o de `CampoEnvase`: anillo `ring-pronto`, `aria-invalid` y `MensajeError` debajo |
| Confirmar y Volver | Los de MATU-51 3.3, sin cambios |

**Prohibido:** valores escritos a mano, un color para el resultado, un ícono de caja o paquete, y poner los dos `Stepper` lado a lado (a 360 px no caben y en pantalla ancha se leen como una sola cifra).

---

## 7. Textos exactos

| Dónde | Texto | Marca |
|---|---|---|
| Pregunta del bloque y del panel | ¿Cuántos quedan hoy, más o menos? | [L 18] |
| Ayuda del panel, modo sueltos | Reemplaza lo que calculábamos. Si no queda nada, escribe 0. | [L 23] |
| Ayuda del panel, modo envases | Cuenta los envases enteros y, a ojo, lo suelto. Reemplaza lo que calculábamos. | [PROPUESTO] |
| Ayuda del alta, modo envases | Cuenta los envases enteros y, a ojo, lo suelto. | [PROPUESTO] |
| Ayuda de la edición, modo envases | El {fecha} anotaste {n}. Escribe cuántos quedan hoy, o déjalo en blanco si no lo sabes. Cuenta los envases enteros y, a ojo, lo suelto. | [L 18] + [PROPUESTO] |
| Enlace para pasar a envases | Contar en envases | [PROPUESTO] |
| Enlace para volver | Contar sueltos | [PROPUESTO] |
| Primer campo | Envases enteros | [PROPUESTO] |
| Sufijo del primer campo | envase de {u} unidades · envases de {u} unidades (con sobres, «de {u} sobres») · sin envase válido: envases | [L 21] · [PROPUESTO] el «envases» solo |
| Segundo campo | Unidades sueltas · Sobres sueltos | [PROPUESTO] |
| Sufijo del segundo campo | unidades · sobres | [L 18] |
| Botones − y + (lector) | Uno menos: Envases enteros · Uno más: Envases enteros · Uno menos: Unidades sueltas · Uno más: Unidades sueltas (o Sobres sueltos) | Forma de MATU-36 |
| Campo del envase | ¿Cuántas unidades trae cada envase? | [L 21] |
| Ayuda del campo del envase, modo envases | Lo guardamos para la próxima vez y para la lista. | [PROPUESTO] |
| Ayuda del campo del envase, modo sueltos (al final del formulario) | Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco. | [L 21], sin cambios |
| Resultado, varias unidades | En total, quedan unas {n} unidades. | [PROPUESTO] |
| Resultado, varios sobres | En total, quedan unos {n} sobres. | [PROPUESTO] |
| Resultado, 1 | En total, queda 1 unidad. · En total, queda 1 sobre. | [PROPUESTO] |
| Resultado, 0 | En total, no queda nada. | [PROPUESTO] |
| Confirmar, panel | Anotar lo que queda | [L 23] |
| Confirmación | Anotamos lo que queda de «{nombre}»: {cantidad}. Alcanza para {n} días, hasta el {fecha}. (y sus variantes) | [L 23] |
| Confirmación, si se anotó el envase en el panel | (lo anterior) + También anotamos que cada envase trae {u} unidades. · … trae {u} sobres. · Con {u} igual a 1 no aplica (D6) | [PROPUESTO] |

**Errores:**

| Caso | Dónde | Texto | Marca |
|---|---|---|---|
| Los dos vacíos al confirmar (panel y alta) | Bajo «Envases enteros», foco ahí | Escribe cuántos quedan. Si no queda nada, escribe 0. | [L 18] |
| Envase vacío con un número en envases enteros | Bajo el campo del envase, foco ahí | Escribe cuántas unidades trae cada envase. | [PROPUESTO] |
| Envase en 0 o sobre 10.000, en modo envases (o 422 en `unidades_por_envase`) | Bajo el campo del envase | Escribe un número de 1 a 10.000. | [PROPUESTO] (en modo sueltos sigue el de L 21, que dice «o déjalo en blanco») |
| El total pasa de 100.000 | Bajo «Envases enteros» | Con eso quedarían más de 100.000 unidades. Revisa cuántos envases y sueltos anotaste. (o «sobres») | [PROPUESTO] |
| Más de 10 años (422 `cobertura_maxima`), panel | Bajo «Envases enteros» | Con esa cantidad alcanzaría para más de 10 años. Revisa cuántos quedan. | [L 23] |
| Más de 10 años, formulario | Error general del formulario | Con esos números alcanzaría para más de 10 años. Revisa cuánto queda y cuánto se usa. | [L 18] |
| 404, 403, 409, 412, 428, red | Los de MATU-51 5.5 y MATU-36 | Sin cambios | [L 18] [L 23] |

**Sin cambios que aprobar en lo ya aprobado:** la pregunta, las confirmaciones y los errores de MATU-51 se reutilizan tal cual. El total siempre se dice en la unidad del insumo.

**Prohibido en todos:** «stock», «quiebre», «reponer», «inventario», «exacto», precios, y cualquier término de `lenguaje.md` 3. «Más o menos» y «a ojo» se mantienen porque son lo que hace la persona frente a la repisa, y la predicción se corrige con «Compré» y «Me quedan» (MATU-51).

---

## 8. Foco y lectores de pantalla

| Momento | Foco | Qué se anuncia |
|---|---|---|
| Abre «Me quedan» en modo envases (envase guardado) | En el panel (`role="group"`, `tabIndex={-1}`), sin abrir el teclado (D4) | «¿Cuántos quedan hoy, más o menos?, grupo». El `Tab` sigue a «−», «Envases enteros», «+», «−», los sueltos, «+», «Anotar lo que queda», «Volver» y «Contar sueltos» |
| Abre «Me quedan» en modo sueltos | En el campo, como hoy | La etiqueta y la ayuda |
| Toca «Contar en envases» | En el campo del envase si no hay envase, o en «Envases enteros» si ya lo hay. El enlace desaparece, así que el foco nunca queda en un elemento que ya no existe | La etiqueta del campo y su ayuda |
| Toca «Contar sueltos» | En el campo único | Su etiqueta y la ayuda |
| Cambia el resultado | El foco no se mueve. El resultado **no** es región viva: con cada «+» se leería otra vez. En el panel va en el `aria-describedby` de «Anotar lo que queda». En el formulario no se agrega a «Guardar»: el lector lo encuentra en el orden de lectura, bajo los dos campos, y la vista previa ya dice cuánto alcanza | Al llegar al botón: «Anotar lo que queda, botón, En total, quedan unas 45 unidades.» |
| Error, éxito, 412 y demás | Los de MATU-51 4 | — |

**MATU-67 (salir sin guardar):** los dos campos nuevos cuentan como cambios, y el orden para llevar el foco es el envase, envases enteros y sueltos, en el lugar del campo de lo que queda.

---

## 9. Insumos en ml y en g

**No aplica.** En ml y en g, «Me quedan» y el formulario siguen como hoy, en la unidad del insumo, sin «Contar en envases» (D2).

**Por qué:** frente a la repisa, un frasco abierto no se cuenta en mililitros: se ve «a la mitad» o «casi vacío». Pedir «unos 120 ml sueltos» convierte el «a ojo» en un cálculo, que es justo lo que U3 dice que cuesta. Además, en la app de hoy ml y g solo llegan desde un producto del catálogo, que es la capa 3 y se puede quitar. Tampoco cambia nada en «Compré», donde ml y g con envase ya funcionan (MATU-51 3.4): ahí se cuentan envases cerrados, que sí se ven.

**Si se quiere más adelante** (no en esta historia): envases enteros más «¿Hay uno abierto? Casi lleno · A la mitad · Casi vacío», que la pantalla convierte en ¾, ½ y ¼ del envase. Va al Product Backlog si Jorge lo pide.

---

## 10. Estados y límites

| Estado | Qué se ve |
|---|---|
| Con envase guardado | Modo envases al abrir (4.1, 5.2) |
| Sin envase | Modo sueltos y «Contar en envases» (4.2, 5.1) |
| Envase de 1 | Como sin envase (D6). En el formulario, el campo del envase muestra 1 al final, como hoy |
| ml o g | Como hoy, sin enlace (9) |
| Enviando | MATU-51 5.2: «Guardando…», los campos en solo lectura, los «−» y «+» y los dos enlaces ignoran el toque, `Escape` no cierra |
| Éxito | MATU-51 5.3, con la confirmación de 4.5 |
| Error | Sección 7. El panel o el formulario siguen abiertos con lo escrito, en el mismo modo |
| Conflicto (412) | MATU-51 5.5 en el panel. En el formulario, el conflicto de MATU-36 3.5: «Lo tuyo, sin guardar» muestra el total en unidades y, si cambió el envase, «Cada envase trae {u} unidades.» [L 21] |
| Límites | Envases enteros de 0 a ⌊100.000 / u⌋ (con 20 por envase, 5.000), sueltos de 0 a 100.000, total hasta 100.000, envase de 1 a 10.000. Los sueltos pueden ser más que un envase («2 envases y 25 sueltas»): es «a ojo» y no se corrige |
| Pagador, observador, «Sin seguir» | Sin panel ni formulario, como en MATU-51 3.7 |

---

## 11. Accesibilidad visual

- **Áreas táctiles:** los «−» y «+», los campos, «Contar en envases», «Contar sueltos», «Anotar lo que queda» y «Volver» miden `min-h-12` (51 px) y al menos 48 px de ancho. Los dos enlaces llevan `px-2` y `self-start` para que el área no se estire a lo ancho ni quede menor a 48 px. Entre controles, `gap-3`.
- **Sin depender del teclado numérico:** envases y sueltos se cuentan con «+» y «−», sin escribir. El único dato que se escribe es el envase, una sola vez, y su campo es `type="text"` con `inputMode="numeric"`: acepta cualquier teclado, pegar y el dictado.
- **Nombres accesibles:** cada campo con su `label` visible. Los «−» y «+» nombran su campo («Uno más: Envases enteros»). El panel es un grupo con el nombre de la pregunta, así que cada fila no necesita repetir el nombre del insumo en cada control.
- **Foco visible:** el contorno base de 3 px `turquesa` con 2 px de separación, en claro y oscuro, también en los dos enlaces.
- **Contraste,** con los valores de DISENO.md medidos en MATU-51 6: `turquesa` sobre `hoja` 6,7:1 y 8,2:1 (enlaces) · `tenue` sobre `hoja` 7,2:1 y 8,1:1 (ayuda y sufijos) · `tinta` sobre `hoja` (resultado) sobre 4,5:1 · `borde` del campo sobre `hoja` 3,2:1 y 4,4:1 · subrayado del enlace en `turquesa/40`: no lleva significado (el texto ya es `turquesa` y en negrita), se mide igual en la revisión.
- **Estado nunca solo por color:** el error lleva texto, ícono y anillo. El resultado no lleva color.
- **320 px con texto al 200 % (modo `angosto:`):** cada `Stepper` en su renglón, el sufijo «envases de 10.000 unidades» baja de renglón, el resultado refluye con la cifra en `cifras`, los dos enlaces quedan solos en su renglón, y el `li` usa `angosto:px-2`. Sin desplazamiento horizontal, también con un nombre de 60 caracteres sin espacios.
- **`prefers-reduced-motion`:** el cambio de modo es inmediato. Los campos aparecen y desaparecen sin animación en todos los casos: no se agrega ninguna.
- **Proyector:** nada relevante bajo `text-base`. Tema claro.

---

## 12. Criterios visuales verificables

1. En un insumo con 20 unidades por envase, «Me quedan» abre con «Envases enteros» y «Unidades sueltas» vacíos, sin abrir el teclado, y el foco en el panel.
2. Con «+» dos veces en envases y cinco en sueltos se lee «En total, quedan unas 45 unidades.», y lo que llega a `recontar` es `{"stock_unidades": 45}`.
3. Con un solo campo con número, el otro vale 0. Con los dos vacíos, confirmar muestra el error bajo «Envases enteros» y no llama a la API.
4. En un insumo sin envase, «Contar en envases» muestra el campo del envase con el foco. Al escribir 20, el sufijo pasa de «envases» a «envases de 20 unidades». Confirmar manda un solo `PATCH` con `stock_unidades` y `unidades_por_envase`, y la confirmación termina con «También anotamos que cada envase trae 20 unidades.».
5. «Contar sueltos» lleva el total al campo único sin perderlo, y «Contar en envases» con 65 y envase de 20 deja 3 y 5.
6. En el alta, el formulario se ve como hoy hasta tocar «Contar en envases». Después, el campo del envase está en el bloque de lo que queda y no al final. Nunca aparece dos veces.
7. En la edición de un insumo con envase guardado, el bloque abre en modo envases con el envase a la vista y los dos campos vacíos. Guardar con los dos vacíos no cambia lo que queda.
8. La vista previa del formulario («Así, alcanza para…») usa el total.
9. En un insumo en ml o en g no existe «Contar en envases».
10. «Anotar lo que queda» o «Guardar» es el único `turquesa` macizo. Los dos enlaces son texto subrayado.
11. A 320 px con texto al 200 %, sin desplazamiento horizontal, con «envases de 10.000 unidades» y un nombre de 60 caracteres sin espacios.
12. Todo lo que se toca mide al menos 48 × 48 px y el foco se ve en claro y en oscuro.
13. Ningún texto dice «stock», «inventario» ni «exacto», ni ofrece comprar.

---

## 13. Qué revisaré después de construir

**Lo que el frontend deja levantable, contra el doble del contrato:** un insumo con 20 unidades por envase, uno con 10 sobres por caja, uno sin envase, uno con envase de 1, uno en ml con envase, uno de 60 caracteres sin espacios con 10.000 por envase, y respuestas de 412, 422 `cobertura_maxima`, 422 en `unidades_por_envase`, 500 y una lenta.

**Capturas:**

| Qué | Anchos | Temas | Navegadores |
|---|---|---|---|
| Panel «Me quedan» con envase, vacío, con números y con error | 360, 1280 y 1920 px | Claro y oscuro | Chrome y Firefox |
| Panel sin envase, antes y después de «Contar en envases» | 360, 1280 y 1920 px | Claro y oscuro | Chrome y Firefox |
| Alta en modo sueltos y en modo envases | 360, 1280 y 1920 px | Claro y oscuro | Chrome y Firefox |
| Edición con envase guardado | 360 y 1280 px | Claro y oscuro | Chrome |
| Los tres casos con texto al 200 % | 320 px efectivos | Claro | Chrome y Firefox |
| Foco con teclado por todo el panel | 360 y 1280 px | Claro y oscuro | Chrome y Firefox |
| `prefers-reduced-motion` | 360 px | Claro | Chrome |

**Lo que mido:** contraste de los enlaces, el resultado y los sufijos en los dos temas · área de los dos enlaces (48 px) · que el teclado no se abra al entrar al panel con envase (emulación móvil en Chrome) · el orden del `Tab` · que el resultado se lea en el `aria-describedby` del botón y no como región viva · que no haya ningún valor escrito a mano en las clases nuevas.

---

## 14. Para el orquestador

- **Sin cambios de contrato ni de backend.** `recontar` y el `PATCH` con `unidades_por_envase` ya existen (decisiones 121 y 139).
- **Contradicción con MATU-51 3.5** («siempre en la unidad del insumo»): la reemplaza la decisión de Jorge del 10-11. Ver la sección 0.
- **Cambia MATU-60 9.1** (el envase siempre al final) y **MATU-51 4** (el foco de «Me quedan»): D3 y D4, para el visto de Jorge.
- **Textos [PROPUESTO]** de la sección 7: entran a `lenguaje.md` como una sección nueva o como filas de la 23, cuando Jorge los apruebe.
