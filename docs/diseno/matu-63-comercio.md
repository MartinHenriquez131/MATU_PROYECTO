# MATU-63 · La vista web del comercio · Especificación de diseño

**Versión 1.0 · 13/11/2026** · agente 6 (UI/UX) · para el frontend
**Historia:** MATU-63, la preparación y el retiro de cada parte del pedido en el comercio (ADR-027, capa 3). Quien atiende un comercio ve los pedidos que le tocan, marca qué tiene y qué no, avisa que está listo y revisa el código de quien viene a buscarlo. También dice cuántos tiene de cada producto y si lo ofrece en MATU.
**Dónde se construye:** `web/`, una app aparte bajo `/comercio`, con React 19, TypeScript y Tailwind CSS v4, mobile first.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · las decisiones del orquestador del 13-11 sobre la revisión previa del analista (D-63-1 a D-63-16), en especial D-63-2, D-63-3, D-63-4, D-63-5, D-63-6, D-63-7 y D-63-8 · los textos de la sección 4.5 de esa revisión, tal como los resumió el orquestador · ADR-027, puntos 4, 5 y 6 · `lenguaje.md` secciones 2, 3, 8 y 11 · las escenas 24 a 26 de `Demo/ESPEC-ADR-027.md` (la consola validada en la demo) · `docs/diseno/matu-39-app-familia.md` 3.3 (Entrar) · el código de `web/src/compartido/ui/`, `web/src/familia/ui.tsx` y `web/src/relevo/PantallaPin.tsx`.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual en pantalla. Marcas de origen:
- **[A45]** texto del analista, sección 4.5 de su revisión previa;
- **[AJUSTE]** un texto de [A45] que cambio, con el porqué;
- **[L nn]** texto ya aprobado en esa sección de `lenguaje.md`;
- **[E39]** texto de Entrar en `matu-39-app-familia.md` 3.3;
- **[NUEVO]** un texto mío, que Jorge aprueba antes de construir.

Las llaves son datos de la API: `{nombre}` es el `nombre_fantasia` del comercio de la cuenta, `{ref}` la referencia opaca de la parte, `{producto}` el `nombre` del producto («Pañal adulto M x30»), `{presentacion}` su presentación («Paquete de 30 unidades»), `{cantidad}` la cantidad de envases de la línea, `{HH:MM}` en 24 horas y hora de Chile, `{precio}` en pesos enteros con punto de miles.

**Tokens:** **ningún token nuevo**, ningún color nuevo y ninguna regla nueva en la capa base. Todo sale de los componentes que ya existen (`Boton`, `Nota`, `Etiqueta`, `CampoTexto`, `GrupoOpciones` con `forma="chips"`, `Stepper`, `MensajeError`, `Pestanas`, `Volver`, `Acciones`, `Anunciado`, `DistintivoPiloto`, `BotonMostrar` de `Alta.tsx`) y de cuatro piezas que el frontend arma con tokens existentes: la **barra de la consola** (3), la **fila de la cola** (5.3), la **línea por marcar** (6.4) y el **campo del código** (7.2). `DISENO.md` cambia en dos frases, sin tokens: el foco dentro de la barra `tinta` y la referencia en `digitos` (sección 13).

---

## 0. Puntos abiertos

Ninguno bloquea empezar: cada uno tiene una propuesta, y la pantalla se construye con ella hasta que se decida otra cosa.

| # | Qué | Para quién | Propuesta |
|---|---|---|---|
| O1 | **Distinguir una cuenta de comercio de una de familia al entrar.** La pantalla tiene que saber si la cuenta que entró es de un comercio, para ir a `/comercio`, y qué responder si una cuenta de familia entra por `/comercio/entrar` (o al revés) | Backend | La respuesta de la sesión trae el tipo de cuenta (`familia` o `comercio`). Una cuenta de familia en `/comercio/entrar` ve el aviso de 4.4, y una de comercio en `/entrar` va sola a `/comercio`. Nunca se dice si el correo existe |
| O2 | **«Avisa a MATU» no tiene un canal.** Seis textos del analista terminan en «Avisa a MATU» (código bloqueado, vencido, cuenta inactiva) y no hay en la app un teléfono ni un correo de operación | Jorge y backend | Un solo contacto de operación del piloto (correo o teléfono de la serie 5555), de configuración y no del código, que la pantalla muestra al pie de cada vista (5.6) y que los avisos nombran: «Avisa a MATU: `{contacto}`». Sin él, el texto queda sin canal y es un P2 |
| O3 | **Todos los productos de una parte faltan.** «Listo para retirar» no tiene sentido si no hay nada que entregar, y D-63-8 dice que entonces se devuelve todo | Backend y Jorge | Con todas las líneas en «No lo tengo», el botón principal dice «Avisar que no tengo ninguno» **[NUEVO]**, la parte pasa a `cancelada` con el motivo `producto_faltante` y la pantalla muestra 6.8. Si el backend prefiere `lista` sin líneas, la pantalla no cambia de texto, solo de estado final |
| O4 | **Hasta cuándo se puede cambiar una marca.** La pantalla supone que «Lo tengo» y «No lo tengo» se pueden cambiar hasta tocar «Listo para retirar», y que la devolución por un faltante sale recién ahí. Si la devolución saliera al marcar, un toque equivocado le devolvería dinero a una familia | Backend | `comercio_marcar_linea` se puede llamar otra vez sobre la misma línea mientras la parte esté en `preparando`, y el evento de la devolución sale con `comercio_listo` |
| O5 | **Qué cuenta «Tienes».** La pantalla de productos (8) le pide al encargado lo que cuenta en su local. Hay que saber si `stock` incluye lo apartado y cuándo baja | Backend | `stock` es lo que hay en el local para vender, **incluido lo apartado que todavía no se prepara**. Al marcar «Listo para retirar», lo preparado sale de `stock` y de `apartado` a la vez. «Disponibles» = `stock` − `apartado`, nunca bajo 0. Si el backend lo define distinto, cambian la ayuda del campo y la cifra «Disponibles», no la pantalla |
| O6 | **El alfabeto de la referencia.** Se dicta letra a letra en el mostrador | Backend | Seis caracteres de mayúsculas y números sin los que se confunden al dictar o al leer (sin `0`, `O`, `1`, `I`, `L`), por ejemplo `K4M7XP`. La pantalla los muestra en `digitos` y en grupos de tres para el lector (`K4M 7XP`) solo si el backend no lo hace |

**Lo que este documento no decide:** la pantalla de operación, que genera y regenera el código y marca «en camino», «entregado» y «no entregado» (MATU-81, D-63-5 y D-63-6); lo que ve la familia de cada parte, el retracto y la cancelación después de pagar (MATU-92); los textos de la política 0.19 y de las condiciones 0.3 (analista, D-63-16).

---

## 1. Para quién y qué

**Quien atiende el mostrador** de una farmacia o un almacén, con el teléfono en una mano y clientes esperando. Abre MATU entre una venta y otra: ve qué pedido le toca, lo prepara, y cuando llega alguien a buscarlo le pide el código y lo escribe. No tiene tiempo de aprender nada: cada pantalla tiene **una** cosa que hacer y la dice con un verbo.

En el piloto, el comercio es **de prueba** (`ficticio`), con una cuenta `@example.com`, y los pedidos son inventados.

