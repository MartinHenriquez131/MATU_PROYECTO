import { useEffect, useState } from 'react'
import { Check, CircleCheck, CreditCard, Landmark, LoaderCircle, Lock, MapPin, ReceiptText, Store, TriangleAlert } from 'lucide-react'
import { useDemo } from '../demo/estado'
import {
  avisar,
  datosPedido,
  elegirMedio,
  etapa,
  ir,
  pilaComercio,
  pilaFamilia,
  reemplazar,
  resultadoPago,
  volver,
} from '../demo/logica'
import { COMERCIO } from '../demo/datos'
import { MARGEN_PORCENTAJE, diasRestantes, fmtDinero, fmtFecha, fmtHora, montoAPagar, reservaCredito, DIA } from '../demo/calculos'
import type { EstadoPedido, Medio, Pedido } from '../demo/tipos'
import { Pantalla } from '../components/Pantalla'
import { Boton, CampoTexto, GrupoOpciones, Nota, Sello, Tarjeta } from '../components/Ui'

// ---------- Boleta: estimado, reservado o cobrado, y monto real ----------

function Renglon({ texto, monto, fuerte = false, nota }: { texto: string; monto: string; fuerte?: boolean; nota?: string }) {
  return (
    <div className={`flex flex-col ${fuerte ? 'font-bold' : ''}`}>
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 shrink">{texto}</span>
        <span aria-hidden className="min-w-4 flex-1 translate-y-[-0.3em] border-b-2 border-dotted border-tinta/20" />
        <span className={`cifras shrink-0 ${fuerte ? 'text-[1.2rem]' : ''}`}>{monto}</span>
      </div>
      {nota && <span className="text-sm text-tenue">{nota}</span>}
    </div>
  )
}

export function Boleta({ p }: { p: Pedido }) {
  const credito = p.medio === 'credito'
  const entregado = p.estado === 'entregado'
  const real = p.montoReal
  const dif = real !== null ? p.montoPagado - real : null
  return (
    <section
      aria-label="Boleta del pedido"
      className="relative bg-hoja px-4 pt-4 pb-6 ring-1 ring-linea [mask:radial-gradient(circle_at_50%_100%,transparent_0.42rem,#000_0.45rem)_bottom/1.1rem_100%_repeat-x] rounded-t-[1.2rem]"
    >
      <h2 className="mb-3 flex items-center gap-2 font-display text-[1.1rem] font-bold">
        <ReceiptText aria-hidden className="size-5 text-pino" />
        Pedido #{p.numero}
      </h2>
      <div className="flex flex-col gap-2.5">
        <Renglon texto="Estimado" monto={fmtDinero(p.estimado)} />
        {credito ? (
          <Renglon
            texto="Reservado en tu tarjeta"
            monto={fmtDinero(p.montoPagado)}
            nota={entregado ? 'Ya no está retenido.' : `Estimado más ${MARGEN_PORCENTAJE}% por si algún precio cambió.`}
          />
        ) : (
          <Renglon texto="Cobrado al confirmar" monto={fmtDinero(p.montoPagado)} nota="El débito se cobra al instante." />
        )}
        <Renglon
          texto="Monto real de la boleta"
          monto={real !== null ? fmtDinero(real) : 'por saber'}
          nota={real === null ? 'Se sabe cuando la farmacia arma el pedido.' : p.boleta ? `Boleta N° ${p.boleta}` : undefined}
        />
        <hr className="border-0 border-t-2 border-tinta" />
        {credito ? (
          <>
            <Renglon texto={entregado ? 'Cobrado' : 'Se cobrará'} monto={real !== null ? fmtDinero(real) : 'el monto real'} fuerte />
            {dif !== null && (
              <Renglon texto={entregado ? 'Liberado' : 'Se liberará'} monto={fmtDinero(dif)} nota={entregado ? 'Ya volvió a tu cupo.' : 'Al entregar, sin que hagas nada.'} />
            )}
          </>
        ) : (
          <>
            <Renglon texto="Pagas en total" monto={real !== null ? fmtDinero(real) : 'el monto real'} fuerte />
            {dif !== null && <Renglon texto="Te devolvemos" monto={fmtDinero(dif)} nota="A la misma tarjeta, cuando la farmacia armó el pedido." />}
          </>
        )}
      </div>
    </section>
  )
}

// ---------- Pedido ----------

