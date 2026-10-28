// Pedido con precio exacto y un solo cobro (ADR-027). Antes de pagar, la familia ve el total
// confirmado con envío e IVA, lo que cambió desde la lista y las condiciones; paga una sola vez
// ese total, con crédito o débito, y es lo mismo que se cobra al entregar.
import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  ArrowDownUp,
  Check,
  Clock,
  CreditCard,
  Download,
  Info,
  Landmark,
  Lock,
  ReceiptText,
  RefreshCw,
  ShoppingBag,
  Store,
  TriangleAlert,
  Undo2,
} from 'lucide-react'
import { useDemo } from '../demo/estado'
import {
  armarPedido,
  avisar,
  cancelarPedido,
  confirmarStock,
  datosPedido,
  etapa,
  ir,
  nombrePila,
  noPedir,
  pilaFamilia,
  reemplazar,
  resultadoPago,
  volver,
} from '../demo/logica'
import { COMERCIO, OTRO_COMERCIO } from '../demo/datos'
import { CONDICIONES, QUIEN_VENDE, SI_FALTA_ALGO, VIGENCIA_MINUTOS } from '../demo/textos-pedido'
import { DIA, devolucion, diasRestantes, fmtDinero, fmtFecha, fmtHora, totalVencido } from '../demo/calculos'
import type { EstadoPedido, Medio, Pedido } from '../demo/tipos'
import { Acciones, Boton, CampoTexto, Etiqueta, Nota, PreciosDeEjemplo, Renglon, Subtitulo } from '../components/Ui'
import { Columna, Columnas, Pagina } from './Shell'

// ---------- Boleta: solo dinero exacto ----------

type ModoBoleta = 'antes' | 'pagado' | 'entregado' | 'cancelado'

export function Boleta({ p, modo, tenue = false }: { p: Pedido; modo: ModoBoleta; tenue?: boolean }) {
  const dev = devolucion(p)
  return (
    <section
      aria-labelledby="boleta-t"
      className={`relative rounded-t-lg bg-hoja px-4 @3xl:px-7 pt-5 pb-8 ring-1 ring-linea [mask:radial-gradient(circle_at_50%_100%,transparent_0.42rem,var(--color-tinta)_0.45rem)_bottom/1.1rem_100%_repeat-x] ${
        tenue ? 'text-tenue' : ''
      }`}
    >
      <h2 id="boleta-t" className="mb-4 flex items-center gap-2 text-xl font-bold">
        <ReceiptText aria-hidden className="size-5 text-pino" />
        Pedido #{p.numero}
      </h2>
      <div className="flex flex-col gap-3">
        {p.lineas.map((l) => (
          <Renglon
            key={l.insumoId}
            texto={
              <>
                {l.nombre} <span className="tabular-nums text-tenue">× {l.paquetes}</span>
              </>
            }
            monto={fmtDinero(l.paquetes * l.precio)}
            nota={
              <span className="flex flex-wrap items-center gap-2">
                {l.reasignado?.comercio ?? l.comercio}
                {l.noLlego && <Etiqueta>No llegó</Etiqueta>}
              </span>
            }
          />
        ))}
        <Renglon texto="Envío, uno por pedido" monto={fmtDinero(p.envio)} />
        <hr className="border-0 border-t-2 border-tinta" />
        {modo === 'antes' && (
          <Renglon
            texto="Total con IVA"
            monto={fmtDinero(p.total)}
            fuerte
            nota={
              <>
                Se cobra una sola vez.
                {p.estado === 'apartado' && (
                  <span className="block tabular-nums">Este total vale hasta las {fmtHora(p.venceMin)}.</span>
                )}
              </>
            }
          />
        )}
        {modo === 'pagado' && <Renglon texto="Pagado" monto={fmtDinero(p.total)} fuerte />}
        {modo === 'cancelado' && (
          <>
            <Renglon texto="Pagado" monto={fmtDinero(p.total)} />
            <Renglon texto="Te devolveremos" monto={fmtDinero(p.total)} tono="ok" fuerte nota="El mismo día, a la misma tarjeta." />
          </>
        )}
        {modo === 'entregado' && (
          <>
            <Renglon texto="Cobrado" monto={fmtDinero(p.total)} fuerte={dev === 0} nota="Es el total que viste antes de pagar." />
            {dev > 0 && (
              <>
                <Renglon texto="Te devolveremos" monto={fmtDinero(dev)} tono="ok" nota="El mismo día, a la misma tarjeta." />
                <Renglon texto="Pagas en total" monto={fmtDinero(p.total - dev)} fuerte />
              </>
            )}
          </>
        )}
      </div>
    </section>
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
        <p className="text-lg text-tenue">Arma uno desde la lista de reposición. Ves el total exacto antes de pagar y se cobra una sola vez.</p>
        <Boton onClick={() => haz((x) => pilaFamilia(x, ['se-acaba', 'reponer']))}>Ir a la lista de reposición</Boton>
      </div>
    </Pagina>
  )
}

