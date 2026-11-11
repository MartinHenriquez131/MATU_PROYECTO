// «Insumos» de la app de la familia (MATU-36, especificación docs/diseno/matu-36-insumos.md):
// el permiso la primera vez, la lista con «Seguir» y la papelera, anotar o cambiar un insumo con
// `If-Match`, el conflicto 412 a la vista y el diálogo de eliminar. Sin interfaz optimista: la
// lista cambia solo con la respuesta de la API. Nada se guarda en el navegador ni en la URL.
// MATU-51 (docs/diseno/matu-51-compre-me-quedan.md v1.2): «Compré» y «Me quedan» en cada fila, con
// `If-Match` y sin interfaz optimista, y un solo panel abierto a la vez en toda la pantalla.
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Bell, BellRing, CalendarCheck, Check, CircleAlert, CircleCheck, Hourglass, ListChecks, Lock, PauseCircle, Plus, Trash2 } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  anotarCompra,
  anotarLoQueQueda,
  autorizarConsumo,
  crearPerfil,
  editarPerfil,
  eliminarPerfil,
  leerConflictoPerfil,
  listarConsumo,
  listarPorAcabarse,
  resolverAviso,
  type LoComprado,
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
import { AVISO_VERSION } from '../compartido/textosVersion'
import { registrarSinGuardar } from '../compartido/version'
import { Boton } from '../compartido/ui/Boton'
import { LeePoliticaAntesDeAutorizar } from '../compartido/ui/Enlaces'
import { AVISO_CUIDADOR, CALIDADES } from './datos'
import { useDemora } from './Estados'
import { puedeEditar, useFamilia } from './estado'
import { navegar, useRuta, type Ruta } from './ruteo'
import { enfocar, entero, esTipo, permisoDe, soloDigitos, Stepper, unaLinea, useAncho } from './insumosComun'
import { AUTORIZACION, FICHA, GENERAL, LISTA } from './textos'
import { envaseUtil, envaseValido, ENVASE_MAX, juntar, maxEnvases, repartir, seCuentaEnEnvases, TOTAL_MAX, totalDe, totalVisible } from './enEnvases'
import { cantidadEnTexto, miles, sufijoCantidad } from './textoLista'
import { CATALOGO } from './textosCatalogo'
import { ALERTAS, cantidad, DECLARACION_CONSUMO, diasEnTexto, EN_ENVASES, enPantalla, INSUMOS, lineaDias, REGISTRO } from './textosInsumos'
import { Acciones, AvisoCuidadorDeHecho, CampoTexto, GrupoOpciones, MensajeError, Nota, Pestanas, Titulo, Volver } from './ui'

type Carga = 'cargando' | 'listo' | 'sin-consentimiento' | 'revision-vencida' | 'no-encontrado' | 'red'

/** Los que se siguen, el que se acaba primero arriba (el orden de la API). */
const porFecha = (a: Perfil, b: Perfil) => a.fecha_quiebre_estimada.localeCompare(b.fecha_quiebre_estimada)

/**
 * MATU-60 (2.1): las vistas de la sección, antes del título. En `/insumos` con la lista cargada y en
 * `/insumos/lista` en todos sus estados. No en el formulario a 360 px.
 * MATU-59 (2.2, N1): «Catálogo» al final, en `/insumos/catalogo` en todos sus estados. En `/insumos`,
 * en el permiso, en «Falta el permiso» y en «Hay que renovar» van solo «Insumos» y «Catálogo»
 * (`sinLista`): «Lista de insumos» llevaría de vuelta a la misma pantalla.
 */
export function PestanasInsumos({ activa, sinLista = false }: { activa: '/insumos' | '/insumos/lista' | '/insumos/catalogo'; sinLista?: boolean }) {
  const items: { texto: string; ruta: Ruta; activa: boolean }[] = [{ texto: INSUMOS.titulo, ruta: '/insumos', activa: activa === '/insumos' }]
  if (!sinLista) items.push({ texto: LISTA.titulo, ruta: '/insumos/lista', activa: activa === '/insumos/lista' })
  items.push({ texto: CATALOGO.titulo, ruta: '/insumos/catalogo', activa: activa === '/insumos/catalogo' })
  return <Pestanas etiqueta={LISTA.vistas} items={items} />
}

/**
 * MATU-51 3.6: el panel abierto, uno solo en toda la pantalla: «Compré» o «Me quedan» de una fila,
 * o «Ya lo resolví» de un aviso. El formulario de «Anotar un insumo» también cuenta: abrir un panel
 * lo cierra, y abrirlo cierra el panel.
 */
type Panel = { tipo: 'compre' | 'quedan' | 'resolver'; id: string }

/** La confirmación de una fila (5.3): la frase y, si la hay, la fecha, que va en `cifras` con su punto. */
/** MATU-84 (4.5): `cola`, la frase que va después de la fecha si se anotó el envase en el panel. */
type Hecho = { texto: string; fecha: string | null; cola?: string }

