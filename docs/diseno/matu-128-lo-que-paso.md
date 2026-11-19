# MATU-128 · Quien pagó ve «Lo que pasó con tu pedido» · Especificación de diseño

**Versión 1.0 · 19/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Viene de:** la revisión previa del analista (C5 y C6, sección «Frontend y diseñador») y las decisiones R2 y R3: una ruta aparte, `GET /v1/grupos/{grupo_id}/pedidos/{pedido_id}/lo-que-paso`, que responde 200 a quien pagó ese pedido, 404 a quien no lo pagó y 503 sin la clave. Solo quien pagó ve el bloque en «Tus pedidos». Quien administra y quien cuida lo siguen viendo en «Datos de», sin cambios.

**Es frontend y textos.** No hay tokens nuevos y `Demo/DISENO.md` no cambia. Todo lo que se usa ya existe: `bg-hoja`, `ring-linea`, `text-tinta`, `text-tenue`, `text-turquesa`, `cifras`, `titular`, los tonos `neutro` y `ok` de `Etiqueta`, `Nota` (tono `rocio`), `Boton` (`secundario`), la variante `angosto` y la animación `animate-aparecer`, que ya respeta `prefers-reduced-motion`.

**Se construye en:**
- `web/src/familia/TusPedidos.tsx`: `Detalle` (la lectura de la ruta nueva y el bloque);
- una pieza compartida para cada cosa anotada (sección 3), que usan «Tus pedidos» y «Datos de»;
- `textosTusPedidos.ts` (los textos nuevos de la sección 6) y `textosMisDatos.ts` (sin cambios de texto).

**Marcas:** **[L 39]** ya está en `lenguaje.md`, sección 39. **[L 38]** y **[L 26]**, en las secciones 38 y 26. **[CÓDIGO]** está aprobado y en el código, pero falta en `lenguaje.md`. **[NUEVO]** lo propongo yo y lo aprueba Jorge.

**En la interfaz nunca se dice** «incidente», «incidencia», «nota del equipo», quién del equipo anotó algo, ni quién de la familia reclamó. Siempre «Lo que pasó con tu pedido» (D-81-4).

---

## 0. Lo que hay hoy (leído en el código de la rama, 19-11)

| # | Dónde | Qué pasa hoy | Qué implica |
|---|---|---|---|
| H1 | `TusPedidos.tsx`, `Detalle` | El detalle de un pedido pagado no muestra lo que anotó el equipo (MATU-116, H3) | El bloque es nuevo en esta pantalla |
| H2 | `DatosPersona.tsx`, `LoQuePaso` (~712 a 760) | El componente recibe `PedidoCopia['lo_que_paso']`, se titula con un `h4` y va dentro del `li` de un pedido de la copia, con `border-t` | **No se reusa entero:** el nivel del título, el borde y el tipo vienen de la copia. Se extrae solo cada cosa anotada (sección 3) |
| **H3** | `DatosPersona.tsx`, `LoQuePaso` | Las fechas usan `ConFechaHora`: «Lo anotamos el 28/10/2026 a las 11:24.». **`lenguaje.md` 39 dice «Las fechas van en DD/MM/AAAA, sin la hora»** | Contradice el texto aprobado. La pieza compartida usa solo la fecha, y así se corrige también «Datos de». **Lo decide el orquestador** (es un cambio visible en «Datos de», fuera del alcance estricto). Si no se acepta, la pieza recibe la forma de la fecha y «Tus pedidos» usa solo la fecha igual |
| H4 | `textosMisDatos.ts`, `loQuePaso.notaNoDisponible` | «La nota ya no está disponible: se borró con los datos de la persona.» está aprobado por Jorge el 17-11 (decisión 471), pero **no está en la tabla de `lenguaje.md` 39** | Se agrega a 39 (sección 6.3) |
| H5 | El encargo | Pide reusar los textos de «`lenguaje.md` §35». Están en la **sección 39** (MATU-81); la 35 es la copia de los datos | Solo una referencia. Esta especificación cita la 39 |

---

## 1. Objetivo

**Rodrigo, que pagó el pedido, ve en ese pedido qué pasó si hubo un problema y cómo se resolvió, sin tener que preguntarle a nadie.**

Vale igual para quien está en «Paga» y para quien está en «Se informa» y pagó (`vista: 'pagaste'`, MATU-116): el detalle es el mismo. **La pantalla no mira el rol ni `vista` para decidir si muestra el bloque:** pide la ruta y pinta lo que responde (C5). Si responde 404, no hay bloque.

---

## 2. Dónde va y jerarquía

