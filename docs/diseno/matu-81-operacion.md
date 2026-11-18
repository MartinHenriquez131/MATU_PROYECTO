# MATU-81 · La consola de operación · Especificación de diseño

**Versión 1.1 · 17/11/2026** · agente 6 (UI/UX) · para el frontend
**Cambios de la 1.1** (después de la revisión visual de 5a92dc6): el detalle ancho pasa a dos columnas desde `@3xl/detalle` (6.2); los dígitos del código van con `gap-x-10` (6.4); la sección «Retractos» del pedido solo aparece si hay algo que mostrar o hacer, y sus filas llevan la etiqueta del estado (8.5); el foco al abrir «No devolver» y «Anotar una incidencia» (8.4 y 9.3); el plazo se quita con el bloqueo (4.4); el texto de `hay_mas` (8.2); el criterio 14.2 deja de chocar con la ayuda de C11; el criterio 18 dice la medida. Después de a2a7ea6: se quita el 409 «otro retracto en curso» de 8.5 (un pedido puede tener varios retractos, por decisión del orquestador) y el diálogo de «No devolver» muestra el motivo con el texto de la familia (8.4).
**Historia:** MATU-81, el backoffice mínimo de operación (capa 3, ADR-027). El equipo de MATU entra con su contraseña y un código de su teléfono, sigue cada pedido pagado hasta que se entrega, genera el código de retiro, resuelve los retractos, anota lo que pasó con un pedido, revisa que los cobros y las devoluciones calcen, y cambia el precio y la cantidad de los comercios de prueba.
**Dónde se construye:** `web/`, una app aparte bajo `/operacion`, con React 19, TypeScript y Tailwind CSS v4, mobile first. Sigue el mismo camino que la consola del comercio (`web/src/comercio/`): su propia rama en `main.tsx`, su proveedor de estado en memoria y su marco.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · la revisión previa del analista y las decisiones D-81-1 a D-81-12 con las condiciones C1 a C36 · `docs/diseno/matu-63-comercio.md` (la consola del comercio, de la que esta copia el marco, la cola y el detalle) · `docs/diseno/matu-62-pago.md` 6.3 y 7.7 (confirmar y mostrar devoluciones) · `docs/diseno/matu-48-compartir.md` 4 (el PIN, una sola vez) · `lenguaje.md` secciones 3, 8, 11, 35 y 36 · el contrato de `docs/api/openapi.json` en esta rama (`/v1/operacion/*`, `/v1/sesiones`).

**Cómo se lee:** los textos entre comillas latinas «» van tal cual en pantalla. Marcas de origen:
- **[A81]** texto del analista o de las condiciones de MATU-81;
- **[L nn]** texto ya aprobado en esa sección de `lenguaje.md`;
- **[C63]** texto de la consola del comercio (`matu-63-comercio.md`, `lenguaje.md` 36);
- **[NUEVO]** un texto mío, que Jorge aprueba antes de construir.

Las llaves son datos de la API: `{ref}` la referencia del pedido, `{ref_parte}` la referencia de una parte, `{comercio}` el `nombre_fantasia`, `{monto}` pesos enteros con punto de miles y signo `$` («$69.000»), `{DD/MM/AAAA}` y `{HH:MM}` en hora de Chile y 24 horas, `{n}` un número.

**Tokens:** **ningún token nuevo**, ningún color nuevo y ninguna regla nueva en la capa base. Todo sale de los componentes que ya existen (`Boton` con sus siete variantes, `Nota`, `Etiqueta`, `CampoTexto`, `GrupoOpciones`, `Stepper`, `MensajeError`, `Pestanas`, `Volver`, `Acciones`, `Anunciado`, `DialogoConfirmar`, `DistintivoPiloto`, `BotonMostrar`, el `textarea` con contador de `EditorSeccion`) y de las piezas de la consola del comercio: la barra `tinta` (`MarcoComercio`), la fila de la cola y el cuadro del detalle. `DISENO.md` no cambia: la sección 3 ya dice que la consola es «más densa y más sobria», y esta es la tercera app de ese molde.

---

## 0. Puntos abiertos

Ninguno bloquea empezar: cada uno tiene una propuesta, y la pantalla se construye con ella hasta que se decida otra cosa. Si el contrato del backend nombra distinto, manda el contrato.

| # | Qué | Para quién | Propuesta |
|---|---|---|---|
| P1 | **El tipo de cuenta y el desafío.** La pantalla tiene que saber que la contraseña era de una cuenta de operación y que falta el código | Backend | `POST /v1/sesiones` responde 401 `/errores/mfa-requerido` con `{ desafio, expira_en }` (o 200 con `mfa_requerido: true`, sin tokens). `POST /v1/sesiones/mfa` responde como `SesionRespuesta` con `tipo_cuenta: "operacion"`. Una cuenta de familia o de comercio en `/operacion/entrar` ve el aviso de 4.4 |
| P2 | **Los tres fallos del código.** Código que no es, cinco fallos y desafío vencido tienen que distinguirse | Backend | Tres `type` distintos: `codigo-mfa-incorrecto` (401, con los intentos que quedan si se pueden decir sin ayudar a adivinar; si no, sin número), `demasiadas-peticiones` (429 con `Retry-After`) y `desafio-vencido` (401 o 410). Sin Redis, 503 (C32) |
| P3 | **Las acciones posibles.** La pantalla no debe copiar la máquina de estados de `ordering/domain/estados.py` | Backend | `GET /v1/operacion/pedidos/{id}` trae `acciones` (`en_camino`, `entregado`, `no_entregado`, `cancelar_con_devolucion`) con el **monto que devolvería cada una** (`monto_a_devolver`, entero, 0 si no devuelve). La pantalla muestra ese monto en la confirmación y nunca lo calcula (C22) |
| P4 | **El filtro de la lista.** Once estados del pedido no caben como chips en 360 px | Backend | La lista acepta varios estados (`estado` repetido, o una lista en el cuerpo de `buscar`). La pantalla ofrece seis grupos (5.4), cada uno es una lista fija de estados |
| P5 | **Qué quiere decir `producto_no_recibido`.** Puede ser «MATU no recibió de vuelta el producto» o «la familia nunca lo recibió» (que no es un retracto, sino un pedido no entregado) | Analista y Jorge | Lo leo como lo primero: «MATU no recibió el producto de vuelta.». Lo que lee la familia lo fija MATU-92 con la misma idea |
| P6 | **Las líneas del retracto.** `RetractoVista` no trae productos ni cantidades (C23) | Backend | `RetractoVista` suma `lineas: [{ producto, presentacion, cantidad, monto }]` y `referencia` del pedido. Para el retracto por correo, la pantalla usa las líneas del pedido |
| P7 | **El ETag de la incidencia y de la oferta.** `PATCH` con `If-Match` (C4, ruta 6) | Backend | `GET` de la incidencia y de la oferta traen `ETag`; la lista trae una `version` por fila para abrir el editor sin otro `GET` |
| P8 | **Dónde se entrega el código de retiro.** Hoy no hay repartidor en la app | Jorge | En el piloto, quien opera se lo da a quien va a retirar al comercio. Los textos dicen «quien va a retirar el pedido», sin nombrar a nadie |

**Lo que este documento no decide:** lo que ve la familia de sus incidencias, del motivo del rechazo y de la revisión de su pedido (MATU-54 y MATU-92, con el texto «Lo que pasó con tu pedido» de D-81-4); el alta de la cuenta de operación (C28, una tarea de consola sin pantalla); los indicadores (fuera, D-81 «si las horas no alcanzan»).

---

## 1. Para quién y qué

**Quien opera MATU** en el piloto: Jorge o Martín, en un computador o en el teléfono, con varios pedidos a la vez y la responsabilidad de no cobrar ni devolver de más. No es una persona cansada como Carmen, pero sí alguien que trabaja rápido y que puede equivocarse con un toque: **toda acción que mueve dinero o cambia un pedido pide confirmar y dice cuánto se devuelve.**

En el piloto, los comercios son de prueba, los pedidos son inventados y los pagos son del ambiente de prueba de Transbank.

**Lo que estas pantallas nunca hacen:**
- Mostrar datos de la persona cuidada ni de la familia: nombre, nivel de apoyo, dirección, teléfono, grupo, nombre del grupo, ni quién pidió o pagó (C5 y C6). La línea de tiempo dice «La familia», nunca un nombre.
- Mostrar la tarjeta, los últimos 4, el tipo de tarjeta, las cuotas, el código de autorización, el token ni el `session_id` de Transbank (C18). Sí muestran `buy_order`, como «Orden de compra».
- Poner un id, la referencia, el `buy_order`, un correo ni un código en la URL, en `localStorage`, `sessionStorage`, `history.state` ni el `<title>` (C7, C18, C20).
- Listar a los miembros de un grupo, ni siquiera para elegir quién pidió un retracto por correo (C25).
- Copiar el código de retiro al portapapeles (C20).
- Cambiar el precio de un comercio real (C1, D-81-7).
- Decir «token», «sesión», «inválido», «rechazado», «fallido» ni un código de error (`lenguaje.md` 3.2). Dentro de la consola sí se dice «incidencia», porque es una palabra interna del equipo; ningún texto de esta consola llega a la familia.

---

## 2. Rutas y navegación

### 2.1 Rutas

Una rama propia en `main.tsx`, como `/comercio`: el prefijo `/operacion` monta `AppOperacion`, sin `ProveedorFamilia` ni `ProveedorComercio`, con `RegionesVivas` antes de la app.

| Ruta | Pantalla | Pública | `<title>` | Sección |
|---|---|---|---|---|
| `/operacion/entrar` | Entrar al equipo de MATU (dos pasos) | Sí | «Entrar a operación · MATU» [NUEVO] | 4 |
| `/operacion` | Pedidos | No | «Pedidos · Operación · MATU» [NUEVO] | 5 |
| `/operacion/pedido` | Un pedido | No | «Pedido · Operación · MATU» [NUEVO], **sin la referencia** | 6 |
| `/operacion/retractos` | Retractos | No | «Retractos · Operación · MATU» [NUEVO] | 8 |
| `/operacion/incidencias` | Incidencias | No | «Incidencias · Operación · MATU» [NUEVO] | 9 |
| `/operacion/cobros` | Cobros por revisar | No | «Cobros · Operación · MATU» [NUEVO] | 10 |
| `/operacion/catalogo` | Catálogo de prueba | No | «Catálogo · Operación · MATU» [NUEVO] | 11 |

- **El pedido, el retracto y la incidencia elegidos viven en la memoria de la página**, nunca en la URL. Al recargar `/operacion/pedido`, la app va a `/operacion` con `replace`. A diferencia del comercio, el `<title>` del pedido **no** lleva la referencia: el título queda en el historial del navegador (C7).
- El paso del código vive en la misma ruta `/operacion/entrar`: el desafío queda solo en memoria. Al recargar en el segundo paso se vuelve al primero.
- Sin la entrada vigente, toda ruta no pública va a `/operacion/entrar` y vuelve a la misma ruta después (sin lo elegido).
- **Al llegar a cada ruta, el foco va al `h1`.** Elegir otra fila en pantalla ancha también es llegar: el foco va al `h1` del detalle.
- Atrás del navegador vuelve de `/operacion/pedido` a la lista de la que vino (`/operacion` o `/operacion/cobros`).

### 2.2 Las pestañas

Bajo la barra, en toda ruta no pública, `Pestanas` con `etiqueta="Secciones de operación"` [NUEVO]:

| Pestaña | Ruta | Texto |
|---|---|---|
| 1 | `/operacion` (activa también en `/operacion/pedido` si vino de aquí) | «Pedidos» [NUEVO] |
| 2 | `/operacion/retractos` | «Retractos» [NUEVO] |
| 3 | `/operacion/incidencias` | «Incidencias» [NUEVO] |
| 4 | `/operacion/cobros` (activa en `/operacion/pedido` si vino de aquí) | «Cobros» [NUEVO] |
| 5 | `/operacion/catalogo` | «Catálogo» [NUEVO] |