**Lo que estas pantallas nunca hacen:**
- Mostrar quién pide, para quién es ni a dónde va: ningún nombre, dirección, teléfono, grupo ni persona cuidada (D-63-1). Tampoco el `pedido_id`, la referencia corta de la familia, montos, precios del pedido ni lo que se devolvió.
- Mostrar el código de retiro. El encargado lo **escribe**, nunca lo **ve** (D-63-5).
- Ofrecer cambiar un producto por otra marca u otro producto (RF-21, ADR-027).
- Cambiar el precio (D-63-2): se ve, pero no se edita.
- Marcar «en camino» ni «entregado»: el comercio llega hasta «retirado» (D-63-6).
- Guardar algo de un pedido en `localStorage`, `sessionStorage` ni la URL. Las rutas no llevan ids ni la referencia.
- Decir «stock», «reserva», «reservar», «token», «sesión», «inválido», «rechazado» ni un código de error (`lenguaje.md` 3). En pantalla es «Tienes», «Apartados» y «Disponibles».

---

## 2. Rutas y navegación

### 2.1 Rutas

Una rama propia en `main.tsx`, como `/r` y `/privacidad`: el prefijo `/comercio` monta `AppComercio`, sin `ProveedorFamilia`, con `RegionesVivas` antes de la app.

| Ruta | Pantalla | Pública | `<title>` | Sección |
|---|---|---|---|---|
| `/comercio/entrar` | Entrar como comercio | Sí | «Entrar como comercio · MATU» | 4 |
| `/comercio` | Pedidos de hoy | No | «Pedidos de hoy · `{nombre}` · MATU» | 5 |
| `/comercio/pedido` | Un pedido (la parte elegida) | No | «Pedido `{ref}` · MATU» | 6 y 7 |
| `/comercio/productos` | Tus productos | No | «Tus productos · `{nombre}` · MATU» | 8 |

- **La parte elegida vive en la memoria de la página**, nunca en la URL. Al recargar `/comercio/pedido`, o si la parte ya no viene en la lista, la app va a `/comercio` con `replace`.
- Sin la entrada vigente, toda ruta no pública va a `/comercio/entrar` y vuelve a la misma ruta después de entrar (sin la parte elegida).
- **Al llegar a cada ruta, el foco va al `h1`** (la regla de la app). Elegir otra parte en pantalla ancha también es llegar a `/comercio/pedido`: el foco va al `h1` del pedido.
- La navegación es la de la familia (`navegar`, sin recargar). El botón Atrás del navegador vuelve de `/comercio/pedido` a `/comercio`.

### 2.2 Las dos pestañas

Bajo la barra, en todas las rutas no públicas, `Pestanas` con `etiqueta="Secciones del comercio"`:

| Pestaña | Ruta | Texto |
|---|---|---|
| 1 | `/comercio` (activa también en `/comercio/pedido`) | «Pedidos de hoy» |
| 2 | `/comercio/productos` | «Tus productos» |

Sin barra inferior en el teléfono: son dos secciones y caben arriba (ESPEC-ADR-027 7.6.4). Sin número en la pestaña (MATU-61 2.2).

---

## 3. El marco: la barra de la consola

**Objetivo:** que quien atiende sepa en un vistazo que está en la cuenta de su comercio, y pueda salir.

```
360 px
┌────────────────────────────────────┐
│ ▣ Almacén El Ejemplo               │  bg-tinta text-papel, font-bold
│   (comercio ficticio)              │  inline-block: baja entero
│   Pedidos de MATU        ⇥ Salir   │  opacity-85 · Boton de texto en papel
├────────────────────────────────────┤
│ ● Piloto académico con datos de    │  DistintivoPiloto, sobre papel
│   prueba                           │
│ Pedidos de hoy │ Tus productos     │  Pestanas
└────────────────────────────────────┘

Ancho (≥ 48 rem de app)
┌ ▣ Almacén El Ejemplo (comercio ficticio)   Pedidos de MATU              ⇥ Salir ┐  bg-tinta
├─────────────────────────────────────────────────────────────────────────────────┤
│ Pedidos de hoy   Tus productos                    ● Piloto académico con datos… │  Pestanas + distintivo a la derecha
└─────────────────────────────────────────────────────────────────────────────────┘
```

- **Barra:** `header` con `bg-tinta text-papel`, `px-4 angosto:px-2 @3xl/app:px-10 py-3`, `flex flex-wrap items-center gap-x-5 gap-y-1`. Es la consola de `DISENO.md` 3: más sobria que la app de la familia, porque es otra persona con otro trabajo. El texto `papel` sobre `tinta` mide 14,1:1 en claro y 15,4:1 en oscuro, y «Pedidos de MATU» al 85 % mide 10,5:1 y 10,3:1.
- **Ícono:** `Store` de lucide, `size-6`, `aria-hidden`. No el logo: el círculo `marca` sobre `tinta` oscura queda en 2,9:1.
- **Nombre:** `{nombre}` en negrita y, en su propio `inline-block`, «(comercio ficticio)» **solo si** `ficticio` es `true` [L 11]. Es la primera mención del comercio en cada pantalla, así que no se repite más abajo.
- **«Salir»:** `Boton variante="texto"` con el ícono `LogOut`, con `text-papel decoration-papel/40` en vez de `turquesa` (el `turquesa` sobre `tinta` mide 2,4:1 en claro y 1,6:1 en oscuro). Mide `min-h-12`.
- **Foco dentro de la barra:** `[&_:focus-visible]:outline-papel` en el `header`. La demo usaba `outline-miel`, que en oscuro mide 1,5:1 contra `tinta`: en `web/` es `papel`, 14,1:1 y 15,4:1 (sección 13).
- **Distintivo:** `DistintivoPiloto` **fuera** de la barra, sobre `papel`, porque su `bg-tinta/7 text-tenue` no se ve sobre `tinta`. En el teléfono va en su propio renglón, arriba de las pestañas. Desde `@3xl/app`, en la misma fila de las pestañas, a la derecha (`ms-auto`). Visible siempre, también con el texto al 200 % [L 11].
- **Contenido:** `main` con `@container/main px-4 angosto:px-2 @3xl/app:px-10 pt-6 pb-16`, y dentro `max-w-7xl` alineado a la izquierda.

---

## 4. Entrar como comercio (`/comercio/entrar`)

**Objetivo:** que quien atiende entre a los pedidos de su comercio con dos datos.

**Jerarquía:** 1) el título, que dice que es la entrada del comercio · 2) los dos campos · 3) «Entrar».

### 4.1 Esquema

```
360 px                                  Ancho: la misma columna, max-w-md, alineada a la izquierda
┌────────────────────────────────────┐
│ ▣ Pedidos de MATU                  │  Store + font-bold, sobre papel (sin barra: aún no hay comercio)
│ ● Piloto académico con datos de    │  DistintivoPiloto
│   prueba                           │
│                                    │
│ Entrar como comercio               │  h1 titular text-3xl (angosto: text-2xl)
│ Para quien atiende un comercio que │  text-lg text-tenue max-w-prose
│ trabaja con MATU.                  │
│                                    │
│ [aviso, si corresponde]            │  Nota (4.3)
│ Tu correo                          │  CampoTexto
│ [                              ]   │
│ Tu contraseña                      │  CampoTexto + BotonMostrar
│ [                       ] [Mostrar]│
│ [ Entrar ]                         │  único turquesa macizo
│                                    │
│ ¿Olvidaste tu contraseña? Avisa a  │  text-base text-tenue
│ MATU: {contacto}.                  │
│ ¿Cuidas a alguien? Entra en la app │  frase + EnlaceEnFrase a /entrar
│ de MATU para familias.             │
└────────────────────────────────────┘
```

- **Reutiliza** la lógica y las piezas de `Entrar` de `Alta.tsx` (MATU-39 3.3): `CampoTexto`, `BotonMostrar`, el 429 con `aria-disabled` y el foco que se queda en el botón. **No** reutiliza `MarcoAlta`: su panel turquesa es la bienvenida de la familia.
- Columna `flex max-w-md flex-col gap-5`, en `main` con `px-4 angosto:px-2 py-8`.
- Sin «¿Olvidaste tu contraseña?» como enlace: la recuperación por celular (MATU-57) es de las cuentas de familia. Va como frase, sin `href`.

