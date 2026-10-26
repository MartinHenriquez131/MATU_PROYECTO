// Pedido y pago con un solo pagador. A la izquierda lo que se hace; a la derecha, la boleta:
// estimado, reserva o cobro, monto real y lo que vuelve.
import { useEffect, useState } from 'react'
import { Check, CircleCheck, CreditCard, Landmark, LoaderCircle, Lock, ReceiptText, ShoppingBag, TriangleAlert } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { avisar, datosPedido, elegirMedio, etapa, ir, nombrePila, pilaFamilia, reemplazar, resultadoPago, volver } from '../demo/logica'
import { COMERCIO } from '../demo/datos'
import { DIA, MARGEN_PORCENTAJE, diasRestantes, fmtDinero, fmtFecha, fmtHora, montoAPagar, reservaCredito } from '../demo/calculos'
import type { EstadoPedido, Medio, Pedido } from '../demo/tipos'
import { Acciones, Boton, CampoTexto, GrupoOpciones, Nota, Renglon, Subtitulo } from '../components/Ui'
import { Columna, Columnas, Pagina } from './Shell'

// ---------- Boleta ----------

export function Boleta({ p, medioVista }: { p: Pedido; medioVista?: Medio }) {
  const medio = medioVista ?? p.medio
  const pagado = etapa(p.estado) >= etapa('pagado')
  const entregado = p.estado === 'entregado'
  const credito = medio === 'credito'
  const monto = medio ? (pagado ? p.montoPagado : montoAPagar(p.estimado, medio)) : null
  const real = p.montoReal
  const dif = real !== null && monto !== null ? monto - real : null
  return (
    <section
      aria-labelledby="boleta-t"
      className="relative rounded-t-lg bg-hoja px-4 @3xl:px-7 pt-5 pb-8 ring-1 ring-linea [mask:radial-gradient(circle_at_50%_100%,transparent_0.42rem,#000_0.45rem)_bottom/1.1rem_100%_repeat-x]"
    >
      <h2 id="boleta-t" className="mb-4 flex items-center gap-2 text-xl font-bold">
        <ReceiptText aria-hidden className="size-5 text-pino" />
        Pedido #{p.numero}
      </h2>
      <div className="flex flex-col gap-3">
        <Renglon texto="Estimado" monto={fmtDinero(p.estimado)} nota={`${p.lineas.reduce((n, l) => n + l.paquetes, 0)} paquetes, precios de hoy.`} />
        {medio === null ? (
          <Renglon texto="Cómo pagas" monto="por elegir" tono="tenue" />
        ) : credito ? (
          <Renglon
            texto={pagado ? 'Reservado en tu tarjeta' : 'Se reservará en tu tarjeta'}
            monto={fmtDinero(monto!)}
            nota={entregado ? 'Ya no está retenido.' : `Estimado más ${MARGEN_PORCENTAJE}% por si algún precio cambió.`}
          />
        ) : (
          <Renglon texto={pagado ? 'Cobrado al confirmar' : 'Se cobrará al confirmar'} monto={fmtDinero(monto!)} nota="El débito se cobra al instante." />
        )}
        <Renglon
          texto="Monto real de la boleta"
          monto={real !== null ? fmtDinero(real) : 'por saber'}
          tono={real === null ? 'tenue' : undefined}
          nota={real === null ? 'Se sabe cuando la farmacia arma el pedido.' : p.boleta ? `Boleta N° ${p.boleta}` : undefined}
        />
        <hr className="border-0 border-t-2 border-tinta" />
        {medio !== 'debito' ? (
          <>
            <Renglon texto={entregado ? 'Cobrado' : 'Se cobrará'} monto={real !== null ? fmtDinero(real) : 'el monto real'} fuerte />
            {dif !== null && (
              <Renglon texto={entregado ? 'Liberado' : 'Se liberará'} monto={fmtDinero(dif)} tono="ok" nota={entregado ? 'Ya volvió a tu cupo.' : 'Al entregar, sin que hagas nada.'} />
            )}
          </>
        ) : (
          <>
            <Renglon texto="Pagas en total" monto={real !== null ? fmtDinero(real) : 'el monto real'} fuerte />
            {dif !== null && <Renglon texto="Te devolveremos" monto={fmtDinero(dif)} tono="ok" nota="Cómo y en qué plazo, todavía por definir." />}
          </>
        )}
      </div>
    </section>
  )
}

function ColumnaBoleta({ p, medioVista }: { p: Pedido; medioVista?: Medio }) {
  return (
    <Columna etiqueta="Boleta">
      <Boleta p={p} medioVista={medioVista} />
    </Columna>
  )
}

