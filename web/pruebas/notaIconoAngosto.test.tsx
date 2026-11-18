// MATU-121 (docs/diseno/matu-121-nota-icono.md): a 320 px con el texto al 200 %, la nota con el ícono
// en su columna partía palabras y fechas («01/11/202⏎6.»). Desde ahora toda `Nota` lleva el ícono en
// línea en el modo angosto, por omisión: en la línea del título si tiene, flotando al comienzo del texto
// si no. En línea mide `size-5` sin margen superior aunque la pantalla pase uno de `size-6`. Fuera de
// `angosto:` la nota es la de siempre: el ícono en su columna (`contents` no cambia el diseño).
// jsdom no mide: se afirma la estructura, con el patrón de avisosCuenta.test.tsx. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { ShieldAlert } from 'lucide-react'
import { describe, expect, it } from 'vitest'
import { Nota } from '../src/compartido/ui/Nota'

const TEXTO = 'No pudimos registrar tu pedido porque el plazo venció el 01/11/2026.'
const TITULO = 'Tienes cambios sin guardar en «Su día»'
const EN_LINEA = ['angosto:[&>svg]:size-5', 'angosto:[&>svg]:mt-0'] as const

const laNota = (texto: string) => screen.getByText(texto).closest('.flex.max-w-prose') as HTMLElement
/** El ícono de la columna: dentro de `contents`, que se oculta en angosto. */
const columna = (nota: HTMLElement) => nota.querySelector(':scope > span.contents')