- Cinco pestañas arriba también en el teléfono, sin barra inferior: `Pestanas` ya hace `flex-wrap` y a 360 px quedan en dos renglones de 51 px. Nunca un menú escondido: quien opera tiene que ver de un vistazo las cinco secciones.
- Sin número en la pestaña (MATU-61 2.2). Lo pendiente se ve dentro de cada sección.

---

## 3. El marco

**Objetivo:** que quien opera sepa siempre que está en la consola interna, y hasta cuándo vale su entrada.

```
360 px
┌────────────────────────────────────┐
│ 🎧 Operación de MATU               │  bg-tinta text-papel, font-bold
│   Equipo de MATU         ⇥ Salir   │  opacity-85 · Boton textoSobreTinta
│   Tu entrada vale hasta las 21:40  │  opacity-85, cifras
├────────────────────────────────────┤
│ ● Piloto académico con datos de    │  DistintivoPiloto, sobre papel
│   prueba                           │
│ Pedidos  Retractos  Incidencias    │  Pestanas, flex-wrap
│ Cobros  Catálogo                   │
└────────────────────────────────────┘

Ancho (≥ 48 rem de app)
┌ 🎧 Operación de MATU   Equipo de MATU   Tu entrada vale hasta las 21:40      ⇥ Salir ┐  bg-tinta
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Pedidos  Retractos  Incidencias  Cobros  Catálogo       ● Piloto académico con datos… │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Es `MarcoComercio`** con otro contenido: la misma barra `bg-tinta text-papel`, el mismo foco `papel` (`[&_:focus-visible]:outline-papel`, 14,1:1 y 15,4:1), el distintivo fuera de la barra y el mismo `main` (`@container/main px-4 angosto:px-2 @3xl/app:px-10 pt-6 pb-16`, `max-w-7xl`). El frontend puede extraer un marco común de consola; la pantalla no cambia.
- **Ícono:** `Headset` de lucide, `size-6`, `aria-hidden`. No el logo (2,9:1 sobre `tinta` oscura, [C63] 3).
- **Textos:** «Operación de MATU» [NUEVO] en negrita · «Equipo de MATU» [NUEVO] al 85 % · «Tu entrada vale hasta las `{HH:MM}`.» [NUEVO] al 85 %, con la hora en `cifras`, calculada del vencimiento que trae la respuesta de la entrada (12 horas como máximo, C31). Nunca del reloj del teléfono solo.
- **«Salir»** [E39]: `Boton variante="textoSobreTinta"` con `LogOut`, `min-h-12`.
- **Rótulo del piloto**, una vez por pantalla, al pie de la lista y lejos del botón principal: `Nota tono="atenta"` con `Info`, título «Datos de prueba.» [NUEVO] y texto «Estos pedidos, pagos y comercios son inventados. Los pagos son del ambiente de prueba de Transbank.» [NUEVO].
- **Aviso de privacidad**, bajo el `h1` de Pedidos, Retractos e Incidencias: `p` con `ShieldCheck` en `text-turquesa`, `text-base text-tenue max-w-prose`: «Aquí no ves a quién cuida la familia ni dónde vive. Abrir un pedido queda registrado, y la familia lo ve en la copia de sus datos.» [NUEVO] (C9, D-81-5). Es lo que hace que quien opera abra un pedido solo cuando lo necesita.

---

## 4. Entrar al equipo de MATU (`/operacion/entrar`)

**Objetivo:** que solo una persona del equipo, con su contraseña **y** su teléfono, entre a la consola.

**Jerarquía, paso 1:** 1) el título que dice que es la entrada interna · 2) los dos campos · 3) «Seguir».
**Jerarquía, paso 2:** 1) qué falta: el código del teléfono · 2) el campo de 6 cifras · 3) «Entrar» y cuánto queda del desafío.

### 4.1 Esquema a 360 px

```
Paso 1                                  Paso 2 (misma ruta, sin recargar)
┌────────────────────────────────────┐  ┌────────────────────────────────────┐
│ 🎧 Operación de MATU               │  │ 🎧 Operación de MATU               │  Headset + font-bold, sobre papel
│ ● Piloto académico con datos de    │  │ ● Piloto académico con datos de    │
│   prueba                           │  │   prueba                           │
│                                    │  │                                    │
│ Entrar a operación                 │  │ Escribe el código de tu teléfono   │  h1 titular text-3xl (angosto text-2xl)
│ Para el equipo de MATU. Después de │  │ Ábrelo en la aplicación de códigos │  text-lg text-tenue max-w-prose
│ la contraseña te pedimos el código │  │ de tu teléfono. Cambia cada 30     │
│ de tu teléfono.                    │  │ segundos.                          │
│                                    │  │                                    │
│ [aviso, si corresponde]            │  │ [resultado, si hay] ← recibe foco  │  Nota (4.4)
│ Tu correo                          │  │ Código de 6 números                │  label font-bold
│ [                              ]   │  │ ┌──────────────────┐               │
│ Tu contraseña                      │  │ │   4 8 2 1 7 3    │               │  digitos text-3xl, max-w-72
│ [                       ] [Mostrar]│  │ └──────────────────┘               │
│ [ Seguir ]                         │  │ Tienes hasta las 14:25 para        │  text-base text-tenue, cifras
│                                    │  │ escribirlo.                        │
│ ¿No eres del equipo? Entra en la   │  │ [ Entrar ]                         │  único turquesa macizo
│ app de MATU para familias.         │  │ Volver a la contraseña             │  Boton texto
└────────────────────────────────────┘  └────────────────────────────────────┘
```

**Ancho:** la misma columna `flex max-w-md flex-col gap-5`, alineada a la izquierda, en `MarcoEntrar` con el ícono `Headset` y «Operación de MATU». Sin panel de bienvenida.

### 4.2 Componentes

- **Paso 1:** reutiliza `EntrarComercio` tal cual (`CampoTexto`, `BotonMostrar`, el 429 con `aria-disabled` y el foco que se queda en el botón). Cambia solo el texto del botón, que es «Seguir» porque todavía no entra. El token no existe en este paso: la respuesta trae solo el desafío.
- **Paso 2:** al recibir `mfa-requerido`, la contraseña se borra de la memoria, el paso 1 se desmonta y el foco va al `h1` del paso 2. El desafío queda solo en memoria.
- **El campo del código** usa el patrón del campo del código de retiro ([C63] 7.2), con dos diferencias:
  - `autoComplete="one-time-code"` e `inputMode="numeric"` [A81], `enterKeyHint="go"`, `spellCheck={false}`. Aquí sí `one-time-code`: el código es de quien escribe, y algunos teléfonos lo sugieren desde la aplicación de códigos;
  - `type="text"`, nunca `type="number"` (quita los ceros del principio).
- Clases: `digitos min-h-16 w-full max-w-72 rounded-xl bg-hoja text-center text-3xl angosto:text-2xl font-bold tracking-widest ring-2 ring-inset ring-borde focus-visible:ring-turquesa`; con un código que no es, `ring-pronto text-pronto` y `aria-invalid`.
- **Pegar o escribir con espacios o guiones** («482 173»): se quitan los que no son números y se toman los primeros 6 ([C63] 7.2).
- **Con 6 números escritos, no envía solo.** Se toca «Entrar» o Enter: así nadie pierde un intento por un número a medio corregir.
- **«Tienes hasta las `{HH:MM}` para escribirlo.»** sale de `expira_en` del desafío. No hay cuenta regresiva visible ni anunciada (WCAG 2.2.1: el plazo se dice una vez y se puede volver a empezar).
- **«Volver a la contraseña»** (`Boton variante="texto"`): borra el desafío y vuelve al paso 1 con el correo escrito.
- `aria-describedby` del campo: la bajada, el plazo y, si hay, el resultado.

### 4.3 Textos

| Parte | Texto | Origen |
|---|---|---|
| Paso 1, título | Entrar a operación | [NUEVO] |
| Paso 1, bajada | Para el equipo de MATU. Después de la contraseña te pedimos el código de tu teléfono. | [NUEVO] |
| Campos | Tu correo · Tu contraseña · Mostrar · Ocultar | [E39] |
| Paso 1, botón | Seguir · mientras envía: Revisando… | [NUEVO] |
| Faltan datos | Escribe tu correo y tu contraseña. | [E39] |
| A la familia | ¿No eres del equipo? Entra en la `app de MATU para familias`. | [NUEVO], la parte marcada es `EnlaceEnFrase` a `/entrar` |
| Paso 2, título | Escribe el código de tu teléfono | [NUEVO] |
| Paso 2, bajada | Ábrelo en la aplicación de códigos de tu teléfono. Cambia cada 30 segundos. | [NUEVO] |
| Etiqueta del campo | Código de 6 números | [NUEVO] |
| Plazo | Tienes hasta las `{HH:MM}` para escribirlo. | [NUEVO] |
| Paso 2, botón | Entrar · mientras envía: Entrando… | [E39] |
| Volver | Volver a la contraseña | [NUEVO] |
| Menos de 6 | Escribe los 6 números del código. | [C63] 7.2, con «del código» |

### 4.4 Avisos, errores y resultados

Cada resultado del paso 2 es una `Nota` con `titulo`, `enfocable` y `rol`, que se monta de nuevo en cada intento y **recibe el foco después de montarse** ([C63] 7.3). Va entre la bajada y el campo, para que el teclado del teléfono no la tape.

| Situación | Componente | Texto | Después | Origen |
|---|---|---|---|---|
| 401 `credenciales-invalidas` (paso 1) | `Nota tono="pronto" rol="alert"`, bajo los campos | El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo. | Se queda en el paso 1 | [E39] |
| 429 (paso 1) | `Nota tono="atenta" rol="status"`; botón con `aria-disabled` | Hubo varios intentos de entrar. Espera `{minutos}` minutos. | — | [C63] 4.3 |
| La contraseña es de una cuenta de familia o de comercio | `Nota tono="atenta" rol="status"`, arriba | **Esta cuenta no es del equipo de MATU.** Si atiendes un comercio, entra en la entrada del comercio. Si cuidas a alguien, entra en la app para familias. | Se borra la contraseña. La pantalla no sabe ni dice si el correo existe | [NUEVO] |
| El código no es (`codigo-mfa-incorrecto`) | `Nota tono="pronto" rol="alert"` | **Ese código no coincide.** Revisa que sea el de MATU en tu aplicación y escribe el que se ve ahora. | El campo queda con lo escrito seleccionado | [NUEVO] |
| Cinco códigos que no coinciden (429) | `Nota tono="atenta" rol="alert"` | **Hubo 5 códigos que no coinciden.** Espera `{minutos}` minutos y vuelve a entrar con tu contraseña. Si perdiste tu teléfono, pide que te den de alta de nuevo. | Se quitan el campo, «Entrar» y la línea «Tienes hasta las…» (ya no hay nada que escribir); queda «Volver a la contraseña», con `aria-disabled` hasta que pase el tiempo | [NUEVO], C28 y C32 |
| El desafío venció | `Nota tono="atenta" rol="status"`, en el paso 1 | **Pasaron más de 5 minutos.** Vuelve a escribir tu contraseña para pedir otro código. | Vuelve al paso 1 con el correo escrito; la nota recibe el foco | [NUEVO], C29 |
| Un código ya usado | Igual que «no coincide» | (mismo texto) | — | C32: no se dice que ya se usó |
| 503 (sin Redis) | `Nota tono="pronto" rol="alert"` | **No podemos revisar el código ahora.** Vuelve a intentarlo en unos minutos. | El campo sigue con lo escrito | [NUEVO] |
| Red o 5xx | `Nota tono="pronto" rol="alert"` | No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. | — | [L 8], sin «Lo que escribiste sigue aquí.» |
| Volvió por la entrada vencida o el 401 `mfa-requerido` de una ruta | `Nota tono="rocio" rol="status"`, arriba del paso 1 | Tu entrada venció. Vuelve a entrar con tu contraseña y el código de tu teléfono. | — | [NUEVO], C30 y C31 |
| Después de «Salir» | `Nota tono="rocio" rol="status"` | El texto de «Salir» de la familia (MATU-39 2.4) | — | [E39] |

**200 de `/v1/sesiones/mfa`:** va a la ruta guardada o a `/operacion`. El token queda solo en memoria, como en la familia y el comercio.

---

## 5. Pedidos (`/operacion`)

**Objetivo:** que quien opera encuentre rápido el pedido que necesita atender, sin abrir los demás.

**Jerarquía:** 1) buscar por referencia y filtrar por estado · 2) la lista, con lo que pide atención primero · 3) el aviso de privacidad, el rótulo del piloto.

### 5.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (barra, distintivo y pestañas, 3)  │
├────────────────────────────────────┤
│ Pedidos                            │  h1 titular text-3xl
│ 🛡 Aquí no ves a quién cuida la    │  ShieldCheck + text-base text-tenue
│   familia ni dónde vive. Abrir un  │
│   pedido queda registrado…         │
│                                    │
│ Buscar por referencia              │  form role="search", label font-bold
│ [ 4821            ] [🔍 Buscar ]   │  CampoTexto digitos + Boton secundario
│                                    │
│ Mostrar                            │  GrupoOpciones forma chips (5.4)
│ (•) Por atender ( ) En camino      │
│ ( ) Con problema ( ) Cerrados      │
│ ( ) Cancelados  ( ) Todos          │
│ Actualizado a las 14:20. Actualizar│  text-base text-tenue + Boton texto
│                                    │
│ ┌────────────────────────────────┐ │  fila (5.3), button
│ │ Pedido 4821     [◐ Por despach]│ │  ref en digitos font-bold + Etiqueta
│ │ $57.460 · 2 partes             │ │  cifras
│ │ Pagado el 17/11 a las 13:05    │ │  text-tenue
│ │ ⚠ Incidencia abierta           │ │  atenta font-bold, TriangleAlert
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Pedido 4822     [○ En prepara.]│ │
│ │ …                              │ │
│ └────────────────────────────────┘ │
│ [ Ver más pedidos ]                │  Boton secundario, si hay más
│                                    │
│ ⓘ Datos de prueba. Estos pedidos,  │  Nota atenta (3)
│   pagos y comercios son inventados.│
└────────────────────────────────────┘
```

