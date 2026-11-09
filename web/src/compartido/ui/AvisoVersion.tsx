// MATU-67: el aviso de versión nueva (especificación docs/diseno/matu-67-aviso-version.md, secciones
// 3 y 4), el mismo en la app de la familia y en el relevo. Tiene la apariencia de `Nota` (`rocio`
// con borde e ícono en línea en modo angosto), va en el flujo de la página y nunca recarga sola.
//
// - No toma el foco y se anuncia una sola vez por la región `status`, aunque cambie de pantalla.
// - Espera para aparecer con el foco en un campo de texto y donde el marco lo pide (`esperar`).
// - «Recargar» es secundario. Si el formulario a la vista tiene algo sin guardar, no recarga: el
//   aviso pasa a `atenta`, se anuncia por `alert` y el foco va a «Seguir escribiendo».
// - «Más tarde» lo retira; vuelve en la próxima revisión, nunca antes de 15 minutos (D4).
import { useEffect, useReducer, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { AVISO_VERSION } from '../textosVersion'
import { marcarAnunciado, mostrarAviso, navegador, posponerAviso, useFaseVersion, yaAnunciado, type FuenteSinGuardar, type SinGuardar } from '../version'
import { anunciar, retirar } from './Anuncios'
import { Boton } from './Boton'
import { Nota } from './Nota'

const TIPOS_DE_TEXTO = new Set(['text', 'email', 'tel', 'number', 'password', 'search', 'url'])

/** 4.2, caso 1: el foco está en un campo donde se escribe. */
export function esCampoDeTexto(el: Element | null): boolean {
  if (el instanceof HTMLTextAreaElement) return true
  if (el instanceof HTMLInputElement) return TIPOS_DE_TEXTO.has(el.type)
  return el instanceof HTMLElement && el.isContentEditable
}

/** El foco a un elemento por su id, o al título de la página, o al contenido. Nunca al `body`. */
function enfocar(id?: string | null) {
  const el = (id && document.getElementById(id)) || document.getElementById('titulo-pagina') || document.getElementById('contenido')
  el?.focus()
}

const ACCIONES = 'mt-3 flex flex-wrap items-center gap-x-5 gap-y-3'

export function AvisoVersion({
  bajada,
  esperar = false,
  sinGuardar,
  className = '',
}: {
  bajada: string
  /** 4.2, casos 2 y 3: la pantalla retiene algo que una recarga borra. */
  esperar?: boolean
  /** Solo la familia: lo que el formulario a la vista tiene sin guardar (4.3). */
  sinGuardar?: FuenteSinGuardar
  className?: string
}) {
  const fase = useFaseVersion()
  const [, refrescar] = useReducer((n: number) => n + 1, 0)
  const [perdible, setPerdible] = useState<SinGuardar | null>(null)
  const [recargando, setRecargando] = useState(false)
  const seguir = useRef<HTMLButtonElement>(null)
  const caja = useRef<HTMLDivElement>(null)
  // Solo se funde al aparecer por primera vez: al cambiar de pantalla, ya estaba.
  const [nuevo] = useState(() => !yaAnunciado())

  const texto = `${AVISO_VERSION.titulo} ${bajada}`
  const tituloPerdible = perdible?.titulo || (perdible?.donde ? AVISO_VERSION.sinGuardarEn(perdible.donde) : AVISO_VERSION.sinGuardar)
  const textoPerdible = `${tituloPerdible} ${AVISO_VERSION.sinGuardarBajada}`
  const aLaVista = fase === 'visible' && !esperar

  // Mientras espera, cada cambio de foco vuelve a mirar si ya puede aparecer. Al salir de un campo
  // el foco pasa un instante por el `body`: se mira después, donde quedó.
  useEffect(() => {
    if (fase !== 'pendiente') return
    let reloj: number | undefined
    const alEntrar = () => refrescar()
    const alSalir = () => {
      window.clearTimeout(reloj)
      reloj = window.setTimeout(refrescar, 0)
    }
    document.addEventListener('focusin', alEntrar)
    document.addEventListener('focusout', alSalir)
    return () => {
      window.clearTimeout(reloj)
      document.removeEventListener('focusin', alEntrar)
      document.removeEventListener('focusout', alSalir)
    }
  }, [fase])

  useEffect(() => {
    if (fase === 'pendiente' && !esperar && !esCampoDeTexto(document.activeElement)) mostrarAviso()
  })

  // 4.1: se anuncia una vez, cuando aparece. Los botones no se leen.
  useEffect(() => {
    if (!aLaVista || yaAnunciado()) return
    marcarAnunciado()
    anunciar(texto, 'status')
  }, [aLaVista, texto])

  // 4.3: el estado «sin guardar» se anuncia como urgente. La pantalla baja hasta el borde de arriba
  // de la caja (inmediato con movimiento reducido) y después el foco va a «Seguir escribiendo», sin
  // volver a desplazar (revisión visual del 09-11).
  useEffect(() => {
    if (!perdible) return
    anunciar(textoPerdible, 'alert')
    const reducido = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    caja.current?.scrollIntoView?.({ block: 'start', behavior: reducido ? 'instant' : 'smooth' })
    seguir.current?.focus({ preventScroll: true })
    return () => retirar(textoPerdible)
  }, [perdible, textoPerdible])

  if (!aLaVista) return null

  const recargar = () => {
    setRecargando(true)
    navegador.recargar()
  }

  const alRecargar = () => {
    const s = sinGuardar?.() ?? null
    if (s) return setPerdible(s)
    recargar()
  }

  const masTarde = () => {
    retirar(texto)
    enfocar()
    posponerAviso()
  }

  const seguirEscribiendo = () => {
    const foco = perdible?.foco
    setPerdible(null)
    enfocar(foco)
  }

  return (
    <div ref={caja} data-aviso-version className={className}>
      {perdible ? (
        <Nota tono="atenta" borde iconoEnLinea titulo={tituloPerdible}>
          <p>{AVISO_VERSION.sinGuardarBajada}</p>
          <div className={ACCIONES}>
            <Boton ref={seguir} variante="secundario" onClick={seguirEscribiendo}>
              {AVISO_VERSION.seguirEscribiendo}
            </Boton>
            <Boton variante="textoPeligro" ocupado={recargando} textoOcupado={AVISO_VERSION.recargando} onClick={recargar}>
              {AVISO_VERSION.recargarIgual}
            </Boton>
          </div>
        </Nota>
      ) : (
        <Nota
          tono="rocio"
          borde
          iconoEnLinea
          icono={<RefreshCw aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}
          titulo={AVISO_VERSION.titulo}
          className={nuevo ? 'animate-aparecer' : ''}
        >
          <p>{bajada}</p>
          <div className={ACCIONES}>
            <Boton variante="secundario" ocupado={recargando} textoOcupado={AVISO_VERSION.recargando} onClick={alRecargar}>
              {AVISO_VERSION.recargar}
            </Boton>
            <Boton variante="texto" onClick={masTarde}>
              {AVISO_VERSION.masTarde}
            </Boton>
          </div>
        </Nota>
      )}
    </div>
  )
}
