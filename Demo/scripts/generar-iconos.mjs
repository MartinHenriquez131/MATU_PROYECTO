// Genera los íconos PNG del manifiesto sin dependencias: dibuja el logo de MATU
// (techo y corazón) con funciones de distancia y lo codifica con zlib.
// Uso: node scripts/generar-iconos.mjs
import { deflateSync } from 'node:zlib'
import { writeFileSync } from 'node:fs'

const PINO = [14, 94, 87]
const PAPEL = [238, 243, 240]
const MIEL = [227, 164, 58]

function distSegmento(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy))
}
function enTriangulo(px, py, [ax, ay], [bx, by], [cx, cy]) {
  const s = (ax - cx) * (py - cy) - (ay - cy) * (px - cx)
  const t = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
  if ((s < 0) !== (t < 0) && s !== 0 && t !== 0) return false
  const d = (cx - bx) * (py - by) - (cy - by) * (px - bx)
  return d === 0 || (d < 0) === (s + t <= 0)
}
// Color en coordenadas del lienzo de 48 x 48. null = transparente.
function muestra(x, y, maskable) {
  const radio = maskable ? 0 : 14
  const dentro =
    maskable ||
    (() => {
      const qx = Math.max(radio - x, 0, x - (48 - radio))
      const qy = Math.max(radio - y, 0, y - (48 - radio))
      return Math.hypot(qx, qy) <= radio
    })()
  if (!dentro) return null
  // En el ícono maskable el dibujo se achica hacia la zona segura.
  const k = maskable ? 0.72 : 1
  const u = 24 + (x - 24) / k, v = 24 + (y - 24) / k
  const techo = Math.min(distSegmento(u, v, 11, 23.5, 24, 12), distSegmento(u, v, 24, 12, 37, 23.5))
  if (techo <= 1.7) return PAPEL
  const corazon =
    Math.hypot(u - 19.75, v - 25.3) <= 4.45 ||
    Math.hypot(u - 28.25, v - 25.3) <= 4.45 ||
    enTriangulo(u, v, [15.3, 25.3], [32.7, 25.3], [24, 35.4])
  if (corazon) return MIEL
  return PINO
}

function crc32(buf) {
  let c, crc = 0xffffffff
  for (let n = 0; n < buf.length; n++) {
    c = (crc ^ buf[n]) & 0xff
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    crc = (crc >>> 8) ^ c
  }
  return (crc ^ 0xffffffff) >>> 0
}
function bloque(tipo, datos) {
  const largo = Buffer.alloc(4); largo.writeUInt32BE(datos.length)
  const cuerpo = Buffer.concat([Buffer.from(tipo, 'ascii'), datos])
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(cuerpo))
  return Buffer.concat([largo, cuerpo, crc])
}
function png(tam, maskable) {
  const SS = 4
  const filas = []
  for (let py = 0; py < tam; py++) {
    const fila = Buffer.alloc(1 + tam * 4)
    for (let px = 0; px < tam; px++) {
      let r = 0, g = 0, b = 0, a = 0
      for (let sy = 0; sy < SS; sy++) for (let sx = 0; sx < SS; sx++) {
        const c = muestra(((px + (sx + 0.5) / SS) / tam) * 48, ((py + (sy + 0.5) / SS) / tam) * 48, maskable)
        if (c) { r += c[0]; g += c[1]; b += c[2]; a += 1 }
      }
      const o = 1 + px * 4
      if (a) { fila[o] = r / a; fila[o + 1] = g / a; fila[o + 2] = b / a }
      fila[o + 3] = Math.round((a / (SS * SS)) * 255)
    }
    filas.push(fila)
  }
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(tam, 0); ihdr.writeUInt32BE(tam, 4)
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    bloque('IHDR', ihdr),
    bloque('IDAT', deflateSync(Buffer.concat(filas))),
    bloque('IEND', Buffer.alloc(0)),
  ])
}

writeFileSync('public/icono-192.png', png(192, false))
writeFileSync('public/icono-512.png', png(512, false))
writeFileSync('public/icono-maskable-512.png', png(512, true))
writeFileSync('public/icono-180.png', png(180, true))
console.log('Íconos generados en public/')