### 5.2 Pantalla ancha (contenedor `main` desde 48 rem)

```
Pedidos                                                   h1
🛡 Aquí no ves a quién cuida la familia ni dónde vive. Abrir un pedido queda registrado…
┌ cola, 19 rem ─────────────────┐  ┌ detalle ────────────────────────────────────────────────┐
│ Buscar por referencia         │  │                                                          │
│ [4821        ] [🔍 Buscar]    │  │  Elige un pedido de la lista para ver sus partes,        │  text-lg text-tenue
│ Mostrar                       │  │  su pago y lo que pasó.                                  │
│ (•) Por atender ( ) En camino │  │                                                          │
│ …                             │  └──────────────────────────────────────────────────────────┘
│ Actualizado a las 14:20.      │
│ [Pedido 4821 …              ] │
│ [Pedido 4822 …              ] │
│ ⓘ Datos de prueba. …          │
└───────────────────────────────┘
```

- La grilla de la consola del comercio: `grid grid-cols-1 items-start gap-x-8 gap-y-8 @3xl/main:grid-cols-[19rem_minmax(0,1fr)]`. La cola de 19 rem es la medida fija de `DISENO.md` 3; no es una medida nueva.
- En el teléfono no hay columna de detalle: tocar una fila lleva a `/operacion/pedido`.
- El cuadro vacío del detalle (solo en ancho): `bg-hoja ring-1 ring-linea rounded-xl px-6 py-6`, sin ícono ni acción.

### 5.3 La fila

- Un `ul` `flex flex-col gap-2`; cada `li` lleva un `button` con las clases de la fila del comercio ([C63] 5.3): `flex w-full min-h-12 flex-col items-start gap-0.5 rounded-xl bg-hoja px-4 angosto:px-2 py-3 text-left ring-1 ring-linea hover:ring-borde`.
- **Primera línea:** «Pedido» y `{ref}` en `digitos font-bold`, y la `Etiqueta` del estado (5.5) a la derecha (`flex flex-wrap justify-between gap-x-3 gap-y-1`: a 360 px baja sola).
- **Segunda:** `{monto}` del total confirmado en `cifras` y «`{n}` partes» («1 parte»).
- **Tercera:** «Pagado el `{DD/MM}` a las `{HH:MM}`» en `text-tenue`.
- **Cuarta, solo si aplica**, en `font-bold text-atenta` con `TriangleAlert` `size-5`: «Incidencia abierta» [NUEVO] o «Devolución sin terminar» [NUEVO]. Si hay las dos, dos renglones.
- **Elegida** (ancho, en `/operacion/pedido`): `aria-current="true"`, `bg-rocio`, `ring-2 ring-turquesa` y `ChevronRight` al final de la primera línea ([C63] 5.3).
- Nombre accesible: todo su texto en orden, «Pedido 4821, Por despachar, $57.460, 2 partes, Pagado el 17/11 a las 13:05, Incidencia abierta».
- Orden: lo que pide atención primero (incidencia abierta o devolución sin terminar), después por la hora de pago, la más antigua primero. En «Cerrados» y «Cancelados», la más reciente primero.
- **Ningún nombre, dirección ni grupo en la fila.** El comercio tampoco: se ve en el detalle, por parte.

### 5.4 Buscar y filtrar

- **Buscar** es un `form role="search"` con `CampoTexto` «Referencia del pedido» [NUEVO] (`digitos`, `autoComplete="off"`, `spellCheck={false}`, `inputMode` por omisión: la referencia puede tener letras) y `Boton variante="secundario"` con `Search` «Buscar» [NUEVO] · «Buscando…» [NUEVO]. El envío hace `POST /v1/operacion/pedidos/buscar` con la referencia **en el cuerpo** (C7). Nunca un `GET` con la referencia, nunca `?ref=`.
- Con un resultado, la lista muestra solo esa fila, con «Mostrando el pedido `{ref}`.» [NUEVO] y `Boton variante="texto"` «Ver todos» [NUEVO], que limpia el campo y vuelve al filtro. Con un resultado **no se abre solo**: abrir queda registrado (C9), y eso lo decide quien opera.
- Sin resultado: `Nota tono="rocio" rol="status"`: «No hay un pedido con la referencia `{ref}`. Revisa que esté bien escrita.» [NUEVO].
- Vacío al buscar: `MensajeError` «Escribe la referencia del pedido.» [NUEVO].
- **Filtro:** `GrupoOpciones forma="chips"` con `leyenda` «Mostrar» [NUEVO], radio, seis opciones. Al elegir, se vuelve a pedir la lista; el foco se queda en el chip.

| Chip [NUEVO] | Estados del pedido (P4) |
|---|---|
| «Por atender» (inicial) | `pagado`, `enviado_a_comercio`, `preparando`, `listo_retiro`, `retirado`, `reprogramado` |
| «En camino» | `en_ruta` |
| «Con problema» | `no_entregado`, `sin_repartidor`, y los que tienen una incidencia abierta o una devolución sin terminar |
| «Cerrados» | `entregado`, `cerrado` |
| «Cancelados» | `cancelado_con_devolucion`, `cancelado` |
| «Todos» | todos los pagados (C8) |

### 5.5 Las palabras del estado

La consola usa palabras más finas que las de la familia ([L 35]), porque quien opera actúa según el paso exacto. Cada `Etiqueta` lleva ícono (`size-5`, hijo directo, se oculta en `angosto`) y palabra.

| Estado | Etiqueta [NUEVO] | Tono | Ícono |
|---|---|---|---|
| `pagado` | Pagado | `neutro` | `Circle` |
| `enviado_a_comercio` | En el comercio | `neutro` | `Circle` |
| `preparando` | En preparación | `neutro` | `Contrast` |
| `listo_retiro` | Listo para retirar | `atenta` | `PackageCheck` |
| `retirado` | Por despachar | `atenta` | `Package` |
| `asignado`, `sin_repartidor` | Sin repartidor | `atenta` | `TriangleAlert` |
| `en_ruta` | En camino | `activo` | `Truck` |
| `entregado`, `cerrado` | Entregado | `ok` | `PackageCheck` |
| `no_entregado` | No se entregó | `atenta` | `PackageX` |
| `reprogramado` | Reprogramado | `neutro` | `Clock` |
| `cancelado`, `cancelado_con_devolucion` | Cancelado | `neutro` | `Ban` |

`atenta` marca lo que espera una acción del equipo; `activo` (`rocio` y `turquesa`) lo que está en curso. Nunca `pronto` en una etiqueta: `pronto` es para lo que se perdió o no se deshace, y va en las notas.

### 5.6 Al día sin recargar

Como el comercio ([C63] 5.5): la lista se pide cada 60 segundos con la pestaña visible, al volver a ella y al tocar «Actualizar» [C63] («Actualizando…»). «Actualizado a las `{HH:MM}`.» [C63] no se anuncia. **Una búsqueda no se refresca sola.** Nunca se mueve el foco ni el desplazamiento por una actualización automática.

### 5.7 Estados de la pantalla

| Estado | Qué se ve |
|---|---|
| **Cargando** | Nada el primer segundo (`useDemora`); después, «Cargando los pedidos…» [C63] en `text-tenue` con `aria-busy` en la cola. Sin esqueletos |
| **Vacío** (en el filtro elegido) | «No hay pedidos en «`{chip}`».» [NUEVO] en `text-xl font-bold`. En «Por atender», además: «Cuando se pague uno, aparece aquí.» [NUEVO] en `text-tenue` |
| **Error al traer** | `Nota tono="pronto" rol="alert"`: «No pudimos traer los pedidos. Revisa tu conexión y vuelve a intentarlo.» [C63] y `Boton variante="secundario"` «Volver a intentar» [L 26]. Si había una lista, se queda a la vista bajo la nota |
| **Sin permiso (404 de `operador()`)** | La cuenta no es de operación: se cierra la entrada y se va a `/operacion/entrar` con el aviso «Esta cuenta no es del equipo de MATU.» de 4.4 |
| **401 `mfa-requerido` o entrada vencida** | A `/operacion/entrar` con «Tu entrada venció…» (4.4). Lo elegido se borra |
| **409** | No aplica en la lista (no hay acciones). Si llega, como un error al traer |
| **412** | No aplica en la lista |

---

## 6. Un pedido (`/operacion/pedido`)

**Objetivo:** que quien opera vea en una pantalla todo lo del pedido (partes, productos, pago y lo que pasó) y haga **la** acción que sigue, sabiendo cuánto dinero mueve.

**Jerarquía:** 1) qué pedido es, en qué estado está y la acción que sigue · 2) las partes, con sus productos, faltantes y el código de retiro · 3) el pago, lo que pasó, las incidencias y los retractos.

Abrir esta pantalla hace `GET /v1/operacion/pedidos/{id}` y `GET …/cobro`, que el servidor registra como `operacion.pedido_ver` (C9). La pantalla no los pide de nuevo por el refresco de la lista: solo al abrir, después de una acción, tras un 409 y con «Actualizar».

### 6.1 Esquema a 360 px (estado `en_ruta`)

```
┌────────────────────────────────────┐
│ (barra, distintivo y pestañas, 3)  │
├────────────────────────────────────┤
│ ‹ Volver a los pedidos             │  Volver (solo bajo 48 rem de main)
│ Pedido 4821                        │  h1 titular text-3xl, ref en digitos
│ [⛟ En camino]                      │  Etiqueta activo
│ Pagado el 17/11/2026 a las 13:05   │  text-base text-tenue, cifras
│                                    │
│ [ Marcar entregado ]               │  único turquesa macizo
│ [ Marcar no entregado ]            │  Boton secundario
│                                    │
│ Partes                             │  h2 text-xl font-bold
│ ┌────────────────────────────────┐ │  section bg-hoja ring-1 ring-linea rounded-xl
│ │ Almacén El Ejemplo             │ │  h3 font-bold
│ │ (comercio ficticio)            │ │  inline-block
│ │ Parte K4M7XP  [✓ Retirado]     │ │  digitos + Etiqueta
│ │ ────────────────────────────── │ │
│ │ 2 × Pañal adulto M x30         │ │  font-bold, cifras
│ │ Paquete de 30 unidades         │ │  text-tenue
│ │ $25.980 · [✓ Lo tiene]         │ │  cifras + Etiqueta ok
│ │ ────────────────────────────── │ │
│ │ 3 × Suplemento vainilla x12    │ │
│ │ $26.490 · [⊗ Faltó]            │ │  Etiqueta neutro PackageX
│ │ Faltan 3 de 3 · Devuelto       │ │  text-tenue
│ │ ────────────────────────────── │ │
│ │ Código de retiro: usado        │ │  text-base, KeyRound
│ └────────────────────────────────┘ │
│                                    │
│ Pago                               │  h2 (7)
│ …                                  │
│ Lo que pasó                        │  h2 (6.6)
│ …                                  │
│ Incidencias                        │  h2 (9.3)
│ [ Anotar una incidencia ]          │  secundario
│ Retractos                          │  h2 (8.4)
│ [ Registrar un retracto por correo]│  secundario
│                                    │
│ ⓘ Datos de prueba. …               │  Nota atenta, al pie
└────────────────────────────────────┘
```

