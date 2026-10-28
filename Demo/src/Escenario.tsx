// Compone la demo: la franja del presentador, la app del rol actual y el cajón de la guía.
// "Texto al 200%" aplica zoom 2 solo a la app: como todo se ordena con container queries, la app
// se reacomoda a la mitad del ancho y la guía queda igual.
import { useEffect, useRef, useState, useSyncExternalStore, type CSSProperties } from 'react'
import { useDemo } from './demo/estado'
import { pantallaComercio, pantallaFamilia } from './demo/logica'
import type { Estado } from './demo/tipos'
import { RelevoUrl } from './components/RelevoUrl'
import { AppFamilia, conBarraDeSecciones } from './familia/AppFamilia'
import { RelevoApp } from './relevo/Relevo'
import { Consola } from './comercio/Comercio'
import { ProveedorPresentador, usePresentador } from './presentador/contexto'
import { Cajon, DistintivoFlotante, Franja, useAtajos } from './presentador/Presentador'

const ANCHO_CAJON = '(min-width: 64rem)'
function suscribir(cb: () => void) {
  const m = window.matchMedia(ANCHO_CAJON)
  m.addEventListener('change', cb)
  return () => m.removeEventListener('change', cb)
}
/** Desde 64 rem el cajón empuja la app; más angosto, la tapa. */
const useCajonEmpuja = () => useSyncExternalStore(suscribir, () => window.matchMedia(ANCHO_CAJON).matches, () => true)

function clave(s: Estado): string {
  if (s.rol === 'familia') return `f${pantallaFamilia(s).n}`
  if (s.rol === 'comercio') return `c${pantallaComercio(s).n}`
  return `r${s.relevo.fase}${s.relevo.token ?? ''}`
}

/**
 * Al navegar, el foco va al título de la página (o al detalle, en las vistas con lista y detalle),
 * para que un lector de pantalla anuncie dónde está. Si el foco estaba en la guía o la franja, se
 * queda ahí: el presentador sigue eligiendo escenas.
 */
function useFocoAlNavegar(k: string) {
  // Se compara con la clave anterior y no con un "primera vez": con StrictMode el efecto corre dos
  // veces al montar y el foco saltaba al título al cargar, antes de "Saltar al contenido".
  const anterior = useRef(k)
  useEffect(() => {
    if (anterior.current === k) return
    anterior.current = k
    const activo = document.activeElement
    const enPresentador = !!activo?.closest('#guia-presentador, [data-presentador]')
    const detalle = document.querySelector<HTMLElement>('[data-foco="detalle"]')
    if (detalle) {
      // En el teléfono el detalle va debajo de la lista: se lleva arriba para que se vea entero
      // (ESPEC-ADR-027, 7.6). En pantalla ancha está al lado y basta con 'nearest'.
      const telefono = window.matchMedia('(width < 40rem)').matches
      detalle.scrollIntoView({ block: telefono ? 'start' : 'nearest' })
      if (!enPresentador) detalle.focus({ preventScroll: true })
      return
    }
    window.scrollTo({ top: 0 })
    if (!enPresentador) document.getElementById('titulo-pagina')?.focus({ preventScroll: true })
  }, [k])
}

/** El aviso breve de cada acción. Se anuncia a lectores de pantalla y se va solo. */
function Aviso({ corrido, presentacion, sobreBarra }: { corrido: boolean; presentacion: boolean; sobreBarra: boolean }) {
  const { s, haz } = useDemo()
  const a = s.aviso
  useEffect(() => {
    if (!a) return
    const id = window.setTimeout(() => haz((x) => (x.aviso?.id === a.id ? { ...x, aviso: null } : x)), 5000)
    return () => window.clearTimeout(id)
  }, [a, haz])
  // Con el texto al 200% la app tiene zoom 2: la distancia al borde se divide por dos para que
  // el aviso no quede bajo el cajón de la guía.
  const derecha = corrido ? (s.texto200 ? 'right-50' : 'right-100') : s.texto200 ? 'right-3' : 'right-5'
  // En el teléfono, sobre la barra de secciones de la familia y, si está, sobre el distintivo
  // flotante, que también sube. Con el texto al 200% no hay barra fija (ESPEC-ADR-027, 7.6.2).
  const abajo = presentacion
    ? s.texto200
      ? 'bottom-12'
      : sobreBarra
        ? 'bottom-24 max-sm:bottom-40'
        : 'bottom-24'
    : s.texto200
      ? 'bottom-3'
      : sobreBarra
        ? 'bottom-5 max-sm:bottom-20'
        : 'bottom-5'
  return (
    <div aria-live="polite" className={`pointer-events-none fixed left-5 z-30 ml-auto flex max-w-md justify-end ${derecha} ${abajo}`}>
      {a && (
        <p key={a.id} className="pointer-events-auto rounded-xl bg-tinta px-4 py-3 text-papel shadow-lg motion-safe:animate-aparecer">
          {a.texto}
        </p>
      )}
    </div>
  )
}

function AppActual() {
  const { s } = useDemo()
  if (s.rol === 'relevo') return <RelevoApp />
  if (s.rol === 'comercio') return <Consola />
  return <AppFamilia />
}

function Marco() {
  const { s } = useDemo()
  const p = usePresentador()
  const empuja = useCajonEmpuja()
  useAtajos()
  useFocoAlNavegar(clave(s))
  const zoom: CSSProperties | undefined = s.texto200 ? { zoom: 2 } : undefined
  const corrido = p.cajon && empuja
  // El aviso de piloto tiene que estar siempre en pantalla. La franja va en el flujo (a 320 px no
  // cabe fija), así que cuando su distintivo no se ve entero aparece el distintivo flotante. Se
  // observa el distintivo y no toda la franja: a 320 px la franja es alta y su parte de abajo
  // puede seguir a la vista cuando el distintivo ya salió.
  const franja = useRef<HTMLDivElement>(null)
  const [franjaVisible, setFranjaVisible] = useState(true)
  useEffect(() => {
    const el = franja.current?.querySelector('[data-distintivo="franja"]')
    if (!el) return
    const obs = new IntersectionObserver(([e]) => setFranjaVisible(e.intersectionRatio >= 0.99), { threshold: [0, 0.99, 1] })
    obs.observe(el)
    return () => obs.disconnect()
  }, [p.presentacion])
  const flotante = p.presentacion || !franjaVisible
  const sobreBarra = conBarraDeSecciones(s)
  return (
    <>
      <RelevoUrl />
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-hoja focus:px-4 focus:py-3 focus:font-bold focus:text-pino"
      >
        Saltar al contenido
      </a>
      {/* Espacio al final para que el distintivo flotante no tape el último contenido. */}
      {/* En modo presentación el distintivo va arriba, con su espacio reservado: al cargar no tapa el titular. */}
      <div className={`flex min-h-dvh flex-col pb-24 ${corrido ? 'pr-96' : ''} ${p.presentacion ? 'pt-18' : ''}`}>
        {!p.presentacion && (
          <div data-presentador ref={franja}>
            <Franja />
          </div>
        )}
        <div style={zoom} className="@container/app flex flex-1 flex-col">
          <AppActual />
          <Aviso corrido={corrido} presentacion={flotante && !p.presentacion} sobreBarra={sobreBarra} />
        </div>
      </div>
      {flotante && (
        <div data-presentador>
          <DistintivoFlotante arriba={p.presentacion} sobreBarra={sobreBarra && !s.texto200} />
        </div>
      )}
      {p.cajon && <Cajon />}
    </>
  )
}

export function Escenario() {
  return (
    <ProveedorPresentador>
      <Marco />
    </ProveedorPresentador>
  )
}