### 4.2 Textos

| Parte | Texto | Origen |
|---|---|---|
| Título | Entrar como comercio | **[NUEVO]** |
| Bajada | Para quien atiende un comercio que trabaja con MATU. | **[NUEVO]** |
| Campos | Tu correo · Tu contraseña · Mostrar · Ocultar | [E39] |
| Botón | Entrar · mientras envía: Entrando… | [E39] |
| Faltan datos | Escribe tu correo y tu contraseña. | [E39] |
| Olvido | ¿Olvidaste tu contraseña? Avisa a MATU: `{contacto}`. | **[NUEVO]**, depende de O2 |
| A la familia | ¿Cuidas a alguien? Entra en la `app de MATU para familias`. | **[NUEVO]**, la parte marcada es el enlace a `/entrar` |

### 4.3 Avisos y errores

| Situación | Componente | Texto | Origen |
|---|---|---|---|
| 401 `credenciales-invalidas` | `Nota tono="pronto" rol="alert"`, bajo los campos | El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo. | [E39] |
| 429 | `Nota tono="atenta" rol="status"`, arriba; botón con `aria-disabled` hasta que pase el tiempo | Hubo varios intentos de entrar. Espera `{minutos}` minutos. | [E39] sin «pídele ayuda a alguien de tu familia» **[AJUSTE]**: no es una familia |
| Entrada vencida | `Nota tono="rocio" rol="status"`, arriba | Hace tiempo que no entrabas. Vuelve a entrar con tu correo y tu contraseña. | [L 8] |
| Después de «Salir» | `Nota tono="rocio" rol="status"`, arriba | El texto de «Salir» de la familia (MATU-39 2.4) | [E39] |
| Cuenta de familia (O1) | `Nota tono="atenta" rol="status"`, arriba | **Esta cuenta es de la app para familias.** Para ver los pedidos de un comercio, entra con la cuenta del comercio. | **[NUEVO]** |
| Cuenta o comercio inactivo (403) | `Nota tono="atenta" rol="status"`, arriba | **Esta cuenta de comercio no está activa.** Avisa a MATU: `{contacto}`. | **[NUEVO]** |
| 503, red o 5xx | `Nota tono="pronto" rol="alert"` | Los de MATU-39 3.3 | [E39], [L 8] |

**200:** si la cuenta es de comercio, va a la ruta guardada o a `/comercio`. El token queda solo en memoria, como en la familia.

---

## 5. Pedidos de hoy (`/comercio`)

**Objetivo:** que quien atiende vea en un vistazo qué pedido le toca preparar primero.

**Jerarquía:** 1) lo que hay que preparar, por la hora en que tiene que estar · 2) lo que está en curso y lo que espera retiro · 3) lo terminado, el rótulo del piloto y el aviso de privacidad.