### 6.2 Pantalla ancha

La cola de 5 a la izquierda (19 rem, con la fila elegida marcada) y el detalle a la derecha, en `bg-hoja ring-1 ring-linea rounded-xl px-4 @3xl:px-8 py-5` con `@container/detalle`. Sin `Volver`. El único `h1` es «Pedido `{ref}`» ([C63] 6.2).

Dentro del detalle, desde `@3xl/detalle` (48 rem, 816 px de contenido). Medido en 5a92dc6: a 1920 px el contenido del detalle mide 935 px y queda en dos columnas; a 1280 px mide 770 px y queda en una. La 1.0 decía `@4xl/detalle` (952 px), que nunca se alcanza porque `main` llega a `max-w-7xl`:

```
┌ Pedido 4821  [⛟ En camino]                      [ Marcar entregado ] [ Marcar no entregado ] ┐
│ Pagado el 17/11/2026 a las 13:05                                                             │
├──────────────────────────────────────────────┬──────────────────────────────────────────────┤
│ Partes                                       │ Pago                                         │
│ (las partes, 6.3)                            │ (la conciliación, 7)                         │
│                                              │ Lo que pasó                                  │
│ Incidencias (9.3)                            │ (la línea de tiempo, 6.6)                    │
│ Retractos (8.4)                              │                                              │
└──────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

- `grid grid-cols-1 gap-x-10 gap-y-8 @3xl/detalle:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]`. Siempre `grid-cols-1` en lo chico.
- La cabecera: `flex flex-wrap items-start justify-between gap-x-6 gap-y-3`, el `h1` y la etiqueta a la izquierda y las acciones (`Acciones`) a la derecha. Los botones nunca son de ancho completo en escritorio.

### 6.3 Las partes

- `h2` «Partes» [NUEVO]. Una `section` por parte con `aria-labelledby` en su `h3`. En el detalle ancho, que ya es `bg-hoja`, la parte va sin fondo, con `border-t border-linea pt-4`.
- **`h3`:** `{comercio}` en negrita y, en su propio `inline-block`, «(comercio ficticio)» [L 11] si `ficticio`. Es la primera mención de ese comercio en la pantalla.
- Debajo: «Parte» y `{ref_parte}` en `digitos`, y la `Etiqueta` del estado de la parte con las palabras del comercio ([C63] 5.4: «Por preparar», «Preparando», «Listo para retirar», «Retirado», «Cancelado», con sus íconos).
- **Las líneas**, en `ul divide-y divide-linea`, cada `li` `flex flex-col gap-1 py-3`:
  - «`{cantidad}` × `{producto}`» en `font-bold` (cantidad en `cifras`), `{presentacion}` en `text-tenue` debajo;
  - el precio pagado de la línea en `cifras`, y la `Etiqueta` del estado de la línea [NUEVO]: «Por marcar» (`neutro`, `Circle`), «Lo tiene» (`ok`, `Check`), «Faltó» (`neutro`, `PackageX`), «Devuelto» (`neutro`, `Undo2`);
  - con faltantes: «Faltan `{n}` de `{cantidad}`» [C63] 6.5 y, al lado, el estado de su devolución: «Devuelto» o «Devolución en curso» [NUEVO], en `text-tenue`. El monto se ve en Pago (7), no aquí, para no repetirlo.
- **El código de retiro** cierra cada parte (6.4).

### 6.4 El código de retiro de una parte

**Objetivo:** que quien opera tenga el código para dárselo a quien va a retirar, sabiendo que no lo va a volver a ver y que un código nuevo anula el anterior.

**Lo que se ve según `estado_codigo`** (renglón `flex flex-wrap items-center gap-x-3 gap-y-2` con `KeyRound` `size-5 text-tenue`):

| `estado_codigo` | Texto [NUEVO] | Botón |
|---|---|---|
| `sin_codigo` (parte `lista`) | «Código de retiro: todavía no hay uno.» | «Generar el código» (`secundario`) |
| `vigente` | «Código de retiro: hay uno vigente.» | «Generar un código nuevo» (`secundario`) |
| `vencido` | «Código de retiro: venció.» | «Generar un código nuevo» (`secundario`) |
| `bloqueado` | «Código de retiro: se bloqueó por demasiados intentos en el comercio.» | «Generar un código nuevo» (`secundario`) |
| `usado` | «Código de retiro: ya se usó.» | Ninguno |
| parte que no está `lista` ni cancelada | «Código de retiro: cuando el comercio lo tenga listo.» | Ninguno |

El botón es secundario: la acción principal de la pantalla es la del pedido. Si el pedido no tiene acción principal (por ejemplo, en `listo_retiro`), sigue siendo secundario: así nunca hay dos macizos cuando cambia el estado.

**Confirmar** (C21), con `DialogoConfirmar variante="principal"` e ícono `KeyRound`:

| Parte | Generar | Generar uno nuevo |
|---|---|---|
| Título | ¿Generar el código de retiro de la parte `{ref_parte}`? | ¿Generar un código nuevo para la parte `{ref_parte}`? |
| Texto | Lo verás una sola vez. Tenlo a mano para dárselo a quien va a retirar el pedido. | Lo verás una sola vez. Tenlo a mano para dárselo a quien va a retirar el pedido. |
| Destacado (negrita) | — | El código anterior deja de servir. Si ya se lo diste a alguien, avísale que use el nuevo. |
| Confirmar · ocupado | Generar el código · Generando… | Generar un código nuevo · Generando… |
| Seguir | Volver al pedido | Volver al pedido |

Todos [NUEVO]. El destacado va en negrita porque es lo único que tiene consecuencia fuera de la pantalla (MATU-62 6.3).

**El código, una sola vez** (C20), en el lugar del renglón, dentro de la parte:

```
┌ 🔑 Código de retiro · Parte K4M7XP ┐  section bg-rocio rounded-xl px-5 py-5, h3 con KeyRound
│                                    │
│      482  173                      │  digitos text-6xl (angosto text-3xl) font-bold text-turquesa
│                                    │
│ Vence el 17/11/2026 a las 18:00.   │  font-bold, cifras
│ Dáselo a quien va a retirar el     │  text-base
│ pedido en Almacén El Ejemplo.      │
│ Solo lo verás ahora. Si generas    │  text-base
│ otro, este deja de servir.         │
│ ────────────────────────────────── │
│ Ya lo tengo                        │  Boton texto
└────────────────────────────────────┘
```

- **Los dígitos:** dos grupos de tres en `flex flex-wrap gap-x-10` (con `gap-x-6` el hueco entre grupos se parecía al `tracking-widest` entre dígitos y los grupos no se distinguían), cada grupo en `digitos text-6xl angosto:text-3xl font-bold text-turquesa tracking-widest`. Se agrupan como un teléfono para dictarlos sin perderse. A 320 px con el texto al 200 % los dos grupos bajan uno bajo otro si no caben, y nunca hay desplazamiento horizontal. `text-turquesa` sobre `rocio`: 5,6:1 en claro y 6,7:1 en oscuro (`DISENO.md` 1), como el PIN de MATU-48.
- **Para el lector:** el párrafo de los dígitos lleva `aria-label="Código: 4 8 2 1 7 3"` y los grupos son `aria-hidden`, como el PIN.
- **No se copia:** ningún botón «Copiar», `select-none` en los dígitos, y el código no va en ningún `title`, `aria-live`, aviso ni anuncio. No se intercepta el teclado ni el menú del navegador: se quita la invitación a copiar, no la capacidad de usar el computador.
- **Al mostrarlo,** el foco va al `h3` de la sección (`tabIndex={-1}`), que se lee «Código de retiro · Parte K4M7XP»; los dígitos se leen al avanzar.
- **Desaparece** (se borra de la memoria y se vuelve al renglón, que pasa a «hay uno vigente») al tocar «Ya lo tengo», al salir de `/operacion/pedido` por cualquier camino, al elegir otro pedido, al vencer (a la hora de `expira_en`), al recibir un 401 y al cerrar la entrada. Al volver a abrir el pedido no se ve: solo se puede generar otro.
- **Textos [NUEVO]:** título «Código de retiro · Parte `{ref_parte}`» · «Vence el `{DD/MM/AAAA}` a las `{HH:MM}`.» · «Dáselo a quien va a retirar el pedido en `{comercio}`.» · «Solo lo verás ahora. Si generas otro, este deja de servir.» · «Ya lo tengo».
- **Errores:** 409 (la parte ya no está lista, o se usó): se vuelve a pedir el pedido, `Nota tono="atenta" rol="status"` «Esta parte cambió mientras la veías. Te mostramos cómo quedó.» [NUEVO, del molde de C63 6.9]. 503: `Nota tono="pronto" rol="alert"` «No pudimos generar el código. Vuelve a intentarlo en unos minutos.» [NUEVO]. Red: [L 8] sin «Lo que escribiste sigue aquí.».

### 6.5 Las acciones del pedido

Una sola acción principal por estado (la tabla sale de `acciones`, P3). Cada una abre `DialogoConfirmar` y su confirmación usa **el mismo verbo** que el botón. El monto sale de `monto_a_devolver` de la API.

| Estado | Principal | Otra | 
|---|---|---|
| `retirado`, `reprogramado` | «Marcar en camino» | — |
| `en_ruta` | «Marcar entregado» | «Marcar no entregado» (`secundario`) |
| `no_entregado` | — | «Cancelar con devolución» (`peligro`) |
| `pagado`, `enviado_a_comercio` sin preparar | — | «Cancelar con devolución» (`peligro`) |
| Los demás | — | — |

«Cancelar con devolución» nunca es macizo fuera del diálogo: devolver todo no es la acción principal de ninguna pantalla.

**Los diálogos** (todos [NUEVO]; `{monto}` es `monto_a_devolver`):

| | Marcar en camino | Marcar entregado | Marcar no entregado | Cancelar con devolución |
|---|---|---|---|---|
| Variante | `principal`, `Truck` | `principal`, `PackageCheck` | `peligroPrincipal`, `PackageX` | `peligroPrincipal`, `Undo2` |
| Título | ¿Marcar en camino el pedido `{ref}`? | ¿Marcar entregado el pedido `{ref}`? | ¿Marcar no entregado el pedido `{ref}`? | ¿Cancelar con devolución el pedido `{ref}`? |
| Texto | La familia ve que su pedido salió a entregarse. | Hazlo solo cuando el pedido ya esté en manos de quien lo recibe. Esto no se deshace. | Hazlo si nadie pudo recibirlo. Después puedes cancelarlo con devolución. | Se cancelan todas sus partes y los comercios ven que no deben prepararlas. Esto no se deshace. |
| Destacado, con 0 | No se devuelve dinero. | No se devuelve dinero. | No se devuelve dinero ahora. | — |
| Destacado, con monto | — | Se devuelven `{monto}` a la misma tarjeta, por lo que faltó. | — | Se devuelven `{monto}` a la misma tarjeta con que se pagó, envío incluido. |
| Confirmar · ocupado | Marcar en camino · Marcando… | Marcar entregado · Marcando… | Marcar no entregado · Marcando… | Cancelar con devolución · Cancelando… |
| Seguir | Volver al pedido | Volver al pedido | Volver al pedido | No cancelar |
| Hecho (`Nota ok rol="status"`, recibe el foco) | Marcaste en camino el pedido `{ref}`. | Marcaste entregado el pedido `{ref}`. | Marcaste no entregado el pedido `{ref}`. | Cancelaste el pedido `{ref}`. Estamos devolviendo `{monto}` a la misma tarjeta. |

- El destacado va siempre, también con 0: quien opera tiene que leer cuánto dinero mueve antes de confirmar, aunque sea nada (C22).
- La `Nota` del hecho va sobre las partes y reemplaza a la anterior. La de «Cancelaste» va en `ok` aunque la devolución siga en curso: lo que se hizo, se hizo; el estado de la devolución se ve en Pago.
- Después de confirmar, la pantalla vuelve a pedir el pedido y el cobro, y enfoca la nota del hecho **después** de montarla ([C63] 6.3).

**Errores de las acciones** (en el diálogo, en su región de error, o sobre las partes si el diálogo ya cerró):

| Situación | Qué se ve |
|---|---|
| 409 `estado-pedido` (otra persona del equipo, el comercio o el sistema lo cambió) | El diálogo se cierra. Se vuelve a pedir el pedido. `Nota tono="atenta" rol="status"`: «Este pedido cambió mientras lo veías. Te mostramos cómo quedó. Revisa si todavía hace falta.» [NUEVO, del molde de C63 6.9]. El foco va a la nota |
| 503 al cancelar (sin Transbank) | En el diálogo: «No pudimos hablar con Transbank. El pedido no cambió. Vuelve a intentarlo en unos minutos.» [NUEVO]. Si la respuesta dice que se canceló pero la devolución no salió, la nota del hecho cambia su texto a «Cancelaste el pedido `{ref}`. La devolución de `{monto}` no salió todavía: revísala en «Cobros».» [NUEVO] |
| 404 | `Nota tono="atenta"`: «Este pedido ya no está disponible.» [NUEVO] y «Volver a los pedidos» |
| Red o 5xx | En el diálogo: [L 8] sin «Lo que escribiste sigue aquí.». El pedido se vuelve a pedir al cerrar, porque la acción pudo haberse hecho |

### 6.6 Lo que pasó (la línea de tiempo)

- `h2` «Lo que pasó» [NUEVO] (la misma frase que verá la familia en D-81-4, sin «con tu pedido»).
- Un `ol` del más reciente al más antiguo, cada `li` con `flex gap-3 py-2 border-b border-linea`: la hora a la izquierda en `cifras text-tenue` («17/11 14:20»), y a la derecha la frase en `font-bold` y el actor en `text-tenue` debajo.
- **La frase:** «`{desde}` → `{hacia}`» con las palabras de 5.5 (la flecha `→` es `aria-hidden`, y el lector lee «de En el comercio a En preparación»: el `li` lleva el texto con «de… a…» en un `sr-only`). Con motivo, debajo y en `text-tenue`, la palabra del motivo [NUEVO]: `total_vencio` «Venció el total» · `familia_cancela` «La familia lo canceló» · `familia_cambia_carrito` «La familia cambió el pedido» · `autorizacion_retirada` «Se retiró la autorización de pedidos» · `persona_borrada` «La familia borró los datos» · `pago_aprobado` «Transbank aprobó el pago» · `producto_faltante` «Faltaron todos los productos». Un motivo que la pantalla no conoce no se muestra (el frontend lo pide al orquestador).
- **El actor** [NUEVO] (C6): `familia` «La familia» · `comercio` «`{comercio}`» · `operacion` «Equipo de MATU» · `sistema` «MATU, de forma automática». **Nunca** el nombre de una persona de la familia ni del equipo.
- Ícono por actor, decorativo (`aria-hidden`, `size-5 text-tenue`): `Users`, `Store`, `Headset`, `Cog`. El actor siempre va en palabras.

---

## 7. El pago del pedido (conciliación, en el detalle)

**Objetivo:** que quien opera vea si lo cobrado y lo devuelto calzan con el total confirmado, sin ver nada de la tarjeta.

**Jerarquía:** 1) total confirmado, cobrado y devuelto · 2) el estado de la venta y la orden de compra · 3) cada devolución.

```
│ Pago                               │  h2 text-xl font-bold
│ Total confirmado         $57.460   │  dl grid grid-cols-[minmax(0,1fr)_auto]
│ Cobrado                  $57.460   │  dd cifras text-right
│ Devuelto                −$26.490   │  signo menos U+2212
│ ══════════════════════════════════ │  border-t-2 border-tinta
│ Queda cobrado            $30.970   │  font-bold text-lg
│                                    │
│ Venta    [✓ Aprobada]              │  Etiqueta
│ Orden de compra                    │  dt
│ MATU-4821-7Q2                      │  dd digitos, select-text
│                                    │
│ Devoluciones                       │  h3 font-bold
│ ┌────────────────────────────────┐ │  ul divide-y divide-linea
│ │ Producto no entregado  $26.490 │ │  font-bold + cifras
│ │ [✓ Hecha] · 17/11 14:32        │ │  Etiqueta + cifras text-tenue
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

