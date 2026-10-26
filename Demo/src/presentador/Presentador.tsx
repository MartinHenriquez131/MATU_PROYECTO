// Panel del presentador: una franja delgada arriba y un cajón lateral con la guía. No es parte de
// MATU: es la guía para mostrarla. Se oculta con el modo presentación.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Eye,
  Monitor,
  Moon,
  RotateCcw,
  Server,
  ServerOff,
  Store,
  Sun,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react'
import { useDemo, type Cambio } from '../demo/estado'
import { CAPAS, ESCENAS, ESCENAS_REALES, escenaActual, prepararEscena } from '../demo/escenas'
import {
  abrirRelevo,
  accesoDelRelevo,
  estadoInicial,
  etapa,
  pantallaComercio,
  pantallaFamilia,
  pasarMinutos,
  pedidoHasta,
  pilaComercio,
  pilaFamilia,
  rodrigoEdita,
  ultimoAcceso,
} from '../demo/logica'
import { TEXTO_CAMPO, TEXTO_RODRIGO } from '../demo/datos'
import { totalVencido } from '../demo/calculos'
import { VIGENCIA_MINUTOS } from '../demo/textos-pedido'
import type { Estado, Rol } from '../demo/tipos'
import { useBackend } from '../datos/backend'
import { usePresentador, type Tema } from './contexto'

// ---------- escenas ----------

export function useEscenas() {
  const { s, haz } = useDemo()
  const actual = escenaActual(s)
  const [ultima, setUltima] = useState<string | null>(actual)
  useEffect(() => {
    if (actual) setUltima(actual)
  }, [actual])
  const ref = actual ?? ultima
  const indice = ref ? ESCENAS.findIndex((e) => e.id === ref) : -1
  const ir = useCallback((id: string) => haz((x) => prepararEscena(x, id)), [haz])
  const siguiente = () => ir(ESCENAS[Math.min(ESCENAS.length - 1, indice + 1)].id)
  const anterior = () => ir(ESCENAS[Math.max(0, indice - 1)].id)
  return { actual, indice, ir, siguiente, anterior, escena: indice >= 0 ? ESCENAS[indice] : null }
}

function useEsReal() {
  const b = useBackend()
  return (id: string) => b.modo === 'real' && ESCENAS_REALES.has(id)
}

// ---------- ayudas de la escena: lo que solo existe en la demo ----------

interface Ayuda {
  id: string
  texto: string
  /** Rótulo corto para la franja bajo 90 rem, donde no cabe el largo. */
  corto?: string
  dato?: string
  accion?: Cambio
}

function ayudas(s: Estado): Ayuda[] {
  const r: Ayuda[] = []
  const p = s.pedido
  const pagado = !!p && etapa(p.estado) >= etapa('pagado')
  if (s.rol === 'relevo') {
    const a = accesoDelRelevo(s)
    if (a && s.relevo.fase === 'pin') r.push({ id: 'pin', texto: `PIN que dictó ${s.cuenta?.nombre || 'Carmen'}`, corto: 'PIN', dato: a.pin })
    return r
  }
  if (s.rol === 'comercio') {
    const id = pantallaComercio(s).id
    if (!pagado) r.push({ id: 'pagar', texto: 'La familia paga el pedido', accion: (x) => pilaComercio(pedidoHasta(x, 'pagado'), ['c-pedidos']) })
    if (id === 'c-codigo' && p?.estado === 'listo') r.push({ id: 'codigo', texto: 'Código que muestra quien retira', corto: 'Código', dato: p.codigoRetiro })
    // Mientras se muestra el código de retiro, la vista de la familia no hace falta y no cabría.
    if (pagado && p && !r.some((x) => x.id === 'codigo')) r.push({ id: 'familia', texto: 'Ver lo que ve la familia', accion: (x) => pilaFamilia(x, [x.pedido?.estado === 'entregado' ? 'entregado' : 'seguimiento']) })
    return r
  }
  const top = pantallaFamilia(s).id
  if (top === 'completar' && s.borrador) {
    const b = s.borrador
    const yaGuardo = s.ficha[b.campo].version !== b.versionBase
    r.push(
      yaGuardo
        ? { id: 'rodrigo', texto: `Rodrigo ya guardó «${TEXTO_CAMPO[b.campo].titulo}». Ahora guarda Carmen.` }
        : { id: 'rodrigo', texto: 'Rodrigo guarda este campo', accion: (x) => (x.borrador ? rodrigoEdita(x, x.borrador.campo, TEXTO_RODRIGO) : x) },
    )
  }
  if (top === 'enlace-pin' || top === 'enlaces' || top === 'quien-vio') {
    const a = ultimoAcceso(s)
    if (a) r.push({ id: 'abrir', texto: `Abrir como ${a.nombre}`, accion: (x) => abrirRelevo(x, a.id) })
  }
  if (top === 'pedido' && p?.estado === 'apartado' && !totalVencido(p, s.ahora)) {
    r.push({ id: 'vence', texto: `Pasan ${VIGENCIA_MINUTOS} minutos`, accion: (x) => pasarMinutos(x, VIGENCIA_MINUTOS + 1) })
  }
  if (top === 'seguimiento' && pagado && p?.estado !== 'entregado') {
    r.push({
      id: 'farmacia',
      texto: 'Ver qué hace la farmacia',
      accion: (x) => pilaComercio(x, x.pedido && (x.pedido.estado === 'listo' || x.pedido.estado === 'en_camino') ? ['c-pedidos', 'c-codigo'] : ['c-pedidos']),
    })
  }
  return r
}

