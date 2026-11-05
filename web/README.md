# MATU · cliente web

Aplicación web mobile first de MATU (ADR-026): React 19, TypeScript, Vite, Tailwind CSS v4, iconos de `lucide-react` y Axios. Tiene dos partes: la app de la familia (MATU-39, `docs/diseno/matu-39-app-familia.md`), en `/`, y la página del relevo, `/r#<token>` (MATU-23, `docs/diseno/matu-23-pagina-relevo.md`).

## Cómo correrlo

Requiere Node 20 o más nuevo.

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

## El doble del contrato (solo desarrollo)

Mientras no existe el backend de MATU-19, `doble/servidor.ts` es un middleware de Vite que responde `POST /v1/relevo/presentacion`, `POST /v1/relevo/canje` y `GET /v1/relevo/ficha` por HTTP, con la cookie HttpOnly, los códigos, el cuerpo RFC 7807 y las cabeceras del contrato. Se activa en `npm run dev` y en `npm run preview`, y se apaga con `--mode api`. Vive fuera de `src/` y **no entra al build**: `web/dist` solo trae la aplicación.

En `http://localhost:5173/ejemplos` (solo en desarrollo) están las cuentas de ejemplo de la familia y un enlace de ejemplo del relevo por estado. El PIN correcto es **4821**. Los tokens están en `doble/escenarios.ts`:

| Token (`/r#…`) | Qué muestra |
|---|---|
| `ejemplo-tres-campos` | Ficha con los tres campos (horas, corrido, sin completar). Cada PIN malo descuenta un intento; el quinto bloquea |
| `ejemplo-un-campo` | Ficha con un solo campo |
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

`doble/familia.ts` responde `POST /v1/usuarios`, `POST /v1/sesiones`, `…/renovar` (con la cookie HttpOnly `matu-refresh-doble`, que rota), `…/cerrar`, `GET` y `POST /v1/grupos`, las personas del grupo y la ficha con `ETag`, 412, 428 y 422. La contraseña de todas las cuentas de ejemplo es `contrasena-ejemplo`; la lista con qué muestra cada una está en `/ejemplos`. Las cuentas nuevas se crean con cualquier correo y empiezan sin grupo (primera visita). En «Crear cuenta», `espera-ip@ejemplo.cl`, `espera-ip-60@ejemplo.cl` y `espera-ip-sin-cabecera@ejemplo.cl` provocan el 429 del límite por IP (`Retry-After` 61, 60 y sin cabecera), y un correo `@dominio-no-permitido.cl` el 422 `dominio_no_permitido` de staging; están también en `/ejemplos`. Todo vive en memoria: reinicia `npm run dev` para volver a cero.

La entrada en el cliente (`src/compartido/api/sesion.ts`): el access token solo en memoria, renovación con la cookie al abrir y ante un 401, serializada entre pestañas con `navigator.locks` y avisada con `BroadcastChannel('matu-entrada')` sin el token.

`npm run contrato:familia` regenera `src/compartido/api/familia.openapi.ts` desde `docs/api/openapi.json`.

## Para servirlo desde la API

Lo hace el backend: servir `web/dist` con `StaticFiles` en el mismo origen, y responder `index.html` en `/r` y en las rutas de la familia (`/`, `/entrar`, `/crear-cuenta`, `/empezar/*`, `/ficha*`, `/insumos`, `/compartir`). La especificación (D6) recomienda que esa respuesta lleve `Cache-Control: no-store`, `Referrer-Policy: no-referrer` y `X-Robots-Tag: noindex`. El HTML del build ya trae una política de contenido (`Content-Security-Policy`) sin terceros.

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
    └── desarrollo/        lista de ejemplos (solo en desarrollo)
```

Los textos que ve quien abre el enlace están todos en `src/relevo/textos.ts`. Los ejemplos de cada campo (decisión D2) se apagan con `MOSTRAR_EJEMPLO`, y la ruta de la política de privacidad (D5) se fija en `RUTA_POLITICA`.
