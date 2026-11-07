# MATU-44 · Retirar una autorización · Especificación de diseño

**Versión 1.3 · 07/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Cambios de la 1.1:** las decisiones de Jorge del 06-11 sobre P1 a P8 (sección 11) y los nombres reales del contrato de MATU-44 (`docs/api/openapi.json` y README, decisiones 123 a 135, sección 7).

**Cambios de la 1.3:** el ícono de estado del bloque va en línea en modo angosto (3.3).

**Cambios de la 1.2, tras la revisión visual del 07-11:** A1 y A2 quedan resueltas en el contrato (decisiones 127 y 130) y sale la nota provisional de 3.6. Se confirman cuatro decisiones del frontend (sección 0.1). Se agregan tres reglas que la revisión mostró que faltaban: el punto final va pegado a la fecha (3.4), la confirmación no se cierra con un segundo `Esc` mientras retira (4.4) y la espera de 5.1 y 5.2 no cambia el título ni pierde el foco (5.1).

**Historia:** Carmen puede retirar, desde Grupo familiar, la autorización para guardar la ficha de María o la autorización para calcular sus insumos. Retirar la de la ficha corta para siempre todos sus enlaces de relevo. Lo guardado queda sin que nadie lo vea y se borra a los 90 días si nadie vuelve a autorizar.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` (sin agregar ninguno) · las decisiones de Jorge del 06-11 · el borrador de la sección 22 del analista normativo, aprobado por Jorge · el contrato de MATU-44 (decisiones 123 a 135) · `docs/lenguaje.md` del repositorio MATU (secciones 2, 6, 8, 9, 9.1, 13 y 18) · `docs/legal/politica-privacidad.md` (secciones 8 y 10) · las especificaciones de MATU-36 (3.1 y 3.6.2), MATU-39 (2, 3.5 y 5), MATU-48 (5) y MATU-60 · el código de `web/src/familia/` (`Shell.tsx`, `ui.tsx`, `Alta.tsx`, `Insumos.tsx`, `Compartir.tsx`, `Ficha.tsx`, `textos.ts`) y `web/src/compartido/ui/Anuncios.tsx` y `Boton.tsx`.

**Marcas de los textos:** sin marca, el borrador aprobado tal cual · **[AJUSTE]** cambié el borrador · **[NUEVO]** no estaba en el borrador · **[L n]** ya está en `lenguaje.md`.

---

## 0. Lo que estaba abierto

Nada queda abierto en el contrato.

| # | Qué faltaba | Cómo se resolvió |
|---|---|---|
| A1 | El pagador y el observador no recibían el estado (P2) | **Resuelta, decisión 127.** `GET …/consentimientos` responde a los cuatro roles. El pagador y el observador reciben `AutorizacionesPersonaResumen` con `AutorizacionVistaResumen`, la misma vista sin `calidad_otorgante` |
| A2 | Después del día 90 la ficha respondía 404 al volver a autorizar, contra P8 | **Resuelta, decisión 130.** La ficha queda en blanco, en 0 de 3 y sin secciones. Lo borrado no vuelve, la primera escritura crea una clave nueva y los enlaces cortados siguen cortados |

### 0.1 Decisiones del frontend, confirmadas

| Decisión | Veredicto |
|---|---|
| En 6.4, para `admin` y `cuidador`, se reemplaza la última oración («Pídele a quien administra el grupo que la registre.») por «La puedes volver a autorizar desde Grupo familiar.» | **Confirmada.** Es lo que pide 4.5, y ya está en `lenguaje.md` |
| El 404 general (lenguaje 8) va en una `Nota tono="rocio"` con `Lock` cuando Grupo familiar se queda sin personas y cuando volver a autorizar los insumos responde 404 | **Confirmada.** Es el patrón de «sin acceso» de MATU-39 5.6, sin decir por qué. En Grupo familiar ese caso solo ocurre si todas las personas responden 404: sin personas, el ruteo de MATU-39 5.4 actúa antes |
| «Cargando…» pasados 400 ms en 5.1 | **Confirmada**, con la regla nueva de 5.1: mientras carga, el título es el de la pantalla que se abre, no «Grupo familiar», y el foco queda en ese `h1` |
| `Permiso` de Insumos sigue preseleccionando `cuidador_de_hecho` y 5.1 no preselecciona | **Confirmada.** 5.2 reutiliza `Permiso` sin cambios (P3), y la preselección es la aprobada en MATU-36. 5.1 sigue al alta, que no preselecciona. La diferencia se acepta: unificarla cambiaría Insumos

---

## 1. Para quién y qué

**Carmen** cuida a María y administra el grupo. Un día decide, o María le pide, que MATU deje de guardar la ficha, o deje de calcular los insumos. Lo hace desde el teléfono, con una mano, sin saber de leyes. Tiene que entender en una lectura **qué se corta ahora, qué no vuelve y qué todavía puede recuperar**, y confirmar una sola vez.

**Rodrigo**, también cuidador, puede hacer lo mismo. **Quien paga** u **observa** ve el estado y las fechas, sin poder cambiarlos (P2).

**Rosa**, que tenía un enlace, no ve nada nuevo: la próxima vez que mire la ficha recibe el «Ya no está disponible» de siempre (lenguaje 7.3, 410 `relevo-revocado`). Esta historia no cambia la página del relevo.

**Tres momentos:**
1. **Ver** los dos permisos en Grupo familiar (sección 3).
2. **Retirar** uno, con una sola confirmación (sección 4).
3. **Volver a autorizar**, con el mismo flujo del alta (sección 5).

---

## 2. Grupo familiar en `web/` (P1)

Grupo familiar no existía en `web/`, solo en la demo (`Demo/src/familia/Grupo.tsx`). Jorge aprobó una **cuarta sección mínima**: solo las personas cuidadas y sus dos permisos. Sin integrantes ni relevos, que no tienen contrato.

### 2.1 Ruta y navegación

| Ruta | Pantalla | Quién |
|---|---|---|
| `/grupo` | Grupo familiar (sección 3) | Todos los roles |
| `/grupo/autorizar-ficha` | Volver a autorizar la ficha (5.1) | `admin` y `cuidador`. Otro rol, o sin una persona elegida con la ficha en `retirada` o `borrada`, redirige a `/grupo` |
| `/grupo/autorizar-insumos` | Volver a autorizar los insumos (5.2) | Igual, con los insumos en `retirada` o `borrada` |

- **Barra de secciones:** una cuarta entrada al final, después de Compartir. `texto` «Grupo familiar» **[L 6.4]**, `corto` «Grupo» **[DEMO]**, ícono `Users` de lucide, ruta `/grupo`. Visible para todos los roles. `seccionDe` reconoce `/grupo` y sus dos subrutas. Sin pista de estado.
- En el teléfono la barra pasa a **cuatro columnas** (`telefono:grid-cols-4`, que hoy falta en el mapa de `columnas` de `Shell.tsx`). A 360 px cada celda mide unos 88 px, y «Compartir» en `text-sm` cabe en una línea. Con menos secciones visibles, el mapa ya resuelve 2 y 3 columnas.
- **`<title>`:** «Grupo familiar · MATU» en las tres rutas, nunca con nombres (MATU-39 2.5).
- Las rutas no llevan el id de la persona. Al tocar «Volver a autorizar» de una persona, la app la **elige** en memoria (lo mismo que hace el selector de `Shell.tsx`) y navega. Si se recarga una subruta, no hay estado y redirige a `/grupo`, como `/empezar/autorizacion` sin borrador.

### 2.2 Datos al abrir

- Las personas del grupo: `GET /v1/grupos/{grupo_id}/personas-cuidadas`, como hoy.
- Por cada persona: `GET /v1/personas-cuidadas/{persona_id}/consentimientos` → `AutorizacionesPersona`, con `autorizaciones` siempre de dos ítems, en este orden: `plan_cuidado` (el bloque de la ficha) y `consumo` (el de los insumos). Cada `AutorizacionVista` trae `estado`, `otorgado_en`, `revision_vence_en`, `revocado_en`, `borrado_en` y `borrada`.
- Solo para `admin` y `cuidador`, y solo por cada persona con la ficha en `vigente` o `revision_vencida`: cuántos enlaces hay hoy, con `GET …/accesos-relevo?estado=vigente&limite=100`, contando los `items`. Se pide al abrir la pantalla, no al abrir la confirmación, para que la confirmación no espere ni salte. Si falla, la confirmación omite esa frase (4.3) y la pantalla sigue.
- Nada se guarda entre visitas. Al volver a `/grupo` se pide todo de nuevo.

---

## 3. Grupo familiar (`/grupo`)

**Objetivo, desde Carmen:** saber qué permisos diste para María y, si quieres, retirar uno.

**Jerarquía:**
1. «Grupo familiar» y la bajada.
2. El nombre de cada persona cuidada.
3. Sus dos bloques, cada uno con su estado en una frase y su botón.

**Acción principal en `turquesa` macizo:** ninguna. Retirar y volver a autorizar son acciones raras, no el camino de la pantalla, y con dos bloques por persona habría dos o más macizos. Igual que Enlaces (MATU-48 5).

### 3.1 Esquema a 360 px (admin, ficha y consumo autorizados)

```
┌────────────────────────────────────┐
│ (esqueleto MATU-39)                │
├────────────────────────────────────┤
│ Grupo familiar                     │  h1 titular text-3xl
│ A quién cuidan en Familia Soto y   │  bajada text-base text-tenue
│ qué permisos dieron.               │  max-w-prose
│                                    │
│ María Soto                         │  h2 text-xl font-bold
│ ┌────────────────────────────────┐ │
│ │ Permiso para guardar su ficha  │ │  h3 text-lg font-bold
│ │ ◈ Autorizada el 04/11/2026.    │ │  ShieldCheck text-ok + text-base
│ │ [ Retirar la autorización ]    │ │  Boton peligro, self-start
│ └────────────────────────────────┘ │  bg-hoja ring-1 ring-linea rounded-xl
│ ┌────────────────────────────────┐ │
│ │ Permiso para calcular sus      │ │
│ │ insumos                        │ │
│ │ ◈ Autorizado el 05/11/2026.    │ │
│ │ [ Retirar la autorización ]    │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
│ Ficha  Insumos  Compartir  Grupo   │  barra fija, cuatro columnas
```

**Después de retirar la ficha** (el bloque no cambia de lugar):

```
│ ┌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┐ │  bg-papel border-2 border-dashed
│ ╎ Permiso para guardar su ficha  ╎ │  border-borde rounded-xl
│ ╎ ┌────────────────────────────┐ ╎ │
│ ╎ │ ✓ Autorización retirada.   │ ╎ │  Nota tono ok, recibe el foco
│ ╎ │   Cortamos 2 enlaces.      │ ╎ │
│ ╎ └────────────────────────────┘ ╎ │
│ ╎ ⊘ Autorización retirada el     ╎ │  ShieldOff text-tenue + text-base
│ ╎   06/11/2026. Si no vuelves a  ╎ │
│ ╎   autorizar, lo guardado se    ╎ │
│ ╎   borra el 04/02/2027.         ╎ │
│ ╎ [ Volver a autorizar ]         ╎ │  Boton secundario
│ └╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┘ │
```

**Pagador u observador** (3.6):

```
│ ┌────────────────────────────────┐ │
│ │ Permiso para guardar su ficha  │ │
│ │ ◈ Autorizada el 04/11/2026.    │ │
│ │ Puede retirarla quien          │ │  text-base text-tenue
│ │ administra el grupo o quien    │ │
│ │ cuida a María.                 │ │
│ └────────────────────────────────┘ │
```

### 3.2 Pantalla ancha

- La página usa el `Pagina` de `ui.tsx`. El contenido, en `max-w-5xl`.
- Cada persona es una `section` con su `h2`. Debajo, los dos bloques en `grid grid-cols-1 @3xl/main:grid-cols-2 gap-6 items-start`. A 1280 px con la barra lateral (contenedor de unos 906 px) quedan dos columnas de unos 440 px.
- Con más de una persona, las secciones se apilan con `gap-10`, en el orden de la API.
- Los botones, al ancho de su texto (DISENO.md 5).

```
┌──────────────┬─────────────────────────────────────────────────────────────┐
│ (M) MATU     │ Cuidas a María Soto                     Tu cuenta   Salir   │
│ Ficha        ├─────────────────────────────────────────────────────────────┤
│ Insumos      │ Grupo familiar                                              │
│ Compartir    │ A quién cuidan en Familia Soto y qué permisos dieron.       │
│ Grupo famil. │                                                             │
│              │ María Soto                                                  │
│              │ ┌──────────────────────────┐  ┌──────────────────────────┐  │
│              │ │ Permiso para guardar su  │  │ Permiso para calcular    │  │
│              │ │ ficha                    │  │ sus insumos              │  │
│              │ │ ◈ Autorizada el 04/11/26 │  │ ◈ Autorizado el 05/11/26 │  │
│              │ │ [Retirar la autorización]│  │ [Retirar la autorización]│  │
│              │ └──────────────────────────┘  └──────────────────────────┘  │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

