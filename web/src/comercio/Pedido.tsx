// Un pedido (especificación MATU-63, sección 6): la parte elegida, con sus productos y la única
// acción que sigue. Nunca muestra de quién es, a dónde va, montos ni el código. Las marcas se
// guardan al elegir (interfaz optimista: se pueden cambiar hasta «Listo para retirar» y no mueven
// dinero, O4); empezar, terminar y el código esperan la respuesta.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, PackageX, TriangleAlert } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  marcarLinea,
  marcarLista,
  prepararParte,
  verParte,
  type LineaComercio,
  type ParteResumen,
  type ParteVista,
  type SolicitudMarca,
} from '../compartido/api/comercio'
import { esVencida } from '../compartido/api/sesion'
import { Anunciado, anunciar } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { navegar } from '../familia/ruteo'
import { Acciones, Etiqueta, GrupoOpciones, MensajeError, Stepper, Titulo, Volver } from '../familia/ui'
import { CampoCodigo, CIERRA, ID_RESULTADO, NotaResultado, type Resultado } from './Codigo'
import { CantidadProducto, enCurso, ETIQUETA_ESTADO, faltanDe, horaChile, IconoEstado, plazo } from './comun'
import { useComercio } from './estado'
import { RotuloPiloto } from './Marco'
import { CODIGO_RETIRO, PEDIDO_COMERCIO as T, PEDIDOS } from './textos'

type Marca = { estado: 'preparada' | 'faltante'; faltan: number } | null
type Fallo = 'red' | 'no-esta'

const marcaDe = (l: LineaComercio): Marca =>
  l.estado_linea === 'preparada' ? { estado: 'preparada', faltan: 0 } : l.estado_linea === 'faltante' || l.estado_linea === 'devuelta' ? { estado: 'faltante', faltan: faltanDe(l) } : null
const marcasDe = (p: ParteVista) => Object.fromEntries(p.lineas.map((l) => [l.id, marcaDe(l)])) as Record<string, Marca>
const idLinea = (id: string) => `linea-${id}`
const ID_PRODUCTOS = 'productos-del-pedido'
const ID_NOTA_ESTADO = 'nota-del-pedido'

const ID_MARCA_CADA = 'marca-cada-producto'
const RADIO = 'input[type="radio"]'

/** El estado inicial de la revisión del código al abrir una parte `lista` (7.3, «Al abrir…»). */
function resultadoAlAbrir(p: ParteVista): Resultado | null {
  if (p.estado !== 'lista') return null
  if (p.estado_codigo === 'bloqueado' || p.estado_codigo === 'vencido' || p.estado_codigo === 'usado' || p.estado_codigo === 'sin_codigo')
    return { tipo: p.estado_codigo, intentos: 0, lineas: p.lineas, vivo: false, n: 0 }
  return null
}

