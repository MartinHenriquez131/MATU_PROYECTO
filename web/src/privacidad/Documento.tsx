// El texto de la política como elementos de React (especificación MATU-75, 1.6 a 1.8). Todo llega
// como hijos de texto: React los escapa, así que nada del texto se interpreta como HTML. Sin
// `dangerouslySetInnerHTML`.
import { Fragment, type MouseEvent, type ReactNode } from 'react'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { POLITICA } from '../compartido/textosPolitica'
import type { Bloque, Linea, Seccion } from './markdown'

function EnLinea({ partes }: { partes: Linea[] }) {
  return (
    <>
      {partes.map((p, i) => {
        switch (p.tipo) {
          case 'texto':
            return <Fragment key={i}>{p.texto}</Fragment>
          case 'negrita':
            return (
              <strong key={i} className="font-bold">
                <EnLinea partes={p.hijos} />
              </strong>
            )
          case 'cursiva':
            return (
              <em key={i} className="italic">
                <EnLinea partes={p.hijos} />
              </em>
            )
          case 'codigo':
            // Sin achicarlo, y partible: la huella de 64 caracteres cabe a 320 px con el texto al 200 %.
            return (
              <code key={i} className="font-mono text-base [overflow-wrap:anywhere]">
                {p.texto}
              </code>
            )
          case 'enlace':
            return p.destino === 'externo' ? (
              <EnlaceEnFrase key={i} href={p.href} otraPestana>
                <EnLinea partes={p.hijos} /> {POLITICA.otraPestana}
              </EnlaceEnFrase>
            ) : (
              <EnlaceEnFrase key={i} href={p.href} className={p.destino === 'correo' ? '[overflow-wrap:anywhere]' : ''}>
                <EnLinea partes={p.hijos} />
              </EnlaceEnFrase>
            )
        }
      })}
    </>
  )
}

/** Bajo `@xl/main` cada fila es un bloque, con el encabezado sobre cada dato (1.8). */
function Tabla({ encabezados, filas }: { encabezados: Linea[][]; filas: Linea[][][] }) {
  return (
    <table role="table" className="mt-4 block w-full border-collapse text-start @xl/main:table">
      <thead role="rowgroup" className="hidden @xl/main:table-header-group">
        <tr role="row">
          {encabezados.map((h, i) => (
            <th key={i} role="columnheader" scope="col" className="border-b-2 border-borde py-2 pe-4 text-start align-bottom font-bold">
              <EnLinea partes={h} />
            </th>
          ))}
        </tr>
      </thead>
      <tbody role="rowgroup" className="block @xl/main:table-row-group">
        {filas.map((fila, f) => (
          <tr key={f} role="row" className="block border-b border-linea py-3 @xl/main:table-row @xl/main:py-0">
            {fila.map((celda, c) => (
              <td key={c} role="cell" className="block leading-relaxed not-first:mt-2 @xl/main:mt-0 @xl/main:table-cell @xl/main:border-b @xl/main:border-linea @xl/main:py-3 @xl/main:pe-4 @xl/main:align-top">
                <span className="block font-bold @xl/main:hidden">
                  <EnLinea partes={encabezados[c]} />
                </span>
                <EnLinea partes={celda} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** `margen`: nada al principio, `mt-3` después de un título y entre los párrafos de una cita, `mt-4` en lo demás. */
function BloqueDoc({ b, margen }: { b: Bloque; margen: string }) {
  switch (b.tipo) {
    case 'titulo':
      return b.nivel === 2 ? (
        <h2 id={b.id} className={`text-xl font-bold leading-snug scroll-mt-6 ${margen}`}>
          <EnLinea partes={b.hijos} />
        </h2>
      ) : (
        <h3 id={b.id} className="mt-8 text-lg font-bold leading-snug scroll-mt-6">
          <EnLinea partes={b.hijos} />
        </h3>
      )
    case 'parrafo':
      return (
        <p className={`${margen} text-base leading-relaxed text-tinta`}>
          <EnLinea partes={b.hijos} />
        </p>
      )
    case 'lista': {
      const clase = `${margen} flex flex-col gap-2 ps-6 angosto:ps-4 leading-relaxed marker:text-tenue`
      const items = b.items.map((it, i) => (
        <li key={i}>
          <EnLinea partes={it} />
        </li>
      ))
      return b.ordenada ? (
        <ol start={b.inicio === 1 ? undefined : b.inicio} className={`${clase} list-decimal`}>
          {items}
        </ol>
      ) : (
        <ul className={`${clase} list-disc`}>{items}</ul>
      )
    }
    case 'cita':
      return (
        <blockquote className={`${margen} rounded-xl border-l-4 border-turquesa bg-rocio px-4 angosto:px-2 py-3 leading-relaxed`}>
          <Bloques bloques={b.bloques} enCita />
        </blockquote>
      )
    case 'separador':
      return <hr className="my-10 border-t border-linea" />
    case 'tabla':
      return <Tabla encabezados={b.encabezados} filas={b.filas} />
    case 'bloqueCodigo':
      return <pre className={`${margen} font-mono text-base whitespace-pre-wrap [overflow-wrap:anywhere]`}>{b.texto}</pre>
  }
}

function Bloques({ bloques, enCita = false }: { bloques: Bloque[]; enCita?: boolean }) {
  return (
    <>
      {bloques.map((b, i) => {
        const anterior = bloques[i - 1]
        const margen = i === 0 ? '' : enCita ? 'mt-3' : anterior.tipo === 'titulo' ? 'mt-3' : 'mt-4'
        return <BloqueDoc key={i} b={b} margen={margen} />
      })}
    </>
  )
}

/** «Volver al índice» (J2), solo bajo `@4xl/main`: en pantalla ancha el índice ya está a la vista. */
function VolverAlIndice({ alVolver }: { alVolver: () => void }) {
  return (
    <p className="mt-4 @4xl/main:hidden">
      <a
        href="#indice"
        onClick={(e: MouseEvent) => {
          e.preventDefault()
          alVolver()
        }}
        className="inline-flex min-h-12 items-center gap-1 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa"
      >
        {POLITICA.volverAlIndice}
      </a>
    </p>
  )
}

/**
 * El documento, una `section` por título de primer nivel, cada una cerrada con «Volver al índice».
 * Sin `alVolver` (las condiciones del pedido, MATU-61 9.8: diez secciones cortas) va sin índice.
 */
export function Documento({ secciones, alVolver }: { secciones: Seccion[]; alVolver?: () => void }) {
  return (
    <article className="min-w-0 max-w-xl">
      {secciones.map((s, i) => {
        // Un `---` al final de la sección va después de «Volver al índice», que es de la sección.
        const final = s.bloques[s.bloques.length - 1]
        const conSeparador = final?.tipo === 'separador'
        const bloques: Bloque[] = s.titulo ? [s.titulo, ...s.bloques] : s.bloques
        const contenido: ReactNode = (
          <>
            <Bloques bloques={conSeparador ? bloques.slice(0, -1) : bloques} />
            {s.titulo && alVolver && <VolverAlIndice alVolver={alVolver} />}
            {conSeparador && <hr className="my-10 border-t border-linea" />}
          </>
        )
        const margen = i === 0 || secciones[i - 1].bloques[secciones[i - 1].bloques.length - 1]?.tipo === 'separador' ? '' : 'mt-12'
        return s.titulo ? (
          <section key={s.titulo.id} aria-labelledby={s.titulo.id} className={margen}>
            {contenido}
          </section>
        ) : (
          <div key={`sin-titulo-${i}`}>
            {contenido}
          </div>
        )
      })}
    </article>
  )
}