- **Las cifras** [NUEVO]: «Total confirmado», «Cobrado», «Devuelto» (con `−` y solo las devoluciones hechas), «Queda cobrado» (= cobrado − devuelto, que da la API; la pantalla no resta). Sin cobro todavía: «Cobrado» dice «Nada todavía» [NUEVO].
- **El estado de la venta** [NUEVO], `Etiqueta` con ícono: `iniciada` «Iniciada» (`neutro`, `Circle`) · `autorizando` «Esperando a Transbank» (`atenta`, `Clock`) · `aprobada` «Aprobada» (`ok`, `Check`) · `rechazada` «No aprobada» (`neutro`, `Ban`) · `error` «Sin respuesta clara» (`atenta`, `TriangleAlert`). Sin «rechazada» ni «error» en pantalla (`lenguaje.md` 3.2).
- **«Orden de compra»** [NUEVO] es `buy_order`, en `digitos`, seleccionable (sirve para buscarlo en el portal de Transbank). No va en la URL, el título ni un anuncio (C18). Sin botón de copiar: no hace falta y no es el patrón de la consola.
- **Cada devolución** [NUEVO]: el motivo (`pago_tardio` «Pago tardío» · `producto_no_entregado` «Producto no entregado» · `cancelacion` «Cancelación» · `retracto` «Retracto»), el monto, una `Etiqueta` con el estado («Hecha», `ok`, `Check` · «En curso», `atenta`, `Clock` · «Sin terminar», `atenta`, `TriangleAlert`) y la hora. Si es de una línea, el producto debajo en `text-tenue`.
- **No calza:** si cobrado es mayor que el total confirmado, o hay una devolución «Sin terminar», arriba de las cifras va `Nota tono="atenta" borde`: «**Este pago necesita revisión.** Lo cobrado o lo devuelto no calza con el total confirmado. Anota una incidencia si todavía no hay una.» [NUEVO], con `Boton variante="texto"` «Anotar una incidencia» que abre el formulario de 9.3 con el tipo ya elegido (`cobro_sin_respuesta` o `devolucion_pendiente`). Es lectura: la conciliación no tiene acciones propias (C19).
- **Lo que nunca aparece:** tarjeta, últimos 4, tipo de tarjeta, cuotas, código de autorización, token, `session_id`, `payload_respuesta` (C18). Tampoco el nombre de quien pagó.
- **Cargando, error:** el pedido se ve aunque el cobro falle. En lugar de las cifras: «Cargando el pago…» [NUEVO] o `Nota tono="pronto"` «No pudimos traer el pago de este pedido. Vuelve a intentarlo.» [NUEVO] con «Volver a intentar» [L 26].

---

## 8. Retractos (`/operacion/retractos`)

**Objetivo:** que quien opera resuelva cada retracto dentro del plazo, devolviendo o explicando por qué no.

**Jerarquía:** 1) los que esperan respuesta, el plazo más cercano primero · 2) el elegido, con sus productos y el monto · 3) «Devolver» o «No devolver».

### 8.1 Esquema a 360 px

```
│ Retractos                          │  h1
│ 🛡 Aquí no ves a quién cuida…      │  privacidad (3)
│ Mostrar                            │  GrupoOpciones chips
│ (•) Por resolver ( ) Devueltos     │
│ ( ) Sin devolución                 │
│ ┌────────────────────────────────┐ │  fila (5.3)
│ │ Retracto del pedido 4821       │ │  font-bold, digitos
│ │ $26.490 · Por la app           │ │  cifras · text-tenue (Mail si es por correo)
│ │ ⚠ Responder antes del 27/11    │ │  atenta font-bold si quedan 2 días o menos
│ └────────────────────────────────┘ │
```

**Ancho:** la cola de 19 rem y el detalle a la derecha, como Pedidos.

### 8.2 La lista

- Filtro [NUEVO]: «Por resolver» (`solicitado`, inicial) · «Devueltos» (`devuelto`) · «Sin devolución» (`rechazado`).
- Fila [NUEVO]: «Retracto del pedido `{ref}`» · `{monto}` · «Por la app» o «Por correo» (con `Mail`) · tercera línea: «Pedido el `{DD/MM}`» y, si está por resolver, «Responder antes del `{DD/MM/AAAA}`» (de `plazo_hasta`). Con 2 días o menos, esa línea va en `font-bold text-atenta` con `TriangleAlert`; vencido: «El plazo venció el `{DD/MM/AAAA}`.» en `font-bold text-atenta`.
- Orden: por `plazo_hasta`, el más cercano primero.
- **Más de 200** (`hay_mas`): al pie de la lista, antes del rótulo del piloto, en `text-base text-tenue`: «Hay más de 200 retractos aquí. Mostramos los primeros 200.» [NUEVO]. Reemplaza a «Mostramos los primeros 200.», que no decía que faltaban otros. «Los primeros» se entiende en el orden de la lista, que es el plazo más cercano en «Por resolver».
- Vacío: «No hay retractos por resolver.» [NUEVO] (y «No hay retractos en «`{chip}`».» en los otros).

### 8.3 El retracto elegido

```
│ Retracto del pedido 4821           │  h1 (en ancho, el del detalle)
│ [○ Por resolver]                   │  Etiqueta atenta Circle
│ Pedido el 17/11 · Por la app       │
│ Responder antes del 27/11/2026     │  font-bold
│                                    │
│ Productos que devuelve             │  h2
│ 3 × Suplemento vainilla x12        │  ul divide-y
│ $26.490                            │
│ Incluye el envío: no               │
│ ══════════════════════════════════ │
│ Se devolverían          $26.490    │  font-bold text-lg
│                                    │
│ [ Devolver $26.490 ]               │  único macizo
│ [ No devolver ]                    │  secundario
│ Ver el pedido                      │  Boton texto → /operacion/pedido
```

- Textos [NUEVO]: `h2` «Productos que devuelve» · «Incluye el envío: sí» o «Incluye el envío: no» · «Se devolverían» · el estado en `Etiqueta`: «Por resolver» (`atenta`, `Circle`), «Devuelto» (`ok`, `Undo2`), «Sin devolución» (`neutro`, `Ban`) · «Ver el pedido».
- Las líneas salen de `RetractoVista.lineas` (P6). Un retracto por correo usa las líneas que se registraron (8.5).
- Resuelto: en vez de los botones, «Resuelto el `{DD/MM/AAAA}` a las `{HH:MM}`.» y, si no se devolvió, el motivo (8.4).

### 8.4 Resolver

**Devolver** (`DialogoConfirmar variante="principal"`, `Undo2`) [NUEVO]:
- Título: «¿Devolver `{monto}` por este retracto?»
- Texto: «Es el retracto del pedido `{ref}`. Esto no se deshace.»
- Destacado: «Se devuelven `{monto}` a la misma tarjeta con que se pagó.»
- Confirmar: «Devolver `{monto}`» · «Devolviendo…» · Seguir: «Volver al retracto».
- Hecho (`Nota ok rol="status"`, recibe el foco): «Devolviste `{monto}` por el retracto del pedido `{ref}`. Cuándo se ve en la cuenta depende del banco.»