/** Productos del pedido con cantidad, precio unitario, subtotal, comercio y lo que cambió. */
function TablaProductos({ p }: { p: Pedido }) {
  return (
    <ul className="flex flex-col divide-y divide-linea bg-hoja px-4 ring-1 ring-linea">
      {p.lineas.map((l, i) => (
        <li key={l.insumoId} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-3">
          <span className="min-w-0 grow basis-40">
            <span className="block font-bold">{l.nombre}</span>
            <span className="flex flex-wrap items-center gap-2 text-sm text-tenue">
              {i === 0 ? COMERCIO.nombreFicticio : l.comercio}
              {l.cambio === 'precio' && (
                <Etiqueta tono="atenta">
                  <ArrowDownUp aria-hidden className="size-4" />
                  Cambió el precio
                </Etiqueta>
              )}
              {l.cambio === 'comercio' && (
                <Etiqueta tono="atenta">
                  <Store aria-hidden className="size-4" />
                  Otro comercio
                </Etiqueta>
              )}
            </span>
          </span>
          <span className="tabular-nums text-tenue">
            {l.paquetes} × {fmtDinero(l.precio)}
          </span>
          <span className="cifras ml-auto w-24 text-right">{fmtDinero(l.paquetes * l.precio)}</span>
        </li>
      ))}
      <li className="flex flex-wrap items-baseline justify-between gap-x-4 py-3">
        <span>Envío, uno por pedido</span>
        <span className="cifras">{fmtDinero(p.envio)}</span>
      </li>
      <li className="flex flex-wrap items-baseline justify-between gap-x-4 py-3 font-bold">
        <span>Total con IVA</span>
        <span className="cifras text-xl">{fmtDinero(p.total)}</span>
      </li>
    </ul>
  )
}

function NoDisponibles({ p }: { p: Pedido }) {
  if (!p.salieron.length) return null
  return (
    <section aria-labelledby="fuera-t" className="flex flex-col gap-2">
      <Subtitulo id="fuera-t">No está disponible hoy</Subtitulo>
      <ul className="flex flex-col gap-2 text-tenue">
        {p.salieron.map((l) => (
          <li key={l.insumoId} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{l.nombre}</span>
            <span className="tabular-nums">
              {l.paquetes} × {fmtDinero(l.precio)}
            </span>
            <Etiqueta>Salió del pedido</Etiqueta>
          </li>
        ))}
      </ul>
    </section>
  )
}

function LoQueCambio({ p }: { p: Pedido }) {
  const precios = p.lineas.filter((l) => l.cambio === 'precio')
  if (!p.salieron.length && !precios.length) return null
  return (
    <Nota titulo="Lo que cambió desde tu lista" icono={<RefreshCw aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />}>
      <ul className="flex flex-col gap-1">
        {p.salieron.map((l) => (
          <li key={l.insumoId}>{l.nombre}: nadie la tiene hoy. Salió del pedido y sigue en tu lista.</li>
        ))}
        {precios.map((l) => (
          <li key={l.insumoId} className="tabular-nums">
            {l.nombre}: {l.precio < l.precioLista ? 'bajó' : 'subió'} de {fmtDinero(l.precioLista)} a {fmtDinero(l.precio)}.
          </li>
        ))}
        {p.total !== p.totalLista && (
          <li className="tabular-nums">
            El total {p.total < p.totalLista ? 'bajó' : 'subió'} de {fmtDinero(p.totalLista)} a {fmtDinero(p.total)}.
          </li>
        )}
      </ul>
    </Nota>
  )
}