### 3.3 Un bloque de permiso

| Pieza | Construcción | Texto |
|---|---|---|
| Contenedor | `section aria-labelledby={id del h3}`, `flex flex-col gap-3 rounded-xl px-4 angosto:px-2 py-4`. Con `vigente` o `revision_vencida`: `bg-hoja ring-1 ring-linea`. Con `retirada`, `borrada` o `sin_autorizar`: `bg-papel border-2 border-dashed border-borde`, el mismo trato que un insumo «Sin seguir» (MATU-36 5) | — |
| Título | `h3 text-lg font-bold break-words` | «Permiso para guardar su ficha» · «Permiso para calcular sus insumos» |
| Estado | `p flex gap-2 text-base`, ícono `size-5 shrink-0 mt-0.5 aria-hidden`. Cada estado con **ícono distinto y frase**, nunca solo color. **En modo angosto el ícono va en la primera línea de la frase**, como en `MensajeError` (`angosto:block` en el `p`, `angosto:inline` en el ícono): con el ícono en su columna, a 320 px con el texto al 200 % «Autorización» se parte en «Autorizació / n» y la fecha toca el borde (revisión del 07-11) | Tabla 3.4 |
| Confirmación o aviso | `Nota`, solo después de una acción (3.5) | Tabla 3.5 |
| Botón | `Boton`, `self-start`, sin ícono. Solo `admin` y `cuidador` | Tabla 3.4 |
| Quién puede retirarla | Solo pagador y observador, `p text-base text-tenue` | 3.6 |

