// Consola de Farmacia Los Aromos: la cola de pedidos del día a la izquierda y el pedido elegido a
// la derecha, con sus tres pasos. Ve el nombre de pila, nunca la dirección ni nada de la ficha.
import { useState, type ReactNode } from 'react'
import { Check, CircleCheck, PackageCheck, Store } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { avisar, cerrarMonto, empezarPreparacion, etapa, ir, marcarEntregado, nombrePila, pantallaComercio, pilaComercio, resolverLinea, validarCodigo } from '../demo/logica'
import { BOLETA_EJEMPLO, COMERCIO, EQUIVALENTES, MONTO_REAL_EJEMPLO } from '../demo/datos'
import { TOPE_EQUIVALENTE_PORCENTAJE, diaDeLaSemana, fmtDinero, fmtFecha, fmtHora, leerPesos, topeEquivalente } from '../demo/calculos'
import type { Estado, Pedido } from '../demo/tipos'
import { Acciones, Boton, CampoTexto, Etiqueta, Nota, type Tono } from '../components/Ui'

const tope = (p: Pedido) => p.montoPagado

const ESTADO: Record<string, { texto: string; tono: Tono; forma: string }> = {
  pagado: { texto: 'Por preparar', tono: 'pronto', forma: 'bg-current' },
  preparando: { texto: 'Preparando', tono: 'atenta', forma: 'grid place-items-center border-2 border-current' },
  listo: { texto: 'Listo para retiro', tono: 'ok', forma: 'border-2 border-current' },
  en_camino: { texto: 'Retirado', tono: 'neutro', forma: 'border-2 border-current' },
  entregado: { texto: 'Entregado', tono: 'neutro', forma: 'border-2 border-current' },
}

function ChipEstado({ e }: { e: keyof typeof ESTADO }) {
  const x = ESTADO[e]
  return (
    <Etiqueta tono={x.tono}>
      <span aria-hidden className={`size-2.5 rounded-full ${x.forma}`}>{e === 'preparando' && <span className="size-0.5 rounded-full bg-current" />}</span>
      {x.texto}
    </Etiqueta>
  )
}

const pedidoPagado = (s: Estado) => (s.pedido && etapa(s.pedido.estado) >= etapa('pagado') ? s.pedido : null)

// ---------- marco ----------

function Cola() {
  const { s, haz } = useDemo()
  const p = pedidoPagado(s)
  const abrir = () => {
    if (!p) return
    if (p.estado === 'pagado') haz((x) => pilaComercio(x, ['c-pedidos']))
    else if (p.estado === 'preparando') haz((x) => pilaComercio(x, ['c-pedidos', 'c-preparar']))
    else haz((x) => pilaComercio(x, ['c-pedidos', 'c-codigo']))
  }
  const fila = 'flex w-full flex-col gap-1 border-l-4 px-4 py-3 text-left'
  return (
    <section aria-labelledby="cola-t" className="flex flex-col gap-3">
      <h1 id="titulo-pagina" tabIndex={-1} className="titular text-3xl outline-none">
        Pedidos de hoy
      </h1>
      <ul className="flex flex-col gap-2" id="cola-t" aria-label="Pedidos de hoy">
        {p && (
          <li>
            <button type="button" onClick={abrir} aria-current="true" className={`${fila} border-pino bg-hoja ring-2 ring-pino ring-inset`}>
              <span className="flex flex-wrap items-center justify-between gap-2">
                <span className="cifras font-bold">#{p.numero}</span>
                <ChipEstado e={p.estado} />
              </span>
              <span className="text-base">
                Para {nombrePila(s)}, {p.lineas.reduce((n, l) => n + l.paquetes, 0)} paquetes
              </span>
              <span className="text-sm text-tenue">Retiro {COMERCIO.ventana}</span>
            </button>
          </li>
        )}
        <li className={`${fila} border-transparent bg-hoja/60`}>
          <span className="flex flex-wrap items-center justify-between gap-2">
            <span className="cifras font-bold">#4822</span>
            <ChipEstado e="preparando" />
          </span>
          <span className="text-base">3 paquetes</span>
          <span className="text-sm text-tenue">Retiro entre 18:00 y 19:00</span>
        </li>
        <li className={`${fila} border-transparent bg-hoja/60`}>
          <span className="flex flex-wrap items-center justify-between gap-2">
            <span className="cifras font-bold">#4819</span>
            <ChipEstado e="en_camino" />
          </span>
          <span className="text-base">4 paquetes</span>
          <span className="cifras text-sm text-tenue">Retirado a las 13:20</span>
        </li>
      </ul>
      {!p && <p className="text-tenue">El pedido de {nombrePila(s)} aparece aquí cuando la familia lo paga.</p>}
    </section>
  )
}

