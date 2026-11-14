// El marco de la consola del comercio (especificación MATU-63, sección 3): la barra `tinta`, el
// distintivo del piloto sobre `papel`, las dos pestañas y el contenido. Más sobria que la app de la
// familia: es otra persona con otro trabajo (Demo/DISENO.md 3, «El comercio»).
import type { ReactNode } from 'react'
import { Info, LogOut, Store } from 'lucide-react'
import { Boton } from '../compartido/ui/Boton'
import { DistintivoPiloto } from '../compartido/ui/Marca'
import { Nota } from '../compartido/ui/Nota'
import { useRuta } from '../familia/ruteo'
import { Pestanas } from '../familia/ui'
import { useComercio } from './estado'
import { MARCO_COMERCIO, PEDIDOS } from './textos'

/** 3: la barra. El contorno del foco es `papel` dentro de ella (`turquesa` sobre `tinta` mide 2,4:1). */
function Barra({ conSalir = true }: { conSalir?: boolean }) {
  const { comercio, salir } = useComercio()
  return (
    <header className="flex flex-wrap items-center gap-x-5 gap-y-1 bg-tinta px-4 angosto:px-2 @3xl/app:px-10 py-3 text-papel [&_:focus-visible]:outline-papel">
      <p className="flex min-w-0 items-start gap-2">
        <Store aria-hidden className="mt-0.5 size-6 shrink-0" />
        <span className="min-w-0">
          {comercio && (
            <>
              <span className="font-bold">{comercio.nombre_fantasia}</span>{' '}
              {comercio.ficticio && <span className="inline-block font-bold">{MARCO_COMERCIO.ficticio}</span>}{' '}
            </>
          )}
          <span className={comercio ? 'inline-block opacity-85' : 'inline-block font-bold'}>{MARCO_COMERCIO.consola}</span>
        </span>
      </p>
      {conSalir && (
        <Boton variante="textoSobreTinta" className="ms-auto" icono={<LogOut aria-hidden className="size-5" />} onClick={() => void salir()}>
          {MARCO_COMERCIO.salir}
        </Boton>
      )}
    </header>
  )
}

/** 2.2: «Pedidos de hoy» (activa también en `/comercio/pedido`) y «Tus productos». */
function Secciones() {
  const ruta = useRuta()
  return (
    <Pestanas
      etiqueta={MARCO_COMERCIO.secciones}
      items={[
        { texto: MARCO_COMERCIO.pedidosDeHoy, ruta: '/comercio', activa: ruta === '/comercio' || ruta === '/comercio/pedido' },
        { texto: MARCO_COMERCIO.tusProductos, ruta: '/comercio/productos', activa: ruta === '/comercio/productos' },
      ]}
    />
  )
}

const CONTENIDO = '@container/main flex-1 px-4 angosto:px-2 @3xl/app:px-10 pt-6 pb-16 outline-none'

/** Las rutas no públicas. Sin `pestanas` (cuenta inactiva, 5.7), solo la barra con «Salir». */
export function MarcoComercio({ children, pestanas = true }: { children: ReactNode; pestanas?: boolean }) {
  return (
    <>
      <Barra />
      {/* En el teléfono, el distintivo en su renglón y las pestañas debajo; desde 48 rem, en una fila. */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 angosto:px-2 @3xl/app:px-10 pt-3">
        <DistintivoPiloto className="@3xl/app:order-last @3xl/app:ms-auto" />
        {pestanas && (
          <div className="min-w-0 basis-full @3xl/app:basis-auto">
            <Secciones />
          </div>
        )}
      </div>
      <main id="contenido" tabIndex={-1} className={CONTENIDO}>
        <div className="max-w-7xl">{children}</div>
      </main>
    </>
  )
}

/** 4.1: Entrar, sin barra (todavía no hay comercio): el ícono y «Pedidos de MATU» sobre `papel`. */
export function MarcoEntrar({ children }: { children: ReactNode }) {
  return (
    <main id="contenido" tabIndex={-1} className="@container/main flex-1 px-4 angosto:px-2 py-8 outline-none">
      <div className="flex max-w-md flex-col gap-5">
        <div className="flex flex-col items-start gap-2">
          <p className="flex items-center gap-2 font-bold">
            <Store aria-hidden className="size-6 shrink-0" />
            {MARCO_COMERCIO.consola}
          </p>
          <DistintivoPiloto />
        </div>
        {children}
      </div>
    </main>
  )
}

/** 5.6 y 8.4: el rótulo del piloto, una vez por pantalla y solo si el comercio es de prueba. */
export function RotuloPiloto({ texto }: { texto: string }) {
  const { comercio } = useComercio()
  if (!comercio?.ficticio) return null
  return (
    <Nota tono="atenta" titulo={PEDIDOS.rotuloTitulo} icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
      {texto}
    </Nota>
  )
}

/** 5.6 (O2): «¿Algo no calza? Avisa a MATU: …». */
export function Pie() {
  const { contacto } = useComercio()
  return <p className="max-w-prose text-base break-words text-tenue">{PEDIDOS.pie(contacto)}</p>
}