**En la columna principal del detalle, justo después de «Cómo va» y antes de «Dinero devuelto».** Es la explicación de lo que «Cómo va» muestra (por ejemplo, «Faltaron 2») y de lo que «Dinero devuelto» devuelve. Se lee en el orden de la historia: cómo va, qué pasó, qué se devolvió.

Jerarquía del detalle con el bloque (la de MATU-116 1.9, con un paso nuevo):
1. «Volver a tus pedidos», el `h1` «Pedido {referencia}», «Pagado el…» y la etiqueta del estado. Sin cambios.
2. «Cómo va». Sin cambios.
3. **«Lo que pasó con tu pedido»** (nuevo), si hay algo anotado.
4. «Dinero devuelto», «Productos para devolver», «Arrepentirme de la compra» y «Cancelar el pedido». Sin cambios.
5. El comprobante y lo demás de la columna derecha. Sin cambios.

Dentro del bloque:
1. El `h2` «Lo que pasó con tu pedido».
2. Por cada cosa anotada, su tipo (`h3`) y su estado en una etiqueta con ícono y palabra.
3. La fecha en que se anotó, lo anotado, «Cómo se resolvió:» con la resolución y la fecha en que se resolvió.

**No va:** en la fila de la lista, en el bloque «Tus pedidos» de «Pedido», en «Tus datos» (C6), ni en la hoja que se imprime con «Imprimir o guardar en PDF»: el comprobante impreso no cambia.

---

## 3. La pieza que se reusa

Se extrae de `LoQuePaso` de `DatosPersona.tsx` **solo lo que pinta una cosa anotada**, como una pieza compartida (por ejemplo `CosaAnotada`, en `PiezasMisDatos.tsx` o en un archivo propio). Las dos pantallas la usan; cada una pone su propio título y su propia lista.

- **Su tipo sale del contrato de la ruta nueva**, con siete campos y nada más: `tipo`, `estado`, `anotado_en`, `resuelto_en`, `nota`, `resolucion` y `nota_disponible`. No usa `PedidoCopia['lo_que_paso']`, ni nada de la copia: ni la referencia del pedido, ni el pago, ni la entrega. `LoQuePasoCopia` tiene los mismos siete campos, así que «Datos de» la usa sin cambiar su contrato.
- **Los textos** siguen saliendo de `textosMisDatos.ts` (`loQuePaso`), que ya están aprobados. `textosTusPedidos.ts` los toma de ahí; no se copian.
- **El nivel del título del tipo** lo pone quien la usa: `h3` en «Tus pedidos», como en «Cómo va»; en «Datos de» sigue como está hoy.
- **La fecha va sin la hora** en las dos (H3, si el orquestador lo acepta).

---

## 4. Esquemas

### 4.1 A 360 px, con dos cosas anotadas

```
│ Catálogo · Lista · Pedido · Tus pedidos │
│ ‹ Volver a tus pedidos                  │  Volver
│ Pedido 4790                             │  h1 Titulo, cifras
│ Pagado el 28/10/2026 a las 11:24        │  p text-base text-tenue
│ [✓ Entregado el 30/10/2026]             │  EtiquetaEstado
│                                         │
│ Cómo va                                 │  h2 titular text-2xl
│ ┌─────────────────────────────────────┐ │
│ │ De Farmacia Los Aromos (comercio    │ │
│ │ ficticio)                           │ │
│ │ [▣ Retirado]                        │ │
│ │ 2 × Pañal adulto talla M x10        │ │
│ │   [⊠ Faltaron 1]                    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Lo que pasó con tu pedido               │  h2 titular text-2xl  (nuevo)
│ ┌─────────────────────────────────────┐ │  li rounded-xl bg-hoja ring-1 ring-linea
│ │ Faltó un producto                   │ │  h3 text-lg font-bold
│ │ [✓ Resuelto]                        │ │  Etiqueta tono ok, CircleCheck
│ │ Lo anotamos el 30/10/2026.          │ │  p text-base text-tenue, cifras
│ │ La farmacia no tenía una de las     │ │  p text-base, pre-line, break-words
│ │ bolsas de pañales.                  │ │
│ │ Cómo se resolvió: devolvimos su     │ │  p text-base, «Cómo se resolvió:» en b
│ │ precio a tu tarjeta.                │ │
│ │ Se resolvió el 31/10/2026.          │ │  p text-base text-tenue, cifras
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ No se pudo entregar                 │ │
│ │ [⌛ MATU lo está revisando]          │ │  Etiqueta tono neutro, Hourglass
│ │ Lo anotamos el 31/10/2026.          │ │
│ │ No había nadie en la casa a la hora │ │
│ │ de la entrega.                      │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Dinero devuelto                         │  sin cambios
│ …                                       │
```