export function PedidoPantalla() {
  const { s, haz } = useDemo()
  const p = s.pedido
  const [direccion, setDireccion] = useState(p?.direccion || s.persona?.direccion || '')
  const [equivalente, setEquivalente] = useState(p?.aceptaEquivalente ?? true)
  const [error, setError] = useState<string | null>(null)
  if (!p) return null
  const seguir = () => {
    if (!direccion.trim()) return setError('Necesitamos la dirección para llevar el pedido.')
    haz((x) => ir(datosPedido(x, direccion.trim(), equivalente), 'medio'))
  }
  return (
    <Pantalla titulo="Tu pedido" pie={<Boton onClick={seguir}>Elegir cómo pagar</Boton>}>
      <ul className="flex flex-col divide-y divide-linea rounded-[1.2rem] bg-hoja px-4 ring-1 ring-linea">
        {p.lineas.map((l) => (
          <li key={l.insumoId} className="flex flex-wrap items-baseline justify-between gap-x-3 py-3">
            <span>
              {l.nombre} <span className="cifras text-tenue">× {l.paquetes}</span>
            </span>
            <span className="cifras">{fmtDinero(l.paquetes * l.precio)}</span>
          </li>
        ))}
        <li className="flex flex-wrap items-baseline justify-between gap-x-3 py-3 font-bold">
          <span>Total estimado</span>
          <span className="cifras text-[1.25rem]">{fmtDinero(p.estimado)}</span>
        </li>
      </ul>
      <p className="flex gap-2 text-[0.95rem]">
        <Store aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />
        <span>
          Lo prepara {COMERCIO.nombre} y llega hoy {COMERCIO.ventana}. El precio final se sabe cuando lo arman.
        </span>
      </p>
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
      />
      <label className="flex min-h-13 cursor-pointer items-center gap-3 rounded-2xl bg-hoja px-4 py-3 ring-1 ring-linea">
        <input type="checkbox" checked={equivalente} onChange={(e) => setEquivalente(e.target.checked)} className="size-6 shrink-0 accent-[var(--color-pino)]" />
        <span>Si falta algo, acepto un equivalente hasta 10% más caro</span>
      </label>
      <p className="flex gap-2 text-[0.95rem] text-tenue">
        <MapPin aria-hidden className="mt-0.5 size-4.5 shrink-0" />
        Paga una sola persona: tú.
      </p>
    </Pantalla>
  )
}

export function MedioPago() {
  const { s, haz } = useDemo()
  const p = s.pedido
  const [medio, setMedio] = useState<Medio>(p?.medio ?? 'credito')
  if (!p) return null
  const monto = montoAPagar(p.estimado, medio)
  return (
    <Pantalla
      titulo="¿Cómo pagas?"
      pie={
        <Boton icono={<Lock aria-hidden className="size-5" />} onClick={() => haz((x) => ir(elegirMedio(x, medio), 'pasarela'))}>
          Pagar <span className="cifras">{fmtDinero(monto)}</span>
        </Boton>
      }
    >
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
        <Tarjeta tono="rocio">
          <p className="font-bold">
            Reservamos <span className="cifras">{fmtDinero(reservaCredito(p.estimado))}</span> por si algún precio cambió.
          </p>
          <p>Se te cobrará solo lo que realmente cueste, y el resto se libera automáticamente.</p>
          <div className="mt-1 flex flex-col gap-1.5 rounded-xl bg-hoja p-3 text-[0.95rem]">
            <Renglon texto="Estimado" monto={fmtDinero(p.estimado)} />
            <Renglon texto={`Holgura de ${MARGEN_PORCENTAJE}%`} monto={fmtDinero(reservaCredito(p.estimado) - p.estimado)} />
            <Renglon texto="Se reserva" monto={fmtDinero(reservaCredito(p.estimado))} fuerte />
          </div>
        </Tarjeta>
      ) : (
        <Tarjeta tono="rocio">
          <p className="font-bold">
            Con débito el banco cobra al instante: se cobran <span className="cifras">{fmtDinero(p.estimado)}</span> al confirmar.
          </p>
          <p>Si el pedido sale por menos, te devolvemos la diferencia a la misma tarjeta cuando la farmacia lo arme.</p>
          <div className="mt-1 flex flex-col gap-1.5 rounded-xl bg-hoja p-3 text-[0.95rem]">
            <Renglon texto="Estimado" monto={fmtDinero(p.estimado)} />
            <Renglon texto="Se cobra ahora" monto={fmtDinero(p.estimado)} fuerte />
          </div>
        </Tarjeta>
      )}
      <p className="flex gap-2 text-[0.95rem] text-tenue">
        <Lock aria-hidden className="mt-0.5 size-4.5 shrink-0" />
        Pagas en Transbank. MATU nunca ve ni guarda los datos de tu tarjeta.
      </p>
    </Pantalla>
  )
}

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
        const msg = t.pedido?.medio === 'credito' ? 'Pago aprobado. Reservamos el monto y avisamos a la farmacia.' : 'Pago aprobado. Avisamos a la farmacia.'
        return avisar(pilaFamilia(t, ['seguimiento']), msg)
      })
    }, 1100)
    return () => window.clearTimeout(id)
  }, [procesando, haz])
  if (!p || !p.medio) return null
  const credito = p.medio === 'credito'
  return (
    <Pantalla
      titulo="Pasarela de pago simulada"
      encabezado={
        <header className="shrink-0 bg-[#1f2a37] px-4 py-3 text-white">
          <p className="font-bold">Pasarela de pago simulada</p>
          <p className="text-[0.95rem] opacity-85">Transbank, ambiente de prueba</p>
        </header>
      }
      cuerpoClase="bg-[#f3f4f6] text-[#1f2a37]"
    >
      <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-black/10">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[0.95rem]">
          <dt className="text-[#4b5563]">Comercio</dt>
          <dd className="text-right font-bold">MATU</dd>
          <dt className="text-[#4b5563]">Orden</dt>
          <dd className="cifras text-right">{p.numero}</dd>
          <dt className="text-[#4b5563]">{credito ? 'Monto a reservar' : 'Monto a cobrar'}</dt>
          <dd className="cifras text-right text-[1.3rem] font-bold">{fmtDinero(p.montoPagado)}</dd>
        </dl>
      </div>
      <div className="flex items-center gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-black/10">
        {credito ? <CreditCard aria-hidden className="size-7 shrink-0" /> : <Landmark aria-hidden className="size-7 shrink-0" />}
        <div className="min-w-0">
          <p className="font-bold">{credito ? 'Tarjeta de crédito de prueba' : 'Tarjeta de débito de prueba'}</p>
          <p className="cifras text-[#4b5563]">•••• •••• •••• 6623</p>
        </div>
      </div>
      {procesando !== null ? (
        <p role="status" className="flex items-center justify-center gap-2 py-4 font-bold">
          <LoaderCircle aria-hidden className="size-6 animate-spin" />
          Consultando al banco…
        </p>
      ) : (
        <div className="flex flex-col gap-2.5">
          <button
            type="button"
            onClick={() => setProcesando(true)}
            className="min-h-13 rounded-xl bg-[#1f2a37] px-4 font-bold text-white hover:bg-[#111827]"
          >
            Aprobar el pago (simulado)
          </button>
          <button
            type="button"
            onClick={() => setProcesando(false)}
            className="min-h-13 rounded-xl bg-white px-4 font-bold text-[#9f1c14] ring-2 ring-[#9f1c14]/70 ring-inset hover:bg-[#fef2f2]"
          >
            Simular que el banco lo rechaza
          </button>
          <button type="button" onClick={() => haz(volver)} className="min-h-12 font-bold text-[#1f2a37] underline underline-offset-4">
            Volver a MATU sin pagar
          </button>
        </div>
      )}
      <p className="text-center text-sm text-[#4b5563]">No se mueve dinero real. Los datos de tarjeta solo existen en Transbank.</p>
    </Pantalla>
  )
}