### 5.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (barra, distintivo y pestañas, 3)  │
├────────────────────────────────────┤
│ Pedidos de hoy                     │  h1 titular text-3xl
│ 🛡 Aquí ves solo los productos.    │  ShieldCheck turquesa + text-base text-tenue
│   MATU no te muestra de quién es   │
│   el pedido ni a dónde va.         │
│ Actualizado a las 14:20. Actualizar│  text-base text-tenue + Boton texto
│                                    │
│ ○ Por preparar (2)                 │  h2 text-xl font-bold, ícono Circle en atenta
│ ┌────────────────────────────────┐ │  fila (5.3), button
│ │ Pedido K4M7XP                  │ │  font-bold, ref en digitos
│ │ 3 productos                    │ │
│ │ ⚠ Era para las 14:00.          │ │  atenta, font-bold, TriangleAlert
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Pedido R8T2WQ                  │ │
│ │ 1 producto                     │ │
│ │ Preparar antes de las 16:30    │ │  tenue
│ └────────────────────────────────┘ │
│ ◐ Preparando (1)                   │  h2, Contrast en tenue
│ ┌ Pedido H6N3VD · 2 productos ...┐ │
│ ▣ Listos para retirar (1)          │  h2, PackageCheck en ok
│ ┌ Pedido ...                     ┐ │
│ ✓ Retirados (3)                    │  h2, CircleCheck en tenue
│ ┌ Pedido ... · Retirado 13:20    ┐ │
│ ⊘ Cancelados (1)                   │  h2, Ban en tenue
│ ┌ Pedido ... · No lo prepares    ┐ │
│                                    │
│ ⓘ Comercio de prueba.              │  Nota atenta, ícono Info (rótulo del piloto)
│   Estos pedidos son inventados.    │
│ ¿Algo no calza? Avisa a MATU: …    │  pie (5.6)
└────────────────────────────────────┘
```

### 5.2 Pantalla ancha (contenedor `main` desde 48 rem)

```
Pedidos de hoy                                   h1
🛡 Aquí ves solo los productos. MATU no te muestra de quién es el pedido ni a dónde va.
Actualizado a las 14:20. Actualizar
┌ cola, 19 rem ─────────────┐  ┌ detalle ───────────────────────────────────────────┐
│ ○ Por preparar (2)        │  │                                                     │
│ [Pedido K4M7XP          ] │  │  Elige un pedido de la lista para prepararlo.       │  text-lg text-tenue
│ [Pedido R8T2WQ          ] │  │                                                     │
│ ◐ Preparando (1)          │  └─────────────────────────────────────────────────────┘
│ …                         │
│ ⓘ Comercio de prueba. …   │
└───────────────────────────┘
```

- Grilla `grid grid-cols-1 items-start gap-x-8 gap-y-8 @3xl/main:grid-cols-[19rem_minmax(0,1fr)]`: la cola de 19 rem es la medida fija de la consola en `DISENO.md` 3. Siempre `grid-cols-1` en el ancho chico.
- En el teléfono **no hay** columna de detalle: la cola ocupa todo y tocar una fila lleva a `/comercio/pedido`.
- El cuadro vacío del detalle (solo en ancho) es `bg-hoja ring-1 ring-linea rounded-xl px-6 py-6`, sin ícono ni acción. Se ve solo en `/comercio`: en `/comercio/pedido` el detalle es el de 6.

### 5.3 La fila de la cola

- Un `ul` por grupo, `flex flex-col gap-2`. Cada `li` lleva un `button` de ancho completo de la columna (es una fila de lista, no un botón de acción): `flex w-full min-h-12 flex-col items-start gap-0.5 rounded-xl bg-hoja px-4 angosto:px-2 py-3 text-left ring-1 ring-linea hover:ring-borde`.
- **Primera línea:** «Pedido» y la `{ref}` en `digitos font-bold`. **Segunda:** «`{n}` productos» («1 producto»). **Tercera:** depende del grupo (5.4).
- **Elegida** (en ancho, en `/comercio/pedido`): `aria-current="true"`, `bg-rocio`, `ring-2 ring-turquesa` y la primera línea con el ícono `ChevronRight` al final. Es navegación, no estado: por eso puede ir en `turquesa`, y además cambia la forma (anillo de 2 px y el ícono), no solo el color.
- El nombre accesible del `button` es todo su texto, en orden: «Pedido K4M7XP, 3 productos, Era para las 14:00».
- Orden dentro de cada grupo: por «preparar antes de», la más temprana primero. Retirados y cancelados: el más reciente primero.

### 5.4 Los grupos

Un grupo sin partes no se muestra. El `h2` lleva el ícono, la palabra y el número: el estado nunca va solo por el color ni solo por la posición.

| Grupo (`h2`) | Estado de la parte | Ícono (lucide, `size-5`, `aria-hidden`) | Tercera línea de la fila |
|---|---|---|---|
| «Por preparar» | `enviada` | `Circle` en `text-atenta` | «Preparar antes de las `{HH:MM}`» en `text-tenue`. Atrasada: «Era para las `{HH:MM}`.» en `font-bold text-atenta` con `TriangleAlert` |
| «Preparando» | `preparando` | `Contrast` en `text-tenue` | Igual que «Por preparar» |
| «Listos para retirar» | `lista` | `PackageCheck` en `text-ok` | «Esperando retiro» en `text-tenue` |
| «Retirados» | `retirada` | `CircleCheck` en `text-tenue` | «Retirado a las `{HH:MM}`» en `text-tenue`, si el contrato trae la hora |
| «Cancelados» | `cancelada` | `Ban` en `text-tenue` | «No lo prepares.» en `font-bold` |

- **Atrasada:** la hora de «preparar antes de» ya pasó y la parte está en `enviada` o `preparando`. La hora de ahora sale de la cabecera `Date` de la última respuesta, nunca del reloj del teléfono solo (MATU-61 O11).
- Fecha distinta de hoy: «Preparar antes del `{DD/MM/AAAA}`, `{HH:MM}`», con dos `cifras`.
- El número del grupo va entre paréntesis: «Por preparar (2)».

### 5.5 Al día sin recargar

- La lista se vuelve a pedir **cada 60 segundos** mientras la pestaña está visible, al volver a ella (`visibilitychange`) y al tocar «Actualizar» (`Boton variante="texto"`, `textoOcupado` «Actualizando…»).
- «Actualizado a las `{HH:MM}`.» cambia con cada respuesta. **No se anuncia**: cambiaría cada minuto.
- **Llegó una parte nueva** a «Por preparar»: se anuncia una vez por las regiones vivas, `status`: «Llegó un pedido nuevo: `{ref}`.» **[NUEVO]**. Con varias: «Llegaron `{n}` pedidos nuevos.» **[NUEVO]**.
- **Una parte que se ve en el detalle cambia a `cancelada`:** se anuncia `alert`: «El pedido `{ref}` se canceló. No lo prepares.» y el detalle muestra 6.8.
- **Nunca** se mueve el foco ni el desplazamiento por una actualización automática.

### 5.6 Rótulo del piloto, privacidad y pie

- **Privacidad**, bajo el `h1`: `p` con `flex gap-2 max-w-prose text-base text-tenue` y el ícono `ShieldCheck` en `text-turquesa`. Texto: «Aquí ves solo los productos. MATU no te muestra de quién es el pedido ni a dónde va.» [A45]
- **Rótulo del piloto**, al pie de la cola (una vez por pantalla, lejos del botón principal, como «Precios de ejemplo», [L 11]): `Nota tono="atenta"` con el ícono `Info` en `text-atenta`, título «Comercio de prueba.» y texto «Estos pedidos son inventados.» [A45]. Va solo si el comercio es `ficticio`.
- **Pie** (O2): «¿Algo no calza? Avisa a MATU: `{contacto}`.» **[NUEVO]** en `text-base text-tenue`.

### 5.7 Estados de la pantalla

| Estado | Qué se ve |
|---|---|
| **Cargando** | Nada durante el primer segundo (`useDemora`). Después, «Cargando los pedidos…» en `text-tenue` con `aria-busy` en la cola. Sin esqueletos |
| **Vacío** (ninguna parte en `enviada`, `preparando` ni `lista`) | En lugar de los tres primeros grupos: «No hay pedidos por preparar.» [A45] en `text-xl font-bold` y «Cuando llegue uno, aparece aquí.» **[NUEVO]** en `text-tenue`. Retirados y cancelados de hoy siguen debajo si los hay |
| **Error al traer** | `Nota tono="pronto" rol="alert"`: «No pudimos traer los pedidos. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]**, con `Boton variante="secundario"` «Volver a intentar» [L 26]. Si ya había una lista, se queda a la vista y la nota va arriba de ella |
| **Entrada vencida (401)** | A `/comercio/entrar` con el aviso de entrada vencida (4.3) |
| **Cuenta inactiva (403)** | La pantalla entera es la `Nota tono="atenta"` de 4.3, sin pestañas, con «Salir» en la barra |

---

## 6. Un pedido (`/comercio/pedido`)

**Objetivo:** que quien atiende prepare la parte sin dudar: qué productos, cuántos, y qué hacer si uno no está.

**Jerarquía:** 1) qué pedido es, en qué estado está y para cuándo · 2) los productos con sus cantidades · 3) la única acción que sigue.

### 6.1 Esquema a 360 px (estado `preparando`)

```
┌────────────────────────────────────┐
│ (barra, distintivo y pestañas, 3)  │
├────────────────────────────────────┤
│ ‹ Volver a los pedidos             │  Volver (solo bajo 48 rem de main)
│ Pedido K4M7XP                      │  h1 titular text-3xl, ref en digitos
│ [◐ Preparando]                     │  Etiqueta tono neutro
│ Preparar antes de las 16:30        │  text-base, cifras
│ Llegó a las 14:24 · 3 productos    │  text-base text-tenue
│                                    │
│ Productos                          │  h2 text-xl font-bold
│ Marca si tienes cada uno.          │  text-base text-tenue
│ ┌────────────────────────────────┐ │  fieldset (6.4), bg-hoja ring-1 ring-linea
│ │ 2 × Pañal adulto M x30         │ │  legend font-bold, cantidad en cifras
│ │ Paquete de 30 unidades         │ │  text-tenue
│ │ (•) Lo tengo  ( ) No lo tengo  │ │  GrupoOpciones forma chips
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ 3 × Suplemento vainilla x12    │ │
│ │ Caja de 12 unidades            │ │
│ │ ( ) Lo tengo  (•) No lo tengo  │ │
│ │ ┃ No lo cambies por otra marca │ │  Nota atenta borde, dentro de la línea
│ │ ┃ ni por otro producto. MATU se│ │
│ │ ┃ encarga del resto.           │ │
│ │ ¿Cuántos te faltan?            │ │  Stepper, min 1 max 3
│ │ [−]  3  [+]                    │ │
│ │ El pedido lleva 3.             │ │  ayuda del Stepper
│ └────────────────────────────────┘ │
│ ┌ 1 × Toallitas húmedas x80 ─────┐ │
│ │ ( ) Lo tengo  ( ) No lo tengo  │ │  sin marcar
│ └────────────────────────────────┘ │
│ Después de marcarlo listo ya no    │  text-base text-tenue
│ puedes cambiar lo que marcaste.    │
│ [ Listo para retirar ]             │  único turquesa macizo
│                                    │
│ ⓘ Comercio de prueba. Estos        │  Nota atenta, al pie
│   pedidos son inventados.          │
└────────────────────────────────────┘
```

### 6.2 Pantalla ancha

La cola de 5 a la izquierda (19 rem, con la fila elegida marcada) y el detalle a la derecha, dentro de `bg-hoja ring-1 ring-linea rounded-xl px-4 @3xl:px-8 py-5` con `@container`. Sin `Volver`. El rótulo del piloto queda al pie de la cola y no se repite en el detalle. Las líneas siguen una debajo de otra (no en tabla): con las opciones y el `Stepper`, una tabla no cabe en 600 px de detalle, y una sola columna se lee igual en el teléfono y en el escritorio.

En el detalle ancho, la cabecera va en una fila con `flex flex-wrap items-start justify-between gap-x-6 gap-y-3`: a la izquierda el `h1` y la `Etiqueta`, a la derecha «Preparar antes de las 16:30» en `text-lg font-bold` y «Llegó a las 14:24 · 3 productos» debajo.

### 6.3 Lo que cambia según el estado

| Estado | Etiqueta | Productos | Acción principal | Nota |
|---|---|---|---|---|
| `enviada` | «Por preparar», tono `atenta`, `Circle` | Solo lectura (6.5) | «Empezar a preparar» [A45] · «Empezando…» **[NUEVO]** | — |
| `preparando` | «Preparando», tono `neutro`, `Contrast` | Por marcar (6.4) | «Listo para retirar» [A45] · «Guardando…» [L 5.4]. Con todas en «No lo tengo», O3 | — |
| `lista` | «Listo para retirar», tono `ok`, `PackageCheck` | Solo lectura con lo marcado (6.5) | «Revisar código» (7) | 6.6, una vez, al llegar a este estado |
| `retirada` | «Retirado», tono `neutro`, `CircleCheck` | Solo lectura | Ninguna | 6.7 |
| `cancelada` | «Cancelado», tono `neutro`, `Ban` | Solo lectura, sin marcas | Ninguna | 6.8 |

Una sola acción principal por estado. La `Etiqueta` lleva siempre ícono y palabra.

### 6.4 La línea por marcar (`preparando`)

- Cada línea es un `fieldset` con `flex flex-col gap-3 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea`. En el detalle ancho, que ya es `bg-hoja`, la línea va sin fondo y con `divide-y divide-linea` entre líneas, en vez de anillo.
- **`legend`:** «`{cantidad}` × `{producto}`» en `font-bold` (la cantidad en `cifras`, con el `×` pegado). **Debajo**, `{presentacion}` en `text-tenue`. **[AJUSTE]** del «`{cantidad}` × `{producto}` `{presentación}`» pedido: en el catálogo, `nombre` ya dice el envase («Pañal adulto M x30») y `presentacion` lo explica («Paquete de 30 unidades»). En una sola línea se repite y no cabe a 360 px.
- **Opciones:** `GrupoOpciones forma="chips"` con dos opciones de radio, `nombre` único por línea y la `legend` como nombre del grupo: «Lo tengo» (`preparada`) y «No lo tengo» (`faltante`) [A45]. Sin opción elegida al principio. Los chips son la figura de opción única (punto redondo), con `rocio` y anillo `turquesa` al elegir (`DISENO.md` 6).
- **Al elegir «No lo tengo»**, aparecen dentro de la línea, en este orden:
  1. `Nota tono="atenta" borde` con el ícono `TriangleAlert`: «No lo cambies por otra marca ni por otro producto. MATU se encarga del resto.» [A45]. Va en la línea porque es el momento en que se piensa en reemplazar. El grupo de opciones la lleva en `aria-describedby`.
  2. Solo si `{cantidad}` es mayor que 1: `Stepper` con la etiqueta «¿Cuántos te faltan?» **[AJUSTE]** de «¿Cuántas te faltan?»: la cantidad cuenta envases (paquetes, cajas), no unidades sueltas, y «cuántas» con «x30» al lado hace pensar en pañales. `min` 1, `max` `{cantidad}`, valor inicial `{cantidad}` (faltan todos) y la ayuda «El pedido lleva `{cantidad}`.» **[NUEVO]**.
- **Al elegir «Lo tengo»** después de «No lo tengo», la nota y el `Stepper` desaparecen.
- **Se guarda al elegir**, con interfaz optimista: es reversible hasta «Listo para retirar» y no mueve dinero (O4). Mientras guarda, el grupo lleva `aria-busy`. El `Stepper` guarda 800 ms después del último toque. Si falla, la opción vuelve a la anterior y bajo la línea aparece `MensajeError`: «No pudimos guardar lo que marcaste. Vuelve a intentarlo.» **[NUEVO]**.
- **Bajo las líneas**, antes del botón: «Después de marcarlo listo ya no puedes cambiar lo que marcaste.» **[NUEVO]** en `text-base text-tenue`.

**«Listo para retirar» con líneas sin marcar:** no envía. Sobre el botón, `MensajeError`: «Marca cada producto: si lo tienes o no.» **[NUEVO]**, y el foco va a la primera opción de la primera línea sin marcar. Esa línea lleva `ring-2 ring-pronto` hasta que se marca. El botón **nunca** está deshabilitado.

### 6.5 Las líneas en solo lectura

`ul` con `divide-y divide-linea border-y border-linea`, cada `li` con `flex flex-col gap-1 py-3`: la `legend` de 6.4 como texto y, desde `lista`, una `Etiqueta` con lo marcado:
- «Lo tengo», tono `ok`, `Check`;
- «No lo tengo», tono `neutro`, `PackageX`, y si faltan menos que la cantidad: «Faltan `{n}` de `{cantidad}`» **[NUEVO]**.

En `enviada` no hay etiqueta, y bajo la lista: «Toca «Empezar a preparar» cuando vayas a buscar los productos.» **[NUEVO]** en `text-tenue`.

### 6.6 Listo para retirar

Al responder `comercio_listo`, en el lugar de la acción, `Nota tono="ok" rol="status"`, título «Pedido listo para retirar.» **[NUEVO]** (el verbo del botón) y texto «MATU le avisa a quien viene a buscarlo.» **[NUEVO]**. Debajo aparece la sección del código (7). El foco va a esa nota (`enfocable`). Al volver a abrir una parte ya `lista`, la nota no se repite: se ve solo la sección del código.

### 6.7 Retirado

`Nota tono="ok"`, sin rol al abrir: título «Pedido retirado.» **[NUEVO]** y, si el contrato trae la hora, «Se retiró a las `{HH:MM}`.» **[NUEVO]**. Sin acciones.

### 6.8 Cancelado

`Nota tono="pronto" borde`, sin rol al abrir y con `rol="alert"` si se canceló mientras se veía (5.5): título «Este pedido se canceló. No lo prepares.» [A45] y texto «Si ya sacaste productos, vuelve a dejarlos en su lugar.» **[NUEVO]**. Las líneas siguen a la vista, sin etiquetas, para saber qué devolver al estante. Con O3 (todo faltaba), el título es el mismo y el texto: «Avisaste que no tienes ninguno de estos productos. MATU se encarga del resto.» **[NUEVO]**.

### 6.9 Errores del pedido

| Situación | Qué se ve |
|---|---|
| 409 o 412 al empezar, marcar o terminar (otra persona del comercio lo cambió, o se canceló) | Se vuelve a pedir la parte. `Nota tono="atenta" rol="status"` arriba de los productos: «Este pedido cambió mientras lo veías. Te mostramos cómo quedó.» **[NUEVO]**, con el patrón de [L 31]. Si quedó `cancelada`, se ve 6.8 en vez de esta nota |
| 404 (la parte ya no es de este comercio) | `Nota tono="atenta"`: «Este pedido ya no está en tu lista.» **[NUEVO]** y `Boton variante="secundario"` «Volver a los pedidos» |
| Red o 5xx | `MensajeError` sobre el botón: «No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.» [L 8], sin «Lo que escribiste sigue aquí.» porque no escribió nada. El botón no cambia |

---

## 7. Revisar el código de retiro (estado `lista`)

**Objetivo:** que quien atiende entregue el pedido solo a quien trae el código correcto, sin pensar dos veces.

**Jerarquía:** 1) qué hacer: pedir el código · 2) el campo · 3) «Revisar código» y el resultado.

### 7.1 Esquema a 360 px

```
│ Código de retiro                   │  h2 text-xl font-bold
│ Pide el código de retiro a quien   │  text-base max-w-prose
│ viene a buscar el pedido y         │
│ escríbelo aquí.                    │
│ Código de retiro (6 números)       │  label font-bold
│ ┌──────────────────┐               │
│ │   4 8 2 1 7 3    │               │  input digitos text-3xl, max-w-72, centrado
│ └──────────────────┘               │
│ [ Revisar código ]                 │  único turquesa macizo
│ ┌────────────────────────────────┐ │  resultado (7.3), recibe el foco
│ │ ✓ Código correcto. Entrega el  │ │
│ │   pedido K4M7XP.               │ │
│ │   • 2 × Pañal adulto M x30     │ │
│ │   • 1 × Toallitas húmedas x80  │ │
│ └────────────────────────────────┘ │
```

En pantalla ancha es lo mismo dentro del detalle, bajo los productos, con la columna del campo en `max-w-md`.

### 7.2 El campo

- `form noValidate` con `label` «Código de retiro (6 números)» [A45] y el `input`: `type="text"`, `inputMode="numeric"`, `autoComplete="off"`, `enterKeyHint="done"`, `maxLength` 6 después de limpiar, `spellCheck={false}`. **No** `one-time-code`: el teléfono del comercio sugeriría los códigos que le llegan a él por SMS.
- **Pegar con espacios o guiones** («482 173», «482-173»): se quitan todos los caracteres que no son números y se toman los primeros 6, como el PIN (`PantallaPin.tsx`, `pegar`). Lo mismo al escribir.
- Clases del patrón del PIN: `digitos min-h-16 w-full max-w-72 rounded-xl bg-hoja text-center text-3xl angosto:text-2xl font-bold tracking-widest ring-2 ring-inset`, con `ring-borde focus-visible:ring-turquesa`, y `ring-pronto text-pronto` con `aria-invalid` después de un código que no es. Seis cifras a `text-2xl` miden unos 107 px más el relleno: caben en los 160 px de la app a 320 px con el texto al 200 %.
- `aria-describedby`: la instrucción y, si hay, el resultado.
- **El código no se guarda en ninguna parte:** se borra del campo al recibir «correcto», «bloqueado», «vencido», «ya retirado» o «cancelado», y nunca va a la URL ni a un aviso. Con «no es», queda escrito y seleccionado, para corregirlo o reemplazarlo.
- **Menos de 6 números:** no envía. `MensajeError` bajo el campo: «Escribe los 6 números del código.» **[NUEVO]**, y el foco vuelve al campo.
- Botón: «Revisar código» [A45] · «Revisando…» **[NUEVO]**. Mientras revisa, el campo es de solo lectura.

### 7.3 Los resultados

Cada resultado es una `Nota` con `titulo`, `enfocable` y `rol` (el patrón de MATU-44 3.5): se anuncia por las regiones vivas y **el foco va a la nota**, que muestra su título primero. Se monta de nuevo en cada intento (una `key` nueva) para que se anuncie aunque repita el texto.

| Resultado | `Nota` | Título | Texto | Después | Origen |
|---|---|---|---|---|---|
| Correcto | `ok`, `rol="status"` | «Código correcto. Entrega el pedido `{ref}`.» | «Entrega estos productos:» y la lista de lo que tiene («`{cantidad}` × `{producto}`», descontando lo que falta) | La parte pasa a `retirada` y se ve 6.7 bajo esta nota. Desaparecen el campo y el botón | [A45] el título · **[NUEVO]** el texto |
| No es | `pronto`, `rol="alert"` | «Ese código no es el de este pedido.» | «No entregues el pedido todavía. Te quedan `{n}` intentos.» · con 1: «Te queda 1 intento.» | El campo sigue, con lo escrito seleccionado | [A45] **[AJUSTE]**: suma «No entregues el pedido todavía.», que es lo que tiene que hacer en el mostrador, y separa título y texto |
| Bloqueado | `pronto`, `rol="alert"` | «El código se bloqueó por demasiados intentos.» | «No entregues el pedido. Avisa a MATU: `{contacto}`.» | Desaparecen el campo y el botón | [A45] **[AJUSTE]**: suma «No entregues el pedido.» |
| Vencido | `atenta`, `rol="alert"` | «Este código venció.» | «No entregues el pedido todavía. Avisa a MATU para que le den un código nuevo a quien viene a buscarlo: `{contacto}`.» | Desaparecen el campo y el botón hasta que operación genere otro (se ve al actualizar, 5.5) | [A45] **[AJUSTE]**: dice qué pasa después y a quién llega el código nuevo |
| Ya retirado | `atenta`, `rol="alert"` | «Este pedido ya se retiró.» | «No lo entregues de nuevo.» | Se ve 6.7 | [A45] **[AJUSTE]**: suma la instrucción |
| Cancelado | `pronto`, `rol="alert"` | «Este pedido se canceló. No lo prepares.» | «No lo entregues. Si ya lo preparaste, vuelve a dejar los productos en su lugar.» | Se ve 6.8 | [A45] **[AJUSTE]**: en el mostrador, el pedido ya está preparado |
| Demasiados intentos de la cuenta (429) | `atenta`, `rol="status"` | «Hubo muchos intentos con códigos en poco tiempo.» | «Espera `{minutos}` minutos y vuelve a intentarlo.» | El botón queda con `aria-disabled` hasta que pase el tiempo, sin cuenta regresiva (el 429 de Entrar) | **[NUEVO]** |
| Red o 5xx | `pronto`, `rol="alert"` | «No pudimos revisar el código.» | «Revisa tu conexión y vuelve a intentarlo. No entregues el pedido hasta ver «Código correcto».» | El campo sigue con lo escrito | **[NUEVO]** con [L 8] |

- **Al abrir una parte `lista`** cuyo código ya está `bloqueado`, `vencido` o `usado`, se ve directamente la nota de ese resultado, sin `rol` y sin mover el foco, en lugar del campo. Con `sin_codigo`: `Nota tono="atenta"`: «Todavía no hay un código para este pedido. Avisa a MATU: `{contacto}`.» **[NUEVO]**.
- «No es» en `pronto` y no en `atenta`: un código que no es puede ser otra persona, y el mensaje dice **no entregues**. «Vencido» y «ya retirado» van en `atenta` porque nadie se equivocó.
- El número de intentos va en negrita (`b font-bold`), como en el PIN.

---

## 8. Tus productos (`/comercio/productos`)

**Objetivo:** que quien atiende diga cuántos tiene de cada producto y si lo ofrece en MATU, sin tocar el precio.

**Jerarquía:** 1) cada producto con cuántos tiene · 2) lo apartado y lo disponible · 3) cambiar cuántos tiene o dejar de ofrecerlo.

### 8.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Tus productos                      │  h1 titular text-3xl
│ Aquí dices cuántos tienes y si los │  text-base text-tenue max-w-prose
│ ofreces en MATU. El precio lo      │
│ cambia MATU.                       │
│ ┌────────────────────────────────┐ │  li bg-hoja ring-1 ring-linea rounded-xl
│ │ Pañal adulto M x30             │ │  h2 text-lg font-bold
│ │ Paquete de 30 unidades         │ │  text-tenue
│ │ $12.990 · Precio de ejemplo    │ │  cifras + text-tenue
│ │ Tienes          14             │ │  dl en dos columnas, cifras a la derecha
│ │ Apartados        3             │ │
│ │ Disponibles     11             │ │  font-bold
│ │ [x] Lo ofreces en MATU         │ │  casilla
│ │ [ Cambiar cuántos tienes ]     │ │  Boton secundario
│ └────────────────────────────────┘ │
│ ┌ Crema protectora 200 g ────────┐ │
│ │ …                              │ │
│ │ [ ] Lo ofreces en MATU         │ │
│ │ [– No se ofrece]               │ │  Etiqueta neutro, Ban
│ └────────────────────────────────┘ │
│ ⓘ Comercio de prueba. Estos        │  Nota atenta, al pie
│   productos y precios son de       │
│   ejemplo.                         │
└────────────────────────────────────┘
```

