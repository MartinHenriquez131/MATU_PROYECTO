// Insumos: el horizonte de 30 días a la izquierda (cada producto es una barra que termina el día que
// se acaba) y el detalle del producto elegido a la derecha. La lista de reposición es otra pestaña.
import { useState, type ReactNode } from 'react'
import { CalendarCheck, Copy, Download, ListChecks, Plus, Send, Share2, ShoppingBag } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { ajustarLista, armarPedido, avisar, declarar, etapa, ir, nombrePila, pantallaFamilia, pilaFamilia, reemplazar, volver, yaLoCompre } from '../demo/logica'
import { COBERTURA_DIAS, DIA, DIAS_PRONTO, diasRestantes, fmtDinero, fmtFecha, lineasLista, nivel, totalProductos } from '../demo/calculos'
import type { Estado, Insumo } from '../demo/tipos'
import { COMERCIO, ENVIO } from '../demo/datos'
import { Acciones, BarraDias, Boton, EtiquetaNivel, GrupoOpciones, HORIZONTE_DIAS, Nota, PreciosDeEjemplo, Renglon, Stepper, Subtitulo, posicionDia } from '../components/Ui'
import { Columna, Columnas, Pagina, Pestanas } from './Shell'

function fechaFin(i: Insumo, ahora: number) {
  const d = diasRestantes(i)
  return Number.isFinite(d) ? fmtFecha(ahora + d * DIA) : 'sin fecha'
}

const ordenados = (s: Estado) => s.insumos.filter((i) => i.declarado).sort((a, b) => diasRestantes(a) - diasRestantes(b))

function PestanasInsumos() {
  const { s, haz } = useDemo()
  const top = pantallaFamilia(s).id
  const lista = top === 'reponer' || top === 'exportar'
  return (
    <Pestanas
      items={[
        { texto: 'Qué se acaba', activa: !lista, ir: () => haz((x) => pilaFamilia(x, ['se-acaba'])) },
        { texto: 'Lista de reposición', activa: lista, ir: () => haz((x) => pilaFamilia(x, ['se-acaba', 'reponer'])) },
      ]}
    />
  )
}

function PaginaInsumos({ children, bajada }: { children: ReactNode; bajada?: ReactNode }) {
  return (
    <Pagina titulo="Insumos" bajada={bajada} pestanas={<PestanasInsumos />}>
      {children}
    </Pagina>
  )
}

// ---------- Qué se acaba ----------

function Horizonte({ seleccionado }: { seleccionado: string | null }) {
  const { s, haz } = useDemo()
  const declarados = ordenados(s)
  const hayMas = s.insumos.some((i) => !i.declarado)
  return (
    <Columna etiqueta="Qué se acaba primero">
      {declarados.length > 0 && (
        <div className="relative mx-4 h-11 text-sm text-tenue" aria-hidden>
          <span className="absolute bottom-0 left-0">
            Hoy
            <span className="cifras block">{fmtFecha(s.ahora).slice(0, 5)}</span>
          </span>
          <span className="absolute bottom-0 hidden -translate-x-1/2 text-center whitespace-nowrap @md:block" style={{ left: posicionDia(DIAS_PRONTO) }}>
            Aviso
            <span className="block">7 días</span>
          </span>
          <span className="absolute right-0 bottom-0 text-right">
            {HORIZONTE_DIAS} días
            <span className="cifras block">{fmtFecha(s.ahora + HORIZONTE_DIAS * DIA).slice(0, 5)}</span>
          </span>
        </div>
      )}
      <ul className="flex flex-col gap-2">
        {declarados.map((i) => {
          const d = diasRestantes(i)
          const n = nivel(d)
          const on = i.id === seleccionado
          return (
            <li key={i.id}>
              <button
                type="button"
                aria-current={on ? 'true' : undefined}
                onClick={() => haz((x) => pilaFamilia(x, [['se-acaba', i.id]]))}
                className={`flex w-full flex-col gap-2.5 border-l-4 bg-hoja px-4 py-3 text-left ${
                  on ? 'border-pino ring-2 ring-pino ring-inset' : 'border-transparent hover:border-pino/40'
                }`}
              >
                <span className="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-1">
                  <span className="min-w-0">
                    <span className="font-bold">{i.nombre}</span> <span className="text-tenue">{i.presentacion}</span>
                  </span>
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <b className="cifras">{d} días</b>
                    <EtiquetaNivel nivel={n} />
                  </span>
                </span>
                <BarraDias dias={d} nivel={n} />
              </button>
            </li>
          )
        })}
      </ul>
      {declarados.length === 0 && <Nota>Todavía no hay productos. Cuenta cuánto usa de uno y aparece aquí.</Nota>}
      {hayMas && (
        <Boton variante="texto" className="self-start" icono={<Plus aria-hidden className="size-5" />} onClick={() => haz((x) => pilaFamilia(x, ['se-acaba', 'agregar']))}>
          Agregar un producto
        </Boton>
      )}
    </Columna>
  )
}