### 4.2 Pantalla ancha (1280 y 1920 px)

La rejilla de MATU-92 4.8, `3fr / 2fr`, sin cambios. El bloque va en la columna izquierda, entre «Cómo va» y «Dinero devuelto», con el mismo `gap-10` entre secciones. A la derecha sigue el comprobante `sticky`.

```
┌──────────────────────────────────────────────────┬──────────────────────────────┐
│ Cómo va                                          │ ┌ Comprobante ─────────────┐ │
│ ┌──────────────────────────────────────────────┐ │ │ …                        │ │
│ │ De Farmacia Los Aromos (comercio ficticio)   │ │ │ Total pagado    $21.900  │ │
│ │ [▣ Retirado]                                 │ │ └──────────────────────────┘ │
│ └──────────────────────────────────────────────┘ │ Datos del pedido             │
│                                                  │ Lo que te garantizamos       │
│ Lo que pasó con tu pedido                        │ [ Imprimir o guardar en PDF ]│
│ ┌──────────────────────────────────────────────┐ │                              │
│ │ Faltó un producto                            │ │                              │
│ │ [✓ Resuelto]                                 │ │                              │
│ │ Lo anotamos el 30/10/2026.                   │ │                              │
│ │ La farmacia no tenía una de las bolsas de    │ │  ← el texto, máx. max-w-prose │
│ │ pañales.                                     │ │                              │
│ │ Cómo se resolvió: devolvimos su precio a tu  │ │                              │
│ │ tarjeta.                                     │ │                              │
│ │ Se resolvió el 31/10/2026.                   │ │                              │
│ └──────────────────────────────────────────────┘ │                              │
│                                                  │                              │
│ Dinero devuelto                                  │                              │
└──────────────────────────────────────────────────┴──────────────────────────────┘
```

La tarjeta ocupa el ancho de la columna, como las de «Cómo va». Los párrafos de dentro llevan `max-w-prose`, para que la línea no pase de unos 70 caracteres a 1920 px.

### 4.3 Clases, por nombre

| Pieza | Clases |
|---|---|
| La sección | `section aria-labelledby="lo-que-paso-t" className="flex min-w-0 flex-col gap-3"`, como «Cómo va» |
| `h2` | `id="lo-que-paso-t" className="titular text-2xl"`, como «Cómo va» |
| La lista | `ul className="flex flex-col gap-3"` |
| Cada cosa anotada | `li className="flex min-w-0 flex-col items-start gap-2 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea"`, la misma tarjeta de «Cómo va» |
| El tipo | `h3 className="max-w-full break-words text-lg font-bold"` |
| Resuelto | `Etiqueta tono="ok"` con `CircleCheck aria-hidden className="size-4 shrink-0"` y la palabra |
| En revisión | `Etiqueta tono="neutro"` con `Hourglass aria-hidden className="size-4 shrink-0"` y la palabra |
| Las fechas | `p className="text-base text-tenue"`, la fecha en `span.cifras` dentro de `time dateTime={iso}` |
| Lo anotado | `p className="max-w-prose text-base whitespace-pre-line break-words"` |
| La resolución | el mismo `p`, con «Cómo se resolvió:» en `b` y un espacio |
| La nota ilegible | `p className="max-w-prose text-base text-tenue"` |

**Ningún valor escrito a mano.** El ícono `size-4` es el de las etiquetas de esta pantalla (en «Datos de» es `size-3.5`; aquí se sigue a «Tus pedidos»). En `angosto` la etiqueta ya oculta el ícono y deja la palabra (MATU-107).

---

## 5. Estados

La ruta se pide **en paralelo con el seguimiento**, al abrir el detalle, y no lo frena: el detalle se pinta apenas llega el seguimiento, como hoy. Nada se guarda en el navegador ni en la URL, y la respuesta no se reutiliza al volver a la lista: cada vez que se abre el detalle, se pide de nuevo.

