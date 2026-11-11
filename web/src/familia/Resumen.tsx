// «Antes de pagar» (MATU-61, especificación 9, C1, C15, C23 y C25): el total confirmado y hasta qué
// hora vale, lo que cambió desde el pedido, los productos con su retracto, la entrega, qué pasa si
// falta algo, quién vende y reclamos, las condiciones y su casilla, y la salida sin costo.
//
// - El total vale lo que dice el servidor: la hora sale de `vence_en` y el aviso de los 2 minutos de
//   `vigencia_segundos`, contados desde que llegó la respuesta. Nunca el reloj del teléfono solo.
// - Nada cuenta hacia atrás: el aviso llega una vez y el texto no cambia cada segundo.
// - «Pagar» es de MATU-62: su lugar queda vacío y no se dibuja un botón que no paga (9.9).
import { useEffect, useRef, useState } from 'react'
import { ArrowDownUp, Clock, CloudOff, FileText, PackageX, ReceiptText, RefreshCw, Store } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { cambiarContacto, confirmarPedido, volverABorrador, type LineaPedido, type PedidoVista } from '../compartido/api/pedido'
import { esVencida } from '../compartido/api/sesion'
import { anunciar } from '../compartido/ui/Anuncios'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { Boton } from '../compartido/ui/Boton'
import { enfocar, esTipo } from './insumosComun'
import { PestanasInsumos } from './Insumos'
import { direccionEnTexto, hayCambios, huellaDelTotal } from './pedidoComun'
import { AvisoPiloto, DialogoCancelar, horaDeVencimiento, Retracto, siFaltaTexto, TelefonoContacto } from './PiezasPedido'
import { navegar } from './ruteo'
import { GENERAL } from './textos'
import { pesos } from './textosCatalogo'
import { PEDIDO } from './textosPedido'
import { Etiqueta, MensajeError, Nota, Titulo, Volver } from './ui'

/** La página de las condiciones, pública, que se abre en otra pestaña (9.8, O6). */
export const RUTA_CONDICIONES = '/condiciones-pedido'

const ID_AVISO_PLAZO = 'aviso-plazo'
const ID_CASILLA = 'casilla-condiciones'
const ID_ENLACE_CONDICIONES = 'enlace-condiciones'
const ID_CANCELAR = 'cancelar-pedido'