**No devolver** (`Boton variante="secundario"`; el API lo llama `rechazar`):
1. Al tocarlo, bajo los botones aparece un `GrupoOpciones` de lista, sin opción elegida, con la leyenda «¿Por qué no se devuelve?» [NUEVO] y las dos opciones de la lista cerrada (C24):
   - `sello_abierto`: «El sello del producto se abrió.» [NUEVO];
   - `producto_no_recibido`: «MATU no recibió el producto de vuelta.» [NUEVO] (P5).
   Debajo, en `text-tenue`: «La familia ve este motivo.» [NUEVO]. Mientras está abierto, «Devolver» se oculta: hay un solo macizo, el de este paso. **Al abrirse, el foco va a la primera opción** (el botón que se tocó desaparece; el foco nunca queda en `body`). Con «Cancelar», el grupo se cierra y el foco vuelve a «No devolver».
2. `Boton variante="peligroPrincipal"` «No devolver» y `Boton variante="texto"` «Cancelar» [NUEVO]. Sin motivo elegido: `MensajeError` «Elige por qué no se devuelve.» [NUEVO] y el foco a la primera opción.
3. Con el motivo, `DialogoConfirmar` (`peligroPrincipal`, `Ban`) [NUEVO]: título «¿No devolver el dinero de este retracto?» · texto «Es el retracto del pedido `{ref}`. Esto no se deshace.» · destacado «No se devuelve dinero. La familia ve el motivo: `{motivo_familia}`», donde `{motivo_familia}` es **el texto exacto que lee la familia** en «Tus pedidos» (MATU-92), no la opción de la consola: `sello_abierto` «El producto volvió con el sello abierto.» · `producto_no_recibido` «No recibimos el producto de vuelta.». Así quien opera lee antes de confirmar lo mismo que va a leer la familia · confirmar «No devolver» · «Guardando…» · seguir «Volver al retracto».
4. Hecho: `Nota tono="ok" rol="status"`: «Respondiste el retracto del pedido `{ref}` sin devolver dinero.» [NUEVO].

**Errores:** 409 (ya se resolvió, o el pedido cambió): «Este retracto cambió mientras lo veías. Te mostramos cómo quedó.» [NUEVO]; 503: «No pudimos hablar con Transbank. No se devolvió nada. Vuelve a intentarlo en unos minutos.» [NUEVO]; red: [L 8] sin «Lo que escribiste sigue aquí.».

### 8.5 Registrar un retracto que llegó por correo

**Dónde:** en el detalle del pedido, sección «Retractos» (`h2` [NUEVO]). **La sección solo aparece** si el pedido tiene retractos o se puede registrar uno (entregado y dentro del plazo); si no, no hay `h2` vacío. Lleva la lista de los retractos del pedido, cada fila como 8.2 **con la `Etiqueta` de su estado** («Por resolver», «Devuelto», «Sin devolución») y la línea del plazo si está por resolver, y `Boton variante="secundario"` «Registrar un retracto por correo» [NUEVO]. Abre el formulario en la misma sección; el foco va a su primer campo. Mientras está abierto, la acción principal del pedido se oculta (un solo macizo, como el editor de [C63] 8.3).

```
│ Registrar un retracto por correo   │  h3 font-bold
│ El plazo vence el 27/11/2026.      │  text-tenue (de plazo_hasta)
│                                    │
│ Correo de quien lo pidió           │  CampoTexto type email
│ [                              ]   │
│ Escríbelo tal como viene en el     │  ayuda
│ correo. Tiene que ser de quien     │
│ administra el grupo de este pedido.│
│                                    │
│ ¿Qué productos devuelve?           │  fieldset, legend font-bold
│ 2 × Pañal adulto M x30             │  por línea del pedido
│ ¿Cuántos?  [−] 0 [+]               │  Stepper min 0 max cantidad
│ 1 × Toallitas húmedas x80          │
│ ¿Cuántos?  [−] 1 [+]               │
│                                    │
│ [ Registrar el retracto ]  Cancelar│  principal + texto
```

- **El correo** (`correo_solicitante`, C25): `CampoTexto` «Correo de quien lo pidió» [NUEVO], `type="email"`, `autoComplete="off"` (es el correo de otra persona, no el de quien opera), `spellCheck={false}`, `maxLength` 254, ayuda «Escríbelo tal como viene en el correo. Tiene que ser de quien administra el grupo de este pedido.» [NUEVO]. **Nunca** una lista, un autocompletar ni una sugerencia de correos. Al responder (bien o con 422) el correo **se borra de la memoria y del campo**, y no se repite en ningún aviso.
- **Las líneas:** un `Stepper` por línea del pedido que se entregó, con la `legend` de la línea, la etiqueta «¿Cuántos?» [NUEVO], `min` 0, `max` la cantidad entregada, inicial 0. Las líneas que faltaron no aparecen: ya se devolvieron.
- **El envío no se elige:** lo decide el servidor (`incluye_envio`).
- **Textos [NUEVO]:** `h3` «Registrar un retracto por correo» · «El plazo vence el `{DD/MM/AAAA}`.» · `legend` «¿Qué productos devuelve?» · «Registrar el retracto» · «Registrando…» · «Cancelar».
- **No pide confirmar:** registrar no mueve dinero. El dinero se mueve al resolverlo (8.4), que sí confirma.
- **Hecho:** el formulario se cierra, el retracto nuevo aparece en la lista de la sección y `Nota tono="ok" rol="status"` (recibe el foco): «Registraste el retracto del pedido `{ref}`. Resuélvelo en «Retractos».» [NUEVO], con `Boton variante="texto"` «Ir a Retractos» [NUEVO].

| Situación | Qué se ve [NUEVO] |
|---|---|
| Sin correo | `MensajeError` del campo: «Escribe el correo de quien lo pidió.» |
| Correo con mal formato | «Escribe un correo, por ejemplo nombre@example.com.» |
| Ningún producto | `MensajeError` sobre el botón: «Elige al menos un producto.» y el foco al primer `Stepper` |
| 422, el correo no es de un administrador activo del grupo | `Nota tono="atenta" rol="alert"` sobre el campo: «**Ese correo no es de quien administra el grupo de este pedido.** Revisa el correo. Si lo mandó otra persona, respóndele que lo pida quien administra.» El campo queda vacío y recibe el foco. Nunca dice quién administra |
| 409, fuera de plazo | `Nota tono="atenta" rol="alert"`: «Este pedido ya no tiene plazo de retracto: venció el `{DD/MM/AAAA}`.» |
| Red o 5xx | [L 8] completo, con «Lo que escribiste sigue aquí.»: el correo sí se conserva en este caso, porque no hubo respuesta |

---

## 9. Incidencias (`/operacion/incidencias` y en el pedido)

**Objetivo:** que el equipo anote lo que pasó con un pedido y lo cierre con cómo se resolvió, sabiendo que la familia lo puede leer.

### 9.1 La lista

```
│ Incidencias                        │  h1
│ 🛡 Aquí no ves a quién cuida…      │  privacidad (3)
│ Mostrar                            │  GrupoOpciones chips
│ (•) Abiertas ( ) En gestión        │
│ ( ) Resueltas                      │
│ ┌────────────────────────────────┐ │  fila (5.3)
│ │ Falta un producto  [○ Abierta] │ │  font-bold + Etiqueta
│ │ Pedido 4821                    │ │  digitos
│ │ Anotada el 17/11 a las 14:40   │ │  text-tenue
│ └────────────────────────────────┘ │
```

- Filtro [NUEVO]: «Abiertas» (`abierta`, inicial) · «En gestión» (`en_gestion`) · «Resueltas» (`resuelta`).
- Estado [NUEVO]: «Abierta» (`atenta`, `Circle`) · «En gestión» (`activo`, `Contrast`) · «Resuelta» (`ok`, `CircleCheck`).
- Fila [NUEVO]: el tipo (9.4) en `font-bold` y la `Etiqueta` · «Pedido `{ref}`» · «Anotada el `{DD/MM}` a las `{HH:MM}`». **La nota no va en la fila**: se lee al abrirla. Así la lista no expone texto libre.
- Orden: la más antigua primero en «Abiertas» y «En gestión»; la más reciente en «Resueltas».
- Vacío: «No hay incidencias abiertas.» [NUEVO] (y «No hay incidencias en «`{chip}`».»).
- Ancho: cola de 19 rem y detalle.

### 9.2 La incidencia elegida

```
│ Falta un producto                  │  h1 (en ancho, el del detalle)
│ [○ Abierta]                        │
│ Pedido 4821 · Ver el pedido        │  digitos + Boton texto
│ Anotada el 17/11 a las 14:40       │  text-tenue
│                                    │
│ Nota                               │  h2 text-lg font-bold
│ El comercio avisó que no le llegó  │  whitespace-pre-line, max-w-prose
│ el suplemento.                     │
│                                    │
│ [ Resolver ]                       │  único macizo
│ [ Pasar a en gestión ]             │  secundario (solo si está abierta)
```

- Textos [NUEVO]: «Ver el pedido» · «Anotada el `{DD/MM/AAAA}` a las `{HH:MM}`» · `h2` «Nota» · «Pasar a en gestión» · «Resolver». Ver el pedido lo abre (y eso queda registrado, C9).
- **Quién la anotó o la tiene** no se muestra con nombre: el equipo es de dos personas y la familia no debe leer nombres del equipo en la copia. Si la API trae «asignada a ti», la pantalla dice «La tienes tú.» [NUEVO]; si no, nada.
- **Resuelta:** `h2` «Cómo se resolvió» [NUEVO] con el texto de `resolucion` y «Resuelta el `{DD/MM/AAAA}` a las `{HH:MM}`.» [NUEVO]. Sin acciones.

### 9.3 Anotar y resolver

**Anotar** (en el detalle del pedido, sección «Incidencias», `h2` [NUEVO], con la lista de las del pedido y `Boton variante="secundario"` «Anotar una incidencia» [NUEVO]; solo en pedidos pagados, C12). Abre el formulario en la sección; **el foco va a la primera opción de «¿Qué pasó?»** (o a la ya elegida si viene de «Anotar una incidencia» del pago, 7); mientras está abierto, la acción principal del pedido se oculta. Con «Cancelar», el foco vuelve a «Anotar una incidencia».

```
│ Anotar una incidencia              │  h3 font-bold
│ ¿Qué pasó?                         │  GrupoOpciones forma lista, legend font-bold
│ ( ) Falta un producto              │
│ ( ) No se pudo entregar            │
│ ( ) Reclamo de la familia          │
│ ( ) Cobro sin respuesta            │
│ ( ) Devolución pendiente           │
│ ( ) Otra cosa                      │
│                                    │
│ Nota                               │  label font-bold
│ ┃ No escribas nombres, datos de    │  Nota atenta borde, ayuda del campo
│ ┃ salud ni la dirección. La familia│
│ ┃ puede leer esta nota.            │
│ [                              ]   │  textarea, min-h-32
│ [                              ]   │
│ 0 de 500 caracteres                │  contador text-base text-tenue
│                                    │
│ [ Guardar la incidencia ] Cancelar │  principal + texto
```

- **La ayuda** va **antes** del campo, como `Nota tono="atenta" borde` con `TriangleAlert`, y en el `aria-describedby` del `textarea`. Texto exacto [A81, C11]: «No escribas nombres, datos de salud ni la dirección. La familia puede leer esta nota.». Va arriba y no debajo porque tiene que leerse antes de escribir, y en `atenta` porque es una advertencia, no una explicación.
- **El campo:** el `textarea` de `EditorSeccion` (`bg-hoja ring-2 ring-inset ring-borde focus-visible:ring-turquesa rounded-xl px-4 py-3 text-lg`), `maxLength` 500, `spellCheck` por omisión, `autoComplete="off"`. Contador «`{n}` de 500 caracteres» [L, `textos.ts`], con `aria-live="polite"` solo desde 450.
- **Textos [NUEVO]:** `h3` «Anotar una incidencia» · `legend` «¿Qué pasó?» · `label` «Nota» · «Guardar la incidencia» · «Guardando…» · «Cancelar».
- **No pide confirmar:** no mueve dinero ni cambia el pedido.
- Hecho: el formulario se cierra, la incidencia aparece en la sección y `Nota tono="ok" rol="status"` (recibe el foco): «Anotaste la incidencia en el pedido `{ref}`.» [NUEVO].