| Estado | Qué ve | Texto | Origen |
|---|---|---|---|
| **Cargando** | **Nada visible** y sin espacio reservado. La mayoría de los pedidos no tiene nada anotado: un «Cargando…» que después desaparece sería ruido | — | — |
| **200, lista vacía** | **No hay bloque**, ni título ni frase de vacío | — | — |
| **200, con cosas anotadas** | El bloque de la sección 4, en el orden que trae la API | Los de 6.1 | [L 39] |
| **Una cosa anotada ilegible** (`nota_disponible: false`) | La tarjeta igual, con el tipo, el estado y las fechas. En vez de lo anotado y la resolución, la frase de la nota ilegible. Las otras tarjetas, normales | La nota ya no está disponible: se borró con los datos de la persona. | [CÓDIGO] (decisión 471) |
| **`nota` o `resolucion` en `null`** con `nota_disponible: true` | Esa línea no se pinta. Sin resolución no hay «Cómo se resolvió:» | — | — |
| **503** (sin la clave) | En el lugar del bloque, una `Nota tono="rocio"` con el ícono `Clock` (`text-turquesa`) y «Volver a intentar». **Sin el `h2`**: no se sabe si hay algo anotado. El resto del detalle sigue igual | Por ahora no podemos revisar si anotamos algo sobre este pedido. Vuelve a intentarlo en unos minutos. · Volver a intentar | **[NUEVO]** · [L 26] |
| **Sin red o 500** | Lo mismo, con `CloudOff` (`text-turquesa`) | No pudimos revisar si anotamos algo sobre este pedido. Revisa tu conexión y vuelve a intentarlo. · Volver a intentar | **[NUEVO]** · [L 26] |
| **Reintentando** | «Volver a intentar» con `ocupado` y su texto | Cargando… | [L 26] |
| **Reintento con lista vacía** | La `Nota` se cambia por una frase corta en `p text-base text-tenue`, que recibe el foco (el botón desapareció) | No hay nada anotado sobre este pedido. | **[NUEVO]** |
| **Reintento con cosas anotadas** | El bloque, y el foco va a su `h2` | Los de 6.1 | [L 39] |
| **404** (no pagó ese pedido, salió del grupo, o es de otro grupo) | **Nada**: ni bloque, ni aviso, ni error. El detalle sigue igual. Le pasa a «Paga» en los pedidos que pagó otra persona, y es lo normal | — | — |
| **401** | El manejo general de la sesión vencida, como el resto del detalle | — | — |
| **Conflicto (412)** | No aplica: el bloque es de solo lectura | — | — |

**Por qué el 503 no dice «Lo que pasó con tu pedido».** La ruta puede responder 503 en un pedido sin nada anotado. Si el aviso nombrara el bloque, daría a entender que hubo un problema. La frase dice que **no pudimos revisar**, nunca que la nota no está, se perdió o se borró, y «Vuelve a intentarlo en unos minutos» dice que es pasajero. Es la misma lógica del 503 de «Datos de» [L 35].

**Para el backend, vía el orquestador:** conviene que la ruta responda **200 con la lista vacía cuando no hay nada anotado, aunque falte la clave**, y 503 solo cuando hay algo que descifrar. Así el 503 sale menos. El texto de arriba funciona igual en los dos casos.

**Una sola acción principal:** «Volver a intentar» es `secundario`, como en el error del comprobante. El detalle no gana ningún macizo.

---

## 6. Textos

### 6.1 Los aprobados que se usan

| Dónde | Texto | Origen |
|---|---|---|
| `h2` | Lo que pasó con tu pedido | [L 39] |
| Tipos | Faltó un producto · No se pudo entregar · Un reclamo de la familia · Un pago que no se confirmó · Una devolución pendiente · Otra cosa | [L 39] |
| Estado `abierta` o `en_gestion` | MATU lo está revisando | [L 39] |
| Estado `resuelta` | Resuelto | [L 39] |
| Cuándo se anotó | Lo anotamos el {DD/MM/AAAA}. | [L 39] |
| Cuándo se resolvió | Se resolvió el {DD/MM/AAAA}. | [L 39] |
| Antes de la resolución | Cómo se resolvió: | [L 39] |
| Nota ilegible | La nota ya no está disponible: se borró con los datos de la persona. | [CÓDIGO] |
| Botón del error | Volver a intentar · Cargando… | [L 26] |

Un tipo que no esté en la lista se muestra como «Otra cosa», como hoy en «Datos de».

### 6.2 Los nuevos, para aprobar

| # | Dónde | Texto |
|---|---|---|
| N1 | 503 | Por ahora no podemos revisar si anotamos algo sobre este pedido. Vuelve a intentarlo en unos minutos. |
| N2 | Sin red o 500 | No pudimos revisar si anotamos algo sobre este pedido. Revisa tu conexión y vuelve a intentarlo. |
| N3 | Reintento con lista vacía | No hay nada anotado sobre este pedido. |
| N4 | Anuncio de la región viva (5 y 7), solo para lectores de pantalla | Más abajo está lo que pasó con tu pedido. |

### 6.3 Lo que cambia en `lenguaje.md`, para el orquestador

