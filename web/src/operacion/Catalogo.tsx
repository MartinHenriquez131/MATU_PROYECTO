// Catálogo de prueba (especificación MATU-81, sección 11): el precio, la cantidad y si se ofrece cada
// producto de los comercios ficticios (C1, D-81-7). Un comercio real se lista en solo lectura. El
// precio es un entero en pesos con IVA incluido (C2) y vale solo para las confirmaciones nuevas (C3).
// Cambiarlo pide confirmar con el precio anterior; guardar usa `If-Match` (C4). Un editor a la vez.
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Ban, Check, Info, Tag } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { cambiarOferta, esProblema, verCatalogo, type OfertaConsola } from '../compartido/api/operacion'
import { anunciar } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { DialogoConfirmar } from '../familia/DialogoConfirmar'
import { Acciones, CampoTexto, MensajeError, Titulo } from '../familia/ui'
import { EtiquetaCon, Monto, pesos, useFocoAlMontar } from './comun'
import { useOperacion } from './estado'
import { RotuloPiloto } from './Marco'
import { CATALOGO as T, MARCO } from './textos'

/** 11.3: acepta «69000» y «69.000» (sin los puntos); no acepta comas, decimales ni letras. */
export function leerPrecio(v: string): number | null {
  const t = v.trim()
  // El punto solo como separador de miles, en grupos de tres: «69.000.5» o «69000.5» no son un precio.
  if (!/^\d+$/.test(t) && !/^\d{1,3}(\.\d{3})+$/.test(t)) return null
  const limpio = t.replace(/\./g, '')
  if (!/^\d{1,7}$/.test(limpio)) return null
  const n = Number(limpio)
  return n > 0 ? n : null
}
const leerCantidad = (v: string): number | 'numero' | 'maximo' => {
  if (!/^\d+$/.test(v.trim())) return 'numero'
  const n = Number(v.trim())
  return n > 9999 ? 'maximo' : n
}

type NotaFila = { tono: 'atenta'; texto: string; rol: 'status' | 'alert'; n: number }

export function PantallaCatalogo() {
  const { fallo } = useOperacion()
  const [ofertas, setOfertas] = useState<OfertaConsola[] | null>(null)
  const [error, setError] = useState(false)
  const [editando, setEditando] = useState<string | null>(null)
  /** 11.4: los que el servidor dijo que no son de prueba quedan en solo lectura aquí. */
  const [bloqueadas, setBloqueadas] = useState<Set<string>>(new Set())
  const [notas, setNotas] = useState<Record<string, NotaFila>>({})
  const contador = useRef(0)
  const pedirFoco = useFocoAlMontar()
  const verCargando = useDemora(1000)

  const traer = useCallback(async (): Promise<OfertaConsola[] | null> => {
    try {
      const o = await verCatalogo()
      setOfertas(o)
      setError(false)
      return o
    } catch (x) {
      if (!fallo(x, true)) setError(true)
      return null
    }
  }, [fallo])

  useEffect(() => {
    void traer()
  }, [traer])

  const notaEn = (id: string, texto: string, rol: 'status' | 'alert') => setNotas((x) => ({ ...x, [id]: { tono: 'atenta', texto, rol, n: ++contador.current } }))

  const comercios = new Map<string, { ficticio: boolean; ofertas: OfertaConsola[] }>()
  for (const o of ofertas ?? []) {
    const c = comercios.get(o.comercio.nombre_fantasia) ?? { ficticio: o.comercio.ficticio, ofertas: [] }
    c.ofertas.push(o)
    comercios.set(o.comercio.nombre_fantasia, c)
  }

  return (
    <div className="flex max-w-3xl flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Titulo className="text-3xl">{T.titulo}</Titulo>
        <Nota tono="rocio" borde icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {T.aviso}
        </Nota>
        <p className="max-w-prose text-base text-tenue">{T.soloPrueba}</p>
      </div>
      {error && (
        <div className="flex flex-col items-start gap-3">
          <Nota tono="pronto" rol="alert">
            {T.errorAlTraer}
          </Nota>
          <Boton variante="secundario" onClick={() => void traer()}>
            {MARCO.volverAIntentar}
          </Boton>
        </div>
      )}
      {!ofertas && !error && <p className="text-tenue">{verCargando ? T.cargando : ''}</p>}
      {ofertas && ofertas.filter((o) => o.editable).length === 0 && <p className="text-xl font-bold">{T.vacio}</p>}
      {[...comercios.entries()].map(([nombre, c], ic) => (
        <section key={nombre} aria-labelledby={`comercio-${ic}`} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <h2 id={`comercio-${ic}`} className="text-xl font-bold break-words">
              {nombre} {c.ficticio && <span className="inline-block">{T.ficticio}</span>}
            </h2>
            {!c.ofertas.some((o) => o.editable) && <p className="text-base text-tenue">{T.noEsDePrueba}</p>}
          </div>
          <ul className="flex flex-col gap-3">
            {c.ofertas.map((o) => (
              <li key={o.id} className="grid grid-cols-1 gap-x-6 gap-y-2 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea @xl/main:grid-cols-[minmax(0,1fr)_18rem]">
                <Producto
                  o={o}
                  editable={o.editable && !bloqueadas.has(o.id)}
                  abierto={editando === o.id}
                  otroAbierto={editando !== null && editando !== o.id}
                  nota={notas[o.id] ?? null}
                  onAbrir={() => {
                    setEditando(o.id)
                    setNotas((x) => Object.fromEntries(Object.entries(x).filter(([k]) => k !== o.id)))
                    pedirFoco(`editor-${o.id}`, 'input')
                  }}
                  onCerrar={() => {
                    setEditando(null)
                    pedirFoco(`cambiar-${o.id}`)
                  }}
                  onGuardado={(nueva) => {
                    setOfertas((l) => l?.map((x) => (x.id === nueva.id ? nueva : x)) ?? l)
                    setEditando(null)
                    anunciar(T.guardado(nueva.producto, nueva.precio, nueva.stock), 'status')
                    pedirFoco(`cambiar-${o.id}`)
                  }}
                  onConflicto={async () => {
                    await traer()
                    notaEn(o.id, T.otraPersona, 'status')
                  }}
                  onNoSePuede={() => {
                    setEditando(null)
                    setBloqueadas((b) => new Set(b).add(o.id))
                    notaEn(o.id, T.noSePuede, 'alert')
                  }}
                  fallo={fallo}
                />
              </li>
            ))}
          </ul>
        </section>
      ))}
      <RotuloPiloto />
    </div>
  )
}