function Detalle({ titulo, children }: { titulo: ReactNode; children: ReactNode }) {
  return (
    <Columna etiqueta="Detalle del producto">
      <section aria-labelledby="detalle-t" className="flex flex-col gap-5 bg-hoja px-4 angosto:px-2 @3xl:px-7 py-5 ring-1 ring-linea">
        <h2 id="detalle-t" data-foco="detalle" tabIndex={-1} className="text-xl font-bold leading-snug outline-none">
          {titulo}
        </h2>
        {children}
      </section>
    </Columna>
  )
}

const nombreProducto = (i: Insumo) => (
  <>
    {i.nombre} <span className="font-normal text-tenue">{i.presentacion}</span>
  </>
)

function VerProducto({ i }: { i: Insumo }) {
  const { s, haz } = useDemo()
  const d = diasRestantes(i)
  const n = nivel(d)
  return (
    <Detalle titulo={nombreProducto(i)}>
      <p className="text-2xl angosto:text-xl leading-snug" role="status">
        Le alcanza <b className="cifras">{d} días</b>, hasta el <b className="cifras">{fechaFin(i, s.ahora)}</b>.
      </p>
      <div className="flex flex-col items-start gap-2">
        <EtiquetaNivel nivel={n} />
        <BarraDias dias={d} nivel={n} grosor="h-4" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Renglon texto={`Quedan, más o menos`} monto={`${i.quedan} ${i.unidad}`} />
        <Renglon texto="Usa al día" monto={`${i.porDia}`} />
        <Renglon texto={`${i.quedan} ÷ ${i.porDia}`} monto={`${d} días`} fuerte />
      </div>
      <p className="text-base text-tenue">Te avisamos cuando quedan {DIAS_PRONTO} días o menos.</p>
      <Acciones>
        <Boton variante="secundario" onClick={() => haz((x) => ir(x, 'declarar', i.id))}>
          Cambiar lo que usa
        </Boton>
        <Boton variante="secundario" onClick={() => haz((x) => ir(x, 'ya-compre', i.id))}>
          Ya lo compré
        </Boton>
      </Acciones>
    </Detalle>
  )
}

const cancelar = (id: string) => (x: Estado) => (x.nav.familia.length > 1 ? volver(x) : pilaFamilia(x, [['se-acaba', id]]))

