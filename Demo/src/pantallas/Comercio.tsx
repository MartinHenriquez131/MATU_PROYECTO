// Vista de comercio: un computador compartido en la farmacia. Ve el nombre de pila, nunca la
// dirección ni nada de la ficha.
import { useState } from 'react'
import { CircleCheck, PackageCheck, Store } from 'lucide-react'
import { useDemo } from '../demo/estado'
import {
  avisar,
  cerrarMonto,
  empezarPreparacion,
  etapa,
  ir,
  marcarEntregado,
  pedidoHasta,
  pilaComercio,
  resolverLinea,
  validarCodigo,
} from '../demo/logica'
import { BOLETA_EJEMPLO, COMERCIO, EQUIVALENTES, MONTO_REAL_EJEMPLO } from '../demo/datos'
import { TOPE_EQUIVALENTE_PORCENTAJE, fmtDinero, leerPesos, topeEquivalente } from '../demo/calculos'
import type { Pedido } from '../demo/tipos'
import { Pantalla } from '../components/Pantalla'
import { Boton, CampoTexto, Etiqueta, Nota, Tarjeta } from '../components/Ui'

const tope = (p: Pedido) => p.montoPagado

function EncabezadoComercio({ titulo, volver }: { titulo: string; volver?: boolean }) {
  return volver ? undefined : (
    <header className="flex min-h-15 shrink-0 items-center gap-3 border-b border-linea bg-hoja px-5">
      <Store aria-hidden className="size-6 shrink-0 text-pino" />
      <p className="min-w-0 font-display text-[1.15rem] font-bold" aria-hidden>
        {titulo}
      </p>
    </header>
  )
}

const ESTADO_COMERCIO: Record<string, { texto: string; tono: 'pronto' | 'atenta' | 'ok' | 'neutro' }> = {
  pagado: { texto: 'Por preparar', tono: 'pronto' },
  preparando: { texto: 'Preparando', tono: 'atenta' },
  listo: { texto: 'Listo para retiro', tono: 'ok' },
  en_camino: { texto: 'Retirado', tono: 'ok' },
  entregado: { texto: 'Entregado', tono: 'neutro' },
}

export function CPedidos() {
  const { s, haz } = useDemo()
  const p = s.pedido && etapa(s.pedido.estado) >= etapa('pagado') ? s.pedido : null
  const accion = () => {
    if (!p) return
    if (p.estado === 'pagado') haz((x) => ir(empezarPreparacion(x), 'c-preparar'))
    else if (p.estado === 'preparando') haz((x) => ir(x, 'c-preparar'))
    else if (p.estado === 'listo' || p.estado === 'en_camino') haz((x) => ir(x, 'c-codigo'))
  }
  const textoAccion = p
    ? { pagado: `Preparar pedido #${p.numero}`, preparando: `Seguir con #${p.numero}`, listo: `Entregar #${p.numero}`, en_camino: `Entregar #${p.numero}` }[
        p.estado as 'pagado'
      ]
    : null
  return (
    <Pantalla
      titulo={`${COMERCIO.nombre} · Hoy`}
      encabezado={<EncabezadoComercio titulo={`${COMERCIO.nombre} · Hoy`} />}
      pie={textoAccion && <Boton onClick={accion}>{textoAccion}</Boton>}
    >
      <ul className="flex flex-col gap-2.5">
        {p && (
          <li className="flex flex-wrap items-center justify-between gap-2 rounded-[1.2rem] border-l-[6px] border-pino bg-hoja p-4 ring-1 ring-linea">
            <span className="min-w-0">
              <span className="cifras block font-bold">
                #{p.numero} · {p.lineas.reduce((n, l) => n + l.paquetes, 0)} productos
              </span>
              <span className="text-[0.95rem] text-tenue">Para {s.persona?.nombrePila ?? 'María'} · retiro {COMERCIO.ventana}</span>
            </span>
            <Etiqueta tono={ESTADO_COMERCIO[p.estado].tono}>{ESTADO_COMERCIO[p.estado].texto}</Etiqueta>
          </li>
        )}
        <li className="flex flex-wrap items-center justify-between gap-2 rounded-[1.2rem] bg-hoja p-4 ring-1 ring-linea">
          <span>
            <span className="cifras block font-bold">#4822 · 3 productos</span>
            <span className="text-[0.95rem] text-tenue">Retiro entre 18:00 y 19:00</span>
          </span>
          <Etiqueta tono="atenta">Preparando</Etiqueta>
        </li>
        <li className="flex flex-wrap items-center justify-between gap-2 rounded-[1.2rem] bg-hoja p-4 ring-1 ring-linea">
          <span>
            <span className="cifras block font-bold">#4819 · 4 productos</span>
            <span className="text-[0.95rem] text-tenue">Retirado 15:20</span>
          </span>
          <Etiqueta tono="ok">Listo</Etiqueta>
        </li>
      </ul>
      {!p && (
        <>
          <Nota>El pedido de {s.persona?.nombrePila ?? 'María'} aparece aquí cuando la familia lo paga.</Nota>
          <button
            type="button"
            onClick={() => haz((x) => pilaComercio(pedidoHasta(x, 'pagado'), ['c-pedidos']))}
            className="min-h-12 rounded-2xl border-2 border-dashed border-tenue/50 px-4 font-bold text-tenue hover:text-tinta"
          >
            Demo: la familia paga el pedido
          </button>
        </>
      )}
    </Pantalla>
  )
}

