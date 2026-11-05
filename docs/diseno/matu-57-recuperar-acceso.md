# MATU-57 · Recuperar el acceso y verificar el celular · Especificación de diseño

**Versión 0.1 · 03-11-2026 · agente 6 UI/UX.** Base: MATU-39 (`docs/diseno/matu-39-app-familia.md`, secciones 3.2, 3.3 y 4), `Demo/DISENO.md` y los tokens de `Demo/src/index.css`, `docs/lenguaje.md` (13.3). **Sin tokens nuevos.** Todo usa `MarcoAlta`, `CampoTexto`, `Boton`, `Nota`, `MensajeError` y `Volver` ya especificados en MATU-39.

---

## 0. Lo que tiene que decidir alguien más

| # | Pregunta | Propuesta |
|---|---|---|
| D1 | Las decisiones del 03-11 dicen «email». lenguaje.md y MATU-39 (D1) dicen «correo». | Usar **«correo»** en todos los textos. Los textos de abajo ya están así. |
| D2 | El texto final dice «cerramos tu sesión en todos tus dispositivos». lenguaje.md prohíbe «sesión». | «Listo. Cambiamos tu contraseña. Por seguridad, tendrás que volver a entrar en tus otros teléfonos y computadores.» **[aprobado por Jorge el 03-11]** |
| D3 | ¿Después de cambiar la contraseña, la app entra sola o pide entrar? | **Pide entrar** (en `/entrar`, con el correo ya escrito en memoria y el aviso de éxito arriba). Es un paso más, pero confirma que la contraseña nueva funciona y no requiere que la API emita tokens en la recuperación. Si el backend prefiere entrar directo, el aviso va a la ficha en vez de `/entrar`. |
| D4 | El aviso de verificar el celular «en la primera entrada»: ¿es un paso obligatorio o se puede omitir? | **Se puede omitir** («Ahora no»). No bloquea llegar a la ficha. Vuelve a ofrecerse desde el perfil. |
| D5 | Dónde está «el perfil». MATU-39 no especifica pantalla de perfil. | **Aprobado:** «Tu cuenta» va en la cabecera del `Shell`, junto a «Salir», con la fila del celular (sección 5.2). |

---

## 1. Para quién y qué

- **Carmen olvidó la contraseña.** Está apurada y quizás en el teléfono que usa para todo. Quiere volver a la ficha de María en tres pasos: correo, código, contraseña nueva.
- **Nunca se revela** si un correo tiene cuenta ni a qué canal llegó el código (decisión del analista).
- **Verificar el celular** se explica como ayuda («para que puedas recuperar tu cuenta»), nunca como amenaza ni como requisito de seguridad.

Rutas **[PROPUESTO]**: `/entrar/recuperar` (pedir código) y `/entrar/recuperar/codigo` (código y contraseña nueva); `/cuenta/celular` (verificar). **El correo nunca va en la URL ni en `localStorage`/`sessionStorage`**: vive en memoria (el mismo estado del flujo). Si la persona recarga en `/entrar/recuperar/codigo` y el correo se perdió, se vuelve a `/entrar/recuperar` con el campo vacío y sin aviso de error.

---

## 2. Pedir el código (`/entrar/recuperar`)

**Objetivo:** «Escribo mi correo y me mandan algo para volver a entrar.»
**Jerarquía:** 1) el título, 2) el campo del correo, 3) «Enviar código».

**A 360 px:**

```
(♥) MATU      [Piloto académico / con datos de prueba]

< Volver a entrar                       Volver, 48 px
Recupera tu cuenta                      titular text-3xl
Escribe tu correo y te enviaremos un    text-tenue
código para crear una contraseña nueva.

Tu correo
[                              ]

[ Enviar código ]                       único turquesa macizo
```

**Pantalla ancha:** `MarcoAlta` sin pasos, panel izquierdo sobre `hoja` con la marca y la frase de MATU-39; formulario a la derecha en `max-w-xl` (campo de una columna). Botón **no** de ancho completo.