const PASOS = ['Preparar', 'Monto real', 'Retiro']

function Pasos({ paso }: { paso: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2" aria-label="Pasos del pedido">
      {PASOS.map((t, i) => {
        const n = i + 1
        const estado = n < paso ? 'hecho' : n === paso ? 'ahora' : 'falta'
        return (
          <li key={t} className="flex items-center gap-2" aria-current={estado === 'ahora' ? 'step' : undefined}>
            {i > 0 && <span aria-hidden className={`h-0.5 w-6 ${n <= paso ? 'bg-pino' : 'bg-tinta/15'}`} />}
            <span
              aria-hidden
              className={`grid size-8 place-items-center rounded-full text-sm font-bold ${
                estado === 'hecho' ? 'bg-pino text-papel' : estado === 'ahora' ? 'text-pino ring-3 ring-pino ring-inset' : 'text-tenue ring-2 ring-tinta/20 ring-inset'
              }`}
            >
              {estado === 'hecho' ? <Check className="size-4.5" strokeWidth={3} /> : n}
            </span>
            <span className={estado === 'ahora' ? 'font-bold' : estado === 'falta' ? 'text-tenue' : ''}>
              {t}
              {estado === 'hecho' && <span className="sr-only">, hecho</span>}
              {estado === 'ahora' && <span className="sr-only">, ahora</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function Detalle({ paso, children }: { paso: number; children: ReactNode }) {
  const { s } = useDemo()
  const p = s.pedido!
  return (
    <section aria-labelledby="detalle-t" className="@container flex flex-col gap-5 bg-hoja px-4 @3xl:px-8 py-5 ring-1 ring-linea">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <h2 id="detalle-t" data-foco="detalle" tabIndex={-1} className="text-2xl font-bold outline-none">
            Pedido #{p.numero} para {nombrePila(s)}
          </h2>
          <p className="text-tenue">Retiro hoy {COMERCIO.ventana}</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-tenue">Tope autorizado</p>
          <p className="cifras text-2xl font-bold">{fmtDinero(tope(p))}</p>
        </div>
      </div>
      <Pasos paso={paso} />
      {children}
    </section>
  )
}

function Lineas({ editable = false }: { editable?: boolean }) {
  const { s, haz } = useDemo()
  const p = s.pedido!
  return (
    <ul className="flex flex-col divide-y divide-linea border-y border-linea">
      {p.lineas.map((l) => {
        const eq = EQUIVALENTES[l.insumoId]
        return (
          <li key={l.insumoId} className="flex flex-col gap-2 py-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <span className="min-w-0">
                <span className="block font-bold">
                  {l.nombre} <span className="cifras font-normal text-tenue">× {l.paquetes}</span>
                </span>
                {l.resolucion === 'reemplazado' && <span className="text-base text-tenue">Por: {l.reemplazo?.nombre}</span>}
                {l.resolucion === 'sin_stock' && (
                  <span className="text-base text-tenue">
                    {p.aceptaEquivalente ? `La familia acepta un equivalente hasta ${TOPE_EQUIVALENTE_PORCENTAJE}% más caro.` : 'La familia no acepta equivalentes.'}
                  </span>
                )}
              </span>
              {l.resolucion === 'ok' && (
                <Etiqueta tono="ok">
                  <Check aria-hidden className="size-4" strokeWidth={3} />
                  Listo
                </Etiqueta>
              )}
              {l.resolucion === 'sin_stock' && <Etiqueta tono="pronto">Sin stock</Etiqueta>}
              {l.resolucion === 'reemplazado' && <Etiqueta tono="atenta">Reemplazado</Etiqueta>}
              {l.resolucion === 'no_disponible' && <Etiqueta>No disponible, no se cobra</Etiqueta>}
            </div>
            {editable && l.resolucion === 'sin_stock' && (
              <Acciones>
                {p.aceptaEquivalente && eq && eq.precio <= topeEquivalente(l.precio) && (
                  <Boton onClick={() => haz((x) => resolverLinea(x, l.insumoId, 'reemplazado'))}>
                    Reemplazar por otra marca, <span className="cifras">{fmtDinero(eq.precio)}</span>
                  </Boton>
                )}
                <Boton variante="secundario" onClick={() => haz((x) => resolverLinea(x, l.insumoId, 'no_disponible'))}>
                  Marcar como no disponible
                </Boton>
              </Acciones>
            )}
          </li>
        )
      })}
    </ul>
  )
}

// ---------- pasos ----------

function Resumen() {
  const { s, haz } = useDemo()
  const p = pedidoPagado(s)
  if (!p) {
    return (
      <div className="flex flex-col items-start gap-3 bg-hoja px-6 py-6 ring-1 ring-linea">
        <h2 data-foco="detalle" tabIndex={-1} className="text-xl font-bold outline-none">
          Nada por preparar
        </h2>
        <p className="text-tenue">Cuando una familia paga un pedido, aparece en la cola con su tope autorizado.</p>
      </div>
    )
  }
  const paso = p.estado === 'pagado' || p.estado === 'preparando' ? 1 : p.estado === 'listo' ? 3 : 4
  return (
    <Detalle paso={paso}>
      <Lineas />
      {p.estado === 'entregado' ? (
        <Nota tono="ok" titulo={`Entregado a las ${fmtHora(p.hitos.entregado ?? s.ahora)}`}>
          Se cobraron {fmtDinero(p.montoReal ?? 0)}. La familia ya lo ve en su pedido.
        </Nota>
      ) : (
        <Acciones>
          {p.estado === 'pagado' && <Boton onClick={() => haz((x) => ir(empezarPreparacion(x), 'c-preparar'))}>Empezar a preparar</Boton>}
          {p.estado === 'preparando' && <Boton onClick={() => haz((x) => ir(x, 'c-preparar'))}>Seguir preparando</Boton>}
          {(p.estado === 'listo' || p.estado === 'en_camino') && <Boton onClick={() => haz((x) => ir(x, 'c-codigo'))}>Entregar el pedido</Boton>}
        </Acciones>
      )}
    </Detalle>
  )
}

function Preparar() {
  const { s, haz } = useDemo()
  const p = s.pedido!
  const pendientes = p.lineas.some((l) => l.resolucion === 'sin_stock')
  return (
    <Detalle paso={1}>
      <Lineas editable />
      <Acciones>
        <Boton disabled={pendientes} onClick={() => haz((x) => ir(x, 'c-monto'))}>
          Ingresar el monto real
        </Boton>
        {pendientes && <span className="text-tenue">Resuelve lo que falta para seguir.</span>}
      </Acciones>
      <p className="text-base text-tenue">Ves el nombre de pila de quien recibe. La dirección solo la ve quien entrega.</p>
    </Detalle>
  )
}

function Monto() {
  const { s, haz } = useDemo()
  const p = s.pedido!
  const max = tope(p)
  // El monto de la prueba real si cabe en el tope; si no (otro pedido), el tope mismo.
  const [monto, setMonto] = useState(fmtDinero(Math.min(MONTO_REAL_EJEMPLO, max)).slice(1))
  const [boleta, setBoleta] = useState(BOLETA_EJEMPLO)
  const [error, setError] = useState<string | null>(null)
  const cerrar = () => {
    const valor = leerPesos(monto)
    if (valor === null || valor === 0) return setError('Escribe el total en pesos, sin decimales.')
    if (valor > max) return setError(`Supera el tope autorizado de ${fmtDinero(max)}. Revisa la boleta o llama a la familia.`)
    haz((x) => {
      const t = pilaComercio(cerrarMonto(x, valor, boleta.trim()), ['c-pedidos'])
      const extra = p.medio === 'debito' ? ` A la familia se le devuelven ${fmtDinero(p.montoPagado - valor)}.` : ''
      return avisar(t, `Listo para retiro. Avisamos a la familia.${extra}`)
    })
  }
  return (
    <Detalle paso={2}>
      <form
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          cerrar()
        }}
      >
        <div className="grid gap-5 @xl:grid-cols-2">
          <CampoTexto
            etiqueta="Total de la boleta, en pesos"
            inputMode="numeric"
            grande
            value={monto}
            onChange={(e) => {
              setMonto(e.target.value)
              setError(null)
            }}
            error={error}
            ayuda={`Dentro del tope autorizado de ${fmtDinero(max)}.`}
          />
          <CampoTexto etiqueta="N° de boleta" inputMode="numeric" grande value={boleta} onChange={(e) => setBoleta(e.target.value)} />
        </div>
        <Nota>El total se carga a la cuenta de MATU. La familia ve este mismo monto en su pedido.</Nota>
        <Acciones>
          <Boton type="submit" icono={<PackageCheck aria-hidden className="size-5" />}>
            Marcar listo para retiro
          </Boton>
        </Acciones>
      </form>
    </Detalle>
  )
}

function Codigo() {
  const { s, haz } = useDemo()
  const p = s.pedido!
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const validado = p.estado === 'en_camino' || p.estado === 'entregado'
  const validar = () => {
    if (codigo !== p.codigoRetiro) return setError('Ese código no coincide. Pídele a quien retira que lo revise.')
    setError(null)
    haz((x) => avisar(validarCodigo(x), 'Código válido. Entrega el pedido.'))
  }
  return (
    <Detalle paso={validado ? 4 : 3}>
      {!validado ? (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            validar()
          }}
        >
          <CampoTexto
            etiqueta="Código que muestra quien retira"
            inputMode="numeric"
            maxLength={4}
            value={codigo}
            onChange={(e) => {
              setCodigo(e.target.value.replace(/\D/g, '').slice(0, 4))
              setError(null)
            }}
            className="max-w-3xs [&_input]:digitos [&_input]:min-h-16 [&_input]:text-center [&_input]:text-4xl [&_input]:font-bold [&_input]:tracking-widest"
            error={error}
            ayuda="Es de un solo uso y vence en 90 minutos."
          />
          <Acciones>
            <Boton type="submit">Validar código</Boton>
          </Acciones>
        </form>
      ) : (
        <div className="flex flex-col items-start gap-3">
          <p className="flex items-center gap-3 text-xl font-bold text-ok">
            <CircleCheck aria-hidden className="size-8" />
            Código válido
          </p>
          <p>{p.estado === 'entregado' ? 'El pedido ya se entregó.' : 'Entrega el pedido y márcalo cuando llegue a la casa.'}</p>
          {p.estado === 'en_camino' && (
            <Boton
              onClick={() => haz((x) => avisar(pilaComercio(marcarEntregado(x), ['c-pedidos']), 'Entregado. Se cobró el monto real y se avisó a la familia.'))}
            >
              Marcar como entregado
            </Boton>
          )}
        </div>
      )}
      <p className="text-base text-tenue">En el semestre, el retiro y la entrega se marcan desde esta consola.</p>
    </Detalle>
  )
}

export function Consola() {
  const { s } = useDemo()
  const top = pantallaComercio(s)
  const p = s.pedido
  let detalle: ReactNode = <Resumen />
  if (p && top.id === 'c-preparar') detalle = <Preparar />
  else if (p && top.id === 'c-monto') detalle = <Monto />
  else if (p && top.id === 'c-codigo') detalle = <Codigo />
  return (
    <div className="flex flex-1 flex-col">
      <header className="bg-tinta text-papel [&_:focus-visible]:outline-miel">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-4 @3xl:px-10 py-3">
          <span className="flex items-center gap-2.5 font-bold">
            <Store aria-hidden className="size-6" />
            {COMERCIO.nombre}
          </span>
          <span className="opacity-85">Pedidos de MATU</span>
          <span className="flex-1" />
          <span className="opacity-85 tabular-nums">
            {diaDeLaSemana(s.ahora)} {fmtFecha(s.ahora)}, {fmtHora(s.ahora)}
          </span>
        </div>
      </header>
      <main id="contenido" tabIndex={-1} className="@container/main px-4 @3xl:px-10 pt-6 pb-16 outline-none">
        <div className="mx-auto grid max-w-7xl items-start gap-x-8 gap-y-8 @3xl/main:grid-cols-[19rem_minmax(0,1fr)]">
          <Cola />
          <div key={top.n} className="min-w-0">
            {detalle}
          </div>
        </div>
      </main>
    </div>
  )
}
