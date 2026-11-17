# MATU-95 · «A quién llamar» a primera vista, y las alergias en las preguntas guía · Especificación de diseño

**Versión 1.0 · 17/11/2026** · Agente 6, UI/UX. Especifica y no construye. Cambia la sección 3.11 de `matu-23-pagina-relevo.md` (el orden de la hoja) y la hoja de la familia (`HojaFicha`, MATU-39 y MATU-49). Sin tokens nuevos, sin textos nuevos del diseñador, sin API ni migración.

**La decisión de Jorge (11-11, `docs/resultados-entrevistas.md` del repositorio MATU):** ningún campo nuevo. «A quién llamar» ya es el contacto de emergencia y tiene que verse primero y con fuerza en el relevo. Las alergias entran como recordatorio en las preguntas guía de «Comer y beber» y «Sus remedios», sin un campo clínico (ADR-028).

---

## 0. Lo que se vio funcionando (7fceca1, vite con el doble, 17-11)

Capturas en `scratchpad/capturas95/` (no van al repositorio). Posición del título «A quién llamar» desde el borde superior de la página:

| Pantalla | Ancho | Dónde queda hoy | Pantallas de alto |
|---|---|---|---|
| Relevo, `ejemplo-tres-campos` | 360 × 800 | 1.265 px, tercer campo, después de «Su día» y «Si se altera» | 1,58 |
| Relevo, `ejemplo-telefonos` | 360 × 800 | 1.121 px | 1,40 |
| Relevo, `ejemplo-textos-largos` (500 caracteres por campo) | 360 × 800 | 2.239 px | 2,80 |
| Relevo, texto al 200 % | 320 × 740 | 4.194 px | 5,67 |
| Relevo | 1280 × 800 | 781 px, justo bajo el borde | 0,98 |
| Ficha de la familia, vista previa «Así la ve quien te reemplaza» | 360 × 800 | 2.859 px, tercer campo | 3,57 |

- **No se ve primero ni con fuerza.** Es el tercer campo, con el mismo `h2 text-xl text-turquesa` que los otros dos. En el teléfono de Rosa hay que bajar más de una pantalla, y con el texto al 200 % más de cinco.
- Sin desplazamiento horizontal en ningún caso (`scrollWidth` igual a `clientWidth`). Los teléfonos no se parten (3.11.4).
- Al abrir la ficha, el foco va al nombre (`#titulo-pagina`) y la página se desplaza hasta la hoja. Lo que sigue al nombre es lo primero que Rosa ve, también con el texto al 200 %.

## 1. Objetivo

Rosa abre el enlace en un apuro y, sin bajar, sabe a quién llamar.

## 2. Jerarquía de la hoja del relevo

1. El nombre: «Ficha de cuidado de» y `{nombre_pila}` (sin cambios).
2. **«A quién llamar»**, primero, en un bloque con fondo y ícono.
3. «Su día» y «Si se altera», en ese orden, como hoy.
4. Las secciones de «Más sobre…», como hoy.

**Solo cambia el orden de la hoja.** La columna de datos (vigencia, «Actualizar», «Solo `{nombre}` puede cambiar esta ficha.») sigue arriba en el teléfono y a la derecha en pantalla ancha. No hace falta moverla: al abrir, la página baja hasta el nombre, y el bloque queda justo debajo.

En la familia, **la lista de campos para escribir no cambia de orden** («Su día», «Si se altera», «A quién llamar», con «`{n}` de 3 campos listos» y el botón principal en el primero que falta). Es el orden de escritura validado en la Fase 1 y el que siguen el editor y el alta. **Lo que cambia es la hoja** (`HojaFicha`), que es «Así la ve quien te reemplaza» y tiene que verse igual que la de Rosa: la vista previa de la ficha, la de «Compartir» y la del editor.

## 3. Esquemas

### 3.1 Relevo, 360 px (lo que se ve al abrir)