function Dato({ termino, children }: { termino: string; children: ReactNode }) {
  return (
    <div className="grid gap-x-6 gap-y-1 border-b border-linea py-3 last:border-0 @md:grid-cols-[9rem_minmax(0,1fr)]">
      <dt className="font-bold">{termino}</dt>
      <dd className="text-base">{children}</dd>
    </div>
  )
}

/** Dos columnas: lo de arriba y lo de abajo a la izquierda, la boleta a la derecha. A una columna,
 *  la boleta va entre los productos y las condiciones. */
function DosZonas({ arriba, boleta, abajo }: { arriba: ReactNode; boleta: ReactNode; abajo?: ReactNode }) {
  return (
    <div className="grid grid-cols-1 items-start gap-x-8 @3xl:gap-x-16 gap-y-8 @2xl/main:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
      <div className="@container flex min-w-0 flex-col gap-5 @2xl/main:col-start-1">{arriba}</div>
      <div className="@container flex min-w-0 flex-col gap-5 @2xl/main:col-start-2 @2xl/main:row-span-2 @2xl/main:row-start-1">{boleta}</div>
      {abajo && <div className="@container flex min-w-0 flex-col gap-5 @2xl/main:col-start-1">{abajo}</div>}
    </div>
  )
}

// ---------- Escena 21 y 31: Tu pedido ----------

