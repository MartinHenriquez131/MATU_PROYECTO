import { useEffect, type CSSProperties } from 'react'
import { BatteryFull, Signal, Wifi } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { fmtHora } from '../demo/calculos'
import { pantallaComercio, pantallaFamilia } from '../demo/logica'
import { Pantallas } from '../pantallas/Pantallas'

/** El aviso breve de cada acción. Se anuncia a lectores de pantalla y se va solo. */
function Aviso() {
  const { s, haz } = useDemo()
  const a = s.aviso
  useEffect(() => {
    if (!a) return
    const id = window.setTimeout(() => haz((x) => (x.aviso?.id === a.id ? { ...x, aviso: null } : x)), 4200)
    return () => window.clearTimeout(id)
  }, [a, haz])
  return (
    <div aria-live="polite" className="pointer-events-none absolute inset-x-3 bottom-24 z-30 flex justify-center">
      {a && (
        <p key={a.id} className="pointer-events-auto max-w-full rounded-2xl bg-tinta px-4 py-3 text-[0.95rem] text-papel shadow-lg animate-subir">
          {a.texto}
        </p>
      )}
    </div>
  )
}

/** La app en sí: las pantallas, con su transición y el modo de texto al 200%. */
export function App() {
  const { s } = useDemo()
  const clave =
    s.rol === 'familia' ? `f${pantallaFamilia(s).n}` : s.rol === 'comercio' ? `c${pantallaComercio(s).n}` : `r${s.relevo.fase}${s.relevo.token ?? ''}`
  // zoom: 2 duplica todo como el zoom del navegador, y obliga a que el contenido se reacomode
  // en la mitad del ancho: la prueba de WCAG 1.4.4 y 1.4.10 hecha visible.
  const zoom: CSSProperties | undefined = s.texto200 ? { zoom: 2 } : undefined
  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-papel">
      <div style={zoom} className="flex min-h-0 flex-1 flex-col">
        <div key={clave} className={`flex min-h-0 flex-1 flex-col ${s.dir === 'atras' ? 'animate-volver' : 'animate-entrar'}`}>
          <Pantallas />
        </div>
      </div>
      <Aviso />
    </div>
  )
}

/** Marco de teléfono para el proyector, con su barra de estado y la hora de la demo. */
export function MarcoTelefono() {
  const { s } = useDemo()
  return (
    <div className="relative h-[min(52rem,calc(100dvh-5rem))] w-[24.4rem] shrink-0 rounded-[3.4rem] bg-[#0a1113] p-[0.7rem] shadow-[0_2px_0_1px_rgb(255_255_255/0.06)_inset,0_40px_80px_-30px_rgb(0_0_0/0.55),0_0_0_1px_rgb(0_0_0/0.4)]">
      <div className="relative flex h-full flex-col overflow-hidden rounded-[2.75rem] bg-papel">
        <div className="relative z-20 flex h-12 shrink-0 items-center justify-between bg-hoja px-7 text-[0.85rem] font-bold" aria-hidden>
          <span className="cifras">{fmtHora(s.ahora)}</span>
          <span className="absolute top-2.5 left-1/2 h-7 w-28 -translate-x-1/2 rounded-full bg-[#0a1113]" />
          <span className="flex items-center gap-1.5">
            <Signal className="size-4" />
            <Wifi className="size-4" />
            <BatteryFull className="size-5" />
          </span>
        </div>
        <App />
        <div className="flex h-6 shrink-0 items-center justify-center bg-hoja" aria-hidden>
          <span className="h-1.5 w-32 rounded-full bg-tinta/80" />
        </div>
      </div>
    </div>
  )
}