function Declarar({ i }: { i: Insumo }) {
  const { s, haz } = useDemo()
  const [porDia, setPorDia] = useState(i.porDia)
  const [quedan, setQuedan] = useState(i.quedan)
  const vista = { ...i, porDia, quedan }
  const d = diasRestantes(vista)
  return (
    <Detalle titulo={<>¿Cuánto usa {nombrePila(s)}? <span className="block text-base font-normal text-tenue">{i.nombre} {i.presentacion}</span></>}>
      <Stepper etiqueta={i.preguntaDia} valor={porDia} onCambio={setPorDia} min={1} max={30} unidad={`${i.unidad} al día`} />
      <Stepper etiqueta="¿Cuántos le quedan, más o menos?" valor={quedan} onCambio={setQuedan} min={0} max={999} paso={i.tamanoPaquete >= 30 ? 2 : 1} unidad={i.unidad} />
      <div className="flex flex-col gap-2 border-l-4 border-pino bg-rocio px-4 angosto:px-2 py-3">
        <p className="flex items-center gap-2 font-bold" aria-live="polite">
          <CalendarCheck aria-hidden className="size-5 shrink-0 angosto:hidden" />
          <span>
            Le alcanza <span className="cifras">{d} días</span>, hasta el <span className="cifras">{fechaFin(vista, s.ahora)}</span>
          </span>
        </p>
        <BarraDias dias={d} nivel={nivel(d)} />
      </div>
      <Acciones>
        <Boton onClick={() => haz((x) => pilaFamilia(declarar(x, i.id, porDia, quedan), [['se-acaba', i.id]]))}>Guardar</Boton>
        <Boton variante="texto" onClick={() => haz(cancelar(i.id))}>
          Cancelar
        </Boton>
      </Acciones>
    </Detalle>
  )
}

function YaCompre({ i }: { i: Insumo }) {
  const { s, haz } = useDemo()
  const [paquetes, setPaquetes] = useState(2)
  const despues = { ...i, quedan: i.quedan + paquetes * i.tamanoPaquete }
  return (
    <Detalle titulo={<>Ya lo compré <span className="block text-base font-normal text-tenue">{i.nombre} {i.presentacion}</span></>}>
      <Stepper etiqueta="¿Cuántos paquetes compraste?" valor={paquetes} onCambio={setPaquetes} min={0} max={20} unidad={`de ${i.tamanoPaquete} ${i.unidad}`} />
      <div className="flex flex-col gap-2 border-l-4 border-ok bg-ok-fondo px-4 py-3">
        <p aria-live="polite">
          Antes alcanzaba hasta el <span className="cifras">{fechaFin(i, s.ahora)}</span>.{' '}
          <b>
            Ahora alcanza hasta el <span className="cifras">{fechaFin(despues, s.ahora)}</span>.
          </b>
        </p>
        <BarraDias dias={diasRestantes(despues)} nivel={nivel(diasRestantes(despues))} />
      </div>
      <Acciones>
        <Boton disabled={paquetes === 0} onClick={() => haz((x) => pilaFamilia(yaLoCompre(x, i.id, paquetes), [['se-acaba', i.id]]))}>
          Anotar la compra
        </Boton>
        <Boton variante="texto" onClick={() => haz(cancelar(i.id))}>
          Cancelar
        </Boton>
      </Acciones>
    </Detalle>
  )
}

function Agregar() {
  const { s, haz } = useDemo()
  const disponibles = s.insumos.filter((i) => !i.declarado)
  const [elegido, setElegido] = useState<string | null>(disponibles[0]?.id ?? null)
  return (
    <Detalle titulo="Agregar un producto">
      {disponibles.length === 0 ? (
        <Nota>Ya están todos los productos de la demo.</Nota>
      ) : (
        <GrupoOpciones
          leyenda="¿Qué producto quieres agregar?"
          nombre="producto"
          valor={elegido}
          onCambio={setElegido}
          opciones={disponibles.map((i) => ({ valor: i.id, texto: `${i.nombre} ${i.presentacion}`, detalle: `${fmtDinero(i.precio)} el paquete` }))}
        />
      )}
      <Acciones>
        <Boton disabled={!elegido} onClick={() => elegido && haz((x) => reemplazar(x, 'declarar', elegido))}>
          Continuar
        </Boton>
        <Boton variante="texto" onClick={() => haz((x) => (x.nav.familia.length > 1 ? volver(x) : pilaFamilia(x, ['se-acaba'])))}>
          Cancelar
        </Boton>
      </Acciones>
    </Detalle>
  )
}

