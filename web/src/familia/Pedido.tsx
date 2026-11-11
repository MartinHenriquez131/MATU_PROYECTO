// «Tu pedido» (MATU-61, RF-21, ADR-027, capa 3; especificación docs/diseno/matu-61-pedido.md v1.1).
// Una sola pantalla para las tres rutas: `/insumos/pedido` (el permiso de los pedidos, el carrito y
// su vacío), `/insumos/pedido/direccion` (Direccion.tsx) y `/insumos/pedido/resumen` (Resumen.tsx).
// Como AppFamilia le da la misma `key` en las tres, el pedido sigue en memoria al pasar de una a otra.
//
// - El carrito vive en el servidor como borrador (C18). Nada del pedido, la dirección, el teléfono o
//   la intención de pedir va a localStorage, sessionStorage, la URL ni `history.state`.
// - Solo la cantidad y «Si falta» se guardan solos y se ven antes de la respuesta (7.5 y 7.6:
//   reversibles y no críticos). Sacar, confirmar, cambiar y cancelar esperan la respuesta.
// - La pantalla no calcula el total, el envío ni el vencimiento: la única cuenta es «Productos».
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { CloudOff, Hourglass, Lock, PackageX, SearchX, ShoppingBasket, Store } from 'lucide-react'
import { verCatalogo, type Catalogo } from '../compartido/api/catalogo'
import { leerFallo } from '../compartido/api/cliente'
import { leerAutorizaciones, leerCuenta, nombrePilaDe, type Cuenta, type PersonaListada, type Rol } from '../compartido/api/familia'
import {
  confirmarPedido,
  esVistaCompleta,
  leerConflictoPedido,
  leerPedidoEnCurso,
  reemplazarLineas,
  reemplazarReglas,
  volverABorrador,
  type DireccionVista,
  type LineaPedido,
  type Pedido,
  type PedidoVista,
  type Regla,
} from '../compartido/api/pedido'
import { esVencida } from '../compartido/api/sesion'
import { anunciar, Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { Direccion } from './Direccion'
import { useDemora } from './Estados'
import { puedeEditar, useFamilia, type IntencionPedido } from './estado'
import { enfocar, entero, esTipo, Stepper } from './insumosComun'
import { Permiso, PestanasInsumos } from './Insumos'
import { agregarAlPedido, cambioAjeno, parrafosDeLista, permisoPedidoDe } from './pedidoAcciones'
import { direccionEnTexto, enRango, lineasParaGuardar, productosDe, reglasConCambio, sufijoDelPedido } from './pedidoComun'
import { AvisoPiloto, DialogoCancelar, horaDeVencimiento, Retracto, siFaltaTexto, TelefonoContacto, UnaColumna } from './PiezasPedido'
import { Resumen } from './Resumen'
import { navegar, useRuta } from './ruteo'
import { GENERAL } from './textos'
import { pesos } from './textosCatalogo'
import { PEDIDO } from './textosPedido'
import { Acciones, GrupoOpciones, MensajeError, Nota, Titulo, Volver } from './ui'

type Carga = 'cargando' | 'listo' | 'red' | 'apagado' | 'no-encontrado'
type Aut = 'vigente' | 'revision-vencida' | 'sin-autorizacion'
/** Una nota bajo la bajada, hasta salir de la pantalla (6.4, 7.3 y 11.2). */
export interface NotaPedido {
  tono: 'ok' | 'rocio'
  parrafos: string[]
}

const RUTA_DIRECCION = '/insumos/pedido/direccion'
const RUTA_RESUMEN = '/insumos/pedido/resumen'
const ID_AGREGAR_DIRECCION = 'agregar-direccion'
const ID_TELEFONO_T = 'telefono-contacto-t'
const ID_CANCELAR = 'cancelar-pedido'
const ID_NOTA = 'nota-pedido'
const idCantidad = (pid: string) => `cantidad-${pid}`
const idProducto = (pid: string) => `producto-${pid}`

const pilaDe = (p: PersonaListada | null) => (p ? (nombrePilaDe(p).trim().split(/\s+/)[0] ?? '') : '')
const direccionDe = (p: PersonaListada | null): DireccionVista | null => (p && 'direccion' in p ? (p.direccion ?? null) : null)
const enfocarTitulo = (ms = 40) => enfocar('titulo-pagina', ms)

// ---------------------------------------------------------------- pantalla

export function PantallaPedido() {
  const ruta = useRuta()
  const { persona, personaId, rol, fijar, intencionPedido, llegadaPedido, direccionDesdeGrupo, capa3 } = useFamilia()
  const editor = puedeEditar(rol)
  const pila = pilaDe(persona)

  const [carga, setCarga] = useState<Carga>('cargando')
  const [cargado, setCargado] = useState(false)
  const [aut, setAut] = useState<Aut>('sin-autorizacion')
  const [pedido, setPedidoEstado] = useState<Pedido | null>(null)
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [cuenta, setCuenta] = useState<Cuenta | null>(null)
  /** 7.8.1: el teléfono escrito antes de confirmar, solo en memoria. Es del pedido, no de la persona. */
  const [telefono, setTelefono] = useState<string | null>(null)
  const [nota, setNota] = useState<NotaPedido | null>(() => (llegadaPedido && llegadaPedido.personaId === personaId ? { tono: llegadaPedido.tono, parrafos: llegadaPedido.parrafos } : null))
  const [deLista, setDeLista] = useState<Record<string, string>>(() => (llegadaPedido && llegadaPedido.personaId === personaId ? llegadaPedido.deLista : {}))
  /** 4: desde dónde se llegó al permiso, para `Volver`. La intención misma sigue en el contexto. */
  const [intencion] = useState<IntencionPedido | null>(() => (intencionPedido && intencionPedido.personaId === personaId ? intencionPedido : null))
  const [renovando, setRenovando] = useState(false)
  const [errAgregar, setErrAgregar] = useState(false)
  const [desdeDireccion, setDesdeDireccion] = useState<'carrito' | 'resumen' | 'grupo'>(() => (direccionDesdeGrupo ? 'grupo' : 'carrito'))
  /** 9.8: la casilla de las condiciones, en la memoria de la página. Se envía al pagar (MATU-62). */
  const [acepto, setAcepto] = useState(false)
  /** 8.6: el error de volver a confirmar después de cambiar la dirección, que se ve en el resumen. */
  const [errResumen, setErrResumen] = useState<'red' | 'nada' | null>(null)
  const pedidoRef = useRef<Pedido | null>(null)

  const setPedido = useCallback((p: Pedido | null) => {
    pedidoRef.current = p
    setPedidoEstado(p)
  }, [])

  // La nota de llegada y la vuelta de Grupo familiar se leen una vez y salen del contexto.
  useEffect(() => {
    if (llegadaPedido) fijar({ llegadaPedido: null })
    if (direccionDesdeGrupo) fijar({ direccionDesdeGrupo: false })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const cargar = useCallback(
    async (silencioso = false) => {
      if (!personaId) return
      if (!silencioso) setCarga('cargando')
      const [auts, enCurso, cat, cu] = await Promise.allSettled([
        leerAutorizaciones(personaId),
        leerPedidoEnCurso(personaId),
        verCatalogo(),
        editor ? leerCuenta() : Promise.resolve(null),
      ])
      if (cat.status === 'rejected') {
        if (esVencida(cat.reason)) return
        // 11.2: la capa 3 apagada responde 404 en el catálogo y en el pedido.
        if (leerFallo(cat.reason).status === 404) {
          fijar({ capa3: false })
          setCargado(true)
          return setCarga('apagado')
        }
        return setCarga('red')
      }
      for (const r of [auts, enCurso]) {
        if (r.status === 'rejected') {
          if (esVencida(r.reason)) return
          return setCarga(leerFallo(r.reason).status === 404 ? 'no-encontrado' : 'red')
        }
      }
      if (capa3 !== true) fijar({ capa3: true })
      const despacho = auts.status === 'fulfilled' ? auts.value.find((a) => a.finalidad === 'despacho') : undefined
      setAut(despacho?.estado === 'vigente' ? 'vigente' : despacho?.estado === 'revision_vencida' ? 'revision-vencida' : 'sin-autorizacion')
      setPedido(enCurso.status === 'fulfilled' ? enCurso.value : null)
      setCatalogo(cat.value)
      if (cu.status === 'fulfilled') setCuenta(cu.value)
      setCargado(true)
      setCarga('listo')
    },
    [personaId, editor, capa3, fijar, setPedido],
  )

  useEffect(() => {
    if (ruta !== RUTA_DIRECCION && !cargado) void cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ruta, cargado])

  // 9: el resumen existe solo con un total confirmado o vencido, y nunca para el observador.
  useEffect(() => {
    if (ruta !== RUTA_RESUMEN || carga !== 'listo') return
    if (!pedido || !esVistaCompleta(pedido) || pedido.estado === 'borrador' || (editor && aut !== 'vigente')) navegar('/insumos/pedido', { reemplazar: true })
  }, [ruta, carga, pedido, editor, aut])

  // 2.6 y revisión P2-2: el foco de la llegada queda en el h1 de «Cargando», que se reemplaza por el de
  // lo que llega (el permiso, el carrito, el 404…). Si al reemplazarlo cayó al body, lo recibe el h1
  // nuevo: así «Antes de pedir, un permiso» lo recibe al llegar desde el catálogo o la lista.
  const cargaAntes = useRef<Carga>(carga)
  useEffect(() => {
    const venia = cargaAntes.current
    cargaAntes.current = carga
    if (venia !== 'cargando' || carga === 'cargando') return
    const activo = document.activeElement
    if (activo === null || activo === document.body) document.getElementById('titulo-pagina')?.focus()
  }, [carga])

  /** 11.2: otra persona lo canceló, lo confirmó o lo cambió: se muestra cómo quedó. */
  const alCambioAjeno = useCallback(
    async (x: unknown) => {
      const actual = leerConflictoPedido(x)
      if (actual) setPedido(actual)
      setNota({ tono: 'rocio', parrafos: [PEDIDO.cambioMientras] })
      if (!actual) await cargar(true)
      enfocar(ID_NOTA, 60)
    },
    [cargar, setPedido],
  )

  /** Lo común a toda escritura del pedido: la entrada, el permiso, otra persona y el 404. `true` si lo resolvió. */
  const manejar = useCallback(
    (x: unknown): boolean => {
      if (esVencida(x)) return true
      const permiso = permisoPedidoDe(x)
      if (permiso) {
        setAut(permiso)
        setRenovando(false)
        enfocarTitulo(60)
        return true
      }
      if (cambioAjeno(x)) {
        void alCambioAjeno(x)
        return true
      }
      if (leerFallo(x).status === 404) {
        setCarga('no-encontrado')
        return true
      }
      return false
    },
    [alCambioAjeno],
  )

  /** 4.3: con la autorización dada, se hace lo que se quería y se vuelve al carrito con su nota. */
  const alAutorizar = async () => {
    if (!personaId) return
    const quiere = intencionPedido && intencionPedido.personaId === personaId ? intencionPedido : null
    fijar({ intencionPedido: null })
    setRenovando(false)
    setErrAgregar(false)
    let nueva: NotaPedido = { tono: 'ok', parrafos: [pedidoRef.current?.lineas.length ? PEDIDO.autorizados : PEDIDO.autorizadosDesdePestana] }
    if (quiere) {
      if (quiere.agregar.length) {
        try {
          const { pedido: p, yaEstaban } = await agregarAlPedido(personaId, quiere.agregar, productosDe(catalogo))
          setPedido(p)
          nueva = {
            tono: 'ok',
            parrafos:
              quiere.desde === 'catalogo' ? [PEDIDO.autorizadosConProducto(quiere.agregar[0].nombre)] : [PEDIDO.autorizados, ...parrafosDeLista(quiere, yaEstaban)],
          }
          setDeLista(Object.fromEntries(quiere.agregar.filter((a) => a.deLista).map((a) => [a.producto_id, a.deLista!])))
        } catch (x) {
          if (esVencida(x)) return
          nueva = { tono: 'ok', parrafos: [PEDIDO.autorizados] }
          setErrAgregar(true)
        }
      } else nueva = { tono: 'ok', parrafos: [PEDIDO.autorizados, ...parrafosDeLista(quiere, [])] }
    }
    setNota(nueva)
    await cargar(true)
    enfocarTitulo(60)
  }

  // ---------------------------------------------------------------- rutas

  if (ruta === RUTA_DIRECCION)
    return (
      <Direccion
        desde={desdeDireccion}
        onVolver={() => {
          if (desdeDireccion === 'grupo') return navegar('/grupo')
          navegar(desdeDireccion === 'resumen' ? RUTA_RESUMEN : '/insumos/pedido')
        }}
        onGuardada={() => void alGuardarDireccion()}
        onDejarLaSuya={() => {
          if (desdeDireccion === 'grupo') return navegar('/grupo')
          if (desdeDireccion === 'resumen') return navegar(RUTA_RESUMEN)
          setNota({ tono: 'ok', parrafos: [PEDIDO.dejasteLaSuya] })
          navegar('/insumos/pedido')
        }}
        onVaciada={() => {
          if (desdeDireccion === 'grupo') {
            fijar({ aviso: { titulo: PEDIDO.vaciamosDireccion, tono: 'ok' } })
            return navegar('/grupo')
          }
          setNota({ tono: 'ok', parrafos: [PEDIDO.vaciamosDireccion] })
          navegar('/insumos/pedido')
        }}
      />
    )

  /** 8.4 y 8.6: al carrito con su nota, al resumen confirmando de nuevo, o a Grupo familiar. */
  async function alGuardarDireccion() {
    if (desdeDireccion === 'grupo') {
      fijar({ aviso: { titulo: PEDIDO.guardamosDireccion, tono: 'ok' } })
      return navegar('/grupo')
    }
    const p = pedidoRef.current
    if (desdeDireccion === 'resumen' && p && esVistaCompleta(p) && p.estado !== 'borrador') {
      setErrResumen(null)
      try {
        const nuevo = await confirmarPedido(p.id, null)
        setPedido(nuevo)
        anunciar(PEDIDO.confirmamosDeNuevo(horaDeVencimiento(nuevo)), 'status')
      } catch (x) {
        if (esVencida(x)) return
        const f = leerFallo(x)
        if (!manejar(x)) setErrResumen(f.status === 409 && esTipo(f.tipo, 'nada-disponible') ? 'nada' : 'red')
      }
      return navegar(RUTA_RESUMEN)
    }
    setNota({ tono: 'ok', parrafos: [PEDIDO.guardamosDireccion] })
    navegar('/insumos/pedido')
  }

  const irADireccion = (desde: 'carrito' | 'resumen') => {
    setDesdeDireccion(desde)
    navegar(RUTA_DIRECCION)
  }

  const volver =
    intencion?.desde === 'catalogo' ? (
      <Volver onClick={() => navegar('/insumos/catalogo')}>{PEDIDO.volverAlCatalogo}</Volver>
    ) : intencion?.desde === 'lista' ? (
      <Volver onClick={() => navegar('/insumos/lista')}>{PEDIDO.volverALista}</Volver>
    ) : null

  const encabezado = (conTitulo = true) => (
    <>
      <PestanasInsumos activa="/insumos/pedido" />
      {conTitulo && (
        <div>
          <Titulo className="text-3xl @2xl/main:text-5xl">{PEDIDO.titulo}</Titulo>
          <p className="mt-1.5 max-w-prose text-base text-tenue">{PEDIDO.bajada}</p>
        </div>
      )}
    </>
  )

  const notaVista = nota && (
    <Nota id={ID_NOTA} tono={nota.tono} rol="status" enfocable className="animate-aparecer">
      {nota.parrafos.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </Nota>
  )

  // ---------------------------------------------------------------- estados que no son el carrito

  if (carga === 'cargando')
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado()}
        <Cargando />
      </div>
    )
  if (carga === 'apagado')
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado()}
        <UnaColumna tono="neutro" icono={<Store aria-hidden className="size-9" />}>
          <p className="max-w-prose text-lg">{PEDIDO.apagado}</p>
        </UnaColumna>
      </div>
    )
  if (carga === 'red')
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado()}
        <UnaColumna tono="neutro" icono={<CloudOff aria-hidden className="size-9" />}>
          <Anunciado urgencia="alert" como="p" className="max-w-prose text-lg">
            {PEDIDO.errCarga}
          </Anunciado>
          <Boton onClick={() => void cargar()}>{GENERAL.volverAIntentar}</Boton>
        </UnaColumna>
      </div>
    )
  if (carga === 'no-encontrado')
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado()}
        <UnaColumna tono="neutro" icono={<SearchX aria-hidden className="size-9" />}>
          <p className="max-w-prose text-lg">{PEDIDO.noEncontrado}</p>
          <Boton
            variante="secundario"
            onClick={() => {
              setCargado(false)
              navegar('/insumos/pedido')
            }}
          >
            {PEDIDO.irATuPedido}
          </Boton>
        </UnaColumna>
      </div>
    )

  // 4 y 7.2: admin y cuidador sin la autorización vigente ven el permiso (o, por renovar, 4.5).
  if (editor && (aut === 'sin-autorizacion' || renovando))
    return (
      <Permiso
        finalidad="despacho"
        pila={pila}
        personaId={personaId}
        antes={
          <>
            <PestanasInsumos activa="/insumos/pedido" />
            {volver}
          </>
        }
        onListo={() => void alAutorizar()}
        onNoEncontrado={() => setCarga('no-encontrado')}
      />
    )
  if (aut === 'revision-vencida')
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado()}
        <UnaColumna tono="atenta" icono={<Hourglass aria-hidden className="size-9" />}>
          <p className="max-w-prose text-lg">
            <strong>{PEDIDO.renovarTitulo(pila)}</strong> {PEDIDO.renovar}
          </p>
          {editor ? (
            <Boton
              onClick={() => {
                setRenovando(true)
                enfocarTitulo(60)
              }}
            >
              {PEDIDO.renovarBoton}
            </Boton>
          ) : (
            <p className="max-w-prose text-lg">{PEDIDO.renovarPide(pila)}</p>
          )}
        </UnaColumna>
      </div>
    )
  if (!editor && aut === 'sin-autorizacion' && !pedido)
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado()}
        <UnaColumna tono="neutro" icono={<Lock aria-hidden className="size-9" />}>
          <p className="max-w-prose text-lg">
            <strong>{PEDIDO.faltaAutTitulo(pila)}</strong> {PEDIDO.faltaAut(pila)}
          </p>
        </UnaColumna>
      </div>
    )

  const fallaAgregar = errAgregar && (
    <Anunciado urgencia="alert">
      <MensajeError>{PEDIDO.errAgregar}</MensajeError>
    </Anunciado>
  )

  if (ruta === RUTA_RESUMEN && pedido && esVistaCompleta(pedido) && pedido.estado !== 'borrador')
    return (
      <Resumen
        pedido={pedido}
        editor={editor}
        acepto={acepto}
        onAcepto={setAcepto}
        error={errResumen}
        onError={setErrResumen}
        onPedido={setPedido}
        manejar={manejar}
        onCambiado={(p) => {
          setPedido(p)
          setAcepto(false)
          setNota({ tono: 'rocio', parrafos: [PEDIDO.yaPuedesCambiar] })
          navegar('/insumos/pedido')
        }}
        onCancelado={(ya) => {
          setPedido(null)
          setAcepto(false)
          setNota(ya ? { tono: 'rocio', parrafos: [PEDIDO.yaCancelado] } : { tono: 'ok', parrafos: [PEDIDO.cancelamos] })
          navegar('/insumos/pedido')
        }}
        onCambiarDireccion={() => irADireccion('resumen')}
      />
    )

  // 7.10: sin pedido, el vacío.
  if (!pedido || pedido.lineas.length === 0)
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado()}
        {notaVista}
        {fallaAgregar}
        <Vacio editor={editor} pila={pila} />
      </div>
    )

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {encabezado()}
      <Carrito
        key={pedido.id}
        pedido={pedido}
        editor={editor}
        rol={rol}
        pila={pila}
        catalogo={catalogo}
        direccion={rol === 'observador' ? undefined : direccionDe(persona)}
        cuenta={cuenta}
        telefono={telefono}
        onTelefono={setTelefono}
        deLista={deLista}
        nota={
          <>
            {notaVista}
            {fallaAgregar}
          </>
        }
        pedidoRef={pedidoRef}
        onPedido={setPedido}
        manejar={manejar}
        onVacio={() => {
          setPedido(null)
          void cargar(true)
        }}
        onConfirmado={(p) => {
          setPedido(p)
          setAcepto(false)
          setNota(null)
          navegar(RUTA_RESUMEN)
        }}
        onCambiado={(p) => {
          setPedido(p)
          setAcepto(false)
          setNota({ tono: 'rocio', parrafos: [PEDIDO.yaPuedesCambiar] })
          enfocarTitulo(60)
        }}
        onCancelado={(ya) => {
          setPedido(null)
          setNota(ya ? { tono: 'rocio', parrafos: [PEDIDO.yaCancelado] } : { tono: 'ok', parrafos: [PEDIDO.cancelamos] })
          enfocarTitulo(60)
        }}
        onAgregarDireccion={() => irADireccion('carrito')}
      />
    </div>
  )
}

