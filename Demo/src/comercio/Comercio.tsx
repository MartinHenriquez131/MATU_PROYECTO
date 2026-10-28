// Consola de Farmacia Los Aromos (ADR-027): la cola del día a la izquierda y el pedido elegido a la
// derecha, con sus tres pasos: apartado, preparar y retiro. El comercio ve solo productos,
// cantidades, la referencia y el código: ningún nombre ni dirección de la familia.
import { useState, type ReactNode } from 'react'
import { Check, CircleCheck, PackageCheck, Store } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { avisar, empezarPreparacion, etapa, ir, listoParaRetiro, marcarEntregado, marcarLinea, pantallaComercio, pilaComercio, validarCodigo } from '../demo/logica'
import { COMERCIO, REF_APARTADO } from '../demo/datos'
import { diaDeLaSemana, fmtDinero, fmtFecha, fmtHora, productosDelComercio } from '../demo/calculos'
import type { Estado } from '../demo/tipos'
import { Acciones, Boton, CampoTexto, Etiqueta, Nota, PreciosDeEjemplo, type Tono } from '../components/Ui'

type Fase = 'pagado' | 'apartado' | 'preparando' | 'listo' | 'en_camino' | 'entregado'

const ESTADO: Record<Fase, { texto: string; tono: Tono; forma: 'llena' | 'media' | 'vacia' }> = {
  pagado: { texto: 'Por preparar', tono: 'pronto', forma: 'llena' },
  apartado: { texto: 'Apartado', tono: 'atenta', forma: 'media' },
  preparando: { texto: 'Preparando', tono: 'atenta', forma: 'media' },
  listo: { texto: 'Listo para retiro', tono: 'ok', forma: 'vacia' },
  en_camino: { texto: 'Retirado', tono: 'neutro', forma: 'vacia' },
  entregado: { texto: 'Retirado', tono: 'neutro', forma: 'vacia' },
}

function ChipEstado({ e }: { e: Fase }) {
  const x = ESTADO[e]
  return (
    <Etiqueta tono={x.tono}>
      <span aria-hidden className={`grid size-2.5 place-items-center rounded-full ${x.forma === 'llena' ? 'bg-current' : 'border-2 border-current'}`}>
        {x.forma === 'media' && <span className="size-0.5 rounded-full bg-current" />}
      </span>
      {x.texto}
    </Etiqueta>
  )
}

const pedidoPagado = (s: Estado) => (s.pedido && etapa(s.pedido.estado) >= etapa('pagado') ? s.pedido : null)
const cuenta = (n: number) => `${n} ${n === 1 ? 'producto' : 'productos'}`

// ---------- cola ----------

function Cola({ apartadoElegido, elegirApartado }: { apartadoElegido: boolean; elegirApartado: (v: boolean) => void }) {
  const { s, haz } = useDemo()
  const p = pedidoPagado(s)
  const abrir = () => {
    elegirApartado(false)
    if (!p) return
    if (p.estado === 'pagado') haz((x) => pilaComercio(x, ['c-pedidos']))
    else if (p.estado === 'preparando') haz((x) => pilaComercio(x, ['c-pedidos', 'c-preparar']))
    else haz((x) => pilaComercio(x, ['c-pedidos', 'c-codigo']))
  }
  const fila = 'flex w-full flex-col gap-1 border-l-4 px-4 py-3 text-left'
  return (
    <section aria-labelledby="titulo-pagina" className="flex flex-col gap-3">
      <h1 id="titulo-pagina" tabIndex={-1} className="titular text-3xl outline-none">
        Pedidos de hoy
      </h1>
      <ul className="flex flex-col gap-2" aria-label="Pedidos de hoy">
        {p && (
          <li>
            <button type="button" onClick={abrir} aria-current={apartadoElegido ? undefined : 'true'} className={`${fila} bg-hoja ${apartadoElegido ? 'border-transparent' : 'border-pino ring-2 ring-pino ring-inset'}`}>
              <span className="flex flex-wrap items-center justify-between gap-2">
                <span className="cifras font-bold">#{p.numero}</span>
                <ChipEstado e={p.estado as Fase} />
              </span>
              <span className="text-base">{cuenta(p.lineas.length)}</span>
              <span className="text-sm text-tenue">Retiro {COMERCIO.ventana}</span>
            </button>
          </li>
        )}
        <li>
          <button
            type="button"
            onClick={() => elegirApartado(true)}
            aria-current={apartadoElegido ? 'true' : undefined}
            className={`${fila} bg-hoja ${apartadoElegido ? 'border-pino ring-2 ring-pino ring-inset' : 'border-transparent'}`}
          >
            <span className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-bold">
                Ref. <span className="digitos">{REF_APARTADO}</span>
              </span>
              <ChipEstado e="apartado" />
            </span>
            <span className="text-base">{cuenta(2)}, sin pagar</span>
            <span className="text-sm text-tenue">
              Se libera a las <span className="cifras">{fmtHora(s.ahora + 15)}</span>
            </span>
          </button>
        </li>
        <li className={`${fila} border-transparent bg-hoja/60`}>
          <span className="flex flex-wrap items-center justify-between gap-2">
            <span className="cifras font-bold">#4819</span>
            <ChipEstado e="entregado" />
          </span>
          <span className="text-base">{cuenta(4)}</span>
          <span className="text-sm text-tenue">
            Retirado a las <span className="cifras">13:20</span>
          </span>
        </li>
      </ul>
    </section>
  )
}

