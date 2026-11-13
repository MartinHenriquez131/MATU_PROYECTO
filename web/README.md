# MATU · cliente web

Aplicación web mobile first de MATU (ADR-026): React 19, TypeScript, Vite, Tailwind CSS v4, iconos de `lucide-react` y Axios. Tiene dos partes: la app de la familia (MATU-39, `docs/diseno/matu-39-app-familia.md`), en `/`, y la página del relevo, `/r#<token>` (MATU-23, `docs/diseno/matu-23-pagina-relevo.md`).

## Cómo correrlo

Requiere Node 20.19 o más nuevo (Vite 8), y Node 22.12 o más nuevo para las pruebas.

```bash
cd web
npm install
npm run dev        # http://localhost:5173 con el doble del contrato (sin backend)
npm run build      # tsc --noEmit + vite build → web/dist (ignorado en git)
npm run preview    # sirve web/dist, también con el doble
```

Contra la API real (uvicorn en `127.0.0.1:8000`), sin el doble:

```bash
npm run dev:api        # /v1 va por proxy a la API local
npm run preview:api
```

`npm run typecheck` revisa los tipos. `npm run contrato` regenera `src/compartido/api/relevo.openapi.ts` desde `docs/api/propuestos/relevo.openapi.yaml`.

## Pruebas de interfaz

Vitest + Testing Library sobre jsdom (estrategia de pruebas v1.2, fila «Interfaz web»). Requieren Node 22.12 o más nuevo, como Vitest 5. Corren en cada push, en el trabajo `web` del CI, después de los tipos.

```bash
cd web
npm test                       # vitest run: todas, una vez
npx vitest                     # se quedan mirando los cambios
npx vitest run pruebas/entrar  # solo los archivos que calzan
```

Viven en `pruebas/`, fuera de `src/`: `vite build` solo empaqueta lo que importa `index.html`, así que nunca entran a `web/dist`, y `tsc` las revisa igual que el resto. La configuración está en `vitest.config.ts` y los matchers de jest-dom se cargan en `pruebas/preparacion.ts`. `pruebas/apiFalsa.ts` reemplaza el adaptador de Axios para que la pantalla pase por su cliente real sin red, y `pruebas/familiaFalsa.ts` da el contexto de la familia sin `ProveedorFamilia`. `pruebas/regiones.tsx` monta las regiones vivas antes de la pantalla, como `main.tsx`.

Qué revisan: la semántica y el foco de los componentes críticos, los errores de campo con `aria-describedby` y `aria-invalid`, los avisos anunciados en las regiones vivas (`role="status"` y `role="alert"`, en `src/compartido/ui/Anuncios.tsx`) y los textos de `docs/lenguaje.md`, escritos tal cual en la prueba. Cada corrección de pantalla deja una prueba que falla sin ella (definición de terminado, punto 6). Solo datos sintéticos: correos `@example.com` y el celular de ejemplo de `lenguaje.md`.

## El doble del contrato (solo desarrollo)

Mientras no existe el backend de MATU-19, `doble/servidor.ts` es un middleware de Vite que responde `POST /v1/relevo/presentacion`, `POST /v1/relevo/canje` y `GET /v1/relevo/ficha` por HTTP, con la cookie HttpOnly, los códigos, el cuerpo RFC 7807 y las cabeceras del contrato. Se activa en `npm run dev` y en `npm run preview`, y se apaga con `--mode api`. Vive fuera de `src/` y **no entra al build**: `web/dist` solo trae la aplicación.

En `http://localhost:5173/ejemplos` (solo en desarrollo) están las cuentas de ejemplo de la familia y un enlace de ejemplo del relevo por estado. El PIN correcto es **4821**. Los tokens están en `doble/escenarios.ts`:

