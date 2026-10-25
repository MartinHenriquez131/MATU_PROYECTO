import { useState } from 'react'
import { CalendarCheck, Copy, Download, FileText, ListChecks, Minus, Plus, Share2, ShoppingBag } from 'lucide-react'
import { useDemo } from '../demo/estado'
import {
  ajustarLista,
  armarPedido,
  avisar,
  declarar,
  ir,
  nombrePila,
  pilaFamilia,
  reemplazar,
  volver,
  yaLoCompre,
} from '../demo/logica'
import {
  COBERTURA_DIAS,
  DIA,
  DIAS_PRONTO,
  diasRestantes,
  fmtDinero,
  fmtFecha,
  lineasLista,
  nivel,
  totalEstimado,
} from '../demo/calculos'
import type { Insumo } from '../demo/tipos'
import { Pantalla } from '../components/Pantalla'
import { BarraDias, Boton, EtiquetaNivel, Fila, GrupoOpciones, Nota, Sello, Stepper, Tarjeta } from '../components/Ui'

function fechaFin(i: Insumo, ahora: number) {
  const d = diasRestantes(i)
  return Number.isFinite(d) ? fmtFecha(ahora + d * DIA) : 'sin fecha'
}

export function SeAcaba() {
  const { s, haz } = useDemo()
  const pila = nombrePila(s)
  const declarados = s.insumos.filter((i) => i.declarado).sort((a, b) => diasRestantes(a) - diasRestantes(b))
  const hayMas = s.insumos.some((i) => !i.declarado)

  if (declarados.length === 0) {
    return (
      <Pantalla
        titulo="Qué se está acabando"
        pie={
          <>
            <Boton onClick={() => haz((x) => ir(x, 'declarar', 'panal-m'))}>Empezar por los pañales</Boton>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>
              Después
            </Boton>
          </>
        }
      >
        <div className="flex flex-col items-start gap-3 pt-6">
          <Sello tono="suave">
            <ListChecks aria-hidden className="size-9" />
          </Sello>
          <p className="font-display text-[1.5rem] leading-tight font-bold">Aún no sabemos qué usa {pila}</p>
          <p className="text-tenue">
            Cuéntanos de un solo producto, el que más te preocupa. Con eso ya te podemos avisar antes de que se acabe.
          </p>
        </div>
      </Pantalla>
    )
  }

  const primero = declarados[0]
  return (
    <Pantalla
      titulo="Qué se está acabando"
      pie={
        <Fila>
          <Boton variante="secundario" onClick={() => haz((x) => ir(x, 'ya-compre', primero.id))}>
            Ya lo compré
          </Boton>
          <Boton onClick={() => haz((x) => ir(x, 'reponer'))}>Qué reponer</Boton>
        </Fila>
      }
    >
      <p className="text-[0.95rem] text-tenue">
        Hoy es <span className="cifras">{fmtFecha(s.ahora)}</span>. Toca un producto para cambiar cuánto usa o cuánto queda.
      </p>
      <ul className="flex flex-col gap-2.5">
        {declarados.map((i) => {
          const d = diasRestantes(i)
          const n = nivel(d)
          return (
            <li key={i.id}>
              <button
                type="button"
                onClick={() => haz((x) => ir(x, 'declarar', i.id))}
                className="flex w-full flex-col gap-2.5 rounded-[1.2rem] bg-hoja p-4 text-left ring-1 ring-linea hover:ring-pino/50"
              >
                <span className="flex w-full flex-wrap items-start justify-between gap-2">
                  <span className="min-w-0">
                    <span className="block font-bold">
                      {i.nombre} <span className="font-normal text-tenue">{i.presentacion}</span>
                    </span>
                    <span className="text-[0.95rem]">
                      Quedan <b className="cifras">{d} días</b>, hasta el <span className="cifras">{fechaFin(i, s.ahora)}</span>
                    </span>
                  </span>
                  <EtiquetaNivel nivel={n} />
                </span>
                <BarraDias dias={d} nivel={n} />
              </button>
            </li>
          )
        })}
      </ul>
      {hayMas && (
        <Boton variante="texto" icono={<Plus aria-hidden className="size-5" />} onClick={() => haz((x) => ir(x, 'agregar'))}>
          Agregar un producto
        </Boton>
      )}
      <Nota>
        <span className="cifras">Días = lo que queda ÷ lo que usa al día.</span> Te avisamos cuando quedan {DIAS_PRONTO} días o menos.
      </Nota>
    </Pantalla>
  )
}

