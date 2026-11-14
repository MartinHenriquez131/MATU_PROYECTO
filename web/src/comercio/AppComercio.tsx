// La consola del comercio (MATU-63, especificación sección 2): una app aparte bajo `/comercio`, sin
// `ProveedorFamilia`. Decide qué pantalla va en cada ruta según la entrada; el foco va al `h1` al
// llegar a cada ruta y el `<title>` nunca lleva la parte elegida en la URL.
import { useEffect, useLayoutEffect } from 'react'
import { WifiOff } from 'lucide-react'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { navegar, useRuta, type RutaComercio } from '../familia/ruteo'
import { Titulo } from '../familia/ui'
import { EntrarComercio } from './Entrar'
import { ProveedorComercio, useComercio } from './estado'
import { MarcoComercio, MarcoEntrar } from './Marco'
import { PantallaPedidos } from './Pedidos'
import { PantallaProductos } from './Productos'
import { GENERAL } from '../familia/textos'
import { ENTRAR_COMERCIO, MARCO_COMERCIO, PEDIDOS, TITULO_COMERCIO } from './textos'

export function AppComercio() {
  return (
    <ProveedorComercio>
      <Rutas />
    </ProveedorComercio>
  )
}

const RUTAS: readonly RutaComercio[] = ['/comercio', '/comercio/entrar', '/comercio/pedido', '/comercio/productos']
const esRutaComercio = (r: string): r is RutaComercio => (RUTAS as readonly string[]).includes(r)

/** La redirección que corresponde, o `null` si la ruta se muestra tal cual. */
function redireccion(ruta: string, s: ReturnType<typeof useComercio>): RutaComercio | null {
  if (!esRutaComercio(ruta)) return s.fase === 'dentro' ? '/comercio' : '/comercio/entrar'
  if (s.fase === 'fuera') return ruta === '/comercio/entrar' ? null : '/comercio/entrar'
  if (s.fase === 'dentro' && ruta === '/comercio/entrar') return s.destino ?? '/comercio'
  return null
}

function Rutas() {
  const s = useComercio()
  const ruta = useRuta()
  const destino = s.fase === 'cargando' || s.fase === 'error' || s.fase === 'inactiva' ? null : redireccion(ruta, s)

  useEffect(() => {
    if (!destino) return
    // 2.1: la ruta pedida sin haber entrado se guarda en memoria (sin la parte elegida).
    if (s.fase === 'fuera' && destino === '/comercio/entrar' && esRutaComercio(ruta) && ruta !== '/comercio/entrar')
      s.fijar({ destino: ruta === '/comercio/pedido' ? '/comercio' : ruta })
    navegar(destino, { reemplazar: true })
  }, [destino, ruta, s])

  // 2.1: el `<title>` de cada ruta. El de un pedido lleva la referencia, nunca la URL.
  const nombre = s.comercio?.nombre_fantasia
  useLayoutEffect(() => {
    if (ruta === '/comercio/entrar' || s.fase !== 'dentro') document.title = TITULO_COMERCIO.entrar
    else if (ruta === '/comercio/productos') document.title = nombre ? TITULO_COMERCIO.productos(nombre) : TITULO_COMERCIO.sinNombre
    else if (ruta === '/comercio') document.title = nombre ? TITULO_COMERCIO.pedidos(nombre) : TITULO_COMERCIO.sinNombre
  }, [ruta, nombre, s.fase])

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
        <Titulo className="text-3xl">{MARCO_COMERCIO.consola}</Titulo>
        <Nota tono="pronto" rol="alert" icono={<WifiOff aria-hidden className="mt-0.5 size-5 shrink-0 text-pronto" />}>
          {GENERAL.errorAlCargar}
        </Nota>
        <Boton variante="secundario" className="self-start" onClick={() => void s.cargar()}>
          {PEDIDOS.volverAIntentar}
        </Boton>
      </MarcoEntrar>
    )
  // 5.7: la cuenta o el comercio dejaron de estar activos: la nota, sin pestañas, con «Salir».
  if (s.fase === 'inactiva')
    return (
      <MarcoComercio pestanas={false}>
        <div className="flex max-w-prose flex-col gap-4">
          <Titulo className="text-3xl">{MARCO_COMERCIO.consola}</Titulo>
          <Nota tono="atenta" rol="status" titulo={ENTRAR_COMERCIO.inactivaTitulo}>
            <span className="break-words">{ENTRAR_COMERCIO.inactivaTexto(s.contacto)}</span>
          </Nota>
        </div>
      </MarcoComercio>
    )
  if (destino) return null
  if (ruta === '/comercio/entrar') return <EntrarComercio />

  return (
    <MarcoComercio>
      {ruta === '/comercio/productos' ? (
        <div key="productos" className="animate-aparecer">
          <PantallaProductos />
        </div>
      ) : (
        // Las dos rutas de los pedidos son una sola pantalla: la lista se conserva al elegir una parte.
        <div key="pedidos" className="animate-aparecer">
          <PantallaPedidos ruta={ruta === '/comercio/pedido' ? '/comercio/pedido' : '/comercio'} />
        </div>
      )}
    </MarcoComercio>
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