```
┌ hoja bg-hoja shadow-xl ────────────┐
│ Ficha de cuidado de                │ text-lg text-tenue
│ María                              │ titular text-5xl
│ ────────────────────────────────── │ border-b-2 border-tinta
│ ┃ ☎ A quién llamar                 │ bloque: bg-rocio, border-s-4 border-turquesa
│ ┃ ¿A quién llamar si algo pasa?    │   h2 text-2xl font-bold text-tinta, ícono Phone text-turquesa
│ ┃ Rodrigo, su hijo: +56 9 5555 0141│   pregunta text-base text-tenue
│ ┃ Ana, la vecina del 3: 9 5555-0102│   contenido: TextoCampo sin cambios (text-lg, renglones)
│                                    │
│ Su día                             │ h2 text-xl text-turquesa (sin cambios)
│ ¿Cómo es un día normal para María? │
│ 08:00 ● Se levanta…                │
```

### 3.2 Relevo, 320 px con el texto al 200 %

El mismo orden. El bloque usa `angosto:px-2 angosto:py-3`, como la hoja, para no quitarle ancho a los teléfonos. Con «+56 9» y «5555 0141» en dos renglones (3.11.4), ningún grupo se sale.

### 3.3 Pantalla ancha (1280 y 1920 px)

Igual que hoy: la hoja en `max-w-3xl` y la columna de datos a la derecha. El bloque ocupa el ancho de la hoja, con el contenido en su `max-w-prose`. Queda a unos 300 px del borde superior, dentro de la primera pantalla también en el proyector.

### 3.4 Familia, la hoja (`HojaFicha`)

El mismo bloque, en escala de la hoja de la familia: después de «Ficha de cuidado de `{pila}`», con `mt-5`, y el título en `h3 text-xl` en vez de `h2 text-2xl`. Sin la pregunta guía, como hoy en esa hoja. Después, «Su día» y «Si se altera».

## 4. Componentes y tokens

| Parte | Relevo (`PantallaFicha`, `Hoja`) | Familia (`HojaFicha`, `ui.tsx`) |
|---|---|---|
| Orden | `red_apoyo` primero, después `rutina` y `manejo_situaciones` (constante `ORDEN_CAMPOS` del relevo) | El mismo orden **solo en la hoja**. `CAMPOS` (lista, editor, alta) no cambia |
| Contenedor | `section` `mt-6 rounded-md bg-rocio border-s-4 border-turquesa px-4 py-4 angosto:px-2 angosto:py-3` | `section` `mt-5 rounded-md bg-rocio border-s-4 border-turquesa px-4 py-3 angosto:px-2` |
| Título | `h2` `flex items-center gap-2 text-2xl font-bold text-tinta`, con `Phone` de lucide `size-6 shrink-0 text-turquesa`, `aria-hidden` | `h3` `mb-1 flex items-center gap-2 text-xl font-bold text-tinta`, con `Phone` `size-5` |
| Pregunta guía | `p` `mt-1 text-base text-tenue` (sin cambios) | No lleva (sin cambios) |
| Contenido | `TextoCampo` sin cambios: `renglones text-lg leading-7`, teléfonos sin partir, sin `tel:` (3.11.2) | `TextoCampo` sin cambios |
| Mientras se escribe ese campo | — | El borde del bloque pasa de `border-turquesa` a `border-miel`, sin el `-ml-3` de los otros campos |

- **El título va en `tinta` y más grande**, a diferencia de los otros campos en `turquesa`. La fuerza sale del tamaño, del fondo `rocio` y del ícono, nunca de un color de estado: no es `pronto` ni `atenta`, porque no es una alerta.
- **El estado nunca solo por color:** el bloque se reconoce por su título, su ícono y su posición. El fondo es un refuerzo.
- **Ningún elemento en `turquesa` macizo** en la hoja (3.11 sigue igual: «Actualizar» es secundario).

### Contraste medido

| Par | Claro | Oscuro |
|---|---|---|
| `tinta` sobre `rocio` (título y contenido) | 13,1:1 | 11:1 |
| `tenue` sobre `rocio` (pregunta) | 6,0:1 | 6,3:1 |
| `turquesa` sobre `rocio` (ícono, con significado) | 5,6:1 | 6,4:1 |

## 5. Estados