function ListaAyudas({ compacta = false }: { compacta?: boolean }) {
  const { s, haz } = useDemo()
  const lista = ayudas(s)
  if (!lista.length) return null
  return (
    <ul className={`flex flex-wrap items-center ${compacta ? 'gap-2' : 'flex-col items-stretch gap-2'}`} aria-label="Ayudas de esta escena">
      {lista.map((a) => (
        <li key={a.id}>
          {a.accion ? (
            <button
              type="button"
              onClick={() => haz(a.accion!)}
              className={`rounded-lg border-2 border-dashed border-tenue/50 px-3 text-left font-bold text-tinta hover:border-pino hover:text-pino ${compacta ? 'min-h-10 text-sm' : 'min-h-11 w-full'}`}
            >
              {a.texto}
            </button>
          ) : (
            <p className={`flex flex-wrap items-center gap-x-2 rounded-lg bg-rocio px-3 ${compacta ? 'min-h-10 text-sm' : 'min-h-11'}`}>
              {compacta && a.corto ? (
                <>
                  <span className="@min-[90rem]:hidden">{a.corto}</span>
                  <span className="hidden @min-[90rem]:inline">{a.texto}</span>
                </>
              ) : (
                <span>{a.texto}</span>
              )}
              {a.dato && <b className="digitos text-lg tracking-widest text-pino">{a.dato}</b>}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

// ---------- piezas ----------

/**
 * Aviso de piloto académico (figura legal del piloto, sección 4.1): se ve siempre, en las tres
 * apps, en modo presentación y con el texto al 200%. En la franja, bajo 90 rem, se parte en dos
 * líneas para que la franja siga en una. Solo, en modo presentación, va a 17 px.
 */
export function Distintivo({ flotante = false }: { flotante?: boolean }) {
  return (
    <span
      data-distintivo={flotante ? undefined : 'franja'}
      className={`inline-flex items-center gap-2 px-3 py-1 font-bold text-tenue ${
        flotante
          ? // Flotante: puede partirse en dos líneas y nunca es más ancho que la pantalla (WCAG 1.4.10).
            'min-w-0 rounded-2xl bg-hoja text-base leading-snug shadow-md ring-1 ring-linea'
          : 'max-w-44 shrink-0 rounded-xl bg-tinta/7 text-sm leading-tight @min-[90rem]:max-w-none @min-[90rem]:rounded-full'
      }`}
    >
      <span aria-hidden className="size-2 shrink-0 rounded-full bg-miel" />
      Piloto académico con datos de prueba
    </span>
  )
}

const ROLES: { rol: Rol; texto: string; quien: string; Icono: typeof UserRound }[] = [
  { rol: 'familia', texto: 'Familia', quien: 'Carmen', Icono: UsersRound },
  { rol: 'relevo', texto: 'Relevo', quien: 'Rosa', Icono: UserRound },
  { rol: 'comercio', texto: 'Comercio', quien: 'Farmacia', Icono: Store },
]

function useCambiarRol() {
  const { haz } = useDemo()
  return (rol: Rol) =>
    haz((x) => {
      if (x.rol === rol) return x
      if (rol === 'relevo') {
        // Si Rosa ya tenía la página abierta, vuelve a ella: al montarse se revalida el enlace,
        // y si Carmen lo cortó, ya no ve la ficha. Antes se reiniciaba siempre en el PIN.
        return x.relevo.token && accesoDelRelevo(x) ? { ...x, rol } : abrirRelevo(x)
      }
      return { ...x, rol }
    })
}

function SelectorRol({ compacto = false }: { compacto?: boolean }) {
  const { s } = useDemo()
  const cambiar = useCambiarRol()
  return (
    <fieldset className="min-w-0">
      <legend className={compacto ? 'sr-only' : 'mb-2 font-bold'}>Ver como</legend>
      <div className={`flex flex-wrap gap-1 rounded-xl bg-tinta/6 p-1 ${compacto ? '' : ''}`}>
        {ROLES.map(({ rol, texto, quien, Icono }) => {
          const on = s.rol === rol
          return (
            <label
              key={rol}
              className={`flex min-h-10 flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2.5 text-sm has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-pino ${
                on ? 'bg-hoja font-bold text-tinta shadow-sm' : 'text-tenue hover:text-tinta'
              }`}
            >
              <input type="radio" name={compacto ? 'rol-franja' : 'rol-cajon'} className="sr-only" checked={on} onChange={() => cambiar(rol)} />
              <Icono aria-hidden className={`size-4.5 shrink-0 ${compacto ? 'hidden @min-[90rem]:block' : ''}`} />
              <span className="whitespace-nowrap">
                {texto}
                {/* En la franja va solo el rol, para que quepa en una línea; en la guía, también quién es. */}
                {!compacto && <span className="font-normal text-tenue">, {quien}</span>}
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

function EtiquetaModo({ real }: { real: boolean }) {
  return real ? (
    <span className="rounded-full bg-ok-fondo px-2 py-0.5 text-xs font-bold text-ok">Real</span>
  ) : (
    <span className="rounded-full px-2 py-0.5 text-xs font-bold text-tenue ring-1 ring-linea ring-inset">Simulado</span>
  )
}

function NavEscena() {
  const { s } = useDemo()
  const { indice, escena, siguiente, anterior } = useEscenas()
  const esReal = useEsReal()
  const btn = 'grid size-10 shrink-0 place-items-center rounded-lg text-tinta hover:bg-tinta/7 disabled:opacity-35'
  return (
    <div className="flex min-w-0 items-center gap-1" role="group" aria-label="Escenas">
      <button type="button" className={btn} onClick={anterior} disabled={indice <= 0} aria-label="Escena anterior" title="Escena anterior ([ o Re Pág)">
        <ChevronLeft aria-hidden className="size-5" />
      </button>
      <p className="flex min-w-0 flex-wrap items-center gap-x-2 px-1" aria-live="polite">
        <span className="cifras text-sm text-tenue">
          {indice + 1} de {ESCENAS.length}
        </span>
        <span className="font-bold">{escena?.titulo ?? 'Fuera del guion'}</span>
        {escena && <EtiquetaModo real={esReal(escena.id)} />}
        {s.texto200 && escena?.id !== 'texto-200' && <span className="rounded-full bg-rocio px-2 py-0.5 text-sm font-bold text-pino">Texto al 200%</span>}
      </p>
      <button type="button" className={btn} onClick={siguiente} disabled={indice >= ESCENAS.length - 1} aria-label="Escena siguiente" title="Escena siguiente (] o Av Pág)">
        <ChevronRight aria-hidden className="size-5" />
      </button>
    </div>
  )
}

/** La dirección del relevo, para que se vea que el token se borra después del canje. */
function DireccionRelevo() {
  const { s } = useDemo()
  if (s.rol !== 'relevo') return null
  const limpia = s.relevo.urlLimpia || !s.relevo.token
  return (
    <p className="text-sm text-tenue">
      {/* Bajo 90 rem queda solo el valor: el rótulo y la aclaración no caben en una línea. */}
      <span className="sr-only @min-[90rem]:not-sr-only">Dirección: </span>
      <span className="cifras font-bold text-tinta">{limpia ? '/r' : `/r#${s.relevo.token!.slice(0, 6)}…`}</span>
      {limpia && s.relevo.fase === 'ficha' && <span className="sr-only @min-[90rem]:not-sr-only">, el token ya se borró</span>}
    </p>
  )
}

export function Franja() {
  const { cajon, setCajon } = usePresentador()
  return (
    <header aria-label="Controles de la demo" className="@container border-b border-linea bg-papel">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2 px-3 py-2 @min-[90rem]:gap-x-3">
        <Distintivo />
        <SelectorRol compacto />
        <NavEscena />
        <DireccionRelevo />
        <ListaAyudas compacta />
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => setCajon((x) => !x)}
          aria-expanded={cajon}
          aria-controls="guia-presentador"
          aria-label="Abrir la guía"
          className="inline-flex min-h-10 min-w-10 items-center justify-center gap-2 rounded-lg px-2.5 font-bold text-pino hover:bg-rocio"
        >
          <BookOpen aria-hidden className="size-5" />
          {/* Bajo 90 rem la franja no cabe en una línea con el texto: quedan el ícono y la tecla. */}
          <span className="hidden @min-[90rem]:inline">Guía</span>
          <kbd className="rounded-md bg-tinta/7 px-1.5 text-xs font-bold text-tenue">?</kbd>
        </button>
      </div>
    </header>
  )
}

/** En modo presentación queda solo esto: el distintivo y una forma de volver a la guía. */
export function DistintivoFlotante({ arriba = false }: { arriba?: boolean }) {
  const { setCajon, cajon } = usePresentador()
  return (
    // Entre los dos bordes de la pantalla: el distintivo se acomoda al ancho que haya.
    <div className={`pointer-events-none fixed inset-x-3 z-30 flex items-center gap-1 [&>*]:pointer-events-auto ${arriba ? 'top-3' : 'bottom-3'}`}>
      <Distintivo flotante />
      <button
        type="button"
        onClick={() => setCajon((x) => !x)}
        aria-expanded={cajon}
        aria-controls="guia-presentador"
        aria-label="Abrir la guía del presentador"
        className="grid size-10 shrink-0 place-items-center rounded-full bg-hoja text-tenue shadow-md ring-1 ring-linea hover:text-tinta"
      >
        <BookOpen aria-hidden className="size-4.5" />
      </button>
    </div>
  )
}

// ---------- cajón ----------

function EstadoBackend() {
  const b = useBackend()
  const conectado = b.modo === 'real'
  const texto = b.modo === 'detectando' ? 'Buscando el backend' : conectado ? 'Backend conectado' : 'Modo simulado'
  const detalle =
    b.modo === 'detectando'
      ? 'Consultando GET /v1/salud.'
      : conectado
        ? 'Cuenta, sesión, grupo y alta van a la API real. El resto es simulado.'
        : b.motivo === 'archivo-unico'
          ? 'Versión de un solo archivo: todo corre en el navegador, sin servidor.'
          : b.motivo === 'por-falla'
            ? 'Pasaste a simulado después de una falla de la API.'
            : 'GET /v1/salud no respondió. Todo corre en el navegador.'
  return (
    <section aria-label="Estado del backend" className={`flex gap-3 rounded-xl p-3 ${conectado ? 'bg-ok-fondo' : 'bg-tinta/6'}`}>
      {conectado ? <Server aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" /> : <ServerOff aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue" />}
      <div className="min-w-0 flex-1">
        <p className={`font-bold ${conectado ? 'text-ok' : ''}`} role="status">
          {texto}
        </p>
        <p className="text-sm leading-snug text-tenue">{detalle}</p>
        {b.modo === 'simulado' && b.motivo !== 'archivo-unico' && (
          <button type="button" onClick={() => void b.reintentarReal()} className="mt-1 min-h-10 font-bold text-pino underline underline-offset-4">
            Buscar el backend de nuevo
          </button>
        )}
      </div>
    </section>
  )
}

function Llamadas() {
  const { llamadas, modo } = useBackend()
  if (modo !== 'real' || llamadas.length === 0) return null
  return (
    <div>
      <p className="mb-1 text-sm font-bold text-tenue">Respuestas de la API, sin cuerpo ni token</p>
      <table className="w-full text-sm">
        <tbody>
          {llamadas.slice(0, 4).map((l) => (
            <tr key={l.id} className="border-t border-linea">
              <td className="py-1 pr-2 font-bold">{l.metodo}</td>
              <td className="cifras py-1 pr-2 break-all whitespace-normal">{l.ruta}</td>
              <td className={`cifras py-1 pr-2 text-right font-bold ${l.status && l.status < 400 ? 'text-ok' : 'text-pronto'}`}>{l.status ?? 'sin red'}</td>
              <td className="cifras py-1 text-right text-tenue">{l.ms} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Interruptor({ etiqueta, activo, onCambio, ayuda }: { etiqueta: string; activo: boolean; onCambio: (v: boolean) => void; ayuda?: string }) {
  return (
    <label className="flex min-h-11 cursor-pointer items-start justify-between gap-3">
      <span>
        <span className="block font-bold">{etiqueta}</span>
        {ayuda && <span className="block text-sm text-tenue">{ayuda}</span>}
      </span>
      <input type="checkbox" role="switch" checked={activo} onChange={(e) => onCambio(e.target.checked)} className="mt-1 size-5 shrink-0 accent-pino" />
    </label>
  )
}

const TEMAS: { valor: Tema; texto: string; Icono: typeof Sun }[] = [
  { valor: 'sistema', texto: 'Sistema', Icono: Monitor },
  { valor: 'claro', texto: 'Claro', Icono: Sun },
  { valor: 'oscuro', texto: 'Oscuro', Icono: Moon },
]

const ATAJOS: [string, string][] = [
  ['?', 'Abrir o cerrar esta guía'],
  ['] o Av Pág', 'Escena siguiente'],
  ['[ o Re Pág', 'Escena anterior'],
  ['p', 'Modo presentación'],
  ['Esc', 'Cerrar la guía'],
]

export function Cajon() {
  const { s, haz } = useDemo()
  const b = useBackend()
  const p = usePresentador()
  const { actual, escena, ir } = useEscenas()
  const esReal = useEsReal()
  const lista = useRef<HTMLElement>(null)
  const raiz = useRef<HTMLElement>(null)
  const cerrar = useRef<HTMLButtonElement>(null)

  // Al abrir, el foco entra al cajón; al cerrar, vuelve a quien lo abrió.
  useEffect(() => {
    const antes = document.activeElement as HTMLElement | null
    cerrar.current?.focus()
    return () => {
      if (antes && document.contains(antes)) antes.focus()
    }
  }, [])
  // La escena activa siempre queda a la vista en la lista.
  useEffect(() => {
    lista.current?.querySelector('[aria-current="step"]')?.scrollIntoView({ block: 'nearest' })
  }, [actual])

  return (
    <aside
      ref={raiz}
      id="guia-presentador"
      aria-label="Guía del presentador"
      onKeyDown={(e) => {
        if (e.key === 'Escape') p.setCajon(false)
      }}
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-sm flex-col border-l border-linea bg-hoja shadow-2xl motion-safe:animate-aparecer"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-linea px-4 py-2">
        <h2 className="titular text-xl">Guía de la demo</h2>
        <button ref={cerrar} type="button" onClick={() => p.setCajon(false)} aria-label="Cerrar la guía" className="grid size-11 place-items-center rounded-lg hover:bg-tinta/7">
          <X aria-hidden className="size-5" />
        </button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 py-4">
        <EstadoBackend />
        <SelectorRol />

        {escena && (
          <section aria-labelledby="escena-actual" className="flex flex-col gap-2 border-l-4 border-pino pl-3">
            <div className="flex flex-wrap items-center gap-2">
              <h3 id="escena-actual" className="text-lg font-bold">
                {escena.titulo}
              </h3>
              <EtiquetaModo real={esReal(escena.id)} />
            </div>
            <p>{escena.nota}</p>
            <ListaAyudas />
            {esReal(escena.id) && <Llamadas />}
          </section>
        )}

        <nav ref={lista} aria-label="Escenas de la demo" className="flex flex-col gap-4">
          {CAPAS.map((c) => (
            <section key={c.capa} aria-labelledby={`capa-${c.capa}`}>
              <h3 id={`capa-${c.capa}`} className="font-bold">
                {c.capa < 4 ? `Capa ${c.capa}. ${c.titulo}` : c.titulo}
              </h3>
              <p className="mb-1 text-sm text-tenue">{c.bajada}</p>
              <ol className="flex flex-col">
                {ESCENAS.filter((e) => e.capa === c.capa).map((e) => {
                  const on = e.id === actual
                  const n = ESCENAS.indexOf(e) + 1
                  return (
                    <li key={e.id}>
                      <button
                        type="button"
                        aria-current={on ? 'step' : undefined}
                        onClick={() => ir(e.id)}
                        className={`flex min-h-10 w-full items-center gap-2 rounded-lg px-2 text-left text-base ${on ? 'bg-pino font-bold text-papel' : 'hover:bg-tinta/6'}`}
                      >
                        <span className={`cifras w-6 shrink-0 text-right text-sm ${on ? '' : 'text-tenue'}`}>{n}</span>
                        <span className="min-w-0 flex-1">{e.titulo}</span>
                        {e.rol !== 'familia' && <span className={`text-sm ${on ? '' : 'text-tenue'}`}>{e.rol === 'relevo' ? 'Rosa' : 'Farmacia'}</span>}
                        {esReal(e.id) ? (
                          <span className={`rounded-full px-1.5 text-xs font-bold ${on ? 'bg-papel text-pino' : 'bg-ok-fondo text-ok'}`}>Real</span>
                        ) : (
                          <span className={`text-xs ${on ? '' : 'text-tenue'}`}>Simulado</span>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ol>
            </section>
          ))}
        </nav>

        <section aria-labelledby="ajustes" className="flex flex-col gap-3 border-t border-linea pt-4">
          <h3 id="ajustes" className="font-bold">
            Ajustes
          </h3>
          <Interruptor
            etiqueta="Texto al 200%"
            activo={s.texto200}
            onCambio={(v) => haz((x) => ({ ...x, texto200: v }))}
            ayuda="Agranda solo la app. La guía queda igual."
          />
          <Interruptor etiqueta="Modo presentación" activo={p.presentacion} onCambio={p.setPresentacion} ayuda="Oculta la franja. Queda solo el distintivo." />
          <fieldset>
            <legend className="mb-1.5 font-bold">Tema</legend>
            <div className="flex gap-1 rounded-xl bg-tinta/6 p-1">
              {TEMAS.map(({ valor, texto, Icono }) => (
                <label
                  key={valor}
                  className={`flex min-h-10 flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg text-sm has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-pino ${
                    p.tema === valor ? 'bg-hoja font-bold shadow-sm' : 'text-tenue hover:text-tinta'
                  }`}
                >
                  <input type="radio" name="tema" className="sr-only" checked={p.tema === valor} onChange={() => p.setTema(valor)} />
                  <Icono aria-hidden className="size-4" />
                  {texto}
                </label>
              ))}
            </div>
          </fieldset>
          <Interruptor etiqueta="Atajos de teclado" activo={p.atajos} onCambio={p.setAtajos} ayuda="Se pueden apagar si interfieren con un lector de pantalla." />
          {p.atajos && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              {ATAJOS.map(([k, t]) => (
                <div key={k} className="contents">
                  <dt>
                    <kbd className="rounded-md bg-tinta/7 px-1.5 font-bold">{k}</kbd>
                  </dt>
                  <dd className="text-tenue">{t}</dd>
                </div>
              ))}
            </dl>
          )}
          <button
            type="button"
            onClick={() => {
              b.olvidarSesion()
              haz(() => estadoInicial())
            }}
            className="mt-1 flex min-h-12 items-center justify-center gap-2 rounded-xl bg-hoja font-bold text-pino ring-2 ring-pino/60 ring-inset hover:bg-rocio"
          >
            <RotateCcw aria-hidden className="size-5" />
            Reiniciar demo
          </button>
          <p className="flex gap-2 text-sm text-tenue">
            <Eye aria-hidden className="mt-0.5 size-4 shrink-0" />
            Nada se guarda en el navegador: al recargar, la demo parte de cero.
          </p>
        </section>
      </div>
    </aside>
  )
}

// ---------- atajos ----------

export function useAtajos() {
  const p = usePresentador()
  const { siguiente, anterior } = useEscenas()
  const acciones = useRef({ siguiente, anterior })
  useEffect(() => {
    acciones.current = { siguiente, anterior }
  })
  useEffect(() => {
    const alPresionar = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && p.cajon) {
        p.setCajon(false)
        return
      }
      if (!p.atajos || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return
      const t = e.target as HTMLElement | null
      if (t?.closest('input, textarea, select, [contenteditable="true"]')) return
      if (e.key === '?') {
        e.preventDefault()
        p.setCajon((x) => !x)
      } else if (e.key === ']' || e.key === 'PageDown') {
        e.preventDefault()
        acciones.current.siguiente()
      } else if (e.key === '[' || e.key === 'PageUp') {
        e.preventDefault()
        acciones.current.anterior()
      } else if (e.key === 'p' || e.key === 'P') {
        e.preventDefault()
        p.setPresentacion((x) => !x)
      }
    }
    window.addEventListener('keydown', alPresionar)
    return () => window.removeEventListener('keydown', alPresionar)
  }, [p])
}