export function PedidoPantalla() {
  const { s, haz } = useDemo()
  const p = s.pedido
  const [acepto, setAcepto] = useState(false)
  const [direccion, setDireccion] = useState(p?.direccion ?? '')
  const [intento, setIntento] = useState(false)
  const confirmando = p?.estado === 'confirmando'

  // En la demo, confirmar el stock dura menos de un segundo.
  useEffect(() => {
    if (!confirmando) return
    const id = window.setTimeout(() => haz((x) => confirmarStock(x, x.pedido?.reconfirmado ?? false)), 700)
    return () => window.clearTimeout(id)
  }, [confirmando, haz])

  if (!p) return <SinPedido />
  if (confirmando) {
    return (
      <Pagina titulo="Tu pedido" volver>
        <p aria-busy="true" role="status" className="text-lg">
          Confirmando el stock con los comercios…
        </p>
      </Pagina>
    )
  }
  if (etapa(p.estado) > etapa('apartado') || p.estado === 'cancelado') return <Seguimiento />

  if (p.lineas.length === 0) {
    return (
      <Pagina titulo="Tu pedido" volver>
        <div className="flex max-w-prose flex-col items-start gap-4">
          <p className="text-lg">Ningún comercio en convenio tiene estos productos hoy. No se cobró nada y tu lista sigue igual.</p>
          <Boton onClick={() => haz((x) => pilaFamilia({ ...x, pedido: null }, ['se-acaba', 'reponer']))}>Volver a la lista</Boton>
        </div>
      </Pagina>
    )
  }

  const vencido = totalVencido(p, s.ahora)
  if (vencido) {
    return (
      <Pagina titulo="Tu pedido" volver>
        <DosZonas
          arriba={
            <>
              <Nota tono="atenta" titulo="Este total ya no vale" icono={<Clock aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
                <p>Pasaron {VIGENCIA_MINUTOS} minutos y el stock o los precios pueden haber cambiado. No se cobró nada.</p>
                <Acciones className="mt-3">
                  <Boton onClick={() => haz((x) => confirmarStock(armarPedido(x), true))}>Confirmar de nuevo</Boton>
                  <Boton variante="texto" onClick={() => haz(noPedir)}>
                    No pedir por ahora
                  </Boton>
                </Acciones>
              </Nota>
              <Subtitulo>Lo que habías visto</Subtitulo>
              <div className="text-tenue">
                <TablaProductos p={p} />
              </div>
            </>
          }
          boleta={<Boleta p={{ ...p, estado: 'confirmando' }} modo="antes" tenue />}
        />
      </Pagina>
    )
  }

  const faltaDireccion = !p.direccion && !direccion.trim()
  const pagar = () => {
    setIntento(true)
    if (!acepto || faltaDireccion) return
    haz((x) => ir(p.direccion ? x : datosPedido(x, direccion.trim()), 'pasarela'))
  }
  const sinCambios = !p.salieron.length && !p.lineas.some((l) => l.cambio)
  const resumen = p.reconfirmado
    ? `Confirmamos de nuevo el stock. El total quedó en ${fmtDinero(p.total)}.`
    : sinCambios
      ? 'Confirmamos el stock: está todo.'
      : `Confirmamos el stock. El total quedó en ${fmtDinero(p.total)}.`

  return (
    <Pagina titulo="Tu pedido" volver bajada={resumen}>
      <DosZonas
        arriba={
          <>
            <LoQueCambio p={p} />
            <Subtitulo>Productos</Subtitulo>
            <TablaProductos p={p} />
            <NoDisponibles p={p} />
          </>
        }
        boleta={
          <>
            <Boleta p={p} modo="antes" />
            <PreciosDeEjemplo />
          </>
        }
        abajo={
          <>
            <dl className="bg-hoja px-4 ring-1 ring-linea">
              <Dato termino="Entrega">
                {p.direccion ? (
                  `Llega hoy ${COMERCIO.ventana} a ${p.direccion}.`
                ) : (
                  <div className="flex flex-col gap-2">
                    <span>Llega hoy {COMERCIO.ventana}.</span>
                    <CampoTexto
                      etiqueta="¿A dónde lo llevamos?"
                      value={direccion}
                      onChange={(e) => setDireccion(e.target.value)}
                      placeholder="Calle, número y comuna"
                      autoComplete="off"
                      error={intento && faltaDireccion ? 'Escribe la dirección para que el pedido llegue.' : null}
                    />
                  </div>
                )}
              </Dato>
              <Dato termino="Boleta">{QUIEN_VENDE}</Dato>
              <Dato termino="Si falta algo">
                <Nota>{SI_FALTA_ALGO}</Nota>
              </Dato>
            </dl>
            <div className="flex flex-col gap-2">
              <label className="flex min-h-12 cursor-pointer items-center gap-3 bg-hoja px-4 py-3 font-bold ring-2 ring-borde ring-inset">
                <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} className="size-5 shrink-0 accent-pino" />
                Leí y acepto las condiciones del pedido.
              </label>
              <details className="group">
                <summary className="inline-flex min-h-10 telefono:min-h-12 cursor-pointer items-center px-1 font-bold text-pino underline decoration-pino/40 underline-offset-4">
                  Ver las condiciones
                </summary>
                <ul className="mt-2 flex list-disc flex-col gap-1.5 bg-hoja py-3 pr-4 pl-9 ring-1 ring-linea">
                  {CONDICIONES.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </details>
            </div>
            <p className="max-w-prose">Pagas con crédito o débito en Transbank. Se cobra una sola vez este total, sin cobros después.</p>
            <Acciones>
              <Boton icono={<Lock aria-hidden className="size-5" />} disabled={!acepto} onClick={pagar}>
                Pagar <span className="cifras">{fmtDinero(p.total)}</span>
              </Boton>
              {!acepto && <span className="text-tenue">Acepta las condiciones del pedido para pagar.</span>}
              <Boton variante="texto" onClick={() => haz(noPedir)}>
                No pedir por ahora
              </Boton>
            </Acciones>
          </>
        }
      />
    </Pagina>
  )
}

// ---------- Escena 22: pasarela simulada, otra empresa, otro aspecto ----------

export function Pasarela() {
  const { s, haz } = useDemo()
  const [procesando, setProcesando] = useState<null | boolean>(null)
  const [medio, setMedio] = useState<Medio>('credito')
  const p = s.pedido
  useEffect(() => {
    if (procesando === null) return
    const id = window.setTimeout(() => {
      haz((x) => {
        const t = resultadoPago(x, procesando, medio)
        if (!procesando) return reemplazar(t, 'rechazado')
        return avisar(pilaFamilia(t, ['seguimiento']), `Pago aprobado por ${fmtDinero(t.pedido?.total ?? 0)}. Avisamos a la farmacia.`)
      })
    }, 800)
    return () => window.clearTimeout(id)
  }, [procesando, medio, haz])
  if (!p || p.estado !== 'apartado' || totalVencido(p, s.ahora)) {
    return (
      <main id="contenido" tabIndex={-1} className="grid min-h-96 place-items-center px-4 angosto:px-2 outline-none">
        <div className="flex flex-col items-start gap-3">
          <h1 id="titulo-pagina" tabIndex={-1} className="text-2xl font-bold outline-none">
            No hay un pago pendiente
          </h1>
          <Boton onClick={() => haz((x) => (x.pedido?.estado === 'apartado' ? volver(x) : pilaFamilia(x, ['seguimiento'])))}>Volver a MATU</Boton>
        </div>
      </main>
    )
  }
  const tarjetas: { valor: Medio; texto: string; final: string; Icono: typeof CreditCard }[] = [
    { valor: 'credito', texto: 'Tarjeta de crédito de prueba', final: '6623', Icono: CreditCard },
    { valor: 'debito', texto: 'Tarjeta de débito de prueba', final: '4051', Icono: Landmark },
  ]
  return (
    <main id="contenido" tabIndex={-1} className="flex-1 bg-pasarela px-4 angosto:px-2 py-10 text-pasarela-tinta outline-none [color-scheme:light] [&_:focus-visible]:outline-pasarela-tinta">
      <div className="mx-auto flex max-w-xl flex-col gap-4">
        <header className="rounded-xl bg-pasarela-tinta px-5 py-4 text-pasarela-hoja">
          <h1 id="titulo-pagina" tabIndex={-1} className="text-xl font-bold outline-none">
            Pasarela de pago simulada
          </h1>
          <p className="opacity-90">Transbank, ambiente de prueba.</p>
        </header>
        <p className="flex gap-3 rounded-xl border-l-4 border-pasarela-tinta bg-pasarela-hoja px-5 py-3 font-bold ring-1 ring-pasarela-tinta/10">
          <Info aria-hidden className="mt-0.5 size-5 shrink-0" />
          Pago de prueba. No se cobra dinero real.
        </p>
        <div className="rounded-xl bg-pasarela-hoja px-5 py-4 ring-1 ring-pasarela-tinta/10">
          <dl className="grid grid-cols-[auto_1fr] angosto:grid-cols-1 gap-x-4 gap-y-1.5">
            <dt className="text-pasarela-tenue">Comercio</dt>
            <dd className="text-right angosto:text-left font-bold">MATU</dd>
            <dt className="text-pasarela-tenue">Orden</dt>
            <dd className="cifras text-right angosto:text-left">{p.numero}</dd>
            <dt className="text-pasarela-tenue">Monto a pagar</dt>
            <dd className="cifras text-right angosto:text-left text-2xl font-bold">{fmtDinero(p.total)}</dd>
          </dl>
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 font-bold">Elige una tarjeta de prueba</legend>
          {tarjetas.map(({ valor, texto, final, Icono }) => {
            const on = medio === valor
            return (
              <label
                key={valor}
                className={`flex min-h-13 cursor-pointer items-center gap-3 rounded-xl bg-pasarela-hoja px-4 py-3 ring-inset has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pasarela-tinta ${
                  on ? 'ring-3 ring-pasarela-tinta' : 'ring-2 ring-pasarela-tenue'
                }`}
              >
                <input type="radio" name="tarjeta" className="sr-only" checked={on} onChange={() => setMedio(valor)} />
                <span aria-hidden className={`grid size-6 shrink-0 place-items-center rounded-full ring-2 ring-inset ${on ? 'ring-pasarela-tinta' : 'ring-pasarela-tenue'}`}>
                  {on && <span className="size-3 rounded-full bg-pasarela-tinta" />}
                </span>
                <Icono aria-hidden className="size-6 shrink-0" />
                <span className="min-w-0">
                  <span className="block font-bold">{texto}</span>
                  <span className="text-pasarela-tenue tabular-nums">terminada en {final}</span>
                </span>
              </label>
            )
          })}
        </fieldset>
        {procesando !== null ? (
          <p role="status" aria-busy="true" className="py-3 font-bold">
            Pagando…
          </p>
        ) : (
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => setProcesando(true)} className="min-h-12 rounded-lg bg-pasarela-tinta px-5 font-bold text-pasarela-hoja hover:bg-pasarela-presionado">
              Pagar
            </button>
            <button
              type="button"
              onClick={() => setProcesando(false)}
              className="min-h-12 rounded-lg bg-pasarela-hoja px-5 font-bold text-pasarela-rechazo ring-2 ring-pasarela-rechazo/70 ring-inset hover:bg-pasarela-rechazo-fondo"
            >
              Simular que el banco lo rechaza
            </button>
            <button type="button" onClick={() => haz(volver)} className="min-h-12 px-2 font-bold text-pasarela-tinta underline underline-offset-4">
              Volver a MATU sin pagar
            </button>
          </div>
        )}
        <p className="text-sm text-pasarela-tenue">Los datos de la tarjeta solo existen en Transbank. MATU recibe el resultado, nunca la tarjeta.</p>
      </div>
    </main>
  )
}