function SinPedido() {
  const { haz } = useDemo()
  return (
    <Pagina titulo="Pedidos">
      <div className="flex max-w-prose flex-col items-start gap-4">
        <span className="grid size-16 place-items-center rounded-2xl bg-rocio text-pino">
          <ShoppingBag aria-hidden className="size-9" />
        </span>
        <h2 className="titular text-3xl">No hay un pedido en curso</h2>
        <p className="text-base text-tenue">Arma uno desde la lista de reposición. Paga una sola persona y se cobra lo que realmente cuesta.</p>
        <Boton onClick={() => haz((x) => pilaFamilia(x, ['se-acaba', 'reponer']))}>Ir a la lista de reposición</Boton>
      </div>
    </Pagina>
  )
}

// ---------- Tu pedido ----------

export function PedidoPantalla() {
  const { s, haz } = useDemo()
  const p = s.pedido
  const [direccion, setDireccion] = useState(p?.direccion || s.persona?.direccion || '')
  const [equivalente, setEquivalente] = useState(p?.aceptaEquivalente ?? true)
  const [error, setError] = useState<string | null>(null)
  if (!p) return <SinPedido />
  const seguir = () => {
    if (!direccion.trim()) return setError('Escribe la dirección para que el pedido llegue.')
    haz((x) => ir(datosPedido(x, direccion.trim(), equivalente), 'medio'))
  }
  return (
    <Pagina titulo="Tu pedido" volver bajada={`Lo prepara ${COMERCIO.nombre} y llega hoy ${COMERCIO.ventana}. Paga una sola persona: tú.`}>
      <Columnas izquierda="ancha">
        <Columna etiqueta="Datos del pedido">
          <Subtitulo>Productos</Subtitulo>
          <ul className="flex flex-col divide-y divide-linea bg-hoja px-4 ring-1 ring-linea">
            {p.lineas.map((l) => (
              <li key={l.insumoId} className="flex flex-wrap items-baseline justify-between gap-x-4 py-3">
                <span>
                  {l.nombre} <span className="cifras text-tenue">× {l.paquetes}</span>
                </span>
                <span className="cifras">{fmtDinero(l.paquetes * l.precio)}</span>
              </li>
            ))}
            <li className="flex flex-wrap items-baseline justify-between gap-x-4 py-3 font-bold">
              <span>Total estimado</span>
              <span className="cifras text-xl">{fmtDinero(p.estimado)}</span>
            </li>
          </ul>
          <CampoTexto
            etiqueta="¿A dónde lo llevamos?"
            value={direccion}
            onChange={(e) => {
              setDireccion(e.target.value)
              setError(null)
            }}
            placeholder="Calle, número y comuna"
            autoComplete="off"
            ayuda="Solo la ve quien entrega. La farmacia no la ve."
            error={error}
            className="max-w-xl"
          />
          <label className="flex min-h-12 max-w-2xl cursor-pointer items-center gap-3 bg-hoja px-4 py-3 ring-1 ring-linea">
            <input type="checkbox" checked={equivalente} onChange={(e) => setEquivalente(e.target.checked)} className="size-5 shrink-0 accent-pino" />
            <span>Si falta algo, acepto un equivalente hasta 10% más caro</span>
          </label>
          <Acciones>
            <Boton onClick={seguir}>Elegir cómo pagar</Boton>
          </Acciones>
        </Columna>
        <ColumnaBoleta p={p} />
      </Columnas>
    </Pagina>
  )
}