**Editando un producto** (uno a la vez), en el lugar de «Cambiar cuántos tienes»:

```
│ │ ¿Cuántos tienes ahora?         │ │  CampoTexto inputMode numeric, max-w-40
│ │ [ 14 ]                         │ │
│ │ Cuenta todo lo que tienes para │ │  ayuda
│ │ vender, también lo apartado que│ │
│ │ todavía no preparas.           │ │
│ │ [ Guardar ]  Cancelar          │ │  principal + Boton texto
```

### 8.2 Pantalla ancha

Una lista de una columna de `max-w-3xl`, alineada a la izquierda, cada producto en una fila con `@xl:grid @xl:grid-cols-[minmax(0,1fr)_auto] @xl:gap-x-8`: a la izquierda el nombre, la presentación, el precio y la casilla; a la derecha el `dl` de las tres cifras y el botón. Sin tabla: con el editor dentro de la fila, una tabla no refluye a 320 px.

### 8.3 Componentes y reglas

- **Cifras:** `dl` con `grid grid-cols-[minmax(0,1fr)_auto] gap-x-4`, cada `dt` en `text-tenue` y cada `dd` en `cifras text-right`. «Disponibles» va en `font-bold`. Con «Disponibles» en 0: «0» y al lado la `Etiqueta tono="atenta"` con `TriangleAlert` «Sin disponibles» **[NUEVO]**.
- **«Lo ofreces en MATU»** es una casilla nativa (`DISENO.md` 6, `size-6 accent-turquesa` en una etiqueta `min-h-12`). Se guarda al tocarla, con `aria-busy` en la casilla mientras guarda. Sin marcar, bajo la casilla: `Etiqueta tono="neutro"` con `Ban` «No se ofrece» **[NUEVO]** y, si hay apartados, «Lo apartado sigue apartado.» **[NUEVO]** en `text-tenue`.
- **El precio** se lee, no se edita: en `cifras` y, si el comercio es `ficticio`, seguido de «· Precio de ejemplo» [L 11] en `text-tenue`. Sin campo, sin lápiz y sin botón.
- **«Cambiar cuántos tienes»** (`Boton variante="secundario"`) abre el editor en la misma fila y el foco va al campo. Mientras uno está abierto, los botones «Cambiar cuántos tienes» de las demás filas se ocultan: así hay **un solo** «Guardar», que es la acción principal de la pantalla en ese momento. Sin un editor abierto, la pantalla no tiene botón principal.
- **«Guardar»** · «Guardando…» [L 5.4]. **«Cancelar»** (`Boton variante="texto"`) cierra sin guardar y devuelve el foco a «Cambiar cuántos tienes» de esa fila.
- **Hecho:** el editor se cierra, las cifras cambian y se anuncia `status`: «Guardado: tienes `{n}` de `{producto}`.» **[NUEVO]**. El foco vuelve a «Cambiar cuántos tienes».
- **Menos de los apartados:** se guarda (es lo que hay), y bajo las cifras aparece `Nota tono="atenta"`: «Tienes menos de los que ya están apartados para pedidos. Al preparar, marca «No lo tengo» en lo que falte.» **[NUEVO]**.