function Producto({
  o,
  editable,
  abierto,
  otroAbierto,
  nota,
  onAbrir,
  onCerrar,
  onGuardado,
  onConflicto,
  onNoSePuede,
  fallo,
}: {
  o: OfertaConsola
  editable: boolean
  abierto: boolean
  otroAbierto: boolean
  nota: NotaFila | null
  onAbrir: () => void
  onCerrar: () => void
  onGuardado: (o: OfertaConsola) => void
  onConflicto: () => Promise<void>
  onNoSePuede: () => void
  fallo: (e: unknown) => boolean
}) {
  return (
    <>
      <div className="flex min-w-0 flex-col gap-0.5">
        <h3 className="text-lg font-bold break-words">{o.producto}</h3>
        <p className="text-base text-tenue break-words">{o.presentacion}</p>
        <p>
          <span className="text-lg font-bold">
            <Monto n={o.precio} />
          </span>{' '}
          <span className="text-tenue">· {T.ivaIncluido}</span>
        </p>
      </div>
      <div className="flex min-w-0 flex-col items-start gap-2">
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4">
          <dt>{T.tiene}</dt>
          <dd className="cifras">{o.stock}</dd>
        </dl>
        {o.disponible ? <EtiquetaCon Icono={Check} tono="ok" texto={T.seOfrece} /> : <EtiquetaCon Icono={Ban} tono="neutro" texto={T.noSeOfrece} />}
        {editable && !abierto && !otroAbierto && (
          <Boton id={`cambiar-${o.id}`} variante="secundario" onClick={onAbrir}>
            {T.cambiar}
          </Boton>
        )}
      </div>
      {nota && (
        <div key={nota.n} className="@xl/main:col-span-2">
          <Nota tono={nota.tono} rol={nota.rol}>
            {nota.texto}
          </Nota>
        </div>
      )}
      {abierto && (
        <div className="@xl/main:col-span-2">
          <Editor o={o} onCerrar={onCerrar} onGuardado={onGuardado} onConflicto={onConflicto} onNoSePuede={onNoSePuede} fallo={fallo} />
        </div>
      )}
    </>
  )
}