| Estado | Qué se ve |
|---|---|
| Con texto | El bloque con el texto de Carmen |
| Vacío (`texto: null`) | El bloque igual, primero, con la pregunta y la píldora «Sin completar» (3.11.2). Rosa sabe enseguida que no hay a quién llamar, en vez de descubrirlo al final |
| Cargando, error, enlace vencido o cortado | Sin cambios (no hay hoja) |
| «Actualizar» con éxito | La hoja se repinta en el mismo orden y el foco no se mueve (sin cambios) |
| Conflicto (412) | No aplica: el relevo solo lee. En el editor de la familia, el conflicto de «A quién llamar» muestra la hoja con el mismo bloque |

## 6. Textos

**Ninguno nuevo del diseñador.** «A quién llamar», «¿A quién llamar si algo pasa?» (relevo, lenguaje 5.3) y «Sin completar» siguen iguales.

### 6.1 Las alergias en las preguntas guía (las fija el analista)

Lugar reservado. Los textos los fija el analista normativo y los aprueba Jorge en `docs/lenguaje.md`, sección 14. El diseño solo fija dónde van:

| Sección | Dónde se ve hoy | Texto de hoy | Texto nuevo |
|---|---|---|---|
| Comer y beber (`alimentacion`) | Etiqueta del editor (`seccion.pregunta`, `label font-bold`) | «¿Qué le gusta comer y cómo se le sirve?» | `{ANALISTA: pregunta guía que incluya lo que no puede comer o tomar}` |
| Sus remedios (`remedios`) | Etiqueta del editor | «¿Qué remedios toma y a qué hora, tal como se los da la familia?» | `{ANALISTA: pregunta guía que incluya los remedios que no puede tomar}` |
| Las dos | Ayuda bajo el campo (`#seccion-ayuda`, `text-base text-tenue`, en el `aria-describedby`), después de «No hace falta escribir diagnósticos…» | «Si tiene alergia a algún remedio o alimento, anótalo aquí.» | `{ANALISTA: el recordatorio en lenguaje cotidiano, o se deja el de hoy}` |

Reglas de diseño para esos textos:
- Siguen en el **editor de la familia**. El relevo nunca ve preguntas ni ejemplos de las secciones (MATU-49, D5).
- Una pregunta de **una línea** a 360 px si se puede, y nunca más de dos: es la etiqueta del campo.
- Sin palabras clínicas ni de la lista prohibida de `lenguaje.md`, y en tú.
- Si el analista cambia el ejemplo («Por ejemplo: «…»»), sigue en `#seccion-ejemplo` con su borde `linea`, sin teléfonos ni nombres de remedios reales.

## 7. Criterios verificables

1. En el relevo, el primer `h2` después del nombre es «A quién llamar», también con el campo vacío.
2. A 360 × 800 px, al abrir la ficha, el título y el primer renglón del contenido de «A quién llamar» se ven sin bajar.
3. A 320 px con el texto al 200 %, el título «A quién llamar» se ve sin bajar, y `scrollWidth` es igual a `innerWidth`.
4. El bloque es el único de la hoja con `bg-rocio` y título en `tinta`. «Su día» y «Si se altera» siguen en `text-xl text-turquesa`.
5. La vista previa de la ficha y la de «Compartir» muestran «A quién llamar» primero. La lista de campos para escribir sigue con «Su día» primero.
6. Tema claro y oscuro con los contrastes de la sección 4, y foco visible en «Actualizar» sin cambios.
7. Los teléfonos dentro del bloque siguen sin partirse (3.11.4) y sin `tel:`.
8. Prueba del orden en `PaginaRelevo.test.tsx` y en la hoja de la familia, que falla con el orden de hoy (definición de terminado, punto 6).

## 8. Lo que cambia en otras especificaciones

- `matu-23-pagina-relevo.md`, 3.11: el orden de los campos de la hoja pasa a «A quién llamar», «Su día», «Si se altera», con el bloque de la sección 4. Ya lleva la nota en 3.11.1 (17/11/2026).
- El comentario de `ORDEN_CAMPOS` en `web/src/relevo/textos.ts` dice «Orden fijo de los campos en la hoja (lenguaje 5)». `lenguaje.md` 5 solo enumera los campos y no fija un orden de la hoja, así que no hay contradicción. El frontend actualiza el comentario.