export function DetallePedido({
  parteId,
  resumen,
  ahora,
  onCambio,
}: {
  parteId: string
  /** La fila de la lista, para saber si la parte cambió desde afuera (5.5). */
  resumen: ParteResumen | undefined
  ahora: () => Date
  /** La parte cambió por una acción de aquí: la lista la actualiza sin esperar al minuto. */
  onCambio: (p: ParteVista) => void
}) {
  const { contacto, quedoInactiva, fijar } = useComercio()
  const [parte, setParte] = useState<ParteVista | null>(null)
  const [fallo, setFallo] = useState<Fallo | null>(null)
  const [nota, setNota] = useState<'cambio' | 'listo' | null>(null)
  const [marcas, setMarcas] = useState<Record<string, Marca>>({})
  const [guardando, setGuardando] = useState<Record<string, boolean>>({})
  const [errorLinea, setErrorLinea] = useState<Record<string, boolean>>({})
  const [sinMarcar, setSinMarcar] = useState<string | null>(null)
  const [errorAccion, setErrorAccion] = useState(false)
  const [ocupado, setOcupado] = useState<'empezar' | 'listo' | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const etag = useRef<string | null>(null)
  const cola = useRef<Promise<void>>(Promise.resolve())
  const relojes = useRef<Record<string, number>>({})
  const verCargando = useDemora(1000)
  /** P1-3: «Avisar que no tengo ninguno» acaba de cancelar la parte: la nota se anuncia. */
  const [recienSinNinguno, setRecienSinNinguno] = useState(false)
  /** P2-7: cada «Listo para retirar» con una línea sin marcar vuelve a anunciar el mensaje. */
  const [intentoListo, setIntentoListo] = useState(0)

  /**
   * P1 de la revisión visual: el foco va a un elemento cuando ya está montado. Un `setTimeout` corría
   * antes de que React pintara la nota (o con el botón ya desmontado), y el foco caía en `body`.
   * El efecto corre después de cada render y espera hasta que el elemento exista.
   */
  const [foco, setFoco] = useState<{ id: string; selector?: string } | null>(null)
  const pedirFoco = (id: string, selector?: string) => setFoco({ id, selector })
  useEffect(() => {
    if (!foco) return
    const el = document.getElementById(foco.id)
    const objetivo = foco.selector ? el?.querySelector<HTMLElement>(foco.selector) : el
    if (!objetivo) return
    objetivo.focus()
    setFoco(null)
  })

  const mostrar = useCallback((p: ParteVista, version: string | null) => {
    etag.current = version
    setParte(p)
    setMarcas(marcasDe(p))
    setResultado(resultadoAlAbrir(p))
  }, [])

  /** Un fallo de una acción o de la carga: devuelve `true` si ya se resolvió aquí. */
  const comun = useCallback(
    (x: unknown): boolean => {
      if (esVencida(x)) return true
      const f = leerFallo(x)
      if (f.status === 403) return quedoInactiva(), true
      if (f.status === 404) return setFallo('no-esta'), true
      return false
    },
    [quedoInactiva],
  )

  const cargar = useCallback(
    async (motivo: 'abrir' | 'cambio' | 'afuera'): Promise<ParteVista | null> => {
      try {
        const r = await verParte(parteId)
        mostrar(r.parte, r.etag)
        setFallo(null)
        onCambio(r.parte)
        if (motivo === 'cambio') setNota(r.parte.estado === 'cancelada' ? null : 'cambio')
        return r.parte
      } catch (x) {
        if (!comun(x) && motivo === 'abrir') setFallo('red')
        return null
      }
    },
    [parteId, mostrar, onCambio, comun],
  )

  useEffect(() => {
    setParte(null)
    setFallo(null)
    setNota(null)
    setSinMarcar(null)
    setErrorAccion(false)
    setErrorLinea({})
    setRecienSinNinguno(false)
    setFoco(null)
    void cargar('abrir').then((p) => {
      // P1-1: si el foco quedó en el cuerpo (la fila elegida se desmontó en el teléfono), vuelve al `h1`.
      if (p && (document.activeElement === document.body || !document.activeElement)) setFoco({ id: 'titulo-pagina' })
    })
    const r = relojes.current
    return () => Object.values(r).forEach((t) => window.clearTimeout(t))
    // Solo al elegir otra parte.
  }, [parteId])

  // 5.5: la lista trae la parte en otro estado (se canceló, u operación generó un código nuevo).
  const estadoAfuera = resumen ? `${resumen.estado}:${resumen.estado_codigo}` : null
  useEffect(() => {
    if (!parte || !resumen || ocupado) return
    if (resumen.estado === parte.estado && resumen.estado_codigo === parte.estado_codigo) return
    if (resumen.estado === 'cancelada' && parte.estado !== 'cancelada') {
      // 5.5: se anuncia una vez, con la referencia; la nota de 6.8 se ve sin repetirlo.
      anunciar(PEDIDOS.seCancelo(parte.referencia), 'alert')
    }
    void cargar('afuera')
  }, [estadoAfuera])

  /** 409 o 412: se vuelve a pedir la parte y se dice que cambió (6.9). */
  const conflicto = (x: unknown): boolean => {
    const s = leerFallo(x).status
    if (s !== 409 && s !== 412) return false
    void cargar('cambio')
    return true
  }

  // ------------------------------------------------ acciones

  const empezar = async () => {
    if (!parte) return
    setErrorAccion(false)
    setNota(null)
    setOcupado('empezar')
    try {
      const r = await prepararParte(parte.id, etag.current)
      mostrar(r.parte, r.etag)
      onCambio(r.parte)
      pedirFoco(ID_PRODUCTOS)
    } catch (x) {
      if (!comun(x) && !conflicto(x)) setErrorAccion(true)
    } finally {
      setOcupado(null)
    }
  }

  /** Guarda una marca en orden, con la versión que dejó la anterior. */
  const guardarMarca = (linea: LineaComercio, marca: SolicitudMarca, antes: Marca) => {
    setGuardando((g) => ({ ...g, [linea.id]: true }))
    cola.current = cola.current.then(async () => {
      try {
        const r = await marcarLinea(parteId, linea.id, marca, etag.current)
        etag.current = r.etag
        setParte(r.parte)
        onCambio(r.parte)
      } catch (x) {
        if (comun(x) || conflicto(x)) return
        setMarcas((m) => ({ ...m, [linea.id]: antes }))
        setErrorLinea((e) => ({ ...e, [linea.id]: true }))
      } finally {
        setGuardando((g) => ({ ...g, [linea.id]: false }))
      }
    })
  }

  const elegir = (linea: LineaComercio, estado: 'preparada' | 'faltante') => {
    const antes = marcas[linea.id] ?? null
    if (antes?.estado === estado) return
    window.clearTimeout(relojes.current[linea.id])
    const nueva: Marca = estado === 'preparada' ? { estado, faltan: 0 } : { estado, faltan: linea.cantidad }
    setMarcas((m) => ({ ...m, [linea.id]: nueva }))
    setErrorLinea((e) => ({ ...e, [linea.id]: false }))
    if (sinMarcar === linea.id) setSinMarcar(null)
    guardarMarca(linea, estado === 'preparada' ? { estado } : { estado, unidades_faltantes: linea.cantidad }, antes)
  }

  /** El `Stepper` guarda 800 ms después del último toque. */
  const cambiarFaltan = (linea: LineaComercio, faltan: number) => {
    const antes = marcas[linea.id] ?? null
    setMarcas((m) => ({ ...m, [linea.id]: { estado: 'faltante', faltan } }))
    window.clearTimeout(relojes.current[linea.id])
    relojes.current[linea.id] = window.setTimeout(() => {
      delete relojes.current[linea.id]
      guardarMarca(linea, { estado: 'faltante', unidades_faltantes: faltan }, antes)
    }, 800)
  }

  const terminar = async () => {
    if (!parte) return
    setErrorAccion(false)
    setNota(null)
    // 6.4: con una línea sin marcar no envía; el foco va a su primera opción.
    const falta = parte.lineas.find((l) => !marcas[l.id])
    if (falta) {
      setSinMarcar(falta.id)
      setIntentoListo((n) => n + 1)
      return pedirFoco(idLinea(falta.id), RADIO)
    }
    setSinMarcar(null)
    setOcupado('listo')
    // Lo que el `Stepper` tenía por guardar se guarda ahora, y se espera a la cola.
    for (const [lineaId, t] of Object.entries(relojes.current)) {
      window.clearTimeout(t)
      delete relojes.current[lineaId]
      const l = parte.lineas.find((x) => x.id === lineaId)
      const m = marcas[lineaId]
      if (l && m?.estado === 'faltante') guardarMarca(l, { estado: 'faltante', unidades_faltantes: m.faltan }, m)
    }
    await cola.current
    try {
      const r = await marcarLista(parte.id, etag.current)
      mostrar(r.parte, r.etag)
      onCambio(r.parte)
      if (r.parte.estado === 'lista') setNota('listo')
      if (r.parte.estado === 'cancelada') setRecienSinNinguno(true)
      // P1-2 y P1-3: a la nota de «listo» o a la de cancelado (O3), cuando ya está montada.
      pedirFoco(ID_NOTA_ESTADO)
    } catch (x) {
      if (comun(x) || conflicto(x)) return
      const f = leerFallo(x)
      if (f.status === 422 && f.tipo?.endsWith('lineas-pendientes')) {
        // Otra persona dejó una línea sin marcar: la misma ayuda de 6.4, con la parte al día.
        const p = await cargar('afuera')
        const pendiente = p?.lineas.find((l) => !marcaDe(l))
        if (pendiente) {
          setSinMarcar(pendiente.id)
          setIntentoListo((n) => n + 1)
          pedirFoco(idLinea(pendiente.id), RADIO)
        }
        return
      }
      setErrorAccion(true)
    } finally {
      setOcupado(null)
    }
  }

  // ------------------------------------------------ vista

  const volver = () => {
    fijar({ parteId: null })
    navegar('/comercio')
  }

  const referencia = parte?.referencia ?? resumen?.referencia ?? null
  const etiqueta = parte ? ETIQUETA_ESTADO[parte.estado] : null
  const elPlazo = parte ? plazo(parte.preparar_antes_de, ahora()) : null
  const todosFaltan = !!parte && parte.lineas.length > 0 && parte.lineas.every((l) => marcas[l.id]?.estado === 'faltante')
  // Decisión 430: «no tenía ninguno» lo dice la API; sin el campo, se deduce de las marcas.
  const sinNinguno = parte?.motivo_cancelacion !== undefined ? parte.motivo_cancelacion === 'producto_faltante' : todosFaltan
  const campoVisible = !!parte && parte.estado === 'lista' && parte.estado_codigo === 'vigente' && (!resultado || !CIERRA.has(resultado.tipo))
  const conCodigo = !!parte && (parte.estado === 'lista' || resultado !== null)
  // 7.3 (P2-9): si el código dijo «cancelado», se ve solo esa nota, sin la de 6.8.
  const canceladaPorCodigo = resultado?.vivo === true && resultado.tipo === 'cancelada'
  // v1.1 (7.3): con «ya retirado», tampoco la de 6.7.
  const retiradaPorCodigo = resultado?.vivo === true && resultado.tipo === 'usado'

  return (
    <div className="flex flex-col gap-6" aria-busy={!parte && !fallo ? true : undefined}>
      {/* 6.1 y 6.2: la cabecera. Un solo `h1`, que no se desmonta al llegar la parte (P1-1). */}
      <div className="flex flex-col gap-3">
        <div className="@3xl/main:hidden">
          <Volver onClick={volver}>{T.volver}</Volver>
        </div>
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="flex min-w-0 flex-col items-start gap-2">
            <Titulo className="text-3xl">
              {referencia ? (
                <>
                  {PEDIDOS.pedido} <span className="digitos">{referencia}</span>
                </>
              ) : (
                PEDIDOS.titulo
              )}
            </Titulo>
            {parte && etiqueta && (
              <Etiqueta tono={etiqueta.tono}>
                <IconoEstado estado={parte.estado} enEtiqueta />
                {etiqueta.texto}
              </Etiqueta>
            )}
          </div>
          {parte && elPlazo && (
            <div className="flex flex-col gap-1">
              {enCurso(parte.estado) &&
                (elPlazo.atrasada ? (
                  <p className="flex items-start gap-1.5 font-bold text-atenta @3xl/main:text-lg">
                    <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0" />
                    <span className="cifras whitespace-normal">{elPlazo.texto}</span>
                  </p>
                ) : (
                  <p className="cifras whitespace-normal @3xl/main:text-lg @3xl/main:font-bold">{elPlazo.texto}</p>
                ))}
              <p className="text-base text-tenue">
                <span className="cifras whitespace-normal">{T.llego(horaChile(parte.enviado_en))}</span> · {PEDIDOS.productos(parte.lineas.length)}
              </p>
            </div>
          )}
        </div>
      </div>

      {fallo === 'no-esta' && (
        <div className="flex flex-col items-start gap-4">
          <Nota tono="atenta">{T.yaNoEsta}</Nota>
          <Boton variante="secundario" onClick={volver}>
            {T.volver}
          </Boton>
        </div>
      )}
      {fallo === 'red' && !parte && (
        <div className="flex flex-col items-start gap-4">
          <Nota tono="pronto" rol="alert">
            {T.error}
          </Nota>
          <Boton variante="secundario" onClick={() => void cargar('abrir')}>
            {PEDIDOS.volverAIntentar}
          </Boton>
        </div>
      )}
      {!parte && !fallo && <p className="text-tenue">{verCargando ? T.cargando : ''}</p>}

      {parte && fallo !== 'no-esta' && (
        <>
          {/* 6.9: la parte cambió mientras se veía. */}
          {nota === 'cambio' && (
            <Nota tono="atenta" rol="status">
              {T.cambio}
            </Nota>
          )}

          <section aria-labelledby={ID_PRODUCTOS} className="flex flex-col gap-3">
            <div>
              <h2 id={ID_PRODUCTOS} tabIndex={-1} className="text-xl font-bold outline-none">
                {T.productosTitulo}
              </h2>
              {parte.estado === 'preparando' && <p className="text-base text-tenue">{T.marca}</p>}
            </div>
            {parte.estado === 'preparando' ? (
              <ul className="flex flex-col gap-3 @3xl/main:gap-0 @3xl/main:divide-y @3xl/main:divide-linea">
                {parte.lineas.map((l) => (
                  <li key={l.id}>
                    <LineaPorMarcar
                      linea={l}
                      marca={marcas[l.id] ?? null}
                      guardando={!!guardando[l.id]}
                      error={!!errorLinea[l.id]}
                      sinMarcar={sinMarcar === l.id}
                      onElegir={(e) => elegir(l, e)}
                      onFaltan={(n) => cambiarFaltan(l, n)}
                    />
                  </li>
                ))}
              </ul>
            ) : (
              <LineasSoloLectura parte={parte} />
            )}
            {parte.estado === 'enviada' && <p className="text-tenue">{T.tocaEmpezar}</p>}
          </section>

          {/* 6.3: una sola acción principal por estado. */}
          {parte.estado === 'enviada' && (
            <div className="flex flex-col gap-3">
              {errorAccion && <MensajeError>{T.error}</MensajeError>}
              <Acciones>
                <Boton ocupado={ocupado === 'empezar'} textoOcupado={T.empezando} onClick={() => void empezar()}>
                  {T.empezar}
                </Boton>
              </Acciones>
            </div>
          )}
          {parte.estado === 'preparando' && (
            <div className="flex flex-col gap-3">
              <p className="max-w-prose text-base text-tenue">{T.despuesDeListo}</p>
              {/* P2-7: se anuncia por la región urgente en cada intento, y describe la línea sin marcar. */}
              {sinMarcar && (
                <Anunciado key={intentoListo} urgencia="alert" id={ID_MARCA_CADA}>
                  <MensajeError>{T.marcaCada}</MensajeError>
                </Anunciado>
              )}
              {errorAccion && <MensajeError>{T.error}</MensajeError>}
              <Acciones>
                <Boton ocupado={ocupado === 'listo'} textoOcupado={T.guardando} onClick={() => void terminar()}>
                  {todosFaltan ? T.ningunoBoton : T.listo}
                </Boton>
              </Acciones>
            </div>
          )}
          {parte.estado === 'lista' && nota === 'listo' && (
            <Nota id={ID_NOTA_ESTADO} enfocable tono="ok" rol="status" titulo={T.listoTitulo}>
              {T.listoTexto}
            </Nota>
          )}

          {conCodigo && (
            <section aria-labelledby="titulo-codigo" className="flex flex-col gap-4">
              <h2 id="titulo-codigo" className="text-xl font-bold">
                {CODIGO_RETIRO.titulo}
              </h2>
              {resultado && <NotaResultado key={resultado.n} r={resultado} referencia={parte.referencia} contacto={contacto} retiradaEn={parte.retirada_en} />}
              {campoVisible && (
                <CampoCodigo
                  parte={parte}
                  resultado={resultado}
                  onInactiva={quedoInactiva}
                  onResultado={(r, p) => {
                    setResultado(r)
                    if (p) {
                      setParte(p)
                      onCambio(p)
                    }
                    // P1-4 y P2-8: a la nota, cuando ya está montada (y el campo, si se va, desmontado).
                    pedirFoco(ID_RESULTADO)
                  }}
                />
              )}
            </section>
          )}

          {parte.estado === 'retirada' && !retiradaPorCodigo && (
            <Nota id={ID_NOTA_ESTADO} tono="ok" titulo={T.retiradoTitulo}>
              {parte.retirada_en ? <span className="cifras whitespace-normal">{T.retiradoTexto(horaChile(parte.retirada_en))}</span> : undefined}
            </Nota>
          )}
          {parte.estado === 'cancelada' && !canceladaPorCodigo && (
            <Nota id={ID_NOTA_ESTADO} enfocable tono="pronto" borde titulo={T.canceladoTitulo} rol={recienSinNinguno ? 'status' : undefined}>
              {sinNinguno ? T.canceladoNinguno : T.canceladoTexto}
            </Nota>
          )}
        </>
      )}

      {/* 6.2: en el detalle ancho, el rótulo queda al pie de la cola y no se repite aquí. */}
      <div className="@3xl/main:hidden">
        <RotuloPiloto texto={PEDIDOS.rotuloPedidos} />
      </div>
    </div>
  )
}

