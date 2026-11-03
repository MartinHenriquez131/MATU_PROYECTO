// Quién la vio (MATU-45, especificación docs/diseno/matu-45-aperturas.md), copiada de `QuienVio` y
// `Eventos` de la demo (Demo/src/familia/Ficha.tsx). Lee `GET …/plan/aperturas` de a 20 líneas; no
// guarda nada entre visitas ni en el navegador. Sin la columna «Quién puede verla ahora» ni los
// botones hacia Enlaces y Compartir mientras MATU-48 no exista en web/ (decisión D4).
import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { CircleAlert, CloudOff, Link2, Lock, ShieldCheck, UserRound } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { listarAperturas, type Apertura } from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { diaRelativoDeChile, fechaYHoraDeChile } from '../compartido/fechas'
import { Boton } from '../compartido/ui/Boton'
import { useDemora } from './Estados'
import { puedeVerFicha, useFamilia } from './estado'
import { SinAcceso } from './Ficha'
import { navegar } from './ruteo'
import { Nota, Pagina, Volver } from './ui'
import { FICHA, QUIEN } from './textos'

const LIMITE = 20

const FRASE: Record<Apertura['tipo'], (n: string) => string> = {
  presentacion: QUIEN.presentacion,
  apertura: QUIEN.apertura,
  pin_incorrecto: QUIEN.pinIncorrecto,
  bloqueo: QUIEN.bloqueo,
}

/** Cuatro formas distintas: el tipo nunca se distingue solo por el color. */
function IconoApertura({ tipo }: { tipo: Apertura['tipo'] }) {
  const atenta = tipo === 'pin_incorrecto' || tipo === 'bloqueo'
  const Icono = tipo === 'presentacion' ? Link2 : tipo === 'apertura' ? UserRound : tipo === 'pin_incorrecto' ? CircleAlert : Lock
  return (
    <span aria-hidden className={`mt-0.5 grid size-9 shrink-0 place-items-center rounded-full ${atenta ? 'bg-atenta-fondo text-atenta' : 'bg-rocio text-turquesa'}`}>
      <Icono className="size-5" />
    </span>
  )
}

const instante = (a: Apertura) => new Date(a.ocurrido_en)
const valida = (a: Apertura) => !Number.isNaN(instante(a).getTime())

/** «a las 10:14» o, con `completa`, «hoy a las 10:14», «el 24/10/2026 a las 10:14». Siempre en <time>. */
function Hora({ a, completa = false }: { a: Apertura; completa?: boolean }) {
  const d = instante(a)
  const { fecha, hora } = fechaYHoraDeChile(d)
  return (
    <time dateTime={a.ocurrido_en} title={`${fecha} ${hora}`} className="block text-base text-tenue tabular-nums">
      {completa ? `${diaRelativoDeChile(d, new Date(), true)} ${QUIEN.aLas(hora)}` : QUIEN.aLas(hora)}
    </time>
  )
}

/** Una línea (4.3), con la explicación tranquila bajo una presentación sin apertura y bajo un bloqueo. */
function LineaApertura({ a, sinAbrir, completa, foco }: { a: Apertura; sinAbrir: boolean; completa?: boolean; foco?: React.Ref<HTMLLIElement> }) {
  return (
    <li ref={foco} tabIndex={foco ? -1 : undefined} className="flex items-start gap-3 border-b border-linea py-3 outline-none last:border-0 angosto:flex-col angosto:gap-2">
      <IconoApertura tipo={a.tipo} />
      <span className="flex min-w-0 flex-col">
        <span className="text-lg font-bold leading-snug break-words">{FRASE[a.tipo](a.acceso.nombre_relevo)}</span>
        <Hora a={a} completa={completa} />
        {sinAbrir && <span className="mt-1 text-base text-tenue">{QUIEN.sinAbrir}</span>}
        {a.tipo === 'bloqueo' && <span className="mt-1 text-base text-tenue">{QUIEN.bloqueado}</span>}
      </span>
    </li>
  )
}

/**
 * ¿La presentación `i` no tiene, más arriba en la lista, una apertura del mismo acceso? La lista va
 * de la más nueva a la más vieja, así que lo de arriba ya está cargado.
 */