// ---------------------------------------------------------------- piezas

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

/** 7.10: sin pedido. Admin y cuidador, con dos salidas y sin principal; pagador y observador, sin acciones. */
function Vacio({ editor, pila }: { editor: boolean; pila: string }) {
  return (
    <UnaColumna tono={editor ? 'rocio' : 'neutro'} icono={<ShoppingBasket aria-hidden className="size-9" />}>
      <p className="max-w-prose text-lg">{editor ? PEDIDO.vacio : PEDIDO.vacioLector(pila)}</p>
      {editor && (
        <Acciones>
          <Boton variante="secundario" onClick={() => navegar('/insumos/catalogo')}>
            {PEDIDO.irAlCatalogo}
          </Boton>
          <Boton variante="texto" onClick={() => navegar('/insumos/lista')}>
            {PEDIDO.irALista}
          </Boton>
        </Acciones>
      )}
    </UnaColumna>
  )
}

// ---------------------------------------------------------------- 7 el carrito

interface PropsCarrito {
  pedido: Pedido
  editor: boolean
  rol: Rol
  pila: string
  catalogo: Catalogo | null
  /** `undefined` para el observador: su vista no trae la entrega. */
  direccion: DireccionVista | null | undefined
  cuenta: Cuenta | null
  telefono: string | null
  onTelefono: (t: string) => void
  deLista: Record<string, string>
  nota: ReactNode
  pedidoRef: React.RefObject<Pedido | null>
  onPedido: (p: Pedido) => void
  manejar: (x: unknown) => boolean
  onVacio: () => void
  onConfirmado: (p: PedidoVista) => void
  onCambiado: (p: PedidoVista) => void
  onCancelado: (yaCancelado: boolean) => void
  onAgregarDireccion: () => void
}

