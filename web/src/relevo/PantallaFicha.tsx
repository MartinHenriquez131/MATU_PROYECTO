// La ficha abierta (3.11): la hoja y, al lado o arriba, hasta cuándo se puede ver y «Actualizar».
// Ningún elemento en turquesa macizo: la hoja es lo principal y «Actualizar» es secundario.
import { useState } from 'react'
import { Clock3, RefreshCw } from 'lucide-react'
import type { FichaRelevo } from '../compartido/api/relevo'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { Boton } from '../compartido/ui/Boton'
import { CAMPOS, ERROR, FICHA, MOSTRAR_EJEMPLO, ORDEN_CAMPOS } from './textos'
import { TextoCampo } from './TextoCampo'

/** `ok` = llegó la ficha nueva · `error` = red o 5xx, la hoja sigue · `salio` = otro momento. */
export type ResultadoActualizar = 'ok' | 'error' | 'salio'

export function PantallaFicha({ ficha, onActualizar }: { ficha: FichaRelevo; onActualizar: () => Promise<ResultadoActualizar> }) {
  const [actualizando, setActualizando] = useState(false)
  const [aviso, setAviso] = useState<{ vez: number; tipo: 'ok'; hora: string } | { vez: number; tipo: 'error' } | null>(null)
  const vence = fechaYHoraDeChile(new Date(ficha.vence_en))

  const actualizar = async () => {
    setActualizando(true)
    const r = await onActualizar()
    if (r === 'salio') return
    setActualizando(false)
    const vez = (aviso?.vez ?? 0) + 1
    setAviso(r === 'ok' ? { vez, tipo: 'ok', hora: fechaYHoraDeChile(new Date()).hora } : { vez, tipo: 'error' })
  }

  return (
    <div className="mx-auto grid max-w-6xl grid-cols-1 items-start gap-8 @4xl/main:grid-cols-[minmax(0,1fr)_17rem]">
      <div className="mx-auto w-full max-w-3xl">
        <Hoja ficha={ficha} />
      </div>
      <aside aria-label={FICHA.columna} className="order-first flex flex-col gap-4 @4xl/main:order-none @4xl/main:sticky @4xl/main:top-6">
        <p className="flex items-start gap-2 text-base">
          <Clock3 aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
          <span>
            {FICHA.vigenciaInicio} <b className="cifras font-bold">{vence.fecha}</b> {FICHA.vigenciaMedio} <b className="cifras font-bold">{vence.hora}</b>.
          </span>
        </p>
        <Boton
          variante="secundario"
          className="self-start"
          icono={<RefreshCw aria-hidden className="size-5 shrink-0" />}
          ocupado={actualizando}
          textoOcupado={FICHA.actualizando}
          onClick={actualizar}
        >
          {FICHA.actualizar}
        </Boton>
        {aviso?.tipo === 'ok' && (
          <p key={aviso.vez} role="status" className="animate-aparecer text-base text-tenue">
            {FICHA.actualizada(aviso.hora)}
          </p>
        )}
        {aviso?.tipo === 'error' && (
          <p key={aviso.vez} role="alert" className="text-base">
            <b className="font-bold">{ERROR.titulo}</b> {ERROR.conexion}
          </p>
        )}
        <p className="text-base text-tenue">{FICHA.soloPuede(ficha.nombre_pila_comparte)}</p>
      </aside>
    </div>
  )
}

/** La hoja del refrigerador con su imán de miel: la única superficie con sombra de la página. */
function Hoja({ ficha }: { ficha: FichaRelevo }) {
  const pila = ficha.nombre_pila
  return (
    <div className="relative pt-3">
      <span aria-hidden className="absolute top-0 left-1/2 z-10 size-7 -translate-x-1/2 rounded-full bg-miel shadow-md" />
      <div className="rounded-sm bg-hoja px-4 angosto:px-2 @3xl/main:px-9 pt-7 pb-6 shadow-xl ring-1 ring-linea/60">
        <div className="border-b-2 border-tinta pb-3">
          <p className="text-lg text-tenue">{FICHA.encabezado}</p>
          <h1 id="titulo-pagina" tabIndex={-1} className="titular text-5xl @2xl/main:text-6xl angosto:text-3xl leading-none outline-none">
            {pila}
          </h1>
        </div>
        {/* Solo los campos que vienen en `campos`. Uno que no viene no deja rastro. */}
        {ORDEN_CAMPOS.filter((c) => ficha.campos[c] !== undefined).map((c) => {
          const def = CAMPOS[c]
          return (
            <section key={c} aria-labelledby={`campo-${c}`} aria-describedby={MOSTRAR_EJEMPLO ? `ejemplo-${c}` : undefined} className="mt-6">
              <h2 id={`campo-${c}`} className="text-xl font-bold text-turquesa">
                {def.etiqueta}
              </h2>
              <p className="mt-1 text-base text-tenue">{def.pregunta(pila)}</p>
              <div className="mt-3">
                <TextoCampo texto={ficha.campos[c]?.texto ?? null} />
              </div>
              {MOSTRAR_EJEMPLO && (
                <p id={`ejemplo-${c}`} className="mt-3 border-s-2 border-linea ps-3 text-base text-tenue">
                  {def.ejemplo}
                </p>
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}
