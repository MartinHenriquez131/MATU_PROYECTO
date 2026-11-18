// El pago del pedido (especificación MATU-81, sección 7): si lo cobrado y lo devuelto calzan con el
// total confirmado, sin nada de la tarjeta (C18). Es lectura (C19): las cifras salen tal cual de la
// API, también «Queda cobrado»; la pantalla no suma ni resta. La orden de compra se puede seleccionar
// para buscarla en el portal de Transbank, y nunca va en la URL, el título ni un anuncio.
import type { CobroPedido, TipoIncidencia } from '../compartido/api/operacion'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { enChile, EtiquetaAnulacion, EtiquetaVenta, Monto } from './comun'
import { MARCO, MOTIVO_ANULACION, PAGO as T } from './textos'

/** El signo menos de las devoluciones (U+2212). */
const MENOS = String.fromCharCode(0x2212)
const FILA = 'grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 angosto:grid-cols-1'

export function Pago({
  cobro,
  fallo,
  onReintentar,
  onAnotar,
}: {
  cobro: CobroPedido | null
  fallo: boolean
  onReintentar: () => void
  /** «Anotar una incidencia» con el tipo ya elegido. Sin él (un formulario abierto), no se ofrece. */
  onAnotar?: (tipo: TipoIncidencia) => void
}) {
  return (
    <section aria-labelledby="pago-titulo" className="flex flex-col gap-3">
      <h2 id="pago-titulo" className="text-xl font-bold">
        {T.titulo}
      </h2>
      {fallo ? (
        <div className="flex flex-col items-start gap-3">
          <Nota tono="pronto" rol="alert">
            {T.error}
          </Nota>
          <Boton variante="secundario" onClick={onReintentar}>
            {MARCO.volverAIntentar}
          </Boton>
        </div>
      ) : !cobro ? (
        <p className="text-tenue">{T.cargando}</p>
      ) : (
        <Cifras cobro={cobro} onAnotar={onAnotar} />
      )}
    </section>
  )
}

function Cifras({ cobro, onAnotar }: { cobro: CobroPedido; onAnotar?: (tipo: TipoIncidencia) => void }) {
  const sinTerminar = cobro.anulaciones.some((a) => a.estado === 'rechazada')
  const revisar = !cobro.calza || sinTerminar
  const venta = [...cobro.ventas].sort((a, b) => new Date(b.creada_en).getTime() - new Date(a.creada_en).getTime())[0]
  const hayCobro = cobro.cobrado > 0 || cobro.ventas.some((v) => v.estado === 'aprobada')
  return (
    <>
      {revisar && (
        <div className="flex flex-col items-start gap-1">
          <Nota tono="atenta" borde titulo={T.revisionTitulo}>
            {T.revisionTexto}
          </Nota>
          {onAnotar && (
            <Boton variante="texto" onClick={() => onAnotar(sinTerminar ? 'devolucion_pendiente' : 'cobro_sin_respuesta')}>
              {T.anotar}
            </Boton>
          )}
        </div>
      )}
      <dl className="flex w-full flex-col gap-1">
        <div className={FILA}>
          <dt>{T.totalConfirmado}</dt>
          <dd className="text-right angosto:text-left">
            <Monto n={cobro.total_confirmado} />
          </dd>
        </div>
        <div className={FILA}>
          <dt>{T.cobrado}</dt>
          <dd className="text-right angosto:text-left">{hayCobro ? <Monto n={cobro.cobrado} /> : T.nadaTodavia}</dd>
        </div>
        <div className={FILA}>
          <dt>{T.devuelto}</dt>
          <dd className="text-right angosto:text-left">{cobro.devuelto > 0 ? <Monto n={cobro.devuelto} signo={MENOS} /> : <Monto n={0} />}</dd>
        </div>
        <div className={`${FILA} mt-1 border-t-2 border-tinta pt-2 text-lg font-bold`}>
          <dt>{T.quedaCobrado}</dt>
          <dd className="text-right angosto:text-left">
            <Monto n={cobro.queda_cobrado} />
          </dd>
        </div>
      </dl>
      {venta && (
        <dl className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <dt>{T.venta}</dt>
            <dd>
              <EtiquetaVenta estado={venta.estado} />
            </dd>
          </div>
          <div className="flex flex-col">
            <dt>{T.ordenDeCompra}</dt>
            <dd className="digitos break-words select-text">{venta.buy_order}</dd>
          </div>
        </dl>
      )}
      {cobro.anulaciones.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="font-bold">{T.devoluciones}</h3>
          <ul className="flex flex-col divide-y divide-linea">
            {cobro.anulaciones.map((a) => {
              const { dia, hora } = enChile(a.en)
              return (
                <li key={a.id} className="flex flex-col gap-1 py-2">
                  <span className={`${FILA} font-bold`}>
                    <span className="min-w-0 break-words">{MOTIVO_ANULACION[a.motivo]}</span>
                    <span className="text-right angosto:text-left">
                      <Monto n={a.monto} />
                    </span>
                  </span>
                  <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <EtiquetaAnulacion estado={a.estado} />
                    <span className="cifras whitespace-normal text-tenue">{`${dia} ${hora}`}</span>
                  </span>
                  {a.producto && <span className="text-base text-tenue break-words">{a.producto}</span>}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </>
  )
}