| Elemento | Texto |
|---|---|
| Volver | «Volver a entrar» **[aprobado por Jorge el 03-11]** |
| Título (h1) | «Recupera tu cuenta» **[aprobado por Jorge el 03-11]** |
| Bajada | «Escribe tu correo y te enviaremos un código para crear una contraseña nueva.» **[aprobado por Jorge el 03-11]** |
| Campo | «Tu correo», `type="email"`, `autoComplete="email"`, `maxLength={254}`. Si viene de `/entrar` con el correo escrito, se precarga desde memoria |
| Botón | «Enviar código» / ocupado «Enviando…» **[aprobado por Jorge el 03-11]** |
| Validación cliente | vacío o sin `@`: «Revisa tu correo.» (MATU-39) |

**Estados**

- **Enviando:** botón `disabled`, `aria-busy`, texto «Enviando…». El campo no se borra.
- **202/200 (siempre, exista o no la cuenta):** pasa a `/entrar/recuperar/codigo` y arriba muestra `Nota tono="rocio"` con `role="status"`: «Si hay una cuenta con ese correo, te enviamos un código. Puede tardar un minuto.» **[aprobado por Jorge el 03-11, con «correo» por D1]**. El foco va al h1 de la pantalla siguiente.
- **Sin 429:** `POST /v1/recuperacion/codigo` responde siempre 202 (decisión 82); esta pantalla no tiene estado de espera.
  - Nota: decir «el último código todavía sirve» no revela que la cuenta exista si la API responde 429 igual para correos sin cuenta (requisito a la API, sección 6).
- **503 / red / 5xx:** los textos de MATU-39 3.3 en `Nota tono="pronto"`.

---

## 3. Escribir el código y la contraseña nueva (`/entrar/recuperar/codigo`)

**Objetivo:** «Copio el código que me llegó y elijo una contraseña nueva.»
**Jerarquía:** 1) el título, 2) el campo del código, 3) la contraseña nueva, 4) «Cambiar contraseña». El reenvío al correo es secundario.

**A 360 px:**

```
< Volver
[i] Si hay una cuenta con ese correo,    Nota rocio, role=status
    te enviamos un código. Puede
    tardar un minuto.

Escribe el código                       titular text-3xl
Te lo enviamos por mensaje al celular   text-tenue
o al correo. Tiene 6 números.

Código
[ _ _ _ _ _ _ ]                         un solo input, text-2xl, tracking amplio
Nueva contraseña
[                              ] [Mostrar]
Al menos 10 caracteres.

[ Cambiar contraseña ]                  único turquesa macizo

¿No te llegó?                           text-tenue
Pide que te lo enviemos a tu correo     Boton variante="texto", 48 px
```

**Pantalla ancha:** igual a la sección 2; código y contraseña en una columna (son dos campos, no vale la pena partir).

| Elemento | Texto |
|---|---|
| Título | «Escribe el código» **[aprobado por Jorge el 03-11]** |
| Bajada | «Te lo enviamos por mensaje al celular o al correo. Tiene 6 números.» **[aprobado por Jorge el 03-11]** (no dice cuál, no revela el canal) |
| Campo código | Etiqueta «Código» **[aprobado por Jorge el 03-11]** |
| Campo contraseña | «Nueva contraseña» **[aprobado por Jorge el 03-11]**, ayuda «Al menos 10 caracteres.» (MATU-39), botón Mostrar/Ocultar de MATU-39 |
| Botón | «Cambiar contraseña» / «Cambiando…» **[aprobado por Jorge el 03-11]** |
| Reenvío | «¿No te llegó?» + botón de texto «Pide que te lo enviemos a tu correo» **[aprobado por Jorge el 03-11]**, alineado a la izquierda bajo «¿No te llegó?», sin padding horizontal, 48 px de alto. **Aprobado:** queda `disabled` 60 s desde el último envío, sin cuenta regresiva, con «Puedes pedir otro en un minuto.» debajo. |
| Tras reenviar | `Nota tono="rocio"`, `role="status"`: «Si hay una cuenta con ese correo, te enviamos un código nuevo al correo. Puede tardar un minuto.» **[aprobado por Jorge el 03-11]** (sin «El código anterior ya no sirve»: dentro de 60 s la API no envía otro y el anterior sigue sirviendo) |