**Nombre accesible de los botones.** En la página hay dos o más botones «Retirar la autorización» y dos o más «Volver a autorizar». Cada uno lleva un `aria-label` que **empieza con el texto visible** (WCAG 2.5.3): «Retirar la autorización de la ficha de `{nombre_pila}`», «Retirar la autorización de los insumos de `{nombre_pila}`», «Volver a autorizar la ficha de `{nombre_pila}`», «Volver a autorizar los insumos de `{nombre_pila}`» **[NUEVO]**.

### 3.4 Estados de un bloque, por `estado`

Las fechas, `DD/MM/AAAA` en hora de Chile, cada una en su `cifras`. «Autorizada» es la ficha y «Autorizado» el permiso de los insumos, como en el borrador.

**El punto que cierra la frase va dentro del mismo `cifras` que la fecha** (por ejemplo `<span class="cifras">05/11/2026.</span>`). Si queda fuera, en modo angosto el punto baja solo a un renglón propio (revisión del 07-11). Vale para todas las fechas de esta pantalla, de 5.1 y de 5.2.

| `estado` | Ícono | Frase y fechas | Botón (`admin` y `cuidador`) |
|---|---|---|---|
| `vigente` | `ShieldCheck` `text-ok` | Autorizada el `{otorgado_en}`. · Autorizado el `{otorgado_en}`. | `peligro` «Retirar la autorización» |
| `revision_vencida` | `Hourglass` `text-atenta` | Autorizada el `{otorgado_en}`. Hay que renovarla desde el `{revision_vence_en}`. **[NUEVO]** (insumos: «Autorizado el `{otorgado_en}`. Hay que renovarlo desde el `{revision_vence_en}`.») | `peligro` «Retirar la autorización» (P6). Sin botón de renovar (P5: queda fuera) |
| `retirada` | `ShieldOff` `text-tenue` | Autorización retirada el `{revocado_en}`. Si no vuelves a autorizar, lo guardado se borra el `{borrado_en}`. | `secundario` «Volver a autorizar» |
| `borrada` | `ShieldOff` `text-tenue` | Autorización retirada el `{revocado_en}`. Lo guardado se borró el `{borrado_en}`. **[NUEVO]** | `secundario` «Volver a autorizar» |
| `sin_autorizar` (solo insumos) | `ShieldQuestion` `text-tenue` | Sin permiso todavía. Se pide al anotar el primer insumo. | Ninguno (retirar respondería 404, decisión 123) |

- **La pantalla no suma 90 días ni decide qué se borró** (decisión 127). La frase sale de `estado`, y la fecha de borrado de `borrado_en`. Con `borrado_en` en `null` en `retirada` (no debería pasar), la frase termina en «Si no vuelves a autorizar en 90 días, lo guardado se borra.» **[NUEVO]**.
- Con `vigente` y `borrada: true` (se volvió a autorizar después del día 90), el bloque es el de `vigente`. Lo de antes no vuelve, y eso ya lo dijo la confirmación de 5.3.
- El ícono de estado mide 3:1 o más sobre su fondo en los dos temas: `ok`, `atenta` y `tenue` pasan con margen sobre `hoja` y `papel` (DISENO.md 1).

### 3.5 Avisos dentro de un bloque

Van entre el título y la frase de estado, solo después de una acción, y desaparecen al salir de la pantalla.

| Cuándo | Componente | Texto |
|---|---|---|
| Retiro hecho, ficha (200) | `Nota tono="ok"` (`CircleCheck`), `rol="status"`, `tabIndex={-1}`, recibe el foco | Autorización retirada. Cortamos `{enlaces_cortados}` enlaces. (Con 1: «Autorización retirada. Cortamos 1 enlace.» Con 0: «Autorización retirada. No había enlaces que abrieran.») **[AJUSTE]** |
| Retiro hecho, insumos (200) | Igual | Autorización retirada. Ya no calculamos ni avisamos por los insumos de `{nombre_pila}`. |
| 409 `/errores/ya-retirada` | `Nota tono="rocio"` (`Info`), `rol="status"`, `tabIndex={-1}`, recibe el foco | Otra persona de tu grupo ya retiró esta autorización. |
| Volvió a autorizar (vuelve de 5.1 o 5.2) | `Nota tono="ok"`, `rol="status"`. El foco va al `h1` por la regla de ruta | Tabla 5.3 |

- `{enlaces_cortados}` es el de `RetiroAutorizacion`, **no** el que contó la pantalla al abrir. La API corta también los bloqueados y los en pausa (decisión 124), así que puede ser mayor que «Hoy abren `{n}`».
- Con el 200, el bloque se redibuja con `RetiroAutorizacion.autorizacion`, que ya viene con `estado: retirada`. No hace falta pedir de nuevo la lista.

### 3.6 Pagador y observador (P2)

- **Sin ningún botón**, ni «Retirar la autorización» ni «Volver a autorizar».
- Ven el mismo título, el mismo ícono y la misma frase de 3.4, con las mismas fechas. **Nunca la calidad de quien autorizó** (ni `calidad_otorgante`, ni «representante legal», ni «cuidador de hecho»).
- Debajo, en `text-base text-tenue`, una línea por estado **[NUEVO]**:

| `estado` | Línea |
|---|---|
| `vigente` o `revision_vencida` | Puede retirarla quien administra el grupo o quien cuida a `{nombre_pila}`. |
| `retirada` o `borrada` | Puede volver a autorizarla quien administra el grupo o quien cuida a `{nombre_pila}`. |
| `sin_autorizar` | Ninguna: «Se pide al anotar el primer insumo» ya lo dice |

- La frase de `retirada` les dice «Si no vuelves a autorizar…», que no pueden hacer. Para estos dos roles va en impersonal **[NUEVO]**: «Autorización retirada el `{revocado_en}`. Si nadie vuelve a autorizar, lo guardado se borra el `{borrado_en}`.»
- Los datos salen de `AutorizacionesPersonaResumen` (decisión 127), que no trae `calidad_otorgante`.
- `{nombre_pila}`: la vista del pagador y del observador no trae `nombre_pila`, así que la frase usa lo que devuelve `nombrePilaDe` («María Soto»). Se acepta: se lee bien y no exige otro dato.

### 3.7 Estados de la pantalla

| Estado | Qué se ve |
|---|---|
| Cargando | «Cargando…» **[L, MATU-39 5.1]** pasados 400 ms, `role="status"`, en lugar de las secciones. Sin esqueleto |
| Error al cargar | `Nota tono="atenta"` con `CloudOff`, `rol="alert"`: «No pudimos traer los permisos. Revisa tu conexión e inténtalo de nuevo.» **[NUEVO, como L 9.1]** y «Intentar de nuevo» **[L 15]**, secundario |
| Sin personas | La regla de MATU-39 5.4: admin y cuidador van a `/empezar/persona`, el resto ve la nota de 5.4 |
| 404 de una persona | Esa persona sale de la lista. Si no queda ninguna, MATU-39 5.6, sin decir por qué |
| 401 | El cliente de MATU-39 |

---

## 4. La confirmación de retirar

**Objetivo, desde Carmen:** entender en una lectura qué pasa al retirar, y confirmar o arrepentirse.

**Jerarquía:**
1. La pregunta, con el nombre de la persona.
2. Lo que pasa ahora y lo que no vuelve.
3. Lo que se puede recuperar y lo que no cambia.
4. «Retirar la autorización» y «No retirar».

