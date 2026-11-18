// El marco de la consola de operación (especificación MATU-81, sección 3): la barra `tinta` de la
// consola del comercio, con «Operación de MATU», «Equipo de MATU», hasta cuándo vale la entrada y
// «Salir»; el distintivo del piloto sobre `papel` y las cinco pestañas (2.2).
import type { ReactNode } from 'react'
import { Headset, Info, LogOut, ShieldCheck } from 'lucide-react'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { Boton } from '../compartido/ui/Boton'
import { DistintivoPiloto } from '../compartido/ui/Marca'
import { Nota } from '../compartido/ui/Nota'
import { useRuta } from '../familia/ruteo'
import { Pestanas } from '../familia/ui'
import { useOperacion } from './estado'
import { MARCO } from './textos'

/** 3: la barra. El contorno del foco es `papel` dentro de ella (`turquesa` sobre `tinta` mide 2,4:1). */
function Barra() {
  const { venceEn, salir } = useOperacion()
  const hora = venceEn && !Number.isNaN(new Date(venceEn).getTime()) ? fechaYHoraDeChile(new Date(venceEn)).hora : null
  return (
    <header className="flex flex-wrap items-center gap-x-5 gap-y-1 bg-tinta px-4 angosto:px-2 @3xl/app:px-10 py-3 text-papel [&_:focus-visible]:outline-papel">
      <p className="flex min-w-0 items-start gap-2">
        <Headset aria-hidden className="mt-0.5 size-6 shrink-0" />
        <span className="flex min-w-0 flex-col @3xl/app:flex-row @3xl/app:flex-wrap @3xl/app:gap-x-5">
          <span className="font-bold">{MARCO.consola}</span>
          <span className="opacity-85">{MARCO.equipo}</span>
          {hora && <span className="cifras whitespace-normal opacity-85">{MARCO.vale(hora)}</span>}
        </span>
      </p>
      <Boton variante="textoSobreTinta" className="ms-auto" icono={<LogOut aria-hidden className="size-5" />} onClick={() => void salir()}>
        {MARCO.salir}
      </Boton>
    </header>
  )
}

/** 2.2: las cinco secciones, también en el teléfono (dos renglones con `flex-wrap`). */
function Secciones() {
  const ruta = useRuta()
  const { origen } = useOperacion()
  const enPedido = ruta === '/operacion/pedido'
  return (
    <Pestanas
      etiqueta={MARCO.secciones}
      items={[
        { texto: MARCO.pedidos, ruta: '/operacion', activa: ruta === '/operacion' || (enPedido && origen === '/operacion') },
        { texto: MARCO.retractos, ruta: '/operacion/retractos', activa: ruta === '/operacion/retractos' },
        { texto: MARCO.incidencias, ruta: '/operacion/incidencias', activa: ruta === '/operacion/incidencias' },
        { texto: MARCO.cobros, ruta: '/operacion/cobros', activa: ruta === '/operacion/cobros' || (enPedido && origen === '/operacion/cobros') },
        { texto: MARCO.catalogo, ruta: '/operacion/catalogo', activa: ruta === '/operacion/catalogo' },
      ]}
    />
  )
}

const CONTENIDO = '@container/main flex-1 px-4 angosto:px-2 @3xl/app:px-10 pt-6 pb-16 outline-none'

/** Las rutas no públicas. */
export function MarcoOperacion({ children }: { children: ReactNode }) {
  return (
    <>
      <Barra />
      {/* En el teléfono, el distintivo en su renglón y las pestañas debajo; desde 48 rem, en una fila. */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 angosto:px-2 @3xl/app:px-10 pt-3">
        <DistintivoPiloto className="@3xl/app:order-last @3xl/app:ms-auto" />
        <div className="min-w-0 basis-full @3xl/app:basis-auto">
          <Secciones />
        </div>
      </div>
      <main id="contenido" tabIndex={-1} className={CONTENIDO}>
        <div className="max-w-7xl">{children}</div>
      </main>
    </>
  )
}

/** 4.1: Entrar, sin barra: el ícono y «Operación de MATU» sobre `papel`. */
export function MarcoEntrar({ children }: { children: ReactNode }) {
  return (
    <main id="contenido" tabIndex={-1} className="@container/main flex-1 px-4 angosto:px-2 py-8 outline-none">
      <div className="flex max-w-md flex-col gap-5">
        <div className="flex flex-col items-start gap-2">
          <p className="flex items-center gap-2 font-bold">
            <Headset aria-hidden className="size-6 shrink-0" />
            {MARCO.consola}
          </p>
          <DistintivoPiloto />
        </div>
        {children}
      </div>
    </main>
  )
}

/** 3: el rótulo del piloto, una vez por pantalla, al pie y lejos del botón principal. */
export function RotuloPiloto() {
  return (
    <Nota tono="atenta" titulo={MARCO.rotuloTitulo} icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
      {MARCO.rotuloTexto}
    </Nota>
  )
}

/** 3 (C9, D-81-5): bajo el `h1` de Pedidos, Retractos e Incidencias. */
export function AvisoPrivacidad() {
  return (
    <p className="flex max-w-prose gap-2 text-base text-tenue">
      <ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
      <span className="min-w-0">{MARCO.privacidad}</span>
    </p>
  )
}