**Campo del código (accesibilidad):** un solo `<input>`, nunca seis cajas. `type="text"`, `inputMode="numeric"`, `autoComplete="one-time-code"`, `pattern="[0-9]*"`, `maxLength={6}`, `autoCorrect="off"`, `spellCheck={false}`. Acepta pegar con espacios o guiones y los quita en el cliente. Tipografía `text-2xl` con `font-variant-numeric: tabular-nums` (utilidad `tabular-nums` de Tailwind, sin token nuevo) y `tracking-widest` **solo aquí** (es un código, no una etiqueta en mayúsculas; no contradice DISENO.md 5). Ancho `max-w-60` para que no parezca un campo de texto libre. Alto mínimo 48 px.

**Validación cliente** (al enviar, foco al primer error, `aria-describedby`):
- Código con menos de 6 números: «El código tiene 6 números.» **[aprobado por Jorge el 03-11]**
- Contraseña corta: «La contraseña necesita al menos 10 caracteres.» (MATU-39)

**Estados**

- **Cambiando:** botón `disabled`, `aria-busy`, campos sin borrar.
- **Éxito (204/200):** va a `/entrar` con el correo precargado en memoria y `Nota tono="ok"`, `role="status"`, foco al h1: «Listo. Cambiamos tu contraseña. Por seguridad, tendrás que volver a entrar en tus otros teléfonos y computadores.» **[aprobado por Jorge el 03-11, D2]**. Ícono `CircleCheck` (nunca solo el verde).
- **Código incorrecto o vencido (400/422 con un solo tipo, sección 6):** `MensajeError` bajo el campo del código, borde `pronto` + `CircleAlert`: «El código no es correcto o ya venció. Pide uno nuevo.» **[aprobado por Jorge el 03-11]**. El código se vacía, la contraseña **se conserva**, el foco va al campo del código. El enlace «Pide que te lo enviemos a tu correo» queda visible justo debajo.
- **Demasiados intentos con el código (429):** `Nota tono="atenta"`: «Hubo varios intentos con ese código. Pide uno nuevo en `{minutos}` minutos.» **[aprobado por Jorge el 03-11]**. Botón principal y reenvío `disabled` hasta `Retry-After`.
- **422 contraseña:** «La contraseña necesita entre 10 y 128 caracteres.» (MATU-39).
- **Red / 5xx / 503:** textos de MATU-39 3.3.

---

## 4. Cambios en `/entrar` (MATU-39 3.3)

- Aparece el enlace «¿Olvidaste tu contraseña?» bajo la contraseña, de texto `turquesa` subrayado, 48 px de alto. Lleva a `/entrar/recuperar` pasando el correo escrito **en memoria**.
- **429 de entrar, texto nuevo** (reemplaza el de lenguaje.md 13.3): «Hubo varios intentos de entrar. Espera `{minutos}` minutos.» seguido, dentro de la misma `Nota`, del enlace «Recupera tu cuenta» **[aprobado por Jorge el 03-11]** (sin repetir «¿Olvidaste tu contraseña?», que ya está bajo el campo). El enlace sigue activo mientras el botón «Entrar» está `disabled`.
- Aviso de éxito de la sección 3 (tono `ok`), sobre el formulario.

---

## 5. Verificar el celular

### 5.1 Ofrecimiento tras la primera entrada (`/cuenta/celular`)

**Aprobado:** se muestra **solo en la primera visita**, después de `/empezar/autorizacion` (o al entrar, si la cuenta tiene celular sin verificar y nunca se ofreció). No es un modal: es una pantalla dentro del `Shell`. «Ahora no» lleva a la ficha.