Una sola confirmación. Sin contraseña, sin motivo y sin escribir el nombre (decisión del 06-11). Al confirmar: `POST /v1/personas-cuidadas/{persona_id}/consentimientos/{finalidad}/retiro`, sin cuerpo, con `X-Grupo-Id`, y `finalidad` `plan_cuidado` o `consumo` (decisión 123).

### 4.1 Construcción

Es el patrón del diálogo de eliminar de MATU-36 (3.6.2), con tres cambios: más ancho, con desplazamiento propio y con el foco inicial en el título.

- `<dialog>` modal nativo con `showModal()`, `aria-labelledby` (el `h2`) y `aria-describedby` (la lista).
- `m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-lg max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl bg-hoja p-6 angosto:px-2 angosto:py-4 text-tinta backdrop:bg-tinta/40`. `max-w-lg` y no `max-w-md`, porque el texto de la ficha tiene cinco puntos y el de los insumos cinco. El `calc` es geometría, como en MATU-36. Sin animación.
- Título: `h2 tabIndex={-1} text-xl font-bold break-words outline-none`.
- Texto: `ul` con `list-disc ps-5 marker:text-tenue flex flex-col gap-2 text-base leading-relaxed max-w-prose`. Un punto por `li`. **Solo lo que no vuelve va en `font-bold`:** en la ficha, «Un enlace cortado no vuelve a abrir, aunque autorices de nuevo.», y en los insumos, «Una lista que ya imprimiste o compartiste no se borra…».
- Región de error: `div role="alert" className="empty:-mb-4"`, montada vacía con el diálogo, igual que MATU-36. Con `showModal` lo de fuera queda inerte, también las regiones vivas de `main.tsx`.
- Botones con `Acciones`: primero «Retirar la autorización», **`bg-pronto text-papel` macizo**, misma forma que el principal (el botón de peligro de MATU-36 5). Después «No retirar», de texto (`text-turquesa underline`, `min-h-12`, `px-2`). Es el único macizo del diálogo, y no es `turquesa` porque no es una acción de avance.

**Recomendación para el frontend:** hoy el botón de eliminar repite sus clases dentro de `DialogoEliminar`. Conviene una variante de `Boton` para los dos diálogos (por ejemplo `peligroPrincipal`, `bg-pronto text-papel`), con el foco base y el gerundio de `Boton`. No es un token nuevo: son `pronto` y `papel`.

### 4.2 Esquema a 360 px

**Ficha:**

```
┌────────────────────────────────────┐
│ ¿Retirar la autorización de la     │  h2 text-xl font-bold, foco inicial
│ ficha de María?                    │
│                                    │
│ • Nadie del grupo podrá ver ni     │  ul text-base
│   cambiar su ficha.                │
│ • Se cortan ahora todos sus        │
│   enlaces de relevo. Hoy abren 2.  │
│   Si alguien tiene la ficha        │
│   abierta, se le cierra cuando     │
│   vuelva a mirarla. No recibe      │
│   aviso.                           │
│ • Un enlace cortado no vuelve a    │  font-bold
│   abrir, aunque autorices de nuevo.│
│ • Lo escrito queda guardado sin    │
│   que nadie lo vea. Si no vuelves  │
│   a autorizar en 90 días, se borra.│
│ • La autorización de los insumos   │
│   no cambia.                       │
│                                    │
│ [ Retirar la autorización ]        │  bg-pronto text-papel
│ No retirar                         │  texto, baja de renglón si no cabe
└────────────────────────────────────┘
```

**Insumos:**

```
┌────────────────────────────────────┐
│ ¿Retirar la autorización de los    │
│ insumos de María?                  │
│                                    │
│ • Dejamos de calcular cuándo se    │
│   acaban y de avisar, desde ahora. │
│   Tampoco avisamos al resto del    │
│   grupo.                           │
│ • Nadie del grupo podrá ver los    │
│   insumos anotados.                │
│ • Lo anotado queda guardado sin    │
│   que nadie lo vea. Si no vuelves  │
│   a autorizar en 90 días, se borra.│
│ • Una lista que ya imprimiste o    │  font-bold
│   compartiste no se borra: quedó   │
│   fuera de MATU.                   │
│ • Su ficha y los enlaces de relevo │
│   no cambian.                      │
│                                    │
│ [ Retirar la autorización ]        │
│ No retirar                         │
└────────────────────────────────────┘
```

En pantalla ancha es el mismo diálogo, centrado, de 32 rem como máximo. Los dos botones quedan en una fila.

### 4.3 Textos que se arman

| Punto | Regla |
|---|---|
| «Hoy abren `{n}`.» (ficha `vigente`) | `n` es el conteo de 2.2. Con 1: «Hoy abre 1.» Con 0: «Hoy ningún enlace abre.» Si el conteo falló, se omite esa frase **[AJUSTE]** |
| Ficha en `revision_vencida` (P6) | Los enlaces no abren (decisión 33), así que «Hoy abren `{n}`» sería falso. Se dice «Hoy están en pausa `{n}`.» Con 1: «Hoy está en pausa 1.» Con 0: «Hoy ningún enlace abre.» **[NUEVO]** |
| «La autorización de los insumos no cambia.» | Solo si los insumos están en `vigente` o `revision_vencida`. Si no, se omite **[AJUSTE]**: decir que no cambia algo que no existe confunde |
| «Su ficha y los enlaces de relevo no cambian.» (insumos) | Siempre |
| «Una lista que ya imprimiste o compartiste no se borra: quedó fuera de MATU.» (insumos, P7) | Siempre, en `font-bold`. La política lo dice en la sección 10, «La lista de insumos» **[NUEVO]** |

### 4.4 Estados de la confirmación

| Estado | Qué se ve | Foco |
|---|---|---|
| Abierta | El esquema de 4.2 | En el `h2`. Así, con la lista larga a 360 px o con el texto al 200 %, la pregunta se ve primero y no se desplaza fuera de la vista (APG, diálogo modal). `Tab` lleva a «Retirar la autorización» y luego a «No retirar» |
| En curso | El botón dice «Retirando…» con el mismo ancho y `aria-busy` (`Boton` con `ocupado`). **«No retirar» y `Esc` no hacen nada mientras tanto** (`aria-disabled` en «No retirar», `onCancel` con `preventDefault`): la petición ya salió y Carmen no debe creer que la canceló. **Un segundo `Esc` también:** Chrome deja anular solo el primer `cancel` después de un toque, y el segundo cierra el `<dialog>` igual. Por eso, si el diálogo recibe `close` con la petición en curso, se vuelve a abrir con `showModal()` y el foco vuelve al botón. Si no, un error de red quedaría dentro de un diálogo cerrado, sin que nadie lo vea | Se queda en el botón |
| 200 `RetiroAutorizacion` | Se cierra el diálogo. El bloque pasa a `retirada` con `autorizacion` y muestra la `Nota` de 3.5 con `enlaces_cortados` | En la `Nota` de confirmación |
| 409 `/errores/ya-retirada` | Se cierra el diálogo, se vuelve a pedir `GET …/consentimientos` y el bloque muestra la `Nota` rocío de 3.5 | En esa `Nota` |
| Red o 5xx | En la región del diálogo, `MensajeError`: «No pudimos retirar la autorización. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.» El botón vuelve a «Retirar la autorización» para reintentar. Si falla un corte, la API no escribe nada (decisión 124), así que la frase es verdad | Se queda en el botón |
| 404 (la persona ya no está, o cambió el rol) | Se cierra el diálogo y la pantalla vuelve a cargar (3.7) | En el `h1` |
| 401 | El cliente de MATU-39 | — |
| «No retirar» o `Esc` | Se cierra sin pedir nada | Vuelve al botón «Retirar la autorización» que la abrió |