### 8.4 Errores y estados

| Situación | Qué se ve | Origen |
|---|---|---|
| Campo vacío, con letras o negativo | `MensajeError` del campo: «Escribe un número, desde 0.» | **[NUEVO]** |
| Más de 9.999 | «Escribe un número hasta 9.999.» | **[NUEVO]** |
| 412 (otra persona del comercio lo cambió) | Se vuelve a pedir el producto. `Nota tono="atenta" rol="status"` en la fila: «Otra persona cambió este producto mientras lo editabas. Te mostramos cómo quedó.» El editor sigue abierto con lo que escribiste | **[NUEVO]**, con el patrón de [L 6.2] |
| Red o 5xx | `MensajeError` sobre «Guardar»: [L 8] completo, con «Lo que escribiste sigue aquí.» | [L 8] |
| Cargando | Como 5.7: «Cargando tus productos…» después de un segundo | **[NUEVO]** |
| Vacío | «Todavía no tienes productos en MATU.» en `text-xl font-bold` y «Avisa a MATU para agregarlos: `{contacto}`.» | **[NUEVO]** |
| Error al traer | `Nota tono="pronto" rol="alert"`: «No pudimos traer tus productos. Revisa tu conexión y vuelve a intentarlo.» y «Volver a intentar» | **[NUEVO]** |