| Token (`/r#…`) | Qué muestra |
|---|---|
| `ejemplo-tres-campos` | Ficha con los tres campos (horas, corrido, sin completar). Cada PIN malo descuenta un intento; el quinto bloquea |
| `ejemplo-un-campo` | Ficha con un solo campo |
| `ejemplo-telefonos` | Teléfonos dentro del texto (especificación 3.11.4): junto a una hora, sin separadores, con guion entre el prefijo y el resto («+56-9-5555-0177»), en la línea de tiempo y en una sección con paréntesis, y un monto y una fecha que no se reconocen |
| `ejemplo-quedan-3` / `ejemplo-quedan-1` | PIN incorrecto con 3 y con 1 intento |
| `ejemplo-bloqueado`, `ejemplo-vencido`, `ejemplo-cortado`, `ejemplo-no-disponible`, `ejemplo-pausado` | Estados en que el enlace no abre |
| `ejemplo-espera-60`, `ejemplo-espera-600`, `ejemplo-espera-sin-cabecera`, `ejemplo-espera-canje` | 429 con `Retry-After` 60, 600, sin cabecera y en el canje |
| `ejemplo-error-500`, `ejemplo-error-una-vez`, `ejemplo-error-canje`, `ejemplo-error-ficha` | Errores 5xx en la presentación, el canje y la ficha |
| `ejemplo-sesion-cerrada`, `ejemplo-cortado-despues`, `ejemplo-bloqueado-despues`, `ejemplo-pausado-despues`, `ejemplo-actualizar-falla` | La ficha abre y «Actualizar» responde 401, 410, 423, 410 pausado o 503 |
| `ejemplo-vence-pronto` | La ficha vence 90 s después de abrirla y la página la vuelve a pedir sola |
| `ejemplo-lento` | Cada respuesta tarda 2 s (textos de carga) |
| `ejemplo-textos-largos` | Nombres largos y campos de 500 caracteres |
| `/r` sin fragmento | Sin cookie: «Vuelve a abrir el enlace» |
| Un fragmento de más de 128 caracteres | 422: «Este enlace no está disponible» |

Los intentos y las sesiones del doble viven en memoria: se reinicia `npm run dev` para volver a cero.

## El doble de la app de la familia (MATU-39)

`doble/familia.ts` responde `POST /v1/usuarios`, `POST /v1/sesiones`, `…/renovar` (con la cookie HttpOnly `matu-refresh-doble`, que rota), `…/cerrar`, `GET` y `POST /v1/grupos`, las personas del grupo y la ficha con `ETag`, 412, 428 y 422. La contraseña de todas las cuentas de ejemplo es `contrasena-ejemplo`; la lista con qué muestra cada una está en `/ejemplos`. Las cuentas nuevas se crean con cualquier correo y empiezan sin grupo (primera visita). En «Crear cuenta», `espera-ip@example.com`, `espera-ip-60@example.com` y `espera-ip-sin-cabecera@example.com` provocan el 429 del límite por IP (`Retry-After` 61, 60 y sin cabecera), y un correo `@dominio-no-permitido.internal` el 422 `dominio_no_permitido` de staging; están también en `/ejemplos`. Los correos de los dobles son de dominios reservados (`@example.com`, decisión 105); el del 422 usa `.internal`, que no está entre los que staging acepta y que ICANN reservó en 2024 para redes privadas: nunca existirá en internet. Todo vive en memoria: reinicia `npm run dev` para volver a cero.

La entrada en el cliente (`src/compartido/api/sesion.ts`): el access token solo en memoria, renovación con la cookie al abrir y ante un 401, serializada entre pestañas con `navigator.locks` y avisada con `BroadcastChannel('matu-entrada')` sin el token.

Compartir y cortar (MATU-48): `POST` y `GET …/plan/accesos-relevo` y `DELETE /v1/accesos-relevo/{id}`, con un enlace con token y PIN al azar, el teléfono solo para admin y cuidador, y una cuenta por estado (`enlaces-…` y `compartir-…` en `/ejemplos`).

