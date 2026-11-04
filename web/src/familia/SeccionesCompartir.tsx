// Qué secciones ve el relevo, para el paso de compartir (especificación MATU-49, sección 6).
//
// La pantalla de compartir es de MATU-48 (Martín) y todavía no existe en `main`: aquí están solo
// las piezas, listas para integrar. Cómo se integran en la pantalla de MATU-48:
//
//   1. En lugar de los chips de «¿Qué puede ver?» de los tres campos, va <ElegirSecciones>, entre
//      «Su teléfono» y «¿Hasta cuándo?». Recibe las secciones agregadas de la ficha
//      (`seccionesAgregadas(ficha)`); los tres campos van siempre y no se eligen.
//   2. El estado sale de `useEleccionSecciones()`, que parte vacío y con Sus remedios desmarcada
//      cada vez que se monta la pantalla (6.5), aunque el acceso anterior la haya incluido.
//   3. Al tocar «Crear enlace»: si `remedios` está marcada, NO se crea todavía. Se muestra
//      <ConfirmacionRemedios> justo encima del botón, y «Crear enlace» se oculta mientras está
//      abierta. Solo «Sí, crear el enlace» hace el POST. «No incluir sus remedios» desmarca la
//      casilla, cierra el bloque y devuelve el foco a la casilla (`idCasillaRemedios`).
//   4. Si cambia el nombre o el plazo con la confirmación abierta, se cierra (6.3).
//   5. El cuerpo del POST lleva `secciones_adicionales: eleccion.paraEnviar` y no lleva `campos`
//      (deprecado en docs/api/openapi.json). Un 422 `seccion_no_agregada` significa que otra
//      persona quitó una sección mientras tanto: hay que volver a leer la ficha.
//   6. En la pantalla del PIN y en «Enlaces»: `COMPARTIR_SECCIONES.loQueVe(titulos)` y, bajo el
//      PIN, `COMPARTIR_SECCIONES.despues(nombre)` (6.4).
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Check, Info } from 'lucide-react'
import { seccionesDe, type Ficha } from '../compartido/api/familia'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { ORDEN_SECCIONES, TITULO_SECCION, type SeccionApi } from '../compartido/secciones'
import { Boton } from '../compartido/ui/Boton'
import { COMPARTIR_SECCIONES as T } from './textos'
import { Acciones } from './ui'

export const idCasillaRemedios = 'compartir-remedios'

/** Las secciones con texto, en el orden fijo. Nunca se ofrece una sección vacía. */
export const seccionesAgregadas = (f: Ficha | null): SeccionApi[] => {
  const s = seccionesDe(f)
  return ORDEN_SECCIONES.filter((x) => s[x]?.texto?.trim())
}

/** Lo elegido, en el orden fijo, con Sus remedios solo si se marcó su casilla. */
export const seccionesAdicionales = (elegidas: readonly SeccionApi[], remedios: boolean): SeccionApi[] =>
  ORDEN_SECCIONES.filter((x) => (x === 'remedios' ? remedios : elegidas.includes(x)))

/** Estado de la elección. Parte vacío en cada montaje: lo mínimo por defecto (6.1). */
export function useEleccionSecciones() {
  const [elegidas, setElegidas] = useState<SeccionApi[]>([])
  const [remedios, setRemedios] = useState(false)
  const paraEnviar = useMemo(() => seccionesAdicionales(elegidas, remedios), [elegidas, remedios])
  return { elegidas, setElegidas, remedios, setRemedios, paraEnviar }
}