// ---------- Escena 32: el pago no pasó ----------

export function Rechazado() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p) return <SinPedido />
  const vencido = totalVencido(p, s.ahora)
  return (
    <Pagina titulo="El pago no pasó">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Qué pasó">
          <div className="flex gap-3 border-l-4 border-pronto bg-pronto-fondo px-4 py-4" role="alert">
            <TriangleAlert aria-hidden className="mt-0.5 size-6 shrink-0 text-pronto" />
            <div>
              <h2 className="text-xl font-bold">El banco no aprobó el pago</h2>
              <p>Puede ser el cupo o un bloqueo del banco. No se cobró nada.</p>
            </div>
          </div>
          <p className="max-w-prose tabular-nums">
            Tu pedido sigue apartado hasta las {fmtHora(p.venceMin)}. Si no lo pagas, se libera solo y nadie pierde dinero.
            {p.rechazos > 1 && ' Si sigue sin pasar, prueba con otra tarjeta.'}
          </p>
          <Acciones>
            {/* Si el total ya venció, "Probar de nuevo" lleva a confirmarlo de nuevo. */}
            <Boton onClick={() => haz((x) => (vencido ? volver(x) : reemplazar(x, 'pasarela')))}>Probar de nuevo</Boton>
            <Boton variante="texto" onClick={() => haz(noPedir)}>
              No pedir por ahora
            </Boton>
          </Acciones>
        </Columna>
        <Columna etiqueta="Boleta">
          <Boleta p={p} modo="antes" />
          <PreciosDeEjemplo />
        </Columna>
      </Columnas>
    </Pagina>
  )
}