export function Rechazado() {
  const { s, haz } = useDemo()
  return (
    <Pantalla
      titulo="El pago no pasó"
      pie={
        <>
          <Boton onClick={() => haz(volver)}>Probar de nuevo</Boton>
          <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>
            Volver al inicio
          </Boton>
        </>
      }
    >
      <Tarjeta tono="pronto" className="items-start">
        <Sello tono="pronto">
          <TriangleAlert aria-hidden className="size-9" />
        </Sello>
        <h2 className="font-display text-[1.35rem] font-bold">El banco no aprobó el pago</h2>
        <p>Puede ser el cupo o un bloqueo del banco. No se te cobró nada.</p>
      </Tarjeta>
      <Nota>
        Tu pedido queda guardado. Si no lo pagas, la farmacia no lo prepara y nadie pierde dinero.
        {s.pedido && s.pedido.rechazos > 1 && ' Si sigue sin pasar, prueba con otra tarjeta.'}
      </Nota>
    </Pantalla>
  )
}

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

export function Seguimiento() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p || p.estado === 'borrador') {
    return (
      <Pantalla titulo="Pedido">
        <Nota>No hay un pedido en curso.</Nota>
      </Pantalla>
    )
  }
  const actual = etapa(p.estado)
  const cambios = p.lineas.filter((l) => l.resolucion === 'reemplazado' || l.resolucion === 'no_disponible')
  return (
    <Pantalla
      titulo={`Pedido de ${s.persona?.nombrePila ?? 'María'}`}
      pie={
        p.estado === 'entregado' ? (
          <Boton onClick={() => haz((x) => ir(x, 'entregado'))}>Ver cómo terminó</Boton>
        ) : (
          <button
            type="button"
            onClick={() => haz((x) => pilaComercio(x, p.estado === 'listo' || p.estado === 'en_camino' ? ['c-pedidos', 'c-codigo'] : ['c-pedidos']))}
            className="min-h-12 rounded-2xl border-2 border-dashed border-tenue/50 px-4 font-bold text-tenue hover:text-tinta"
          >
            Demo: ver qué hace la farmacia
          </button>
        )
      }
    >
      <ol className="flex flex-col">
        {PASOS.map((paso, i) => {
          const n = etapa(paso.e)
          const hecho = n <= actual
          const esActual = n === actual
          return (
            <li key={paso.e} className="relative flex gap-3 pb-4 last:pb-0">
              {i < PASOS.length - 1 && (
                <span aria-hidden className={`absolute top-8 bottom-0 left-[0.95rem] w-0.5 ${n < actual ? 'bg-pino' : 'bg-tinta/12'}`} />
              )}
              <span
                aria-hidden
                className={`relative z-10 grid size-8 shrink-0 place-items-center rounded-full ${
                  hecho ? 'bg-pino text-papel' : 'bg-hoja text-tenue ring-2 ring-tinta/15 ring-inset'
                } ${esActual ? 'shadow-[0_0_0_5px_var(--color-rocio)]' : ''}`}
              >
                {hecho ? <Check className="size-4.5" strokeWidth={3} /> : <span className="cifras text-sm font-bold">{i + 1}</span>}
              </span>
              <span className="min-w-0 pt-0.5">
                <span className={`block font-bold ${hecho ? '' : 'text-tenue'}`}>
                  {paso.titulo(p)}
                  {esActual && <span className="sr-only"> (ahora)</span>}
                </span>
                <span className="text-[0.95rem] text-tenue">
                  {hecho ? paso.detalle(p) : 'Pendiente'}
                  {hecho && p.hitos[paso.e] !== undefined && <span className="cifras">, a las {fmtHora(p.hitos[paso.e]!)}</span>}
                </span>
              </span>
            </li>
          )
        })}
      </ol>
      {(p.estado === 'listo' || p.estado === 'pagado' || p.estado === 'preparando') && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-rocio px-4 py-3">
          <span className="text-[0.95rem]">Código de retiro, lo muestra quien retira</span>
          <span className="digitos text-[1.5rem] font-bold tracking-[0.2em] text-pino">{p.codigoRetiro}</span>
        </div>
      )}
      {cambios.length > 0 && (
        <Tarjeta tono="atenta">
          <h2 className="font-bold">Cambios de la farmacia</h2>
          {cambios.map((l) => (
            <p key={l.insumoId} className="text-[0.95rem]">
              {l.resolucion === 'reemplazado' ? `${l.nombre}: cambiada por ${l.reemplazo?.nombre.toLowerCase()}.` : `${l.nombre}: no había. No se cobra.`}
            </p>
          ))}
        </Tarjeta>
      )}
      <Boleta p={p} />
    </Pantalla>
  )
}