/** Lleva el foco a un elemento y lo desplaza a la vista, sin pasar por debajo de la barra fija (4). */
const mostrar = (id: string, ms = 40) =>
  window.setTimeout(() => {
    const el = document.getElementById(id)
    el?.focus()
    el?.scrollIntoView?.({ block: 'nearest' })
  }, ms)

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
  // MATU-51: el panel abierto, la confirmación de la fila y el 404 arriba, en el lugar del aviso.
  const [panel, setPanel] = useState<Panel | null>(null)
  const [hecho, setHecho] = useState<(Hecho & { id: string }) | null>(null)
  const [avisoFalla, setAvisoFalla] = useState<string | null>(null)
  // Mientras un panel guarda, no se abre otro ni se cierra (5.2).
  const guardandoPanel = useRef(false)

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

  // Abrir el formulario cierra el panel abierto (3.6).
  useEffect(() => {
    if (modo) setPanel(null)
  }, [modo])

  /** En la pantalla hay un solo mensaje a la vez (3.6). */
  const limpiarMensajes = () => {
    setAviso(null)
    setAvisoAlerta(null)
    setHecho(null)
    setAvisoFalla(null)
  }

  const abrirPanel = (tipo: Panel['tipo'], id: string) => {
    if (guardandoPanel.current) return
    limpiarMensajes()
    setErrorFila(null)
    if (modo) {
      setEditandoId(null)
      navegar('/insumos')
    }
    setPanel({ tipo, id })
  }

  /** «Volver» y Escape: cierra sin guardar y devuelve el foco al botón que lo abrió. */
  const cerrarPanel = (foco: string) => {
    if (guardandoPanel.current) return
    setPanel(null)
    enfocar(foco)
  }

  /** «Compré» o «Me quedan» guardó: la fila, el bloque y la confirmación salen de la respuesta (5.3). */
  // MATU-84 D5: el `PATCH` responde el perfil sin `avisando`; la marca sale de `refrescarBloque`.
  const alAnotar = (r: Perfil | PorAcabarse, texto: Hecho) => {
    reemplazar(r)
    setPorAcabarse((xs) => {
      if (!xs) return xs
      if (!('avisando' in r)) return xs.map((x) => (x.id === r.id ? { ...x, ...r } : x))
      return xs.some((x) => x.id === r.id) ? xs.map((x) => (x.id === r.id ? r : x)) : r.avisando ? [...xs, r] : xs
    })
    void refrescarBloque()
    setPanel(null)
    setHecho({ id: r.id, ...texto })
    mostrar(`hecho-${r.id}`)
  }

  const alPermiso = (c: 'sin-consentimiento' | 'revision-vencida') => {
    setPanel(null)
    setCarga(c)
    enfocar('titulo-pagina', 60)
  }

  /** 404: la fila ya no existe, así que el mensaje va arriba, con el foco (5.5). */
  const alNoEstar = () => {
    setPanel(null)
    limpiarMensajes()
    setAvisoFalla(REGISTRO.errNoEsta)
    void cargar(true)
    enfocar('aviso-insumos', 60)
  }

  /** «Ver cómo quedó» después de un 409 o un 412: recarga en silencio y lleva el foco a lo que sigue. */
  const verComoQuedo = async (foco: string) => {
    setPanel(null)
    await cargar(true)
    enfocar(document.getElementById(foco) ? foco : 'titulo-pagina', 80)
  }

  const volverALista = (texto: string | null) => {
    setAviso(texto)
    setAvisoAlerta(null)
    setHecho(null)
    setAvisoFalla(null)
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
    setHecho(null)
    setAvisoFalla(null)
    if (panel?.id === p.id && !guardandoPanel.current) setPanel(null)
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
    setHecho(null)
    setAvisoFalla(null)
    if (panel?.id === p.id) setPanel(null)
    if (yaNoEstaba) {
      void cargar()
    } else {
      setItems((xs) => xs.filter((x) => x.id !== p.id))
      void refrescarBloque()
      setAviso(INSUMOS.eliminaste(nombreDe(p)))
    }
    enfocar('titulo-pagina')
  }

  // MATU-59 (2.2): el catálogo no depende del permiso de los insumos; sin estas pestañas no se llegaría a él.
  const pestanasPermiso = ruta === '/insumos' ? <PestanasInsumos activa="/insumos" sinLista /> : undefined

  const contenido = () => {
    if (carga === 'cargando') return <Cargando />
    if (carga === 'sin-consentimiento')
      return editor ? (
        <Permiso
          pila={pila}
          personaId={personaId}
          antes={pestanasPermiso}
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
        <UnaColumna titulo={INSUMOS.titulo} baldosa={<Lock aria-hidden className="size-9" />} tono="neutro" antes={pestanasPermiso}>
          <p className="max-w-prose text-lg">
            <strong>{INSUMOS.faltaPermisoTitulo(pila)}</strong> {INSUMOS.faltaPermiso(pila)}
          </p>
        </UnaColumna>
      )
    if (carga === 'revision-vencida')
      return (
        <UnaColumna titulo={INSUMOS.titulo} baldosa={<Hourglass aria-hidden className="size-9" />} tono="atenta" antes={pestanasPermiso}>
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
          abiertoId={panel?.tipo === 'resolver' ? panel.id : null}
          onAbrir={(id) => abrirPanel('resolver', id)}
          onCerrar={(id) => cerrarPanel(`resolver-${id}`)}
          onOcupado={(v) => (guardandoPanel.current = v)}
          onReintentar={() => void refrescarBloque()}
          onResuelto={async (texto) => {
            setAviso(null)
            await cargar(true)
            setPanel(null)
            setAvisoAlerta(texto)
            enfocar('aviso-alertas', 60)
          }}
          onVerComoQuedo={() => {
            setPanel(null)
            void cargar(true).then(() => enfocar(document.getElementById('titulo-se-acaban') ? 'titulo-se-acaban' : 'titulo-pagina', 80))
          }}
          onPermiso={alPermiso}
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
        hecho={hecho?.id === p.id ? hecho : null}
        abierto={panel && panel.id === p.id && panel.tipo !== 'resolver' ? panel.tipo : null}
        panel={
          panel && panel.id === p.id && panel.tipo !== 'resolver' && personaId ? (
            <PanelRegistro
              key={`${panel.tipo}-${p.id}`}
              tipo={panel.tipo}
              perfil={p}
              personaId={personaId}
              onCerrar={() => cerrarPanel(`${panel.tipo}-${p.id}`)}
              onOcupado={(v) => (guardandoPanel.current = v)}
              onHecho={alAnotar}
              onPermiso={alPermiso}
              onNoEncontrado={alNoEstar}
              onVerComoQuedo={(foco) => void verComoQuedo(foco)}
            />
          ) : null
        }
        onAbrir={(tipo) => abrirPanel(tipo, p.id)}
        onCambiar={() => {
          if (guardandoPanel.current) return
          limpiarMensajes()
          setPanel(null)
          setEditandoId(p.id)
          navegar('/insumos/cambiar')
        }}
        onSeguir={(v) => void alSeguir(p, v)}
        onEliminar={() => {
          if (guardandoPanel.current) return
          setEliminando(p)
        }}
      />
    )
    const botonAnotar = editor && items.length > 0 && (
      <Boton
        // A5: con un panel abierto, el macizo es su confirmar, no «Anotar un insumo».
        variante={form || panel ? 'secundario' : 'principal'}
        icono={<Plus aria-hidden className="size-5" />}
        className="self-start"
        onClick={() => {
          if (guardandoPanel.current) return
          limpiarMensajes()
          setPanel(null)
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
        {!ancho && avisoFalla && <AvisoFalla texto={avisoFalla} />}

        <div className={ancho ? 'grid grid-cols-[3fr_2fr] items-start gap-10' : 'flex flex-col gap-5'}>
          <div className="flex min-w-0 flex-col gap-5">
            {/* En pantalla ancha, el bloque y la nota van en la columna de la lista (3.4). */}
            {ancho && bloque}
            {ancho && nota}
            {ancho && aviso && <AvisoOk texto={aviso} />}
            {ancho && avisoFalla && <AvisoFalla texto={avisoFalla} />}
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

function UnaColumna({
  titulo,
  baldosa,
  tono,
  antes,
  children,
}: {
  titulo: string
  baldosa: ReactNode
  tono: 'neutro' | 'atenta' | 'rocio'
  antes?: ReactNode
  children: ReactNode
}) {
  const fondo = { neutro: 'bg-tinta/7 text-tenue', atenta: 'bg-atenta-fondo text-atenta', rocio: 'bg-rocio text-turquesa' }[tono]
  const titular = <Titulo className="text-3xl @2xl/main:text-5xl">{titulo}</Titulo>
  return (
    <div className="flex flex-col items-start gap-5">
      {antes ? (
        <div className="flex flex-col gap-3 self-stretch">
          {antes}
          {titular}
        </div>
      ) : (
        titular
      )}
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

/** MATU-51 5.5: el 404 de «Compré» o «Me quedan», en el lugar de `AvisoOk` y con el foco. */
function AvisoFalla({ texto }: { texto: string }) {
  return (
    <div id="aviso-insumos" tabIndex={-1} role="alert" className="max-w-prose outline-none">
      <MensajeError>{texto}</MensajeError>
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
  hecho,
  abierto,
  panel,
  onAbrir,
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
  /** MATU-51: la confirmación de «Compré» o «Me quedan» de esta fila. */
  hecho: Hecho | null
  /** El panel abierto en esta fila, que reemplaza el renglón de registro (3.4). */
  abierto: 'compre' | 'quedan' | null
  panel: ReactNode
  onAbrir: (tipo: 'compre' | 'quedan') => void
  onCambiar: () => void
  onSeguir: (v: boolean) => void
  onEliminar: () => void
}) {
  const nombre = nombreDe(p)
  const idNombre = `nombre-${p.id}`
  const registro = editor && p.activo
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
      {hecho && (
        <div id={`hecho-${p.id}`} tabIndex={-1} role="status" className="animate-aparecer flex scroll-mb-28 gap-3 rounded-xl bg-ok-fondo px-4 angosto:px-2 py-3 outline-none">
          <Check aria-hidden className="mt-0.5 size-5 shrink-0 text-ok angosto:hidden" strokeWidth={3} />
          <p className="min-w-0 break-words [overflow-wrap:anywhere]">
            {hecho.texto}
            {hecho.fecha && (
              <>
                {' '}
                <span className="cifras whitespace-nowrap">{hecho.fecha}.</span>
              </>
            )}
            {hecho.cola && <> {hecho.cola}</>}
          </p>
        </div>
      )}
      {/* MATU-51 3.1 y 3.7: «Compré» y «Me quedan» solo para admin y cuidador, y solo en lo que se sigue. */}
      {registro &&
        (abierto ? (
          panel
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Boton
              id={`compre-${p.id}`}
              variante="secundario"
              aria-label={REGISTRO.compreDe(nombre)}
              aria-expanded={false}
              aria-controls={`panel-compre-${p.id}`}
              onClick={() => onAbrir('compre')}
            >
              {REGISTRO.compre}
            </Boton>
            <Boton
              id={`quedan-${p.id}`}
              variante="secundario"
              aria-label={REGISTRO.meQuedanDe(nombre)}
              aria-expanded={false}
              aria-controls={`panel-quedan-${p.id}`}
              onClick={() => onAbrir('quedan')}
            >
              {REGISTRO.meQuedan}
            </Boton>
          </div>
        ))}
      {editor && (
        <div className={`flex flex-wrap items-center gap-4 ${registro ? 'border-t border-linea pt-3' : ''}`}>
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
              className="size-6 shrink-0 accent-turquesa"
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
            className="ms-auto grid size-12 shrink-0 place-items-center rounded-xl bg-hoja text-pronto ring-2 ring-inset ring-pronto/80 hover:bg-pronto-fondo active:bg-pronto-fondo"
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

// ---------------------------------------------------------------- MATU-51 «Compré» y «Me quedan»

/** La confirmación de 5.3 y 8, con los días y la fecha de la respuesta, nunca calculados aquí. */
function textoHecho(tipo: 'compre' | 'quedan', nombre: string, n: number, envase: number | null, r: Perfil): Hecho {
  if (tipo === 'quedan' && n === 0) return { texto: REGISTRO.noQueda(nombre), fecha: null }
  const cant = enPantalla(cantidadEnTexto(n, r.unidad, envase))
  const base = tipo === 'compre' ? REGISTRO.compraAnotada(nombre, cant) : REGISTRO.quedaAnotado(nombre, cant)
  const d = r.dias_restantes
  if (d > 0) return { texto: `${base} ${tipo === 'compre' ? REGISTRO.ahoraAlcanza(d) : REGISTRO.alcanza(d)}`, fecha: fechaCorta(r.fecha_quiebre_estimada) }
  if (d < 0 && tipo === 'compre') return { texto: `${base} ${REGISTRO.puedeQueNo}`, fecha: null }
  return { texto: `${base} ${REGISTRO.seAcabaHoy}`, fecha: null }
}

/** Un error del panel (5.5): con «Ver cómo quedó» después de un 409 o un 412, que lleva el foco a `foco`. */
type FallaPanel = { texto: string; foco?: string }

/**
 * MATU-84 (6): «Contar en envases» y «Contar sueltos», enlaces de texto con el aspecto del
 * «Cancelar» del formulario. Mientras guarda ignoran el toque (10).
 */
function EnlaceModo({ children, onClick, ocupado = false }: { children: ReactNode; onClick: () => void; ocupado?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => {
        if (!ocupado) onClick()
      }}
      className="inline-flex min-h-12 items-center self-start px-2 text-left font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa"
    >
      {children}
    </button>
  )
}

/**
 * MATU-84 (4.1, 5.1 y 6): «Envases enteros» y los sueltos, uno debajo del otro, y el total en vivo.
 * `u` es el envase válido, o `null` mientras falta. `antes` es el campo del envase, cuando se anota
 * aquí. El total no es región viva: el panel lo pone en el `aria-describedby` de su confirmar (8).
 */
function BloqueEnvases({
  id,
  unidad,
  u,
  envases,
  sueltos,
  onEnvases,
  onSueltos,
  error,
  describe,
  soloLectura = false,
  antes,
}: {
  id: string
  unidad: Unidad
  u: number | null
  envases: string
  sueltos: string
  onEnvases: (v: string) => void
  onSueltos: (v: string) => void
  error?: string | null
  describe?: string
  soloLectura?: boolean
  antes?: ReactNode
}) {
  const nEnvases = entero(envases)
  // 1.2: sin envase válido y con envases enteros, el total no se muestra.
  const total = totalVisible(envases, sueltos, u)
  const t = total === null ? null : EN_ENVASES.total(total, unidad)
  return (
    <>
      {antes}
      <Stepper
        id={`${id}-envases`}
        etiqueta={EN_ENVASES.envasesEnteros}
        sufijo={u === null ? EN_ENVASES.sufijoSinEnvase : sufijoCantidad(nEnvases ?? 0, unidad, u)}
        valor={envases}
        onCambio={onEnvases}
        min={0}
        max={maxEnvases(u)}
        error={error}
        describe={describe}
        soloLectura={soloLectura}
        vacioEs={0}
      />
      <Stepper
        id={`${id}-sueltos`}
        etiqueta={EN_ENVASES.sueltos(unidad)}
        sufijo={INSUMOS.sufijoStock(unidad)}
        valor={sueltos}
        onCambio={onSueltos}
        min={0}
        max={TOTAL_MAX}
        describe={describe}
        soloLectura={soloLectura}
        vacioEs={0}
      />
      {t && (
        <p id={`${id}-total`} className="text-base font-bold break-words [overflow-wrap:anywhere]">
          {t.antes}
          {t.cifra !== null && (
            <>
              {' '}
              <span className="cifras">{t.cifra}</span> {t.despues}
            </>
          )}
        </p>
      )}
    </>
  )
}

/**
 * El panel de «Compré» o «Me quedan» (3.4 y 3.5), dentro de la fila. «Compré» pregunta en envases,
 * con 1 por omisión, cuando se sabe cuánto trae cada uno; si no, en la unidad del insumo y vacío.
 * MATU-84: «Me quedan», en unidades y sobres, pregunta en envases enteros más sueltos cuando el
 * envase se conoce y es de más de 1 (D6), y si no ofrece «Contar en envases». ml y g, como siempre
 * (D2). La cantidad va solo en el cuerpo, y siempre en la unidad del insumo.
 */
function PanelRegistro({
  tipo,
  perfil: p,
  personaId,
  onCerrar,
  onOcupado,
  onHecho,
  onPermiso,
  onNoEncontrado,
  onVerComoQuedo,
}: {
  tipo: 'compre' | 'quedan'
  perfil: Perfil
  personaId: string
  onCerrar: () => void
  onOcupado: (v: boolean) => void
  onHecho: (r: Perfil | PorAcabarse, texto: Hecho) => void
  onPermiso: (c: 'sin-consentimiento' | 'revision-vencida') => void
  onNoEncontrado: () => void
  onVerComoQuedo: (foco: string) => void
}) {
  const nombre = nombreDe(p)
  const compre = tipo === 'compre'
  const envase = compre ? (p.unidades_por_envase ?? null) : null
  const conEnvase = envase !== null
  // MATU-84: «Me quedan» en envases solo en unidades y sobres, con el envase guardado de más de 1.
  const contable = !compre && seCuentaEnEnvases(p.unidad)
  const guardado = contable ? envaseUtil(p.unidades_por_envase) : null
  const id = `panel-${tipo}-${p.id}`
  const campo = `campo-${tipo}-${p.id}`
  const idEnvase = `${campo}-envase`
  const idEnvases = `${campo}-envases`
  const idTotal = `${campo}-total`
  const idFalla = `falla-${tipo}-${p.id}`
  const sufijoUnidad = INSUMOS.sufijoStock(p.unidad)
  const [valor, setValor] = useState(conEnvase ? '1' : '')
  const [errorCampo, setErrorCampo] = useState<string | null>(null)
  const [falla, setFalla] = useState<FallaPanel | null>(null)
  const [ocupado, setOcupado] = useState(false)
  // MATU-84 (3): el modo se elige al abrir y no se recuerda. Envases y sueltos abren vacíos (4.1).
  const [modo, setModo] = useState<'sueltos' | 'envases'>(guardado !== null ? 'envases' : 'sueltos')
  const [envases, setEnvases] = useState('')
  const [sueltos, setSueltos] = useState('')
  const [envaseEscrito, setEnvaseEscrito] = useState('')
  const [errores, setErrores] = useState<{ envase?: string; envases?: string }>({})
  const enEnvases = modo === 'envases'
  // Sin envase guardado, el campo del envase se anota aquí (4.2) y se guarda con lo que queda (D5).
  const anotaEnvase = enEnvases && guardado === null
  const u = guardado ?? (anotaEnvase ? envaseValido(envaseEscrito) : null)

  // MATU-67 (G1): con una cantidad distinta de la inicial, «Recargar» del aviso de versión nueva
  // pregunta antes. Sin `texto`: si la entrada vence, no hay nada de la ficha que mostrar. MATU-84
  // (8): el envase, envases enteros y sueltos cuentan como cambios, en ese orden.
  const { sinGuardar } = useFamilia()
  const actual = { valor, envases, sueltos, envaseEscrito }
  const actualRef = useRef(actual)
  actualRef.current = actual
  useEffect(
    () =>
      registrarSinGuardar(sinGuardar, () => {
        const a = actualRef.current
        const foco = a.envaseEscrito ? idEnvase : a.envases ? idEnvases : a.sueltos ? `${campo}-sueltos` : a.valor !== (conEnvase ? '1' : '') ? campo : null
        if (!foco) return null
        return { texto: '', titulo: AVISO_VERSION.sinGuardarInsumo(nombre), foco: document.getElementById(foco) ? foco : campo }
      }),
    [sinGuardar, conEnvase, nombre, campo, idEnvase, idEnvases],
  )

  // 4: con envase el foco va al panel (no se abre el teclado); si hay que escribir, al campo.
  // MATU-84 D4: «Me quedan» con envase guardado, también al panel.
  const alPanel = conEnvase || guardado !== null
  useEffect(() => {
    const t = window.setTimeout(() => {
      document.getElementById(alPanel ? id : campo)?.focus({ preventScroll: true })
      document.getElementById(id)?.scrollIntoView?.({ block: 'nearest' })
    }, 40)
    return () => window.clearTimeout(t)
  }, [alPanel, id, campo])

  // Error del panel: el foco al mensaje sin desplazar, y después el panel entero a la vista (4).
  useEffect(() => {
    if (!falla) return
    const t = window.setTimeout(() => {
      document.getElementById(idFalla)?.focus({ preventScroll: true })
      document.getElementById(id)?.scrollIntoView?.({ block: 'nearest' })
    }, 60)
    return () => window.clearTimeout(t)
  }, [falla, id, idFalla])

  /** Un error de lo que queda: bajo «Envases enteros» en modo envases (7), o bajo el campo único. */
  const errorDeCampo = (texto: string) => {
    if (enEnvases) {
      setErrores({ envases: texto })
      return void enfocar(idEnvases, 0)
    }
    setErrorCampo(texto)
    enfocar(campo, 0)
  }

  /** MATU-84 (3): de sueltos a envases, sin perder lo escrito. El foco al envase si falta (8). */
  const aEnvases = () => {
    const r = repartir(valor, guardado)
    setEnvases(r.envases)
    setSueltos(r.sueltos)
    setEnvaseEscrito('')
    setErrorCampo(null)
    setErrores({})
    setModo('envases')
    enfocar(guardado !== null ? idEnvases : idEnvase, 0)
  }

  /** De envases a sueltos: el total al campo único. El envase escrito aquí, que no se guardó, se descarta (4.2). */
  const aSueltos = () => {
    setValor(juntar(envases, sueltos, u))
    setEnvaseEscrito('')
    setErrorCampo(null)
    setErrores({})
    setModo('sueltos')
    enfocar(campo, 0)
  }

  /** Validación de la pantalla (5.4): el mismo texto que si lo devolviera la API. */
  const validar = (n: number | null): string | null => {
    if (!compre) return n === null ? REGISTRO.errVacioQuedan : n > TOTAL_MAX ? REGISTRO.errTopeQuedan : null
    if (conEnvase) return n === null || n < 1 ? REGISTRO.errVacioEnvases : n > 99 ? REGISTRO.errTopeEnvases : null
    return n === null || n < 1 ? REGISTRO.errVacio : n > 10_000 ? REGISTRO.errTope : null
  }

  /** MATU-84 (7): los errores del modo envases, en el orden del foco: el envase y envases enteros. */
  const validarEnvases = (): { envase?: string; envases?: string } => {
    const e: { envase?: string; envases?: string } = {}
    const nEnvases = entero(envases)
    if (anotaEnvase) {
      const ev = entero(envaseEscrito)
      if (ev === null) {
        if (nEnvases !== null && nEnvases > 0) e.envase = LISTA.errFaltaEnvase
      } else if (envaseValido(envaseEscrito) === null) e.envase = LISTA.errEnvaseRango
    }
    const t = totalDe(envases, sueltos, u)
    if (t === null) e.envases = REGISTRO.errVacioQuedan
    else if (!e.envase && t > TOTAL_MAX) e.envases = EN_ENVASES.errTotal(p.unidad)
    return e
  }

  /** El 422 de la API en el campo de la cantidad, o `null` si va como error del panel. */
  const leer422 = (errores: { campo: string; tipo: string }[]): string | null => {
    const campos = compre ? ['envases', 'cantidad'] : ['stock_unidades']
    for (const e of errores) {
      // El `PATCH` de MATU-84 (D5) puede responder `cobertura_maxima` sin el campo del recuento.
      if (!compre && e.tipo === 'cobertura_maxima') return REGISTRO.errCoberturaQuedan
      if (!campos.includes(e.campo.split('.').pop() ?? e.campo)) continue
      if (e.tipo === 'cobertura_maxima') return compre ? REGISTRO.errCoberturaCompre : REGISTRO.errCoberturaQuedan
      if (e.tipo === 'stock_maximo') return REGISTRO.errStockMaximo(sufijoUnidad)
      if (e.tipo === 'envases_o_cantidad' || e.tipo === 'sin_unidades_por_envase') continue
      if (e.tipo.startsWith('less')) return !compre ? REGISTRO.errTopeQuedan : conEnvase ? REGISTRO.errTopeEnvases : REGISTRO.errTope
      return !compre ? REGISTRO.errVacioQuedan : conEnvase ? REGISTRO.errVacioEnvases : REGISTRO.errVacio
    }
    return null
  }

  const enviar = async () => {
    if (ocupado) return
    setFalla(null)
    let n: number
    let envaseNuevo: number | null = null
    if (enEnvases) {
      const e = validarEnvases()
      setErrores(e)
      if (e.envase) return void enfocar(idEnvase, 0)
      if (e.envases) return void enfocar(idEnvases, 0)
      n = totalDe(envases, sueltos, u)!
      envaseNuevo = anotaEnvase ? u : null
    } else {
      const v = entero(valor)
      const mal = validar(v)
      if (mal) return errorDeCampo(mal)
      setErrorCampo(null)
      n = v!
    }
    setOcupado(true)
    onOcupado(true)
    try {
      // Sin interfaz optimista (5.2): la fila no cambia hasta la respuesta.
      if (compre) {
        const comprado: LoComprado = conEnvase ? { envases: n } : { cantidad: n }
        const r = await anotarCompra(personaId, p.id, p.etag, comprado)
        return onHecho(r, textoHecho(tipo, nombreDe(r) || nombre, n, envase, r))
      }
      // MATU-84 D5: el envase anotado aquí va con lo que queda en un solo `PATCH`. Si no, `recontar`.
      const r = envaseNuevo !== null ? await editarPerfil(personaId, p.id, { stock_unidades: n, unidades_por_envase: envaseNuevo }, p.etag) : await anotarLoQueQueda(personaId, p.id, p.etag, n)
      const hecho = textoHecho(tipo, nombreDe(r) || nombre, n, null, r)
      onHecho(r, envaseNuevo !== null && envaseNuevo > 1 ? { ...hecho, cola: EN_ENVASES.tambienEnvase(envaseNuevo, p.unidad) } : hecho)
    } catch (x) {
      if (esVencida(x)) return
      const permiso = permisoDe(x)
      if (permiso) return onPermiso(permiso)
      const f = leerFallo(x)
      if (f.status === 404) return onNoEncontrado()
      if (f.status === 412) {
        const actual = leerConflictoPerfil(x)
        return setFalla({ texto: REGISTRO.errConflicto(actual?.actualizado_por?.nombre?.trim() || INSUMOS.otraPersona, actual ? nombreDe(actual) : nombre), foco: `insumo-${p.id}` })
      }
      if (f.status === 409 && esTipo(f.tipo, 'perfil-inactivo')) return setFalla({ texto: REGISTRO.errInactivo(nombre), foco: `seguir-${p.id}` })
      if (f.status === 428) return setFalla({ texto: REGISTRO.errFaltaVersion })
      if (f.status === 422) {
        // MATU-84 (4.4): el 422 del envase anotado aquí, bajo su campo.
        if (anotaEnvase && f.errores.some((e) => (e.campo.split('.').pop() ?? e.campo) === 'unidades_por_envase')) {
          setErrores({ envase: LISTA.errEnvaseRango })
          return void enfocar(idEnvase, 0)
        }
        const texto = leer422(f.errores)
        return texto ? errorDeCampo(texto) : setFalla({ texto: REGISTRO.errOtro422 })
      }
      setFalla({ texto: REGISTRO.errRed })
    } finally {
      setOcupado(false)
      onOcupado(false)
    }
  }

  const n = entero(valor)
  // MATU-84 (8): el total va en la descripción de «Anotar lo que queda», sin región viva.
  const hayTotal = enEnvases && totalVisible(envases, sueltos, u) !== null
  return (
    <div
      id={id}
      role="group"
      aria-labelledby={`${campo}-l`}
      tabIndex={-1}
      className="flex scroll-mb-28 flex-col gap-3 border-t border-linea pt-3 outline-none"
      onKeyDown={(e) => {
        if (e.key !== 'Escape' || ocupado) return
        e.stopPropagation()
        onCerrar()
      }}
    >
      <form
        noValidate
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          void enviar()
        }}
      >
        {enEnvases ? (
          <>
            <div className="flex min-w-0 flex-col gap-1.5">
              <p id={`${campo}-l`} className="font-bold">
                {REGISTRO.preguntaQuedan}
              </p>
              <span id={`${campo}-a`} className="text-base text-tenue">
                {EN_ENVASES.ayudaPanel}
              </span>
            </div>
            <BloqueEnvases
              id={campo}
              unidad={p.unidad}
              u={u}
              envases={envases}
              sueltos={sueltos}
              onEnvases={(v) => {
                setEnvases(v)
                setErrores((e) => ({ ...e, envases: undefined }))
              }}
              onSueltos={(v) => {
                setSueltos(v)
                setErrores((e) => ({ ...e, envases: undefined }))
              }}
              error={errores.envases}
              describe={`${campo}-a`}
              soloLectura={ocupado}
              antes={
                anotaEnvase && (
                  <CampoEnvase
                    id={idEnvase}
                    valor={envaseEscrito}
                    onCambio={(v) => {
                      setEnvaseEscrito(v)
                      setErrores((e) => ({ ...e, envase: undefined }))
                    }}
                    sufijo={sufijoUnidad}
                    ayuda={LISTA.envaseAyudaEnvases}
                    error={errores.envase}
                    soloLectura={ocupado}
                  />
                )
              }
            />
          </>
        ) : (
          <div className="flex min-w-0 flex-col gap-1">
            <Stepper
              id={campo}
              etiqueta={compre ? (conEnvase ? REGISTRO.preguntaEnvases : REGISTRO.pregunta(p.unidad)) : REGISTRO.preguntaQuedan}
              ayuda={compre ? REGISTRO.ayudaCompre : REGISTRO.ayudaQuedan}
              sufijo={conEnvase ? sufijoCantidad(n ?? 0, p.unidad, envase) : sufijoUnidad}
              valor={valor}
              onCambio={(v) => {
                setValor(v)
                setErrorCampo(null)
              }}
              min={compre ? 1 : 0}
              max={compre ? (conEnvase ? 99 : 10_000) : TOTAL_MAX}
              error={errorCampo}
              soloLectura={ocupado}
            />
            {contable && (
              <EnlaceModo ocupado={ocupado} onClick={aEnvases}>
                {EN_ENVASES.contarEnvases}
              </EnlaceModo>
            )}
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <Boton type="submit" ocupado={ocupado} textoOcupado={REGISTRO.guardando} aria-describedby={hayTotal ? idTotal : undefined}>
            {compre ? REGISTRO.anotarCompra : REGISTRO.anotarQueda}
          </Boton>
          <Boton variante="secundario" disabled={ocupado} onClick={onCerrar}>
            {REGISTRO.volver}
          </Boton>
        </div>
        {/* 4.1: «Contar sueltos» bajo «Volver», en su propio renglón. */}
        {enEnvases && (
          <EnlaceModo ocupado={ocupado} onClick={aSueltos}>
            {EN_ENVASES.contarSueltos}
          </EnlaceModo>
        )}
      </form>
      {falla && (
        <div id={idFalla} tabIndex={-1} role="alert" className="flex flex-col items-start gap-3 outline-none">
          <MensajeError>{falla.texto}</MensajeError>
          {falla.foco && (
            <Boton variante="secundario" onClick={() => onVerComoQuedo(falla.foco!)}>
              {REGISTRO.verComoQuedo}
            </Boton>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- 3.1 el permiso

/**
 * También lo usa volver a autorizar los insumos (MATU-44 5.2), sin cambiarlo: `antes` pone «Volver a
 * Grupo familiar» arriba, `frase` la frase de estado bajo la bajada y `cargando` reemplaza el
 * formulario mientras llega la vista, con el mismo título (5.1, revisión del 07-11). En Insumos no van (P3).
 */
export function Permiso({
  pila,
  personaId,
  onListo,
  onNoEncontrado,
  antes,
  frase,
  cargando,
}: {
  pila: string
  personaId: string | null
  onListo: (yaVigente: boolean) => void
  onNoEncontrado: () => void
  antes?: ReactNode
  frase?: ReactNode
  cargando?: ReactNode
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
        {antes}
        <p className="text-base text-tenue">{INSUMOS.titulo}</p>
        <Titulo className="text-3xl @2xl/main:text-5xl">{INSUMOS.permisoTitulo}</Titulo>
        <p className="max-w-prose text-lg">{INSUMOS.permisoBajada(pila)}</p>
        {frase}
      </div>
      {cargando ?? (
        <>
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
        <AvisoCuidadorDeHecho
          idTitulo="aviso-consumo-t"
          idError="leido-consumo-e"
          leido={leido}
          error={error === 'leido'}
          onLeido={(v) => {
            setLeido(v)
            setError(null)
          }}
        />
      )}
      {calidad && (
        <Nota tono="rocio" titulo={AUTORIZACION.declaras} iconoEnLinea>
          <p className="max-w-prose">{DECLARACION_CONSUMO[calidad]}</p>
          <LeePoliticaAntesDeAutorizar />
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
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- 3.4 anotar o cambiar

type CampoForm = 'nombre' | 'uso' | 'cada' | 'stock' | 'aviso' | 'envase' | 'envases' | 'sueltos'
// MATU-60 9.1: el envase va al final, al anotar y al cambiar.
const ORDEN_NUEVO: CampoForm[] = ['nombre', 'uso', 'cada', 'stock', 'aviso', 'envase']
const ORDEN_CAMBIAR: CampoForm[] = ['stock', 'uso', 'cada', 'aviso', 'nombre', 'envase']
/** MATU-84 D3 y 8: en modo envases, el envase, envases enteros y sueltos van en el lugar de lo que queda. */
const ordenDe = (nuevo: boolean, enEnvases: boolean): CampoForm[] => {
  const base = nuevo ? ORDEN_NUEVO : ORDEN_CAMBIAR
  if (!enEnvases) return base
  return base.filter((k) => k !== 'envase').flatMap((k): CampoForm[] => (k === 'stock' ? ['envase', 'envases', 'sueltos'] : [k]))
}

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
  // MATU-84 (5.2): la edición de un insumo con envase de más de 1, en unidades o sobres, abre en
  // envases. El alta abre siempre en sueltos (5.1). El modo no se recuerda (3).
  const [modoQueda, setModoQueda] = useState<'sueltos' | 'envases'>(
    perfil && seCuentaEnEnvases(perfil.unidad) && envaseUtil(perfil.unidades_por_envase) !== null ? 'envases' : 'sueltos',
  )
  const [envases, setEnvases] = useState('')
  const [sueltos, setSueltos] = useState('')
  const enEnvases = modoQueda === 'envases' && seCuentaEnEnvases(unidad)
  const uForm = enEnvases ? envaseValido(envase) : null
  // La vista previa y la API usan siempre el total (5.1).
  const stockTotal = enEnvases ? totalDe(envases, sueltos, uForm) : entero(stock)
  const [errores, setErrores] = useState<Partial<Record<CampoForm, string>>>({})
  const [general, setGeneral] = useState<{ titulo?: string; texto: string } | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [conflicto, setConflicto] = useState<Perfil | null>(null)
  const [inactivo, setInactivo] = useState(false)
  const ids: Record<CampoForm, string> = {
    nombre: `${uid}-nombre`,
    uso: `${uid}-uso`,
    cada: `${uid}-cada`,
    stock: `${uid}-stock`,
    aviso: `${uid}-aviso`,
    envase: `${uid}-envase`,
    // MATU-84: los de BloqueEnvases, que los arma desde el id de lo que queda.
    envases: `${uid}-stock-envases`,
    sueltos: `${uid}-stock-sueltos`,
  }
  const orden = ordenDe(nuevo, enEnvases)

  // MATU-67 (G1): lo que cambió desde que se abrió el formulario. «Recargar» del aviso de versión
  // nueva pregunta antes, y «Seguir escribiendo» lleva al primer campo que cambió.
  const { sinGuardar } = useFamilia()
  const valores = { nombre, unidad, frecuencia, cada, uso, stock, aviso, envase, envases, sueltos }
  const iniciales = useRef(valores)
  const actuales = useRef(valores)
  actuales.current = valores
  const ordenRef = useRef(orden)
  ordenRef.current = orden
  useEffect(
    () =>
      registrarSinGuardar(sinGuardar, () => {
        const a = actuales.current
        const i = iniciales.current
        const cambiados = (Object.keys(a) as (keyof typeof a)[]).filter((k) => a[k] !== i[k])
        if (!cambiados.length) return null
        const campo = ordenRef.current.find((k) => cambiados.includes(k))
        // «Anotar un insumo» sin nombre todavía: el título genérico.
        const cual = nuevo ? unaLinea(a.nombre).trim() : perfil ? nombreDe(perfil) : ''
        return { texto: '', titulo: cual ? AVISO_VERSION.sinGuardarInsumo(cual) : null, foco: campo ? ids[campo] : null }
      }),
    // `ids` sale de `uid`, que no cambia.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sinGuardar, nuevo, perfil, uid],
  )

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
    const a = entero(aviso)
    if (a === null || a < 0 || a > 60) e.aviso = INSUMOS.errAviso
    const ev = entero(envase)
    if (enEnvases) {
      // MATU-84 (5.4 y 7): el envase es obligatorio si hay envases enteros, y va de 1 a 10.000.
      const ne = entero(envases)
      if (ev === null) {
        if (ne !== null && ne > 0) e.envase = LISTA.errFaltaEnvase
      } else if (envaseValido(envase) === null) e.envase = LISTA.errEnvaseRango
      // Los dos vacíos: error al anotar, y sin cambio en la edición (5.2).
      if (stockTotal === null) {
        if (nuevo) e.envases = INSUMOS.errStock
      } else if (!e.envase && stockTotal > TOTAL_MAX) e.envases = EN_ENVASES.errTotal(unidad)
      return e
    }
    const s = entero(stock)
    if (s === null && nuevo) e.stock = INSUMOS.errStock
    else if (s !== null && s > 100_000) e.stock = INSUMOS.errStockMax
    // Opcional: vacío no es error (9.3).
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
    if (stockTotal !== null) c.stock_unidades = stockTotal
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
        else if (c === 'stock_unidades') e[enEnvases ? 'envases' : 'stock'] = tipo.startsWith('less') ? INSUMOS.errStockMax : INSUMOS.errStock
        else if (c === 'dias_aviso') e.aviso = INSUMOS.errAviso
        else if (c === 'unidades_por_envase') e.envase = enEnvases ? LISTA.errEnvaseRango : LISTA.errEnvase
        else gen = INSUMOS.errOtro422
      }
      setErrores(e)
      if (gen || !Object.keys(e).length) setGeneral({ texto: gen ?? INSUMOS.errOtro422 })
      const primero = orden.find((k) => e[k])
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
    const primero = orden.find((k) => e[k])
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
          stock_unidades: stockTotal!,
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
  const ayudaStock = perfil ? INSUMOS.stockAyuda(fechaCorta(perfil.stock_medido_en), cantidad(perfil.stock_unidades, perfil.unidad)) : undefined

  /** MATU-84 (3): de sueltos a envases sin perder lo escrito. El foco al envase si falta (8). */
  const aEnvases = () => {
    const u = envaseUtil(envaseValido(envase))
    const r = repartir(stock, u)
    setEnvases(r.envases)
    setSueltos(r.sueltos)
    setStock('')
    setErrores((e) => ({ ...e, stock: undefined }))
    setModoQueda('envases')
    enfocar(u !== null ? ids.envases : ids.envase, 0)
  }
  /** De envases a sueltos: el total al campo único, y el envase escrito se queda al final (5.1). */
  const aSueltos = () => {
    setStock(juntar(envases, sueltos, envaseValido(envase)))
    setEnvases('')
    setSueltos('')
    setErrores((e) => ({ ...e, envases: undefined, envase: undefined }))
    setModoQueda('sueltos')
    enfocar(ids.stock, 0)
  }

  const idAyudaEnvases = `${ids.stock}-ayuda-envases`
  const campoStock = enEnvases ? (
    <fieldset className="flex min-w-0 flex-col gap-4">
      <legend className="mb-1.5 font-bold">{INSUMOS.stock}</legend>
      <span id={idAyudaEnvases} className="text-base text-tenue">
        {ayudaStock ? `${ayudaStock} ${EN_ENVASES.ayudaFormulario}` : EN_ENVASES.ayudaFormulario}
      </span>
      <BloqueEnvases
        id={ids.stock}
        unidad={unidad}
        u={uForm}
        envases={envases}
        sueltos={sueltos}
        onEnvases={setEnvases}
        onSueltos={setSueltos}
        error={errores.envases}
        describe={idAyudaEnvases}
        antes={<CampoEnvase id={ids.envase} valor={envase} onCambio={setEnvase} sufijo={INSUMOS.sufijoStock(unidad)} ayuda={LISTA.envaseAyudaEnvases} error={errores.envase} />}
      />
      <EnlaceModo ocupado={ocupado} onClick={aSueltos}>
        {EN_ENVASES.contarSueltos}
      </EnlaceModo>
    </fieldset>
  ) : (
    <div className="flex min-w-0 flex-col gap-1">
      <Stepper id={ids.stock} etiqueta={INSUMOS.stock} ayuda={ayudaStock} sufijo={INSUMOS.sufijoStock(unidad)} valor={stock} onCambio={setStock} min={0} max={100_000} error={errores.stock} />
      {seCuentaEnEnvases(unidad) && (
        <EnlaceModo ocupado={ocupado} onClick={aEnvases}>
          {EN_ENVASES.contarEnvases}
        </EnlaceModo>
      )}
    </div>
  )
  const campoAviso = (
    <Stepper id={ids.aviso} etiqueta={INSUMOS.aviso} ayuda={INSUMOS.avisoAyuda} sufijo={INSUMOS.sufijoAviso} valor={aviso} onCambio={setAviso} min={0} max={60} error={errores.aviso} />
  )
  // MATU-84 D3: en modo envases, el campo del envase está dentro del bloque de lo que queda, nunca dos veces.
  const campoEnvase = enEnvases ? null : <CampoEnvase id={ids.envase} valor={envase} onCambio={setEnvase} sufijo={INSUMOS.sufijoStock(unidad)} error={errores.envase} />

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
        <VistaPrevia stock={stockTotal} uso={entero(uso)} cada={tasaDias} />
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
function CampoEnvase({
  id,
  valor,
  onCambio,
  sufijo,
  error,
  ayuda = LISTA.envaseAyuda,
  soloLectura = false,
}: {
  id: string
  valor: string
  onCambio: (v: string) => void
  sufijo: string
  error?: string
  /** MATU-84 (7): en modo envases, «Lo guardamos para la próxima vez y para la lista.». */
  ayuda?: string
  soloLectura?: boolean
}) {
  const describe = [`${id}-a`, error ? `${id}-e` : ''].filter(Boolean).join(' ')
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="font-bold">
        {LISTA.envase}
      </label>
      <span id={`${id}-a`} className="text-base text-tenue">
        {ayuda}
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
          readOnly={soloLectura || undefined}
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
  abiertoId,
  onAbrir,
  onCerrar,
  onOcupado,
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
  /** MATU-51 3.6: el panel abierto lo lleva la pantalla, uno solo entre todos. */
  abiertoId: string | null
  onAbrir: (id: string) => void
  onCerrar: (id: string) => void
  onOcupado: (v: boolean) => void
  onReintentar: () => void
  onResuelto: (texto: string) => Promise<void>
  onVerComoQuedo: () => void
  onPermiso: (c: 'sin-consentimiento' | 'revision-vencida') => void
}) {
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
                            aria-controls={`panel-${a.id}`}
                            className="self-end @3xl/main:ms-auto @3xl/main:self-auto"
                            onClick={() => onAbrir(a.id)}
                          >
                            {ALERTAS.boton}
                          </Boton>
                        )}
                      </div>
                      {editor && abierto && (
                        <PanelResolver
                          key={a.id}
                          a={a}
                          personaId={personaId}
                          onCerrar={() => onCerrar(a.id)}
                          onOcupado={onOcupado}
                          onResuelto={onResuelto}
                          onVerComoQuedo={onVerComoQuedo}
                          onPermiso={onPermiso}
                        />
                      )}
                    </li>
                  )
                })}
              </ul>
              <p className="max-w-prose text-base text-tenue">{editor ? ALERTAS.nota : ALERTAS.notaLector}</p>
            </>
          )}
        </section>
      )}
    </>
  )
}

/**
 * El panel de «Ya lo resolví» (MATU-37 3.5, con MATU-51 3.8). Con envase conocido pregunta en
 * envases, con 1 por omisión y de 0 a 99, y el foco va al panel sin abrir el teclado. Sin envase,
 * en la unidad del insumo, vacío y con el foco en el campo. 0 o vacío es «no compré»: va sin cuerpo,
 * porque `cantidad: 0` y `envases: 0` responden 422 (decisión 147).
 */
function PanelResolver({
  a,
  personaId,
  onCerrar,
  onOcupado,
  onResuelto,
  onVerComoQuedo,
  onPermiso,
}: {
  a: PorAcabarse
  personaId: string
  onCerrar: () => void
  onOcupado: (v: boolean) => void
  onResuelto: (texto: string) => Promise<void>
  onVerComoQuedo: () => void
  onPermiso: (c: 'sin-consentimiento' | 'revision-vencida') => void
}) {
  const nombre = nombreDe(a)
  const envase = a.unidades_por_envase ?? null
  const conEnvase = envase !== null
  const panel = `panel-${a.id}`
  const campo = `cantidad-${a.id}`
  const [valor, setValor] = useState(conEnvase ? '1' : '')
  const [ocupado, setOcupado] = useState(false)
  const [falla, setFalla] = useState<ErrorAviso | null>(null)

  // MATU-67 (revisión visual del 09-11): «Recargar» del aviso de versión nueva pregunta antes.
  const { sinGuardar } = useFamilia()
  const valorRef = useRef(valor)
  valorRef.current = valor
  useEffect(
    () =>
      registrarSinGuardar(sinGuardar, () =>
        valorRef.current !== (conEnvase ? '1' : '') ? { texto: '', titulo: AVISO_VERSION.sinGuardarInsumo(nombre), foco: campo } : null,
      ),
    [sinGuardar, conEnvase, nombre, campo],
  )
  const errCantidad = conEnvase ? ALERTAS.errCantidadEnvases : ALERTAS.errCantidad

  useEffect(() => {
    const t = window.setTimeout(() => {
      document.getElementById(conEnvase ? panel : campo)?.focus({ preventScroll: true })
      document.getElementById(panel)?.scrollIntoView?.({ block: 'nearest' })
    }, 40)
    return () => window.clearTimeout(t)
  }, [conEnvase, panel, campo])

  // A 360 px el panel con el error no puede quedar bajo la barra fija: se enfoca el aviso y se
  // desplaza el panel completo (scroll-mb-28 deja el espacio de la barra).
  useEffect(() => {
    if (!falla) return
    const t = window.setTimeout(() => {
      if (falla.tipo !== 'campo') document.getElementById(`falla-${a.id}`)?.focus({ preventScroll: true })
      document.getElementById(panel)?.scrollIntoView?.({ block: 'nearest' })
    }, 60)
    return () => window.clearTimeout(t)
  }, [falla, a.id, panel])

  const errorDeCampo = (texto: string) => {
    setFalla({ texto, tipo: 'campo' })
    enfocar(campo)
  }

  const confirmar = async () => {
    if (ocupado) return
    const n = entero(valor)
    const cant = n === null || n === 0 ? null : n
    if (cant !== null && cant > (conEnvase ? 99 : 10_000)) return errorDeCampo(errCantidad)
    const comprado: LoComprado | null = cant === null ? null : conEnvase ? { envases: cant } : { cantidad: cant }
    setOcupado(true)
    onOcupado(true)
    setFalla(null)
    try {
      // Sin interfaz optimista (4.4): el aviso sigue igual hasta la respuesta.
      const r = await resolverAviso(personaId, a.id, a.etag, comprado)
      const c = cant === null ? null : enPantalla(cantidadEnTexto(cant, a.unidad, envase))
      const texto = c === null ? ALERTAS.okSinCantidad(nombre) : r.dias_restantes > 0 ? ALERTAS.okCantidad(c, nombre, r.dias_restantes) : ALERTAS.okCantidadSinDias(c, nombre)
      await onResuelto(texto)
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
      else if (f.status === 422) {
        // MATU-51 3.8: los topes que solo sabe la API llevan el texto de «Compré».
        const tipos = f.errores.map((e) => e.tipo)
        errorDeCampo(
          tipos.includes('stock_maximo') ? REGISTRO.errStockMaximo(INSUMOS.sufijoStock(a.unidad)) : tipos.includes('cobertura_maxima') ? REGISTRO.errCoberturaCompre : errCantidad,
        )
      } else setFalla({ texto: ALERTAS.errRed, tipo: 'general' })
    } finally {
      setOcupado(false)
      onOcupado(false)
    }
  }

  const n = entero(valor)
  return (
    <div
      id={panel}
      role="group"
      aria-labelledby={`${campo}-l`}
      tabIndex={-1}
      className="mt-3 flex scroll-mb-28 flex-col gap-3 border-t border-linea pt-3 outline-none"
      onKeyDown={(e) => {
        if (e.key !== 'Escape' || ocupado) return
        e.stopPropagation()
        onCerrar()
      }}
    >
      <div className="flex flex-col gap-3 @3xl/main:flex-row @3xl/main:flex-wrap @3xl/main:items-end @3xl/main:gap-4">
        <Stepper
          id={campo}
          etiqueta={conEnvase ? ALERTAS.preguntaEnvases : ALERTAS.pregunta(a.unidad)}
          ayuda={conEnvase ? ALERTAS.ayudaEnvases : ALERTAS.ayuda}
          sufijo={conEnvase ? sufijoCantidad(n ?? 0, a.unidad, envase) : a.unidad === 'sobre' ? 'sobres' : a.unidad === 'unidad' ? undefined : a.unidad}
          valor={valor}
          onCambio={(v) => {
            setValor(v)
            if (falla?.tipo === 'campo') setFalla(null)
          }}
          // 3.8: con envase el − baja hasta 0, que es «no compré» (aprobado por Jorge).
          min={conEnvase ? 0 : 1}
          max={conEnvase ? 99 : 10_000}
          error={falla?.tipo === 'campo' ? falla.texto : null}
          soloLectura={ocupado}
        />
        <div className="flex flex-wrap gap-3 angosto:flex-col angosto:items-stretch">
          <Boton id={`confirmar-${a.id}`} className="angosto:w-full" aria-label={ALERTAS.botonDe(nombre)} ocupado={ocupado} textoOcupado={ALERTAS.guardando} onClick={() => void confirmar()}>
            {ALERTAS.boton}
          </Boton>
          <Boton variante="secundario" className="angosto:w-full" disabled={ocupado} onClick={onCerrar}>
            {ALERTAS.volver}
          </Boton>
        </div>
      </div>
      {falla && falla.tipo !== 'campo' && (
        <div id={`falla-${a.id}`} tabIndex={-1} role="alert" className="flex flex-col items-start gap-3 outline-none">
          <MensajeError>{falla.texto}</MensajeError>
          {falla.tipo === 'cerrado' && (
            <Boton variante="secundario" onClick={onVerComoQuedo}>
              {ALERTAS.verComoQuedo}
            </Boton>
          )}
        </div>
      )}
    </div>
  )
}