const presentacionSinAbrir = (lista: Apertura[], i: number) =>
  lista[i].tipo === 'presentacion' && !lista.slice(0, i).some((x) => x.tipo === 'apertura' && x.acceso.id === lista[i].acceso.id)

/** 5.1: tres líneas esqueleto pasados 300 ms. */
function Esqueleto() {
  const ver = useDemora(300)
  return (
    <ol aria-busy="true" className="flex flex-col">
      <li className="sr-only">{ver ? 'Cargando…' : ''}</li>
      {ver &&
        [0, 1, 2].map((i) => (
          <li key={i} aria-hidden className="flex items-start gap-3 border-b border-linea py-3 last:border-0 motion-safe:animate-pulse">
            <span className="size-9 shrink-0 rounded-full bg-hoja" />
            <span className="flex flex-1 flex-col gap-2 pt-1">
              <span className="h-4 w-3/5 rounded-full bg-hoja" />
              <span className="h-3.5 w-1/4 rounded-full bg-hoja" />
            </span>
          </li>
        ))}
    </ol>
  )
}

function ErrorAperturas({ reintentar }: { reintentar: () => void }) {
  return (
    <div className="flex max-w-prose flex-col items-start gap-4">
      <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
        {QUIEN.error}
      </Nota>
      <Boton variante="secundario" onClick={reintentar}>
        {QUIEN.intentar}
      </Boton>
    </div>
  )
}

type Carga = 'cargando' | 'lista' | 'red' | 'sin-acceso'

// ---------------------------------------------------------------- la pantalla

export function QuienLaVio() {
  const { rol, grupo } = useFamilia()
  // 5.4: el observador (y el pagador sin `puede_ver_plan`) ve lo mismo que en la ficha, sin pedir nada.
  if (!puedeVerFicha(rol, grupo)) return <SinAcceso />
  return <Aperturas />
}

