// Doble de `GET /v1/politica` (MATU-75, decisiones 173 a 177). Pública: no mira cookies ni el token.
// El texto es el de la política 0.11 que sirve la API (backend/…/politica-0.11.md, si está a mano)
// más una sección de ejemplo que no es de la política: una tabla, una huella en `code`, un enlace
// `mailto:` y un texto con una etiqueta, para la revisión visual. Solo datos sintéticos.
//
// MATU_DOBLE_POLITICA cambia lo que responde, al arrancar `npm run dev`:
//   no-publicada  GET /v1/politica y POST /v1/usuarios responden 503 (decisión 174)
//   sin-correo    correo_contacto es null: «Tu cuenta» no muestra cómo pedir
//   lenta         la política tarda 2 s: se ve «Cargando…»
import { createHash, randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { ServerResponse } from 'node:http'

export const MODO_POLITICA = process.env.MATU_DOBLE_POLITICA ?? ''

const VERSION = '0.11'
const ACTUALIZADA_EN = '2026-11-09'
const CORREO = 'cuidaconmatu@gmail.com'

const RESPALDO = `## En un minuto

- MATU te ayuda a organizar el cuidado de una persona mayor.
- **Hoy MATU es un piloto académico y no guarda datos reales.** Si lo pruebas, usa nombres y datos inventados.

---

## 1. Esto es un borrador del piloto académico

- El doble no encontró el texto de la API: este es un resumen corto.
`

const EJEMPLO = `
## 15. Ejemplo para la revisión visual (solo en el doble)

Esta sección no es de la política: la agrega el doble para revisar cómo se ven una tabla, una huella en \`code\`, un enlace de correo y un texto con una etiqueta.

| Dato | Cuánto tiempo | Quién lo ve |
|---|---|---|
| Ficha de relevo | 90 días después de retirar la autorización | Tu grupo y el relevo que elijas |
| Registro de aperturas | 3 años | Tu grupo |
| La política que aceptaste | Mientras exista tu cuenta | Tú, en «Tu cuenta» |

Una huella se ve así: \`2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae\`. Un aviso, así: \`aviso_cuidador_de_hecho\`.

> **Una cita con negrita**
>
> Y un segundo párrafo dentro de la cita, con *cursiva*.

Escríbenos a [${CORREO}](mailto:${CORREO}). Un enlace a otro sitio se abre en otra pestaña: [la Biblioteca del Congreso Nacional](https://www.bcn.cl/leychile).

Este texto trae una etiqueta que se tiene que ver tal cual, sin ejecutarse: <script>alert("no")</script> y <b>sin negrita</b>.
`

function textoDeLaApi(): string {
  try {
    return readFileSync(resolve(process.cwd(), '../backend/app/modules/iam/politica/politica-0.11.md'), 'utf8').replace(/\r\n?/g, '\n')
  } catch {
    return RESPALDO
  }
}

const TEXTO = `${textoDeLaApi().trimEnd()}\n${EJEMPLO}`
/** SHA-256 del texto exacto que se sirve, en UTF-8 con saltos LF (decisión 173). */
export const HUELLA = createHash('sha256').update(TEXTO, 'utf8').digest('hex')

export const politicaPublicada = () => MODO_POLITICA !== 'no-publicada'

/** La aceptación que guarda el alta: la versión y la huella vigentes, nunca las del cliente. */
export const aceptacionVigente = (aceptadaEn: string) => ({ version: VERSION, huella: HUELLA, aceptada_en: aceptadaEn })

/** `GET /v1/politica`. `true` si la ruta era suya. */
export async function atenderPolitica(metodo: string, ruta: string, res: ServerResponse): Promise<boolean> {
  if (ruta !== '/v1/politica' || metodo !== 'GET') return false
  if (MODO_POLITICA === 'lenta') await new Promise((r) => setTimeout(r, 2000))
  res.setHeader('X-Request-ID', randomUUID())
  if (!politicaPublicada()) {
    res.statusCode = 503
    res.setHeader('Cache-Control', 'no-store')
    res.setHeader('Content-Type', 'application/problem+json')
    res.end(JSON.stringify({ type: '/errores/servicio-no-disponible', title: 'TITLE DEL DOBLE: NO SE MUESTRA', status: 503, detail: 'DETAIL DEL DOBLE: NO SE MUESTRA', errores: [], request_id: randomUUID() }))
    return true
  }
  res.statusCode = 200
  // Decisión 175: el navegador la puede guardar, pero la revalida cada vez.
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Content-Type', 'application/json')
  res.end(
    JSON.stringify({
      version: VERSION,
      actualizada_en: ACTUALIZADA_EN,
      huella: HUELLA,
      texto: TEXTO,
      correo_contacto: MODO_POLITICA === 'sin-correo' ? null : CORREO,
    }),
  )
  return true
}