type ErrCant = 'rango' | 'guardar'
type FallaTotal = 'red' | 'nada' | 'direccion' | null

function Carrito(props: PropsCarrito) {
  const { pedido, editor, rol, pila, catalogo, direccion, cuenta, telefono, onTelefono, deLista, nota, pedidoRef, onPedido, manejar } = props
  const borrador = pedido.estado === 'borrador'
  const editable = editor && borrador
  const productos = productosDe(catalogo)
  const vencido = pedido.estado === 'vencido'

  const [valores, setValores] = useState<Record<string, string>>(() => Object.fromEntries(pedido.lineas.map((l) => [l.producto.id, String(l.cantidad)])))
  const valoresRef = useRef(valores)
  valoresRef.current = valores
  const [errCant, setErrCant] = useState<Record<string, ErrCant>>({})
  const [reglas, setReglas] = useState<Record<string, Regla>>({})
  const [errRegla, setErrRegla] = useState<Record<string, boolean>>({})
  const [sacando, setSacando] = useState<string | null>(null)
  const [errSacar, setErrSacar] = useState<string | null>(null)
  const [confirmando, setConfirmando] = useState(false)
  const [falla, setFalla] = useState<FallaTotal>(null)
  const [errTelefono, setErrTelefono] = useState<string | null>(null)
  const [cambiando, setCambiando] = useState(false)
  const [errCambiar, setErrCambiar] = useState(false)
  const [cancelando, setCancelando] = useState(false)
  const errCantRef = useRef(errCant)
  errCantRef.current = errCant
  const cola = useRef<Promise<void>>(Promise.resolve())
  const reloj = useRef<number | undefined>(undefined)
  const enVuelo = useRef(0)

  useEffect(() => () => window.clearTimeout(reloj.current), [])

  // El pedido cambió (la respuesta de un guardado, un 412 con lo de otra persona, «Cambiar el
  // pedido»): los campos muestran lo guardado, salvo lo que se está escribiendo todavía.
  useEffect(() => {
    setValores((v) => {
      const quieto = reloj.current === undefined && enVuelo.current === 0
      return Object.fromEntries(pedido.lineas.map((l) => [l.producto.id, quieto || v[l.producto.id] === undefined ? String(l.cantidad) : v[l.producto.id]]))
    })
  }, [pedido])

  /** Una escritura a la vez, en orden, cada una con el último `etag` (7.5 y 7.6). */
  const encolar = (op: () => Promise<void>) => {
    const p = cola.current.then(async () => {
      enVuelo.current += 1
      try {
        await op()
      } finally {
        enVuelo.current -= 1
      }
    })
    cola.current = p.catch(() => {})
    return p
  }

  const actual = () => pedidoRef.current as PedidoVista

  /** 7.5: la cantidad se guarda sola, 600 ms después del último cambio o al salir del campo. */
  const guardarCantidades = () => {
    window.clearTimeout(reloj.current)
    reloj.current = undefined
    return encolar(async () => {
      const p = actual()
      const cambios: Record<string, number> = {}
      for (const l of p.lineas) {
        const n = entero(valoresRef.current[l.producto.id] ?? '')
        if (enRango(n) && n !== l.cantidad) cambios[l.producto.id] = n
      }
      const ids = Object.keys(cambios)
      if (!ids.length) return
      const volverAtras = () => {
        setValores((v) => ({ ...v, ...Object.fromEntries(ids.map((id) => [id, String(p.lineas.find((l) => l.producto.id === id)!.cantidad)])) }))
        setErrCant((e) => ({ ...e, ...Object.fromEntries(ids.map((id) => [id, 'guardar' as const])) }))
      }
      const lineas = lineasParaGuardar(p.lineas, productos, { cantidades: cambios })
      if (!lineas) return volverAtras()
      try {
        onPedido(await reemplazarLineas(p.id, lineas, p.etag))
        setErrCant((e) => Object.fromEntries(Object.entries(e).filter(([id, t]) => !(t === 'guardar' && ids.includes(id)))))
      } catch (x) {
        if (manejar(x)) return
        volverAtras()
      }
    })
  }

  const alCambiarCantidad = (pid: string, v: string) => {
    setValores((x) => ({ ...x, [pid]: v }))
    const n = entero(v)
    if (enRango(n)) {
      if (errCant[pid]) setErrCant((e) => Object.fromEntries(Object.entries(e).filter(([id]) => id !== pid)))
      window.clearTimeout(reloj.current)
      reloj.current = window.setTimeout(() => void guardarCantidades(), 600)
    }
  }

  const alSalirCantidad = (pid: string) => {
    const n = entero(valoresRef.current[pid] ?? '')
    if (!enRango(n)) return setErrCant((e) => ({ ...e, [pid]: 'rango' }))
    if (reloj.current !== undefined) void guardarCantidades()
  }

  /** 7.6: «Si falta» se guarda al cambiar la opción; si falla, vuelve la de antes. */
  const alCambiarRegla = (l: LineaPedido, accion: Regla) => {
    const pid = l.producto.id
    setReglas((r) => ({ ...r, [pid]: accion }))
    setErrRegla((e) => ({ ...e, [pid]: false }))
    void encolar(async () => {
      const p = actual()
      try {
        onPedido(await reemplazarReglas(p.id, reglasConCambio(p.lineas, pid, accion), p.etag))
      } catch (x) {
        if (!manejar(x)) setErrRegla((e) => ({ ...e, [pid]: true }))
      } finally {
        setReglas((r) => Object.fromEntries(Object.entries(r).filter(([id]) => id !== pid)))
      }
    })
  }

  /** 7.7: sin confirmación, y la línea se queda si falla. El foco va a la siguiente, a la anterior o al título. */
  const sacar = (l: LineaPedido) => {
    const pid = l.producto.id
    if (sacando) return
    setSacando(pid)
    setErrSacar(null)
    window.clearTimeout(reloj.current)
    reloj.current = undefined
    void encolar(async () => {
      const p = actual()
      const i = p.lineas.findIndex((x) => x.producto.id === pid)
      const cambios: Record<string, number> = {}
      for (const x of p.lineas) {
        const n = entero(valoresRef.current[x.producto.id] ?? '')
        if (enRango(n)) cambios[x.producto.id] = n
      }
      const lineas = lineasParaGuardar(p.lineas, productos, { sacar: pid, cantidades: cambios })
      try {
        if (!lineas) throw new Error('oferta')
        const nuevo = await reemplazarLineas(p.id, lineas, p.etag)
        onPedido(nuevo)
        anunciar(PEDIDO.sacamos(l.producto.nombre), 'status')
        const sigue = p.lineas[i + 1] ?? p.lineas[i - 1]
        if (!nuevo.lineas.length) props.onVacio()
        enfocar(sigue && nuevo.lineas.length ? idCantidad(sigue.producto.id) : 'titulo-pagina', 60)
      } catch (x) {
        if (!manejar(x)) setErrSacar(pid)
      } finally {
        setSacando(null)
      }
    })
  }

  /** 7.9: «Ver el total». Nunca deshabilitado: valida al tocarlo. */
  const verTotal = async () => {
    if (confirmando) return
    setFalla(null)
    // Con el total vigente y sin controles, lleva al resumen sin volver a confirmar.
    if (!borrador && pedido.estado === 'total_confirmado' && esVistaCompleta(pedido)) return props.onConfirmado(pedido)
    if (borrador) {
      const malas = pedido.lineas.filter((l) => !enRango(entero(valores[l.producto.id] ?? '')))
      if (malas.length) {
        setErrCant((e) => ({ ...e, ...Object.fromEntries(malas.map((l) => [l.producto.id, 'rango' as const])) }))
        return enfocar(idCantidad(malas[0].producto.id), 0)
      }
      if (!direccion) {
        setFalla('direccion')
        return enfocar(ID_AGREGAR_DIRECCION, 0)
      }
      if (!telefono && !cuenta?.celular_verificado) {
        setErrTelefono(PEDIDO.errTelefono)
        return enfocar('telefono-contacto', 40)
      }
    }
    setConfirmando(true)
    try {
      if (borrador) {
        void guardarCantidades()
        await cola.current
        if (Object.values(errCantRef.current).some((t) => t === 'guardar')) return
      }
      const p = actual()
      props.onConfirmado(await confirmarPedido(p.id, borrador ? telefono : null))
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 409 && esTipo(f.tipo, 'sin-direccion')) {
        setFalla('direccion')
        return enfocar(ID_AGREGAR_DIRECCION, 0)
      }
      if (f.status === 409 && esTipo(f.tipo, 'nada-disponible')) return setFalla('nada')
      if (f.status === 409 && esTipo(f.tipo, 'pedido-vacio')) return props.onVacio()
      if (f.status === 422 && f.campos.some((c) => /telefono/.test(c))) {
        setErrTelefono(PEDIDO.errTelefono)
        return enfocar('telefono-contacto', 40)
      }
      if (manejar(x)) return
      setFalla('red')
    } finally {
      setConfirmando(false)
    }
  }
  /** 9.12 desde el carrito sin controles: vuelve a `borrador` con las mismas líneas. */
  const cambiar = async () => {
    if (cambiando) return
    setCambiando(true)
    setErrCambiar(false)
    try {
      props.onCambiado(await volverABorrador(pedido.id))
    } catch (x) {
      if (!manejar(x)) setErrCambiar(true)
    } finally {
      setCambiando(false)
    }
  }

  // Lo que se ve: las cantidades escritas (válidas) y la suma de los subtotales de la pantalla.
  const cantidadVista = (l: LineaPedido) => {
    const n = entero(valores[l.producto.id] ?? '')
    return borrador && enRango(n) ? n : l.cantidad
  }
  const suma = pedido.lineas.reduce((t, l) => t + cantidadVista(l) * l.precio_unitario, 0)
  const deEjemplo = pedido.precios_de_ejemplo
  const completa = esVistaCompleta(pedido)

  const izquierda = (
    <div className="flex min-w-0 flex-col gap-4">
      <p id="nunca-otra-marca" className="max-w-prose text-base font-bold">
        {PEDIDO.nuncaOtraMarca}
      </p>
      <ul className="flex flex-col gap-4">
        {pedido.lineas.map((l) => (
          <LineaCarrito
            key={l.producto.id}
            linea={l}
            editable={editable}
            deEjemplo={deEjemplo}
            valor={valores[l.producto.id] ?? String(l.cantidad)}
            cantidad={cantidadVista(l)}
            errCant={errCant[l.producto.id] ?? null}
            regla={reglas[l.producto.id] ?? l.regla_faltante}
            errRegla={!!errRegla[l.producto.id]}
            sacando={sacando === l.producto.id}
            errSacar={errSacar === l.producto.id}
            deLista={deLista[l.producto.id] ?? null}
            onCantidad={(v) => alCambiarCantidad(l.producto.id, v)}
            onSalir={() => alSalirCantidad(l.producto.id)}
            onRegla={(a) => alCambiarRegla(l, a)}
            onSacar={() => sacar(l)}
          />
        ))}
      </ul>
    </div>
  )

  const telefonoMostrado = telefono ?? cuenta?.celular_enmascarado ?? null
  const entrega = direccion !== undefined && (
    <section aria-labelledby="entrega-t" className="flex flex-col gap-4">
      <h2 id="entrega-t" className="titular text-2xl">
        {PEDIDO.entrega}
      </h2>
      <div className="flex flex-col items-start gap-1">
        <h3 className="text-lg font-bold">{PEDIDO.direccion}</h3>
        {direccion ? (
          <>
            <p className="text-base break-words">{direccionEnTexto(direccion)}</p>
            {direccion.referencia && <p className="text-base text-tenue break-words">{direccion.referencia}</p>}
            {editable && (
              <Boton id={ID_AGREGAR_DIRECCION} variante="texto" onClick={props.onAgregarDireccion}>
                {PEDIDO.cambiarDireccion}
              </Boton>
            )}
          </>
        ) : (
          <>
            <p className="text-base">{PEDIDO.sinDireccion}</p>
            {editable && (
              <Boton id={ID_AGREGAR_DIRECCION} variante="secundario" className="mt-1" onClick={props.onAgregarDireccion}>
                {PEDIDO.agregarDireccion}
              </Boton>
            )}
          </>
        )}
        {falla === 'direccion' && <MensajeError>{PEDIDO.errSinDireccion}</MensajeError>}
      </div>
      {/* 7.8: el pagador no ve el teléfono en el carrito: antes de confirmar es el celular de quien confirma. */}
      {editor && (
        <div className="flex flex-col items-start gap-1">
          <h3 id={ID_TELEFONO_T} className="text-lg font-bold">
            {PEDIDO.telefono}
          </h3>
          {completa && !borrador && pedido.entrega ? (
            <TelefonoContacto
              mostrado={pedido.entrega.telefono_contacto}
              esTuyo={pedido.entrega.telefono_es_tuyo}
              editable={false}
              abiertoAlInicio={false}
              onGuardar={async () => null}
            />
          ) : (
            <TelefonoContacto
              mostrado={telefonoMostrado}
              esTuyo={!telefono && !!cuenta?.celular_verificado}
              editable={editable}
              abiertoAlInicio={editable && !telefono && !cuenta?.celular_verificado}
              nombradoPor={ID_TELEFONO_T}
              error={errTelefono}
              onGuardar={async (t) => {
                onTelefono(t)
                setErrTelefono(null)
                return null
              }}
            />
          )}
        </div>
      )}
      <p className="text-base">{PEDIDO.llegaEntre(pedido.ventana_entrega)}</p>
    </section>
  )

  const pie = (
    <div className="flex flex-col items-start gap-3">
      <p className="text-xl">
        {PEDIDO.productos} <span className="cifras font-bold">{pesos(suma)}</span>
      </p>
      {/* Revisión P3-3: con el total confirmado o vencido, el envío y el total ya están a la vista. */}
      {borrador && <p className="max-w-prose text-base text-tenue">{PEDIDO.envioAlConfirmar}</p>}
      {editor && (
        <>
          {falla === 'red' && (
            <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
              {PEDIDO.errConfirmar}
            </Nota>
          )}
          {falla === 'nada' && (
            <Nota tono="atenta" rol="alert" icono={<PackageX aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
              {PEDIDO.nadaDisponible}
            </Nota>
          )}
          <Boton ocupado={confirmando} textoOcupado={PEDIDO.confirmando} onClick={() => void verTotal()}>
            {PEDIDO.verTotal}
          </Boton>
          {confirmando && (
            <p role="status" className="text-base">
              {PEDIDO.confirmandoEstado}
            </p>
          )}
          {!borrador && (
            <>
              <Boton variante="secundario" ocupado={cambiando} textoOcupado={PEDIDO.abriendo} onClick={() => void cambiar()}>
                {PEDIDO.cambiarPedido}
              </Boton>
              {errCambiar && <MensajeError>{PEDIDO.errCambiar}</MensajeError>}
            </>
          )}
          <Boton id={ID_CANCELAR} variante="textoPeligro" className="mt-1" onClick={() => setCancelando(true)}>
            {PEDIDO.cancelarPedido}
          </Boton>
        </>
      )}
      {!editor && (
        <>
          <p className="max-w-prose text-base text-tenue">{PEDIDO.quienPuede(pila)}</p>
          {rol === 'pagador' && !borrador && (
            <Boton variante="secundario" onClick={() => navegar(RUTA_RESUMEN)}>
              {PEDIDO.verResumen}
            </Boton>
          )}
        </>
      )}
    </div>
  )

  return (
    <>
      {nota}
      {deEjemplo && <AvisoPiloto />}
      {editor && !borrador && (
        <Nota tono="rocio">{vencido ? <p>{PEDIDO.vencido}</p> : <p>{PEDIDO.yaConfirmaste}</p>}</Nota>
      )}
      <div className="mt-2 grid grid-cols-1 gap-x-10 gap-y-10 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {izquierda}
        <div className="flex min-w-0 flex-col gap-8 @3xl/main:sticky @3xl/main:top-6 @3xl/main:max-h-[calc(100dvh-3rem)] @3xl/main:self-start @3xl/main:overflow-y-auto [scrollbar-width:thin]">
          {entrega}
          {pie}
        </div>
      </div>
      {cancelando && (
        <DialogoCancelar
          pedidoId={pedido.id}
          onCerrar={() => {
            setCancelando(false)
            enfocar(ID_CANCELAR, 0)
          }}
          onCancelado={(ya) => {
            setCancelando(false)
            props.onCancelado(ya)
          }}
          manejar={manejar}
        />
      )}
    </>
  )
}