export function Entregado() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p || p.estado !== 'entregado' || p.montoReal === null) return <Seguimiento />
  const dif = p.montoPagado - p.montoReal
  const panal = s.insumos.find((i) => i.id === 'panal-m')
  return (
    <Pantalla titulo="Pedido entregado" pie={<Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>Volver al inicio</Boton>}>
      <Tarjeta tono="ok" className="items-start">
        <span className="grid size-14 place-items-center rounded-full bg-ok text-ok-fondo">
          <CircleCheck aria-hidden className="size-8" />
        </span>
        <p className="font-display text-[1.35rem] font-bold">
          Entregado a las <span className="cifras">{fmtHora(p.hitos.entregado ?? s.ahora)}</span>
        </p>
      </Tarjeta>
      <p className="text-[1.1rem] leading-snug">
        {p.medio === 'credito' ? (
          <>
            Se cobraron <b className="cifras">{fmtDinero(p.montoReal)}</b>. Los <b className="cifras">{fmtDinero(dif)}</b> restantes ya se liberaron.
          </>
        ) : (
          <>
            Se cobraron <b className="cifras">{fmtDinero(p.montoReal)}</b>. Pagaste {fmtDinero(p.montoPagado)} y te devolvimos{' '}
            <b className="cifras">{fmtDinero(dif)}</b>.
          </>
        )}
      </p>
      <Boleta p={p} />
      {p.lineas
        .filter((l) => l.resolucion === 'reemplazado')
        .map((l) => (
          <p key={l.insumoId} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-atenta-fondo px-4 py-3 text-[0.95rem]">
            <span>
              <b>{l.nombre}</b>: {l.reemplazo?.nombre.toLowerCase()}
            </span>
            <span className="font-bold text-atenta">Cambio</span>
          </p>
        ))}
      {panal && p.sumadoAlStock && (
        <Nota titulo="Ya sumamos lo que llegó">
          Los pañales ahora alcanzan hasta el <span className="cifras">{fmtFecha(s.ahora + diasRestantes(panal) * DIA)}</span>. No tienes que anotar nada.
        </Nota>
      )}
    </Pantalla>
  )
}
