// «Insumos» de la app de la familia (MATU-36, especificación docs/diseno/matu-36-insumos.md):
// el permiso la primera vez, la lista con «Seguir» y la papelera, anotar o cambiar un insumo con
// `If-Match`, el conflicto 412 a la vista y el diálogo de eliminar. Sin interfaz optimista: la
// lista cambia solo con la respuesta de la API. Nada se guarda en el navegador ni en la URL.
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Bell, BellRing, CalendarCheck, Check, CircleAlert, CircleCheck, Hourglass, ListChecks, Lock, PauseCircle, Plus, Trash2, TriangleAlert } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  autorizarConsumo,
  crearPerfil,
  editarPerfil,
  eliminarPerfil,
  leerConflictoPerfil,
  listarConsumo,
  listarPorAcabarse,
  resolverAviso,
  type PorAcabarse,
  nombreDe,
  seguirPerfil,
  type Perfil,
  type SolicitudEdicion,
  type Unidad,
} from '../compartido/api/consumo'
import { nombrePilaDe, type Calidad } from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { fechaCorta, hoyEnChile, sumarDias } from '../compartido/fechas'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { AVISO_CUIDADOR, CALIDADES } from './datos'
import { useDemora } from './Estados'
import { puedeEditar, useFamilia } from './estado'
import { navegar, useRuta } from './ruteo'
import { enfocar, entero, esTipo, permisoDe, soloDigitos, Stepper, unaLinea, useAncho } from './insumosComun'
import { AUTORIZACION, FICHA, GENERAL, LISTA } from './textos'
import { miles, sufijoCantidad } from './textoLista'
import { ALERTAS, cantidad, DECLARACION_CONSUMO, diasEnTexto, INSUMOS, lineaDias } from './textosInsumos'
import { Acciones, CampoTexto, GrupoOpciones, MensajeError, Nota, Pestanas, Titulo, Volver } from './ui'

type Carga = 'cargando' | 'listo' | 'sin-consentimiento' | 'revision-vencida' | 'no-encontrado' | 'red'

/** Los que se siguen, el que se acaba primero arriba (el orden de la API). */
const porFecha = (a: Perfil, b: Perfil) => a.fecha_quiebre_estimada.localeCompare(b.fecha_quiebre_estimada)

/**
 * MATU-60 (2.1): las vistas de la sección, antes del título. En `/insumos` con la lista cargada y en
 * `/insumos/lista` en todos sus estados. No en el permiso, en «Falta el permiso», en «Hay que
 * renovar» ni en el formulario a 360 px.
 */
export function PestanasInsumos({ activa }: { activa: '/insumos' | '/insumos/lista' }) {
  return (
    <Pestanas
      etiqueta={LISTA.vistas}
      items={[
        { texto: INSUMOS.titulo, ruta: '/insumos', activa: activa === '/insumos' },
        { texto: LISTA.titulo, ruta: '/insumos/lista', activa: activa === '/insumos/lista' },
      ]}
    />
  )
}

/**
 * MATU-37: el campo opcional «¿Compraste? ¿Cuántos?» de «Ya lo resolví» (aprobado por Jorge el
 * 03-11). Con cantidad, el backend la suma a lo que estima que queda hoy y devuelve el insumo
 * recalculado; sin cantidad, solo descarta. Apagarla deja solo la confirmación sin cantidad.
 */
const CANTIDAD_EN_RESOLVER = true

// ---------------------------------------------------------------- pantalla