// ---------------------------------------------------------------- 7.4 la línea

function LineaCarrito({
  linea: l,
  editable,
  deEjemplo,
  valor,
  cantidad,
  errCant,
  regla,
  errRegla,
  sacando,
  errSacar,
  deLista,
  onCantidad,
  onSalir,
  onRegla,
  onSacar,
}: {
  linea: LineaPedido
  editable: boolean
  deEjemplo: boolean
  valor: string
  cantidad: number
  errCant: ErrCant | null
  regla: Regla
  errRegla: boolean
  sacando: boolean
  errSacar: boolean
  deLista: string | null
  onCantidad: (v: string) => void
  onSalir: () => void
  onRegla: (r: Regla) => void
  onSacar: () => void
}) {
  const pid = l.producto.id
  const nombre = l.producto.nombre
  const presentacion = l.producto.presentacion.trim()
  const n = entero(valor)
  const sufijo = sufijoDelPedido(enRango(n) ? n : cantidad, l.producto)
  const derecha = '@2xl/linea:col-start-2 @2xl/linea:row-start-1 @2xl/linea:row-span-2'
  return (
    <li className="@container/linea rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
      <div className="grid grid-cols-1 gap-y-3 @2xl/linea:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] @2xl/linea:grid-rows-[auto_1fr_auto] @2xl/linea:gap-x-6">
        <div className="flex min-w-0 flex-col gap-1 @2xl/linea:col-start-1 @2xl/linea:row-start-1">
          <h2 id={idProducto(pid)} className="text-xl font-bold break-words">
            {nombre}
          </h2>
          {presentacion && presentacion !== nombre.trim() && <p className="text-base text-tenue">{presentacion}</p>}
          <p className="text-base break-words">{PEDIDO.comercio(l.comercio.nombre_fantasia, l.comercio.ficticio)}</p>
          <p className="flex flex-wrap items-baseline gap-x-2">
            <span className="cifras text-lg font-bold text-tinta">{pesos(l.precio_unitario)}</span>
            <span className="text-lg">{PEDIDO.cadaUno}</span>
          </p>
          <p className="text-base text-tenue">{deEjemplo ? PEDIDO.precioDeEjemploIva : PEDIDO.ivaIncluido}</p>
        </div>
        <div className={`flex min-w-0 flex-col gap-3 ${derecha}`}>
          {editable ? (
            <Stepper
              id={idCantidad(pid)}
              etiqueta={PEDIDO.cantidad}
              nombradoPor={idProducto(pid)}
              textoMenos={PEDIDO.quitarUno(nombre)}
              textoMas={PEDIDO.agregarUno(nombre)}
              sufijo={sufijo}
              valor={valor}
              onCambio={(v) => onCantidad(v.slice(0, 2))}
              min={1}
              max={99}
              vacioEs={0}
              seleccionarAlEnfocar
              onSalir={onSalir}
              error={errCant === 'rango' ? PEDIDO.errCantidad : errCant === 'guardar' ? PEDIDO.errGuardarCantidad : null}
            />
          ) : (
            <p className="text-lg tabular-nums">
              <span className="cifras">{cantidad}</span> {sufijoDelPedido(cantidad, l.producto)}
            </p>
          )}
          {deLista && <p className="text-base text-tenue">{PEDIDO.enTuLista(deLista)}</p>}
          <p className="text-lg">
            {PEDIDO.subtotal} <span className="cifras font-bold">{pesos(cantidad * l.precio_unitario)}</span>
          </p>
          <div className="border-t border-linea pt-3">
            {editable ? (
              <GrupoOpciones<Regla>
                leyenda={PEDIDO.siFalta}
                nombre={`si-falta-${pid}`}
                valor={regla}
                onCambio={onRegla}
                nombradoPor={idProducto(pid)}
                describe="nunca-otra-marca"
                detalleGrande
                opciones={[
                  { valor: 'otro_comercio', texto: PEDIDO.otroComercio, detalle: PEDIDO.otroComercioDetalle },
                  { valor: 'quitar', texto: PEDIDO.quitar },
                ]}
              >
                {errRegla && <MensajeError>{PEDIDO.errRegla}</MensajeError>}
              </GrupoOpciones>
            ) : (
              <p className="text-base">{siFaltaTexto(regla)}</p>
            )}
          </div>
        </div>
        {/* 7.4: el derecho antes de lo que saca la línea, lejos del campo. En ancho, bajo el precio. */}
        <Retracto pierde={l.retracto_pierde_al_abrir} className="border-t border-linea pt-3 @2xl/linea:col-start-1 @2xl/linea:row-start-2" />
        {editable && (
          <div className="flex min-w-0 flex-col items-end gap-1 @2xl/linea:col-start-2 @2xl/linea:row-start-3">
            <Boton variante="textoPeligro" aria-label={PEDIDO.sacarDe(nombre)} ocupado={sacando} className="text-right" onClick={onSacar}>
              {PEDIDO.sacar}
            </Boton>
            {errSacar && (
              <Anunciado urgencia="alert" className="self-stretch">
                <MensajeError>{PEDIDO.errSacar}</MensajeError>
              </Anunciado>
            )}
          </div>
        )}
      </div>
    </li>
  )
}