function Aperturas() {
  const { personaId, anunciar } = useFamilia()
  const [carga, setCarga] = useState<Carga>('cargando')
  const [items, setItems] = useState<Apertura[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [paginas, setPaginas] = useState(0)
  const [masCargando, setMasCargando] = useState(false)
  const [masFallo, setMasFallo] = useState(false)
  const primeraNueva = useRef<number | null>(null)
  const nodoNuevo = useRef<HTMLLIElement | null>(null)

  const primera = useCallback(async () => {
    if (!personaId) return
    setCarga('cargando')
    setMasFallo(false)
    try {
      const r = await listarAperturas(personaId, null, LIMITE)
      setItems(r.items.filter(valida))
      setCursor(r.siguiente_cursor)
      setPaginas(1)
      setCarga('lista')
    } catch (e) {
      if (esVencida(e)) return
      // 404: no existe o no puedes, sin decir cuál. 422 (cursor) y el resto: como error de red (5.6).
      setCarga(leerFallo(e).status === 404 ? 'sin-acceso' : 'red')
    }
  }, [personaId])

  useEffect(() => {
    void primera()
  }, [primera])

  const anteriores = async () => {
    if (!personaId || !cursor || masCargando) return
    setMasCargando(true)
    setMasFallo(false)
    try {
      const r = await listarAperturas(personaId, cursor, LIMITE)
      const nuevas = r.items.filter(valida)
      primeraNueva.current = nuevas.length ? items.length : null
      setItems((x) => [...x, ...nuevas])
      setCursor(r.siguiente_cursor)
      setPaginas((n) => n + 1)
      anunciar(QUIEN.seAgregaron(nuevas.length))
    } catch (e) {
      if (esVencida(e)) return
      if (leerFallo(e).status === 404) return setCarga('sin-acceso')
      setMasFallo(true)
    } finally {
      setMasCargando(false)
    }
  }

  // 5.7: el foco va a la primera línea nueva.
  useEffect(() => {
    if (primeraNueva.current === null) return
    primeraNueva.current = null
    nodoNuevo.current?.focus()
  }, [items])

  if (carga === 'sin-acceso') return <SinAcceso />

  let cuerpo
  if (carga === 'cargando') cuerpo = <Esqueleto />
  else if (carga === 'red') cuerpo = <ErrorAperturas reintentar={() => void primera()} />
  else if (!items.length) cuerpo = <Nota tono="rocio">{QUIEN.vacio}</Nota>
  else cuerpo = <ListaPorDia items={items} nodoNuevo={nodoNuevo} indiceNuevo={primeraNueva.current} />

  return (
    <Pagina titulo={QUIEN.titulo} bajada={QUIEN.bajada} antes={<Volver onClick={() => navegar('/ficha')}>{FICHA.volverALaFicha}</Volver>}>
      <section aria-label={QUIEN.titulo} className="flex max-w-prose min-w-0 flex-col gap-5">
        {cuerpo}
        {carga === 'lista' &&
          items.length > 0 &&
          (masFallo ? (
            <ErrorAperturas reintentar={() => void anteriores()} />
          ) : cursor ? (
            <Boton variante="secundario" className="self-start" ocupado={masCargando} textoOcupado="Cargando…" aria-disabled={masCargando || undefined} onClick={() => void anteriores()}>
              {QUIEN.anteriores}
            </Boton>
          ) : paginas > 1 ? (
            <p className="text-tenue">{QUIEN.noHayMas}</p>
          ) : null)}
        <p className="flex gap-2 text-base text-tenue">
          <ShieldCheck aria-hidden className="mt-0.5 size-4.5 shrink-0" />
          {QUIEN.nadieDeMatu}
        </p>
      </section>
    </Pagina>
  )
}

/** Las líneas agrupadas por día de Chile, con un h2 por día; el orden es el del servidor. */
function ListaPorDia({ items, nodoNuevo, indiceNuevo }: { items: Apertura[]; nodoNuevo: React.RefObject<HTMLLIElement | null>; indiceNuevo: number | null }) {
  const ahora = new Date()
  const grupos: { dia: string; desde: number; lineas: Apertura[] }[] = []
  items.forEach((a, i) => {
    const dia = diaRelativoDeChile(instante(a), ahora)
    const ultimo = grupos[grupos.length - 1]
    if (ultimo && ultimo.dia === dia) ultimo.lineas.push(a)
    else grupos.push({ dia, desde: i, lineas: [a] })
  })
  return (
    <div className="flex flex-col">
      {grupos.map((g, n) => (
        <Fragment key={`${g.dia}-${g.desde}`}>
          <h2 className={`text-lg font-bold ${n ? 'mt-6' : ''}`}>{g.dia}</h2>
          <ol className="flex flex-col">
            {g.lineas.map((a, j) => {
              const i = g.desde + j
              return (
                <LineaApertura
                  key={`${a.acceso.id}-${a.ocurrido_en}-${a.tipo}-${i}`}
                  a={a}
                  sinAbrir={presentacionSinAbrir(items, i)}
                  foco={i === indiceNuevo ? nodoNuevo : undefined}
                />
              )
            })}
          </ol>
        </Fragment>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- el bloque de la ficha (2.1)

/** «Últimas aperturas» bajo los tres campos: las 3 más recientes, con la fecha en la línea. */
export function UltimasAperturas() {
  const { personaId } = useFamilia()
  const [items, setItems] = useState<Apertura[] | null>(null)
  useEffect(() => {
    if (!personaId) return
    let vivo = true
    listarAperturas(personaId, null, 3)
      .then((r) => vivo && setItems(r.items.filter(valida)))
      // Si falla, el bloque no aparece: la pantalla completa muestra el error (5.3).
      .catch(() => vivo && setItems(null))
    return () => {
      vivo = false
    }
  }, [personaId])
  if (!items) return null
  return (
    <section aria-labelledby="ultimas-t" className="flex flex-col gap-2">
      <h2 id="ultimas-t" className="text-xl font-bold leading-snug">
        {QUIEN.ultimas}
      </h2>
      {items.length === 0 ? (
        <Nota tono="rocio">{QUIEN.vacio}</Nota>
      ) : (
        <>
          <ol className="flex flex-col">
            {items.map((a, i) => (
              <LineaApertura key={`${a.acceso.id}-${a.ocurrido_en}-${a.tipo}-${i}`} a={a} sinAbrir={presentacionSinAbrir(items, i)} completa />
            ))}
          </ol>
          <Boton variante="texto" className="self-start px-0" onClick={() => navegar('/ficha/quien-la-vio')}>
            {QUIEN.verTodo}
          </Boton>
        </>
      )}
    </section>
  )
}