**Sin interfaz optimista** (CLAUDE.md, agente 3, punto 4): el bloque cambia solo con la respuesta de la API.

### 4.5 Después de retirar

**Ficha:**
- La app saca de la memoria la ficha de esa persona (`fijar({ ficha: null })` si es la persona elegida) y deja `autorizacion: 'sin-consentimiento'`. Después del alta, ese 403 solo ocurre por un retiro (decisión 131), y `revision-vencida` sigue siendo «por renovar».
- **Ficha** (`/ficha` y sus campos), 403 `sin-consentimiento`: el aviso de lenguaje 6.4 de siempre. **Para `admin` y `cuidador` (P4)** el aviso termina en «La puedes volver a autorizar desde Grupo familiar.» **[NUEVO]** en lugar de «Pídele a quien administra el grupo que la registre.», y debajo, `Boton variante="secundario"` «Volver a autorizar» **[NUEVO]**, que elige la persona y lleva a `/grupo/autorizar-ficha`. Pagador y observador ven el texto de hoy, sin botón. Cierra el [PENDIENTE] de lenguaje 6.4.
- **Compartir** (`/compartir`) muestra lo mismo que hoy sin autorización: no se crea nada (decisión 18).
- **Enlaces** (`/compartir/enlaces`), con `sin-consentimiento`: arriba de la lista, en lugar del aviso de pausa, `Nota tono="rocio" borde` con `Unlink`, título «Se retiró la autorización de la ficha.» y cuerpo «Los enlaces se cortaron y no vuelven a abrir.» **[AJUSTE, solo de forma]**. Las tarjetas son las que da la API: todas en «Ya no abren», con «Cortado» y «Lo cortaron el…», sin «En pausa». Debajo de la nota, para `admin` y `cuidador`, `Boton variante="texto"` «Ver los permisos en Grupo familiar» **[NUEVO]** a `/grupo`. No es `atenta`: no hay nada que hacer para que vuelvan a abrir. **En modo angosto** la nota no puede medir más que su columna: a 320 px con el texto al 200 %, el borde, el ícono `size-6`, el hueco y «autorización» en negrita suman 154 px en 143 (revisión del 07-11). El ícono va en la primera línea del título, como en `MensajeError` (`angosto:inline`), o el título lleva `hyphens-auto`. Vale también para el aviso de pausa, que usa la misma nota.
- El aviso de pausa (`atenta`, con «En pausa» en las tarjetas) queda **solo** para `revision-vencida`, con la fila nueva de 9.1 (sección 10.2).

**Insumos (P3: la pantalla no cambia):**
- La pantalla de Insumos no guarda nada entre visitas. Al volver, `GET …/consumo` responde 403 con `finalidad: consumo` y Insumos muestra lo que ya muestra hoy: el permiso (MATU-36 3.1) para `admin` y `cuidador`, y «Falta el permiso…» (3.1.3) para el resto. **No se agrega ninguna línea.**
- El contexto (`estado.tsx`) no debe guardar ningún dato del consumo. Si alguna pieza lo guarda (por ejemplo, una pista de la barra), se vacía al retirar.

---

## 5. Volver a autorizar

Las dos usan `POST /v1/personas-cuidadas/{persona_id}/consentimientos` (decisión 128), con `finalidad` `plan_cuidado` o `consumo` y el mismo cuerpo de calidad, referencia y aviso que ya usan el alta y el permiso de los insumos.

### 5.1 La ficha (`/grupo/autorizar-ficha`, D2)

**Objetivo, desde Carmen:** volver a dar la autorización de la ficha, con las mismas declaraciones del alta.

**Es el cuerpo de `Autorizacion` de `Alta.tsx` sin el marco del alta.** Se reutiliza tal cual: el título, la bajada, la leyenda, las tres calidades de `CALIDADES` (`datos.ts`), la referencia del representante, el aviso del cuidador de hecho con su casilla y «Lo que declaras» con la declaración de la calidad elegida. **Ninguna calidad preseleccionada**, igual que el alta. Las declaraciones no cambian ni una palabra (lenguaje 13.2: cambiarlas es publicar otra versión de la política).

Cambia:
- Va dentro del esqueleto de la app (`ShellFamilia`), no de `MarcoAlta`: sin «Paso 4 de 4» ni la lista de pasos.
- Arriba, `Volver` «Volver a Grupo familiar» **[NUEVO]** a `/grupo`.
- Debajo de la bajada del alta, una frase según `estado`, en `text-base`, `max-w-prose`:
  - `retirada`: «Al autorizar de nuevo, vuelve lo que estaba escrito. Los enlaces que se cortaron no vuelven a abrir.» **[NUEVO]** (decisión 128)
  - `borrada` (P8): «Lo escrito antes se borró el `{borrado_en}`. La ficha empieza en blanco.» **[NUEVO]** (decisión 130)
- El botón, único `turquesa` macizo: «Acepto y vuelvo a autorizar» **[NUEVO]**, ocupado «Autorizando…» **[NUEVO]**. El del alta («Acepto y registro a `{nombre_pila}`») no sirve: María ya está registrada.

```
┌────────────────────────────────────┐
│ ‹ Volver a Grupo familiar          │  Volver, min-h-12
│ La autorización para guardar su    │  h1 titular text-3xl
│ ficha                              │
│ Lo que anotes sobre el cuidado de  │  bajada del alta, text-base tenue
│ María es información sensible…     │
│ Al autorizar de nuevo, vuelve lo   │  frase de estado, text-base
│ que estaba escrito. Los enlaces    │
│ que se cortaron no vuelven a abrir.│
│                                    │
│ Doy esta autorización porque…      │  GrupoOpciones, como el alta
│ ( ) María lo autoriza y yo lo …    │
│ ( ) Soy su representante legal     │
│ ( ) La cuido, sin ser su …         │
│ (aviso, referencia y declaración   │
│  según la calidad, como el alta)   │
│ [ Acepto y vuelvo a autorizar ]    │  principal
└────────────────────────────────────┘
```

En pantalla ancha, el mismo bloque en `max-w-3xl`, como el permiso de los insumos (MATU-36 3.1).

**Estados:**

| Estado | Qué se ve |
|---|---|
| Validación | Los mismos mensajes del alta («Elige en qué calidad das la autorización.», el de la referencia y el de la casilla) |
| 201 | Vuelve a `/grupo` con la `Nota` de 5.3. El bloque dice «Autorizada el `{hoy}`.» |
| 409 `autorizacion-vigente` | Otra persona ya autorizó: vuelve a `/grupo` con «Otra persona de tu grupo ya volvió a autorizar.» **[NUEVO]** en `Nota tono="rocio"` |
| 422 | «No pudimos guardar la autorización. Revisa lo que elegiste y vuelve a intentarlo.» **[NUEVO, como L 18]** en `Nota tono="pronto" rol="alert"` |
| Red o 5xx | Lenguaje 8, «No pudimos completar esto…» |
| Cargando la vista | «Cargando…» pasados 400 ms (confirmado). **Mientras carga, el `h1` ya es el de esta pantalla** («La autorización para guardar su ficha», o el título del permiso de los insumos en 5.2), no «Grupo familiar», y es el mismo elemento que queda al terminar de cargar. Así el foco que pone la regla de ruta no se pierde en el `body` cuando la vista llega. Pasa al entrar desde el aviso 6.4 de la ficha, que no trae la vista en memoria |
| 404 | MATU-39 5.6 |

