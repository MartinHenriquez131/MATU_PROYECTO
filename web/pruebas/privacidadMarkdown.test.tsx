// MATU-75 (especificación 1.7 y 1.8): el texto de la política se convierte en elementos de React con
// un lector propio, sin HTML crudo. Un `<script>` o cualquier etiqueta del texto se muestra como texto.
// Solo datos sintéticos.
import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Documento } from '../src/privacidad/Documento'
import { leerMarkdown } from '../src/privacidad/markdown'

const dibujar = (texto: string) => render(<Documento secciones={leerMarkdown(texto)} alVolver={vi.fn()} />)

describe('El renderizador de la política', () => {
  it('un <script> del texto se muestra como texto y no se crea ningún elemento', () => {
    const { container } = dibujar('## En un minuto\n\nAntes <script>alert("x")</script> y <b>esto</b> <img src=x onerror=alert(1)> después.\n')

    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('Antes <script>alert("x")</script> y <b>esto</b> <img src=x onerror=alert(1)> después.')).toBeInTheDocument()
  })

  it('no usa dangerouslySetInnerHTML ni innerHTML en ninguna parte de la página', () => {
    const carpeta = resolve(__dirname, '../src/privacidad')
    for (const archivo of readdirSync(carpeta)) {
      const fuente = readFileSync(resolve(carpeta, archivo), 'utf8')
      expect(fuente, archivo).not.toMatch(/dangerouslySetInnerHTML\s*=|\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML/)
    }
  })

  it('títulos con anclas legibles, párrafos, listas, negritas, cursivas, citas y código', () => {
    const { container } = dibujar(
      [
        '## En un minuto',
        '',
        '- Uno **importante**.',
        '- Dos con *cursiva*.',
        '',
        '---',
        '',
        '## 5. La autorización',
        '',
        '### Aviso',
        '',
        '1. Primero.',
        '2. Segundo.',
        '',
        '> **Lo que declaras**',
        '>',
        '> Un segundo párrafo.',
        '',
        'La huella es `0123456789abcdef`.',
      ].join('\n'),
    )

    expect(screen.getByRole('heading', { level: 2, name: 'En un minuto' })).toHaveAttribute('id', 'en-un-minuto')
    expect(screen.getByRole('heading', { level: 2, name: '5. La autorización' })).toHaveAttribute('id', 'seccion-5')
    expect(screen.getByRole('heading', { level: 3, name: 'Aviso' })).toHaveAttribute('id', 'seccion-5-aviso')
    // Cada sección es una región con su título.
    expect(screen.getByRole('region', { name: '5. La autorización' })).toBeInTheDocument()
    expect(screen.getByText('importante').tagName).toBe('STRONG')
    expect(screen.getByText('cursiva').tagName).toBe('EM')
    expect(container.querySelector('ol li')?.textContent).toBe('Primero.')
    expect(container.querySelector('blockquote strong')?.textContent).toBe('Lo que declaras')
    expect(container.querySelectorAll('blockquote p')).toHaveLength(2)
    expect(screen.getByText('0123456789abcdef').tagName).toBe('CODE')
    expect(container.querySelectorAll('hr')).toHaveLength(1)
  })

  it('cada sección termina con «Volver al índice», y la columna mide max-w-xl (unos 72 caracteres)', () => {
    const { container } = dibujar('## En un minuto\n\nUno.\n\n## 1. Otra\n\nDos.\n')
    expect(container.querySelector('article')).toHaveClass('max-w-xl')
    expect(screen.getAllByRole('link', { name: 'Volver al índice' })).toHaveLength(2)
  })

  it('las tablas llevan sus roles y, apiladas, el encabezado sobre cada dato', () => {
    dibujar('## 8. Plazos\n\n| Dato | Plazo |\n|---|---|\n| Ficha | 90 días |\n| Registro | 3 años |\n')

    const tabla = screen.getByRole('table')
    expect(within(tabla).getAllByRole('columnheader').map((c) => c.textContent)).toEqual(['Dato', 'Plazo'])
    const filas = within(tabla).getAllByRole('row')
    expect(filas).toHaveLength(3)
    // La celda dice qué dato es aunque la tabla esté apilada.
    expect(within(filas[1]).getAllByRole('cell').map((c) => c.textContent)).toEqual(['DatoFicha', 'Plazo90 días'])
    // Apilada, cada par de encabezado y dato se separa del siguiente (v0.2, 1.8).
    expect(within(filas[1]).getAllByRole('cell')[1]).toHaveClass('not-first:mt-2', '@xl/main:mt-0')
  })

  it('un enlace mailto: es enlace; uno a otro sitio va en otra pestaña; uno javascript: queda solo como texto', () => {
    dibujar('## 10. Derechos\n\nEscribe a [privacidad@example.org](mailto:privacidad@example.org), lee [la ley](https://example.org/ley) o [esto](javascript:alert(1)).\n')

    expect(screen.getByRole('link', { name: 'privacidad@example.org' })).toHaveAttribute('href', 'mailto:privacidad@example.org')
    const externo = screen.getByRole('link', { name: 'la ley (se abre en otra pestaña)' })
    expect(externo).toHaveAttribute('target', '_blank')
    expect(externo).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.queryByRole('link', { name: 'esto' })).not.toBeInTheDocument()
    expect(screen.getByText(/esto\./)).toBeInTheDocument()
  })

  it('el texto no se reemplaza: lo que llega es lo que se ve', () => {
    dibujar('## 2. Contacto\n\nTodavía no lo definimos. {correo_privacidad} [PENDIENTE: algo]\n')
    expect(screen.getByText('Todavía no lo definimos. {correo_privacidad} [PENDIENTE: algo]')).toBeInTheDocument()
  })
})