/** 6.4: la línea por marcar, con «Lo tengo» y «No lo tengo». */
function LineaPorMarcar({
  linea,
  marca,
  guardando,
  error,
  sinMarcar,
  onElegir,
  onFaltan,
}: {
  linea: LineaComercio
  marca: Marca
  guardando: boolean
  error: boolean
  sinMarcar: boolean
  onElegir: (e: 'preparada' | 'faltante') => void
  onFaltan: (n: number) => void
}) {
  const id = idLinea(linea.id)
  const falta = marca?.estado === 'faltante'
  return (
    <GrupoOpciones<'preparada' | 'faltante'>
      id={id}
      nombre={id}
      forma="chips"
      ocupado={guardando}
      describe={[falta ? `${id}-nota` : '', sinMarcar ? ID_MARCA_CADA : ''].filter(Boolean).join(' ') || undefined}
      leyendaDentro
      claseGrupo={`gap-3 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ${
        sinMarcar ? 'ring-2 ring-pronto @3xl/main:-mx-3 @3xl/main:px-3' : 'ring-1 ring-linea @3xl/main:rounded-none @3xl/main:bg-transparent @3xl/main:px-0 @3xl/main:ring-0'
      }`}
      leyenda={
        <>
          <span className="block">
            <CantidadProducto linea={linea} />
          </span>
          <span className="block font-normal text-tenue">{linea.producto.presentacion}</span>
        </>
      }
      valor={marca?.estado ?? null}
      onCambio={onElegir}
      opciones={[
        { valor: 'preparada', texto: T.loTengo },
        { valor: 'faltante', texto: T.noLoTengo },
      ]}
    >
      {falta && (
        <>
          <Nota id={`${id}-nota`} tono="atenta" borde iconoEnLinea>
            {T.noLoCambies}
          </Nota>
          {linea.cantidad > 1 && <Stepper etiqueta={T.cuantosFaltan} valor={marca.faltan} min={1} max={linea.cantidad} onCambio={onFaltan} ayuda={T.pedidoLleva(linea.cantidad)} />}
        </>
      )}
      {error && <MensajeError>{T.noPudimosGuardar}</MensajeError>}
    </GrupoOpciones>
  )
}