**Objetivo:** «Confirmo mi celular para no perder la cuenta si olvido la contraseña.»
**Jerarquía:** 1) el título, 2) la explicación con el número, 3) «Enviar código», 4) «Ahora no».

**A 360 px, paso A (pedir):**

```
Confirma tu celular                     titular text-3xl
Si algún día olvidas la contraseña,     text-tinta
te enviaremos un código a este número
para que puedas volver a entrar.

Tu celular
+56 9 5555 0137                         text-lg, solo lectura
Cambiar número                          Boton texto (lleva al campo editable)

¿Cómo prefieres recibir los códigos?    radios, aprobado (sección 6)
( ) Mensaje de texto (SMS)
( ) WhatsApp

[ Enviar código ]                       único turquesa macizo
Ahora no                                Boton texto, 48 px
```

**Paso B (confirmar), en la misma pantalla, reemplaza el bloque del botón:**

```
[i] Te enviamos un código al            Nota rocio, role=status
    +56 9 •••• 0137.

Código
[ _ _ _ _ _ _ ]
[ Confirmar ]                           único turquesa macizo
¿No te llegó? Enviar otro código        Boton texto a la izquierda, px-0 (disabled 60 s, sección 6)
Ahora no
```

El número enmascarado no se corta en dos líneas (`whitespace-nowrap`). El contenido termina con padding inferior mayor que la barra fija del teléfono, que no lo tapa. Aquí sí se muestra el número (enmascarado) porque la persona ya está dentro y es su dato.

**Pantalla ancha:** dentro del `Shell`, contenido en `max-w-xl`, alineado a la izquierda; botones en línea (`flex-wrap gap-3`), no de ancho completo.

| Elemento | Texto |
|---|---|
| Título | «Confirma tu celular» **[aprobado por Jorge el 03-11]** |
| Explicación | «Si algún día olvidas la contraseña, te enviaremos un código a este número para que puedas volver a entrar.» **[aprobado por Jorge el 03-11]** |
| Botón A | «Enviar código» / «Enviando…» **[aprobado por Jorge el 03-11]** |
| Secundario | «Ahora no» **[aprobado por Jorge el 03-11]**; «Cambiar número» **[aprobado por Jorge el 03-11]** |
| Aviso B | «Te enviamos un código al `{celular enmascarado}`.» **[aprobado por Jorge el 03-11]** |
| Botón B | «Confirmar» / «Confirmando…» **[aprobado por Jorge el 03-11]** |
| Canal (paso A) | «¿Cómo prefieres recibir los códigos?»: «Mensaje de texto (SMS)» o «WhatsApp» **[aprobado]** |
| Reenvío | «¿No te llegó? Enviar otro código» **[aprobado por Jorge el 03-11]**; 60 s `disabled` con «Puedes pedir otro en un minuto.» **[aprobado]** |
| Éxito | `Nota tono="ok"`: «Listo. Tu celular quedó confirmado.» **[aprobado por Jorge el 03-11]**; botón principal «Ir a la ficha» **[aprobado por Jorge el 03-11]** (desde el perfil: vuelve a «Tu cuenta») |
| Código malo/vencido | «El código no es correcto o ya venció. Pide uno nuevo.» (el mismo de 3) |
| Celular inválido al cambiarlo | «Escribe un celular de Chile, por ejemplo +56 9 5555 0137.» (lenguaje 8) |
| 429 | «Ya pediste varios códigos. Espera `{minutos}` minutos y vuelve a intentarlo.» **[aprobado por Jorge el 03-11]** |
| Envío falló (proveedor SMS caído, 503) | «No pudimos enviar el mensaje ahora. Vuelve a intentarlo en unos minutos.» **[aprobado por Jorge el 03-11]** |

### 5.2 Desde «Tu cuenta» (D5)