export function SeAcaba() {
  const { s, haz } = useDemo()
  const pila = nombrePila(s)
  const top = pantallaFamilia(s)
  const declarados = ordenados(s)

  if (declarados.length === 0 && top.id === 'se-acaba') {
    return (
      <PaginaInsumos>
        <div className="flex max-w-prose flex-col items-start gap-4 pt-2">
          <span className="grid size-16 place-items-center rounded-2xl bg-rocio text-pino">
            <ListChecks aria-hidden className="size-9" />
          </span>
          <h2 className="titular text-3xl">Aún no sabemos qué usa {pila}</h2>
          <p className="text-base text-tenue">
            Cuéntanos de un solo producto, el que más te preocupa. Con eso ya te podemos avisar antes de que se acabe.
          </p>
          <Acciones>
            <Boton onClick={() => haz((x) => ir(x, 'declarar', 'panal-m'))}>Empezar por los pañales</Boton>
            <Boton variante="texto" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>
              Después
            </Boton>
          </Acciones>
        </div>
      </PaginaInsumos>
    )
  }

  const param = top.p ?? null
  const elegido = s.insumos.find((i) => i.id === param) ?? declarados[0] ?? s.insumos[0]
  const seleccionado = top.id === 'agregar' ? null : elegido.id
  let detalle: ReactNode
  if (top.id === 'declarar') detalle = <Declarar key={`d-${elegido.id}`} i={elegido} />
  else if (top.id === 'ya-compre') detalle = <YaCompre key={`y-${elegido.id}`} i={elegido} />
  else if (top.id === 'agregar') detalle = <Agregar />
  else detalle = <VerProducto i={elegido} />

  return (
    <PaginaInsumos
      bajada={
        <>
          Hoy es <span className="cifras">{fmtFecha(s.ahora)}</span>. Los días son lo que queda dividido por lo que usa al día.
        </>
      }
    >
      <Columnas izquierda="ancha">
        <Horizonte seleccionado={seleccionado} />
        {detalle}
      </Columnas>
    </PaginaInsumos>
  )
}

// ---------- Lista de reposición ----------

export function textoLista(nombre: string, fecha: string, lineas: ReturnType<typeof lineasLista>): string {
  const filas = lineas
    .filter((l) => l.paquetes > 0)
    .map(
      (l, i) =>
        `- ${l.insumo.nombre} ${l.insumo.presentacion}: ${l.paquetes} ${l.paquetes === 1 ? 'paquete' : 'paquetes'} (${fmtDinero(l.insumo.precio)} c/u en ${i === 0 ? COMERCIO.nombreFicticio : COMERCIO.nombre})`,
    )
  return [`Lista de ${nombre}, ${fecha}`, ...filas, 'Precios de ejemplo.'].join('\n')
}

