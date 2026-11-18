// La consola de operación (MATU-81, especificación sección 2): una app aparte bajo `/operacion`, sin
// `ProveedorFamilia` ni `ProveedorComercio`. Decide qué pantalla va en cada ruta según la entrada; el
// foco va al `h1` al llegar a cada ruta, y ni la URL ni el `<title>` llevan lo elegido (C7).
import { useEffect, useLayoutEffect } from 'react'
import { WifiOff } from 'lucide-react'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { navegar, useRuta, type RutaOperacion } from '../familia/ruteo'
import { Titulo } from '../familia/ui'
import { GENERAL } from '../familia/textos'
import { PantallaCatalogo } from './Catalogo'
import { PantallaCobros } from './Cobros'
import { EntrarOperacion } from './Entrar'
import { ProveedorOperacion, rutaSinElegido, useOperacion } from './estado'
import { PantallaIncidencias } from './Incidencias'
import { MarcoEntrar, MarcoOperacion } from './Marco'
import { PantallaPedidos } from './Pedidos'
import { PantallaRetractos } from './Retractos'
import { MARCO, TITULO_OPERACION } from './textos'

export function AppOperacion() {
  return (
    <ProveedorOperacion>
      <Rutas />
    </ProveedorOperacion>
  )
}

const RUTAS: readonly RutaOperacion[] = [
  '/operacion',
  '/operacion/entrar',
  '/operacion/pedido',
  '/operacion/retractos',
  '/operacion/incidencias',
  '/operacion/cobros',
  '/operacion/catalogo',
]
const esRutaOperacion = (r: string): r is RutaOperacion => (RUTAS as readonly string[]).includes(r)

const TITULO: Record<RutaOperacion, string> = {
  '/operacion': TITULO_OPERACION.pedidos,
  '/operacion/entrar': TITULO_OPERACION.entrar,
  '/operacion/pedido': TITULO_OPERACION.pedido,
  '/operacion/retractos': TITULO_OPERACION.retractos,
  '/operacion/incidencias': TITULO_OPERACION.incidencias,
  '/operacion/cobros': TITULO_OPERACION.cobros,
  '/operacion/catalogo': TITULO_OPERACION.catalogo,
}

/** A qué ruta se manda, o `null` si la ruta se muestra tal cual. */
function redireccion(ruta: string, s: ReturnType<typeof useOperacion>): RutaOperacion | null {
  if (!esRutaOperacion(ruta)) return s.fase === 'dentro' ? '/operacion' : '/operacion/entrar'
  if (s.fase === 'fuera') return ruta === '/operacion/entrar' ? null : '/operacion/entrar'
  if (s.fase === 'dentro' && ruta === '/operacion/entrar') return s.destino ?? '/operacion'
  // 2.1: al recargar `/operacion/pedido` no hay pedido elegido: a la lista, con `replace`.
  if (s.fase === 'dentro' && ruta === '/operacion/pedido' && !s.pedidoId) return s.origen
  return null
}

function Rutas() {
  const s = useOperacion()
  const ruta = useRuta()
  const destino = s.fase === 'cargando' || s.fase === 'error' ? null : redireccion(ruta, s)

  useEffect(() => {
    if (!destino) return
    // 2.1: la ruta pedida sin haber entrado se guarda en memoria, sin lo elegido.
    if (s.fase === 'fuera' && destino === '/operacion/entrar') {
      const volver = rutaSinElegido(ruta)
      if (volver) s.fijar({ destino: volver })
    }
    navegar(destino, { reemplazar: true })
  }, [destino, ruta, s])

  // 2.1: el `<title>` de cada ruta, sin la referencia del pedido.
  useLayoutEffect(() => {
    document.title = s.fase !== 'dentro' || !esRutaOperacion(ruta) ? TITULO_OPERACION.entrar : TITULO[ruta]
  }, [ruta, s.fase])

  // 2.1: al llegar a cada ruta, el foco va al `h1`.
  useEffect(() => {
    if (s.fase === 'cargando') return
    const t = window.setTimeout(() => document.getElementById('titulo-pagina')?.focus({ preventScroll: false }), 0)
    return () => window.clearTimeout(t)
  }, [ruta, s.fase])

  if (s.fase === 'cargando')
    return (
      <MarcoEntrar>
        <Abriendo />
      </MarcoEntrar>
    )
  if (s.fase === 'error')
    return (
      <MarcoEntrar>
        <Titulo className="text-3xl">{MARCO.consola}</Titulo>
        <Nota tono="pronto" rol="alert" icono={<WifiOff aria-hidden className="mt-0.5 size-5 shrink-0 text-pronto" />}>
          {GENERAL.errorAlCargar}
        </Nota>
        <Boton variante="secundario" className="self-start" onClick={() => void s.cargar()}>
          {MARCO.volverAIntentar}
        </Boton>
      </MarcoEntrar>
    )
  if (destino) return null
  if (ruta === '/operacion/entrar') return <EntrarOperacion />

  return (
    <MarcoOperacion>
      {ruta === '/operacion/retractos' ? (
        <div key="retractos" className="animate-aparecer">
          <PantallaRetractos />
        </div>
      ) : ruta === '/operacion/incidencias' ? (
        <div key="incidencias" className="animate-aparecer">
          <PantallaIncidencias />
        </div>
      ) : ruta === '/operacion/cobros' || (ruta === '/operacion/pedido' && s.origen === '/operacion/cobros') ? (
        <div key="cobros" className="animate-aparecer">
          <PantallaCobros ruta={ruta === '/operacion/pedido' ? '/operacion/pedido' : '/operacion/cobros'} />
        </div>
      ) : ruta === '/operacion/catalogo' ? (
        <div key="catalogo" className="animate-aparecer">
          <PantallaCatalogo />
        </div>
      ) : (
        // Las dos rutas de los pedidos son una sola pantalla: la lista se conserva al elegir uno.
        <div key="pedidos" className="animate-aparecer">
          <PantallaPedidos ruta={ruta === '/operacion/pedido' ? '/operacion/pedido' : '/operacion'} />
        </div>
      )}
    </MarcoOperacion>
  )
}

function Abriendo() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.abriendo : ''}
    </p>
  )
}