| Situación | Qué se ve [NUEVO] |
|---|---|
| Sin tipo | `MensajeError` en el grupo: «Elige qué pasó.» y el foco a la primera opción |
| Nota vacía | `MensajeError` del campo: «Escribe qué pasó, sin nombres ni datos de salud.» |
| Más de 500 (422) | «La nota admite hasta 500 caracteres. Acórtala un poco para guardarla.» (molde de [L 6.5]) |
| El pedido no está pagado (409 o 422 del trigger) | `Nota tono="atenta"`: «Solo se anotan incidencias de pedidos pagados.» |
| Red o 5xx | [L 8] completo, con «Lo que escribiste sigue aquí.» |

**Pasar a en gestión** (`PATCH` con `If-Match`, `estado: en_gestion`, `asignada_a`: quien opera): sin diálogo, porque se deshace al resolver y no mueve dinero. Hecho: anuncio `status` «La incidencia quedó en gestión.» [NUEVO]; la `Etiqueta` cambia y el foco se queda en «Resolver».

**Resolver:** abre en el detalle un `textarea` con la etiqueta «Cómo se resolvió» [NUEVO], la misma `Nota` de ayuda antes del campo (también la familia lo lee, C11), el contador de 500, y `Boton variante="principal"` «Marcar resuelta» · «Guardando…» [NUEVO] con «Cancelar». Resolver no se deshace, pero el formulario ya es el segundo paso: no lleva diálogo. Sin texto: «Escribe cómo se resolvió, sin nombres ni datos de salud.» [NUEVO]. Hecho: `Nota ok rol="status"` (recibe el foco): «Marcaste resuelta la incidencia.» [NUEVO].

**412 al cambiar** (otra persona del equipo la cambió): `Nota tono="atenta" rol="status"` sobre el formulario: «Otra persona del equipo cambió esta incidencia mientras la veías. Te mostramos cómo quedó. Lo que escribiste sigue aquí.» [NUEVO, del molde de L 6.2]. La incidencia se vuelve a pedir, el `textarea` conserva lo escrito y el `ETag` nuevo se usa al volver a guardar. Si ya quedó resuelta, el formulario se cierra y lo escrito se descarta, con «Ya estaba resuelta.» [NUEVO] en la nota.

### 9.4 Los tipos

| `tipo` (D-81-3) | En pantalla [NUEVO] |
|---|---|
| `faltante` | Falta un producto |
| `entrega_fallida` | No se pudo entregar |
| `reclamo_familia` | Reclamo de la familia |
| `cobro_sin_respuesta` | Cobro sin respuesta |
| `devolucion_pendiente` | Devolución pendiente |
| `otro` | Otra cosa |

Son palabras de la consola. Lo que lee la familia en su copia se decide en MATU-54 y MATU-92, bajo «Lo que pasó con tu pedido» (D-81-4).

---

## 10. Cobros por revisar (`/operacion/cobros`)

**Objetivo:** que quien opera vea en un lugar los cobros y las devoluciones que quedaron a medias, para revisarlos antes de que la familia pregunte.

**Jerarquía:** 1) las ventas sin respuesta · 2) las devoluciones sin terminar · 3) el rótulo del piloto.

```
│ Cobros                             │  h1
│ Ventas sin respuesta y devoluciones│  text-base text-tenue max-w-prose
│ sin terminar. Aquí no ves la       │
│ tarjeta ni el código de            │
│ autorización.                      │
│                                    │
│ ◷ Ventas sin respuesta (1)         │  h2, Clock text-atenta
│ ┌────────────────────────────────┐ │  fila (5.3)
│ │ Pedido 4823          $41.980   │ │  digitos + cifras
│ │ Orden de compra MATU-4823-K2   │ │  digitos text-tenue
│ │ Iniciada a las 13:40, hace 38  │ │  font-bold text-atenta
│ │ minutos                        │ │
│ └────────────────────────────────┘ │
│ ↶ Devoluciones sin terminar (0)    │  h2, Undo2 text-atenta
│ No hay devoluciones sin terminar.  │  text-tenue
```

- **Ancho:** una columna de `max-w-3xl`, sin detalle al lado: cada fila abre `/operacion/pedido` (con la pestaña «Cobros» activa y «Volver a los cobros»), donde está el pago completo (7).
- **Bajada** [NUEVO]: «Ventas sin respuesta y devoluciones sin terminar. Aquí no ves la tarjeta ni el código de autorización.»
- **Grupos** [NUEVO], `h2` con ícono, palabra y número, **también con 0** (aquí el cero es la buena noticia): «Ventas sin respuesta (`{n}`)» · «Devoluciones sin terminar (`{n}`)». Vacíos: «No hay ventas sin respuesta.» · «No hay devoluciones sin terminar.».
- **Fila de venta** [NUEVO]: «Pedido `{ref}`» y el monto · «Orden de compra `{buy_order}`» · «Iniciada a las `{HH:MM}`, hace `{n}` minutos» (más de 15, C17; la hora de la cabecera `Date`). Estado de la venta como en 7.
- **Fila de devolución** [NUEVO]: «Pedido `{ref}`» y el monto · el motivo (7) · «Desde las `{HH:MM}`» · `Etiqueta` «En curso» o «Sin terminar».
- **Sin acciones** (C19): se revisa en el pedido y, si hace falta, se anota una incidencia.
- Estados: cargando «Cargando los cobros…» [NUEVO]; error «No pudimos traer los cobros. Revisa tu conexión y vuelve a intentarlo.» [NUEVO] con «Volver a intentar»; refresco y «Actualizar» como 5.6; 401 y 404 como 5.7.

---

## 11. Catálogo de prueba (`/operacion/catalogo`)

**Objetivo:** que quien opera ajuste el precio, la cantidad y si se ofrece cada producto de los comercios de prueba, sabiendo que el precio nuevo no cambia lo ya confirmado.

**Jerarquía:** 1) el aviso de que el precio nuevo vale para los pedidos nuevos · 2) los productos por comercio, con su precio · 3) «Cambiar» y su editor.

### 11.1 Esquema a 360 px

```
│ Catálogo                           │  h1
│ ┃ ⓘ El precio nuevo vale solo para │  Nota rocio borde
│ ┃ los pedidos que se confirmen     │
│ ┃ desde ahora. Los confirmados y   │
│ ┃ los pagados mantienen su precio. │
│ Solo puedes cambiar los comercios  │  text-base text-tenue
│ de prueba.                         │
│                                    │
│ Almacén El Ejemplo                 │  h2 text-xl font-bold
│ (comercio ficticio)                │
│ ┌────────────────────────────────┐ │  li bg-hoja ring-1 ring-linea rounded-xl
│ │ Pañal adulto M x30             │ │  h3 text-lg font-bold
│ │ Paquete de 30 unidades         │ │  text-tenue
│ │ $12.990 · IVA incluido         │ │  cifras text-lg font-bold + text-tenue
│ │ Tiene           14             │ │  dl
│ │ [✓ Se ofrece]                  │ │  Etiqueta ok
│ │ [ Cambiar ]                    │ │  secundario
│ └────────────────────────────────┘ │
```

**Editando** (uno a la vez, en el lugar de «Cambiar»):

```
│ │ Precio, con IVA incluido       │ │  CampoTexto inputMode numeric, max-w-48
│ │ $ [ 12990    ]                 │ │  «$» delante, text-tenue, aria-hidden
│ │ Se verá como $12.990.          │ │  ayuda, aria-live polite
│ │ ¿Cuántos tiene?                │ │  CampoTexto inputMode numeric, max-w-40
│ │ [ 14 ]                         │ │
│ │ [x] Se ofrece en MATU          │ │  casilla size-6
│ │ [ Guardar ]  Cancelar          │ │  principal + texto
```

### 11.2 Pantalla ancha

Como «Tus productos» del comercio ([C63] 8.2): una columna de `max-w-3xl`, cada producto en `@xl/main:grid-cols-[minmax(0,1fr)_18rem]`, con el nombre, la presentación y el precio a la izquierda y la cantidad, el estado y «Cambiar» a la derecha. Las notas de la fila van a todo el ancho (`@xl/main:col-span-2`).

### 11.3 Reglas

- **Solo los comercios de prueba** (C1, D-81-7). Un comercio real, si la API lo trae, se lista con su `h2` sin «(comercio ficticio)», sus productos en solo lectura y, bajo el `h2`, «Este comercio no es de prueba: aquí no se cambia.» [NUEVO] en `text-tenue`. Sin botón «Cambiar».
- **El precio** se muestra como `$69.000` (punto de miles, sin decimales) seguido de «· IVA incluido» [NUEVO] en `text-tenue` (C2). Nunca «+ IVA» ni el IVA aparte.
- **El campo del precio:** etiqueta «Precio, con IVA incluido» [NUEVO], `inputMode="numeric"`, `autoComplete="off"`. Acepta «69000» y «69.000» (se quitan los puntos); no acepta comas ni decimales. La ayuda «Se verá como `{precio}`.» [NUEVO] cambia al escribir, con `aria-live="polite"`, para que quien opera lea la cifra con su punto antes de guardar (un cero de más es un precio diez veces mayor).
- **«¿Cuántos tiene?»** [NUEVO], con la regla del comercio («Escribe un número, desde 0.», «Escribe un número hasta 9.999.» [C63] 8.4). «Tiene» [NUEVO] en el `dl`, nunca «stock».
- **«Se ofrece en MATU»** [NUEVO]: casilla nativa en el editor. Fuera del editor, `Etiqueta` «Se ofrece» (`ok`, `Check`) o «No se ofrece» (`neutro`, `Ban`) [C63].
- **Un editor a la vez:** mientras uno está abierto, los «Cambiar» de las demás filas se ocultan (un solo «Guardar», [C63] 8.3). Sin editor abierto, la pantalla no tiene botón principal.
- **«Guardar»** · «Guardando…» [L 5.4], `PATCH` con `If-Match` (C4). **Con el precio cambiado**, antes de enviar, `DialogoConfirmar variante="principal"` (`Tag`) [NUEVO]: título «¿Cambiar el precio de `{producto}` a `{precio}`?» · texto «Antes era `{precio_anterior}`.» · destacado «Vale solo para los pedidos que se confirmen desde ahora.» · confirmar «Cambiar el precio» · «Guardando…» · seguir «Volver a editar». Sin cambio de precio, guarda sin diálogo.
- **Hecho:** el editor se cierra, la fila cambia y se anuncia `status`: «Guardado: `{producto}` a `{precio}`, tiene `{n}`.» [NUEVO]. El foco vuelve a «Cambiar» de esa fila.
- **El aviso de arriba** [NUEVO]: `Nota tono="rocio" borde` con `Info`: «El precio nuevo vale solo para los pedidos que se confirmen desde ahora. Los confirmados y los pagados mantienen su precio.» (C3). Bajo él: «Solo puedes cambiar los comercios de prueba.» [NUEVO].
- **Rótulo del piloto** al pie, una vez: el de 3.

### 11.4 Errores y estados

| Situación | Qué se ve [NUEVO salvo que diga] |
|---|---|
| Precio vacío, 0, con letras, coma o decimales | `MensajeError` del campo: «Escribe el precio en pesos, mayor que 0, sin decimales. Por ejemplo, 12990.» |
| 412 | `Nota tono="atenta" rol="status"` en la fila: «Otra persona cambió este producto mientras lo editabas. Te mostramos cómo quedó.» [C63] 8.4. El editor sigue abierto con lo escrito |
| 409 o 404 (el comercio no es de prueba, o dejó de estar) | `Nota tono="atenta" rol="alert"` en la fila: «Este producto no se puede cambiar aquí: su comercio no es de prueba.». El editor se cierra y la fila queda en solo lectura |
| Red o 5xx | [L 8] completo, sobre «Guardar» |
| Cargando | «Cargando el catálogo…» después de un segundo |
| Vacío | «No hay comercios de prueba con productos.» en `text-xl font-bold` |
| Error al traer | `Nota tono="pronto" rol="alert"`: «No pudimos traer el catálogo. Revisa tu conexión y vuelve a intentarlo.» y «Volver a intentar» [L 26] |