La política de privacidad (MATU-75): `doble/politica.ts` responde `GET /v1/politica` sin mirar cookies, con el texto 0.11 que sirve la API (`backend/app/modules/iam/politica/politica-0.11.md`, si está a mano) más una sección 15 de ejemplo que no es de la política: una tabla, una huella en `code`, un enlace `mailto:`, uno a otro sitio y un `<script>` que se tiene que ver como texto. La huella es el SHA-256 de ese texto. El alta exige `acepta_politica: true` y compara la huella; `politica-cambio@example.com` responde 409 `politica-cambio` la primera vez y crea la cuenta la segunda. `GET /v1/cuenta` trae `politica_aceptada`: las cuentas de ejemplo la aceptaron el 09/11/2026, y `politica-sin-registro@example.com` y `sin-celular@example.com` no tienen registro. `MATU_DOBLE_POLITICA` cambia la respuesta al arrancar: `no-publicada` (503 en la política y en el alta), `sin-correo` (`correo_contacto` en `null`) o `lenta` (2 s). Por ejemplo, `MATU_DOBLE_POLITICA=no-publicada npm run dev`.

El pedido (MATU-61): `doble/pedido.ts` responde la autorización `despacho` (con `huella_declaracion` y su retiro, que cancela lo no pagado y conserva la dirección), `PUT` y `DELETE …/direccion` con `If-Match` o `If-None-Match: *`, `GET …/pedido-en-curso`, crear el borrador con `Idempotency-Key`, `PUT …/lineas` y `…/reglas-faltante` con `If-Match`, `confirmar` (15 minutos, un envío de $3.990, lo que salió y lo que cambió), `…/contacto`, `…/cambiar`, `…/cancelar` y `GET /v1/condiciones-pedido`, pública. Con la cuenta `catalogo-apagado@example.com` las rutas del pedido no existen (capa 3 apagada). Las cuentas `pedido-…@example.com` muestran cada estado y rol; están en `/ejemplos`, y `pedido-plazo@example.com` deja ver el aviso de los 2 minutos a los 10 segundos.

El pago (MATU-62): `doble/pedido.ts` responde `POST …/pagar` (con `Idempotency-Key`, `If-Match` y las condiciones), `GET …/pago`, `GET …/pedido-pagado`, `POST /v1/pagos/retorno` (pública, sin 401) y el 409 `pago-en-curso` en las rutas que cambian el pedido. «Pagar» envía el formulario a `/__doble/webpay`, una página falsa de Webpay (no es Transbank) donde se elige qué pasa: débito, crédito en 3 cuotas, prepago, no aprobado, anular compra (vuelve con `TBK_*` en el fragmento), tiempo agotado, pendiente durante 25 s, tardío respetado, anulado (hecho o en curso), sin sesión y un token desconocido. Volver con «Atrás» sin elegir deja el pago en curso. Las cuentas `pago-…@example.com` muestran cada estado y rol, también pedidos ya pagados, con devoluciones y por otra persona; están en `/ejemplos`. Se ve con `npm run dev`: el build lleva `form-action` solo para Webpay, así que `npm run preview` no puede enviar el formulario al doble.

Invitar y quiénes forman el grupo (MATU-42 y MATU-53): `doble/grupo.ts` responde `GET …/miembros`, `PATCH …/miembros/{id}` (con `If-Match`, 428, 412 con `actual` y 409 `ultimo-admin`), `DELETE …/miembros/{id}` y `POST …/salida` (200 con `enlaces_cortados`, 409 `ultimo-admin` y `unica-persona`), `GET`, `POST` y `DELETE …/invitaciones` (con el 429 `tope-invitaciones` y el 409 `invitacion-cerrada`) y las tres rutas de la persona invitada: `POST /v1/invitaciones/presentacion` y `…/verificacion` sin sesión, y `…/aceptacion` con sesión (une a la cuenta en un grupo nuevo del doble). Las cuentas `miembros-…@example.com` muestran cada rol y estado, y `miembros-autor-salio@example.com` al autor que ya no está y el aviso de la autorización. Las invitaciones de ejemplo se abren en `/invitacion#inv-…`, con el código **4729**; una invitación creada con «Invitar a alguien» abre de verdad su enlace, con el código que muestra «Invitación lista». Todo está en `/ejemplos`.

La consola del comercio (MATU-63): `doble/comercio.ts` responde `GET /v1/comercio`, `…/partes`, `…/partes/{id}` (con `ETag`), `POST …/preparar`, `PUT …/lineas/{id}` y `POST …/listo` (con `If-Match` opcional, 409 `estado-parte`, 412 y 422 `lineas-pendientes`; con todo faltante, la parte queda cancelada), `POST …/validar-codigo` (el código solo en el cuerpo, cinco intentos, 429 con `Retry-After` y 503) y `GET` y `PATCH /v1/comercio/productos` (con `If-Match` y 412). La sesión dice `tipo_cuenta`. Las cuentas `comercio-…@example.com` y los códigos de retiro de ejemplo están en `/ejemplos`; se entra por `/comercio/entrar`.