- **Rótulo del piloto**, al pie y una vez: `Nota tono="atenta"` con `Info`, título «Comercio de prueba.» y texto «Estos productos y precios son de ejemplo.» **[AJUSTE]** de [A45]: en esta pantalla no hay pedidos, y lo que puede confundirse con real son los precios.
- Orden: por `nombre`, después `presentacion`. Nunca por precio ni por disponibles.

---

## 9. Lo que las pantallas necesitan del contrato

El backend escribe el contrato en paralelo en esta rama. Esta tabla usa nombres de las decisiones D-63; si el contrato nombra distinto, manda el contrato y la pantalla no cambia.

| Dato | Dónde se usa |
|---|---|
| Tipo de cuenta en la respuesta de la sesión (O1), y el 403 de cuenta o comercio inactivo | 4.3 y 5.7 |
| `nombre_fantasia` y `ficticio` del comercio de la cuenta | La barra (3), los rótulos del piloto y «Precio de ejemplo» |
| Lista de partes de hoy: `parte_id`, `referencia`, `estado`, `enviado_en`, `preparar_antes_de`, `estado_codigo`, el número de líneas y, en `retirada`, la hora del retiro | 5 |
| La parte con sus líneas: `linea_id`, `producto.nombre`, `producto.presentacion`, `cantidad`, `estado_linea`, `unidades_faltantes`, y un `ETag` | 6 |
| `comercio_preparar`, `comercio_marcar_linea` (repetible, O4), `comercio_listo` | 6.3 y 6.4 |
| `comercio_validar_codigo` con el código **en el cuerpo**: el resultado (`correcto`, `no_es`, `bloqueado`, `vencido`, `usado`, `cancelada`) y los intentos que quedan | 7.3 |
| `429` con `Retry-After` en la validación del código | 7.3 |
| Productos del comercio: `oferta_id`, nombre, presentación, `precio`, `stock`, `apartado`, `disponible` (booleano) y `ETag`; cambiar `stock` y `disponible` con `If-Match` | 8 |
| El contacto de operación del piloto (O2) | 4, 5.6, 7.3 y 8.4 |
| La cabecera `Date` de cada respuesta | «Atrasada» (5.4) |

**Lo que las pantallas no usan y no deben recibir:** el `pedido_id`, el grupo, la persona cuidada, quién creó el pedido, la referencia corta de la familia, la dirección, el teléfono, montos, precios del pedido, devoluciones, transiciones, el código de retiro ni su hash (D-63-1).

---

## 10. Accesibilidad visual