/** 11.1: el editor de un producto, en el lugar de «Cambiar». Lo escrito se conserva tras un 412. */
function Editor({
  o,
  onCerrar,
  onGuardado,
  onConflicto,
  onNoSePuede,
  fallo,
}: {
  o: OfertaConsola
  onCerrar: () => void
  onGuardado: (o: OfertaConsola) => void
  onConflicto: () => Promise<void>
  onNoSePuede: () => void
  fallo: (e: unknown) => boolean
}) {
  const [precio, setPrecio] = useState(String(o.precio))
  const [stock, setStock] = useState(String(o.stock))
  const [disponible, setDisponible] = useState(o.disponible)
  const [errPrecio, setErrPrecio] = useState(false)
  const [errStock, setErrStock] = useState<'numero' | 'maximo' | null>(null)
  const [confirmar, setConfirmar] = useState<{ precio: number; stock: number } | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [red, setRed] = useState(0)
  const version = useRef(o.version)
  const pedirFoco = useFocoAlMontar()

  // 11.4 (412): el editor sigue abierto con lo escrito, y guarda con la versión nueva.
  useEffect(() => {
    version.current = o.version
  }, [o.version])

  const guardar = async (cambios: { precio: number; stock: number }): Promise<boolean> => {
    setOcupado(true)
    try {
      onGuardado(await cambiarOferta(o.id, { precio: cambios.precio, stock: cambios.stock, disponible }, version.current))
      return true
    } catch (x) {
      if (fallo(x)) return true
      const f = leerFallo(x)
      if (f.status === 412) {
        await onConflicto()
        return true
      }
      if ((f.status === 409 && esProblema(f.tipo, 'comercio-real')) || f.status === 404) {
        onNoSePuede()
        return true
      }
      setRed((n) => n + 1)
      return true
    } finally {
      setOcupado(false)
    }
  }

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado) return
    const p = leerPrecio(precio)
    const s = leerCantidad(stock)
    setErrPrecio(p === null)
    setErrStock(typeof s === 'number' ? null : s)
    if (p === null) return pedirFoco(`editor-${o.id}`, 'input')
    if (typeof s !== 'number') return pedirFoco(`editor-${o.id}-stock`, 'input')
    setRed(0)
    // 11.3: con el precio cambiado, antes de enviar, se confirma con el precio anterior.
    if (p !== o.precio) return setConfirmar({ precio: p, stock: s })
    await guardar({ precio: p, stock: s })
  }

  const p = leerPrecio(precio)
  return (
    <form noValidate onSubmit={(e) => void enviar(e)} className="flex flex-col gap-4 border-t border-linea pt-4">
      <div id={`editor-${o.id}`} className="flex flex-col gap-1.5">
        <label htmlFor={`precio-${o.id}`} className="font-bold">
          {T.precioEtiqueta}
        </label>
        <div className="flex max-w-48 items-center gap-2">
          <span aria-hidden className="text-tenue">
            $
          </span>
          <input
            id={`precio-${o.id}`}
            inputMode="numeric"
            autoComplete="off"
            value={precio}
            onChange={(e) => {
              setPrecio(e.target.value)
              setErrPrecio(false)
            }}
            aria-invalid={errPrecio || undefined}
            aria-describedby={`precio-${o.id}-ayuda${errPrecio ? ` precio-${o.id}-error` : ''}`}
            className={`cifras min-h-12 w-full min-w-0 rounded-xl bg-hoja px-4 py-2.5 ring-2 ring-inset focus-visible:ring-turquesa ${errPrecio ? 'ring-pronto' : 'ring-borde'}`}
          />
        </div>
        <p id={`precio-${o.id}-ayuda`} aria-live="polite" className="cifras text-base whitespace-normal text-tenue">
          {p !== null ? T.seVeraComo(pesos(p)) : ''}
        </p>
        {errPrecio && <MensajeError id={`precio-${o.id}-error`}>{T.errPrecio}</MensajeError>}
      </div>
      <div id={`editor-${o.id}-stock`}>
        <CampoTexto
          etiqueta={T.cuantos}
          className="max-w-40"
          inputMode="numeric"
          autoComplete="off"
          value={stock}
          onChange={(e) => {
            setStock(e.target.value)
            setErrStock(null)
          }}
          error={errStock === 'numero' ? T.errNumero : errStock === 'maximo' ? T.errMaximo : null}
        />
      </div>
      <label className="flex min-h-12 cursor-pointer items-center gap-3 font-bold">
        <input type="checkbox" checked={disponible} onChange={(e) => setDisponible(e.target.checked)} className="size-6 shrink-0 accent-turquesa" />
        {T.seOfreceEnMatu}
      </label>
      {red > 0 && (
        <div key={red}>
          <Nota tono="pronto" rol="alert">
            {T.error}
          </Nota>
        </div>
      )}
      <Acciones>
        <Boton type="submit" ocupado={ocupado && !confirmar} textoOcupado={T.guardando}>
          {T.guardar}
        </Boton>
        <Boton variante="texto" onClick={onCerrar}>
          {T.cancelar}
        </Boton>
      </Acciones>
      {confirmar && (
        <DialogoConfirmar
          titulo={T.dialogoTitulo(o.producto, confirmar.precio)}
          texto={T.dialogoTexto(o.precio)}
          destacado={T.dialogoDestacado}
          confirmar={T.cambiarPrecio}
          confirmando={T.guardando}
          seguir={T.volverAEditar}
          error={T.error}
          variante="principal"
          icono={<Tag aria-hidden className="size-5" />}
          onConfirmar={async () => {
            const ok = await guardar(confirmar)
            setConfirmar(null)
            return ok
          }}
          onCerrar={() => {
            setConfirmar(null)
            pedirFoco(`editor-${o.id}`, 'input')
          }}
        />
      )}
    </form>
  )
}