`npm run contrato:familia` regenera `src/compartido/api/familia.openapi.ts` desde `docs/api/openapi.json`.

## El aviso de versión nueva (MATU-67)

`npm run build` deja `dist/version.json`, `{"version": "…"}`, con un identificador de 16 caracteres: el hash de los nombres de los archivos del build, que ya traen el hash de su contenido. El mismo identificador va dentro del bundle (`__MATU_VERSION__`), así que volver a construir el mismo código da el mismo identificador y no muestra el aviso. No lleva datos de nadie. La API lo sirve con `Cache-Control: no-store` (decisión 172).

La app de la familia y el relevo piden `/version.json` con `cache: 'no-store'` al volver a la pestaña y cada 15 minutos mientras está visible (`src/compartido/version.ts`). Si el identificador es otro, aparece el aviso (`src/compartido/ui/AvisoVersion.tsx`). Si la revisión falla, no pasa nada. Nunca recarga sola, y «Más tarde» se recuerda solo en memoria.

Para verlo con el doble (`doble/version.ts`), con `npm run dev` o `npm run preview`:

1. Abre la app, por ejemplo `http://localhost:5173/ficha` o `/r#ejemplo-tres-campos`.
2. En otra pestaña, abre `http://localhost:5173/__doble/version-nueva`. Desde ahí, `/version.json` responde otra versión.
3. Vuelve a la pestaña de MATU: aparece el aviso. Con el foco en un campo de texto, aparece al salir del campo.
4. `http://localhost:5173/__doble/version-igual` vuelve a la versión que corre. «Recargar» recarga la página, y como el doble sigue respondiendo otra versión, el aviso vuelve en la próxima revisión hasta que se vuelve a la igual.

## Para servirlo desde la API

Lo hace el backend: servir `web/dist` con `StaticFiles` en el mismo origen, y responder `index.html` en `/r`, en `/privacidad` y en las rutas de la familia (`/`, `/entrar`, `/crear-cuenta`, `/empezar/*`, `/ficha*`, `/insumos`, `/compartir`, `/compartir/listo`, `/compartir/enlaces`). La especificación (D6) recomienda que esa respuesta lleve `Cache-Control: no-store`, `Referrer-Policy: no-referrer` y `X-Robots-Tag: noindex`. El HTML del build ya trae una política de contenido (`Content-Security-Policy`) sin terceros.

## Estructura

```
web/
├── doble/                 doble del contrato (solo servidor de desarrollo)
└── src/
    ├── index.css          tokens del diseñador (no se editan aquí)
    ├── compartido/
    │   ├── api/           cliente Axios, tipos generados del contrato, rutas del relevo
    │   ├── ui/            Boton, Logo, DistintivoPiloto
    │   └── fechas.ts      DD/MM/AAAA y HH:MM en la hora de Chile
    ├── familia/           la app de la familia: ruteo, estado, marco, alta, ficha, dictado
    ├── relevo/            la página /r: textos, estados, pantallas
    ├── privacidad/        la página pública /privacidad y su lector de markdown, sin HTML crudo
    └── desarrollo/        lista de ejemplos (solo en desarrollo)
```

Los textos que ve quien abre el enlace están todos en `src/relevo/textos.ts`. Los ejemplos de cada campo (decisión D2) se controlan con `MOSTRAR_EJEMPLO`, que está apagado desde el 09-11. En «A quién llamar», el teléfono de ejemplo quedaba bajo el teléfono real y, en una crisis, se podía llamar al número equivocado. El relevo ve solo la pregunta guía, y el editor de la familia sigue mostrando los ejemplos. La ruta de la política de privacidad es `RUTA_POLITICA`, `/privacidad` desde MATU-75. Los textos de la política (lenguaje.md, sección 29) están en `src/compartido/textosPolitica.ts`.
