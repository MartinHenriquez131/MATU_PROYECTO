// La vuelta de Webpay y el comprobante (MATU-62, especificación docs/diseno/matu-62-pago.md v1.0,
// secciones 2, 7 y 8; ADR-027). Una ruta, `/insumos/pedido/pago`, que es también la `return_url`:
// - desde Webpay, con los valores de Transbank que main.tsx ya leyó y borró de la dirección
//   (vueltaPago.ts): «Estamos confirmando tu pago», `POST /v1/pagos/retorno` y el resultado;
// - desde «Ver el comprobante», con el pago en la memoria de la página;
// - al recargar, sin nada: el último pedido pagado de la persona, o «Tu pedido».
//
// Sin interfaz optimista: cada estado es lo que respondió el servidor. Los montos vienen del
// servidor y la pantalla no calcula el total. Nada del pago va a la URL ni al almacenamiento del
// navegador. Sin animación de espera ni cuenta regresiva: el texto dice qué pasa.
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Check, CircleCheck, Clock, CloudOff, CreditCard, FileText, Info, Printer, ReceiptText, Undo2 } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { confirmarPedido, esVistaCompleta, leerPedidoEnCurso, type PedidoVista } from '../compartido/api/pedido'
import {
  enviarRetorno,
  esPagoCompleto,
  leerPago,
  leerPedidoPagado,
  type Comprobante,
  type Devolucion,
  type Pago,
  type PagoVista,
  type ResultadoRetorno,
} from '../compartido/api/pago'
import { esVencida } from '../compartido/api/sesion'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { anunciar, Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { useFamilia } from './estado'
import { useDemora } from './Estados'
import { enfocar, esTipo } from './insumosComun'
import { PestanasInsumos } from './Insumos'
import { AvisoPiloto, Baldosa, horaDeVencimiento, type TonoBaldosa } from './PiezasPedido'
import { navegar } from './ruteo'
import { GENERAL } from './textos'
import { pesos } from './textosCatalogo'
import { PAGO } from './textosPago'
import { PEDIDO } from './textosPedido'
import { Acciones, Etiqueta, Nota, Titulo } from './ui'
import { guardarResultado, leerVuelta, marcarFijada, olvidarComprobante, olvidarVuelta, RUTA_PAGO, tomarComprobante } from './vueltaPago'

const RUTA_PEDIDO = '/insumos/pedido'
const RUTA_RESUMEN = '/insumos/pedido/resumen'
/** 7.3: sin respuesta en 10 segundos, la nota de que tarda. */
const TARDA_MS = 10_000
/** 7.3: pregunta sola cada 15 segundos (o lo que diga `volver_a_preguntar_en`) mientras se ve la pantalla… */
const CADA_S = 15
/** …y hasta 15 minutos después de volver de Webpay. Después queda «Revisar ahora». */
const HASTA_MS = 15 * 60_000

/** La condición de la página pública, con la versión aceptada (P4, decisión 240). */
export const enlaceCondiciones = (version: string) => `/condiciones-pedido?version=${encodeURIComponent(version)}`

const fecha = (iso: string) => fechaYHoraDeChile(new Date(iso))

// ---------------------------------------------------------------- la vuelta: preguntar y volver a preguntar

type FaseVuelta = 'esperando' | 'tarda' | 'listo' | 'desconocido'

/**
 * `POST /v1/pagos/retorno` con lo que trajo la dirección, y lo que la pantalla necesita de él: si
 * todavía espera (7.2), si tarda (7.3: `pendiente`, 10 segundos sin respuesta o sin red) o si hay
 * resultado. Mientras tarda, vuelve a preguntar sola, solo con la pantalla visible y hasta 15
 * minutos después de volver. El retorno es idempotente por token: repetirlo no cobra dos veces.
 */
function useVuelta(activa: boolean) {
  const inicial = activa ? leerVuelta() : null
  const [fase, setFase] = useState<FaseVuelta>(() => (!inicial?.resultado ? 'esperando' : inicial.resultado.resultado === 'pendiente' ? 'tarda' : 'listo'))
  const [resultado, setResultado] = useState<ResultadoRetorno | null>(() => inicial?.resultado ?? null)
  const [revisando, setRevisando] = useState(false)
  const [esperaS, setEsperaS] = useState(CADA_S)
  const enVuelo = useRef(false)
  const faseRef = useRef(fase)
  faseRef.current = fase

  const preguntar = useCallback(async (manual: boolean) => {
    const v = leerVuelta()
    if (!v || enVuelo.current) return
    enVuelo.current = true
    if (manual) setRevisando(true)
    const tarda = window.setTimeout(() => {
      if (faseRef.current === 'esperando') setFase('tarda')
    }, TARDA_MS)
    try {
      const r = await enviarRetorno(v.cuerpo)
      guardarResultado(r)
      setResultado(r)
      if (r.resultado === 'pendiente') {
        setEsperaS(r.volver_a_preguntar_en ?? CADA_S)
        if (faseRef.current === 'tarda' && manual) anunciar(PAGO.sigueSinRespuesta, 'status')
        setFase('tarda')
      } else setFase('listo')
    } catch (x) {
      const f = leerFallo(x)
      // 404: los valores no son de ninguna venta de MATU. 422: no traía nada válido. No hay nada que confirmar.
      if (f.status === 404 || f.status === 422) setFase('desconocido')
      else {
        if (faseRef.current === 'tarda' && manual) anunciar(PAGO.sigueSinRespuesta, 'status')
        setFase('tarda')
      }
    } finally {
      window.clearTimeout(tarda)
      enVuelo.current = false
      if (manual) setRevisando(false)
    }
  }, [])

  // La primera vez, al llegar.
  useEffect(() => {
    if (activa && fase === 'esperando') void preguntar(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 7.3: «Te avisamos aquí» se cumple preguntando sola, sin decirlo y sin números que cambien.
  useEffect(() => {
    if (!activa || fase !== 'tarda') return
    let reloj: number | undefined
    const programar = () => {
      window.clearTimeout(reloj)
      const v = leerVuelta()
      if (!v || Date.now() - v.llegada > HASTA_MS) return
      reloj = window.setTimeout(() => {
        if (document.visibilityState === 'visible') void preguntar(false).finally(programar)
      }, esperaS * 1000)
    }
    const alVolver = () => {
      if (document.visibilityState === 'visible') programar()
    }
    programar()
    document.addEventListener('visibilitychange', alVolver)
    return () => {
      window.clearTimeout(reloj)
      document.removeEventListener('visibilitychange', alVolver)
    }
  }, [activa, fase, esperaS, preguntar])

  return { fase, resultado, revisando, revisar: () => void preguntar(true) }
}

// ---------------------------------------------------------------- la pantalla

type Vista =
  | { tipo: 'cargando' }
  | { tipo: 'comprobante'; pago: PagoVista & { comprobante: Comprobante }; yaRegistrado: boolean }
  | { tipo: 'no-se-hizo'; resultado: 'no_aprobado' | 'abandonado' | 'tiempo_agotado'; pedido: PedidoVista | null }
  | { tipo: 'anulado'; anulacion: 'hecha' | 'en_curso'; devolucion: Devolucion; pagoDePrueba: boolean }
  | { tipo: 'sin-sesion'; resultado: ResultadoRetorno }
  | { tipo: 'error'; titulo: string | null }

const conComprobante = (p: PagoVista): p is PagoVista & { comprobante: Comprobante } => p.comprobante !== null

/** La anulación de un pago tardío (regla 3 de D-62-4), la más reciente. */
const anulacionTardia = (p: PagoVista) => [...p.devoluciones].filter((d) => d.motivo === 'pago_tardio').sort((a, b) => a.solicitada_en.localeCompare(b.solicitada_en)).pop() ?? null

export function PantallaPago() {
  const { personaId, grupoId, rol, elegir } = useFamilia()
  const [conVuelta] = useState(() => leerVuelta() !== null)
  const vuelta = useVuelta(conVuelta)
  const [vista, setVista] = useState<Vista>({ tipo: 'cargando' })
  const resuelto = useRef<ResultadoRetorno | null>(null)

  // Al salir de la ruta (no al montarse de nuevo por el cambio de persona), la vuelta y el
  // comprobante en memoria se olvidan: «Ver el comprobante» y una recarga no repiten el retorno.
  useEffect(
    () => () => {
      if (window.location.pathname.replace(/\/+$/, '') !== RUTA_PAGO) {
        olvidarVuelta()
        olvidarComprobante()
      }
    },
    [],
  )

  /** Lee el pago del pedido y elige la vista que corresponde al resultado. */
  const resolver = useCallback(
    async (r: ResultadoRetorno) => {
      if (!r.grupo_id || !r.persona_cuidada_id || !r.pedido_id) return setVista({ tipo: 'sin-sesion', resultado: r })
      // 7.1: fija el grupo y la persona del pedido (la elegida en memoria se perdió al ir a Webpay).
      // La pantalla se monta de nuevo con la persona nueva y sigue desde el resultado guardado.
      if (r.grupo_id !== grupoId || r.persona_cuidada_id !== personaId) {
        // 2.2: si ya se fijó una vez y la persona cambió después, fue la persona quien eligió otra
        // en el encabezado: va a «Tu pedido» de esa persona, y la vuelta se olvida.
        if (leerVuelta()?.fijada) {
          olvidarVuelta()
          return navegar(RUTA_PEDIDO, { reemplazar: true })
        }
        try {
          marcarFijada()
          await elegir(r.grupo_id, r.persona_cuidada_id)
          return
        } catch (x) {
          if (esVencida(x)) return
          return setVista({ tipo: 'error', titulo: tituloDeResultado(r) })
        }
      }
      const pedidoId = r.pedido_id
      try {
        if (r.resultado === 'aprobado' || r.resultado === 'aprobado_tardio') {
          const p = await leerPago(pedidoId)
          if (esPagoCompleto(p) && conComprobante(p)) return setVista({ tipo: 'comprobante', pago: p, yaRegistrado: r.ya_registrado })
          return setVista({ tipo: 'error', titulo: tituloDeResultado(r) })
        }
        if (r.resultado === 'anulado') {
          const p = await leerPago(pedidoId)
          const d = esPagoCompleto(p) ? anulacionTardia(p) : null
          // Decisión 248: el sello sale de `pago_de_prueba` del pago (aquí no hay comprobante).
          if (d && esPagoCompleto(p)) return setVista({ tipo: 'anulado', anulacion: r.anulacion ?? d.estado, devolucion: d, pagoDePrueba: p.pago_de_prueba })
          return setVista({ tipo: 'error', titulo: tituloDeResultado(r) })
        }
        if (r.resultado === 'no_aprobado' || r.resultado === 'abandonado' || r.resultado === 'tiempo_agotado') {
          // El plazo y «Intentar de nuevo» salen del pedido sin pagar; sin él, solo «Ir a tu pedido».
          let pedido: PedidoVista | null = null
          try {
            const p = await leerPedidoEnCurso(r.persona_cuidada_id)
            pedido = p && esVistaCompleta(p) && p.id === pedidoId ? p : null
          } catch (x) {
            if (esVencida(x)) return
          }
          return setVista({ tipo: 'no-se-hizo', resultado: r.resultado, pedido })
        }
      } catch (x) {
        if (esVencida(x)) return
        setVista({ tipo: 'error', titulo: tituloDeResultado(r) })
      }
    },
    [grupoId, personaId, elegir],
  )

  /** Sin vuelta: el comprobante en memoria, o el último pagado de la persona (P2, decisión 237). */
  const cargarPagado = useCallback(async () => {
    if (!personaId) return
    const enMemoria = tomarComprobante(personaId)
    if (enMemoria && conComprobante(enMemoria)) return setVista({ tipo: 'comprobante', pago: enMemoria, yaRegistrado: false })
    setVista({ tipo: 'cargando' })
    try {
      const p = await leerPedidoPagado(personaId)
      if (p && esPagoCompleto(p) && conComprobante(p)) return setVista({ tipo: 'comprobante', pago: p, yaRegistrado: false })
      navegar(RUTA_PEDIDO, { reemplazar: true })
    } catch (x) {
      if (esVencida(x)) return
      setVista({ tipo: 'error', titulo: null })
    }
  }, [personaId])

  useEffect(() => {
    if (!conVuelta) void cargarPagado()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // El resultado de la vuelta, una vez por resultado.
  useEffect(() => {
    if (!conVuelta) return
    if (vuelta.fase === 'desconocido') {
      olvidarVuelta()
      return navegar(RUTA_PEDIDO, { reemplazar: true })
    }
    if (vuelta.fase !== 'listo' || !vuelta.resultado || resuelto.current === vuelta.resultado) return
    resuelto.current = vuelta.resultado
    void resolver(vuelta.resultado)
  }, [conVuelta, vuelta.fase, vuelta.resultado, resolver])

  // ---------------------------------------------------------------- qué se ve

  let contenido: ReactNode
  let titulo: string | null
  if (conVuelta && (vuelta.fase === 'esperando' || vuelta.fase === 'tarda')) {
    titulo = PAGO.confirmandoTitulo
    contenido = <Confirmando tarda={vuelta.fase === 'tarda'} revisando={vuelta.revisando} onRevisar={vuelta.revisar} />
  } else if (vista.tipo === 'comprobante') {
    titulo = PAGO.pagasteTitulo
    contenido = <PagasteTuPedido pago={vista.pago} yaRegistrado={vista.yaRegistrado} />
  } else if (vista.tipo === 'no-se-hizo') {
    titulo = vista.resultado === 'no_aprobado' ? PAGO.noSeHizoTitulo : vista.resultado === 'abandonado' ? PAGO.salisteTitulo : PAGO.tiempoTitulo
    contenido = <NoSeHizo resultado={vista.resultado} pedido={vista.pedido} admin={rol === 'admin'} />
  } else if (vista.tipo === 'anulado') {
    titulo = vista.anulacion === 'hecha' ? PAGO.anulamosTitulo : PAGO.anulandoTitulo
    contenido = <Anulado anulacion={vista.anulacion} devolucion={vista.devolucion} pagoDePrueba={vista.pagoDePrueba} />
  } else if (vista.tipo === 'sin-sesion') {
    titulo = tituloDeResultado(vista.resultado)
    contenido = <ResultadoSinSesion resultado={vista.resultado} dentro />
  } else if (vista.tipo === 'error') {
    titulo = vista.titulo ?? PEDIDO.titulo
    const r = vuelta.resultado
    const reintentar = () => {
      if (!r) return void cargarPagado()
      setVista({ tipo: 'cargando' })
      void resolver(r)
    }
    contenido = <ErrorAlTraer titulo={titulo} onReintentar={reintentar} />
  } else {
    titulo = null
    contenido = (
      <div className="flex min-w-0 flex-col gap-3">
        <PestanasInsumos activa="/insumos/pedido" />
        <Cargando />
      </div>
    )
  }

  useTituloDelEstado(titulo)
  return contenido
}

/** 2.1: el `<title>` es el `h1` de cada estado, y cuando el `h1` cambia en la misma ruta, el foco va a él. */
function useTituloDelEstado(titulo: string | null) {
  const antes = useRef<string | null>(titulo)
  useEffect(() => {
    if (titulo) document.title = `${titulo} · MATU`
    if (titulo && titulo !== antes.current) enfocar('titulo-pagina', 40)
    antes.current = titulo
  }, [titulo])
}

function tituloDeResultado(r: ResultadoRetorno): string {
  switch (r.resultado) {
    case 'aprobado':
    case 'aprobado_tardio':
      return PAGO.pagasteTitulo
    case 'no_aprobado':
      return PAGO.noSeHizoTitulo
    case 'abandonado':
      return PAGO.salisteTitulo
    case 'tiempo_agotado':
      return PAGO.tiempoTitulo
    case 'anulado':
      return r.anulacion === 'en_curso' ? PAGO.anulandoTitulo : PAGO.anulamosTitulo
    default:
      return PAGO.confirmandoTitulo
  }
}

// ---------------------------------------------------------------- piezas comunes

/** Las pestañas, la baldosa y el `h1`. La baldosa va encima del título y, desde `@xl/main`, a su izquierda. */
function Encabezado({ tono, icono, titulo, pestanas = true }: { tono: TonoBaldosa; icono: ReactNode; titulo: string; pestanas?: boolean }) {
  return (
    <>
      {pestanas && <PestanasInsumos activa="/insumos/pedido" />}
      <div className="mt-2 flex flex-col items-start gap-5 @xl/main:flex-row @xl/main:items-center">
        <Baldosa tono={tono} icono={icono} />
        {/* Revisión visual P1: el título puede encogerse junto a la baldosa y partir en renglones. */}
        {/* Revisión visual P3: a 320 px con el texto al 200 %, «confirmando» se parte con guion, en español. */}
        <Titulo lang="es-CL" className="max-w-full min-w-0 hyphens-auto text-3xl @2xl/main:text-4xl">
          {titulo}
        </Titulo>
      </div>
    </>
  )
}

function Cargando() {
  const ver = useDemora()
  return (
    <div aria-busy="true" className="mt-2">
      <p role="status" className="text-lg text-tenue">
        {ver ? GENERAL.cargando : ''}
      </p>
    </div>
  )
}

function ErrorAlTraer({ titulo, onReintentar }: { titulo: string; onReintentar: () => void }) {
  return (
    <div className="flex min-w-0 max-w-3xl flex-col gap-5">
      <Encabezado tono="neutro" icono={<CloudOff aria-hidden className="size-9" />} titulo={titulo} />
      <Anunciado urgencia="alert" como="p" className="max-w-prose text-lg">
        {PEDIDO.errCarga}
      </Anunciado>
      <Boton className="self-start" onClick={onReintentar}>
        {GENERAL.volverAIntentar}
      </Boton>
    </div>
  )
}

// ---------------------------------------------------------------- 7.2 y 7.3

/** 7.2 «Estamos confirmando tu pago» y 7.3 «La respuesta tarda». Sin botón de pagar: es lo que evita el doble pago. */
function Confirmando({ tarda, revisando, onRevisar }: { tarda: boolean; revisando: boolean; onRevisar: () => void }) {
  return (
    <div className="flex min-w-0 max-w-3xl flex-col gap-5">
      <Encabezado
        tono={tarda ? 'atenta' : 'rocio'}
        icono={tarda ? <Clock aria-hidden className="size-9" /> : <CreditCard aria-hidden className="size-9 text-turquesa" />}
        titulo={PAGO.confirmandoTitulo}
      />
      {tarda ? (
        <>
          <Nota tono="atenta" borde rol="status" icono={<Clock aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
            <p>{PAGO.tarda}</p>
          </Nota>
          <Acciones className="angosto:flex-col angosto:items-stretch">
            <Boton variante="secundario" ocupado={revisando} textoOcupado={PAGO.revisando} onClick={onRevisar}>
              {PAGO.revisarAhora}
            </Boton>
            <Boton variante="texto" onClick={() => navegar(RUTA_PEDIDO)}>
              {PAGO.irATuPedido}
            </Boton>
          </Acciones>
        </>
      ) : (
        <div aria-busy="true">
          <p className="max-w-prose text-lg">{PAGO.noCierres}</p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- 7.10 sin la sesión de la app

/**
 * 7.10: el resultado sin montos ni tarjeta, y «Entrar». Fuera de la app (sin sesión) va en el marco
 * simple, sin pestañas; dentro (otra cuenta, que no es del grupo del pedido) sale primero.
 */
export function ResultadoSinSesion({ resultado: r, dentro = false }: { resultado: ResultadoRetorno; dentro?: boolean }) {
  const { fijar, salir } = useFamilia()
  const titulo = tituloDeResultado(r)
  const [tono, icono]: [TonoBaldosa, ReactNode] =
    r.resultado === 'aprobado' || r.resultado === 'aprobado_tardio'
      ? ['ok', <CircleCheck key="i" aria-hidden className="size-9" />]
      : r.resultado === 'anulado'
        ? ['atenta', <Undo2 key="i" aria-hidden className="size-9" />]
        : r.resultado === 'pendiente'
          ? ['atenta', <Clock key="i" aria-hidden className="size-9" />]
          : ['neutro', <CreditCard key="i" aria-hidden className="size-9" />]
  const entrar = async () => {
    fijar({ destino: RUTA_PEDIDO })
    if (dentro) await salir()
    olvidarVuelta()
    navegar('/entrar')
  }
  return (
    <div className="flex min-w-0 max-w-3xl flex-col gap-5">
      <Encabezado tono={tono} icono={icono} titulo={titulo} pestanas={dentro} />
      {r.ya_registrado && (r.resultado === 'aprobado' || r.resultado === 'aprobado_tardio') && (
        <Nota tono="rocio">
          <p>{PAGO.yaRegistrado}</p>
        </Nota>
      )}
      {r.resultado === 'pendiente' && (
        <Nota tono="atenta" borde icono={<Clock aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
          <p>{PAGO.tarda}</p>
        </Nota>
      )}
      {r.resultado === 'no_aprobado' && <p className="max-w-prose text-lg">{PAGO.noSeHizo}</p>}
      {(r.resultado === 'abandonado' || r.resultado === 'tiempo_agotado') && <p className="max-w-prose text-lg">{PAGO.noSeCobro}</p>}
      <p className="max-w-prose text-lg">{PAGO.sinSesion}</p>
      <Boton className="self-start" onClick={() => void entrar()}>
        {PAGO.entrar}
      </Boton>
    </div>
  )
}

/** La vuelta sin sesión, en el marco simple (AppFamilia): pregunta el resultado y lo muestra. */
export function VueltaSinSesion() {
  const vuelta = useVuelta(true)
  const titulo = vuelta.fase === 'listo' && vuelta.resultado ? tituloDeResultado(vuelta.resultado) : PAGO.confirmandoTitulo
  useTituloDelEstado(titulo)
  useEffect(() => {
    if (vuelta.fase === 'desconocido') {
      olvidarVuelta()
      navegar('/entrar', { reemplazar: true })
    }
  }, [vuelta.fase])
  if (vuelta.fase === 'listo' && vuelta.resultado) return <ResultadoSinSesion resultado={vuelta.resultado} />
  if (vuelta.fase === 'tarda' && vuelta.resultado) return <ResultadoSinSesion resultado={vuelta.resultado} />
  return (
    <div className="flex min-w-0 max-w-3xl flex-col gap-5">
      <Encabezado tono="rocio" icono={<CreditCard aria-hidden className="size-9 text-turquesa" />} titulo={PAGO.confirmandoTitulo} pestanas={false} />
      {vuelta.fase === 'tarda' ? (
        <>
          <Nota tono="atenta" borde rol="status" icono={<Clock aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
            <p>{PAGO.tarda}</p>
          </Nota>
          <Boton variante="secundario" className="self-start" ocupado={vuelta.revisando} textoOcupado={PAGO.revisando} onClick={vuelta.revisar}>
            {PAGO.revisarAhora}
          </Boton>
        </>
      ) : (
        <div aria-busy="true">
          <p className="max-w-prose text-lg">{PAGO.noCierres}</p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- 7.11 y 7.12

function NoSeHizo({ resultado, pedido, admin }: { resultado: 'no_aprobado' | 'abandonado' | 'tiempo_agotado'; pedido: PedidoVista | null; admin: boolean }) {
  const [confirmando, setConfirmando] = useState(false)
  const [error, setError] = useState<'red' | 'nada' | null>(null)
  const titulo = resultado === 'no_aprobado' ? PAGO.noSeHizoTitulo : resultado === 'abandonado' ? PAGO.salisteTitulo : PAGO.tiempoTitulo
  const vigente = !!pedido && pedido.estado === 'total_confirmado' && (pedido.vigencia_segundos ?? 0) > 0 && !pedido.pago_en_curso
  const vencido = !!pedido && !pedido.pago_en_curso && (pedido.estado === 'vencido' || (pedido.estado === 'total_confirmado' && (pedido.vigencia_segundos ?? 0) <= 0))
  const hora = pedido ? horaDeVencimiento(pedido) : ''

  /** 7.11 con el total vencido (admin): confirma y lleva al resumen con la hora nueva (MATU-61, 9.6). */
  const confirmarDeNuevo = async () => {
    if (!pedido || confirmando) return
    setConfirmando(true)
    setError(null)
    try {
      await confirmarPedido(pedido.id, null)
      navegar(RUTA_RESUMEN)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      setError(f.status === 409 && esTipo(f.tipo, 'nada-disponible') ? 'nada' : 'red')
    } finally {
      setConfirmando(false)
    }
  }

  return (
    <div className="flex min-w-0 max-w-3xl flex-col gap-5">
      <Encabezado tono="neutro" icono={<CreditCard aria-hidden className="size-9" />} titulo={titulo} />
      <p className="max-w-prose text-lg">{resultado === 'no_aprobado' ? PAGO.noSeHizo : PAGO.noSeCobro}</p>
      {vigente && (
        <p className="text-base">
          {PEDIDO.valeHasta} <span className="cifras">{hora}</span>.
        </p>
      )}
      {vencido && admin && (
        <p className="text-base">
          {PEDIDO.vencioALas} <span className="cifras">{hora}</span>.
        </p>
      )}
      {vencido && !admin && <p className="max-w-prose text-base">{PEDIDO.vencidoPagador}</p>}
      {error && (
        <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
          {error === 'nada' ? PEDIDO.nadaDisponible : PEDIDO.errConfirmar}
        </Nota>
      )}
      <Acciones className="angosto:flex-col angosto:items-stretch">
        {vigente && <Boton onClick={() => navegar(RUTA_RESUMEN)}>{PAGO.intentarDeNuevo}</Boton>}
        {vencido && admin && (
          <Boton ocupado={confirmando} textoOcupado={PEDIDO.confirmando} onClick={() => void confirmarDeNuevo()}>
            {PEDIDO.volverAConfirmar}
          </Boton>
        )}
        <Boton variante="texto" onClick={() => navegar(RUTA_PEDIDO)}>
          {PAGO.irATuPedido}
        </Boton>
      </Acciones>
      {confirmando && (
        <p role="status" className="text-base">
          {PEDIDO.confirmandoEstado}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- 7.9 pago tardío anulado

function Anulado({ anulacion, devolucion: d, pagoDePrueba }: { anulacion: 'hecha' | 'en_curso'; devolucion: Devolucion; pagoDePrueba: boolean }) {
  const monto = <span className="cifras font-bold">{pesos(d.monto)}</span>
  const tarjeta = <span className="cifras">{d.ultimos4 ?? ''}</span>
  return (
    <div className="flex min-w-0 max-w-3xl flex-col gap-5">
      <Encabezado tono="atenta" icono={<Undo2 aria-hidden className="size-9" />} titulo={anulacion === 'hecha' ? PAGO.anulamosTitulo : PAGO.anulandoTitulo} />
      <p className="max-w-prose text-lg">
        {PAGO.anuladoAntes}{' '}
        {anulacion === 'hecha' ? (
          <>
            {PAGO.anulamosMonto} {monto} {PAGO.completoATuTarjeta} {tarjeta}. {PAGO.cuandoTuBanco}
          </>
        ) : (
          <>
            {PAGO.devolviendoTotal} {monto} {PAGO.aTuTarjeta} {tarjeta}. {PAGO.devolviendoTuya}
          </>
        )}
      </p>
      {/* D-62-7: el sello, sin «no es una boleta» porque aquí no hay comprobante. */}
      {pagoDePrueba && <p className="max-w-prose text-base text-tenue">{PAGO.selloSolo}</p>}
      <Boton variante="secundario" className="self-start" onClick={() => navegar(RUTA_PEDIDO)}>
        {PAGO.irATuPedido}
      </Boton>
    </div>
  )
}

// ---------------------------------------------------------------- 7.4 pagaste tu pedido

/** Las devoluciones que restan: las hechas de este pago (la anulación de otro pago tardío no). */
const restan = (c: Comprobante) => c.devoluciones.filter((d) => d.estado === 'hecha' && d.motivo !== 'pago_tardio')

function PagasteTuPedido({ pago, yaRegistrado }: { pago: PagoVista & { comprobante: Comprobante }; yaRegistrado: boolean }) {
  const c = pago.comprobante
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <Encabezado tono="ok" icono={<CircleCheck aria-hidden className="size-9" />} titulo={PAGO.pagasteTitulo} />
      <p className="max-w-prose text-lg">
        {PAGO.pagasteAntes} <span className="cifras font-bold">{pesos(c.total)}</span> {PAGO.pagasteDespues}
      </p>
      {yaRegistrado && (
        <Nota tono="rocio">
          <p>{PAGO.yaRegistrado}</p>
        </Nota>
      )}
      {c.tardio && (
        <Nota tono="rocio">
          <p>
            {PAGO.tardio} <span className="cifras font-bold">{pesos(c.total)}</span>
            {PAGO.tardioCierre}
          </p>
        </Nota>
      )}
      {c.devoluciones.map((d) => (
        <NotaDevolucion key={`${d.solicitada_en}-${d.monto}-${d.producto?.id ?? 'pedido'}`} devolucion={d} pagasteTu={c.pagaste_tu} />
      ))}
      {c.precios_de_ejemplo && <AvisoPiloto />}
      {/* Revisión visual P3: las dos primeras filas miden lo suyo y la última toma el resto, sin huecos. */}
      <div className="mt-4 grid grid-cols-1 gap-x-10 gap-y-10 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] @3xl/main:grid-rows-[auto_auto_1fr]">
        {/* 7.4.2: el comprobante va primero en el DOM (el lector y el Tab lo leen antes) y a la derecha en ancho. */}
        <div className="min-w-0 @3xl/main:col-start-2 @3xl/main:row-span-3 @3xl/main:row-start-1 @3xl/main:sticky @3xl/main:top-6 @3xl/main:max-h-[calc(100dvh-3rem)] @3xl/main:self-start @3xl/main:overflow-y-auto [scrollbar-width:thin]">
          <ComprobanteBoleta c={c} />
        </div>
        <DatosDelPedido c={c} className="@3xl/main:col-start-1 @3xl/main:row-start-1" />
        <Garantias c={c} className="@3xl/main:col-start-1 @3xl/main:row-start-2" />
        <div className="flex min-w-0 flex-col items-start gap-4 @3xl/main:col-start-1 @3xl/main:row-start-3">
          {/* Decisión 249: `correo` llega en null mientras el comprobante no se envíe (el piloto). */}
          {c.pagaste_tu && (
            <p className="max-w-prose text-base text-tenue">
              {c.correo?.enviado ? (
                <>
                  {PAGO.correoEnviado} <span className="break-words">{c.correo.destino}</span>.
                </>
              ) : (
                PAGO.correoPiloto
              )}
            </p>
          )}
          <Acciones className="angosto:flex-col angosto:items-stretch">
            <Boton variante="secundario" icono={<Printer aria-hidden className="size-5 shrink-0" />} onClick={() => window.print()}>
              {PAGO.imprimir}
            </Boton>
            <Boton variante="texto" onClick={() => navegar(RUTA_PEDIDO)}>
              {PAGO.irATuPedido}
            </Boton>
          </Acciones>
        </div>
      </div>
      <HojaComprobante c={c} />
    </div>
  )
}

/** 7.7: una nota por devolución, con la tarjeta solo para quien pagó (D-62-2). */
function NotaDevolucion({ devolucion: d, pagasteTu }: { devolucion: Devolucion; pagasteTu: boolean }) {
  const monto = <span className="cifras font-bold">{pesos(d.monto)}</span>
  const por = PAGO.devolvimosTuya(d.producto?.nombre ?? null)
  const icono = (tono: string) => <Undo2 aria-hidden className={`mt-0.5 size-5 shrink-0 ${tono}`} />
  if (d.estado === 'hecha')
    return (
      <Nota tono="ok" borde icono={icono('text-ok')}>
        <p>
          {PAGO.devolvimosAntes} {monto}{' '}
          {pagasteTu && d.ultimos4 ? (
            <>
              {PAGO.aTuTarjeta} <span className="cifras">{d.ultimos4}</span>, {por}. {PAGO.cuandoTuBanco}
            </>
          ) : (
            <>
              {PAGO.aLaTarjeta}, {por}. {PAGO.cuandoElBanco}
            </>
          )}
        </p>
      </Nota>
    )
  return (
    <Nota tono="atenta" borde icono={icono('text-atenta')}>
      <p>
        {PAGO.devolviendoAntes} {monto} {pagasteTu ? `${PAGO.aTuTarjetaSola} ${PAGO.devolviendoTuya}` : `${PAGO.aLaTarjeta}. ${PAGO.devolviendoAjena}`}
      </p>
    </Nota>
  )
}

const RENGLON = 'flex justify-between gap-4 angosto:flex-col angosto:items-start angosto:gap-0'

/** 7.5.1: la boleta de MATU-61 como comprobante. Su título es «Comprobante», nunca «Boleta». */
function ComprobanteBoleta({ c }: { c: Comprobante }) {
  const { fecha: dia, hora } = fecha(c.pagado_en)
  const devueltas = restan(c)
  const pagasteEnTotal = c.total - devueltas.reduce((t, d) => t + d.monto, 0)
  return (
    <section
      aria-labelledby="comprobante-t comprobante-ref"
      className="relative rounded-t-lg bg-hoja px-4 angosto:px-2 @3xl/main:px-7 pt-5 pb-8 ring-1 ring-linea [mask:radial-gradient(circle_at_50%_100%,transparent_0.42rem,var(--color-tinta)_0.45rem)_bottom/1.1rem_100%_repeat-x]"
    >
      {/* Revisión visual P1: a 320 px con el texto al 200 % el título baja bajo el ícono y no se sale. */}
      <h2 id="comprobante-t" className="mb-4 flex items-center gap-2 text-xl font-bold angosto:flex-col angosto:items-start">
        <ReceiptText aria-hidden className="size-5 shrink-0 text-turquesa" />
        <span className="min-w-0">{PAGO.comprobante}</span>
      </h2>
      <div className="flex flex-col gap-3">
        <div>
          <p id="comprobante-ref" className="text-lg font-bold">
            {PAGO.pedidoRef(c.referencia)}
          </p>
          <p className="text-base">
            <span className="cifras">{dia}</span> {PAGO.aLas} <span className="cifras">{hora}</span>
          </p>
        </div>
        {c.pago_de_prueba && <Sello />}
        <ul className="flex flex-col gap-3">
          {c.lineas.map((l) => (
            <li key={l.producto.id}>
              <p className="text-lg font-bold break-words">{l.producto.nombre}</p>
              <p className={`${RENGLON} text-lg tabular-nums`}>
                <span>
                  <span className="cifras">{l.cantidad}</span> × <span className="cifras">{pesos(l.precio_unitario)}</span>
                </span>
                <span className="cifras">{pesos(l.subtotal)}</span>
              </p>
            </li>
          ))}
        </ul>
        <p className={`${RENGLON} text-lg`}>
          <span>{PAGO.envio}</span>
          <span className="cifras">{pesos(c.costo_envio)}</span>
        </p>
        <hr className="border-0 border-t-2 border-tinta" />
        <p className={`${RENGLON} text-2xl font-bold`}>
          <span>{PAGO.totalPagado}</span>
          <span className="cifras">{pesos(c.total)}</span>
        </p>
        {devueltas.length > 0 && (
          <>
            {devueltas.map((d) => (
              <p key={`${d.solicitada_en}-${d.monto}`} className={`${RENGLON} text-lg`}>
                <span className="break-words">{PAGO.renglonDevolvimos(d.producto?.nombre ?? null)}</span>
                <span className="cifras">−{pesos(d.monto)}</span>
              </p>
            ))}
            <hr className="border-0 border-t-2 border-tinta" />
            <p className={`${RENGLON} text-2xl font-bold`}>
              <span>{PAGO.pagasteEnTotal}</span>
              <span className="cifras">{pesos(pagasteEnTotal)}</span>
            </p>
          </>
        )}
        <span>
          <Etiqueta tono="ok">
            <Check aria-hidden className="size-4 shrink-0" />
            {PAGO.pagado}
          </Etiqueta>
        </span>
        <TarjetaDelPago c={c} />
      </div>
    </section>
  )
}

/** La tarjeta y el código, solo para quien pagó. La pantalla nunca oculta un dato que llegó (2.3). */
function TarjetaDelPago({ c }: { c: Comprobante }) {
  if (!c.tarjeta && !c.codigo_autorizacion) return !c.pagaste_tu ? <p className="text-base">{PAGO.otraPersona}</p> : null
  return (
    <>
      {c.tarjeta && (
        <p className="text-base">
          {PAGO.tarjeta(c.tarjeta.tipo)} <span className="cifras">{c.tarjeta.ultimos4}</span>
          {c.tarjeta.cuotas > 1 && PAGO.enCuotas(c.tarjeta.cuotas)}
        </p>
      )}
      {c.codigo_autorizacion && (
        <p className="text-base">
          {PAGO.codigo} <span className="cifras">{c.codigo_autorizacion}</span>
        </p>
      )}
    </>
  )
}

/** 7.5.2: el sello del piloto, dentro del comprobante y antes de los productos (D-62-7). */
function Sello() {
  return (
    <Nota tono="atenta" icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
      <p>
        <strong className="font-bold">{PAGO.selloTitulo}</strong> {PAGO.selloResto}
      </p>
    </Nota>
  )
}

/** 7.5.3: datos del pedido. */
function DatosDelPedido({ c, className = '' }: { c: Comprobante; className?: string }) {
  return (
    <section aria-labelledby="datos-t" className={`flex min-w-0 flex-col items-start gap-2 ${className}`}>
      <h2 id="datos-t" className="titular text-2xl">
        {PAGO.datosTitulo}
      </h2>
      <p className="max-w-prose text-base">{`Vende: ${c.vendedor}.`}</p>
      <p className="text-base">{PAGO.entrega(c.ventana_entrega)}</p>
      <p className="text-base">
        {PAGO.condicionesAceptadas(c.condiciones.version)} <span className="cifras">{fecha(c.condiciones.aceptadas_en).fecha}</span>
      </p>
      <a
        href={enlaceCondiciones(c.condiciones.version)}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex min-h-12 items-start gap-2 py-3 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa"
      >
        <FileText aria-hidden className="mt-0.5 size-5 shrink-0" />
        {PAGO.condicionesVersion(c.condiciones.version)}
      </a>
    </section>
  )
}

/** 7.5.3: lo que te garantizamos, todo a la vista. */
function Garantias({ c, className = '' }: { c: Comprobante; className?: string }) {
  return (
    <section aria-labelledby="garantias-t" className={`flex min-w-0 flex-col gap-2 ${className}`}>
      <h2 id="garantias-t" className="titular text-2xl">
        {PAGO.garantiasTitulo}
      </h2>
      <ul className="flex max-w-prose list-disc flex-col gap-2 ps-5 text-base marker:text-tenue">
        <li>
          <strong className="font-bold">{PAGO.retractoTitulo}</strong> {PAGO.retracto}
        </li>
        <li>{PAGO.siNoLlega}</li>
        <li>{PAGO.puedeCancelar}</li>
        <li>
          {PAGO.algoNoEsta} <EnlaceEnFrase href={`mailto:${c.canal_reclamo}`}>{c.canal_reclamo}</EnlaceEnFrase>.
        </li>
      </ul>
    </section>
  )
}

/**
 * 7.5.5: la hoja impresa, fuera de `#raiz` (el patrón de MATU-60): solo el comprobante, con el sello
 * arriba y en negrita. En pantalla no existe (`hidden`).
 */
function HojaComprobante({ c }: { c: Comprobante }) {
  const { fecha: dia, hora } = fecha(c.pagado_en)
  const devueltas = restan(c)
  const fila = 'grid break-inside-avoid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 border-b border-borde py-2 text-lg'
  return createPortal(
    <div data-impresion="" className="hidden bg-hoja font-sans text-tinta print:block">
      <p className="break-after-avoid border-b-2 border-tinta pb-2 text-2xl font-bold">
        {PAGO.comprobante} · {PAGO.pedidoRef(c.referencia)}
      </p>
      <p className="py-2 text-base">
        {dia} {PAGO.aLas} {hora}
      </p>
      {c.pago_de_prueba && (
        <p className="py-2 text-lg font-bold">
          {PAGO.selloTitulo} {PAGO.selloResto}
        </p>
      )}
      <ul>
        {c.lineas.map((l) => (
          <li key={l.producto.id} className={fila}>
            <span className="min-w-0 break-words">
              <span className="font-bold">{l.producto.nombre}</span> · {l.cantidad} × {pesos(l.precio_unitario)}
            </span>
            <span className="text-right">{pesos(l.subtotal)}</span>
          </li>
        ))}
        <li className={fila}>
          <span>{PAGO.envio}</span>
          <span className="text-right">{pesos(c.costo_envio)}</span>
        </li>
        <li className={`${fila} font-bold`}>
          <span>{PAGO.totalPagado}</span>
          <span className="text-right">{pesos(c.total)}</span>
        </li>
        {devueltas.map((d) => (
          <li key={`${d.solicitada_en}-${d.monto}`} className={fila}>
            <span className="min-w-0 break-words">{PAGO.renglonDevolvimos(d.producto?.nombre ?? null)}</span>
            <span className="text-right">−{pesos(d.monto)}</span>
          </li>
        ))}
        {devueltas.length > 0 && (
          <li className={`${fila} font-bold`}>
            <span>{PAGO.pagasteEnTotal}</span>
            <span className="text-right">{pesos(c.total - devueltas.reduce((t, d) => t + d.monto, 0))}</span>
          </li>
        )}
      </ul>
      <div className="mt-4 flex flex-col gap-1 text-base">
        {c.tarjeta && (
          <p>
            {PAGO.tarjeta(c.tarjeta.tipo)} {c.tarjeta.ultimos4}
            {c.tarjeta.cuotas > 1 && PAGO.enCuotas(c.tarjeta.cuotas)}
          </p>
        )}
        {c.codigo_autorizacion && (
          <p>
            {PAGO.codigo} {c.codigo_autorizacion}
          </p>
        )}
        {!c.pagaste_tu && <p>{PAGO.otraPersona}</p>}
        <p className="mt-4 text-lg font-bold">{PAGO.datosTitulo}</p>
        <p>{`Vende: ${c.vendedor}.`}</p>
        <p>{PAGO.entrega(c.ventana_entrega)}</p>
        <p>
          {PAGO.condicionesAceptadas(c.condiciones.version)} {fecha(c.condiciones.aceptadas_en).fecha}
        </p>
        <p className="mt-4 text-lg font-bold">{PAGO.garantiasTitulo}</p>
        <ul className="list-disc ps-5">
          <li>
            <strong className="font-bold">{PAGO.retractoTitulo}</strong> {PAGO.retracto}
          </li>
          <li>{PAGO.siNoLlega}</li>
          <li>{PAGO.puedeCancelar}</li>
          <li>
            {PAGO.algoNoEsta} {c.canal_reclamo}.
          </li>
        </ul>
      </div>
    </div>,
    document.body,
  )
}

// ---------------------------------------------------------------- 8 el pedido pagado en «Pedido»

/**
 * 8: al final de «Tu pedido», el último pedido pagado. El observador ve solo «Pedido pagado» y
 * «Pagado» (D-62-2). Sin macizo: no compite con «Ver el total».
 */
export function BloquePedidoPagado({ pago, onVer }: { pago: Pago; onVer: (p: PagoVista) => void }) {
  const completo = esPagoCompleto(pago) && conComprobante(pago) ? pago : null
  const c = completo?.comprobante
  const cuando = c ? fecha(c.pagado_en) : null
  return (
    <section aria-labelledby="pedido-pagado-t" className="mt-10 flex flex-col items-start gap-3 border-t border-linea pt-6">
      <h2 id="pedido-pagado-t" className="titular text-2xl">
        {PAGO.pagadoTitulo}
      </h2>
      <Etiqueta tono="ok">
        <Check aria-hidden className="size-4 shrink-0" />
        {PAGO.pagado}
      </Etiqueta>
      {c && cuando && completo && (
        <>
          <p className="text-base">
            {PAGO.pedidoRef(c.referencia)} · <span className="cifras">{cuando.fecha}</span> {PAGO.aLas} <span className="cifras">{cuando.hora}</span>
          </p>
          <p className="text-lg">
            {PAGO.totalPagadoDos} <span className="cifras font-bold">{pesos(c.total)}</span>
          </p>
          <Boton variante="secundario" onClick={() => onVer(completo)}>
            {PAGO.verComprobante}
          </Boton>
        </>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- 6 el pago en curso

/**
 * 6.1 (quien quiere cambiar) y 6.2 (quien quiere pagar): la nota `atenta` con `CreditCard` y
 * «Revisar de nuevo». Al abrir, sin rol (es el estado de la página); después de un 409, `alert` y el foco.
 */
export function NotaPagoEnCurso({ id, para, alerta, revisando, onRevisar }: { id: string; para: 'cambiar' | 'pagar'; alerta: boolean; revisando: boolean; onRevisar: () => void }) {
  return (
    <Nota id={id} tono="atenta" borde rol={alerta ? 'alert' : undefined} enfocable icono={<CreditCard aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
      <p>{para === 'cambiar' ? PAGO.enCursoCambiar : PAGO.enCursoPagar}</p>
      <p className="mt-2">{para === 'cambiar' ? PAGO.enCursoCambiarCierre : PAGO.enCursoPagarCierre}</p>
      <Acciones className="mt-3 angosto:flex-col angosto:items-stretch">
        <Boton variante="secundario" ocupado={revisando} textoOcupado={PAGO.revisando} onClick={onRevisar}>
          {PAGO.revisarDeNuevo}
        </Boton>
      </Acciones>
    </Nota>
  )
}