- **Texto:** nada bajo `text-base` (17 px), sin `text-sm` ni `text-xs` (MATU-93). Lo secundario va en `tenue`, nunca más chico.
- **Contraste:** todo par sale de `DISENO.md` 1 (medidos). Los nuevos de esta pantalla, medidos el 13/11: `papel` sobre `tinta` 14,1:1 (claro) y 15,4:1 (oscuro); `papel` al 85 % sobre `tinta` 10,5:1 y 10,3:1; el foco `papel` sobre `tinta` igual que el texto. Los que **no** se usan en la barra: `turquesa` sobre `tinta` (2,4:1 y 1,6:1), `miel` sobre `tinta` oscura (1,5:1) y `marca` sobre `tinta` oscura (2,9:1).
- **Áreas táctiles:** toda fila, chip, opción, casilla con su etiqueta, botón, «Salir», «Actualizar», pestaña y botón del `Stepper` mide `min-h-12` (51 px) o `size-12`.
- **Foco:** el contorno base de 3 px en `turquesa` con 2 px de separación, y en `papel` dentro de la barra. Al llegar a cada ruta, el foco va al `h1`. Después de una acción, a la nota del resultado (6.6, 7.3) o al primer control que falta (6.4, 7.2).
- **Estado nunca solo por color:** cada grupo y cada `Etiqueta` llevan ícono y palabra. La fila elegida cambia de anillo y suma un ícono. La línea sin marcar lleva el anillo `pronto` **y** el `MensajeError` con palabras.
- **Reflujo:** sin desplazamiento horizontal a 320 px con el texto al 200 %. Toda grilla declara `grid-cols-1` en el ancho chico. Los chips y las acciones van en `flex-wrap`. El `Stepper` mide 3 × 48 px más los espacios. La barra se parte en renglones.
- **Movimiento:** ninguno propio. Las notas aparecen con `aparecer` (180 ms), que `prefers-reduced-motion` vuelve inmediato. Las páginas cambian sin deslizarse.
- **Regiones vivas:** se anuncia lo que pasa por una acción o por la llegada de un pedido (5.5, 6.6, 7.3, 8.3), nunca la hora de actualización.

---

## 11. Criterios visuales verificables

1. **Una sola acción principal por estado.** En cada estado de 6.3 y en `/comercio/productos` con un editor abierto, hay a lo sumo **un** elemento con `bg-turquesa`. En `/comercio` y en `/comercio/productos` sin editor, ninguno.
2. Ninguna pantalla de `/comercio` muestra un nombre de persona, una dirección, un teléfono de familia, un monto del pedido ni el código de retiro. Un `grep` de los textos de `web/src/comercio/` no encuentra «María», «Carmen», «dirección», «Total» ni «Pagado».
3. Ninguna ruta de `/comercio` lleva un id ni la referencia en la URL. Recargar `/comercio/pedido` lleva a `/comercio`.
4. El campo del código tiene `inputMode="numeric"`, `autoComplete="off"`, y al pegar «482 173» queda «482173».
5. Cada resultado de 7.3 se anuncia una vez por las regiones vivas y recibe el foco. Después de «correcto», el campo ya no existe en el DOM.
6. El texto «No entregues» aparece en los resultados «no es», «bloqueado», «vencido», «cancelado» y en el de red.
7. Con «No lo tengo» elegido, la nota «No lo cambies por otra marca ni por otro producto. MATU se encarga del resto.» está a la vista dentro de esa línea y en el `aria-describedby` de su grupo. Con «Lo tengo», no está.
8. «¿Cuántos te faltan?» aparece solo en líneas con cantidad mayor que 1, y su `Stepper` no baja de 1 ni pasa de la cantidad.
9. «Listo para retirar» con una línea sin marcar no envía: muestra «Marca cada producto: si lo tienes o no.» y el foco queda en la primera opción de esa línea. El botón nunca tiene `disabled`.
10. Cada grupo de la cola tiene un `h2` con ícono, palabra y número. Ningún grupo vacío se muestra.
11. La fila elegida tiene `aria-current="true"` y un anillo de 2 px más el ícono `ChevronRight`.
12. La barra es `bg-tinta text-papel`; su contorno de foco es `papel`. «Salir» no usa `turquesa`.
13. `DistintivoPiloto` está a la vista en las cuatro rutas, también en `/comercio/entrar`, a 360 px, a 1920 px y con el texto al 200 %. Nunca dentro de la barra `tinta`.
14. «(comercio ficticio)» aparece una sola vez por pantalla, en la barra, y solo si el comercio es `ficticio`.
15. El rótulo «Comercio de prueba.» aparece una vez por pantalla y nunca en el mismo grupo de `Acciones` que un botón principal.
16. Ningún texto de `/comercio` mide menos de 17 px. La prueba `textoMinimo17.test.ts`, que ya lee todo `web/src`, pasa con `web/src/comercio/`.
17. A 320 px con el texto al 200 %, ninguna de las cuatro rutas tiene desplazamiento horizontal (`scrollWidth` igual a `clientWidth` en `html`), en los cinco estados del pedido y con el editor de productos abierto.
18. A 1280 px y a 1920 px, `/comercio/pedido` muestra la cola de 19 rem y el detalle a la derecha. Bajo 48 rem de `main`, solo el detalle con «Volver a los pedidos».
19. El precio de `/comercio/productos` no tiene campo, botón ni ícono de edición.
20. Ninguna pantalla dice «stock», «reserva», «sesión», «inválido» ni un código de error.
21. Las seis cifras del código caben en el campo a 320 px con el texto al 200 % (`text-2xl` en `angosto`).
22. En el tema oscuro, la barra sigue en `tinta` con texto `papel` (invertida) y todos los pares de 10 se cumplen.
23. Ningún color, tamaño ni sombra escrito a mano en `web/src/comercio/`: todo sale de los tokens y de las clases de esta especificación.

---

## 12. Textos nuevos para `lenguaje.md`

Todos los **[NUEVO]** y **[AJUSTE]** de este documento entran a `lenguaje.md` en una sección nueva, «Comercio (MATU-63)», en el PR de documentos de MATU-63, y Jorge los aprueba antes de construir. Los ajustes a [A45], con su porqué:

| [A45] | Queda | Por qué |
|---|---|---|
| Cabecera «`{nombre}` · Pedidos de hoy» | La barra dice «`{nombre}` (comercio ficticio)» y el `h1`, «Pedidos de hoy». El `<title>` es «Pedidos de hoy · `{nombre}` · MATU» | Juntos en un renglón no caben a 360 px con «(comercio ficticio)», que es obligatorio [L 11]. Se leen juntos igual |
| «`{cantidad}` × `{producto}` `{presentación}`» | «`{cantidad}` × `{producto}`» y la presentación debajo, en `tenue` | El `nombre` ya dice el envase, y en un renglón se repite y no cabe |
| «¿Cuántas te faltan?» | «¿Cuántos te faltan?» | La cantidad es de envases, no de unidades |
| «Ese código no es el de este pedido. Te quedan `{n}` intentos.» | Título igual, y «No entregues el pedido todavía. Te quedan `{n}` intentos.» («Te queda 1 intento.») | Dice qué hacer en el mostrador, y el singular |
| «El código se bloqueó por demasiados intentos. Avisa a MATU.» | Suma «No entregues el pedido.» y el contacto | Lo mismo, y «Avisa a MATU» necesita a quién (O2) |
| «Este código venció. Avisa a MATU.» | «Este código venció.» · «No entregues el pedido todavía. Avisa a MATU para que le den un código nuevo a quien viene a buscarlo: `{contacto}`.» | Dice qué pasa después y que el código nuevo no le llega al comercio (D-63-5) |
| «Este pedido ya se retiró.» | Suma «No lo entregues de nuevo.» | Instrucción |
| «Este pedido se canceló. No lo prepares.» al revisar el código | Suma «No lo entregues. Si ya lo preparaste, vuelve a dejar los productos en su lugar.» | En el mostrador, el pedido ya está preparado |
| «Comercio de prueba. Estos pedidos son inventados.» en «Tus productos» | «Comercio de prueba. Estos productos y precios son de ejemplo.» | En esa pantalla no hay pedidos |

---

## 13. Cambios en `Demo/DISENO.md`

Dos frases, sin tokens nuevos (hechos en este mismo commit):
- **Sección 2, `digitos`:** suma «la referencia del pedido en la consola del comercio», que se dicta letra a letra en el mostrador (la demo ya la usaba así).
- **Sección 3, «El comercio»:** una nota que apunta a esta especificación para `web/`, y la regla del foco dentro de la barra `tinta`: contorno `papel` (14,1:1 y 15,4:1), no `miel`, que en el tema oscuro mide 1,5:1 contra `tinta`.