### 5.2 Los insumos (`/grupo/autorizar-insumos`)

Mismo patrón: el cuerpo del componente `Permiso` de `Insumos.tsx` (MATU-36 3.1) **sin cambiarlo** (lo exporta o lo mueve a una pieza común el frontend), dentro del esqueleto, con:
- `Volver` «Volver a Grupo familiar» **[NUEVO]**.
- La frase de estado, bajo la bajada, **solo aquí y no en Insumos (P3)**:
  - `retirada`: «Si vuelves a dar el permiso antes del `{borrado_en}`, vuelve lo que estaba anotado.» (fila del borrador, que se mueve de Insumos a esta pantalla) **[AJUSTE]**
  - `borrada`: «Lo anotado antes se borró el `{borrado_en}`. Hay que anotar los insumos de nuevo.» **[NUEVO]** (decisión 128: autorizar tarde borra los perfiles primero)
- El botón y sus estados, los de MATU-36 3.1 («Acepto y continúo»). 409 `autorizacion-vigente` igual que 5.1.
- Al 201 vuelve a `/grupo` (no a Insumos) con la `Nota` de 5.3.

### 5.3 Confirmación al volver a autorizar

En `/grupo`, `Nota tono="ok"` con `rol="status"` justo debajo de la bajada de la página (lo primero después del `h1`, que recibe el foco por la regla de ruta). El caso sale del `estado` que tenía el bloque antes de autorizar.

| Caso | Texto |
|---|---|
| Ficha, desde `retirada` | Autorización registrada. Ya puedes ver y cambiar la ficha de `{nombre_pila}`. **[NUEVO]** |
| Ficha, desde `borrada` (P8) | Autorización registrada. La ficha de `{nombre_pila}` empieza en blanco. **[NUEVO]** |
| Insumos, desde `retirada` | Permiso guardado. Volvió lo que estaba anotado. **[NUEVO]** |
| Insumos, desde `borrada` | Permiso guardado. Ahora anota el primer insumo. **[L 18]** |

**Qué ve la familia después del día 90 (P8), confirmado:**
1. En Grupo familiar, con `estado: borrada`: «Autorización retirada el `{revocado_en}`. Lo guardado se borró el `{borrado_en}`.» y «Volver a autorizar».
2. Al volver a autorizar: «Lo escrito antes se borró… La ficha empieza en blanco.» antes de las declaraciones, para que no autorice esperando recuperar algo.
3. Después: «Autorización registrada. La ficha de `{nombre_pila}` empieza en blanco.» y la ficha con sus tres campos en «Sin completar» (MATU-39, 0 de 3), sin ningún rastro de lo anterior. **Lo de antes no vuelve.**
4. Los enlaces anteriores siguen en «Ya no abren», cortados. Para compartir se crea uno nuevo.

Esto coincide con P8 y con la decisión 130: `GET …/plan/ficha` responde 200 con 0 de 3 y sin secciones.

---

## 6. Accesibilidad visual, temas y reflujo

- **Áreas táctiles:** todos los botones con `Boton` (`min-h-12`, 51 px). «No retirar» y «Volver» con `min-h-12`. Ningún control bajo 48 × 48 px. En la barra del teléfono, cada sección mide 56 px de alto (MATU-39).
- **Foco:** el base, contorno de 3 px `turquesa` con 2 px de separación. El botón de peligro del bloque usa `focus-visible:outline-pronto` (ya en `Boton`). El macizo `pronto` del diálogo usa el foco base `turquesa` sobre `hoja`, como el de eliminar. El `h2` del diálogo y las `Nota` que reciben el foco no muestran contorno (`outline-none`): no son controles, y el lector anuncia su texto.
- **Estado nunca solo por color:** cada estado del bloque lleva su frase y un ícono distinto (`ShieldCheck`, `Hourglass`, `ShieldOff`, `ShieldQuestion`). La retirada además cambia la forma del bloque (borde punteado). Las confirmaciones llevan `CircleCheck` o `Info`, y los errores `CircleAlert`.
- **Contraste, a medir en la revisión:** `bg-pronto` con `text-papel`, 6,1:1 o más en claro (`#A8261B` con `#ECF3F2`) y cerca de 10:1 en oscuro (`#FFA395` con `#0D1719`), por cálculo. `pronto` sobre `hoja` del botón de peligro, 6,1:1 o más. Los íconos de estado, 3:1 o más.
- **Texto al 200 % a 320 px (160 px efectivos):** la app entra en `angosto:`, la barra vuelve arriba en columna, los bloques en una columna con `px-2`, el diálogo en `w-[calc(100%-1rem)]` con `px-2`, y se desplaza **dentro de sí mismo** (`max-h` y `overflow-y-auto`), nunca hacia el lado. Títulos y nombres con `break-words`. Las fechas, cada una en su `cifras`, en una frase que refluye (DISENO.md 2). Los dos botones del diálogo bajan de renglón con `flex-wrap`.
- **Temas claro y oscuro:** solo tokens, con sus valores de cada tema. El fondo del diálogo es `hoja` y el velo `tinta/40` en los dos.
- **`prefers-reduced-motion`:** el diálogo no tiene animación, y `animate-aparecer` de la página ya es inmediato.
- **Proyector:** ningún texto relevante bajo `text-base` (17 px). El tema claro para la presentación.

### 6.1 Anuncios

| Momento | Cómo se anuncia |
|---|---|
| Abrir la confirmación | El foco en el `h2`: el lector dice el nombre del diálogo y su descripción (`aria-describedby`, la lista). Sin anuncio aparte |
| En curso | `aria-busy` y el texto «Retirando…» en el botón con el foco. Sin anuncio aparte |
| Error | La región `role="alert"` del diálogo, montada vacía con él |
| 200, 409 y volver a autorizar | `Nota` con `rol="status"`, que usa las regiones vivas de `Anuncios.tsx`. Se monta **después** de cerrar el diálogo, cuando las regiones ya no están inertes. Es el patrón de «Enlace cortado» (MATU-48 5.4): la `Nota` se anuncia y recibe el foco |
| Error al cargar la pantalla | `Nota rol="alert"` |

### 6.2 Elementos en `turquesa` macizo por pantalla

| Pantalla | Cantidad |
|---|---|
| Grupo familiar, cualquier rol y estado | 0 |
| Confirmación de retirar | 0 (el macizo es `pronto`) |
| Volver a autorizar la ficha | 1: «Acepto y vuelvo a autorizar» |
| Volver a autorizar los insumos | 1: «Acepto y continúo» |
| Ficha sin autorización, admin o cuidador | 0 («Volver a autorizar» es secundario) |

---

## 7. El contrato que usa (decisiones 123 a 135)