describe('MATU-121: el ícono de la Nota va en línea en el modo angosto', () => {
  it('por omisión y sin título: el ícono flota al comienzo del texto y el cuerpo lo contiene', () => {
    render(<Nota tono="pronto">{TEXTO}</Nota>)
    const nota = laNota(TEXTO)
    expect(columna(nota)).toHaveClass('angosto:hidden')
    expect(columna(nota)!.querySelector('svg.lucide-circle-alert')).not.toBeNull()
    const cuerpo = nota.querySelector('.leading-relaxed') as HTMLElement
    expect(cuerpo).toHaveClass('text-base', 'angosto:flow-root')
    const flotante = cuerpo.querySelector(':scope > span:first-child') as HTMLElement
    expect(flotante).toHaveClass('hidden', 'angosto:block', 'angosto:float-start', 'angosto:me-1.5', 'angosto:mt-0.75', 'angosto:leading-none', ...EN_LINEA)
    expect(flotante).not.toHaveClass('angosto:inline-flex')
    expect(flotante.querySelector(':scope > svg.lucide-circle-alert')).toHaveAttribute('aria-hidden')
    // Dos copias del dibujo, una por modo; el texto no cambia.
    expect(nota.querySelectorAll('svg')).toHaveLength(2)
    expect(nota.textContent).toBe(TEXTO)
  })

  it.each(['rocio', 'atenta', 'pronto', 'ok'] as const)('tono %s con borde: también en línea, y la línea de 4 px se queda', (tono) => {
    render(
      <Nota tono={tono} borde>
        {TEXTO}
      </Nota>,
    )
    const nota = laNota(TEXTO)
    expect(nota).toHaveClass('border-l-4')
    expect(columna(nota)).toHaveClass('angosto:hidden')
    expect(nota.querySelector('.leading-relaxed > span.angosto\\:float-start > svg')).not.toBeNull()
  })

  it('con título: el ícono va en la línea del título (inline-flex aprobado) y el cuerpo no flota nada', () => {
    render(
      <Nota tono="atenta" titulo={TITULO}>
        {TEXTO}
      </Nota>,
    )
    const titulo = screen.getByText(TITULO)
    const enLinea = titulo.querySelector(':scope > span > svg')!.parentElement
    expect(enLinea).toHaveClass('hidden', 'angosto:me-1.5', 'angosto:inline-flex', 'angosto:align-middle', ...EN_LINEA)
    const nota = laNota(TEXTO)
    expect(columna(nota)).toHaveClass('angosto:hidden')
    const cuerpo = nota.querySelector('.leading-relaxed') as HTMLElement
    expect(cuerpo).not.toHaveClass('angosto:flow-root')
    expect(cuerpo.querySelector('span')).toBeNull()
  })

  it('con párrafos y sin título: el ícono flota antes del primer párrafo, no queda solo en su línea', () => {
    render(
      <Nota tono="ok">
        <p>Recibimos tu pedido de devolución.</p>
        <p>Te escribimos para coordinar el retiro.</p>
      </Nota>,
    )
    const cuerpo = laNota('Recibimos tu pedido de devolución.').querySelector('.leading-relaxed') as HTMLElement
    expect(cuerpo).toHaveClass('angosto:flow-root')
    expect(cuerpo.firstElementChild).toHaveClass('angosto:float-start')
    expect(cuerpo.firstElementChild!.nextElementSibling!.tagName).toBe('P')
  })

  it('un ícono de 24 px que pasa la pantalla conserva su tamaño en la columna y se achica a size-5 en línea', () => {
    render(
      <Nota tono="atenta" borde titulo={TITULO} icono={<ShieldAlert aria-hidden className="mt-0.5 size-6 shrink-0 text-atenta" />}>
        {TEXTO}
      </Nota>,
    )
    const nota = laNota(TEXTO)
    // En la columna, la clase de la pantalla sin cambios.
    expect(columna(nota)!.querySelector(':scope > svg')).toHaveClass('size-6', 'mt-0.5')
    // En línea, el envoltorio la reemplaza con `[&>svg]`, que es más específico.
    const enLinea = screen.getByText(TITULO).querySelector(':scope > span')!
    expect(enLinea).toHaveClass(...EN_LINEA)
    expect(enLinea.querySelector(':scope > svg.lucide-shield-alert')).not.toBeNull()
  })

  it('con iconoEnLinea={false}: el ícono queda en su columna, como antes, sin copia en línea', () => {
    render(
      <Nota tono="pronto" iconoEnLinea={false}>
        {TEXTO}
      </Nota>,
    )
    const nota = laNota(TEXTO)
    expect(columna(nota)).toBeNull()
    expect(nota.querySelector(':scope > svg.lucide-circle-alert')).not.toBeNull()
    expect(nota.querySelectorAll('svg')).toHaveLength(1)
    expect(nota.querySelector('.leading-relaxed')).not.toHaveClass('angosto:flow-root')
    expect(nota.querySelector('.leading-relaxed > span')).toBeNull()
  })

  it('con iconoEnLinea escrito (los 27 usos de antes) se ve igual que por omisión', () => {
    const { container: escrito } = render(
      <Nota tono="rocio" iconoEnLinea titulo={TITULO}>
        {TEXTO}
      </Nota>,
    )
    const { container: omision } = render(
      <Nota tono="rocio" titulo={TITULO}>
        {TEXTO}
      </Nota>,
    )
    expect(escrito.innerHTML).toBe(omision.innerHTML)
  })

  it('fuera de angosto todo lo nuevo lleva el prefijo: ninguna clase sin `angosto:` además de las de siempre', () => {
    render(
      <>
        <Nota tono="atenta" titulo={TITULO}>
          {TEXTO}
        </Nota>
        <Nota tono="pronto">Otra nota sin título.</Nota>
      </>,
    )
    const sinPrefijo = (e: Element) => [...e.classList].filter((c) => !c.startsWith('angosto:'))
    for (const span of [screen.getByText(TITULO).querySelector(':scope > span')!, laNota('Otra nota sin título.').querySelector('.leading-relaxed > span')!]) {
      // `hidden`: fuera de angosto la copia en línea no se ve; en la columna está el de siempre.
      expect(sinPrefijo(span)).toEqual(['hidden'])
    }
    expect(sinPrefijo(laNota('Otra nota sin título.').querySelector('.leading-relaxed')!)).toEqual(['text-base', 'leading-relaxed'])
  })
})