// ---------- Escenas 23 y 27: seguimiento, con el cambio de local ----------

const PASOS: { e: EstadoPedido; titulo: string; detalle: (p: Pedido) => string }[] = [
  { e: 'pagado', titulo: 'Pagado', detalle: (p) => `${fmtDinero(p.total)} una sola vez, a las ${fmtHora(p.hitos.pagado ?? 0)}` },
  { e: 'preparando', titulo: 'La farmacia lo prepara', detalle: () => COMERCIO.nombre },
  { e: 'listo', titulo: 'Listo para retiro', detalle: () => 'Lo retira quien entrega' },
  { e: 'en_camino', titulo: 'En camino', detalle: () => `Llega ${COMERCIO.ventana}` },
  { e: 'entregado', titulo: 'Entregado', detalle: () => 'Listo' },
]

function Pasos({ p, extra }: { p: Pedido; extra?: ReactNode }) {
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
            <span className="flex min-w-0 flex-col items-start gap-1 pt-1">
              <span className={`font-bold ${hecho ? '' : 'text-tenue'}`}>
                {paso.titulo}
                {esActual && <span className="sr-only">, ahora</span>}
              </span>
              <span className="text-base text-tenue tabular-nums">
                {hecho ? paso.detalle(p) : 'Pendiente'}
                {hecho && i > 0 && p.hitos[paso.e] !== undefined && <>, a las {fmtHora(p.hitos[paso.e]!)}</>}
              </span>
              {i === 0 && extra}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function NotaCambioLocal({ p }: { p: Pedido }) {
  const r = p.lineas.find((l) => l.reasignado)
  if (!r || !r.reasignado) return null
  const diferencia = (r.reasignado.precio - r.precio) * r.paquetes
  return (
    <Nota titulo="Cambiamos de local un producto" icono={<RefreshCw aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />}>
      <p className="tabular-nums">
        {r.nombre} ya no estaba en {COMERCIO.nombre}. Lo retiramos en {OTRO_COMERCIO.nombreFicticio}: es el mismo producto. Pagas lo mismo
        {diferencia > 0 ? `; la diferencia de ${fmtDinero(diferencia)} la pone MATU.` : '.'}
      </p>
      <p className="mt-1 text-sm text-tenue">En esta demo, el cambio de local es simulado.</p>
    </Nota>
  )
}

export function Seguimiento() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p || etapa(p.estado) < etapa('pagado')) {
    if (p && p.estado === 'cancelado') return <Cancelado p={p} />
    return <SinPedido />
  }
  return (
    <Pagina titulo={`Pedido de ${nombrePila(s)}`} bajada={`Lo prepara ${COMERCIO.nombreFicticio}. Llega hoy ${COMERCIO.ventana}.`}>
      <Columnas izquierda="ancha">
        <Columna etiqueta="Seguimiento">
          <NotaCambioLocal p={p} />
          <Pasos
            p={p}
            extra={
              <Boton variante="secundario" icono={<Download aria-hidden className="size-5" />} onClick={() => haz((x) => avisar(x, 'Comprobante descargado.'))}>
                Descargar el comprobante
              </Boton>
            }
          />
          {(p.estado === 'pagado' || p.estado === 'preparando' || p.estado === 'listo') && (
            <div className="flex flex-wrap items-center justify-between gap-3 bg-rocio px-4 py-3">
              <span>Código de retiro. Lo muestra quien retira.</span>
              <span className="digitos text-2xl font-bold tracking-widest text-pino">{p.codigoRetiro}</span>
            </div>
          )}
          {p.estado === 'pagado' && <CancelarPedido total={p.total} />}
        </Columna>
        <Columna etiqueta="Boleta">
          <Boleta p={p} modo="pagado" />
          <PreciosDeEjemplo />
        </Columna>
      </Columnas>
    </Pagina>
  )
}