export function Resumen({
  pedido,
  editor,
  acepto,
  onAcepto,
  error,
  onError,
  onPedido,
  manejar,
  onCambiado,
  onCancelado,
  onCambiarDireccion,
}: {
  pedido: PedidoVista
  editor: boolean
  acepto: boolean
  onAcepto: (v: boolean) => void
  /** El error de volver a confirmar (también el de 8.6, al volver de la dirección). */
  error: 'red' | 'nada' | null
  onError: (e: 'red' | 'nada' | null) => void
  onPedido: (p: PedidoVista) => void
  manejar: (x: unknown) => boolean
  onCambiado: (p: PedidoVista) => void
  onCancelado: (yaCancelado: boolean) => void
  onCambiarDireccion: () => void
}) {
  const [avisoDos, setAvisoDos] = useState(false)
  const [vencioAqui, setVencioAqui] = useState(false)
  const [confirmando, setConfirmando] = useState(false)
  const [cambiando, setCambiando] = useState(false)
  const [errCambiar, setErrCambiar] = useState(false)
  const [cancelando, setCancelando] = useState(false)

  // 9.5 y 9.6: desde la respuesta, los segundos que quedan según el servidor. Un temporizador para el
  // aviso a los 120 s y otro para el vencimiento; se rehacen con cada pedido nuevo.
  useEffect(() => {
    setAvisoDos(false)
    setVencioAqui(false)
    if (pedido.estado !== 'total_confirmado' || pedido.vigencia_segundos === null) return
    const quedan = Math.max(0, pedido.vigencia_segundos)
    const aviso = window.setTimeout(() => setAvisoDos(true), Math.max(0, quedan - 120) * 1000)
    const vence = window.setTimeout(() => setVencioAqui(true), quedan * 1000)
    return () => {
      window.clearTimeout(aviso)
      window.clearTimeout(vence)
    }
  }, [pedido])

  const vencido = pedido.estado === 'vencido' || vencioAqui

  // 9.6: si el foco estaba en lo que desaparece (la casilla o el enlace), pasa al aviso. Si no, no se mueve.
  const antes = useRef(vencido)
  useEffect(() => {
    if (vencido && !antes.current) {
      const activo = document.activeElement?.id
      if (activo === ID_CASILLA || activo === ID_ENLACE_CONDICIONES) enfocar(ID_AVISO_PLAZO, 0)
    }
    antes.current = vencido
  }, [vencido])

  /** «Volver a confirmar»: el mismo pedido, sin cancelar ni volver a `borrador` (C1, 9.5 y 9.6). */
  const confirmarDeNuevo = async () => {
    if (confirmando) return
    setConfirmando(true)
    onError(null)
    const huella = huellaDelTotal(pedido)
    try {
      const nuevo = await confirmarPedido(pedido.id, null)
      const cambio = huellaDelTotal(nuevo) !== huella
      if (cambio) onAcepto(false)
      onPedido(nuevo)
      anunciar(cambio ? `${PEDIDO.confirmamosDeNuevo(horaDeVencimiento(nuevo))} ${PEDIDO.revisaLoQueCambio}` : PEDIDO.confirmamosDeNuevo(horaDeVencimiento(nuevo)), 'status')
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 409 && esTipo(f.tipo, 'nada-disponible')) return onError('nada')
      if (manejar(x)) return
      onError('red')
    } finally {
      setConfirmando(false)
    }
  }

  /** 9.12: vuelve a `borrador` con las mismas líneas, reglas y dirección. Sin confirmación. */
  const cambiar = async () => {
    if (cambiando) return
    setCambiando(true)
    setErrCambiar(false)
    try {
      onCambiado(await volverABorrador(pedido.id))
    } catch (x) {
      if (!manejar(x)) setErrCambiar(true)
    } finally {
      setCambiando(false)
    }
  }

  const guardarTelefono = async (t: string): Promise<string | null> => {
    try {
      onPedido(await cambiarContacto(pedido.id, t, pedido.etag))
      return null
    } catch (x) {
      if (esVencida(x)) return null
      const f = leerFallo(x)
      if (f.status === 422) return PEDIDO.errTelefono
      if (manejar(x)) return null
      return GENERAL.error
    }
  }

  const hora = horaDeVencimiento(pedido)
  const total = pedido.total ?? 0
  const r = pedido.resumen
  const entrega = pedido.entrega

  // ---------------------------------------------------------------- la parte de lectura

  const cambios = hayCambios(pedido) && (
    <Nota tono="rocio" rol="status" titulo={PEDIDO.cambiosTitulo} icono={<RefreshCw aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />} iconoEnLinea>
      <ul className="flex list-disc flex-col gap-1 ps-5 marker:text-tenue">
        {pedido.salieron.map((s) => (
          <li key={`salio-${s.producto.id}`}>{PEDIDO.salio(s.producto.nombre)}</li>
        ))}
        {pedido.lineas.flatMap((l) => {
          const c = l.cambio
          if (!c) return []
          const items = []
          if (c.comercio_antes)
            items.push(<li key={`comercio-${l.producto.id}`}>{PEDIDO.ahoraLoPrepara(l.producto.nombre, l.comercio.nombre_fantasia, l.comercio.ficticio)}</li>)
          if (c.precio_antes !== null)
            items.push(
              <li key={`precio-${l.producto.id}`}>
                {PEDIDO.cambioPrecioAntes(l.producto.nombre)} <span className="cifras">{pesos(c.precio_antes)}</span>, {PEDIDO.ahora}{' '}
                <span className="cifras">{pesos(l.precio_unitario)}</span>.
              </li>,
            )
          return items
        })}
      </ul>
    </Nota>
  )

  const lectura = (
    <div className="flex min-w-0 flex-col gap-8">
      {cambios}
      <section aria-labelledby="productos-t" className="flex flex-col gap-4">
        <h2 id="productos-t" className="titular text-2xl">
          {PEDIDO.productosTitulo}
        </h2>
        <ul className="flex flex-col gap-3">
          {pedido.lineas.map((l) => (
            <LineaResumen key={l.producto.id} linea={l} />
          ))}
        </ul>
        {editor && (
          <div className="mt-4 flex flex-col items-start gap-3">
            <p id="cambiar-frase" className="max-w-prose text-base text-tenue">
              {PEDIDO.cambiarFrase}
            </p>
            <Boton variante="secundario" aria-describedby="cambiar-frase" ocupado={cambiando} textoOcupado={PEDIDO.abriendo} onClick={() => void cambiar()}>
              {PEDIDO.cambiarPedido}
            </Boton>
            {errCambiar && <MensajeError>{PEDIDO.errCambiar}</MensajeError>}
          </div>
        )}
      </section>
      <section aria-labelledby="entrega-t" className="flex flex-col items-start gap-2">
        <h2 id="entrega-t" className="titular text-2xl">
          {PEDIDO.entrega}
        </h2>
        <p className="text-base">{PEDIDO.entregaVentana(r?.ventana_entrega ?? pedido.ventana_entrega)}</p>
        {entrega && (
          <>
            <p className="text-base break-words">{direccionEnTexto(entrega)}</p>
            {entrega.referencia && <p className="text-base text-tenue break-words">{entrega.referencia}</p>}
            {editor && (
              <Boton variante="texto" onClick={onCambiarDireccion}>
                {PEDIDO.cambiarDireccion}
              </Boton>
            )}
            <TelefonoContacto
              key={`${pedido.etag}`}
              conPrefijo
              mostrado={entrega.telefono_contacto}
              esTuyo={entrega.telefono_es_tuyo}
              editable={editor}
              abiertoAlInicio={false}
              onGuardar={guardarTelefono}
            />
          </>
        )}
      </section>
      <section aria-labelledby="si-falta-t" className="flex flex-col gap-2">
        <h2 id="si-falta-t" className="titular text-2xl">
          {PEDIDO.siFaltaTitulo}
        </h2>
        <p className="max-w-prose text-base">{PEDIDO.siFaltaTexto}</p>
      </section>
      {r && (
        <section aria-labelledby="quien-vende-t" className="flex flex-col gap-2">
          <h2 id="quien-vende-t" className="titular text-2xl">
            {PEDIDO.quienVende}
          </h2>
          <p className="max-w-prose text-base">{PEDIDO.vende(r.vendedor, r.boleta)}</p>
          <p className="max-w-prose text-base">
            {PEDIDO.reclamosAntes}
            <EnlaceEnFrase href={`mailto:${r.canal_reclamo}`}>{r.canal_reclamo}</EnlaceEnFrase>.
          </p>
        </section>
      )}
    </div>
  )

  // ---------------------------------------------------------------- la parte de decisión

  const errorConfirmar =
    error === 'red' ? (
      <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
        {PEDIDO.errConfirmar}
      </Nota>
    ) : error === 'nada' ? (
      <Nota tono="atenta" rol="alert" icono={<PackageX aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
        {PEDIDO.nadaDisponible}
      </Nota>
    ) : null

  const decision = (
    <div className="flex min-w-0 flex-col items-stretch gap-5">
      <Boleta pedido={pedido} vencido={vencido} hora={hora} />
      {vencido ? (
        <>
          <Nota id={ID_AVISO_PLAZO} tono="atenta" borde rol="status" enfocable icono={<Clock aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
            <p>{editor ? PEDIDO.vencido : PEDIDO.vencidoPagador}</p>
          </Nota>
          {errorConfirmar}
          {editor && (
            <Boton className="self-start" ocupado={confirmando} textoOcupado={PEDIDO.confirmando} onClick={() => void confirmarDeNuevo()}>
              {PEDIDO.volverAConfirmar}
            </Boton>
          )}
        </>
      ) : (
        <>
          {avisoDos && (
            <Nota id={ID_AVISO_PLAZO} tono="atenta" rol="status" enfocable icono={<Clock aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
              <p>{PEDIDO.quedan2}</p>
              {editor && (
                <Boton variante="secundario" className="mt-3" ocupado={confirmando} textoOcupado={PEDIDO.confirmando} onClick={() => void confirmarDeNuevo()}>
                  {PEDIDO.volverAConfirmar}
                </Boton>
              )}
            </Nota>
          )}
          {errorConfirmar}
          <a
            id={ID_ENLACE_CONDICIONES}
            href={RUTA_CONDICIONES}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-12 items-start gap-2 self-start py-3 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa"
          >
            <FileText aria-hidden className="mt-0.5 size-5 shrink-0" />
            {PEDIDO.condiciones}
          </a>
          <label className="flex min-h-12 cursor-pointer items-center angosto:items-start gap-3 font-bold">
            <input id={ID_CASILLA} type="checkbox" checked={acepto} onChange={(e) => onAcepto(e.target.checked)} className="size-6 shrink-0 accent-turquesa angosto:mt-0.5" />
            {PEDIDO.acepto}
          </label>
          {/* 9.9: aquí va «Pagar {total}» (MATU-62). No se dibuja un botón que no paga. */}
        </>
      )}
      {confirmando && (
        <p role="status" className="text-base">
          {PEDIDO.confirmandoEstado}
        </p>
      )}
      <p className="text-base">{PEDIDO.noPagar}</p>
      {editor && (
        <Boton id={ID_CANCELAR} variante="textoPeligro" className="self-start" onClick={() => setCancelando(true)}>
          {PEDIDO.cancelarPedido}
        </Boton>
      )}
    </div>
  )

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <PestanasInsumos activa="/insumos/pedido" />
      <Volver onClick={() => navegar('/insumos/pedido')}>{PEDIDO.volverATuPedido}</Volver>
      <div>
        <Titulo className="text-3xl @2xl/main:text-5xl">{PEDIDO.resTitulo}</Titulo>
        <p className="mt-1.5 max-w-prose text-lg">
          {PEDIDO.resBajada} <span className="cifras font-bold">{pesos(total)}</span>.
        </p>
      </div>
      {pedido.precios_de_ejemplo && <AvisoPiloto />}
      <div className="mt-4 grid grid-cols-1 gap-x-10 gap-y-10 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {lectura}
        <div className="min-w-0 @3xl/main:sticky @3xl/main:top-6 @3xl/main:max-h-[calc(100dvh-3rem)] @3xl/main:self-start @3xl/main:overflow-y-auto [scrollbar-width:thin]">
          {decision}
        </div>
      </div>
      {cancelando && (
        <DialogoCancelar
          pedidoId={pedido.id}
          onCerrar={() => {
            setCancelando(false)
            enfocar(ID_CANCELAR, 0)
          }}
          onCancelado={(ya) => {
            setCancelando(false)
            onCancelado(ya)
          }}
          manejar={manejar}
        />
      )}
    </div>
  )
}

/** 9.3: cada producto con su cantidad, precio, subtotal, si cambió, «Si falta» y el retracto. */
function LineaResumen({ linea: l }: { linea: LineaPedido }) {
  const precio = l.cambio?.precio_antes !== null && l.cambio?.precio_antes !== undefined
  const comercio = !!l.cambio?.comercio_antes
  return (
    <li className="flex flex-col gap-1.5 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
      <h3 className="text-xl font-bold break-words">{l.producto.nombre}</h3>
      <p className="text-base break-words">{PEDIDO.comercio(l.comercio.nombre_fantasia, l.comercio.ficticio)}</p>
      <p className="text-lg tabular-nums">
        <span className="cifras">{l.cantidad}</span> × <span className="cifras">{pesos(l.precio_unitario)}</span>
      </p>
      <p className="text-lg">
        {PEDIDO.subtotal} <span className="cifras font-bold">{pesos(l.subtotal)}</span>
      </p>
      {(precio || comercio) && (
        <span className="flex flex-wrap gap-2">
          {precio && (
            <Etiqueta tono="atenta">
              <ArrowDownUp aria-hidden className="size-4 shrink-0" />
              {PEDIDO.cambioPrecio}
            </Etiqueta>
          )}
          {comercio && (
            <Etiqueta tono="atenta">
              <Store aria-hidden className="size-4 shrink-0" />
              {PEDIDO.otroComercioEtiqueta}
            </Etiqueta>
          )}
        </span>
      )}
      <p className="text-base">{siFaltaTexto(l.regla_faltante)}</p>
      <Retracto pierde={l.retracto_pierde_al_abrir} />
    </li>
  )
}

/**
 * 9.4: la boleta de la demo, solo con dinero exacto. En pantalla su título es «Tu pedido», nunca
 * «Boleta» (en este piloto no se emite boleta). La máscara del borde cortado es geometría.
 */
function Boleta({ pedido, vencido, hora }: { pedido: PedidoVista; vencido: boolean; hora: string }) {
  const renglon = 'flex justify-between gap-4 angosto:flex-col angosto:items-start angosto:gap-0'
  const n = pedido.lineas.length
  return (
    <section
      aria-labelledby="boleta-t"
      className="relative rounded-t-lg bg-hoja px-4 angosto:px-2 @3xl/main:px-7 pt-5 pb-8 ring-1 ring-linea [mask:radial-gradient(circle_at_50%_100%,transparent_0.42rem,var(--color-tinta)_0.45rem)_bottom/1.1rem_100%_repeat-x]"
    >
      <h2 id="boleta-t" className="mb-4 flex items-center gap-2 text-xl font-bold">
        <ReceiptText aria-hidden className="size-5 shrink-0 text-turquesa" />
        {PEDIDO.boletaTitulo}
      </h2>
      <div className="flex flex-col gap-3">
        <p className={`${renglon} text-lg`}>
          <span>{PEDIDO.productosN(n)}</span>
          <span className="cifras">{pesos(pedido.subtotal_productos)}</span>
        </p>
        <p className={`${renglon} text-lg`}>
          <span>{PEDIDO.envio}</span>
          <span className="cifras">{pesos(pedido.costo_envio)}</span>
        </p>
        <hr className="border-0 border-t-2 border-tinta" />
        <p className={`${renglon} text-2xl font-bold`}>
          <span>{PEDIDO.total}</span>
          <span className="cifras">{pesos(pedido.total ?? 0)}</span>
        </p>
        {vencido && (
          <span>
            <Etiqueta tono="atenta">
              <Clock aria-hidden className="size-4 shrink-0" />
              {PEDIDO.vencio}
            </Etiqueta>
          </span>
        )}
        <p className="text-base">
          {vencido ? PEDIDO.vencioALas : PEDIDO.valeHasta} <span className="cifras">{hora}</span>.
        </p>
        {!vencido && <p className="text-base">{PEDIDO.cobro}</p>}
      </div>
    </section>
  )
}