export function MedioPago() {
  const { s, haz } = useDemo()
  const p = s.pedido
  const [medio, setMedio] = useState<Medio>(p?.medio ?? 'credito')
  if (!p) return <SinPedido />
  const monto = montoAPagar(p.estimado, medio)
  return (
    <Pagina titulo="¿Cómo pagas?" volver bajada="Antes de pagar, te contamos qué se reserva o se cobra y qué vuelve.">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Medio de pago">
          <GrupoOpciones
            leyenda="Elige tu tarjeta"
            nombre="medio"
            valor={medio}
            onCambio={setMedio}
            opciones={[
              { valor: 'credito', texto: 'Tarjeta de crédito', detalle: 'Se reserva y se cobra solo lo real.' },
              { valor: 'debito', texto: 'Tarjeta de débito', detalle: 'Se cobra al confirmar y se devuelve la diferencia.' },
            ]}
          />
          {medio === 'credito' ? (
            <Nota titulo={`Reservamos ${fmtDinero(reservaCredito(p.estimado))} por si algún precio cambió.`}>
              Se te cobrará solo lo que realmente cueste, y el resto se libera automáticamente.
            </Nota>
          ) : (
            <Nota titulo={`Con débito el banco cobra al instante: se cobran ${fmtDinero(p.estimado)} al confirmar.`}>
              Si el pedido sale por menos, te devolveremos la diferencia. Cómo y en qué plazo se devuelve todavía está por definir.
            </Nota>
          )}
          <Acciones>
            <Boton icono={<Lock aria-hidden className="size-5" />} onClick={() => haz((x) => ir(elegirMedio(x, medio), 'pasarela'))}>
              {medio === 'credito' ? 'Reservar' : 'Pagar'} <span className="cifras">{fmtDinero(monto)}</span>
            </Boton>
          </Acciones>
          <p className="flex gap-2 text-base text-tenue">
            <Lock aria-hidden className="mt-0.5 size-4.5 shrink-0" />
            Pagas en Transbank. MATU nunca ve ni guarda los datos de tu tarjeta.
          </p>
        </Columna>
        <ColumnaBoleta p={p} medioVista={medio} />
      </Columnas>
    </Pagina>
  )
}

// ---------- Pasarela simulada: otra empresa, otro aspecto ----------

export function Pasarela() {
  const { s, haz } = useDemo()
  const [procesando, setProcesando] = useState<null | boolean>(null)
  const p = s.pedido
  useEffect(() => {
    if (procesando === null) return
    const id = window.setTimeout(() => {
      haz((x) => {
        const t = resultadoPago(x, procesando)
        if (!procesando) return reemplazar(t, 'rechazado')
        // Textos revisados por el analista normativo. El monto sale de lo calculado, nunca fijo.
        const monto = fmtDinero(t.pedido?.montoPagado ?? 0)
        const msg =
          t.pedido?.medio === 'credito'
            ? `Reserva aprobada por ${monto}. Avisamos a la farmacia. Te cobramos el monto real al entregar.`
            : `Pago aprobado por ${monto}. Avisamos a la farmacia.`
        return avisar(pilaFamilia(t, ['seguimiento']), msg)
      })
    }, 1100)
    return () => window.clearTimeout(id)
  }, [procesando, haz])
  if (!p || !p.medio) {
    return (
      <main id="contenido" tabIndex={-1} className="grid min-h-96 place-items-center px-4 outline-none">
        <div className="flex flex-col items-start gap-3">
          <h1 id="titulo-pagina" tabIndex={-1} className="text-2xl font-bold outline-none">
            No hay un pago pendiente
          </h1>
          <Boton onClick={() => haz((x) => pilaFamilia(x, ['seguimiento']))}>Volver a MATU</Boton>
        </div>
      </main>
    )
  }
  const credito = p.medio === 'credito'
  return (
    <main id="contenido" tabIndex={-1} className="flex-1 bg-[#eef0f3] px-4 py-10 text-[#1f2a37] outline-none [color-scheme:light] [&_:focus-visible]:outline-[#1f2a37]">
      <div className="mx-auto flex max-w-xl flex-col gap-4">
        <header className="rounded-xl bg-[#1f2a37] px-5 py-4 text-white">
          <h1 id="titulo-pagina" tabIndex={-1} className="text-xl font-bold outline-none">
            Pasarela de pago simulada
          </h1>
          <p className="opacity-90">Transbank, ambiente de prueba. No se mueve dinero.</p>
        </header>
        <div className="rounded-xl bg-white px-5 py-4 ring-1 ring-black/10">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
            <dt className="text-[#4b5563]">Comercio</dt>
            <dd className="text-right font-bold">MATU</dd>
            <dt className="text-[#4b5563]">Orden</dt>
            <dd className="cifras text-right">{p.numero}</dd>
            <dt className="text-[#4b5563]">{credito ? 'Monto a reservar' : 'Monto a cobrar'}</dt>
            <dd className="cifras text-right text-2xl font-bold">{fmtDinero(p.montoPagado)}</dd>
          </dl>
        </div>
        <div className="flex items-center gap-3 rounded-xl bg-white px-5 py-4 ring-1 ring-black/10">
          {credito ? <CreditCard aria-hidden className="size-7 shrink-0" /> : <Landmark aria-hidden className="size-7 shrink-0" />}
          <div className="min-w-0">
            <p className="font-bold">{credito ? 'Tarjeta de crédito de prueba' : 'Tarjeta de débito de prueba'}</p>
            <p className="cifras text-[#4b5563]">terminada en 6623</p>
          </div>
        </div>
        {procesando !== null ? (
          <p role="status" className="flex items-center gap-2 py-3 font-bold">
            <LoaderCircle aria-hidden className="size-6 motion-safe:animate-spin" />
            Consultando al banco…
          </p>
        ) : (
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => setProcesando(true)} className="min-h-12 rounded-lg bg-[#1f2a37] px-5 font-bold text-white hover:bg-[#111827]">
              {credito ? 'Aprobar' : 'Aprobar el pago'}
            </button>
            <button
              type="button"
              onClick={() => setProcesando(false)}
              className="min-h-12 rounded-lg bg-white px-5 font-bold text-[#9f1c14] ring-2 ring-[#9f1c14]/70 ring-inset hover:bg-[#fef2f2]"
            >
              Simular que el banco lo rechaza
            </button>
            <button type="button" onClick={() => haz(volver)} className="min-h-12 px-2 font-bold text-[#1f2a37] underline underline-offset-4">
              Volver a MATU sin pagar
            </button>
          </div>
        )}
        <p className="text-sm text-[#4b5563]">Los datos de la tarjeta solo existen en Transbank. MATU recibe el resultado, nunca la tarjeta.</p>
      </div>
    </main>
  )
}