/** Cancelar después de pagar, con una confirmación en el mismo lugar (sin ventana modal). */
function CancelarPedido({ total }: { total: number }) {
  const { haz } = useDemo()
  const [confirmando, setConfirmando] = useState(false)
  const pregunta = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    if (confirmando) pregunta.current?.focus()
  }, [confirmando])
  if (confirmando) {
    return (
      <div className="flex flex-col items-start gap-3 border-l-4 border-atenta bg-atenta-fondo px-4 py-3">
        <p ref={pregunta} tabIndex={-1} className="font-bold tabular-nums outline-none">
          ¿Cancelar el pedido? Te devolveremos {fmtDinero(total)} a la misma tarjeta.
        </p>
        <Acciones>
          <Boton variante="secundario" onClick={() => haz(cancelarPedido)}>
            Sí, cancelar el pedido
          </Boton>
          <Boton variante="texto" onClick={() => setConfirmando(false)}>
            Seguir con el pedido
          </Boton>
        </Acciones>
      </div>
    )
  }
  return (
    <div className="flex flex-col items-start gap-1">
      <Boton variante="texto" onClick={() => setConfirmando(true)}>
        Cancelar el pedido
      </Boton>
      <span className="text-base text-tenue">Sin costo, mientras la farmacia no empiece a prepararlo.</span>
    </div>
  )
}

