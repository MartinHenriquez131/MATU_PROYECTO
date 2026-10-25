// Panel del presentador: capas y escenas, rol, estado del backend y reinicio.
// No es parte de MATU: es la guía para mostrarla.
import { RotateCcw, Server, ServerOff, Store, UserRound, UsersRound } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { CAPAS, ESCENAS, ESCENAS_REALES, escenaActual, prepararEscena } from '../demo/escenas'
import { abrirRelevo, accesoDelRelevo, estadoInicial, pantallaFamilia, rodrigoEdita } from '../demo/logica'
import { TEXTO_RODRIGO } from '../demo/datos'
import type { Rol } from '../demo/tipos'
import { useBackend } from '../datos/backend'

const ROLES: { rol: Rol; texto: string; quien: string; Icono: typeof UserRound }[] = [
  { rol: 'familia', texto: 'Familia', quien: 'Carmen', Icono: UsersRound },
  { rol: 'relevo', texto: 'Relevo', quien: 'Rosa', Icono: UserRound },
  { rol: 'comercio', texto: 'Comercio', quien: 'Farmacia', Icono: Store },
]

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
            ? 'Pasaste a simulado después de una falla de red.'
            : 'GET /v1/salud no respondió. Todo corre en el navegador.'
  return (
    <div className={`flex gap-3 rounded-2xl p-3.5 ${conectado ? 'bg-ok-fondo' : 'bg-tinta/[0.06]'}`}>
      {conectado ? <Server aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" /> : <ServerOff aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue" />}
      <div className="min-w-0 flex-1">
        <p className={`font-bold ${conectado ? 'text-ok' : ''}`} role="status">
          {texto}
        </p>
        <p className="text-[0.9rem] text-tenue">{detalle}</p>
        {b.modo === 'simulado' && b.motivo !== 'archivo-unico' && (
          <button type="button" onClick={() => void b.reintentarReal()} className="mt-1 min-h-11 font-bold text-pino underline underline-offset-4">
            Buscar el backend de nuevo
          </button>
        )}
      </div>
    </div>
  )
}