// ---------- detalle ----------

const PASOS = ['Apartado', 'Preparar', 'Retiro']

function Pasos({ paso }: { paso: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2" aria-label="Pasos del pedido">
      {PASOS.map((t, i) => {
        const n = i + 1
        const estado = n < paso ? 'hecho' : n === paso ? 'ahora' : 'falta'
        return (
          <li key={t} className="flex items-center gap-2" aria-current={estado === 'ahora' ? 'step' : undefined}>
            {i > 0 && <span aria-hidden className={`h-0.5 w-6 angosto:hidden ${n <= paso ? 'bg-pino' : 'bg-tinta/15'}`} />}
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
    <div className="flex flex-col gap-5">
      <section aria-labelledby="detalle-t" className="@container flex flex-col gap-5 bg-hoja px-4 @3xl:px-8 py-5 ring-1 ring-linea">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div>
            <h2 id="detalle-t" data-foco="detalle" tabIndex={-1} className="text-2xl font-bold outline-none">
              Pedido #{p.numero}
            </h2>
            <p className="text-tenue">Retiro hoy {COMERCIO.ventana}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-tenue">Tus productos</p>
            <p className="cifras text-2xl font-bold">{fmtDinero(productosDelComercio(p))}</p>
          </div>
        </div>
        <Pasos paso={paso} />
        <p className="tabular-nums">
          Apartado a las {fmtHora(p.hitos.apartado ?? 0)} y pagado a las {fmtHora(p.hitos.pagado ?? 0)}.
        </p>
        {children}
        <p className="text-base text-tenue">Ves solo productos y cantidades. No ves nombres ni direcciones.</p>
      </section>
      <PreciosDeEjemplo />
    </div>
  )
}

function Lineas({ editable = false }: { editable?: boolean }) {
  const { s, haz } = useDemo()
  const p = s.pedido!
  return (
    <ul className="flex flex-col divide-y divide-linea border-y border-linea">
      {p.lineas.map((l) => (
        <li key={l.insumoId} className="flex flex-col gap-2 py-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <span className="font-bold">
              {l.nombre} <span className="font-normal text-tenue tabular-nums">× {l.paquetes}</span>
            </span>
            {l.enComercio === 'listo' && (
              <Etiqueta tono="ok">
                <Check aria-hidden className="size-4" strokeWidth={3} />
                Listo
              </Etiqueta>
            )}
            {l.enComercio === 'ya_no_esta' && <Etiqueta>Ya no está</Etiqueta>}
          </div>
          {l.enComercio === 'ya_no_esta' && <p className="text-base text-tenue">Lo buscamos en otro local. La familia no paga más.</p>}
          {editable && l.enComercio === 'pendiente' && (
            <Acciones>
              <Boton variante="secundario" onClick={() => haz((x) => marcarLinea(x, l.insumoId, 'listo'))}>
                Listo
              </Boton>
              <Boton variante="secundario" onClick={() => haz((x) => avisar(marcarLinea(x, l.insumoId, 'ya_no_esta'), 'Avisamos a MATU. Lo buscamos en otro local.'))}>
                Ya no está
              </Boton>
            </Acciones>
          )}
        </li>
      ))}
    </ul>
  )
}

function Apartado() {
  const { s } = useDemo()
  return (
    <section aria-labelledby="ref-t" className="flex flex-col gap-4 bg-hoja px-4 @3xl:px-8 py-5 ring-1 ring-linea">
      <h2 id="ref-t" data-foco="detalle" tabIndex={-1} className="text-2xl font-bold outline-none">
        Ref. <span className="digitos">{REF_APARTADO}</span>
      </h2>
      <p className="tabular-nums">
        Apartado para una familia que todavía no paga. Si no paga antes de las {fmtHora(s.ahora + 15)}, se libera solo.
      </p>
      <ul className="flex flex-col divide-y divide-linea border-y border-linea">
        <li className="py-3 font-bold">
          Pañal adulto talla L x20 <span className="font-normal text-tenue">× 1</span>
        </li>
        <li className="py-3 font-bold">
          Crema protectora 200 g <span className="font-normal text-tenue">× 1</span>
        </li>
      </ul>
      <p className="text-base text-tenue">No es un pedido todavía: no tiene número ni acciones.</p>
    </section>
  )
}

function Resumen() {
  const { s, haz } = useDemo()
  const p = pedidoPagado(s)
  if (!p) {
    return (
      <div className="flex flex-col items-start gap-3 bg-hoja px-6 py-6 ring-1 ring-linea">
        <h2 data-foco="detalle" tabIndex={-1} className="text-xl font-bold outline-none">
          No hay pedidos hoy.
        </h2>
        <p className="text-tenue">Cuando una familia paga un pedido, aparece en la cola.</p>
      </div>
    )
  }
  const paso = p.estado === 'pagado' || p.estado === 'preparando' ? 2 : p.estado === 'listo' ? 3 : 4
  return (
    <Detalle paso={paso}>
      <Lineas />
      {p.estado === 'entregado' ? (
        <Nota tono="ok" titulo={`Entregado a las ${fmtHora(p.hitos.entregado ?? s.ahora)}`}>
          La familia ya lo ve en su pedido.
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
  const pendientes = p.lineas.some((l) => l.enComercio === 'pendiente')
  return (
    <Detalle paso={2}>
      <Lineas editable />
      <Acciones>
        <Boton
          icono={<PackageCheck aria-hidden className="size-5" />}
          disabled={pendientes}
          onClick={() => haz((x) => avisar(pilaComercio(listoParaRetiro(x), ['c-pedidos']), 'Listo para retiro. Avisamos a la familia.'))}
        >
          Marcar listo para retiro
        </Boton>
        {pendientes && <span className="text-tenue">Marca cada producto para seguir.</span>}
      </Acciones>
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
    if (codigo !== p.codigoRetiro) return setError('Ese código no es. Revisa los cuatro números.')
    setError(null)
    haz((x) => avisar(validarCodigo(x), 'Código válido. Entrega el pedido.'))
  }
  return (
    <Detalle paso={validado ? 4 : 3}>
      <Lineas />
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
            className="max-w-3xs [&_input]:digitos [&_input]:min-h-16 [&_input]:text-center [&_input]:text-3xl [&_input]:font-bold [&_input]:tracking-widest"
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
            <Boton onClick={() => haz((x) => avisar(pilaComercio(marcarEntregado(x), ['c-pedidos']), 'Entregado. Se avisó a la familia.'))}>Marcar como entregado</Boton>
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
  const [apartadoElegido, setApartadoElegido] = useState(false)
  let detalle: ReactNode = <Resumen />
  if (apartadoElegido) detalle = <Apartado />
  else if (p && top.id === 'c-preparar') detalle = <Preparar />
  else if (p && top.id === 'c-codigo') detalle = <Codigo />
  return (
    <div className="flex flex-1 flex-col">
      <header className="bg-tinta text-papel [&_:focus-visible]:outline-miel">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-4 @3xl:px-10 py-3">
          <span className="flex items-center gap-2.5 font-bold">
            <Store aria-hidden className="size-6" />
            {COMERCIO.nombreFicticio}
          </span>
          <span className="opacity-85">Pedidos de MATU</span>
          <span className="flex-1" />
          <span className="opacity-85 tabular-nums">
            {diaDeLaSemana(s.ahora)} {fmtFecha(s.ahora)}, {fmtHora(s.ahora)}
          </span>
        </div>
      </header>
      <main id="contenido" tabIndex={-1} className="@container/main px-4 angosto:px-2 @3xl:px-10 pt-6 pb-16 outline-none">
        <div className="mx-auto grid max-w-7xl grid-cols-1 items-start gap-x-8 gap-y-8 @3xl/main:grid-cols-[19rem_minmax(0,1fr)]">
          <Cola apartadoElegido={apartadoElegido} elegirApartado={setApartadoElegido} />
          <div key={`${top.n}-${apartadoElegido}`} className="min-w-0">
            {detalle}
          </div>
        </div>
      </main>
    </div>
  )
}