export function CPreparar() {
  const { s, haz } = useDemo()
  const p = s.pedido
  if (!p) return null
  const pendientes = p.lineas.some((l) => l.resolucion === 'sin_stock')
  return (
    <Pantalla
      titulo={`Pedido #${p.numero} · para ${s.persona?.nombrePila ?? 'María'}`}
      pie={
        <Boton disabled={pendientes} onClick={() => haz((x) => ir(x, 'c-monto'))}>
          {pendientes ? 'Resuelve lo que falta para seguir' : 'Ingresar el monto real'}
        </Boton>
      }
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-2xl bg-rocio px-4 py-3">
        <span>Tope autorizado</span>
        <span className="cifras text-[1.3rem] font-bold">{fmtDinero(tope(p))}</span>
      </div>
      <ul className="flex flex-col gap-2.5">
        {p.lineas.map((l) => {
          const eq = EQUIVALENTES[l.insumoId]
          return (
            <li key={l.insumoId} className="flex flex-col gap-2 rounded-[1.2rem] bg-hoja p-4 ring-1 ring-linea">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="min-w-0">
                  <span className="block font-bold">
                    {l.nombre} <span className="cifras font-normal text-tenue">× {l.paquetes}</span>
                  </span>
                  {l.resolucion === 'reemplazado' && <span className="text-[0.95rem] text-tenue">Por: {l.reemplazo?.nombre}</span>}
                  {l.resolucion === 'sin_stock' && (
                    <span className="text-[0.95rem] text-tenue">
                      {p.aceptaEquivalente ? `Acepta equivalente hasta +${TOPE_EQUIVALENTE_PORCENTAJE}%` : 'No acepta equivalentes'}
                    </span>
                  )}
                </span>
                {l.resolucion === 'ok' && <Etiqueta tono="ok">Listo</Etiqueta>}
                {l.resolucion === 'sin_stock' && <Etiqueta tono="pronto">Sin stock</Etiqueta>}
                {l.resolucion === 'reemplazado' && <Etiqueta tono="atenta">Reemplazado</Etiqueta>}
                {l.resolucion === 'no_disponible' && <Etiqueta>No disponible</Etiqueta>}
              </div>
              {l.resolucion === 'sin_stock' && (
                <div className="flex flex-wrap gap-2 [&>*]:min-w-[min(100%,9rem)] [&>*]:flex-1">
                  <Boton variante="secundario" onClick={() => haz((x) => resolverLinea(x, l.insumoId, 'no_disponible'))}>
                    No disponible
                  </Boton>
                  {p.aceptaEquivalente && eq && eq.precio <= topeEquivalente(l.precio) && (
                    <Boton onClick={() => haz((x) => resolverLinea(x, l.insumoId, 'reemplazado'))}>
                      Reemplazar · <span className="cifras">{fmtDinero(eq.precio)}</span>
                    </Boton>
                  )}
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <p className="text-[0.95rem] text-tenue">Ves el nombre de pila de quien recibe. La dirección solo la ve quien entrega.</p>
    </Pantalla>
  )
}

export function CMonto() {
  const { s, haz } = useDemo()
  const p = s.pedido
  const [monto, setMonto] = useState(fmtDinero(MONTO_REAL_EJEMPLO).slice(1))
  const [boleta, setBoleta] = useState(BOLETA_EJEMPLO)
  const [error, setError] = useState<string | null>(null)
  if (!p) return null
  const max = tope(p)
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
    <Pantalla titulo={`Cerrar pedido #${p.numero}`} pie={<Boton icono={<PackageCheck aria-hidden className="size-5" />} onClick={cerrar}>Listo para retiro</Boton>}>
      <CampoTexto
        etiqueta="Total de la boleta, en pesos"
        inputMode="numeric"
        value={monto}
        onChange={(e) => {
          setMonto(e.target.value)
          setError(null)
        }}
        className={`cifras min-h-13 w-full rounded-2xl bg-hoja px-4 py-3 text-[1.4rem] font-bold ring-2 ring-inset outline-none focus-visible:ring-pino ${error ? 'ring-pronto' : 'ring-linea'}`}
        error={error}
        ayuda={`Dentro del tope autorizado de ${fmtDinero(max)}.`}
      />
      <CampoTexto etiqueta="N° de boleta" inputMode="numeric" value={boleta} onChange={(e) => setBoleta(e.target.value)} />
      <Nota>El total se carga a la cuenta de MATU. La familia ve este mismo monto en su pedido.</Nota>
    </Pantalla>
  )
}

export function CCodigo() {
  const { s, haz } = useDemo()
  const p = s.pedido
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState<string | null>(null)
  if (!p) return null
  const validado = p.estado === 'en_camino' || p.estado === 'entregado'
  const validar = () => {
    if (codigo !== p.codigoRetiro) return setError('Ese código no coincide. Pídele a quien retira que lo revise.')
    setError(null)
    haz(validarCodigo)
  }
  return (
    <Pantalla
      titulo={`Entregar #${p.numero}`}
      pie={
        validado ? (
          p.estado === 'en_camino' && (
            <Boton
              onClick={() =>
                haz((x) => avisar(pilaComercio(marcarEntregado(x), ['c-pedidos']), 'Entregado. Se cobró el monto real y se avisó a la familia.'))
              }
            >
              Marcar como entregado
            </Boton>
          )
        ) : (
          <Boton onClick={validar}>Validar código</Boton>
        )
      }
    >
      {!validado ? (
        <>
          <form
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
              className={`cifras min-h-16 w-full rounded-2xl bg-hoja px-4 text-center text-[2rem] font-bold tracking-[0.4em] ring-2 ring-inset outline-none focus-visible:ring-pino ${error ? 'ring-pronto' : 'ring-linea'}`}
              error={error}
              ayuda="Es de un solo uso y vence en 90 minutos."
            />
          </form>
          <p className="rounded-2xl border-2 border-dashed border-tenue/40 px-4 py-3 text-[0.95rem] text-tenue">
            En la demo, el código es <span className="cifras font-bold text-tinta">{p.codigoRetiro}</span>.
          </p>
        </>
      ) : (
        <Tarjeta tono="ok" className="items-center text-center">
          <CircleCheck aria-hidden className="size-12 text-ok" />
          <p className="font-display text-[1.3rem] font-bold">Código válido</p>
          <p>{p.estado === 'entregado' ? 'El pedido ya se entregó.' : 'Entrega el pedido y márcalo cuando llegue a la casa.'}</p>
        </Tarjeta>
      )}
      <p className="text-[0.95rem] text-tenue">En el semestre, el retiro y la entrega se marcan desde esta vista.</p>
    </Pantalla>
  )
}