function ListaReposicion() {
  const { s, haz } = useDemo()
  const lineas = lineasLista(s.insumos, s.ajustesLista)
  const btn = 'grid size-11 shrink-0 place-items-center rounded-lg bg-hoja text-pino ring-2 ring-inset ring-pino/70 hover:bg-rocio disabled:opacity-40'
  if (lineas.length === 0) {
    return (
      <Columna etiqueta="Lista de reposición">
        <Nota titulo="Por ahora no hace falta reponer nada">Todo alcanza para más de {COBERTURA_DIAS} días. Te avisamos antes.</Nota>
      </Columna>
    )
  }
  return (
    <Columna etiqueta="Lista de reposición">
      <section aria-labelledby="precios-t" className="bg-hoja ring-1 ring-linea">
        <h2 id="precios-t" className="border-b border-linea px-4 py-3 font-bold">
          Precios de {COMERCIO.nombreFicticio}
        </h2>
        <ul className="flex flex-col divide-y divide-linea">
          {lineas.map((l) => (
            <li key={l.insumo.id} className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 angosto:px-2 py-3">
              <span className="min-w-0 grow basis-48">
                <span className="block font-bold">
                  {l.insumo.nombre} <span className="font-normal text-tenue">{l.insumo.presentacion}</span>
                </span>
                <span className="text-sm text-tenue tabular-nums">
                  {fmtDinero(l.insumo.precio)} el paquete. Sugerimos {l.sugeridos}.
                </span>
              </span>
              <span className="flex flex-wrap items-center gap-2" role="group" aria-label={`Paquetes de ${l.insumo.nombre}`}>
                <button type="button" className={btn} aria-label={`Un paquete menos de ${l.insumo.nombre}`} disabled={l.paquetes === 0} onClick={() => haz((x) => ajustarLista(x, l.insumo.id, l.paquetes - 1))}>
                  <span aria-hidden className="text-2xl leading-none font-bold">−</span>
                </button>
                <output aria-live="polite" className="cifras min-w-7 text-center text-xl font-bold">
                  {l.paquetes}
                </output>
                <button type="button" className={btn} aria-label={`Un paquete más de ${l.insumo.nombre}`} disabled={l.paquetes >= 20} onClick={() => haz((x) => ajustarLista(x, l.insumo.id, l.paquetes + 1))}>
                  <span aria-hidden className="text-2xl leading-none font-bold">+</span>
                </button>
              </span>
              <span className="cifras ml-auto w-26 angosto:w-auto text-right font-bold">{fmtDinero(l.paquetes * l.insumo.precio)}</span>
            </li>
          ))}
        </ul>
      </section>
      <p className="text-base text-tenue">La lista sirve aunque compres en otra parte.</p>
      <PreciosDeEjemplo />
    </Columna>
  )
}

export function Reponer() {
  const { s, haz } = useDemo()
  const pila = nombrePila(s)
  const conCompra = lineasLista(s.insumos, s.ajustesLista).filter((l) => l.paquetes > 0)
  const hayLista = lineasLista(s.insumos, s.ajustesLista).length > 0
  const productos = totalProductos(conCompra)
  const total = productos + ENVIO
  const enCurso = s.pedido && etapa(s.pedido.estado) >= etapa('pagado') && s.pedido.estado !== 'entregado'
  return (
    <PaginaInsumos bajada={`Cuánto comprar para que ${pila} quede cubierta unas ${COBERTURA_DIAS / 7} semanas.`}>
      <Columnas izquierda="ancha">
        <ListaReposicion />
        {hayLista && (
          <Columna etiqueta="Si pides en MATU">
            <section aria-labelledby="resumen-t" className="flex flex-col gap-4 bg-hoja px-5 py-5 ring-1 ring-linea">
              <h2 id="resumen-t" className="text-xl font-bold">
                Si pides en MATU
              </h2>
              <div className="flex flex-col gap-2">
                <Renglon texto="Productos" monto={fmtDinero(productos)} />
                <Renglon texto="Envío, uno por pedido" monto={fmtDinero(ENVIO)} />
                <hr className="border-0 border-t-2 border-tinta" />
                <Renglon texto="Total con IVA" monto={fmtDinero(total)} fuerte />
              </div>
              <p className="text-base text-tenue">Antes de que pagues confirmamos que haya stock.</p>
              <Acciones>
                {enCurso ? (
                  <Boton onClick={() => haz((x) => pilaFamilia(x, ['seguimiento']))}>Ver el pedido en curso</Boton>
                ) : (
                  <Boton
                    icono={<ShoppingBag aria-hidden className="size-5" />}
                    disabled={conCompra.length === 0}
                    onClick={() => haz((x) => pilaFamilia(armarPedido(x), ['se-acaba', 'reponer', 'pedido']))}
                  >
                    Pedir a domicilio por <span className="cifras">{fmtDinero(total)}</span>
                  </Boton>
                )}
                <Boton variante="secundario" icono={<Share2 aria-hidden className="size-5" />} onClick={() => haz((x) => ir(x, 'exportar'))}>
                  Exportar o compartir
                </Boton>
              </Acciones>
              {conCompra.length === 0 && !enCurso && <p className="text-base text-tenue">Elige al menos un producto para pedir.</p>}
              <p className="text-base text-tenue">Exportarla o compartirla es gratis y no necesitas pedir en MATU.</p>
            </section>
          </Columna>
        )}
      </Columnas>
    </PaginaInsumos>
  )
}

