// «Más sobre…» en la ficha (especificación MATU-49, sección 3): las secciones complementarias
// agregadas, con su texto, y las que se pueden agregar. Nunca una barra «de 6», nunca «falta»: la
// línea de lo agregado solo suma (ADR-018 y ADR-028).
import { Check, PencilLine, Plus } from 'lucide-react'
import { seccionesDe, type Ficha, type Rol } from '../compartido/api/familia'
import { Boton } from '../compartido/ui/Boton'
import { SECCIONES } from './datos'
import { puedeEditar } from './estado'
import { navegar } from './ruteo'
import { CONFLICTO, FICHA, MAS } from './textos'
import { AvisoRemedios, Cuando, TextoSeccion, type SeccionEnHoja } from './ui'

/** Las secciones agregadas, en el orden fijo, para la hoja (3.2). Una sección sin texto no existe. */
export const seccionesEnHoja = (f: Ficha | null): SeccionEnHoja[] => {
  const s = seccionesDe(f)
  return SECCIONES.flatMap((x) => {
    const e = s[x.api]
    return e?.texto?.trim() ? [{ api: x.api, texto: e.texto }] : []
  })
}

export function MasSobre({ ficha, pila, rol }: { ficha: Ficha; pila: string; rol: Rol }) {
  const s = seccionesDe(ficha)
  const agregadas = SECCIONES.filter((x) => s[x.api]?.texto?.trim())
  const porAgregar = SECCIONES.filter((x) => !s[x.api]?.texto?.trim())
  // El pagador ve los botones; un 404 al guardar lleva a «No tienes acceso» (MATU-39 3.6, D3).
  const botones = puedeEditar(rol) || rol === 'pagador'
  return (
    <section aria-labelledby="mas-sobre-t" className="mt-10 flex min-w-0 flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h2 id="mas-sobre-t" className="titular text-2xl">
          {MAS.titulo(pila)}
        </h2>
        <p className="max-w-prose text-base text-tenue">{MAS.bajada(pila)}</p>
        {agregadas.length > 0 && (
          <p key={agregadas.length} className="flex animate-aparecer items-center gap-2 text-base">
            <Check aria-hidden className="size-5 shrink-0 text-ok" />
            {MAS.agregadas(agregadas.length)}
          </p>
        )}
      </div>

      {agregadas.length > 0 && (
        <ul className="flex flex-col gap-3">
          {agregadas.map((x) => {
            const e = s[x.api]!
            return (
              <li key={x.api} className="flex flex-col gap-2 rounded border border-linea bg-hoja px-4 angosto:px-2 py-3.5">
                <h3 className="text-xl font-bold">{x.titulo}</h3>
                {x.api === 'remedios' && <AvisoRemedios />}
                <TextoSeccion texto={e.texto} recortar className="renglones text-base leading-7" />
                {e.actualizado_en && (
                  <p className="text-sm text-tenue">
                    {FICHA.loEscribio(e.actualizado_por?.nombre ?? CONFLICTO.otraPersona)} <Cuando iso={e.actualizado_en} />
                  </p>
                )}
                {botones && (
                  <Boton variante="secundario" className="self-start" icono={<PencilLine aria-hidden className="size-5" />} onClick={() => navegar(x.ruta)}>
                    {MAS.editar(x.titulo)}
                  </Boton>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {botones && porAgregar.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-lg font-bold">{MAS.puedesAgregar}</h3>
          <ul className="flex flex-col gap-2 @4xl/main:flex-row @4xl/main:flex-wrap">
            {porAgregar.map((x) => (
              <li key={x.api} className="flex">
                <Boton variante="secundario" aria-label={MAS.agregar(x.titulo)} icono={<Plus aria-hidden className="size-5" />} onClick={() => navegar(x.ruta)}>
                  {x.titulo}
                </Boton>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