- **En la sección 39**, el párrafo de entrada suma: «Quien pagó un pedido ve lo mismo en ese pedido, en «Tus pedidos» (MATU-128).»
- **En la tabla de la 39**, cuatro filas nuevas, N1 a N4, marcadas **[NUEVO]** MATU-128, y una fila con la nota ilegible, marcada «Decisión 471, aprobado por Jorge el 17-11» (H4).
- **No hay fila nueva en la 38:** los textos del bloque son los de la 39.

---

## 7. Accesibilidad

- **El estado nunca solo por color.** Cada etiqueta lleva la palabra («Resuelto» o «MATU lo está revisando») y su ícono. El color `ok` es un refuerzo. En `angosto` queda la palabra.
- **Los títulos.** El `h2` es hermano de «Cómo va» y «Dinero devuelto», y cada tipo es un `h3`. Con un lector de pantalla se salta de una cosa anotada a la otra con la lista de títulos.
- **El foco.** El bloque no tiene nada interactivo, salvo «Volver a intentar» en el error, con el anillo de siempre (2 px, `turquesa`, 3:1) y su área de 48 px. **Al llegar el bloque, el foco no se mueve.** Solo se mueve después de un reintento: al `h2` si hay cosas anotadas, o a la frase N3 si no hay (con `tabIndex={-1}`), para que el foco no se pierda cuando el botón desaparece.
- **La región viva.** El detalle monta desde el principio un `div role="status"` con `sr-only`, vacío. **Si el bloque llega después de que el detalle ya se pintó**, ese `div` recibe N4, una sola vez. Si llega junto con el seguimiento, no se anuncia: es parte de la página. El 503 y el error de red no se anuncian como alerta (no son urgentes ni culpa de la persona): la `Nota` va sin `rol`, y quien recorre la página la encuentra en su lugar.
- **Texto al 200 % a 320 px.** Nada sale del ancho: la tarjeta es `min-w-0`, los textos llevan `break-words`, el `h3` lleva `max-w-full break-words`, y la etiqueta usa `max-w-full`. Lo anotado puede traer una palabra larga sin espacios: `break-words` la corta.
- **Contraste.** `text-tenue` sobre `bg-hoja` y `text-tinta` sobre `bg-hoja` ya cumplen 4,5:1 en los dos temas (DISENO.md). La etiqueta `ok` cumple 4,5:1 con su texto.
- **Movimiento.** Si se usa `animate-aparecer` al entrar el bloque, ya es inmediato con `prefers-reduced-motion`. No desliza.
- **El proyector.** Todo es `text-base` (17 px) o mayor.

---

## 8. Criterios de revisión visual

Con datos sintéticos: Rodrigo pagó el pedido 4790, con «Faltó un producto» resuelto y «No se pudo entregar» en revisión; otro pedido sin nada anotado; y otro que pagó Carmen.

1. En el detalle del 4790, el bloque «Lo que pasó con tu pedido» está **entre «Cómo va» y «Dinero devuelto»**, en la columna izquierda en pantalla ancha.
2. Su `h2` tiene el mismo tamaño y la misma familia que «Cómo va» (`titular text-2xl`).
3. Cada cosa anotada es una tarjeta `bg-hoja` con `ring-linea`, igual a las de «Cómo va».
4. «Resuelto» y «MATU lo está revisando» se leen como palabras, con su ícono, y se distinguen en escala de grises.
5. Las fechas dicen «Lo anotamos el 30/10/2026.», **sin «a las»**.
6. En ningún lugar del detalle aparecen «incidente», «incidencia», «nota del equipo», ni un nombre de quien anotó.
7. En el pedido sin nada anotado y en el que pagó Carmen (404 para Rodrigo), el detalle es idéntico al de hoy: ni bloque, ni aviso, ni espacio vacío.
8. Con la ruta respondiendo 503, el resto del detalle se ve completo, y en el lugar del bloque está N1 con «Volver a intentar» `secundario`. No aparece el `h2`, ni «se borró», ni «no está disponible».
9. Con `nota_disponible: false`, la tarjeta muestra el tipo, el estado, la fecha y la frase de la nota ilegible, y no muestra «Cómo se resolvió:».
10. A 320 px con el texto al 200 %, no hay desplazamiento horizontal, ni con una nota de una palabra de 60 letras.
11. En el tema oscuro, las tarjetas y la etiqueta `ok` se leen con el contraste de las de «Cómo va».
12. Al tocar «Imprimir o guardar en PDF», la hoja impresa no trae el bloque.
13. Con un lector de pantalla y la ruta lenta (retraso de 2 s en el ambiente de prueba), al llegar el bloque se anuncia N4 una vez, y el foco no se mueve.
14. Lo mismo en el detalle de quien está en «Se informa» y pagó (`vista: 'pagaste'`).