export function ElegirSecciones({
  agregadas,
  elegidas,
  onElegidas,
  remedios,
  onRemedios,
}: {
  agregadas: readonly SeccionApi[]
  elegidas: readonly SeccionApi[]
  onElegidas: (s: SeccionApi[]) => void
  remedios: boolean
  onRemedios: (v: boolean) => void
}) {
  const id = useId()
  const otras = ORDEN_SECCIONES.filter((x) => x !== 'remedios' && agregadas.includes(x))
  const hayRemedios = agregadas.includes('remedios')
  const cambiar = (s: SeccionApi, on: boolean) => onElegidas(ORDEN_SECCIONES.filter((x) => (x === s ? on : elegidas.includes(x))))
  return (
    <div className="flex min-w-0 flex-col gap-6">
      {/* 6.2: un texto, no un control deshabilitado. */}
      <div className="flex flex-col gap-1">
        <p className="font-bold">{T.siempreVe}</p>
        <p className="flex items-start gap-2 text-base">
          <Check aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" />
          {T.base}
        </p>
      </div>

      {otras.length > 0 && (
        <fieldset className="flex min-w-0 flex-col gap-2" aria-describedby={`${id}-elige`}>
          <legend className="font-bold">{T.queMas}</legend>
          <p id={`${id}-elige`} className="text-base text-tenue">
            {T.elige}
          </p>
          <div className="flex flex-wrap gap-2">
            {otras.map((s) => {
              const on = elegidas.includes(s)
              return (
                <label
                  key={s}
                  className={`inline-flex min-h-12 max-w-full cursor-pointer items-center gap-2 angosto:flex-col angosto:items-start angosto:gap-2 rounded-full angosto:rounded-xl px-4 angosto:px-3 py-2 font-bold ring-2 ring-inset has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-turquesa ${
                    on ? 'bg-rocio text-turquesa ring-turquesa' : 'bg-hoja text-tenue ring-borde hover:ring-turquesa/40'
                  }`}
                >
                  <input type="checkbox" className="sr-only" checked={on} onChange={(e) => cambiar(s, e.target.checked)} />
                  <span aria-hidden className={`grid size-5 shrink-0 place-items-center rounded-sm ring-2 ring-inset ${on ? 'ring-turquesa' : 'ring-tenue'}`}>
                    {on && <Check className="size-4 text-turquesa" strokeWidth={3} />}
                  </span>
                  <span className="min-w-0 wrap-anywhere hyphens-auto">{TITULO_SECCION[s]}</span>
                </label>
              )
            })}
          </div>
        </fieldset>
      )}

      {hayRemedios && (
        <label htmlFor={idCasillaRemedios} className="flex min-h-12 cursor-pointer items-start gap-3 angosto:flex-col angosto:gap-2 rounded border border-borde bg-hoja p-4 angosto:p-2">
          <input
            id={idCasillaRemedios}
            type="checkbox"
            checked={remedios}
            onChange={(e) => onRemedios(e.target.checked)}
            aria-describedby={`${id}-remedios`}
            className="mt-0.5 size-6 shrink-0 accent-turquesa"
          />
          <span className="flex min-w-0 flex-col gap-1">
            <span className="font-bold">{T.incluirRemedios}</span>
            <span id={`${id}-remedios`} className="text-base text-tenue">
              {T.ayudaRemedios}
            </span>
          </span>
        </label>
      )}
    </div>
  )
}

/**
 * 6.3: antes de crear un enlace con Sus remedios. Recibe el foco al abrirse. `nombre` es lo escrito
 * en «¿Quién te va a reemplazar?» y `vence`, el vencimiento ya calculado (se muestra en hora de Chile).
 */
export function ConfirmacionRemedios({
  nombre,
  vence,
  ocupado = false,
  onSi,
  onNo,
}: {
  nombre: string
  vence: Date
  ocupado?: boolean
  onSi: () => void
  onNo: () => void
}) {
  const bloque = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bloque.current?.focus()
  }, [])
  const [antes, despues] = T.confirmacion(nombre)
  return (
    <div
      ref={bloque}
      tabIndex={-1}
      aria-busy={ocupado || undefined}
      // 6.5: en angosto, sin ícono y con px-2, para que la fecha en `cifras` quepa entera.
      className="flex max-w-prose gap-3 rounded-xl border-l-4 border-atenta bg-atenta-fondo px-4 angosto:px-2 py-3 focus-visible:outline-atenta"
    >
      <Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta angosto:hidden" />
      <div className="flex min-w-0 flex-col gap-3">
        <p className="text-base leading-relaxed">
          {antes}
          <b className="cifras font-bold">{fechaYHoraDeChile(vence).fecha}</b>
          {despues}
        </p>
        <Acciones>
          <Boton ocupado={ocupado} onClick={onSi}>
            {T.si}
          </Boton>
          <Boton
            variante="secundario"
            disabled={ocupado}
            onClick={() => {
              onNo()
              window.setTimeout(() => document.getElementById(idCasillaRemedios)?.focus(), 0)
            }}
          >
            {T.no}
          </Boton>
        </Acciones>
      </div>
    </div>
  )
}