Una fila con `Etiqueta`: «Tu celular · +56 9 •••• 0137» y la etiqueta `ok` «Confirmado» con `Check`, o neutra «Sin confirmar» **[aprobado por Jorge el 03-11]** con el botón secundario «Confirmar celular» **[aprobado por Jorge el 03-11]** que abre 5.1 sin «Ahora no» (en su lugar `Volver`). El estado va con palabra, nunca solo con color.

---

## 6. Qué necesita de la API (al orquestador y al backend)

1. **Pedir código de recuperación** (`POST`, cuerpo `{email}`): responde **siempre igual** (mismo código y mismo tiempo aproximado) exista o no la cuenta. El 429 también debe responder igual para correos sin cuenta, o el texto «el último código todavía sirve» se quita.
2. **Reenviar al correo**: el mismo endpoint con un indicador de canal (`canal: "correo"`) o uno propio. La respuesta no dice a qué canal fue el primero.
3. **Cambiar con código** (`POST`, `{email, codigo, contrasena_nueva}`): un **solo** tipo de error para código incorrecto, vencido o ya usado (`/errores/codigo-invalido` **[PROPUESTO]**), sin distinguir cuenta inexistente. 422 con `errores[].campo = contrasena_nueva`. Al éxito revoca todos los refresh tokens. ¿Emite tokens o no? (D3).
4. **429 con `Retry-After`** en los tres, y en los intentos con un código.
5. **Verificar celular** (autenticado): pedir código y confirmar código; el perfil (`GET /v1/usuarios/yo` o equivalente) expone `celular_enmascarado` y `celular_verificado: boolean`, y si ya se ofreció (o el cliente decide solo con `celular_verificado`). Cambiar el número lo deja sin verificar.
6. **Reenvío mínimo** sugerido: 60 s entre envíos; el cliente deshabilita «Enviar otro código» ese tiempo sin anunciar cuenta regresiva y lo deja visible con el texto «Puedes pedir otro en un minuto.» **[aprobado por Jorge el 03-11]**.
7. Nunca el email, el código ni el celular en la URL, en logs ni en mensajes de error.

---

## 7. Accesibilidad y criterios visuales verificables

- En cada pantalla, el botón principal es el **único** elemento `turquesa` macizo. «Ahora no», «Cambiar número» y los reenvíos son de texto.
- Todo lo tocable mide al menos 48 × 48 px (enlaces de texto con `min-h-12 inline-flex items-center`).
- Campo del código: `inputMode="numeric"`, `autoComplete="one-time-code"`, etiqueta visible, error con `aria-describedby` y `aria-invalid`.
- Los avisos que llegan al cambiar de pantalla usan `role="status"`; los errores bajo el campo se anuncian por `aria-describedby` y el foco se mueve al campo.
- Estado nunca solo por color: `Nota` con ícono propio (`Info`, `TriangleAlert`, `CircleAlert`, `CircleCheck`) y texto; «Confirmado»/«Sin confirmar» con palabra.
- Sin desplazamiento horizontal a 320 px ni con texto al 200%: el código en `text-2xl` con `max-w-60` cabe a 320 px con zoom (se verifica en la revisión).
- `prefers-reduced-motion`: el cambio de paso A a B es inmediato; sin animación en ningún caso.
- Sin género asumido: todos los textos en tú sin adjetivos con género («Listo», no «Lista»).
- Ningún texto dice «sesión», «token», «autenticar», «verificar identidad» ni «email».

## 8. Textos que pasan a `lenguaje.md` (13.3, al aprobarse)

Todos los marcados **[aprobado por Jorge el 03-11]** arriba, más el reemplazo del 429 de entrar (sección 4). Los dos que eran de instrucción se copian con «correo» en vez de «email» (D1).

## 9. Cómo la voy a revisar

Funcionando, con capturas a 360, 1280 y 1920 px, tema claro y oscuro y texto al 200%, recorriendo: entrar → olvidé → enviar → código malo → reenviar al correo → código bueno → entrar con aviso; 429 en cada paso; verificar celular desde la primera entrada y desde «Tu cuenta». Pruebo el autocompletado del código con el teclado numérico del teléfono emulado.
