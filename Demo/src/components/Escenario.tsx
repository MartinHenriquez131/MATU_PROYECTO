// Decide la presentación: en pantalla ancha (proyector), marco de teléfono y panel al lado;
// en el celular, la app a pantalla completa y el panel detrás de un botón discreto.
import { useEffect, useRef, useState } from 'react'
import { PanelRight, X } from 'lucide-react'
import { usePantallaAncha } from './movimiento'
import { App, MarcoTelefono } from './Telefono'
import { PanelPresentador } from './PanelPresentador'
import { RelevoUrl } from './RelevoUrl'
import { Logo } from './Ui'

function Distintivo({ claro = false }: { claro?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[0.8rem] font-bold ${claro ? 'bg-tinta/[0.07] text-tenue' : 'bg-tinta/[0.07] text-tenue'}`}>
      <span aria-hidden className="size-1.5 rounded-full bg-miel" />
      Demo con datos simulados
    </span>
  )
}

export function Escenario() {
  const ancha = usePantallaAncha()
  const [abierto, setAbierto] = useState(false)
  const dialogo = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const d = dialogo.current
    if (!d) return
    if (abierto && !d.open) d.showModal()
    if (!abierto && d.open) d.close()
  }, [abierto])

  if (ancha) {
    return (
      <div className="flex min-h-dvh items-center justify-center gap-[clamp(2rem,5vw,5rem)] px-8 py-6">
        <RelevoUrl />
        <main className="flex flex-col items-center gap-3">
          <Distintivo />
          <MarcoTelefono />
        </main>
        <aside aria-label="Panel del presentador" className="flex h-[min(52rem,calc(100dvh-3rem))] w-[min(26rem,36vw)] flex-col">
          <header className="flex items-center gap-3 pb-4">
            <Logo className="size-10 shrink-0" />
            <div>
              <p className="font-display text-[1.35rem] leading-none font-extrabold tracking-[-0.02em]">MATU</p>
              <p className="text-[0.9rem] text-tenue">Panel del presentador</p>
            </div>
          </header>
          <div className="sin-barra min-h-0 flex-1 overflow-y-auto pr-1 pb-4">
            <PanelPresentador />
          </div>
        </aside>
      </div>
    )
  }

  return (
    <div className="flex h-dvh flex-col bg-hoja pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
      <RelevoUrl />
      <div className="flex shrink-0 items-center justify-between gap-2 px-3 py-1">
        <Distintivo claro />
        <button
          type="button"
          onClick={() => setAbierto(true)}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-3 text-[0.85rem] font-bold text-tenue hover:text-tinta"
          aria-haspopup="dialog"
        >
          <PanelRight aria-hidden className="size-4.5" />
          Guía
        </button>
      </div>
      <main className="flex min-h-0 flex-1 flex-col">
        <App />
      </main>
      <dialog
        ref={dialogo}
        onClose={() => setAbierto(false)}
        aria-label="Panel del presentador"
        className="m-0 mt-auto h-[88dvh] max-h-none w-full max-w-none rounded-t-[1.6rem] bg-papel p-0 text-tinta backdrop:bg-black/40"
      >
        <div className="flex h-full flex-col">
          <div className="flex shrink-0 items-center justify-between px-5 pt-4 pb-2">
            <p className="font-display text-[1.2rem] font-bold">Guía de la demo</p>
            <button type="button" onClick={() => setAbierto(false)} aria-label="Cerrar la guía" className="grid size-12 place-items-center rounded-full hover:bg-tinta/[0.06]">
              <X aria-hidden className="size-6" />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-8">
            <PanelPresentador alElegir={() => setAbierto(false)} />
          </div>
        </div>
      </dialog>
    </div>
  )
}
