# MATU-49 · Ficha ampliada (ADR-028) · Especificación de diseño

**Del diseñador, 03/11/2026.** Basada en el ADR-028, en las decisiones que Jorge aprobó el 03/11 y en las especificaciones de MATU-39 (app de familia) y MATU-23 (página del relevo). Se construye en MATU-50 (sprint 4). El paso de compartir lo construye Martín en MATU-48: la sección 6 es para él.

**Convenciones:** las referencias «MATU-39 3.7» o «MATU-23 3.11» apuntan a `docs/diseno/matu-39-app-familia.md` y `docs/diseno/matu-23-pagina-relevo.md`. Los textos entre «» son exactos. **[PROPUESTO]** marca lo que no está en las decisiones del 03/11 ni en otro documento aprobado. **No hace falta ningún token nuevo.**

---

## 0. Lo que tiene que decidir alguien más

> **Resuelto por Jorge el 03-11:** D1 se corrige el ADR-028 (MATU PR #23). D2 contrato en `docs/api/propuestos/ficha-ampliada.openapi.yaml`; el relevo ve las ediciones de lo compartido, pero no las secciones creadas después de su enlace. D3 aprobado: quitar una sección la deja de mostrar en el acto. D4 la revisión previa del analista se hizo el 03-11 y no cambia los textos aprobados. D5 aprobado: el relevo no ve preguntas guía ni ejemplos. Los textos de 10.2 se aprueban en `lenguaje.md` sección 14.3.

| # | Qué | Para quién | Mi recomendación |
|---|---|---|---|
| D1 | **Contradicción con el ADR-028.** La tabla del ADR usa «Lo que la hace bien» y preguntas en femenino («¿Qué debería saber de ella…?», «¿Qué la pone contenta…?», «¿Cómo se la ayuda…?», «¿Qué ayuda a que te entienda y a entenderla?», «¿Qué remedios toma y cuándo?»). Las decisiones del 03/11 los reemplazan por «Lo que le hace bien» y preguntas sin género. Esta especificación sigue las del 03/11 | Orquestador → Jorge: corregir la tabla del ADR-028 para que `docs/` no se contradiga | Corregir el ADR |
| D2 | **El contrato de las secciones** (MATU-49 lo define): ruta del editor de sección, `DELETE` con `If-Match`, y cómo `POST` de accesos recibe las secciones elegidas (por ejemplo `secciones: ["quien_es", …]`) y cómo `GET /r` las devuelve (con `tipo`, `texto`). El diseño asume: una sección **existe solo si tiene texto guardado**, y la respuesta de la ficha trae la lista de secciones existentes con su `etag`, `actualizado_por` y `actualizado_en` | Orquestador → backend | Así |
| D3 | Qué pasa con un acceso **ya creado** cuando se **quita** una sección que ese acceso incluía. El diseño asume que el relevo deja de verla (quitar borra el texto: no queda nada que mostrar) y que **nada más cambia** en el acceso | Orquestador → backend y analista normativo | Así |
| D4 | La revisión previa del analista normativo sobre «Sus remedios» (ADR-028) puede cambiar textos de la sección 5.3 y 6.3. Los textos aprobados del 03/11 no los toco | Orquestador | — |
| D5 | El ejemplo de cada sección **no se muestra al relevo** (sección 7.2). Difiere de los tres campos base, que sí lo muestran (MATU-23 3.11.3) | Jorge | Así: un ejemplo inventado de remedios junto a los remedios reales es un riesgo |

---

## 1. Para quién y qué

- **Carmen** completó la ficha inicial en menos de 3 minutos. Ahora, cuando tiene un rato, quiere contar más: que a su mamá le dicen de una forma, que le gustan los boleros, que usa audífono. **Nada le exige hacerlo.** La pantalla celebra lo que agrega y nunca le dice que falta algo.
- **Rosa** abre el enlace y, además de los tres campos, lee las secciones que Carmen eligió compartir, cada una con su título.
- **Martín** construye el paso de compartir (MATU-48) y necesita saber exactamente qué cambia.

**Lo que no cambia:** los tres campos base, su editor (MATU-39 3.7), su conflicto (3.8), la meta de 3 minutos y la pista «`{n}` de 3» de la navegación.

**Lo que sí cambia por el ADR-028 y faltaba aquí** (revisión MATU-50): la bajada de la ficha (lenguaje 5.4, MATU-39 3.6) termina en «… y puedes compartir solo algunos.», que ya no es cierto: los tres campos van siempre (6). Propuesta [PROPUESTO, la decide Jorge en `lenguaje.md` 5.4]: «Tres campos cortos para que quien te reemplace sepa qué hacer. Cada campo se guarda por separado.» Lo que se elige al compartir ya lo dicen la nota de la vista previa (3.2) y la pantalla de compartir (6).

---

## 2. Las seis secciones (aprobado 03/11)

Orden fijo en toda la app y en la página del relevo, sin importar en qué orden se agregaron (Rosa encuentra siempre lo mismo en el mismo lugar).

| Tipo | Título | Ruta del editor [PROPUESTO] | Pregunta guía (la `label`) | Tope | Ejemplo |
|---|---|---|---|---|---|
| `quien_es` | Quién es | `/ficha/quien-es` | ¿Qué le gustaría que supiera de esta persona alguien que recién la conoce? | 500 | Le dicen Tito. Fue profesor de música en Talca. Su nieta Sofía le visita los domingos y tiene un gato, el Pelusa. |
| `preferencias` | Lo que le hace bien | `/ficha/lo-que-le-hace-bien` | ¿Qué le alegra, le entretiene o le calma? | 500 | Le gustan los boleros y conversar de fútbol. Ve las noticias a las 9 de la noche. |
| `alimentacion` | Comer y beber | `/ficha/comer-y-beber` | ¿Qué le gusta comer y cómo se le sirve? | 500 | Toma té con poca azúcar. Prefiere la comida picada en trozos chicos y el pan blando. |
| `movilidad` | Moverse y descansar | `/ficha/moverse-y-descansar` | ¿Cómo se le ayuda a moverse, levantarse y descansar? | 500 | Camina con bastón dentro de la casa. Para levantarse, ofrécele el brazo derecho. Duerme siesta después de almuerzo. |
| `comunicacion` | Cómo hablarle | `/ficha/como-hablarle` | ¿Qué ayuda a que se entiendan? | 500 | Usa audífono en el oído izquierdo. Háblale de frente y despacio. Si algo le molesta, se toca la frente. |
| `remedios` | Sus remedios | `/ficha/sus-remedios` | ¿Qué remedios toma y a qué hora, tal como se los da la familia? | 800 | 8:00 con el desayuno: 1 pastilla blanca de la caja azul. 20:00: 1 pastilla de la caja verde. |

**Ayuda fija** bajo la caja de las seis: «No hace falta escribir diagnósticos ni enfermedades. Escribe lo que ayuda a cuidar».
**Más ayuda** en `alimentacion` y `remedios`, en la línea siguiente: «Si tiene alergia a algún remedio o alimento, anótalo aquí».
**El ejemplo** se presenta como en MATU-39 3.7: «Por ejemplo: «`{ejemplo}`»».

**Íconos:** las secciones **no llevan ícono propio**. Se distinguen por su título. Así no hay tentación de una píldora o una cruz para «Sus remedios», y la lista no se vuelve un tablero de símbolos. Los únicos íconos son los de acción (`Plus`, `Pencil`, `Trash2`) y los de estado (`Check`).

---

## 3. La ficha (`/ficha`) con las secciones

**Objetivo (de Carmen):** ver lo que ya conté de mi mamá y agregar algo más cuando tenga un rato.

**Jerarquía:**
1. Los tres campos base, tal como hoy (MATU-39 3.6), con su barra «`{n}` de 3 campos listos».
2. «Más sobre `{nombre_pila}`»: las secciones agregadas, con su texto.
3. Las secciones por agregar, como botones secundarios.

### 3.1 Esquema a 360 px

```
Ficha de relevo                                  titular text-3xl
Tres campos cortos para que quien te reemplace…
3 de 3 campos listos   ▮▮▮                      BarraCampos (sin cambios)

┌ Su día ─────────────────── Listo ✓ ┐
│ …  [Editar «Su día»]                │          (los tres campos, sin cambios)
└─────────────────────────────────────┘
…

Más sobre María                                  h2 titular text-2xl  [PROPUESTO]
Si quieres, cuenta más para que quien te         text-base text-tenue
reemplace conozca a María. Agrega solo lo que
te sirva, cuando tengas tiempo.
✓ Agregaste 2 secciones.                         text-base, Check en `ok`  (solo si n ≥ 1)

┌ Quién es ───────────────────────────┐          Hoja de sección (borde `linea`, fondo `hoja`)
│ Le dicen Tita. Fue costurera en…    │          text-base, line-clamp-3
│ Lo escribió Carmen: hoy, 10:42      │          text-sm tenue + Cuando
│ [✎ Editar «Quién es»]               │          secundario
└─────────────────────────────────────┘
┌ Sus remedios ───────────────────────┐
│ Esto lo escribe la familia. No      │          aviso fijo (5.3), siempre visible
│ reemplaza la indicación del médico. │
│ 08:00 con el desayuno: 1 pastilla…  │
│ Lo escribió Carmen: ayer, 21:10     │
│ [✎ Editar «Sus remedios»]           │
└─────────────────────────────────────┘

Puedes agregar                                   h3 text-lg font-bold
[+ Lo que le hace bien]                          un botón secundario por sección
[+ Comer y beber]                                no agregada, uno por renglón,
[+ Moverse y descansar]                          `flex flex-col gap-2` y `self-start`
[+ Cómo hablarle]
```

### 3.2 Pantalla ancha

Igual que MATU-39 3.6: dos columnas `@4xl/main:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]`. A la izquierda, campos y luego «Más sobre…»; a la derecha `HojaFicha` («Así la ve quien te reemplaza»), que ahora incluye, después de los tres campos, cada sección agregada con su título (mismo armado de la sección 7). Bajo el título de la hoja, en `text-sm text-tenue`: «Cada relevo ve solo las secciones que eliges al compartir.» [PROPUESTO]. Los botones «Puedes agregar» pasan a `flex flex-wrap gap-2`.

### 3.3 La barra de avance (ADR-018 y ADR-028)

- **La barra se queda en los tres campos base.** Es la única con denominador («`{n}` de 3»), porque es lo único que se pide. La pista de la navegación también se queda en «`{n}` de 3».
- **Las secciones no tienen barra con casillas vacías ni «`{n}` de 6».** Una barra de seis con cuatro huecos castiga lo que falta, y el ADR-028 pide celebrar lo agregado. En su lugar, una línea que solo suma:
  - 0 secciones: no se muestra la línea (solo la bajada).
  - 1: «Agregaste 1 sección.» · 2 o más: «Agregaste `{n}` secciones.» [PROPUESTO]
  - Con el ícono `Check` en `text-ok` (`aria-hidden`); la palabra lleva el significado.
  - Cuando una sección se guarda por primera vez, la línea se actualiza con `animate-aparecer` (inmediato con `prefers-reduced-motion`) y se anuncia en la confirmación de guardado (4.4), no aquí.
- **Prohibido** en toda la pantalla: «incompleta», «te falta», «pendiente», porcentajes, y cualquier color `atenta`/`pronto` ligado a secciones no agregadas.

### 3.4 Una sola acción principal

La regla de MATU-39 3.6 no cambia: el único `pino` macizo es «Completar» del primer campo base que falta. **Con los tres listos, la pantalla no tiene primario macizo.** Los botones de agregar y editar secciones son siempre secundarios: agregar una sección nunca compite con la ficha inicial.

### 3.5 Componentes y tokens

| Pieza | Construcción |
|---|---|
| Título «Más sobre `{nombre_pila}`» | `h2`, `titular text-2xl`, `mt-10` |
| Bajada | `p text-base text-tenue max-w-prose` |
| Línea de lo agregado | `p flex items-center gap-2 text-base`, `Check size-5 text-ok` |
| Tarjeta de sección agregada | La misma tarjeta de campo de MATU-39 3.6 (borde `linea`, `bg-hoja`, `rounded`), **sin** `Etiqueta` Listo/Falta (una sección existe o no; no hay «Falta»). Título `h3 text-xl font-bold`. Texto `text-base renglones line-clamp-3` |
| Botón agregar | `Boton variante="secundario"` con `Plus` y el título de la sección. Nombre accesible: «Agregar «`{título}`»» (`aria-label`, el texto visible queda contenido en él) |
| Botón editar | `Boton variante="secundario"` con `Pencil`, «Editar «`{título}`»» |

### 3.6 Estados de la ficha

| Estado | Qué se ve |
|---|---|
| Cargando | MATU-39 5.1, «Cargando…» |
| Sin secciones | Título, bajada y las seis en «Puedes agregar». Sin línea de lo agregado |
| Las seis agregadas | Sin «Puedes agregar» (desaparece el `h3`) |
| Error al cargar | MATU-39 5.2 |
| Pagador | Igual que con los campos (MATU-39 3.6, D3): los botones se muestran y un 404 lleva a 5.6 |
| Observador | No ve la ficha (MATU-39 2.2) |

---

## 4. Editor de una sección (`/ficha/{sección}`)

**Objetivo:** escribir sobre una parte de la vida de la persona, guardarlo sin perder nada, o quitarlo.
**Copia:** el editor de un campo (MATU-39 3.7), con su dictado (3.7.1). Las diferencias van abajo.

### 4.1 Esquema a 360 px

```
‹ Volver a la ficha
Más sobre María                                  text-sm text-tenue (en lugar de «Campo 1 de 3»)
Comer y beber                                    titular text-3xl (h1)

¿Qué le gusta comer y cómo se le sirve?          label, text-base font-bold
┌──────────────────────────────────┐
│                                  │             textarea, renglones, min 8 líneas
└──────────────────────────────────┘
0 de 500 caracteres                              cifras text-tenue
No hace falta escribir diagnósticos ni           ayuda, text-base text-tenue
enfermedades. Escribe lo que ayuda a cuidar.
Si tiene alergia a algún remedio o alimento,     (solo Comer y beber y Sus remedios)
anótalo aquí.
│ Por ejemplo: «Toma té con poca azúcar…»        ejemplo, border-s-2 border-linea ps-3

[Mic] Dictar en vez de escribir                  secundario
[ Guardar ]   Seguir después                     primario · texto

─────────────────────────────────────            border-t border-linea, mt-10 (solo si ya existe)
[🗑 Quitar «Comer y beber»]                       variante="texto", text-pronto
```

**Sus remedios**, la única diferencia de forma: el aviso va **entre el título y la `label`**, antes de escribir:

```
Sus remedios                                     titular text-3xl
┌▌ Esto lo escribe la familia. No reemplaza   ┐  Nota tono="atenta", ícono `Info`
│▌ la indicación del médico.                  │
└─────────────────────────────────────────────┘
¿Qué remedios toma y a qué hora, tal como se los da la familia?
┌──────────────────────────────────┐
0 de 800 caracteres
…
```

### 4.2 Pantalla ancha

Igual que MATU-39 3.7: editor a la izquierda, «Así la ve quien te reemplaza» a la derecha, que muestra **solo esta sección** con su título, como la verá el relevo (sección 7). El botón «Quitar» queda bajo el editor, nunca junto a «Guardar».

### 4.3 Reglas

- `label` = la pregunta guía; `aria-describedby` = contador, ayuda (y alergias) y ejemplo, en ese orden. En Sus remedios, también el aviso (va primero).
- **Tope:** `maxLength` 500, o 800 en Sus remedios. Contador «`{n}` de `{tope}` caracteres». Pasa a `text-atenta` con `TriangleAlert` al 90 % (450 o 720) y se anuncia con `aria-live="polite"` solo al cruzar ese umbral y el tope (misma regla de MATU-39 3.7).
- **Dictado:** igual que MATU-39 3.7.1; se detiene al llegar al tope de esa sección. **Excepción (decisión de Jorge del 03-11):** en «Sus remedios» no hay botón de dictar mientras esté en consulta legal el envío del audio de un dato de salud al servicio de voz del navegador. Se reactiva con la respuesta legal.
- **El aviso de remedios** es texto en la página, no `title` ni tooltip ni texto que aparece al pasar el puntero. Usa `Nota tono="atenta"` (fondo `atenta-fondo`, `border-l-4 border-atenta`, texto `tinta`) con el ícono `Info` de lucide: comunica «léelo», no «peligro», y no es un ícono clínico. **Nunca** `Pill`, `Cross`, `Stethoscope`, `Syringe` ni `HeartPulse`.

### 4.4 Guardar (agregar o cambiar)

- Sección nueva: `PUT` con `If-None-Match: *`. Sección existente: `If-Match: {etag}`. Siempre `X-Grupo-Id` (D2 confirma la ruta).
- **Vacío sobre una sección que no existe:** no se envía nada ni hay mensaje; «Guardar» lleva de vuelta a la ficha.
- **Vacío sobre una sección que existe:** no se guarda vacía. Se muestra la confirmación de quitar (4.5), porque dejarla en blanco es quitarla. Así no existen secciones vacías y el relevo nunca ve una sección sin texto.
- Mientras: «Guardando…», `aria-busy`, `textarea` `readOnly`.
- **200/201:** vuelve a `/ficha` con el foco en el `h1` y una `Nota tono="ok"` con `CheckCircle2` arriba:
  - Primera vez: «Agregaste «`{título}`».» [PROPUESTO]
  - Cambio: «Guardamos «`{título}`».» (aprobado por Jorge el 03-11; concuerda con cualquier título)
  - Si el grupo tiene accesos de relevo vigentes y la sección es nueva, se suma en la misma nota: «Quien ya tiene un enlace no la verá. Para que la vea, crea un enlace nuevo.» [PROPUESTO] (decisión 3 del 03/11). Si el cliente no sabe si hay accesos vigentes, la frase va siempre que la sección sea nueva.

### 4.5 Quitar (borra)

- **Dónde:** solo en el editor de una sección que existe, abajo y separado por una línea. `Boton variante="texto"` con `Trash2`, texto en `pronto`: «Quitar «`{título}`»» [PROPUESTO]. 48 px de alto.
- **Confirmación en la página** (no un diálogo flotante: con el texto al 200 % se corta). Reemplaza el botón por un bloque `Nota tono="pronto"` con `CircleAlert`:
  - Título (`p font-bold`): «¿Quitar «`{título}`»?» [PROPUESTO]
  - Texto: «Se borra lo que escribiste en esta sección. Quien tenga un enlace dejará de verla. No se puede deshacer.» [PROPUESTO]
  - Botones: «Quitar y borrar» (`Boton variante="peligro"` si existe, o secundario con texto `pronto`; **nunca `pino` macizo**) y «Dejarla como está» (`variante="texto"`) [PROPUESTO]
  - El foco va al título del bloque; con «Dejarla como está» vuelve al botón «Quitar».
- **Acción:** `DELETE` con `If-Match: {etag}`. Mientras: «Quitando…» [PROPUESTO], `aria-busy`.
- **204:** vuelve a `/ficha`, foco en el `h1`, `Nota tono="ok"`: «Quitaste «`{título}`».» [PROPUESTO] (mismo verbo que el botón). La sección vuelve a «Puedes agregar» y la línea de lo agregado resta.
- **412 con `actual`:** el conflicto de 4.6, con el texto propio de quitar.
- **412 con `actual: null`:** la sección ya no existe (otra persona la quitó). Vuelve a `/ficha` con `Nota tono="rocio"`: ««`{título}`» ya no estaba en la ficha.» (aprobado 03-11). *Corregido el 03-11 en la revisión de MATU-50: esta especificación decía 404, pero el contrato (`ficha-ampliada.openapi.yaml`, `DELETE`) responde 412 con `actual: null` para distinguirlo de «no tienes acceso». Manda el contrato.*
- **404:** no tiene acceso (rol o grupo): MATU-39 5.6, «No tienes acceso», igual que en los campos.

### 4.6 Conflicto (412)

**Guardar:** idéntico a MATU-39 3.8 (lenguaje 6.2), con `{campo}` = título de la sección. «Dejar la mía» reintenta con el `ETag` del 412.
**Quitar** mientras otra persona la cambió [PROPUESTO]:

```
Rodrigo cambió «Comer y beber» mientras la ibas a quitar     titular text-2xl
Esta es la versión que guardó Rodrigo:
┌ La de Rodrigo · Guardada a las 10:42 ┐
│ (texto actual)                       │
└──────────────────────────────────────┘
[Quitarla igual]  secundario texto pronto     [Dejarla como está]  texto
```

«Quitarla igual» reintenta el `DELETE` con el `ETag` del 412. Nada se borra sin que Carmen vea la versión nueva. Foco al título, `role="alert"` una vez.

«Dejarla como está» vuelve a `/ficha` con `Nota tono="ok"` y el mismo verbo del botón [aprobado por Jorge el 03-11]: «Dejaste «`{título}`» como la guardó `{autor}`.» (reemplaza «Dejaste la versión de `{autor}`.», que es la confirmación de guardar, no de quitar).

**Guardar cuando otra persona la quitó** (412 con `actual: null` a un `PUT` con `If-Match`) [aprobado por Jorge el 03-11]. La pantalla de 6.2 no sirve: el 412 no trae autor y no hay «versión de otra persona» que elegir (hoy muestra «La de Otra persona · Vacía»). En su lugar, la misma construcción de este bloque (alerta `pronto` con `TriangleAlert`, título `titular text-2xl`), con **solo** la caja «La tuya»:

```
Otra persona quitó «Moverse y descansar» mientras escribías    titular text-2xl
Lo que escribiste no se guardó. Puedes agregarla de nuevo con tu texto.
┌ La tuya · Lo que escribiste recién, sin guardar ┐
│ (texto propio)                                  │
└─────────────────────────────────────────────────┘
[Agregarla de nuevo]  primario      [Dejarla quitada]  texto
```

- «Agregarla de nuevo» hace el `PUT` con `If-None-Match: *`. Al volver: «Agregaste «`{título}`».» más la frase de los enlaces de 4.4 (es una sección nueva para los accesos ya creados).
- «Dejarla quitada» vuelve a `/ficha` sin petición, con `Nota tono="rocio"`: «Dejaste «`{título}`» quitada.»
- Al pie, `text-base text-tenue`: «Si quieres, copia lo que escribiste antes de elegir.»
- Foco al título, `role="alert"` una vez, como en 6.2.

### 4.7 Otros errores

Los de MATU-39 3.9, sin cambios (428, 403 de consentimiento y de revisión, 404, 401, red). El 422 de largo usa el tope de la sección, con un texto propio [aprobado por Jorge el 03-11], porque lenguaje 6.5 dice «Cada campo» y fija 500: «Esta sección admite hasta `{tope}` caracteres. Acorta un poco el texto para guardarlo.» (`{tope}` = 500, u 800 en Sus remedios, en `cifras`).

### 4.8 Texto al 200 % en las pantallas de conflicto (revisión MATU-50)

A 320 px con el texto al 200 %, el título `text-2xl` de la alerta tiene palabras («mientras», «escribías», «remedios»») más anchas que la columna, y el bloque de texto no puede encogerse junto al ícono. Vale para 4.6 y para el conflicto de los campos (MATU-39 3.8), que comparten la construcción:
- El `div` del texto junto al ícono lleva `min-w-0`; el título, `wrap-anywhere` (`overflow-wrap: anywhere`, que también reduce el ancho mínimo del bloque) y `hyphens-auto`.
- En `angosto:` el título baja a `text-xl`, la alerta usa `px-2` y el ícono se oculta (`angosto:hidden`): el borde `pronto` de 4 px y la palabra llevan el estado.
- Criterio: `scrollWidth − clientWidth = 0` en la pantalla de conflicto a 320 px con el texto al 200 %.

---

## 5. Sus remedios, en resumen

1. **Al escribir:** el aviso arriba de la caja (4.1), siempre, aunque esté vacía.
2. **En la ficha:** el aviso dentro de su tarjeta, sobre el texto (3.1), en `text-base` (es texto relevante; nada relevante bajo 1 rem). Forma: `p` con `border-s-4 border-atenta ps-3 text-base`, sin fondo (la tarjeta ya es `hoja`).
3. **Al compartir:** desmarcada siempre, casilla aparte, y confirmación (6.3).
4. **Al leer (relevo):** el aviso sobre el texto (7.1), igual que en la ficha.
5. **Texto exacto en los cuatro lugares:** «Esto lo escribe la familia. No reemplaza la indicación del médico.»
6. **El texto de remedios no se pinta como línea de tiempo** aunque empiece con hora: se muestra tal cual, renglón por renglón, con las horas en `cifras`. [PROPUESTO] Razón: la línea de tiempo de Su día parte las líneas y podría separar una hora de su remedio al reflujo; el texto libre de la familia se respeta literal.

---

## 6. Compartir con un relevo (MATU-48, para Martín)

**Qué cambia contra el «Compartir» de la demo** (`Demo/src/familia/Ficha.tsx`, `Compartir`):

| Hoy en la demo | En MATU-48 con ADR-028 |
|---|---|
| «¿Qué puede ver?» con un chip por cada campo base, que se marca y desmarca | **Los tres campos ya no se eligen.** Van siempre. Se muestran como texto, no como control |
| Error «Elige al menos un campo.» | **Desaparece**: siempre van los tres |
| Aviso de campos vacíos «… está vacío: Rosa verá «Sin completar».» | **Se queda**, igual |
| — | Nuevo grupo de casillas con las **secciones agregadas** (sin Sus remedios) |
| — | Nueva casilla aparte: **«Incluir Sus remedios»**, desmarcada, con su ayuda |
| — | Confirmación de remedios antes de crear el enlace, si se marcó |

### 6.1 Esquema a 360 px (el orden de la columna)

```
¿Quién te va a reemplazar?  [Rosa            ]
Su teléfono                 [+56 9 5555 0137 ]

Siempre ve                                        p font-bold  [PROPUESTO]
✓ Su día, Si se altera y A quién llamar.          Check text-ok, text-base

¿Qué más puede ver?                               legend font-bold  [PROPUESTO]
Elige las secciones que le sirven.                text-base text-tenue  [PROPUESTO]
[☐ Quién es] [☐ Cómo hablarle]                    chips de varias opciones (cuadrado)
                                                  todas desmarcadas al entrar  [PROPUESTO]
┌─────────────────────────────────────────┐
│ [☐] Incluir Sus remedios                │       casilla aparte, borde `borde`, rounded
│     Quien te reemplaza verá qué remedios│       ayuda text-base text-tenue
│     toma y a qué hora. Márcalo solo si  │
│     va a dárselos o a estar a cargo de  │
│     ellos.                              │
└─────────────────────────────────────────┘

¿Hasta cuándo?     (sin cambios)
¿Para qué lo compartes?  (sin cambios)

[ Crear enlace ]
```

- **Sin secciones agregadas:** no aparece «¿Qué más puede ver?». **Sin Sus remedios agregada:** no aparece su casilla. Nunca se ofrece una sección vacía.
- **Valor inicial de las demás secciones:** desmarcadas [PROPUESTO]. Compartir es elegir: lo mínimo por defecto. Si Jorge prefiere marcadas, solo cambia el estado inicial; Sus remedios sigue desmarcada siempre.
- **Pantalla ancha:** la vista previa de la derecha («Lo que verá `{nombre}`») muestra los tres campos y **solo** las secciones marcadas, en el orden fijo de la sección 2, y se actualiza al marcar.

### 6.2 Construcción

- «Siempre ve»: un `p` y una línea con `Check`, no un `fieldset` deshabilitado (un control que no se puede tocar confunde y el lector de pantalla lo anuncia como atenuado).
- «¿Qué más puede ver?»: `fieldset` + `legend`, un `input type="checkbox"` por sección dentro de un `label` con la piel del `Chip` actual (cuadrado con check para varias opciones, ESPEC-ADR-027 6.3). `min-h-12`, foco `has-[:focus-visible]:outline-3 outline-pino`. Elegido: `bg-rocio text-pino ring-pino`; sin elegir: `bg-hoja text-tenue ring-borde`. El estado se ve por el cuadrado con `Check`, no solo por color.
- «Incluir Sus remedios»: `label` en bloque (`flex items-start gap-3 rounded border border-borde bg-hoja p-4`), `input type="checkbox"` visible de `size-6` con `accent-pino`, texto `font-bold` y la ayuda en `p` enlazada con `aria-describedby`. Toda la caja se puede tocar. Va separada del grupo de chips porque no es una sección más: necesita su ayuda a la vista.
- Nada en `pino` macizo salvo «Crear enlace».

### 6.3 Confirmación de Sus remedios

Si «Incluir Sus remedios» está marcada, «Crear enlace» **no crea todavía**: muestra en la misma columna, justo encima del botón, un bloque `Nota tono="atenta"` con `Info` y el foco en él:

```
┌▌ Vas a compartir sus remedios con Rosa hasta    ┐
│▌ el 07/11/2026. Puedes cortar el acceso cuando  │
│▌ quieras.                                       │
│▌ [ Sí, crear el enlace ]  [ No incluir sus remedios ] │
└─────────────────────────────────────────────────┘
```

- Texto aprobado: «Vas a compartir sus remedios con `{nombre}` hasta el `{DD/MM/AAAA}`. Puedes cortar el acceso cuando quieras.» `{nombre}` es lo escrito en «¿Quién te va a reemplazar?»; la fecha es la de vencimiento ya calculada (`cifras`, en bold), en hora de Chile.
- Botones [PROPUESTO]: «Sí, crear el enlace» (primario: en este momento es la acción principal; «Crear enlace» de abajo queda oculto mientras el bloque está abierto) y «No incluir sus remedios» (secundario: desmarca la casilla, cierra el bloque y devuelve el foco a la casilla).
- Si Carmen cambia el nombre o el plazo con el bloque abierto, el bloque se cierra: la confirmación debe decir lo que de verdad se va a crear.
- Sin la casilla marcada, no hay confirmación: «Crear enlace» crea como hoy.

### 6.4 Después de crear (pantalla del PIN y «Enlaces»)

- En la pantalla del PIN, la línea de lo que ve (hoy en «Enlaces»: «Ve su día, si se altera y a quién llamar.») suma las secciones: «Ve su día, si se altera, a quién llamar, quién es y sus remedios.» Títulos en minúscula, unidos con comas e «y» al final, en el orden fijo. [PROPUESTO]
- Debajo, en `text-base text-tenue`: «Si agregas una sección después, `{nombre}` no la verá. Para que la vea, crea un enlace nuevo.» [PROPUESTO] (decisión 3).
- Si el acceso incluye Sus remedios, en «Enlaces» la línea lo nombra igual que arriba: Carmen ve de un vistazo a quién le compartió los remedios.

### 6.5 Criterios verificables de compartir

- No existe ningún control para desmarcar Su día, Si se altera o A quién llamar.
- «Incluir Sus remedios» aparece desmarcada **cada vez** que se abre la pantalla, aunque el acceso anterior la haya incluido.
- Con la casilla marcada, tocar «Crear enlace» no hace ninguna petición a la API hasta tocar «Sí, crear el enlace».
- Un lector de pantalla anuncia «¿Qué más puede ver?, grupo» y cada sección como «casilla, no marcada».
- A 320 px con texto al 200 %: los chips pasan a una columna, la caja de remedios no desborda y la fecha de la confirmación no se parte.
- Cómo se logra en `angosto:` (revisión MATU-50): la confirmación usa `px-2` y oculta el ícono `Info` (el borde `atenta` y el texto llevan el aviso), para que `{DD/MM/AAAA}` en `cifras` quepa entera; los chips pasan a `rounded-xl` y `px-3`, con `hyphens-auto` en el título, para que «Moverse y descansar» no se corte a mitad de palabra sin guion.

---

## 7. La página del relevo (`/r`, MATU-23 3.11)

### 7.1 Cada sección en la hoja

Después de los tres campos, en el orden fijo de la sección 2, **solo las secciones que vienen en la respuesta**. Una sección no compartida no deja rastro (mismo criterio de MATU-23 3.11: ni título, ni «no compartido», ni un conteo).

Construcción de una sección (`section aria-labelledby`, `mt-6`), como un campo de MATU-23 3.11.1, con dos diferencias:

| Pieza | Texto | Construcción |
|---|---|---|
| Separador | — | Antes de la primera sección: `border-t border-linea pt-6 mt-8`, sin texto (la hoja sigue siendo una sola) |
| Título | El título de la sección (2) | `h2 text-xl font-bold text-turquesa` |
| Aviso (solo Sus remedios) | «Esto lo escribe la familia. No reemplaza la indicación del médico.» | `p border-s-4 border-atenta ps-3 text-base`, `mt-2`, antes del texto |
| Contenido | `texto` | MATU-23 3.11.2: texto, nunca HTML, `renglones text-lg leading-7 max-w-prose`. Sin línea de tiempo (5.6) |
| Pregunta guía | **No se muestra** | Está escrita para la familia («tal como se los da la familia», «le gustaría que supiera»); a Rosa no le pregunta nada |
| Ejemplo | **No se muestra** (D5) | Un ejemplo inventado al lado del texto real puede leerse como dato, y en Sus remedios eso es peligroso |

```
│ │ A quién llamar                 │ │
│ │ …                              │ │
│ │ ────────────────────────────── │ │  border-t linea
│ │ Quién es                       │ │  h2 text-xl bold turquesa
│ │ Le dicen Tita. Fue costurera…  │ │  text-lg
│ │                                │ │
│ │ Sus remedios                   │ │
│ │ ▌Esto lo escribe la familia.   │ │  borde izq. atenta, text-base
│ │ ▌No reemplaza la indicación    │ │
│ │ ▌del médico.                   │ │
│ │ 08:00 con el desayuno: 1       │ │  text-lg, horas en cifras
│ │ pastilla blanca de la caja…    │ │
│ └────────────────────────────────┘ │
```

En pantalla ancha, igual que MATU-23 3.11: la hoja crece hacia abajo, la columna de datos no cambia.

### 7.2 Criterios verificables del relevo

- La página sigue sin ningún `turquesa` macizo y la hoja sigue siendo la única superficie con sombra.
- Un acceso creado sin secciones se ve idéntico a MATU-23 3.11.
- Si la sección Sus remedios está en la página, el aviso está a la vista sin tocar nada, antes del texto, y el lector de pantalla lo lee antes del contenido.
- Quitar una sección en la app hace que, tras «Actualizar», desaparezca de la hoja sin dejar título.
- A 320 px con texto al 200 %: sin desplazamiento horizontal.

---

## 8. Tokens y componentes

**Ningún token nuevo.** Se usan: `papel`, `hoja`, `tinta`, `tenue`, `pino` (y su alias `turquesa` en `web/`), `rocio`, `linea`, `borde`, `ok`, `atenta`, `atenta-fondo`, `pronto`, `pronto-fondo`; `titular`, `renglones`, `cifras`; `animate-aparecer`.

| Componente | Estados nuevos o cambiados |
|---|---|
| Tarjeta de sección | normal; con aviso (remedios); foco en su botón |
| Botón agregar sección | secundario: normal, foco, presionado |
| Editor de sección | los de MATU-39 3.7, más tope 500/800 y aviso de remedios |
| Confirmación de quitar | cerrada, abierta, quitando (`aria-busy`), error |
| `Boton` variante peligro | Si no existe en `web/src/compartido/ui/Boton.tsx`: secundario con texto `pronto` y anillo `pronto`, foco `outline-pronto` (contraste 3:1 sobre `hoja` en los dos temas). El frontend lo agrega al componente, no a mano en la pantalla |
| Casilla «Incluir Sus remedios» | desmarcada, marcada, foco, con confirmación abierta |
| Chips de secciones al compartir | marcada (cuadrado con `Check`), desmarcada, foco |
| Nota atenta con `Info` | ya existe la `Nota tono="atenta"`; solo cambia el ícono por prop |

---

## 9. Accesibilidad (además de MATU-39 y MATU-23)

- Todo lo que se toca mide al menos 48 × 48 px (`min-h-12`), incluidos los chips, la casilla de remedios y «Quitar».
- Ningún estado solo por color: sección agregada = tiene texto y botón «Editar»; chip marcado = cuadrado con check; aviso = palabras.
- Contraste: `atenta` sobre `atenta-fondo` y `tinta` sobre `atenta-fondo` ya cumplen 4,5:1 en los dos temas (se verifica en la revisión); el borde `atenta` de 4 px cumple 3:1 sobre `hoja`.
- Foco: al guardar o quitar, al `h1` de `/ficha`; al abrir una confirmación, a su título; al cerrarla, al control que la abrió.
- Los avisos de remedios no son `role="alert"`: son texto estático. Las confirmaciones de guardado sí van en `role="status"`.
- Con `prefers-reduced-motion`, todo inmediato.
- Ningún texto relevante bajo 1 rem; la fecha y la hora de autoría pueden ir en `text-sm` como hoy.

---

## 10. Textos exactos, listos para `lenguaje.md`

### 10.1 Aprobados (03/11)

**Títulos y preguntas guía:** los de la sección 2.
**Ejemplos:** los de la sección 2, precedidos de «Por ejemplo: » y entre «».
**Ayuda de las seis:** «No hace falta escribir diagnósticos ni enfermedades. Escribe lo que ayuda a cuidar».
**Ayuda de alergias** (Comer y beber, Sus remedios): «Si tiene alergia a algún remedio o alimento, anótalo aquí».
**Aviso de remedios:** «Esto lo escribe la familia. No reemplaza la indicación del médico.»
**Casilla al compartir:** «Incluir Sus remedios».
**Ayuda de la casilla:** «Quien te reemplaza verá qué remedios toma y a qué hora. Márcalo solo si va a dárselos o a estar a cargo de ellos.»
**Confirmación:** «Vas a compartir sus remedios con `{nombre}` hasta el `{DD/MM/AAAA}`. Puedes cortar el acceso cuando quieras.»
**Contador:** «`{n}` de 500 caracteres» · «`{n}` de 800 caracteres».

Nota de puntuación: la ayuda y la de alergias se aprobaron sin punto final; en pantalla van con punto, como el resto de las ayudas. Lo confirma quien edita `lenguaje.md`.

### 10.2 Aprobados por Jorge el 03-11 (antes [PROPUESTO])

| Dónde | Texto |
|---|---|
| Ficha, título del bloque | «Más sobre `{nombre_pila}`» |
| Ficha, bajada | «Si quieres, cuenta más para que quien te reemplace conozca a `{nombre_pila}`. Agrega solo lo que te sirva, cuando tengas tiempo.» |
| Ficha, lo agregado | «Agregaste 1 sección.» · «Agregaste `{n}` secciones.» |
| Ficha, encabezado de las no agregadas | «Puedes agregar» |
| Ficha, botones | «Agregar «`{título}`»» (nombre accesible) · «Editar «`{título}`»» |
| Ficha, vista previa | «Cada relevo ve solo las secciones que eliges al compartir.» |
| Editor, sobre el título | «Más sobre `{nombre_pila}`» |
| Guardado, primera vez | «Agregaste «`{título}`».» |
| Guardado, cambio | «Guardamos «`{título}`».» |
| Guardado, con accesos vigentes | «Quien ya tiene un enlace no la verá. Para que la vea, crea un enlace nuevo.» |
| Quitar, botón | «Quitar «`{título}`»» |
| Quitar, pregunta | «¿Quitar «`{título}`»?» |
| Quitar, texto | «Se borra lo que escribiste en esta sección. Quien tenga un enlace dejará de verla. No se puede deshacer.» |
| Quitar, botones | «Quitar y borrar» · «Dejarla como está» |
| Quitar, en curso | «Quitando…» |
| Quitar, hecho | «Quitaste «`{título}`».» |
| Quitar, 412 sin versión (antes «404», corregido) | ««`{título}`» ya no estaba en la ficha.» |
| Quitar, 412 | «`{autor}` cambió «`{título}`» mientras la ibas a quitar» · «Esta es la versión que guardó `{autor}`:» · «Quitarla igual» · «Dejarla como está» |
| Compartir, base | «Siempre ve» · «Su día, Si se altera y A quién llamar.» |
| Compartir, secciones | «¿Qué más puede ver?» · «Elige las secciones que le sirven.» |
| Compartir, confirmación | «Sí, crear el enlace» · «No incluir sus remedios» |
| PIN y Enlaces | «Ve su día, si se altera, a quién llamar, `{secciones en minúscula}`.» · «Si agregas una sección después, `{nombre}` no la verá. Para que la vea, crea un enlace nuevo.» |

### 10.3 Aprobados por Jorge el 03-11 (revisión de MATU-50; en lenguaje.md 14.4 y 5.4)

| Dónde | Texto |
|---|---|
| Ficha, bajada (lenguaje 5.4) | «Tres campos cortos para que quien te reemplace sepa qué hacer. Cada campo se guarda por separado.» |
| Quitar 412, «Dejarla como está» | «Dejaste «`{título}`» como la guardó `{autor}`.» |
| Guardar 412 sin versión, título | «Otra persona quitó «`{título}`» mientras escribías» |
| Guardar 412 sin versión, texto | «Lo que escribiste no se guardó. Puedes agregarla de nuevo con tu texto.» |
| Guardar 412 sin versión, botones | «Agregarla de nuevo» · «Dejarla quitada» |
| Guardar 412 sin versión, al pie | «Si quieres, copia lo que escribiste antes de elegir.» |
| Guardar 412 sin versión, confirmaciones | «Agregaste «`{título}`».» + frase de los enlaces · «Dejaste «`{título}`» quitada.» |
| Sección, 422 de largo | «Esta sección admite hasta `{tope}` caracteres. Acorta un poco el texto para guardarlo.» |

Revisados contra los términos prohibidos (diagnóstico, conducta, incidente, deterioro, incontinencia): «diagnósticos» aparece solo en la ayuda aprobada, como lo que **no** se pide. Ningún texto asume el género de la persona cuidada ni de quien usa la app.

---

## 11. Cómo la voy a revisar (MATU-50)

Con la app funcionando, a 360, 1280 y 1920 px, tema claro y oscuro, y texto al 200 % a 320 px:
1. Ficha sin secciones, con dos y con las seis; que no aparezca ningún «de 6» ni «incompleta».
2. Editor de Comer y beber (ayuda de alergias) y de Sus remedios (aviso arriba, tope 800, contador al 90 %).
3. Quitar: confirmación, 204, 404 y 412.
4. Compartir con 0 secciones, con secciones y con remedios marcados (confirmación sin petición previa).
5. `/r` con y sin secciones, con Sus remedios (aviso visible antes del texto).
6. Contraste del aviso `atenta` en los dos temas, foco visible y 48 px en cada control nuevo.