function Llamadas() {
  const { llamadas, modo } = useBackend()
  if (modo !== 'real' || llamadas.length === 0) return null
  return (
    <div>
      <p className="mb-1.5 text-[0.9rem] font-bold text-tenue">Respuestas de la API (sin cuerpo ni token)</p>
      <table className="w-full text-[0.85rem]">
        <tbody>
          {llamadas.slice(0, 5).map((l) => (
            <tr key={l.id} className="border-t border-linea">
              <td className="py-1 pr-2 font-bold">{l.metodo}</td>
              <td className="cifras py-1 pr-2 break-all">{l.ruta}</td>
              <td className={`cifras py-1 pr-2 text-right font-bold ${l.status && l.status < 400 ? 'text-ok' : 'text-pronto'}`}>{l.status ?? 'sin red'}</td>
              <td className="cifras py-1 text-right text-tenue">{l.ms} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function PanelPresentador({ alElegir }: { alElegir?: () => void }) {
  const { s, haz } = useDemo()
  const b = useBackend()
  const actual = escenaActual(s)
  const escena = ESCENAS.find((e) => e.id === actual)
  const esReal = (id: string) => b.modo === 'real' && ESCENAS_REALES.has(id)

  const cambiarRol = (rol: Rol) => {
    if (rol === 'relevo') haz((x) => (x.rol === 'relevo' ? x : abrirRelevo(x)))
    else haz((x) => ({ ...x, rol, texto200: false }))
    alElegir?.()
  }
  const ir = (id: string) => {
    haz((x) => prepararEscena(x, id))
    alElegir?.()
  }
  const accesoRelevo = s.rol === 'relevo' ? accesoDelRelevo(s) : null
  const editando = s.rol === 'familia' && pantallaFamilia(s).id === 'completar' && s.borrador

  return (
    <div className="flex flex-col gap-5">
      <EstadoBackend />

      <fieldset>
        <legend className="mb-2 font-bold">Ver como</legend>
        <div className="grid grid-cols-3 gap-1.5 rounded-2xl bg-tinta/[0.06] p-1.5">
          {ROLES.map(({ rol, texto, quien, Icono }) => (
            <label
              key={rol}
              className={`flex min-h-14 cursor-pointer flex-col items-center justify-center rounded-xl px-1 text-center has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-pino ${
                s.rol === rol ? 'bg-hoja shadow-sm' : 'text-tenue hover:text-tinta'
              }`}
            >
              <input type="radio" name="rol" className="sr-only" checked={s.rol === rol} onChange={() => cambiarRol(rol)} />
              <Icono aria-hidden className="size-5" />
              <span className="text-[0.9rem] font-bold">{texto}</span>
              <span className="text-[0.75rem] text-tenue">{quien}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {escena && (
        <section aria-label="Escena actual" className="rounded-2xl bg-hoja p-4 ring-1 ring-linea">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-[1.15rem] font-bold">{escena.titulo}</h2>
            <span className={`rounded-full px-2.5 py-0.5 text-[0.8rem] font-bold ${esReal(escena.id) ? 'bg-ok-fondo text-ok' : 'bg-tinta/[0.07] text-tenue'}`}>
              {esReal(escena.id) ? 'Real' : 'Simulado'}
            </span>
          </div>
          <p className="mt-1">{escena.nota}</p>
          {esReal(escena.id) && (
            <div className="mt-3">
              <Llamadas />
            </div>
          )}
          {accesoRelevo && s.relevo.fase === 'pin' && (
            <p className="mt-3 rounded-xl bg-rocio px-3 py-2 text-[0.95rem]">
              PIN de este enlace: <b className="cifras tracking-[0.2em]">{accesoRelevo.pin}</b>
            </p>
          )}
          {editando && (
            <button
              type="button"
              onClick={() => haz((x) => rodrigoEdita(x, x.borrador!.campo, TEXTO_RODRIGO))}
              className="mt-3 min-h-11 w-full rounded-xl border-2 border-dashed border-tenue/50 px-3 font-bold text-tenue hover:text-tinta"
            >
              Simular que Rodrigo guarda este campo ahora
            </button>
          )}
        </section>
      )}

      <nav aria-label="Escenas de la demo" className="flex flex-col gap-4">
        {CAPAS.map((c) => (
          <section key={c.capa}>
            <h2 className="flex items-baseline gap-2">
              <span className="font-display text-[1.05rem] font-bold">{c.capa < 4 ? `Capa ${c.capa}. ${c.titulo}` : c.titulo}</span>
            </h2>
            <p className="mb-1.5 text-[0.85rem] text-tenue">{c.bajada}</p>
            <ol className="flex flex-col">
              {ESCENAS.filter((e) => e.capa === c.capa).map((e) => {
                const on = e.id === actual
                return (
                  <li key={e.id}>
                    <button
                      type="button"
                      aria-current={on ? 'step' : undefined}
                      onClick={() => ir(e.id)}
                      className={`flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-[0.95rem] ${
                        on ? 'bg-pino font-bold text-papel' : 'hover:bg-tinta/[0.06]'
                      }`}
                    >
                      <span className="min-w-0 flex-1">{e.titulo}</span>
                      {e.rol !== 'familia' && <span className={`text-[0.8rem] ${on ? '' : 'text-tenue'}`}>{e.rol === 'relevo' ? 'Rosa' : 'Farmacia'}</span>}
                      {esReal(e.id) && <span className={`size-2 rounded-full ${on ? 'bg-papel' : 'bg-ok'}`} title="Usa la API real" />}
                    </button>
                  </li>
                )
              })}
            </ol>
          </section>
        ))}
      </nav>

      <div className="flex flex-col gap-2 border-t border-linea pt-4">
        <label className="flex min-h-12 cursor-pointer items-center justify-between gap-3 font-bold">
          Texto al 200%
          <input
            type="checkbox"
            role="switch"
            checked={s.texto200}
            onChange={(e) => haz((x) => ({ ...x, texto200: e.target.checked }))}
            className="size-6 accent-[var(--color-pino)]"
          />
        </label>
        <button
          type="button"
          onClick={() => {
            b.olvidarSesion()
            haz(() => estadoInicial())
            alElegir?.()
          }}
          className="flex min-h-12 items-center justify-center gap-2 rounded-2xl bg-hoja font-bold text-pino ring-2 ring-pino/60 ring-inset hover:bg-rocio"
        >
          <RotateCcw aria-hidden className="size-5" />
          Reiniciar demo
        </button>
      </div>
    </div>
  )
}