export function Declarar() {
  const { s, haz } = useDemo()
  const id = s.nav.familia[s.nav.familia.length - 1].p ?? 'panal-m'
  const i = s.insumos.find((x) => x.id === id) ?? s.insumos[0]
  const [porDia, setPorDia] = useState(i.porDia)
  const [quedan, setQuedan] = useState(i.quedan)
  const vista = { ...i, porDia, quedan }
  const d = diasRestantes(vista)
  return (
    <Pantalla
      titulo={`¿Qué usa ${nombrePila(s)}?`}
      pie={
        <Boton
          onClick={() =>
            haz((x) => {
              const t = declarar(x, i.id, porDia, quedan)
              return x.nav.familia.length > 1 ? volver(t) : pilaFamilia(t, ['se-acaba'])
            })
          }
        >
          Guardar
        </Boton>
      }
    >
      <h2 className="font-display text-[1.4rem] leading-tight font-bold">
        {i.nombre} <span className="font-sans text-[1.05rem] font-normal text-tenue">{i.presentacion}</span>
      </h2>
      <Stepper etiqueta={i.preguntaDia} valor={porDia} onCambio={setPorDia} min={1} max={30} unidad={`${i.unidad} al día`} />
      <Stepper
        etiqueta="¿Cuántos le quedan, más o menos?"
        valor={quedan}
        onCambio={setQuedan}
        min={0}
        max={999}
        paso={i.tamanoPaquete >= 30 ? 2 : 1}
        unidad={i.unidad}
      />
      <Tarjeta tono={nivel(d) === 'pronto' ? 'pronto' : nivel(d) === 'atenta' ? 'atenta' : 'ok'}>
        <p className="flex items-center gap-2 font-bold" aria-live="polite">
          <CalendarCheck aria-hidden className="size-5 shrink-0" />
          <span>
            Le alcanza <span className="cifras">{d} días</span>, hasta el <span className="cifras">{fechaFin(vista, s.ahora)}</span>
          </span>
        </p>
        <BarraDias dias={d} nivel={nivel(d)} />
      </Tarjeta>
      <p className="text-[0.95rem] text-tenue">
        Te avisamos <b>{DIAS_PRONTO} días antes</b> de que se acabe. Puedes cambiarlo después.
      </p>
    </Pantalla>
  )
}

export function Agregar() {
  const { s, haz } = useDemo()
  const disponibles = s.insumos.filter((i) => !i.declarado)
  const [elegido, setElegido] = useState<string | null>(disponibles[0]?.id ?? null)
  return (
    <Pantalla
      titulo="Agregar un producto"
      pie={
        <Boton disabled={!elegido} onClick={() => elegido && haz((x) => reemplazar(x, 'declarar', elegido))}>
          Continuar
        </Boton>
      }
    >
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
    </Pantalla>
  )
}

export function YaCompre() {
  const { s, haz } = useDemo()
  const declarados = s.insumos.filter((i) => i.declarado)
  const inicial = s.nav.familia[s.nav.familia.length - 1].p ?? declarados[0]?.id ?? null
  const [id, setId] = useState<string | null>(inicial)
  const [paquetes, setPaquetes] = useState(2)
  const i = declarados.find((x) => x.id === id) ?? declarados[0]
  if (!i) return null
  const despues = { ...i, quedan: i.quedan + paquetes * i.tamanoPaquete }
  return (
    <Pantalla
      titulo="Ya lo compré"
      pie={
        <Boton disabled={paquetes === 0} onClick={() => haz((x) => volver(yaLoCompre(x, i.id, paquetes)))}>
          Anotar la compra
        </Boton>
      }
    >
      <GrupoOpciones
        leyenda="¿Qué compraste?"
        nombre="comprado"
        valor={i.id}
        onCambio={setId}
        opciones={declarados.map((x) => ({ valor: x.id, texto: `${x.nombre} ${x.presentacion}` }))}
      />
      <Stepper etiqueta="¿Cuántos paquetes?" valor={paquetes} onCambio={setPaquetes} min={0} max={20} unidad={`de ${i.tamanoPaquete} ${i.unidad}`} />
      <Tarjeta tono="ok">
        <p aria-live="polite">
          Ajustamos la cuenta: antes alcanzaba hasta el <span className="cifras">{fechaFin(i, s.ahora)}</span>.{' '}
          <b>
            Ahora te alcanza hasta el <span className="cifras">{fechaFin(despues, s.ahora)}</span>.
          </b>
        </p>
        <BarraDias dias={diasRestantes(despues)} nivel={nivel(diasRestantes(despues))} />
      </Tarjeta>
    </Pantalla>
  )
}