| Para qué | Ruta y esquema | Lo que la pantalla usa |
|---|---|---|
| El estado de los dos bloques | `GET /v1/personas-cuidadas/{persona_id}/consentimientos` → `AutorizacionesPersona` (decisión 127) | `autorizaciones[0]` es `plan_cuidado` y `[1]` es `consumo`. De cada `AutorizacionVista`: `estado` (`vigente`, `revision_vencida`, `retirada`, `borrada`, `sin_autorizar`), `otorgado_en`, `revision_vence_en`, `revocado_en`, `borrado_en` y `borrada`. **No muestra `calidad_otorgante`** a nadie en esta pantalla |
| Retirar | `POST …/consentimientos/{finalidad}/retiro`, sin cuerpo → 200 `RetiroAutorizacion {autorizacion, enlaces_cortados}` (decisiones 123 a 126) | `autorizacion` redibuja el bloque. `enlaces_cortados` va en «Cortamos `{n}`». 409 `/errores/ya-retirada`. 404 para otro rol o una finalidad nunca autorizada |
| Volver a autorizar | `POST …/consentimientos` con `finalidad: plan_cuidado` o `consumo` (decisión 128) | 201, 409 `autorizacion-vigente`, 422 |
| Retirada o por renovar en la ficha | 403 `sin-consentimiento` o `revision-vencida` (decisión 131) | Enlaces y Ficha (4.5) |
| El conteo de «Hoy abren `{n}`» | `GET …/accesos-relevo?estado=vigente&limite=100` (ya existe) | La cantidad de `items` |

**Resuelto el 06-11:**
- **P2:** el pagador y el observador reciben `AutorizacionesPersonaResumen` (`AutorizacionVistaResumen`, sin `calidad_otorgante`), decisión 127.
- **P8:** después del día 90, volver a autorizar deja la ficha en 0 de 3 y sin secciones, con una clave nueva en la primera escritura, decisión 130.

---

## 8. Lo que el frontend no debe hacer

- **No guardar** el estado de las autorizaciones, la ficha, el consumo ni el conteo de enlaces en `localStorage`, `sessionStorage` ni la URL. El id de la persona tampoco va en la ruta.
- **No ser optimista:** ni el bloque, ni las tarjetas de Enlaces, ni la pista de la barra cambian antes de la respuesta de la API.
- **No calcular** la fecha de borrado ni decidir si algo se borró: salen de `borrado_en`, `borrada` y `estado`.
- **No usar** el conteo de 2.2 en la confirmación de hecho: «Cortamos `{n}`» es `enlaces_cortados`.
- **No mostrar** `title`, `detail` ni `mensaje` de la API (lenguaje 8). El texto se elige por `type`.
- **No mostrar** `calidad_otorgante` en Grupo familiar, a ningún rol.
- **No agregar** contraseña, motivo, escribir el nombre ni una segunda confirmación.
- **No cambiar** las declaraciones del alta ni las del permiso de los insumos, ni preseleccionar una calidad en 5.1.
- **No tocar** la pantalla de Insumos (`Insumos.tsx` y `ListaInsumos.tsx`). El permiso de los insumos se reutiliza sin cambios (P3).
- **No agregar** «Renovar la autorización» en ninguna parte (P5).
- **No dejar** la ficha ni el consumo de la persona en el contexto después de retirar.
- **No poner** el botón en `turquesa` macizo, ni retirar con un enlace de texto en `pronto`: el del bloque es `peligro` y el del diálogo `pronto` macizo.
- **No escribir** colores, tamaños ni sombras a mano. Ningún token nuevo. Solo lucide: `Users`, `ShieldCheck`, `ShieldOff`, `ShieldQuestion`, `Hourglass`, `Unlink`, `CircleCheck`, `Info`, `CircleAlert`, `CloudOff`, `Lock`, `ChevronLeft`.
- **No usar** las palabras «revocar», «consentimiento», «borrado», «eliminar» ni «suspender» en la interfaz. Se dice «retirar la autorización», «permiso», «se borra» y «cortar».

---

## 9. Criterios visuales verificables

1. En Grupo familiar no hay ningún elemento en `turquesa` macizo, en ningún rol ni estado.
2. Cada bloque dice su estado con una frase y un ícono distinto. Con la pantalla en escala de grises se distinguen `vigente`, `revision_vencida` y `retirada`.
3. `retirada` y `borrada` tienen borde punteado `borde` sobre `papel`, y `vigente` `ring-linea` sobre `hoja`.
4. Pagador y observador no ven ningún botón en los bloques, ni la calidad de quien autorizó, y sí ven las fechas.
5. En el diálogo, el único botón macizo es «Retirar la autorización», en `pronto`.
6. Al abrir el diálogo, el título se ve completo y tiene el foco, a 360 px y a 320 px con el texto al 200 %.
7. Con el texto al 200 % a 320 px no hay desplazamiento horizontal en `/grupo`, en el diálogo ni en 5.1. El diálogo se desplaza hacia abajo dentro de sí mismo.
8. Mientras dice «Retirando…», «No retirar» y `Esc` no cierran el diálogo, y el botón no cambia de ancho.
9. Después de retirar, el foco está en «Autorización retirada…» dentro del mismo bloque, que no cambió de lugar.
10. Al cancelar, el foco vuelve al botón «Retirar la autorización» que abrió el diálogo.
11. En Enlaces después del retiro, no hay ningún «En pausa» ni ninguna nota `atenta`.
12. En Insumos no aparece ninguna línea nueva.
13. Ningún texto relevante bajo 17 px, en los dos temas.

---

## 10. Textos para copiar a `lenguaje.md`

### 10.1 Sección 22 · Retirar una autorización (MATU-44)