---

## 12. Lo que las pantallas necesitan del contrato

| Dato | Dónde |
|---|---|
| `mfa-requerido` con `desafio` y `expira_en`; `POST /v1/sesiones/mfa`; los tres fallos del código (P1, P2) y `tipo_cuenta: "operacion"` | 4 |
| El vencimiento de la entrada (12 horas) en la respuesta | La barra (3) |
| `POST /v1/operacion/pedidos/buscar` (referencia en el cuerpo) y la lista con varios estados (P4), con `referencia`, `estado`, `total_confirmado`, el número de partes, `pagado_en` y dos marcas: incidencia abierta y devolución sin terminar | 5 |
| `GET /v1/operacion/pedidos/{id}`: partes (`id`, `referencia`, `comercio` con `nombre_fantasia` y `ficticio`, `estado`, `estado_codigo`), líneas (`producto`, `presentacion`, `cantidad`, precio pagado, `estado_linea`, `unidades_faltantes`, estado de su devolución), la línea de tiempo (`desde`, `hacia`, `motivo`, `actor_tipo`, nombre del comercio si es comercio, `en`) y `acciones` con `monto_a_devolver` (P3) | 6 |
| `POST …/partes/{id}/codigo` → `codigo`, `expira_en` (ya existe) | 6.4 |
| `GET …/pedidos/{id}/cobro`: total confirmado, cobrado, devuelto, queda cobrado, estado de la venta, `buy_order`, devoluciones (motivo, monto, estado, `en`, producto) | 7 |
| `GET /v1/operacion/cobros/pendientes` | 10 |
| `RetractoVista` con `referencia` y `lineas` (P6); `motivo` en `SolicitudResolverRetracto`; `correo_solicitante` en `SolicitudRetractoPorCorreo`; `plazo_hasta` del pedido | 8 |
| Incidencias: lista por estado, crear, `PATCH` con `If-Match`, `ETag` (P7), y si está asignada a quien pregunta | 9 |
| `GET /v1/operacion/catalogo` (comercio con `ficticio`, oferta con `precio`, `stock`, `disponible`, `ETag`) y `PATCH /v1/operacion/ofertas/{id}` | 11 |
| La cabecera `Date` de cada respuesta | «hace `{n}` minutos», «Responder antes del» |

**Lo que las pantallas no usan y no deben recibir:** nombre, nivel de apoyo, dirección o teléfono de la persona cuidada; `persona_cuidada_id`, `grupo_id` ni nombre del grupo; `usuario_id` o nombre de quien pidió o pagó; `actor_ref` de una cuenta de familia; tarjeta, últimos 4, tipo, cuotas, código de autorización, token, `session_id`, `payload_respuesta`; el hash del código de retiro; la lista de miembros del grupo (C5, C6, C18, C25).

---

## 13. Accesibilidad visual

- **Texto:** nada bajo `text-base` (17 px). Lo secundario va en `tenue`, nunca más chico. La prueba `textoMinimo17.test.ts` cubre `web/src/operacion/`.
- **Contraste:** todos los pares salen de `DISENO.md` 1 y de la consola del comercio ([C63] 10): `papel` sobre `tinta` 14,1:1 y 15,4:1; `papel` al 85 % 10,5:1 y 10,3:1; `turquesa` sobre `rocio` (los dígitos del código) 5,6:1 y 6,7:1; `atenta` sobre `hoja` y `atenta-fondo`, `ok` sobre `ok-fondo` y `pronto` sobre `pronto-fondo`, los medidos. Ningún par nuevo.
- **Áreas táctiles:** toda fila, chip, opción, casilla con su etiqueta, botón (también los de texto), pestaña, «Salir», «Actualizar», «Ya lo tengo» y botón del `Stepper` miden `min-h-12` (51 px) o `size-12`.
- **Foco:** el contorno base de 3 px en `turquesa` con 2 px de separación, y en `papel` dentro de la barra. Al llegar a cada ruta, al `h1`; en el paso 2 de Entrar, al `h1` del paso; después de una acción, a la nota del resultado, montada con su contenido final; al mostrar el código, al `h3` de su sección; al cerrar un diálogo sin hacer nada, al botón que lo abrió. **En ningún caso el foco termina en `body`.**
- **Estado nunca solo por color:** cada `Etiqueta` lleva ícono y palabra; cada grupo, `h2` con ícono, palabra y número; lo que pide atención en la fila lleva `TriangleAlert` y palabra; el dinero devuelto lleva el signo `−` y la palabra «Devuelto».
- **Reflujo:** sin desplazamiento horizontal a 320 px con el texto al 200 % (160 px de app). Toda grilla declara `grid-cols-1` en lo chico; chips, acciones, pestañas y los dos grupos del código van en `flex-wrap`; los `dl` usan `grid-cols-[minmax(0,1fr)_auto]`; la orden de compra y la referencia se parten con `break-words` (`overflow-wrap` de la capa base).
- **Plazos:** el desafío de 5 minutos y la entrada de 12 horas se dicen con su hora, sin cuenta regresiva y con un camino para volver a empezar (WCAG 2.2.1).
- **Movimiento:** ninguno propio. Las notas aparecen con `aparecer` (180 ms), que `prefers-reduced-motion` vuelve inmediato. Los dígitos del código **no** caen uno a uno como el PIN: aquí no hay un momento orquestado, hay trabajo. Las páginas cambian sin deslizarse.
- **Regiones vivas:** se anuncia lo que pasa por una acción (los hechos de 6.5, 8.4, 8.5, 9.3, 11.3) y los resultados de Entrar. Nunca la hora de actualización, nunca el código de retiro, nunca un correo.
- **Diálogos:** `DialogoConfirmar` (`<dialog>` con `showModal()`, foco inicial en el título, Esc cierra si no hay una petición en curso).

---

## 14. Criterios visuales verificables

1. **Un solo macizo.** En cada pantalla y estado hay a lo sumo **un** elemento con `bg-turquesa` o `bg-pronto` fuera de un diálogo abierto. En Pedidos, Cobros, Retractos sin elegir, Incidencias sin elegir y Catálogo sin editor, ninguno.
2. **Sin datos de la familia.** Ninguna pantalla de `/operacion` muestra un nombre de persona, una dirección, un teléfono, un grupo ni un correo, salvo el que se escribe en 8.5 mientras se escribe. Un `grep` de `web/src/operacion/` no encuentra «María», «Carmen», «Rosa», «Rodrigo» ni «grupo_id», ni un campo de dirección (`direccion`, `comuna`, `region` como propiedad de un dato). La palabra «dirección» aparece **una sola vez**, en la ayuda obligatoria de C11 («No escribas nombres, datos de salud ni la dirección. La familia puede leer esta nota.», `INCIDENCIAS.ayuda` de `textos.ts`), que es una advertencia y no un dato: el criterio se cumple si esa es la única coincidencia. Lo que se verifica en pantalla es que ningún texto visible de `/operacion` traiga una dirección, un nombre o un teléfono de la familia.
3. **Sin tarjeta.** Ninguna pantalla muestra «terminada en», últimos 4, tipo de tarjeta, cuotas ni código de autorización. «Orden de compra» sí aparece en el pago y en Cobros.
4. **Nada en la URL.** Ninguna ruta de `/operacion` lleva un id, una referencia, un `buy_order`, un correo ni un código. La búsqueda es un `POST` con la referencia en el cuerpo. Recargar `/operacion/pedido` lleva a `/operacion`. El `<title>` del pedido no lleva la referencia.
5. **El código del teléfono:** el campo tiene `autocomplete="one-time-code"`, `inputmode="numeric"` y `type="text"`; pegar «482 173» deja «482173»; con 6 números no envía solo.
6. **Los tres fallos de Entrar** (no coincide, cinco fallos, desafío vencido) muestran tres notas distintas, cada una se anuncia una vez y recibe el foco. Ninguna dice si el correo existe.
7. **El código de retiro, una vez:** después de «Ya lo tengo», de salir de la ruta, de elegir otro pedido o de vencer, los dígitos no están en el DOM. No hay botón de copiar, los dígitos tienen `select-none`, y el código no aparece en `localStorage`, `sessionStorage`, `history.state`, el `<title>` ni las regiones vivas.
8. **Regenerar** muestra en negrita «El código anterior deja de servir.» antes de confirmar.
9. **Cada acción del pedido** abre un diálogo cuyo botón de confirmar repite el verbo del botón que lo abrió, y su destacado dice un monto o «No se devuelve dinero».
10. **El monto** de los diálogos es el `monto_a_devolver` de la API: el código de `web/src/operacion/` no resta montos para mostrarlos.
11. **Retracto:** «No devolver» no envía sin uno de los dos motivos; el diálogo dice «La familia ve el motivo».
12. **Retracto por correo:** el campo del correo tiene `autocomplete="off"`; después de cualquier respuesta del servidor el campo está vacío; ningún aviso repite el correo; no hay lista ni sugerencias de correos.
13. **Incidencia:** la ayuda «No escribas nombres, datos de salud ni la dirección. La familia puede leer esta nota.» está a la vista antes del campo y en su `aria-describedby`, al anotar y al resolver. El `textarea` tiene `maxlength="500"` y contador.
14. **Línea de tiempo:** cada hecho dice su actor en palabras («La familia», el comercio, «Equipo de MATU», «MATU, de forma automática»), nunca un nombre de persona.
15. **Catálogo:** todo precio se ve como `$12.990 · IVA incluido`; el aviso «El precio nuevo vale solo para los pedidos que se confirmen desde ahora…» está a la vista; un comercio real no tiene «Cambiar».
16. **Estado nunca solo por color:** toda `Etiqueta` tiene ícono y palabra (la palabra queda en `angosto`).
17. **Reflujo:** a 320 px con el texto al 200 %, ninguna de las siete rutas tiene desplazamiento horizontal (`scrollWidth` igual a `clientWidth` en `html`), con el código de retiro a la vista, con un diálogo abierto, con el formulario del retracto por correo y con el editor del catálogo.
18. **Ancho:** a 1280 px, Pedidos, Retractos e Incidencias muestran la cola de 19 rem y el detalle; a 1920 px, el detalle del pedido tiene dos columnas (partes a la izquierda; pago y lo que pasó a la derecha), desde `@3xl/detalle` (6.2); a 1280 px, una sola.
19. **La barra** es `bg-tinta text-papel`, su foco es `papel`, «Salir» no usa `turquesa`, y `DistintivoPiloto` está fuera de ella, a la vista en las siete rutas y con el texto al 200 %.
20. **Foco:** después de cada acción de 13, `document.activeElement` no es `body`.
21. **Lenguaje:** ninguna pantalla dice «token», «sesión», «stock», «inválido», «rechazado», «rechazada», «fallido» ni un código de error, ni ninguno de los términos de `lenguaje.md` 3.1.
22. **Tokens:** ningún color, tamaño ni sombra escrito a mano en `web/src/operacion/`.
23. **Tema oscuro:** la barra sigue en `tinta` con texto `papel` (invertida) y todos los pares de 13 se cumplen.

---

## 15. Textos nuevos para `lenguaje.md`

Todos los **[NUEVO]** de este documento entran a `lenguaje.md` en una sección nueva, «La consola de operación (MATU-81)», en el PR de documentos de MATU-81, y Jorge los aprueba antes de construir. La sección lleva esta regla, como la 36:

**Regla de la sección.** La consola es interna: la usa el equipo de MATU. Puede decir «incidencia», «orden de compra», «retracto» y «venta». Nunca muestra el nombre de la persona cuidada ni de la familia, su dirección, su teléfono, su grupo, la tarjeta ni el código de autorización. Nunca dice «token», «sesión», «stock», «inválido», «rechazado» ni «fallido» (lo que el API llama `rechazar`, en pantalla es «No devolver»; lo que llama `rechazada`, «No aprobada»). Lo que la familia lee de lo que hace el equipo va en la copia de sus datos, bajo «Lo que pasó con tu pedido» (D-81-4), y se escribe en MATU-54 y MATU-92, no aquí.

**Los textos que no son del diseñador:** la ayuda de la nota [A81, C11] va tal cual. Los de [E39], [C63] y [L n] ya están aprobados.
