// «Lista de insumos» de la app de la familia (MATU-60, RF-15, ADR-031; especificación
// docs/diseno/matu-60-lista-insumos.md v1.2). Lo que hoy está en «Se acaban pronto», con una
// cantidad sugerida para 30 días, que la familia ajusta, imprime, copia o comparte como texto.
//
// Nada de esto se guarda: las cantidades cambiadas, las líneas agregadas a mano y las quitadas
// viven en la memoria de la página y nunca llegan al servidor, ni a localStorage, sessionStorage,
// la URL, `history.state` o `document.title` (salvo «Lista de insumos» al imprimir). La lista se
// pide de nuevo cada vez que se abre la pantalla, y si falla nunca se muestra una vieja.
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { CircleAlert, CloudOff, Copy, Hourglass, Info, ListChecks, Lock, Pencil, Plus, Printer, Share2 } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { nombrePilaDe } from '../compartido/api/familia'
import { verListaInsumos, type LineaListaInsumos } from '../compartido/api/consumo'
import { esVencida } from '../compartido/api/sesion'
import { anunciar, Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { useDemora } from './Estados'
import { puedeEditar, useFamilia } from './estado'
import { PestanasInsumos } from './Insumos'
import { enfocar, entero, permisoDe, Stepper, unaLinea, useAncho } from './insumosComun'
import { navegar } from './ruteo'
import { FICHA, GENERAL, LISTA } from './textos'
import { armarLista, cantidadEnTexto, sufijoCantidad, textoDeLista, type LineaParaSacar, type UnidadLinea } from './textoLista'
import { INSUMOS } from './textosInsumos'
import { Acciones, Etiqueta, GrupoOpciones, MensajeError, Nota, Titulo } from './ui'

type Carga = 'cargando' | 'listo' | 'sin-consentimiento' | 'revision-vencida' | 'no-encontrado' | 'red'
type Mensaje = 'copiada' | 'err-copiar' | 'err-compartir'
type UnidadAMano = 'unidad' | 'sobre' | 'envase'

/** 4.4: de 1 a 100.000, o hasta lo sugerido si la API sugiere más. */
const CANTIDAD_MAX = 100_000
const NOMBRE_MAX = 60
const ID_AGREGAR = 'agregar-otro-insumo'

/** Una línea en la memoria de la página. `clave` es el `perfil_id` (nunca se muestra) o una propia. */
interface Linea {
  clave: string
  nombre: string
  unidad: UnidadLinea
  envase: number | null
  /** `null` en lo agregado a mano: no tiene días. */
  dias: number | null
  deMatu: boolean
  /** Lo escrito en el campo, tal cual. */
  valor: string
  /** 8.3: con Ctrl+P y una cantidad inválida, la hoja usa el último valor válido. */
  ultimoValido: number
  max: number
}

const desdeApi = (l: LineaListaInsumos): Linea => {
  const sugerida = l.envases_sugeridos ?? l.unidades_sugeridas
  return {
    clave: l.perfil_id,
    nombre: l.nombre,
    unidad: l.unidad,
    envase: l.envases_sugeridos === null ? null : l.unidades_por_envase,
    dias: l.dias_restantes,
    deMatu: true,
    valor: String(sugerida),
    ultimoValido: sugerida,
    max: Math.max(CANTIDAD_MAX, sugerida),
  }
}

const valida = (l: Linea, v = l.valor) => {
  const n = entero(v)
  return n !== null && n >= 1 && n <= l.max ? n : null
}

const idCantidad = (clave: string) => `cantidad-${clave}`

/** 4.9: la hoja de compartir del teléfono, si existe y acepta texto. */
function hayCompartir(): boolean {
  if (typeof navigator === 'undefined' || typeof navigator.share !== 'function') return false
  if (typeof navigator.canShare !== 'function') return true
  try {
    return navigator.canShare({ text: LISTA.titulo })
  } catch {
    return false
  }
}

// ---------------------------------------------------------------- pantalla

export function ListaDeInsumos() {
  const { persona, rol, personaId } = useFamilia()
  const editor = puedeEditar(rol)
  // 2.4: admin, cuidador y pagador cambian, agregan, quitan y sacan la lista. El observador solo la ve.
  const puede = rol !== 'observador'
  const pila = persona ? (nombrePilaDe(persona).trim().split(/\s+/)[0] ?? '') : ''
  const { ref, ancho } = useAncho()
  const [compartirNativo] = useState(hayCompartir)

  const [carga, setCarga] = useState<Carga>('cargando')
  const [fecha, setFecha] = useState('')
  const [lineas, setLineas] = useState<Linea[]>([])
  const [errores, setErrores] = useState<ReadonlySet<string>>(new Set())
  const [quitoAlguna, setQuitoAlguna] = useState(false)
  const [quitoDeMatu, setQuitoDeMatu] = useState(false)
  const [panel, setPanel] = useState(false)
  const [mensaje, setMensaje] = useState<{ tipo: Mensaje; n: number } | null>(null)
  const contador = useRef(0)

  const cargar = async () => {
    if (!personaId) return
    setCarga('cargando')
    try {
      const r = await verListaInsumos(personaId)
      setFecha(r.fecha)
      setLineas(r.items.map(desdeApi))
      setErrores(new Set())
      setQuitoAlguna(false)
      setQuitoDeMatu(false)
      setMensaje(null)
      setCarga('listo')
    } catch (x) {
      if (esVencida(x)) return
      const permiso = permisoDe(x)
      if (permiso) return setCarga(permiso)
      setCarga(leerFallo(x).status === 404 ? 'no-encontrado' : 'red')
    }
  }

  // 3.1: se pide al llegar, y otra vez cada vez que se vuelve a entrar (la pantalla se monta de nuevo).
  useEffect(() => {
    void cargar()
  }, [personaId]) // `cargar` lee `personaId`: basta con él

  // 6.2: admin o cuidador sin el permiso van a Insumos, que es el único lugar donde se da.
  useEffect(() => {
    if (carga === 'sin-consentimiento' && editor) navegar('/insumos', { reemplazar: true })
  }, [carga, editor])

  // 8.3: Ctrl+P y el menú del navegador cambian el título igual que el botón.
  useEffect(() => {
    const antes = () => {
      document.title = LISTA.documentoImpreso
    }
    const despues = () => {
      document.title = `${LISTA.titulo} · MATU`
    }
    window.addEventListener('beforeprint', antes)
    window.addEventListener('afterprint', despues)
    return () => {
      window.removeEventListener('beforeprint', antes)
      window.removeEventListener('afterprint', despues)
    }
  }, [])

  // 10.4: el mensaje bajo los botones queda a la vista.
  useEffect(() => {
    if (mensaje) document.getElementById('mensaje-lista')?.scrollIntoView?.({ block: 'nearest' })
  }, [mensaje])

  /** 7.3: lo copiado ya no es lo que se ve. */
  const cambio = () => setMensaje((m) => (m?.tipo === 'copiada' ? null : m))

  const alCambiar = (clave: string, v: string) => {
    setLineas((xs) => xs.map((l) => (l.clave === clave ? { ...l, valor: v, ultimoValido: valida(l, v) ?? l.ultimoValido } : l)))
    const l = lineas.find((x) => x.clave === clave)
    if (l && valida(l, v) !== null && errores.has(clave))
      setErrores((e) => {
        const n = new Set(e)
        n.delete(clave)
        return n
      })
    cambio()
  }

  const quitar = (clave: string) => {
    const i = lineas.findIndex((l) => l.clave === clave)
    if (i < 0) return
    const l = lineas[i]
    const siguiente = lineas[i + 1]
    setLineas((xs) => xs.filter((x) => x.clave !== clave))
    setErrores((e) => {
      const n = new Set(e)
      n.delete(clave)
      return n
    })
    setQuitoAlguna(true)
    if (l.deMatu) setQuitoDeMatu(true)
    cambio()
    anunciar(l.deMatu ? LISTA.quitamosDeMatu(l.nombre) : LISTA.quitamos(l.nombre), 'status')
    enfocar(siguiente ? idCantidad(siguiente.clave) : ID_AGREGAR)
  }

  const agregar = (nombre: string, unidad: UnidadAMano, cantidad: number) => {
    contador.current += 1
    const clave = `a-mano-${contador.current}`
    setLineas((xs) => [...xs, { clave, nombre, unidad, envase: null, dias: null, deMatu: false, valor: String(cantidad), ultimoValido: cantidad, max: CANTIDAD_MAX }])
    setPanel(false)
    cambio()
    anunciar(LISTA.agregamos(nombre), 'status')
    enfocar(ID_AGREGAR)
  }

  const cerrarPanel = () => {
    setPanel(false)
    enfocar(ID_AGREGAR)
  }

  const paraSacar: LineaParaSacar[] = lineas.map((l) => ({ nombre: l.nombre, cantidad: valida(l) ?? l.ultimoValido, unidad: l.unidad, envase: l.envase }))
  // 8.5: el observador imprime solo el título, su nota y el pie.
  const hoja = armarLista(fecha, puede ? paraSacar : [])

  /** 4.4: al tocar un botón de salida. Con error, nada sale del teléfono y el foco va al primero. */
  const validarSalida = () => {
    const malas = lineas.filter((l) => valida(l) === null)
    setErrores(new Set(malas.map((l) => l.clave)))
    if (malas.length) {
      document.getElementById(idCantidad(malas[0].clave))?.focus()
      return false
    }
    return true
  }

  const avisar = (tipo: Mensaje | null) => setMensaje(tipo ? { tipo, n: (mensaje?.n ?? 0) + 1 } : null)

  const compartir = async () => {
    if (!validarSalida()) return
    avisar(null)
    try {
      // 7.1: solo `text`. Sin `title`, `url` ni `files`.
      await navigator.share({ text: textoDeLista(hoja) })
    } catch (x) {
      if (x instanceof Error && x.name === 'AbortError') return
      if (typeof x === 'object' && x && (x as { name?: unknown }).name === 'AbortError') return
      avisar('err-compartir')
    }
  }

  const copiar = async () => {
    if (!validarSalida()) return
    try {
      if (!navigator.clipboard?.writeText) throw new Error('sin portapapeles')
      await navigator.clipboard.writeText(textoDeLista(hoja))
      avisar('copiada')
    } catch {
      avisar('err-copiar')
    }
  }

  const imprimir = async () => {
    if (!validarSalida()) return
    avisar(null)
    try {
      await document.fonts?.ready
    } catch {
      // Sin fuentes listas se imprime igual.
    }
    document.title = LISTA.documentoImpreso
    window.print()
  }

  // ---------------------------------------------------------------- composición

  const encabezado = (
    <div className="flex flex-col gap-3">
      <PestanasInsumos activa="/insumos/lista" />
      <div>
        <Titulo className="text-3xl @2xl/main:text-5xl">{LISTA.titulo}</Titulo>
        {carga === 'listo' && <p className="mt-1.5 max-w-prose text-base text-tenue">{puede ? LISTA.bajada : LISTA.bajadaObservador}</p>}
      </div>
    </div>
  )

  const cuerpo = () => {
    if (carga === 'cargando') return <Cargando />
    if (carga === 'sin-consentimiento') {
      if (editor) return null
      return (
        <UnaColumna tono="neutro" icono={<Lock aria-hidden className="size-9" />}>
          <p className="max-w-prose text-lg">
            <strong>{INSUMOS.faltaPermisoTitulo(pila)}</strong> {INSUMOS.faltaPermiso(pila)}
          </p>
        </UnaColumna>
      )
    }
    if (carga === 'revision-vencida')
      return (
        <UnaColumna tono="atenta" icono={<Hourglass aria-hidden className="size-9" />}>
          <div className="flex max-w-prose flex-col gap-3 text-lg">
            <p>
              <strong>{INSUMOS.renovarTitulo(pila)}</strong> {INSUMOS.renovar}
            </p>
            <p>{INSUMOS.renovarPide}</p>
            <p>
              <a href={FICHA.chileAtiendeUrl} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-12 items-center text-turquesa underline underline-offset-4">
                {FICHA.chileAtiende}
              </a>{' '}
              <span className="text-tenue">{FICHA.chileAtiendeNota}</span>
            </p>
          </div>
        </UnaColumna>
      )
    if (carga === 'no-encontrado')
      return (
        <UnaColumna tono="neutro" icono={<CircleAlert aria-hidden className="size-9" />}>
          <p className="max-w-prose text-lg">{GENERAL.noEncontrado}</p>
          <a
            href="/"
            onClick={(e) => {
              e.preventDefault()
              navegar('/')
            }}
            className="inline-flex min-h-12 items-center font-bold text-turquesa underline underline-offset-4"
          >
            {INSUMOS.volverAlInicio}
          </a>
        </UnaColumna>
      )
    if (carga === 'red')
      return (
        <UnaColumna tono="neutro" icono={<CloudOff aria-hidden className="size-9" />}>
          <Anunciado urgencia="alert" como="p" className="max-w-prose text-lg">
            {LISTA.errCarga}
          </Anunciado>
          <Boton onClick={() => void cargar()}>{GENERAL.volverAIntentar}</Boton>
        </UnaColumna>
      )

    const hay = lineas.length > 0
    const nota = rol === 'pagador' ? LISTA.notaPagador : rol === 'observador' ? LISTA.notaObservador : LISTA.nota

    const botonAgregar =
      puede &&
      (panel ? (
        <PanelAgregar onAgregar={agregar} onCancelar={cerrarPanel} />
      ) : (
        <Boton
          id={ID_AGREGAR}
          variante="secundario"
          icono={<Plus aria-hidden className="size-5" />}
          aria-expanded={false}
          className="self-start"
          onClick={() => {
            setPanel(true)
          }}
        >
          {LISTA.agregarOtro}
        </Boton>
      ))
    const sigue = quitoDeMatu && <p className="max-w-prose text-base text-tenue">{LISTA.sigueEnInsumos}</p>

    let izquierda
    if (hay)
      izquierda = (
        <>
          <ul className="@container/lista flex flex-col gap-2">
            {lineas.map((l) => (
              <LineaDeLista key={l.clave} linea={l} puede={puede} error={errores.has(l.clave)} onCambio={(v) => alCambiar(l.clave, v)} onQuitar={() => quitar(l.clave)} />
            ))}
          </ul>
          <p className="max-w-prose text-base text-tenue">{nota}</p>
          {sigue}
          {botonAgregar}
        </>
      )
    else if (!quitoAlguna)
      // 5: el vacío que trae la API.
      izquierda = (
        <div className="flex flex-col items-start gap-4">
          <span className={`grid size-16 place-items-center rounded-2xl ${puede ? 'bg-rocio text-turquesa' : 'bg-tinta/7 text-tenue'}`}>
            <ListChecks aria-hidden className="size-9" />
          </span>
          <p className="max-w-prose text-lg">{puede ? LISTA.vacio : LISTA.vacioObservador}</p>
          {botonAgregar}
        </div>
      )
    // 4.10: se quitaron todas.
    else
      izquierda = (
        <>
          <p className="max-w-prose text-lg">{LISTA.quitasteTodo}</p>
          {sigue}
          {botonAgregar}
        </>
      )

    const derecha = !hay ? null : puede ? (
      <>
        <Nota tono="atenta" borde id="aviso-lista" icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
          <p>{LISTA.aviso(pila)}</p>
        </Nota>
        <Acciones>
          {compartirNativo && (
            <Boton icono={<Share2 aria-hidden className="size-5" />} aria-describedby="aviso-lista" onClick={() => void compartir()}>
              {LISTA.compartir}
            </Boton>
          )}
          <Boton
            variante={compartirNativo ? 'secundario' : 'principal'}
            icono={<Printer aria-hidden className="size-5" />}
            aria-describedby={compartirNativo ? undefined : 'aviso-lista'}
            onClick={() => void imprimir()}
          >
            {LISTA.imprimir}
          </Boton>
          <Boton variante="secundario" icono={<Copy aria-hidden className="size-5" />} onClick={() => void copiar()}>
            {LISTA.copiar}
          </Boton>
        </Acciones>
        {mensaje && (
          <div id="mensaje-lista" key={mensaje.n} className="max-w-prose">
            {mensaje.tipo === 'copiada' ? (
              <Nota tono="ok" rol="status" className="animate-aparecer">
                <p>{LISTA.copiada}</p>
              </Nota>
            ) : (
              <Anunciado urgencia="alert">
                <MensajeError>
                  {mensaje.tipo === 'err-compartir' ? LISTA.errCompartir : compartirNativo ? LISTA.errCopiarCompartir : LISTA.errCopiarImprimir}
                </MensajeError>
              </Anunciado>
            )}
          </div>
        )}
      </>
    ) : (
      <p className="max-w-prose text-base text-tenue">{LISTA.observador}</p>
    )

    // 2.3 (v1.2): el observador no tiene salida, así que en ancho va en una sola columna, sin la derecha.
    if (ancho && derecha && puede)
      return (
        <div className="grid grid-cols-[3fr_2fr] items-start gap-10">
          <div className="flex min-w-0 flex-col gap-5">{izquierda}</div>
          <div className="sticky top-6 flex min-w-0 flex-col items-start gap-4">{derecha}</div>
        </div>
      )
    return (
      <div className={`flex flex-col gap-5 ${puede ? '' : 'max-w-3xl'}`}>
        {izquierda}
        {derecha && (puede ? <div className="flex flex-col items-start gap-4">{derecha}</div> : derecha)}
      </div>
    )
  }

  return (
    <div ref={ref} className="flex min-w-0 flex-col gap-5">
      {encabezado}
      {cuerpo()}
      {carga === 'listo' && <HojaImpresa titulo={hoja.titulo} lineas={hoja.lineas.map((h, i) => ({ ...h, clave: lineas[i]?.clave ?? String(i) }))} pie={hoja.pie} observador={!puede} />}
    </div>
  )
}

// ---------------------------------------------------------------- piezas

function Cargando() {
  const ver = useDemora()
  return (
    <div aria-busy="true">
      <p role="status" className="text-lg text-tenue">
        {ver ? INSUMOS.cargando : ''}
      </p>
    </div>
  )
}

function UnaColumna({ tono, icono, children }: { tono: 'neutro' | 'atenta'; icono: ReactNode; children: ReactNode }) {
  const fondo = tono === 'atenta' ? 'bg-atenta-fondo text-atenta' : 'bg-tinta/7 text-tenue'
  return (
    <div className="flex flex-col items-start gap-5">
      <span className={`grid size-16 place-items-center rounded-2xl ${fondo}`}>{icono}</span>
      {children}
    </div>
  )
}

/** 4.3: los días, solo en la pantalla. Nunca solo por color: 0 y negativo cambian la palabra y suman el ícono. */
function Dias({ n }: { n: number }) {
  if (n <= 0)
    return (
      <p className="flex gap-1.5 text-base font-bold text-tinta">
        <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />
        <span className="min-w-0">{n === 0 ? LISTA.seAcabaHoy : LISTA.puedeQueNo}</span>
      </p>
    )
  return (
    <p className="text-base text-tenue">
      {LISTA.alcanzaPara} <span className="cifras">{n}</span> {n === 1 ? 'día' : 'días'}
    </p>
  )
}

function LineaDeLista({ linea: l, puede, error, onCambio, onQuitar }: { linea: Linea; puede: boolean; error: boolean; onCambio: (v: string) => void; onQuitar: () => void }) {
  const idNombre = `nombre-${l.clave}`
  const n = entero(l.valor)
  return (
    <li
      className={`grid grid-cols-1 items-start gap-x-6 gap-y-2 rounded-xl bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea @2xl/lista:items-center ${
        puede ? '@2xl/lista:grid-cols-[minmax(0,1fr)_20rem_auto]' : '@2xl/lista:grid-cols-[minmax(0,1fr)_auto]'
      }`}
    >
      <div className="flex min-w-0 flex-col gap-1">
        <p id={idNombre} className="text-lg font-bold break-words [overflow-wrap:anywhere]">
          {l.nombre}
        </p>
        {l.dias === null ? (
          <span>
            <Etiqueta>
              <Pencil aria-hidden className="size-4 shrink-0" />
              {LISTA.soloAqui}
            </Etiqueta>
          </span>
        ) : (
          <Dias n={l.dias} />
        )}
      </div>
      {puede ? (
        <>
          <Stepper
            id={idCantidad(l.clave)}
            etiqueta={LISTA.cantidad}
            nombradoPor={idNombre}
            textoMenos={LISTA.menos(l.nombre)}
            textoMas={LISTA.mas(l.nombre)}
            sufijo={sufijoCantidad(n ?? 0, l.unidad, l.envase)}
            valor={l.valor}
            onCambio={onCambio}
            min={1}
            max={l.max}
            error={error ? LISTA.errCantidad : null}
          />
          <Boton variante="textoPeligro" aria-label={LISTA.quitarDe(l.nombre)} className="mt-2 justify-self-end text-right @2xl/lista:mt-0" onClick={onQuitar}>
            {LISTA.quitar}
          </Boton>
        </>
      ) : (
        <p className="text-lg tabular-nums @2xl/lista:text-right">{cantidadEnTexto(l.ultimoValido, l.unidad, l.envase)}</p>
      )}
    </li>
  )
}

/** 4.7: el panel que se abre en el lugar. «Unidades» elegida al abrir, nada se guarda. */
function PanelAgregar({ onAgregar, onCancelar }: { onAgregar: (nombre: string, unidad: UnidadAMano, cantidad: number) => void; onCancelar: () => void }) {
  const uid = useId()
  const [nombre, setNombre] = useState('')
  const [unidad, setUnidad] = useState<UnidadAMano>('unidad')
  const [valor, setValor] = useState('1')
  const [errores, setErrores] = useState<{ nombre?: string; cantidad?: string }>({})
  const idNombre = `${uid}-nombre`
  const idCant = `${uid}-cantidad`

  useEffect(() => {
    document.getElementById(idNombre)?.focus()
  }, [idNombre])

  const enviar = (e: FormEvent) => {
    e.preventDefault()
    const limpio = unaLinea(nombre).trim()
    const n = entero(valor)
    const err: { nombre?: string; cantidad?: string } = {}
    if (!limpio) err.nombre = LISTA.errNombre
    else if (limpio.length > NOMBRE_MAX) err.nombre = LISTA.errNombreLargo
    if (n === null || n < 1 || n > CANTIDAD_MAX) err.cantidad = LISTA.errCantidad
    setErrores(err)
    if (err.nombre) return void document.getElementById(idNombre)?.focus()
    if (err.cantidad) return void document.getElementById(idCant)?.focus()
    onAgregar(limpio, unidad, n!)
  }

  const describeNombre = [`${idNombre}-a`, errores.nombre ? `${idNombre}-e` : ''].filter(Boolean).join(' ')
  return (
    <form
      noValidate
      onSubmit={enviar}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onCancelar()
        }
      }}
      className="flex flex-col gap-5 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea"
    >
      <div className="flex min-w-0 flex-col gap-1.5">
        <label htmlFor={idNombre} className="font-bold">
          {LISTA.nombre}
        </label>
        <span id={`${idNombre}-a`} className="text-base text-tenue">
          {LISTA.nombreAyuda}
        </span>
        <input
          id={idNombre}
          type="text"
          value={nombre}
          maxLength={NOMBRE_MAX}
          autoComplete="off"
          enterKeyHint="next"
          aria-invalid={errores.nombre ? true : undefined}
          aria-describedby={describeNombre}
          onChange={(e) => {
            setNombre(unaLinea(e.target.value))
            if (errores.nombre) setErrores((x) => ({ ...x, nombre: undefined }))
          }}
          className={`min-h-12 w-full max-w-xl min-w-0 rounded-xl bg-hoja px-4 py-2.5 ring-2 ring-inset focus-visible:ring-turquesa ${errores.nombre ? 'ring-pronto' : 'ring-borde'}`}
        />
        {errores.nombre && <MensajeError id={`${idNombre}-e`}>{errores.nombre}</MensajeError>}
      </div>
      <GrupoOpciones forma="chips" leyenda={LISTA.comoSeCuenta} nombre={`${uid}-unidad`} valor={unidad} onCambio={setUnidad} opciones={LISTA.unidades} />
      <Stepper
        id={idCant}
        etiqueta={LISTA.cantidad}
        sufijo={sufijoCantidad(entero(valor) ?? 0, unidad, null)}
        valor={valor}
        onCambio={(v) => {
          setValor(v)
          const n = entero(v)
          if (errores.cantidad && n !== null && n >= 1 && n <= CANTIDAD_MAX) setErrores((x) => ({ ...x, cantidad: undefined }))
        }}
        min={1}
        max={CANTIDAD_MAX}
        error={errores.cantidad}
      />
      <p className="max-w-prose text-base text-tenue">{LISTA.soloAquiNota}</p>
      <Acciones>
        <Boton type="submit" variante="secundario">
          {LISTA.agregar}
        </Boton>
        <button type="button" onClick={onCancelar} className="inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa">
          {LISTA.cancelar}
        </button>
      </Acciones>
    </form>
  )
}

/**
 * 8: la hoja de impresión, fuera de `#raiz`, con la misma `armarLista` del texto compartido. En
 * pantalla no existe (`hidden`). La regla de index.css (8.4) deja fuera del papel todo lo demás.
 */
function HojaImpresa({ titulo, lineas, pie, observador }: { titulo: string; lineas: { clave: string; nombre: string; cantidad: string }[]; pie: string; observador: boolean }) {
  return createPortal(
    <div data-impresion="" className="hidden bg-hoja font-sans text-tinta print:block">
      <p className="break-after-avoid border-b-2 border-tinta pb-2 text-2xl font-bold">{titulo}</p>
      {observador ? (
        <p className="py-3 text-lg">{LISTA.observador}</p>
      ) : (
        <ul>
          {lineas.map((l) => (
            <li key={l.clave} className="grid break-inside-avoid grid-cols-[auto_minmax(0,1fr)_auto] items-baseline gap-x-4 border-b border-borde py-3 text-lg">
              <span aria-hidden className="inline-block size-4 rounded-sm border-2 border-tinta" />
              <span className="min-w-0 font-bold break-words">{l.nombre}</span>
              <span className="text-right">{l.cantidad}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-8 text-base">{pie}</p>
    </div>,
    document.body,
  )
}