export function Rechazado() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p) return <SinPedido />
  return (
    <Pagina titulo="El pago no pasó">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Qué pasó">
          <div className="flex gap-3 border-l-4 border-pronto bg-pronto-fondo px-4 py-4" role="alert">
            <TriangleAlert aria-hidden className="mt-0.5 size-6 shrink-0 text-pronto" />
            <div>
              <h2 className="text-xl font-bold">El banco no aprobó el pago</h2>
              <p>Puede ser el cupo o un bloqueo del banco. No se te cobró ni se reservó nada.</p>
            </div>
          </div>
          <p className="max-w-prose">
            Tu pedido queda guardado. Si no lo pagas, la farmacia no lo prepara y nadie pierde dinero.
            {p.rechazos > 1 && ' Si sigue sin pasar, prueba con otra tarjeta.'}
          </p>
          <Acciones>
            <Boton onClick={() => haz(volver)}>Probar de nuevo</Boton>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>
              Volver al inicio
            </Boton>
          </Acciones>
        </Columna>
        <ColumnaBoleta p={p} />
      </Columnas>
    </Pagina>
  )
}

// ---------- Seguimiento y entrega ----------

const PASOS: { e: EstadoPedido; titulo: (p: Pedido) => string; detalle: (p: Pedido) => string }[] = [
  {
    e: 'pagado',
    titulo: (p) => (p.medio === 'credito' ? 'Monto reservado' : 'Pagado'),
    detalle: (p) => (p.medio === 'credito' ? `${fmtDinero(p.montoPagado)} reservados en tu tarjeta` : `${fmtDinero(p.montoPagado)} cobrados con débito`),
  },
  { e: 'preparando', titulo: () => 'La farmacia lo arma', detalle: () => COMERCIO.nombre },
  {
    e: 'listo',
    titulo: () => 'Listo para retiro',
    detalle: (p) => (p.montoReal !== null ? `Monto real: ${fmtDinero(p.montoReal)}` : 'Aquí se sabe el monto real'),
  },
  { e: 'en_camino', titulo: () => 'En camino', detalle: () => `Llega ${COMERCIO.ventana}` },
  { e: 'entregado', titulo: () => 'Entregado', detalle: (p) => (p.medio === 'credito' ? 'Se cobra el monto real' : 'Listo') },
]