export function Reponer() {
  const { s, haz } = useDemo()
  const pila = nombrePila(s)
  const lineas = lineasLista(s.insumos, s.ajustesLista)
  const conCompra = lineas.filter((l) => l.paquetes > 0)
  const total = totalEstimado(conCompra)
  const enCurso = s.pedido && s.pedido.estado !== 'borrador' && s.pedido.estado !== 'entregado'
  const btn = 'grid size-12 shrink-0 place-items-center rounded-xl bg-hoja text-pino ring-2 ring-inset ring-pino/60 hover:bg-rocio disabled:opacity-40'
  return (
    <Pantalla
      titulo="Qué reponer"
      pie={
        conCompra.length > 0 && (
          <>
            {enCurso ? (
              <Boton onClick={() => haz((x) => ir(x, 'seguimiento'))}>Ver el pedido en curso</Boton>
            ) : (
              <Boton icono={<ShoppingBag aria-hidden className="size-5" />} onClick={() => haz((x) => ir(armarPedido(x), 'pedido'))}>
                Pedir a domicilio por <span className="cifras">{fmtDinero(total)}</span> aprox.
              </Boton>
            )}
            <Boton variante="secundario" icono={<Share2 aria-hidden className="size-5" />} onClick={() => haz((x) => ir(x, 'exportar'))}>
              Exportar o compartir la lista
            </Boton>
          </>
        )
      }
    >
      {lineas.length === 0 ? (
        <Nota titulo="Por ahora no hace falta reponer nada">Todo alcanza para más de {COBERTURA_DIAS} días. Te avisamos antes.</Nota>
      ) : (
        <>
          <ul className="flex flex-col gap-2.5">
            {lineas.map((l) => (
              <li key={l.insumo.id} className="flex flex-col gap-2 rounded-[1.2rem] bg-hoja p-4 ring-1 ring-linea">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="font-bold">
                    {l.insumo.nombre} {l.insumo.presentacion}
                  </span>
                  <span className="cifras text-tenue">{fmtDinero(l.insumo.precio)} c/u</span>
                </div>
                <div className="flex flex-wrap items-center gap-3" role="group" aria-label={`Paquetes de ${l.insumo.nombre}`}>
                  <button type="button" className={btn} aria-label={`Un paquete menos de ${l.insumo.nombre}`} disabled={l.paquetes === 0} onClick={() => haz((x) => ajustarLista(x, l.insumo.id, l.paquetes - 1))}>
                    <Minus aria-hidden className="size-5" strokeWidth={2.5} />
                  </button>
                  <output aria-live="polite" className="cifras min-w-[2ch] text-center text-[1.4rem] font-bold">
                    {l.paquetes}
                  </output>
                  <button type="button" className={btn} aria-label={`Un paquete más de ${l.insumo.nombre}`} onClick={() => haz((x) => ajustarLista(x, l.insumo.id, l.paquetes + 1))}>
                    <Plus aria-hidden className="size-5" strokeWidth={2.5} />
                  </button>
                  <span className="text-tenue">{l.paquetes === 1 ? 'paquete' : 'paquetes'}</span>
                  <span className="cifras ml-auto font-bold">{fmtDinero(l.paquetes * l.insumo.precio)}</span>
                </div>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-t-2 border-tinta pt-3">
            <span className="font-bold">Total estimado</span>
            <span className="cifras text-[1.4rem] font-bold">{fmtDinero(total)}</span>
          </div>
          <p className="text-[0.95rem] text-tenue">
            Con esto {pila} queda cubierta unas {COBERTURA_DIAS / 7} semanas. La lista sirve aunque compres en otra parte.
          </p>
        </>
      )}
    </Pantalla>
  )
}

export function textoLista(nombre: string, fecha: string, lineas: ReturnType<typeof lineasLista>): string {
  const filas = lineas
    .filter((l) => l.paquetes > 0)
    .map((l) => `- ${l.insumo.nombre} ${l.insumo.presentacion}: ${l.paquetes} ${l.paquetes === 1 ? 'paquete' : 'paquetes'}`)
  return [`Lista de ${nombre}, ${fecha}`, ...filas].join('\n')
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
    if (navigator.share) {
      try {
        await navigator.share({ title: `Lista de ${pila}`, text: texto })
        return
      } catch {
        return
      }
    }
    await copiar()
  }
  const descargar = () => {
    const url = URL.createObjectURL(new Blob([texto + '\n'], { type: 'text/plain;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `lista-${pila.toLowerCase()}.txt`
    a.click()
    URL.revokeObjectURL(url)
    haz((x) => avisar(x, 'Lista descargada.'))
  }

  return (
    <Pantalla
      titulo="Lista lista"
      pie={
        <>
          <Boton icono={<Share2 aria-hidden className="size-5" />} onClick={compartir}>
            Compartir
          </Boton>
          <Fila>
            <Boton variante="secundario" icono={<Copy aria-hidden className="size-5" />} onClick={copiar}>
              Copiar
            </Boton>
            <Boton variante="secundario" icono={<Download aria-hidden className="size-5" />} onClick={descargar}>
              Descargar
            </Boton>
          </Fila>
        </>
      }
    >
      <div className="flex flex-col items-start gap-2 pt-1">
        <Sello>
          <FileText aria-hidden className="size-9" />
        </Sello>
        <p className="font-display text-[1.5rem] font-bold">Lista de {pila}</p>
        <p className="text-tenue">Para quien vaya a comprar. Sirve en cualquier farmacia.</p>
      </div>
      <pre className="cifras overflow-x-auto rounded-2xl bg-hoja p-4 text-[0.95rem] leading-relaxed break-words whitespace-pre-wrap ring-1 ring-linea">
        {texto}
      </pre>
    </Pantalla>
  )
}