| Dónde | Texto | Marca |
|---|---|---|
| Barra de secciones | Grupo familiar · corto: Grupo | [NUEVO] |
| Grupo familiar, título y bajada | Grupo familiar · A quién cuidan en `{nombre del grupo}` y qué permisos dieron. | [NUEVO] |
| Grupo familiar, bloque de la ficha | Permiso para guardar su ficha · Autorizada el `{fecha}`. · Retirar la autorización | |
| Grupo familiar, bloque de los insumos | Permiso para calcular sus insumos · Autorizado el `{fecha}`. · Retirar la autorización | |
| Bloque, por renovar | Autorizada el `{fecha}`. Hay que renovarla desde el `{fecha_revision}`. · Insumos: Autorizado el `{fecha}`. Hay que renovarlo desde el `{fecha_revision}`. | [NUEVO] |
| Insumos sin autorización todavía | Sin permiso todavía. Se pide al anotar el primer insumo. | |
| Nombre accesible de los botones | Retirar la autorización de la ficha de `{nombre_pila}` · Retirar la autorización de los insumos de `{nombre_pila}` · Volver a autorizar la ficha de `{nombre_pila}` · Volver a autorizar los insumos de `{nombre_pila}` | [NUEVO] |
| Error al cargar Grupo familiar | No pudimos traer los permisos. Revisa tu conexión e inténtalo de nuevo. · Intentar de nuevo | [NUEVO] |
| Confirmación de la ficha, título | ¿Retirar la autorización de la ficha de `{nombre_pila}`? | |
| Confirmación de la ficha, texto | Nadie del grupo podrá ver ni cambiar su ficha. · Se cortan ahora todos sus enlaces de relevo. Hoy abren `{n}`. (Con 1: «Hoy abre 1.» Con 0: «Hoy ningún enlace abre.») Si alguien tiene la ficha abierta, se le cierra cuando vuelva a mirarla. No recibe aviso. · Un enlace cortado no vuelve a abrir, aunque autorices de nuevo. · Lo escrito queda guardado sin que nadie lo vea. Si no vuelves a autorizar en 90 días, se borra. · La autorización de los insumos no cambia. | [AJUSTE] sin el conteo, se omite «Hoy abren `{n}`.» · [AJUSTE] sin autorización de insumos, se omite el último punto |
| Confirmación de la ficha, autorización por renovar | En lugar de «Hoy abren `{n}`.»: Hoy están en pausa `{n}`. (Con 1: «Hoy está en pausa 1.» Con 0: «Hoy ningún enlace abre.») | [NUEVO] |
| Confirmación de los insumos, título | ¿Retirar la autorización de los insumos de `{nombre_pila}`? | |
| Confirmación de los insumos, texto | Dejamos de calcular cuándo se acaban y de avisar, desde ahora. Tampoco avisamos al resto del grupo. · Nadie del grupo podrá ver los insumos anotados. · Lo anotado queda guardado sin que nadie lo vea. Si no vuelves a autorizar en 90 días, se borra. · Una lista que ya imprimiste o compartiste no se borra: quedó fuera de MATU. · Su ficha y los enlaces de relevo no cambian. | [NUEVO] el cuarto punto |
| Botones | Retirar la autorización · No retirar | |
| En curso | Retirando… | |
| Hecho, ficha | Autorización retirada. Cortamos `{n}` enlaces. (Con 1: «Autorización retirada. Cortamos 1 enlace.» Con 0: «Autorización retirada. No había enlaces que abrieran.») | [AJUSTE] con 1 y con 0 se repite «Autorización retirada.» |
| Hecho, insumos | Autorización retirada. Ya no calculamos ni avisamos por los insumos de `{nombre_pila}`. | |
| Error de conexión | No pudimos retirar la autorización. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba. | |
| Ya la retiró otra persona | Otra persona de tu grupo ya retiró esta autorización. | |
| Grupo familiar, después del retiro | Autorización retirada el `{fecha}`. Si no vuelves a autorizar, lo guardado se borra el `{fecha_borrado}`. · Volver a autorizar | |
| Grupo familiar, ya borrado | Autorización retirada el `{fecha}`. Lo guardado se borró el `{fecha_borrado}`. · Volver a autorizar | [NUEVO] |
| Pagador y observador, debajo del estado | Vigente o por renovar: Puede retirarla quien administra el grupo o quien cuida a `{nombre_pila}`. · Retirada o borrada: Puede volver a autorizarla quien administra el grupo o quien cuida a `{nombre_pila}`. | [NUEVO] |
| Pagador y observador, después del retiro | Autorización retirada el `{fecha}`. Si nadie vuelve a autorizar, lo guardado se borra el `{fecha_borrado}`. | [AJUSTE] en impersonal: estos roles no pueden volver a autorizar |
| Ficha sin autorización (6.4), admin y cuidador | Termina en: La puedes volver a autorizar desde Grupo familiar. · Volver a autorizar | [NUEVO] Cierra el [PENDIENTE] de 6.4 |
| Volver a autorizar, enlace de vuelta | Volver a Grupo familiar | [NUEVO] |
| Volver a autorizar la ficha, frase de estado | Dentro de los 90 días: Al autorizar de nuevo, vuelve lo que estaba escrito. Los enlaces que se cortaron no vuelven a abrir. · Después: Lo escrito antes se borró el `{fecha_borrado}`. La ficha empieza en blanco. | [NUEVO] |
| Volver a autorizar la ficha, botón | Acepto y vuelvo a autorizar · Autorizando… | [NUEVO] |
| Volver a autorizar los insumos, frase de estado | Dentro de los 90 días: Si vuelves a dar el permiso antes del `{fecha_borrado}`, vuelve lo que estaba anotado. · Después: Lo anotado antes se borró el `{fecha_borrado}`. Hay que anotar los insumos de nuevo. | [AJUSTE] la primera va en esta pantalla y no en Insumos · [NUEVO] la segunda |
| Volver a autorizar, errores | No pudimos guardar la autorización. Revisa lo que elegiste y vuelve a intentarlo. · Otra persona de tu grupo ya volvió a autorizar. | [NUEVO] |
| Volver a autorizar, hecho | Ficha: Autorización registrada. Ya puedes ver y cambiar la ficha de `{nombre_pila}`. · Ficha después de los 90 días: Autorización registrada. La ficha de `{nombre_pila}` empieza en blanco. · Insumos: Permiso guardado. Volvió lo que estaba anotado. · Insumos después de los 90 días: Permiso guardado. Ahora anota el primer insumo. | [NUEVO] (la última, [L 18]) |
| Enlaces, autorización retirada | Título: Se retiró la autorización de la ficha. · Cuerpo: Los enlaces se cortaron y no vuelven a abrir. · Ver los permisos en Grupo familiar | [AJUSTE] en título y cuerpo · [NUEVO] el enlace |

**Se quita del borrador:** la fila «Insumos, 403 para admin y cuidador después del retiro». Por P3 su texto no va en Insumos: queda en «Volver a autorizar los insumos, frase de estado».

### 10.2 Sección 9.1 · Fila que reemplaza a «Autorización vencida o retirada, en Enlaces (decisión 33)»

| Dónde | Texto |
|---|---|
| Autorización por renovar, en Enlaces (decisión 33) | Aviso: Mientras no se renueve la autorización, ningún enlace abre. Cuando se renueve, vuelven a abrir los que no hayan vencido. · En cada enlace vigente: En pausa (con ícono, en vez de «Activo») |

[AJUSTE] «Cuando la renueves» pasa a «Cuando se renueve»: Enlaces también lo ve el pagador con `puede_ver_plan`, que no puede renovarla. El caso de la autorización retirada sale de 9.1 y queda en la sección 22, «Enlaces, autorización retirada».

---

## 11. Decisiones de Jorge (06-11)

| # | Decisión | Dónde queda |
|---|---|---|
| P1 | Grupo familiar es una cuarta sección mínima | Sección 2 |
| P2 | Pagador y observador ven el estado y las fechas, sin la calidad de quien autorizó y sin botones | 3.6. Contrato: decisión 127 |
| P3 | En Insumos no se agrega la línea | 4.5 y 5.2 |
| P4 | El aviso de 6.4 muestra «Volver a autorizar» a admin y cuidador | 4.5 |
| P5 | Renovar queda fuera | 3.4 y sección 8 |
| P6 | Se puede retirar con la revisión vencida, con «Hoy están en pausa `{n}`» | 3.4 y 4.3 |
| P7 | La confirmación de los insumos dice que lo ya impreso o compartido no se borra | 4.2 y 4.3 |
| P8 | Desde el día 90, al volver a autorizar, la ficha empieza en blanco (0 de 3) y lo de antes no vuelve | 5.1 y 5.3. Coincide con la especificación y con la decisión 130 |

---

## 12. Cómo la voy a revisar

Mirándola funcionar, con datos sintéticos (María, Carmen, Rodrigo y Rosa). Capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %, de:
- `/grupo` con los cinco `estado`, como admin, como pagador y como observador
- el diálogo de la ficha con 0, 1 y 2 enlaces, sin conteo y en pausa, y el de los insumos
- el diálogo en curso, con error de red y con 409
- el bloque recién retirado con su confirmación
- `/grupo/autorizar-ficha` en `retirada` y en `borrada`, con las tres calidades
- `/ficha` sin autorización, como admin y como observador
- `/compartir/enlaces` después del retiro y con la revisión vencida
- la barra del teléfono con cuatro secciones

Con el teclado: el foco al abrir, al cancelar, al retirar y al volver de autorizar. Con un lector de pantalla: que «Autorización retirada…» se lea una sola vez.