function Pasos({ p }: { p: Pedido }) {
  const actual = etapa(p.estado)
  return (
    <ol className="flex flex-col">
      {PASOS.map((paso, i) => {
        const n = etapa(paso.e)
        const hecho = n <= actual
        const esActual = n === actual
        return (
          <li key={paso.e} className="relative flex gap-4 pb-5 last:pb-0" aria-current={esActual ? 'step' : undefined}>
            {i < PASOS.length - 1 && <span aria-hidden className={`absolute top-9 bottom-0 left-4 w-0.5 ${n < actual ? 'bg-pino' : 'bg-tinta/12'}`} />}
            <span
              aria-hidden
              className={`relative z-10 grid size-9 shrink-0 place-items-center rounded-full ${hecho ? 'bg-pino text-papel' : 'bg-hoja text-tenue ring-2 ring-tinta/15 ring-inset'} ${
                esActual ? 'ring-4 ring-rocio' : ''
              }`}
            >
              {hecho ? <Check className="size-5" strokeWidth={3} /> : <span className="cifras text-sm font-bold">{i + 1}</span>}
            </span>
            <span className="min-w-0 pt-1">
              <span className={`block font-bold ${hecho ? '' : 'text-tenue'}`}>
                {paso.titulo(p)}
                {esActual && <span className="sr-only">, ahora</span>}
              </span>
              <span className="text-base text-tenue">
                {hecho ? paso.detalle(p) : 'Pendiente'}
                {hecho && p.hitos[paso.e] !== undefined && <span className="cifras">, a las {fmtHora(p.hitos[paso.e]!)}</span>}
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export function Seguimiento() {
  const { s } = useDemo()
  const p = s.pedido
  if (!p || p.estado === 'borrador') return <SinPedido />
  const cambios = p.lineas.filter((l) => l.resolucion === 'reemplazado' || l.resolucion === 'no_disponible')
  return (
    <Pagina titulo={`Pedido de ${nombrePila(s)}`} bajada={`Lo prepara ${COMERCIO.nombre}. Llega hoy ${COMERCIO.ventana}.`}>
      <Columnas izquierda="ancha">
        <Columna etiqueta="Seguimiento">
          <Pasos p={p} />
          {(p.estado === 'pagado' || p.estado === 'preparando' || p.estado === 'listo') && (
            <div className="flex flex-wrap items-center justify-between gap-3 bg-rocio px-4 py-3">
              <span>Código de retiro. Lo muestra quien retira.</span>
              <span className="digitos text-2xl font-bold tracking-widest text-pino">{p.codigoRetiro}</span>
            </div>
          )}
          {cambios.length > 0 && (
            <div className="flex flex-col gap-1 border-l-4 border-atenta bg-atenta-fondo px-4 py-3">
              <h2 className="font-bold">Cambios de la farmacia</h2>
              {cambios.map((l) => (
                <p key={l.insumoId}>{l.resolucion === 'reemplazado' ? `${l.nombre}: llega otra marca equivalente.` : `${l.nombre}: no había. No se cobra.`}</p>
              ))}
            </div>
          )}
        </Columna>
        <ColumnaBoleta p={p} />
      </Columnas>
    </Pagina>
  )
}

export function Entregado() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p || p.estado !== 'entregado' || p.montoReal === null) return <Seguimiento />
  const dif = p.montoPagado - p.montoReal
  const panal = s.insumos.find((i) => i.id === 'panal-m')
  return (
    <Pagina titulo="Pedido entregado">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Resumen de la entrega">
          <div className="flex items-center gap-4">
            <span className="grid size-14 shrink-0 place-items-center rounded-full bg-ok text-ok-fondo">
              <CircleCheck aria-hidden className="size-8" />
            </span>
            <p className="titular text-3xl">
              Entregado a las <span className="cifras">{fmtHora(p.hitos.entregado ?? s.ahora)}</span>
            </p>
          </div>
          {p.medio === 'credito' ? (
            <p className="max-w-prose text-xl leading-snug">
              Se cobraron <b className="cifras">{fmtDinero(p.montoReal)}</b>. Los <b className="cifras">{fmtDinero(dif)}</b> restantes ya se liberaron.
            </p>
          ) : (
            <div className="flex max-w-prose flex-col gap-1">
              <p className="text-xl leading-snug">
                Pagaste <b className="cifras">{fmtDinero(p.montoPagado)}</b> y el pedido costó <b className="cifras">{fmtDinero(p.montoReal)}</b>. Te devolveremos la diferencia:{' '}
                <b className="cifras">{fmtDinero(dif)}</b>.
              </p>
              <p className="text-base text-tenue">Cómo y en qué plazo, todavía está por definir.</p>
            </div>
          )}
          {p.lineas
            .filter((l) => l.resolucion === 'reemplazado')
            .map((l) => (
              <p key={l.insumoId} className="flex flex-wrap items-center justify-between gap-2 border-l-4 border-atenta bg-atenta-fondo px-4 py-3">
                <span>
                  <b>{l.nombre}</b>: llegó otra marca equivalente
                </span>
                <span className="font-bold text-atenta">Cambio</span>
              </p>
            ))}
          {panal && p.sumadoAlStock && (
            <Nota titulo="Ya sumamos lo que llegó">
              Los pañales ahora alcanzan hasta el <span className="cifras">{fmtFecha(s.ahora + diasRestantes(panal) * DIA)}</span>. No tienes que anotar nada.
            </Nota>
          )}
          <Acciones>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['se-acaba']))}>
              Ver los insumos
            </Boton>
            <Boton variante="texto" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>
              Volver al inicio
            </Boton>
          </Acciones>
        </Columna>
        <ColumnaBoleta p={p} />
      </Columnas>
    </Pagina>
  )
}