/** 6.5: las líneas en solo lectura. Desde `lista`, con lo marcado; cancelada, sin marcas. */
function LineasSoloLectura({ parte }: { parte: ParteVista }) {
  const conMarca = parte.estado === 'lista' || parte.estado === 'retirada'
  return (
    <ul className="divide-y divide-linea border-y border-linea">
      {parte.lineas.map((l) => {
        const faltan = faltanDe(l)
        return (
          <li key={l.id} className="flex flex-col items-start gap-1 py-3">
            <span className="font-bold">
              <CantidadProducto linea={l} />
            </span>
            <span className="text-tenue">{l.producto.presentacion}</span>
            {conMarca &&
              (l.estado_linea === 'preparada' ? (
                <Etiqueta tono="ok">
                  <Check aria-hidden className="size-4 shrink-0" strokeWidth={3} />
                  {T.loTengo}
                </Etiqueta>
              ) : faltan > 0 ? (
                <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Etiqueta>
                    <PackageX aria-hidden className="size-4 shrink-0" />
                    {T.noLoTengo}
                  </Etiqueta>
                  {faltan < l.cantidad && <span className="cifras whitespace-normal text-base">{T.faltanDe(faltan, l.cantidad)}</span>}
                </span>
              ) : null)}
          </li>
        )
      })}
    </ul>
  )
}