export function Insumos() {
  const { persona, rol, personaId } = useFamilia()
  const ruta = useRuta()
  const editor = puedeEditar(rol)
  // Observador y pagador reciben solo `nombre`: se muestra la primera palabra como nombre de pila.
  const pila = persona ? (nombrePilaDe(persona).trim().split(/\s+/)[0] ?? '') : ''
  const { ref, ancho } = useAncho()

  const [carga, setCarga] = useState<Carga>('cargando')
  const [items, setItems] = useState<Perfil[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [cargandoMas, setCargandoMas] = useState(false)
  const [errorMas, setErrorMas] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)
  const [editandoId, setEditandoId] = useState<string | null>(null)
  const [ocupadoId, setOcupadoId] = useState<string | null>(null)
  const [errorFila, setErrorFila] = useState<{ id: string; texto: string } | null>(null)
  const [eliminando, setEliminando] = useState<Perfil | null>(null)
  // MATU-37: lo que se acaba pronto. `null` mientras no llega o si falló (errorBloque).
  const [porAcabarse, setPorAcabarse] = useState<PorAcabarse[] | null>(null)
  const [errorBloque, setErrorBloque] = useState(false)
  const [avisoAlerta, setAvisoAlerta] = useState<string | null>(null)

  /** La lista y el bloque se piden juntos y se pintan cuando llegan ambos (MATU-37, 4.2). */
  const cargar = useCallback(
    async (silencioso = false) => {
      if (!personaId) return
      if (!silencioso) setCarga('cargando')
      const [lista, bloque] = await Promise.allSettled([listarConsumo(personaId, null), listarPorAcabarse(personaId)])
      if (lista.status === 'rejected') {
        const x: unknown = lista.reason
        if (esVencida(x)) return
        const permiso = permisoDe(x)
        if (permiso) return setCarga(permiso)
        return setCarga(leerFallo(x).status === 404 ? 'no-encontrado' : 'red')
      }
      setItems(lista.value.items)
      setCursor(lista.value.siguiente_cursor)
      if (bloque.status === 'fulfilled') {
        setPorAcabarse(bloque.value)
        setErrorBloque(false)
      } else if (!esVencida(bloque.reason)) {
        setPorAcabarse(null)
        setErrorBloque(true)
      }
      setCarga('listo')
    },
    [personaId],
  )

  /** Solo el bloque, después de cambiar un insumo: la fecha estimada y el aviso pudieron cambiar. */
  const refrescarBloque = useCallback(async () => {
    if (!personaId) return
    try {
      setPorAcabarse(await listarPorAcabarse(personaId))
      setErrorBloque(false)
    } catch (x) {
      if (esVencida(x)) return
      setPorAcabarse(null)
      setErrorBloque(true)
    }
  }, [personaId])

  useEffect(() => {
    void cargar()
  }, [cargar])

  // 2.6: el foco de la llegada queda en el h1 de «Cargando», que se reemplaza por el de lo que llega
  // (la lista, el permiso, el 404…). Si al reemplazarlo el foco cayó al body, lo recibe el h1 nuevo
  // (MATU-60, revisión del 06-11: el cuidador que llega desde la lista sin el permiso).
  const cargaAntes = useRef<Carga>(carga)
  useEffect(() => {
    const venia = cargaAntes.current
    cargaAntes.current = carga
    if (venia !== 'cargando' || carga === 'cargando') return
    const activo = document.activeElement
    if (activo === null || activo === document.body) document.getElementById('titulo-pagina')?.focus()
  }, [carga])

  const modo: 'nuevo' | 'cambiar' | null = ruta === '/insumos/nuevo' ? 'nuevo' : ruta === '/insumos/cambiar' ? 'cambiar' : null
  const editado = modo === 'cambiar' ? (items.find((p) => p.id === editandoId && p.activo) ?? null) : null
  const formulario = carga === 'listo' && editor && (modo === 'nuevo' || (modo === 'cambiar' && editado !== null))

  // 2.4: pagador u observador en una ruta de formulario, o «cambiar» sin un insumo en memoria (recargó).
  useEffect(() => {
    if (carga !== 'listo' || !modo) return
    if (!editor || (modo === 'cambiar' && !editado)) navegar('/insumos', { reemplazar: true })
  }, [carga, modo, editor, editado])

  const volverALista = (texto: string | null) => {
    setAviso(texto)
    setAvisoAlerta(null)
    setEditandoId(null)
    navegar('/insumos')
    if (texto) enfocar('aviso-insumos', 60)
  }

  const reemplazar = (p: Perfil) => setItems((xs) => xs.map((x) => (x.id === p.id ? p : x)))

  const verMas = async () => {
    if (!personaId || !cursor || cargandoMas) return
    setCargandoMas(true)
    setErrorMas(false)
    try {
      const r = await listarConsumo(personaId, cursor)
      const nuevos = r.items.filter((p) => !items.some((x) => x.id === p.id))
      setItems((xs) => [...xs, ...nuevos])
      setCursor(r.siguiente_cursor)
      if (nuevos[0]) enfocar(`insumo-${nuevos[0].id}`)
    } catch (x) {
      if (esVencida(x)) return
      const permiso = permisoDe(x)
      if (permiso) return setCarga(permiso)
      setErrorMas(true)
    } finally {
      setCargandoMas(false)
    }
  }

  const alSeguir = async (p: Perfil, seguir: boolean) => {
    if (!personaId || ocupadoId) return
    setOcupadoId(p.id)
    setErrorFila(null)
    try {
      const nuevo = await seguirPerfil(personaId, p.id, seguir)
      reemplazar(nuevo)
      void refrescarBloque()
      setAviso(seguir ? INSUMOS.volvisteASeguir(nombreDe(nuevo)) : INSUMOS.dejasteDeSeguir(nombreDe(nuevo)))
      enfocar(`seguir-${p.id}`)
    } catch (x) {
      if (esVencida(x)) return
      const permiso = permisoDe(x)
      if (permiso) return setCarga(permiso)
      const f = leerFallo(x)
      if (f.status === 404) return void cargar()
      setErrorFila({ id: p.id, texto: esTipo(f.tipo, 'perfil-duplicado') ? INSUMOS.errDuplicado : INSUMOS.errRedSinEscrito })
      enfocar(`seguir-${p.id}`)
    } finally {
      setOcupadoId(null)
    }
  }

  const alEliminado = (p: Perfil, yaNoEstaba: boolean) => {
    setEliminando(null)
    if (yaNoEstaba) {
      void cargar()
    } else {
      setItems((xs) => xs.filter((x) => x.id !== p.id))
      void refrescarBloque()
      setAviso(INSUMOS.eliminaste(nombreDe(p)))
    }
    enfocar('titulo-pagina')
  }

  const contenido = () => {
    if (carga === 'cargando') return <Cargando />
    if (carga === 'sin-consentimiento')
      return editor ? (
        <Permiso
          pila={pila}
          personaId={personaId}
          onListo={(vigente) => {
            if (vigente) return void cargar()
            setItems([])
            setCursor(null)
            setCarga('listo')
            setAviso(INSUMOS.permisoGuardado)
            navegar('/insumos/nuevo')
          }}
          onNoEncontrado={() => setCarga('no-encontrado')}
        />
      ) : (
        <UnaColumna titulo={INSUMOS.titulo} baldosa={<Lock aria-hidden className="size-9" />} tono="neutro">
          <p className="max-w-prose text-lg">
            <strong>{INSUMOS.faltaPermisoTitulo(pila)}</strong> {INSUMOS.faltaPermiso(pila)}
          </p>
        </UnaColumna>
      )
    if (carga === 'revision-vencida')
      return (
        <UnaColumna titulo={INSUMOS.titulo} baldosa={<Hourglass aria-hidden className="size-9" />} tono="atenta">
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
        <UnaColumna titulo={INSUMOS.titulo} baldosa={<CircleAlert aria-hidden className="size-9" />} tono="neutro">
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
        <UnaColumna titulo={INSUMOS.titulo} baldosa={<CircleAlert aria-hidden className="size-9" />} tono="neutro">
          <Anunciado urgencia="alert" como="p" className="max-w-prose text-lg">
            <strong>{INSUMOS.errRedSinEscrito.split('. ')[0]}.</strong> {INSUMOS.errRedSinEscrito.split('. ').slice(1).join('. ')}
          </Anunciado>
          <Boton onClick={() => void cargar()}>{GENERAL.volverAIntentar}</Boton>
        </UnaColumna>
      )

    const form = formulario ? (
      <Formulario
        key={modo === 'cambiar' ? editado!.id : 'nuevo'}
        modo={modo!}
        perfil={editado}
        pila={pila}
        personaId={personaId!}
        ancho={ancho}
        onCancelar={() => volverALista(null)}
        onGuardado={(p, texto, nuevo) => {
          if (nuevo) setItems((xs) => [p, ...xs.filter((x) => x.id !== p.id)])
          else reemplazar(p)
          void refrescarBloque()
          volverALista(texto)
        }}
        onDejarSuyo={(actual) => {
          reemplazar(actual)
          void refrescarBloque()
          volverALista(INSUMOS.dejasteLoSuyo(actual.actualizado_por?.nombre?.trim() || null))
        }}
        onInactivo={(actual) => actual && reemplazar(actual)}
        onPermiso={(c) => setCarga(c)}
        onNoEncontrado={() => {
          setEditandoId(null)
          navegar('/insumos', { reemplazar: true })
          void cargar()
        }}
      />
    ) : null

    // 360 px: el formulario reemplaza a la lista.
    if (form && !ancho)
      return (
        <div className="flex flex-col gap-5">
          {aviso && <AvisoOk texto={aviso} />}
          {form}
        </div>
      )

    const avisos = (porAcabarse ?? []).filter((a) => a.avisando)
    const avisando = new Set(avisos.map((a) => a.id))
    const bloque =
      items.length > 0 && personaId ? (
        <SeAcabanPronto
          avisos={avisos}
          error={errorBloque}
          editor={editor}
          personaId={personaId}
          confirmacion={avisoAlerta}
          onReintentar={() => void refrescarBloque()}
          onResuelto={async (texto) => {
            setAviso(null)
            await cargar(true)
            setAvisoAlerta(texto)
            enfocar('aviso-alertas', 60)
          }}
          onVerComoQuedo={() => void cargar(true).then(() => enfocar(document.getElementById('titulo-se-acaban') ? 'titulo-se-acaban' : 'titulo-pagina', 80))}
          onPermiso={(c) => setCarga(c)}
        />
      ) : null
    const activos = items.filter((p) => p.activo).sort(porFecha)
    const inactivos = items.filter((p) => !p.activo)
    const fila = (p: Perfil) => (
      <Fila
        key={p.id}
        perfil={p}
        avisando={avisando.has(p.id)}
        editor={editor}
        elegida={!!form && modo === 'cambiar' && p.id === editandoId}
        ocupado={ocupadoId === p.id}
        error={errorFila?.id === p.id ? errorFila.texto : null}
        onCambiar={() => {
          setAviso(null)
          setAvisoAlerta(null)
          setEditandoId(p.id)
          navegar('/insumos/cambiar')
        }}
        onSeguir={(v) => void alSeguir(p, v)}
        onEliminar={() => setEliminando(p)}
      />
    )
    const botonAnotar = editor && items.length > 0 && (
      <Boton
        variante={form ? 'secundario' : 'principal'}
        icono={<Plus aria-hidden className="size-5" />}
        className="self-start"
        onClick={() => {
          setAviso(null)
          setAvisoAlerta(null)
          navegar('/insumos/nuevo')
        }}
      >
        {INSUMOS.anotar}
      </Boton>
    )

    const nota = items.length > 0 && <p className="max-w-prose text-base text-tenue">{editor ? INSUMOS.notaCorta : INSUMOS.notaCortaLector}</p>

    return (
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-3">
          <PestanasInsumos activa="/insumos" />
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
            <Titulo className="text-3xl @2xl/main:text-5xl">{INSUMOS.titulo}</Titulo>
            {ancho && botonAnotar}
          </div>
        </div>
        {/* MATU-37: a 360 px, lo primero bajo el título es «Se acaban pronto». */}
        {!ancho && bloque}
        {!ancho && nota}
        {!ancho && botonAnotar}
        {!ancho && aviso && <AvisoOk texto={aviso} />}

        <div className={ancho ? 'grid grid-cols-[3fr_2fr] items-start gap-10' : 'flex flex-col gap-5'}>
          <div className="flex min-w-0 flex-col gap-5">
            {/* En pantalla ancha, el bloque y la nota van en la columna de la lista (3.4). */}
            {ancho && bloque}
            {ancho && nota}
            {ancho && aviso && <AvisoOk texto={aviso} />}
            {items.length === 0 ? (
              <Vacio pila={pila} editor={editor} />
            ) : (
              <>
                {activos.length > 0 && <ul className="flex flex-col gap-2">{activos.map(fila)}</ul>}
                {inactivos.length > 0 && (
                  <section aria-labelledby="sin-seguir-t" className="mt-8 flex flex-col gap-2">
                    <h2 id="sin-seguir-t" className="text-xl font-bold">
                      {INSUMOS.sinSeguir}
                    </h2>
                    <ul className="flex flex-col gap-2">{inactivos.map(fila)}</ul>
                  </section>
                )}
                {cursor && (
                  <div className="flex flex-col items-start gap-2">
                    <Boton variante="secundario" ocupado={cargandoMas} textoOcupado={INSUMOS.cargandoMas} onClick={() => void verMas()}>
                      {INSUMOS.verMas}
                    </Boton>
                    {errorMas && (
                      <Anunciado urgencia="alert">
                        <MensajeError>{INSUMOS.errRedSinEscrito}</MensajeError>
                      </Anunciado>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
          {ancho &&
            (form ?? (
              items.length > 0 && (
                <Nota titulo={INSUMOS.comoTitulo}>
                  <p>{editor ? INSUMOS.como(pila) : INSUMOS.comoLector(pila)}</p>
                </Nota>
              )
            ))}
        </div>
      </div>
    )
  }

  return (
    <div ref={ref} className="min-w-0">
      {contenido()}
      {eliminando && personaId && (
        <DialogoEliminar perfil={eliminando} personaId={personaId} onCancelar={() => setEliminando(null)} onEliminado={alEliminado} onPermiso={(c) => (setEliminando(null), setCarga(c))} />
      )}
    </div>
  )
}

// ---------------------------------------------------------------- piezas comunes

function Cargando() {
  const ver = useDemora()
  return (
    <div aria-busy="true" className="flex flex-col gap-4">
      <Titulo className="text-3xl @2xl/main:text-5xl">{INSUMOS.titulo}</Titulo>
      <p role="status" className="text-lg text-tenue">
        {ver ? INSUMOS.cargando : ''}
      </p>
    </div>
  )
}

function UnaColumna({ titulo, baldosa, tono, children }: { titulo: string; baldosa: ReactNode; tono: 'neutro' | 'atenta' | 'rocio'; children: ReactNode }) {
  const fondo = { neutro: 'bg-tinta/7 text-tenue', atenta: 'bg-atenta-fondo text-atenta', rocio: 'bg-rocio text-turquesa' }[tono]
  return (
    <div className="flex flex-col items-start gap-5">
      <Titulo className="text-3xl @2xl/main:text-5xl">{titulo}</Titulo>
      <span className={`grid size-16 place-items-center rounded-2xl ${fondo}`}>{baldosa}</span>
      {children}
    </div>
  )
}

function AvisoOk({ texto }: { texto: string }) {
  return (
    <div id="aviso-insumos" tabIndex={-1} role="status" className="animate-aparecer flex max-w-prose gap-3 rounded-xl bg-ok-fondo px-4 py-3 outline-none">
      <Check aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" strokeWidth={3} />
      <p className="min-w-0 break-words">{texto}</p>
    </div>
  )
}

function Vacio({ pila, editor }: { pila: string; editor: boolean }) {
  return (
    <div className="flex flex-col items-start gap-4">
      <span className={`grid size-16 place-items-center rounded-2xl ${editor ? 'bg-rocio text-turquesa' : 'bg-tinta/7 text-tenue'}`}>
        <ListChecks aria-hidden className="size-9" />
      </span>
      <h2 className="titular text-3xl angosto:text-2xl">{editor ? INSUMOS.vacioTitulo(pila) : INSUMOS.vacioLectorTitulo}</h2>
      <p className="max-w-prose text-base text-tenue">{editor ? INSUMOS.vacio : INSUMOS.vacioLector}</p>
      {editor && (
        <Boton icono={<Plus aria-hidden className="size-5" />} onClick={() => navegar('/insumos/nuevo')}>
          {INSUMOS.anotar}
        </Boton>
      )}
    </div>
  )
}

/** «Usa 4 al día. Quedaban 24 el 31/10/2026.» */
function LoAnotado({ p }: { p: Perfil }) {
  const hoy = p.stock_medido_en === hoyEnChile()
  return (
    <p className="text-base text-tenue">
      {INSUMOS.usa(p.tasa_unidades, p.tasa_dias, p.unidad)}{' '}
      {hoy ? (
        INSUMOS.quedanHoy(p.stock_unidades, p.unidad)
      ) : (
        <>
          {INSUMOS.quedaban(p.stock_unidades, p.unidad)} <span className="cifras whitespace-nowrap">{fechaCorta(p.stock_medido_en)}</span>.
        </>
      )}
    </p>
  )
}

/** «Alcanza para 6 días» y «hasta el 06/11/2026» (3.2.1). */
function LineaDias({ p }: { p: Perfil }) {
  const l = lineaDias(p.dias_restantes)
  const fecha = <span className="cifras whitespace-nowrap">{fechaCorta(p.fecha_quiebre_estimada)}</span>
  return (
    <div className="flex flex-col">
      <p className="flex items-start gap-2 text-xl font-bold">
        {l.cifra === null && <CircleAlert aria-hidden className="mt-1 size-5 shrink-0 text-pronto" />}
        <span className="min-w-0">
          {l.texto}
          {l.cifra !== null && (
            <>
              {' '}
              <span className="cifras">{l.cifra}</span> {l.resto}
            </>
          )}
        </span>
      </p>
      {p.dias_restantes > 0 && (
        <p className="text-base">
          {INSUMOS.hastaEl} {fecha}
        </p>
      )}
      {p.dias_restantes < 0 && (
        <p className="text-base">
          {INSUMOS.seAcababa} {fecha}.
        </p>
      )}
    </div>
  )
}

function Fila({
  perfil: p,
  avisando,
  editor,
  elegida,
  ocupado,
  error,
  onCambiar,
  onSeguir,
  onEliminar,
}: {
  perfil: Perfil
  avisando: boolean
  editor: boolean
  elegida: boolean
  ocupado: boolean
  error: string | null
  onCambiar: () => void
  onSeguir: (v: boolean) => void
  onEliminar: () => void
}) {
  const nombre = nombreDe(p)
  const idNombre = `nombre-${p.id}`
  const forma = p.activo
    ? `bg-hoja ring-inset ${elegida ? 'ring-2 ring-turquesa' : 'ring-1 ring-linea'}`
    : 'bg-papel border-2 border-dashed border-borde'
  return (
    <li id={`insumo-${p.id}`} tabIndex={-1} aria-current={elegida || undefined} className={`flex flex-col gap-2 rounded-xl px-4 angosto:px-2 py-3 outline-none ${forma}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-1">
        <p className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <span id={idNombre} className="min-w-0 font-bold break-words [overflow-wrap:anywhere]">
            {nombre}
          </span>
          {p.activo && avisando && (
            <span className="inline-flex max-w-full basis-full items-center gap-1.5 text-base text-tinta">
              <Bell aria-hidden className="size-5 shrink-0 text-atenta" />
              {ALERTAS.marca}
            </span>
          )}
          {!p.activo && (
            <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-tinta/7 px-2.5 py-0.5 text-base font-bold text-tenue">
              <PauseCircle aria-hidden className="size-4 shrink-0" />
              {INSUMOS.sinSeguir}
            </span>
          )}
        </p>
        {p.activo ? <LineaDias p={p} /> : <p className="text-base text-tenue">{INSUMOS.sinSeguirLinea}</p>}
      </div>
      {p.activo && <LoAnotado p={p} />}
      {editor && (
        <div className="flex flex-wrap items-center gap-4">
          <label className={`inline-flex min-h-12 cursor-pointer items-center gap-3 font-bold ${ocupado ? 'cursor-wait' : ''}`}>
            <input
              id={`seguir-${p.id}`}
              type="checkbox"
              checked={p.activo}
              aria-busy={ocupado || undefined}
              aria-describedby={idNombre}
              onChange={(e) => {
                if (ocupado) return
                onSeguir(e.target.checked)
              }}
              className="size-5 shrink-0 accent-turquesa"
            />
            {ocupado ? INSUMOS.guardando : INSUMOS.seguir}
          </label>
          {p.activo && (
            <Boton variante="secundario" aria-label={INSUMOS.cambiarDe(nombre)} onClick={onCambiar}>
              {INSUMOS.cambiar}
            </Boton>
          )}
          <button
            type="button"
            aria-label={INSUMOS.eliminarDe(nombre)}
            onClick={onEliminar}
            className="ms-auto grid size-12 shrink-0 place-items-center rounded-xl bg-hoja text-pronto ring-2 ring-inset ring-pronto/60 hover:bg-pronto-fondo active:bg-pronto-fondo"
          >
            <Trash2 aria-hidden className="size-5" />
          </button>
        </div>
      )}
      {error && (
        <Anunciado urgencia="alert">
          <MensajeError>{error}</MensajeError>
        </Anunciado>
      )}
    </li>
  )
}

// ---------------------------------------------------------------- 3.1 el permiso

function Permiso({
  pila,
  personaId,
  onListo,
  onNoEncontrado,
}: {
  pila: string
  personaId: string | null
  onListo: (yaVigente: boolean) => void
  onNoEncontrado: () => void
}) {
  const [calidad, setCalidad] = useState<Calidad | null>('cuidador_de_hecho')
  const [leido, setLeido] = useState(false)
  const [referencia, setReferencia] = useState('')
  const [error, setError] = useState<'calidad' | 'referencia' | 'leido' | null>(null)
  const [falla, setFalla] = useState<'422' | 'red' | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const aceptar = async () => {
    if (ocupado || !personaId) return
    setFalla(null)
    if (!calidad) return setError('calidad')
    if (calidad === 'representante_legal' && !referencia.trim()) return setError('referencia')
    if (calidad === 'cuidador_de_hecho' && !leido) return setError('leido')
    setError(null)
    setOcupado(true)
    try {
      await autorizarConsumo(personaId, {
        finalidad: 'consumo',
        calidad_otorgante: calidad,
        referencia_documento: calidad === 'representante_legal' ? referencia.trim() : null,
        aviso: calidad === 'cuidador_de_hecho' ? { id: AVISO_CUIDADOR.id, version: AVISO_CUIDADOR.version } : null,
      })
      onListo(false)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 409 && esTipo(f.tipo, 'autorizacion-vigente')) return onListo(true)
      if (f.status === 404) return onNoEncontrado()
      setFalla(f.status === 422 ? '422' : 'red')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <p className="text-base text-tenue">{INSUMOS.titulo}</p>
        <Titulo className="text-3xl @2xl/main:text-5xl">{INSUMOS.permisoTitulo}</Titulo>
        <p className="max-w-prose text-lg">{INSUMOS.permisoBajada(pila)}</p>
      </div>
      <GrupoOpciones
        leyenda={INSUMOS.permisoLeyenda}
        nombre="calidad-consumo"
        valor={calidad}
        columnas
        error={error === 'calidad' ? INSUMOS.errCalidad : null}
        onCambio={(v) => {
          setCalidad(v)
          setError(null)
        }}
        opciones={CALIDADES.map((c) => ({ valor: c.valor, texto: c.texto(pila), detalle: c.detalle(pila) }))}
      />
      {calidad === 'representante_legal' && (
        <CampoTexto
          etiqueta={AUTORIZACION.referencia}
          value={referencia}
          onChange={(e) => setReferencia(e.target.value)}
          ayuda={AUTORIZACION.referenciaAyuda}
          autoComplete="off"
          maxLength={200}
          className="max-w-xl"
          error={error === 'referencia' ? AUTORIZACION.errReferencia : null}
        />
      )}
      {calidad === 'cuidador_de_hecho' && (
        <section aria-labelledby="aviso-consumo-t" className="border-l-4 border-atenta bg-atenta-fondo">
          <h2 id="aviso-consumo-t" className="flex items-start gap-2 px-5 angosto:px-2 pt-4 text-lg font-bold">
            <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />
            {AVISO_CUIDADOR.titulo}
          </h2>
          <div className="flex max-w-prose flex-col gap-2.5 px-5 angosto:px-2 pt-2 pb-4 leading-relaxed">
            {AVISO_CUIDADOR.parrafos.map((p) => (
              <p key={p.slice(0, 24)}>{p}</p>
            ))}
          </div>
          <label className="flex min-h-12 cursor-pointer items-center gap-3 border-t border-linea bg-hoja/60 px-5 angosto:px-2 py-3 font-bold">
            <input
              type="checkbox"
              checked={leido}
              aria-invalid={error === 'leido' ? true : undefined}
              aria-describedby={error === 'leido' ? 'leido-consumo-e' : undefined}
              onChange={(e) => {
                setLeido(e.target.checked)
                setError(null)
              }}
              className="size-5 shrink-0 accent-turquesa"
            />
            {AUTORIZACION.leido}
          </label>
          {error === 'leido' && (
            <div className="px-5 angosto:px-2 pb-3">
              <MensajeError id="leido-consumo-e">{AUTORIZACION.errLeido}</MensajeError>
            </div>
          )}
        </section>
      )}
      {calidad && (
        <Nota tono="rocio" titulo={AUTORIZACION.declaras}>
          <p className="max-w-prose">{DECLARACION_CONSUMO[calidad]}</p>
        </Nota>
      )}
      {falla && (
        <Anunciado urgencia="alert">
          <MensajeError>{falla === '422' ? INSUMOS.errPermiso : INSUMOS.errRedSinEscrito}</MensajeError>
        </Anunciado>
      )}
      <Acciones>
        <Boton onClick={() => void aceptar()} ocupado={ocupado} textoOcupado={INSUMOS.permisoEnviando}>
          {INSUMOS.permisoBoton}
        </Boton>
      </Acciones>
    </div>
  )
}

// ---------------------------------------------------------------- 3.4 anotar o cambiar

type CampoForm = 'nombre' | 'uso' | 'cada' | 'stock' | 'aviso' | 'envase'
// MATU-60 9.1: el envase va al final, al anotar y al cambiar.
const ORDEN_NUEVO: CampoForm[] = ['nombre', 'uso', 'cada', 'stock', 'aviso', 'envase']
const ORDEN_CAMBIAR: CampoForm[] = ['stock', 'uso', 'cada', 'aviso', 'nombre', 'envase']
const ENVASE_MAX = 10_000

/** La vista previa, solo con datos completos (3.4.1). */
function VistaPrevia({ stock, uso, cada }: { stock: number | null; uso: number | null; cada: number }) {
  const valido = stock !== null && uso !== null && uso >= 1 && uso <= 10_000 && stock <= 100_000 && cada >= 1 && cada <= 90
  const dias = valido ? Math.floor((stock * cada) / uso) : null
  const texto = dias === null ? '' : dias <= 0 ? INSUMOS.previa(0) : `${INSUMOS.previa(dias)} ${fechaCorta(sumarDias(hoyEnChile(), dias))}.`
  // El anuncio espera 500 ms: no se dice en cada tecla (6).
  const [anuncio, setAnuncio] = useState('')
  useEffect(() => {
    const t = window.setTimeout(() => setAnuncio(texto), 500)
    return () => window.clearTimeout(t)
  }, [texto])
  return (
    <>
      <div aria-live="polite" className="sr-only">
        {anuncio}
      </div>
      {dias !== null && (
        <div className="flex max-w-prose gap-3 border-l-4 border-turquesa bg-rocio px-4 angosto:px-2 py-3">
          <CalendarCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa angosto:hidden" />
          <p className="min-w-0 font-bold">
            {dias <= 0 ? (
              INSUMOS.previa(0)
            ) : (
              <>
                {INSUMOS.previa(dias)} <span className="cifras whitespace-nowrap">{fechaCorta(sumarDias(hoyEnChile(), dias))}</span>.
              </>
            )}
          </p>
        </div>
      )}
    </>
  )
}

function Formulario({
  modo,
  perfil,
  pila,
  personaId,
  ancho,
  onCancelar,
  onGuardado,
  onDejarSuyo,
  onInactivo,
  onPermiso,
  onNoEncontrado,
}: {
  modo: 'nuevo' | 'cambiar'
  perfil: Perfil | null
  pila: string
  personaId: string
  ancho: boolean
  onCancelar: () => void
  onGuardado: (p: Perfil, aviso: string, nuevo: boolean) => void
  onDejarSuyo: (actual: Perfil) => void
  onInactivo: (actual: Perfil | null) => void
  onPermiso: (c: 'sin-consentimiento' | 'revision-vencida') => void
  onNoEncontrado: () => void
}) {
  const uid = useId()
  const nuevo = modo === 'nuevo'
  const [nombre, setNombre] = useState(perfil ? nombreDe(perfil) : '')
  const [unidad, setUnidad] = useState<Unidad>(perfil?.unidad ?? 'unidad')
  const [frecuencia, setFrecuencia] = useState<'diario' | 'cada'>(perfil && perfil.tasa_dias > 1 ? 'cada' : 'diario')
  const [cada, setCada] = useState(String(perfil && perfil.tasa_dias > 1 ? perfil.tasa_dias : 2))
  const [uso, setUso] = useState(perfil ? String(perfil.tasa_unidades) : '1')
  // Al cambiar, el stock va vacío a propósito: lo anotado no es lo de hoy (3.4).
  const [stock, setStock] = useState('')
  const [aviso, setAviso] = useState(String(perfil?.dias_aviso ?? 7))
  // MATU-60 9.2: al cambiar, con el valor guardado (el envase no envejece). Al anotar, vacío.
  const [envase, setEnvase] = useState(perfil?.unidades_por_envase != null ? String(perfil.unidades_por_envase) : '')
  const [errores, setErrores] = useState<Partial<Record<CampoForm, string>>>({})
  const [general, setGeneral] = useState<{ titulo?: string; texto: string } | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [conflicto, setConflicto] = useState<Perfil | null>(null)
  const [inactivo, setInactivo] = useState(false)
  const ids: Record<CampoForm, string> = { nombre: `${uid}-nombre`, uso: `${uid}-uso`, cada: `${uid}-cada`, stock: `${uid}-stock`, aviso: `${uid}-aviso`, envase: `${uid}-envase` }

  const tasaDias = frecuencia === 'diario' ? 1 : (entero(cada) ?? 0)
  const nombreLimpio = unaLinea(nombre).trim()
  const titulo = nuevo ? INSUMOS.anotar : nombreDe(perfil!)

  // En ancho, el título del formulario es un h2 que recibe el foco (2.2).
  useEffect(() => {
    if (ancho) enfocar(`${uid}-titulo`, 60)
  }, [ancho, uid, modo, perfil?.id])

  const validar = (): Partial<Record<CampoForm, string>> => {
    const e: Partial<Record<CampoForm, string>> = {}
    if ((nuevo || perfil?.nombre_libre !== null) && !nombreLimpio) e.nombre = INSUMOS.errNombre
    const u = entero(uso)
    if (u === null || u < 1) e.uso = INSUMOS.errUso
    else if (u > 10_000) e.uso = INSUMOS.errUsoMax
    if (frecuencia === 'cada') {
      const c = entero(cada)
      if (c === null || c < 2 || c > 90) e.cada = INSUMOS.errCada
    }
    const s = entero(stock)
    if (s === null && nuevo) e.stock = INSUMOS.errStock
    else if (s !== null && s > 100_000) e.stock = INSUMOS.errStockMax
    const a = entero(aviso)
    if (a === null || a < 0 || a > 60) e.aviso = INSUMOS.errAviso
    // Opcional: vacío no es error (9.3).
    const ev = entero(envase)
    if (ev !== null && (ev < 1 || ev > ENVASE_MAX)) e.envase = LISTA.errEnvase
    return e
  }

  /** Solo los campos que cambiaron (decisión 41). */
  const cambios = (): SolicitudEdicion => {
    if (!perfil) return {}
    const c: SolicitudEdicion = {}
    if (perfil.nombre_libre !== null && nombreLimpio !== perfil.nombre_libre) c.nombre_libre = nombreLimpio
    if (entero(uso) !== perfil.tasa_unidades) c.tasa_unidades = entero(uso)!
    if (tasaDias !== perfil.tasa_dias) c.tasa_dias = tasaDias
    if (entero(stock) !== null) c.stock_unidades = entero(stock)!
    if (entero(aviso) !== perfil.dias_aviso) c.dias_aviso = entero(aviso)!
    // Decisión 121: vacío se envía como `null`, que borra el dato. Solo si cambió.
    const ev = entero(envase)
    if (ev !== (perfil.unidades_por_envase ?? null)) c.unidades_por_envase = ev
    return c
  }

  const alFallar = (x: unknown) => {
    if (esVencida(x)) return
    const actual = leerConflictoPerfil(x)
    if (actual) {
      if (!actual.activo) {
        onInactivo(actual)
        return setInactivo(true)
      }
      setConflicto(actual)
      return enfocar(`${uid}-conflicto`)
    }
    const f = leerFallo(x)
    const permiso = permisoDe(x)
    if (permiso) return onPermiso(permiso)
    if (f.status === 404) return onNoEncontrado()
    if (f.status === 409 && esTipo(f.tipo, 'perfil-inactivo')) {
      onInactivo(null)
      return setInactivo(true)
    }
    if (f.status === 409) return setGeneral({ texto: INSUMOS.errDuplicado })
    if (f.status === 428) return setGeneral({ titulo: INSUMOS.faltaVersionTitulo, texto: INSUMOS.faltaVersion })
    if (f.status === 422) {
      const e: Partial<Record<CampoForm, string>> = {}
      let gen: string | null = null
      for (const { campo, tipo } of f.errores) {
        const c = campo.split('.').pop() ?? campo
        if (tipo === 'cobertura_maxima') gen = INSUMOS.errCobertura
        else if (tipo === 'producto_no_admitido') gen = INSUMOS.errNoAdmitido
        else if (c === 'nombre_libre' || tipo === 'producto_o_nombre')
          e.nombre = tipo === 'string_too_long' ? INSUMOS.errNombreLargo : tipo === 'value_error' ? INSUMOS.errNombreLinea : INSUMOS.errNombre
        else if (c === 'tasa_unidades') e.uso = tipo.startsWith('less') ? INSUMOS.errUsoMax : INSUMOS.errUso
        else if (c === 'tasa_dias') e.cada = INSUMOS.errCada
        else if (c === 'stock_unidades') e.stock = tipo.startsWith('less') ? INSUMOS.errStockMax : INSUMOS.errStock
        else if (c === 'dias_aviso') e.aviso = INSUMOS.errAviso
        else if (c === 'unidades_por_envase') e.envase = LISTA.errEnvase
        else gen = INSUMOS.errOtro422
      }
      setErrores(e)
      if (gen || !Object.keys(e).length) setGeneral({ texto: gen ?? INSUMOS.errOtro422 })
      const primero = (nuevo ? ORDEN_NUEVO : ORDEN_CAMBIAR).find((k) => e[k])
      if (primero) enfocar(ids[primero], 0)
      return
    }
    setGeneral({ texto: GENERAL.error })
  }

  const guardar = async (etag?: string) => {
    if (ocupado) return
    setGeneral(null)
    const e = validar()
    setErrores(e)
    const primero = (nuevo ? ORDEN_NUEVO : ORDEN_CAMBIAR).find((k) => e[k])
    if (primero) return void document.getElementById(ids[primero])?.focus()
    if (!nuevo && !Object.keys(cambios()).length) return onGuardadoSinCambios()
    setOcupado(true)
    try {
      if (nuevo) {
        const p = await crearPerfil(personaId, {
          nombre_libre: nombreLimpio,
          unidad,
          tasa_unidades: entero(uso)!,
          tasa_dias: tasaDias,
          stock_unidades: entero(stock)!,
          dias_aviso: entero(aviso)!,
          // Al anotar, vacío no se envía (9.2).
          ...(entero(envase) !== null ? { unidades_por_envase: entero(envase)! } : {}),
        })
        onGuardado(p, `${INSUMOS.guardado(nombreDe(p))} ${diasEnTexto(p.dias_restantes)}`, true)
      } else {
        const p = await editarPerfil(personaId, perfil!.id, cambios(), etag ?? perfil!.etag)
        onGuardado(p, `${INSUMOS.guardado(nombreDe(p))} ${diasEnTexto(p.dias_restantes)}`, false)
      }
    } catch (x) {
      alFallar(x)
    } finally {
      setOcupado(false)
    }
  }

  const onGuardadoSinCambios = () => onGuardado(perfil!, INSUMOS.sinCambios, false)

  const encabezado = ancho ? (
    <div>
      <h2 id={`${uid}-titulo`} tabIndex={-1} className="text-xl font-bold break-words [overflow-wrap:anywhere] outline-none">
        {titulo}
      </h2>
      {!nuevo && <p className="text-base text-tenue">{INSUMOS.cambiarBajada}</p>}
    </div>
  ) : (
    <div className="flex flex-col gap-3">
      <Volver onClick={onCancelar}>{INSUMOS.volver}</Volver>
      <div>
        <Titulo className="text-3xl @2xl/main:text-5xl break-words [overflow-wrap:anywhere]">{titulo}</Titulo>
        {!nuevo && <p className="mt-1.5 text-base text-tenue">{INSUMOS.cambiarBajada}</p>}
      </div>
    </div>
  )

  const marco = (hijos: ReactNode) =>
    ancho ? <div className="flex flex-col gap-6 rounded-xl bg-hoja px-7 py-5 ring-1 ring-linea">{hijos}</div> : <div className="flex flex-col gap-6">{hijos}</div>

  if (inactivo)
    return marco(
      <>
        {encabezado}
        <div className="flex flex-col items-start gap-4">
          <span className="grid size-16 place-items-center rounded-2xl bg-tinta/7 text-tenue">
            <PauseCircle aria-hidden className="size-9" />
          </span>
          <Anunciado urgencia="alert" como="p" className="max-w-prose text-lg">
            <strong>{INSUMOS.inactivoTitulo}</strong> {INSUMOS.inactivo}
          </Anunciado>
          <Boton variante="secundario" onClick={onCancelar}>
            {INSUMOS.volver}
          </Boton>
        </div>
      </>,
    )

  const campoNombre = (
    <CampoNombre
      id={ids.nombre}
      valor={nombre}
      onCambio={setNombre}
      error={errores.nombre}
      soloLectura={!nuevo && perfil?.nombre_libre === null}
    />
  )
  const campoUnidad = nuevo ? (
    <GrupoOpciones leyenda={INSUMOS.unidadLeyenda} nombre={`${uid}-unidad`} valor={unidad} onCambio={setUnidad} opciones={INSUMOS.unidades} />
  ) : (
    <p className="text-base text-tenue">{INSUMOS.unidadFija(unidad)}</p>
  )
  const cadaNum = frecuencia === 'cada' ? entero(cada) : null
  const campoUso = (
    <div className="flex flex-col gap-4">
      <GrupoOpciones leyenda={INSUMOS.frecuenciaLeyenda} nombre={`${uid}-frecuencia`} valor={frecuencia} onCambio={setFrecuencia} opciones={INSUMOS.frecuencias} />
      {frecuencia === 'cada' && (
        <Stepper id={ids.cada} etiqueta={INSUMOS.cadaCuantos} sufijo={INSUMOS.sufijoDias} valor={cada} onCambio={setCada} min={2} max={90} error={errores.cada} />
      )}
      <Stepper
        id={ids.uso}
        etiqueta={INSUMOS.uso(pila, cadaNum && cadaNum >= 2 ? cadaNum : null)}
        sufijo={INSUMOS.sufijoUso(unidad, cadaNum && cadaNum >= 2 ? cadaNum : null)}
        valor={uso}
        onCambio={setUso}
        min={1}
        max={10_000}
        error={errores.uso}
      />
    </div>
  )
  const campoStock = (
    <Stepper
      id={ids.stock}
      etiqueta={INSUMOS.stock}
      ayuda={perfil ? INSUMOS.stockAyuda(fechaCorta(perfil.stock_medido_en), cantidad(perfil.stock_unidades, perfil.unidad)) : undefined}
      sufijo={INSUMOS.sufijoStock(unidad)}
      valor={stock}
      onCambio={setStock}
      min={0}
      max={100_000}
      error={errores.stock}
    />
  )
  const campoAviso = (
    <Stepper id={ids.aviso} etiqueta={INSUMOS.aviso} ayuda={INSUMOS.avisoAyuda} sufijo={INSUMOS.sufijoAviso} valor={aviso} onCambio={setAviso} min={0} max={60} error={errores.aviso} />
  )
  const campoEnvase = <CampoEnvase id={ids.envase} valor={envase} onCambio={setEnvase} sufijo={INSUMOS.sufijoStock(unidad)} error={errores.envase} />

  return marco(
    <>
      {encabezado}
      <form
        noValidate
        className="flex flex-col gap-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (!conflicto) void guardar()
        }}
      >
        {nuevo ? (
          <>
            {campoNombre}
            {campoUnidad}
            {campoUso}
            {campoStock}
            {campoAviso}
            {campoEnvase}
          </>
        ) : (
          <>
            {campoStock}
            {campoUso}
            {campoAviso}
            {campoNombre}
            {campoUnidad}
            {campoEnvase}
          </>
        )}
        <VistaPrevia stock={entero(stock)} uso={entero(uso)} cada={tasaDias} />
        {general && (
          <Anunciado urgencia="alert" className="flex max-w-prose gap-1.5 font-bold text-pronto">
            <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0" />
            <p className="min-w-0">
              {general.titulo && <>{general.titulo} </>}
              {general.texto}
            </p>
          </Anunciado>
        )}
        {conflicto ? (
          <Conflicto
            id={`${uid}-conflicto`}
            leido={perfil!}
            actual={conflicto}
            mio={cambios()}
            ocupado={ocupado}
            onGuardarMio={() => {
              const etag = conflicto.etag
              setConflicto(null)
              void guardar(etag)
            }}
            onDejarSuyo={() => onDejarSuyo(conflicto)}
          />
        ) : (
          <Acciones>
            <Boton type="submit" ocupado={ocupado} textoOcupado={INSUMOS.guardando}>
              {INSUMOS.guardar}
            </Boton>
            <button type="button" onClick={onCancelar} className="inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa">
              {INSUMOS.cancelar}
            </button>
          </Acciones>
        )}
      </form>
    </>,
  )
}

/**
 * MATU-60 9.2: «¿Cuántas unidades trae cada envase?», opcional, de 1 a 10.000. Sin − ni +: los
 * envases traen 20, 30 u 80. La ayuda va antes del campo y lo describe, con el error si lo hay.
 */
function CampoEnvase({ id, valor, onCambio, sufijo, error }: { id: string; valor: string; onCambio: (v: string) => void; sufijo: string; error?: string }) {
  const describe = [`${id}-a`, error ? `${id}-e` : ''].filter(Boolean).join(' ')
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="font-bold">
        {LISTA.envase}
      </label>
      <span id={`${id}-a`} className="text-base text-tenue">
        {LISTA.envaseAyuda}
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <input
          id={id}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          maxLength={5}
          value={valor}
          aria-invalid={error ? true : undefined}
          aria-describedby={describe}
          onChange={(e) => onCambio(soloDigitos(e.target.value, 5))}
          className={`cifras min-h-12 w-32 rounded-xl bg-hoja px-4 text-xl ring-2 ring-inset focus-visible:ring-turquesa ${error ? 'ring-pronto' : 'ring-borde'}`}
        />
        <span className="text-base text-tenue">{sufijo}</span>
      </div>
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
    </div>
  )
}

function CampoNombre({ id, valor, onCambio, error, soloLectura }: { id: string; valor: string; onCambio: (v: string) => void; error?: string; soloLectura: boolean }) {
  if (soloLectura) return null
  const n = valor.length
  const describe = [`${id}-a`, `${id}-c`, error ? `${id}-e` : ''].filter(Boolean).join(' ')
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="font-bold">
        {INSUMOS.nombre}
      </label>
      <span id={`${id}-a`} className="text-base text-tenue">
        {INSUMOS.nombreAyuda}
      </span>
      <input
        id={id}
        type="text"
        value={valor}
        maxLength={60}
        autoComplete="off"
        enterKeyHint="next"
        aria-invalid={error ? true : undefined}
        aria-describedby={describe}
        onChange={(e) => onCambio(unaLinea(e.target.value))}
        className={`min-h-12 w-full max-w-xl min-w-0 rounded-xl bg-hoja px-4 py-2.5 ring-2 ring-inset focus-visible:ring-turquesa ${error ? 'ring-pronto' : 'ring-borde'}`}
      />
      <span id={`${id}-c`} aria-live={n >= 50 ? 'polite' : 'off'} className="cifras max-w-xl text-right text-base text-tenue">
        {INSUMOS.contador(n)}
      </span>
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
    </div>
  )
}

// ---------------------------------------------------------------- 3.5 conflicto

function Conflicto({
  id,
  leido,
  actual,
  mio,
  ocupado,
  onGuardarMio,
  onDejarSuyo,
}: {
  id: string
  leido: Perfil
  actual: Perfil
  mio: SolicitudEdicion
  ocupado: boolean
  onGuardarMio: () => void
  onDejarSuyo: () => void
}) {
  const autor = actual.actualizado_por?.nombre?.trim() || INSUMOS.otraPersona
  const nombre = nombreDe(actual)
  const fila = (texto: ReactNode, cambio: boolean) => (
    <li className={cambio ? 'font-bold' : ''}>
      {texto} {cambio && <span>{INSUMOS.cambio}</span>}
    </li>
  )
  const l = lineaDias(actual.dias_restantes)
  // MATU-60 9.4: el envase, si lo cambió esta persona o la otra.
  const envaseDe = (u: number | null | undefined) => (u == null ? LISTA.sinEnvase : LISTA.envaseConflicto(miles(u), sufijoCantidad(u, actual.unidad, null)))
  const envaseLeido = leido.unidades_por_envase ?? null
  const envaseActual = actual.unidades_por_envase ?? null
  const verEnvase = mio.unidades_por_envase !== undefined || envaseActual !== envaseLeido
  return (
    <div role="alert" className="@container flex flex-col gap-4 rounded-xl border-l-4 border-atenta bg-atenta-fondo px-4 angosto:px-2 py-4">
      <h2 id={id} tabIndex={-1} className="text-xl font-bold break-words [overflow-wrap:anywhere] outline-none">
        {INSUMOS.conflictoTitulo(autor, nombre)}
      </h2>
      <p className="max-w-prose">{INSUMOS.conflicto}</p>
      <div className="grid grid-cols-1 gap-3 @md:grid-cols-2">
        <section className="rounded-xl bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea">
          <h3 className="mb-1 font-bold">{INSUMOS.loQueGuardo}</h3>
          <ul className="flex flex-col gap-1">
            {fila(INSUMOS.nombreEs(nombre), nombre !== nombreDe(leido))}
            {fila(INSUMOS.usa(actual.tasa_unidades, actual.tasa_dias, actual.unidad), actual.tasa_unidades !== leido.tasa_unidades || actual.tasa_dias !== leido.tasa_dias)}
            {fila(
              <>
                {INSUMOS.quedaban(actual.stock_unidades, actual.unidad)} <span className="cifras whitespace-nowrap">{fechaCorta(actual.stock_medido_en)}</span>.
              </>,
              actual.stock_unidades !== leido.stock_unidades || actual.stock_medido_en !== leido.stock_medido_en,
            )}
            {fila(INSUMOS.avisaAntes(actual.dias_aviso), actual.dias_aviso !== leido.dias_aviso)}
            {fila(l.cifra === null ? l.texto : `${l.texto} ${l.cifra} ${l.resto}`, actual.dias_restantes !== leido.dias_restantes)}
            {verEnvase && fila(envaseDe(envaseActual), envaseActual !== envaseLeido)}
          </ul>
        </section>
        <section className="rounded-xl bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea">
          <h3 className="mb-1 font-bold">{INSUMOS.loTuyo}</h3>
          <ul className="flex flex-col gap-1">
            {mio.nombre_libre !== undefined && <li>{INSUMOS.nombreEs(mio.nombre_libre ?? '')}</li>}
            {(mio.tasa_unidades !== undefined || mio.tasa_dias !== undefined) && (
              <li>{INSUMOS.usa(mio.tasa_unidades ?? actual.tasa_unidades, mio.tasa_dias ?? actual.tasa_dias, actual.unidad)}</li>
            )}
            {mio.stock_unidades != null && <li>{INSUMOS.quedanHoy(mio.stock_unidades, actual.unidad)}</li>}
            {mio.dias_aviso != null && <li>{INSUMOS.avisaAntes(mio.dias_aviso)}</li>}
            {mio.unidades_por_envase !== undefined && <li>{envaseDe(mio.unidades_por_envase)}</li>}
          </ul>
        </section>
      </div>
      <Acciones>
        <Boton ocupado={ocupado} textoOcupado={INSUMOS.guardando} onClick={onGuardarMio}>
          {INSUMOS.guardarLoMio}
        </Boton>
        <Boton variante="secundario" onClick={onDejarSuyo}>
          {INSUMOS.dejarLoSuyo}
        </Boton>
      </Acciones>
    </div>
  )
}

// ---------------------------------------------------------------- 3.6.2 eliminar

function DialogoEliminar({
  perfil,
  personaId,
  onCancelar,
  onEliminado,
  onPermiso,
}: {
  perfil: Perfil
  personaId: string
  onCancelar: () => void
  onEliminado: (p: Perfil, yaNoEstaba: boolean) => void
  onPermiso: (c: 'sin-consentimiento' | 'revision-vencida') => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const uid = useId()
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState(false)
  const nombre = nombreDe(perfil)
  const cerrado = useRef(false)
  const cancelarRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
    // Foco inicial en «Cancelar», lo seguro (3.6.2). `showModal` enfoca el primer botón.
    cancelarRef.current?.focus()
    const papelera = document.activeElement as HTMLElement | null
    return () => {
      // Al cancelar, el foco vuelve a la papelera; al eliminar, al título (lo pone la pantalla).
      if (!cerrado.current && papelera && document.contains(papelera)) window.setTimeout(() => papelera.focus(), 0)
    }
  }, [])

  const eliminar = async () => {
    if (ocupado) return
    setOcupado(true)
    setError(false)
    try {
      await eliminarPerfil(personaId, perfil.id)
      cerrado.current = true
      ref.current?.close()
      onEliminado(perfil, false)
    } catch (x) {
      if (esVencida(x)) return
      const permiso = permisoDe(x)
      if (permiso) return onPermiso(permiso)
      if (leerFallo(x).status === 404) {
        cerrado.current = true
        ref.current?.close()
        return onEliminado(perfil, true)
      }
      setError(true)
    } finally {
      setOcupado(false)
    }
  }

  // En modo angosto el diálogo gana ancho y achica el relleno: a 320 px con el texto al 200 % el
  // texto pasa de 150 a 252 px y las palabras ya no se parten (revisión visual del #53, P2).
  return (
    <dialog
      ref={ref}
      aria-labelledby={`${uid}-t`}
      aria-describedby={`${uid}-d`}
      onCancel={(e) => {
        e.preventDefault()
        onCancelar()
      }}
      className="m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-md rounded-2xl bg-hoja p-6 angosto:px-2 angosto:py-4 text-tinta backdrop:bg-tinta/40"
    >
      <div className="flex flex-col gap-4">
        <h2 id={`${uid}-t`} className="text-xl font-bold break-words [overflow-wrap:anywhere]">
          {INSUMOS.eliminarTitulo(nombre)}
        </h2>
        <div id={`${uid}-d`} className="flex flex-col gap-2">
          <p>{INSUMOS.eliminarTexto}</p>
          {perfil.activo && <p className="text-tenue">{INSUMOS.eliminarAlternativa}</p>}
        </div>
        {/* Con `showModal` lo de fuera del diálogo queda inerte, también las regiones vivas de
            main.tsx: el aviso usa su propia región, montada vacía con el diálogo. Vacía, devuelve
            el `gap-4` que le toca, para que el diálogo se vea igual que antes. */}
        <div role="alert" className="empty:-mb-4">
          {error && <MensajeError>{INSUMOS.errRedSinEscrito}</MensajeError>}
        </div>
        <Acciones>
          <button
            type="button"
            aria-busy={ocupado || undefined}
            onClick={() => void eliminar()}
            className="inline-flex min-h-12 max-w-full items-center justify-center rounded-xl bg-pronto px-5 angosto:px-3 py-2.5 font-bold leading-tight text-papel hover:brightness-110 active:brightness-95"
          >
            <span className="grid">
              <span className={`col-start-1 row-start-1 ${ocupado ? 'invisible' : ''}`}>{INSUMOS.eliminar}</span>
              <span className={`col-start-1 row-start-1 ${ocupado ? '' : 'invisible'}`} aria-hidden={!ocupado || undefined}>
                {INSUMOS.eliminando}
              </span>
            </span>
          </button>
          <button
            type="button"
            ref={cancelarRef}
            onClick={onCancelar}
            className="inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa"
          >
            {INSUMOS.cancelar}
          </button>
        </Acciones>
      </div>
    </dialog>
  )
}

// ---------------------------------------------------------------- MATU-37 «Se acaban pronto»

/** Días y fecha de un aviso (especificación MATU-37, 3.5 y 7). */
function DiasDelAviso({ a }: { a: PorAcabarse }) {
  const l = lineaDias(a.dias_restantes)
  const fecha = <span className="cifras whitespace-nowrap">{fechaCorta(a.fecha_quiebre_estimada)}</span>
  return (
    <div className="flex min-w-0 flex-col">
      <p className="flex items-start gap-2 text-xl font-bold">
        {l.cifra === null && <CircleAlert aria-hidden className="mt-1 size-5 shrink-0 text-pronto" />}
        <span className="min-w-0">
          {l.texto}
          {l.cifra !== null && (
            <>
              {' '}
              <span className="cifras">{l.cifra}</span> {l.resto}
            </>
          )}
        </span>
      </p>
      {a.dias_restantes > 0 && (
        <p className="text-base">
          {ALERTAS.fechaEstimada} {fecha}
        </p>
      )}
      {a.dias_restantes < 0 && (
        <p className="text-base">
          {INSUMOS.seAcababa} {fecha}.
        </p>
      )}
    </div>
  )
}

type ErrorAviso = { texto: string; tipo: 'general' | 'cerrado' | 'campo' }

function SeAcabanPronto({
  avisos,
  error,
  editor,
  personaId,
  confirmacion,
  onReintentar,
  onResuelto,
  onVerComoQuedo,
  onPermiso,
}: {
  avisos: PorAcabarse[]
  error: boolean
  editor: boolean
  personaId: string
  confirmacion: string | null
  onReintentar: () => void
  onResuelto: (texto: string) => Promise<void>
  onVerComoQuedo: () => void
  onPermiso: (c: 'sin-consentimiento' | 'revision-vencida') => void
}) {
  const [abiertoId, setAbiertoId] = useState<string | null>(null)
  const [valor, setValor] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [falla, setFalla] = useState<ErrorAviso | null>(null)

  const abrir = (id: string) => {
    if (ocupado) return
    setAbiertoId(id)
    setValor('')
    setFalla(null)
    enfocar(CANTIDAD_EN_RESOLVER ? `cantidad-${id}` : `confirmar-${id}`)
  }
  const cerrar = (id: string) => {
    if (ocupado) return
    setAbiertoId(null)
    setFalla(null)
    enfocar(`resolver-${id}`)
  }

  const confirmar = async (a: PorAcabarse) => {
    if (ocupado) return
    const nombre = nombreDe(a)
    const n = CANTIDAD_EN_RESOLVER ? entero(valor) : null
    const cant = n === null || n === 0 ? null : n
    if (cant !== null && cant > 9999) {
      setFalla({ texto: ALERTAS.errCantidad, tipo: 'campo' })
      return void enfocar(`cantidad-${a.id}`)
    }
    setOcupado(true)
    setFalla(null)
    try {
      // Sin interfaz optimista (4.4): el aviso sigue igual hasta la respuesta.
      const r = await resolverAviso(personaId, a.id, a.etag, cant)
      const texto =
        cant === null
          ? ALERTAS.okSinCantidad(nombre)
          : r.dias_restantes > 0
            ? ALERTAS.okCantidad(cantidad(cant, a.unidad), nombre, r.dias_restantes)
            : ALERTAS.okCantidadSinDias(cantidad(cant, a.unidad), nombre)
      await onResuelto(texto)
      setAbiertoId(null)
    } catch (x) {
      if (esVencida(x)) return
      const permiso = permisoDe(x)
      if (permiso) return onPermiso(permiso)
      const f = leerFallo(x)
      const actual = leerConflictoPerfil(x)
      // 412: otra persona cambió el insumo; no se sumó nada. 428 no debería pasar: cae en el genérico.
      if (f.status === 412) setFalla({ texto: ALERTAS.errConflicto(actual?.actualizado_por?.nombre?.trim() || INSUMOS.otraPersona, actual ? nombreDe(actual) : nombre), tipo: 'cerrado' })
      else if (f.status === 409 && esTipo(f.tipo, 'alerta-cerrada')) setFalla({ texto: ALERTAS.errCerrada, tipo: 'cerrado' })
      else if (f.status === 404 || f.status === 409) setFalla({ texto: ALERTAS.errNoEsta, tipo: 'cerrado' })
      else if (f.status === 422 && CANTIDAD_EN_RESOLVER) {
        setFalla({ texto: ALERTAS.errCantidad, tipo: 'campo' })
        enfocar(`cantidad-${a.id}`)
      } else setFalla({ texto: ALERTAS.errRed, tipo: 'general' })
    } finally {
      setOcupado(false)
    }
  }

  // A 360 px el panel con el error no puede quedar bajo la barra fija: se enfoca el aviso y se
  // desplaza el panel completo (scroll-mb-28 deja el espacio de la barra).
  useEffect(() => {
    if (!falla || !abiertoId) return
    const t = window.setTimeout(() => {
      if (falla.tipo !== 'campo') document.getElementById(`falla-${abiertoId}`)?.focus({ preventScroll: true })
      document.getElementById(`panel-${abiertoId}`)?.scrollIntoView({ block: 'nearest' })
    }, 60)
    return () => window.clearTimeout(t)
  }, [falla, abiertoId])

  const titulo = !error && avisos.length > 3 ? ALERTAS.tituloCuantos(avisos.length) : ALERTAS.titulo
  const hayBloque = error || avisos.length > 0

  return (
    <>
      {confirmacion && (
        <div id="aviso-alertas" tabIndex={-1} role="status" className="animate-aparecer flex max-w-prose gap-3 rounded-xl bg-ok-fondo px-4 py-3 text-tinta outline-none">
          <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" />
          <p className="min-w-0 break-words [overflow-wrap:anywhere]">{confirmacion}</p>
        </div>
      )}
      {hayBloque && (
        <section aria-labelledby="titulo-se-acaban" className="flex flex-col gap-3 rounded-xl bg-atenta-fondo px-4 angosto:px-2 py-4 ring-1 ring-linea">
          <h2 id="titulo-se-acaban" tabIndex={-1} className="flex items-center outline-none gap-2 text-xl font-bold text-tinta">
            <BellRing aria-hidden className="size-6 shrink-0 text-atenta" />
            <span className="min-w-0">{titulo}</span>
          </h2>
          {error ? (
            <div className="flex flex-col items-start gap-3">
              <Anunciado urgencia="alert">
                <MensajeError>{ALERTAS.errCarga}</MensajeError>
              </Anunciado>
              <Boton variante="secundario" onClick={onReintentar}>
                {GENERAL.volverAIntentar}
              </Boton>
            </div>
          ) : (
            <>
              <ul className="flex flex-col gap-2">
                {avisos.map((a) => {
                  const nombre = nombreDe(a)
                  const abierto = abiertoId === a.id
                  const panel = `panel-${a.id}`
                  return (
                    <li key={a.id} className="flex flex-col rounded-xl bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea">
                      <div className="flex flex-col gap-2 @3xl/main:flex-row @3xl/main:flex-wrap @3xl/main:items-center @3xl/main:justify-between @3xl/main:gap-x-6">
                        <p className="min-w-0 font-bold break-words [overflow-wrap:anywhere]">{nombre}</p>
                        <DiasDelAviso a={a} />
                        {editor && !abierto && (
                          <Boton
                            id={`resolver-${a.id}`}
                            variante="secundario"
                            aria-label={ALERTAS.botonDe(nombre)}
                            aria-expanded={false}
                            aria-controls={panel}
                            className="self-end @3xl/main:ms-auto @3xl/main:self-auto"
                            onClick={() => abrir(a.id)}
                          >
                            {ALERTAS.boton}
                          </Boton>
                        )}
                      </div>
                      {editor && abierto && (
                        <div
                          id={panel}
                          className="mt-3 flex scroll-mb-28 flex-col gap-3 border-t border-linea pt-3"
                          onKeyDown={(e) => {
                            if (e.key === 'Escape') {
                              e.stopPropagation()
                              cerrar(a.id)
                            }
                          }}
                        >
                          <div className="flex flex-col gap-3 @3xl/main:flex-row @3xl/main:flex-wrap @3xl/main:items-end @3xl/main:gap-4">
                            {CANTIDAD_EN_RESOLVER && (
                              <Stepper
                                id={`cantidad-${a.id}`}
                                etiqueta={ALERTAS.pregunta(a.unidad)}
                                ayuda={ALERTAS.ayuda}
                                sufijo={a.unidad === 'sobre' ? 'sobres' : a.unidad === 'unidad' ? undefined : a.unidad}
                                valor={valor}
                                onCambio={(v) => {
                                  setValor(v)
                                  if (falla?.tipo === 'campo') setFalla(null)
                                }}
                                min={1}
                                max={9999}
                                error={falla?.tipo === 'campo' ? falla.texto : null}
                              />
                            )}
                            <div className="flex flex-wrap gap-3">
                              <Boton id={`confirmar-${a.id}`} aria-label={ALERTAS.botonDe(nombre)} ocupado={ocupado} textoOcupado={ALERTAS.guardando} onClick={() => void confirmar(a)}>
                                {ALERTAS.boton}
                              </Boton>
                              <Boton variante="secundario" disabled={ocupado} onClick={() => cerrar(a.id)}>
                                {ALERTAS.volver}
                              </Boton>
                            </div>
                          </div>
                          {falla && falla.tipo !== 'campo' && (
                            <div id={`falla-${a.id}`} tabIndex={-1} role="alert" className="flex flex-col items-start gap-3 outline-none">
                              <MensajeError>{falla.texto}</MensajeError>
                              {falla.tipo === 'cerrado' && (
                                <Boton
                                  variante="secundario"
                                  onClick={() => {
                                    setAbiertoId(null)
                                    setFalla(null)
                                    onVerComoQuedo()
                                  }}
                                >
                                  {ALERTAS.verComoQuedo}
                                </Boton>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
              <p className="max-w-prose text-base text-tenue">{ALERTAS.nota}</p>
            </>
          )}
        </section>
      )}
    </>
  )
}