function Cancelado({ p }: { p: Pedido }) {
  const { haz } = useDemo()
  return (
    <Pagina titulo="Pedido cancelado">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Qué pasó">
          <Nota titulo="Cancelaste el pedido antes de que la farmacia empezara a prepararlo" icono={<Undo2 aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />}>
            <p className="tabular-nums">Te devolveremos {fmtDinero(p.total)} el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.</p>
          </Nota>
          <Acciones>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia({ ...x, pedido: null }, ['se-acaba', 'reponer']))}>
              Volver a la lista
            </Boton>
          </Acciones>
        </Columna>
        <Columna etiqueta="Boleta">
          <Boleta p={p} modo="cancelado" />
          <PreciosDeEjemplo />
        </Columna>
      </Columnas>
    </Pagina>
  )
}

// ---------- Escenas 28 y 33: entregado, y un producto que no llegó ----------

export function Entregado() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p || p.estado !== 'entregado') return <Seguimiento />
  const dev = devolucion(p)
  const fuera = p.lineas.filter((l) => l.noLlego)
  const reasignado = p.lineas.find((l) => l.reasignado)
  const panal = s.insumos.find((i) => i.id === 'panal-m')
  const llegoPanal = p.lineas.some((l) => l.insumoId === 'panal-m' && !l.noLlego)
  return (
    <Pagina titulo="Pedido entregado">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Resumen de la entrega">
          <div className="flex items-center gap-4 angosto:flex-col angosto:items-start angosto:gap-3">
            <span className="grid size-14 shrink-0 place-items-center rounded-full bg-ok text-ok-fondo">
              <Check aria-hidden className="size-8" strokeWidth={3} />
            </span>
            <p className="titular text-3xl">
              Llegó a las <span className="cifras">{fmtHora(p.hitos.entregado ?? s.ahora)}</span>
            </p>
          </div>
          <div className="flex max-w-prose flex-col gap-1">
            <p className="text-xl leading-snug">
              Se cobró <b className="cifras">{fmtDinero(p.total)}</b> una sola vez. Es el total que viste antes de pagar.
            </p>
            {reasignado?.reasignado && (
              <p className="text-base text-tenue">
                {reasignado.nombre} llegó desde {OTRO_COMERCIO.nombreFicticio}. No pagaste más.
              </p>
            )}
          </div>
          {dev > 0 && (
            <Nota tono="atenta" titulo={fuera.length === p.lineas.length ? 'Ningún producto llegó' : 'Un producto no llegó'} icono={<Undo2 aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
              {fuera.length === p.lineas.length ? (
                <p className="tabular-nums">Te devolveremos {fmtDinero(dev)}, con el envío, el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.</p>
              ) : (
                <p className="tabular-nums">
                  Ningún comercio en convenio tenía {fuera.map((l) => l.nombre).join(', ')}. Te devolveremos {fmtDinero(dev)} el mismo día, a la misma tarjeta, por anulación
                  en Transbank. Cuándo lo ves en tu cuenta depende de tu banco. El envío no se devuelve porque el resto del pedido sí llegó.
                </p>
              )}
            </Nota>
          )}
          {panal && llegoPanal && p.sumadoAlStock && (
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
        <Columna etiqueta="Boleta">
          <Boleta p={p} modo="entregado" />
          <p className="text-base text-tenue tabular-nums">
            La boleta la emite MATU por el total cobrado, {fmtDinero(p.total)}, con el envío incluido.
          </p>
          <PreciosDeEjemplo />
        </Columna>
      </Columnas>
    </Pagina>
  )
}