export function Exportar() {
  const { s, haz } = useDemo()
  const pila = nombrePila(s)
  const lineas = lineasLista(s.insumos, s.ajustesLista).filter((l) => l.paquetes > 0)
  const texto = textoLista(pila, fmtFecha(s.ahora), lineas)

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto)
      haz((x) => avisar(x, 'Lista copiada. Pégala donde quieras.'))
    } catch {
      haz((x) => avisar(x, 'Este navegador no deja copiar. Usa Descargar.'))
    }
  }
  const compartir = async () => {
    if (typeof navigator.share !== 'function') {
      haz((x) => avisar(x, 'Este navegador no deja compartir. Usa Copiar la lista.'))
      return
    }
    try {
      await navigator.share({ title: `Lista de ${pila}`, text: texto })
      haz((x) => avisar(x, 'Lista compartida.'))
    } catch {
      // Cancelar el diálogo de compartir no es un error.
    }
  }
  const descargar = () => {
    const url = URL.createObjectURL(new Blob([texto + '\n'], { type: 'text/plain;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `lista-${pila.toLowerCase()}.txt`
    document.body.append(a)
    a.click()
    a.remove()
    // Revocar en el mismo instante puede cortar la descarga en algunos navegadores.
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    haz((x) => avisar(x, 'Lista descargada.'))
  }

  return (
    <PaginaInsumos bajada="Para quien vaya a comprar. Sirve en cualquier farmacia.">
      <Columnas izquierda="ancha">
        <ListaReposicion />
        <Columna etiqueta="Exportar o compartir">
          <section aria-labelledby="exportar-t" className="flex flex-col gap-4 bg-hoja px-5 py-5 ring-1 ring-linea">
            <h2 id="exportar-t" data-foco="detalle" tabIndex={-1} className="text-2xl font-bold outline-none">
              Exportar o compartir
            </h2>
            <pre className="rounded-lg bg-papel p-4 text-base leading-relaxed break-words whitespace-pre-wrap tabular-nums">{texto}</pre>
            <Acciones>
              <Boton icono={<Copy aria-hidden className="size-5" />} onClick={copiar}>
                Copiar la lista
              </Boton>
              <Boton variante="secundario" icono={<Download aria-hidden className="size-5" />} onClick={descargar}>
                Descargar
              </Boton>
            </Acciones>
            <Subtitulo>Pasársela a alguien</Subtitulo>
            <Acciones>
              <Boton variante="secundario" icono={<Send aria-hidden className="size-5" />} onClick={() => haz((x) => avisar(x, 'Lista enviada a Rodrigo. La verá en su MATU.'))}>
                Enviar a Rodrigo
              </Boton>
              <Boton variante="secundario" icono={<Share2 aria-hidden className="size-5" />} onClick={compartir}>
                Compartir desde tu teléfono
              </Boton>
            </Acciones>
            <p className="text-sm text-tenue">Solo puedes enviarla a alguien de tu grupo familiar. A otras personas, compártela desde tu teléfono.</p>
            <Boton variante="texto" className="self-start" onClick={() => haz(volver)}>
              Volver a la lista
            </Boton>
          </section>
        </Columna>
      </Columnas>
    </PaginaInsumos>
  )
}
