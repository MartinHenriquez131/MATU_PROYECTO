// «¿Dónde lo entregamos?» (MATU-61, especificación 8): agregar, cambiar y vaciar la dirección de
// entrega de la persona, con `If-Match` (o `If-None-Match: *` la primera vez). No pide la
// autorización de pedidos (C8). Sin mapa, sin ubicación y sin región (C8, 8.2). Lo escrito vive en
// la memoria de la página: nunca va al almacenamiento del navegador ni a la URL.
import { useId, useRef, useState, type FormEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { TriangleAlert } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import type { PersonaListada } from '../compartido/api/familia'
import { guardarDireccion, leerConflictoDireccion, vaciarDireccion, type DireccionEntrada, type DireccionVista } from '../compartido/api/pedido'
import { esVencida } from '../compartido/api/sesion'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { enfocarPrimerError } from './Alta'
import { DialogoPedido } from './DialogoPedido'
import { useFamilia } from './estado'
import { enfocar, unaLinea } from './insumosComun'
import { PestanasInsumos } from './Insumos'
import { direccionEnTexto } from './pedidoComun'
import { GENERAL } from './textos'
import { PEDIDO } from './textosPedido'
import { Acciones, MensajeError, Nota, Titulo, Volver } from './ui'

export type DesdeDireccion = 'carrito' | 'resumen' | 'grupo'
type CampoDir = 'calle' | 'numero' | 'depto' | 'comuna' | 'referencia'
type Valores = Record<CampoDir, string>

const LARGOS: Record<CampoDir, number> = { calle: 120, numero: 20, depto: 20, comuna: 60, referencia: 200 }
const ID_VACIAR = 'vaciar-direccion'

const direccionDe = (p: PersonaListada | null): DireccionVista | null => (p && 'direccion' in p ? (p.direccion ?? null) : null)
const valoresDe = (d: DireccionVista | null): Valores => ({
  calle: d?.calle ?? '',
  numero: d?.numero ?? '',
  depto: d?.depto ?? '',
  comuna: d?.comuna ?? '',
  referencia: d?.referencia ?? '',
})

/** El cuerpo de `PUT …/direccion`. Al cambiar una guardada se reenvían su `etiqueta` y su `region` (8.2). */
function entradaDe(v: Valores, antes: DireccionVista | null): DireccionEntrada {
  const limpio = (x: string) => unaLinea(x).trim()
  return {
    ...(antes ? { etiqueta: antes.etiqueta, region: antes.region } : {}),
    calle: limpio(v.calle),
    numero: limpio(v.numero),
    depto: limpio(v.depto) || null,
    comuna: limpio(v.comuna),
    referencia: limpio(v.referencia) || null,
  }
}

function validar(v: Valores): Partial<Record<CampoDir, string>> {
  const e: Partial<Record<CampoDir, string>> = {}
  if (!v.calle.trim()) e.calle = PEDIDO.errCalle
  if (!v.numero.trim()) e.numero = PEDIDO.errNumero
  if (!v.comuna.trim()) e.comuna = PEDIDO.errComuna
  if (v.referencia.length > LARGOS.referencia) e.referencia = PEDIDO.errReferencia
  return e
}

/**
 * Un campo de texto con la ayuda **antes** del campo (8.2 y 7.8.1), en `text-base` y en su
 * `aria-describedby`. El error va debajo, con `aria-invalid`.
 */
export function CampoConAyuda({
  id: idPropio,
  etiqueta,
  ayuda,
  error,
  className = '',
  anchoCampo = 'w-full',
  ...resto
}: InputHTMLAttributes<HTMLInputElement> & {
  etiqueta: string
  ayuda?: ReactNode
  error?: string | null
  /** El ancho del `input` solo: la etiqueta y el error toman el de la columna (revisión P3-1). */
  anchoCampo?: string
}) {
  const generado = useId()
  const id = idPropio ?? generado
  const describe = [ayuda ? `${id}-a` : '', error ? `${id}-e` : ''].filter(Boolean).join(' ') || undefined
  // Revisión P3-2: nombrado por un título que ya se ve (`aria-labelledby`), sin repetir la etiqueta.
  const nombradoAfuera = !!resto['aria-labelledby']
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      {!nombradoAfuera && (
        <label htmlFor={id} className="font-bold">
          {etiqueta}
        </label>
      )}
      {ayuda && (
        <span id={`${id}-a`} className="text-base text-tenue">
          {ayuda}
        </span>
      )}
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describe}
        className={`min-h-12 ${anchoCampo} min-w-0 rounded-xl bg-hoja px-4 angosto:px-2 py-2.5 ring-2 ring-inset focus-visible:ring-turquesa ${error ? 'ring-pronto' : 'ring-borde'}`}
        {...resto}
      />
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
    </div>
  )
}

export function Direccion({
  desde,
  onGuardada,
  onDejarLaSuya,
  onVaciada,
  onVolver,
}: {
  desde: DesdeDireccion
  onGuardada: (d: DireccionVista) => void
  onDejarLaSuya: () => void
  onVaciada: () => void
  onVolver: () => void
}) {
  const { persona, personaId, personas, fijar } = useFamilia()
  const pila = persona && 'nombre_pila' in persona && persona.nombre_pila ? persona.nombre_pila : (persona?.nombre ?? '')
  const guardada = direccionDe(persona)
  const [valores, setValores] = useState<Valores>(() => valoresDe(guardada))
  const [errores, setErrores] = useState<Partial<Record<CampoDir, string>>>({})
  const [falla, setFalla] = useState<'422' | 'red' | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [conflicto, setConflicto] = useState<DireccionVista | null>(null)
  const [vaciando, setVaciando] = useState(false)
  const [avisoVaciar, setAvisoVaciar] = useState(false)
  const form = useRef<HTMLFormElement>(null)

  /** La dirección nueva (o ninguna) en la persona en memoria: el carrito y Grupo familiar la ven. */
  const enMemoria = (d: DireccionVista | null) => fijar({ personas: personas.map((p) => (p.id === personaId && 'direccion' in p ? { ...p, direccion: d } : p)) })

  const cambiar = (c: CampoDir, v: string) => {
    setValores((x) => ({ ...x, [c]: v }))
    if (errores[c]) setErrores((e) => ({ ...e, [c]: undefined }))
  }

  const enviar = async (etag: string | null, antes: DireccionVista | null) => {
    if (!personaId || ocupado) return
    setOcupado(true)
    setFalla(null)
    try {
      const nueva = await guardarDireccion(personaId, entradaDe(valores, antes), etag)
      enMemoria(nueva)
      setConflicto(null)
      onGuardada(nueva)
    } catch (x) {
      if (esVencida(x)) return
      const actual = leerConflictoDireccion(x)
      if (actual) {
        // 8.5: no se pisa lo que dejó otra persona; se elige a la vista, con el foco en el aviso.
        setConflicto(actual)
        enfocar('conflicto-direccion', 60)
        return
      }
      const f = leerFallo(x)
      if (f.status === 422) {
        const porCampo: Partial<Record<CampoDir, string>> = {}
        for (const c of f.campos) {
          const nombre = c.split('.').pop() as CampoDir
          if (nombre === 'calle') porCampo.calle = PEDIDO.errCalle
          if (nombre === 'numero') porCampo.numero = PEDIDO.errNumero
          if (nombre === 'comuna') porCampo.comuna = PEDIDO.errComuna
          if (nombre === 'referencia') porCampo.referencia = PEDIDO.errReferencia
        }
        if (Object.keys(porCampo).length) {
          setErrores(porCampo)
          enfocarPrimerError(form.current)
        } else setFalla('422')
        return
      }
      setFalla('red')
    } finally {
      setOcupado(false)
    }
  }

  const guardar = (e: FormEvent) => {
    e.preventDefault()
    const errs = validar(valores)
    setErrores(errs)
    if (Object.keys(errs).length) return enfocarPrimerError(form.current)
    void enviar(guardada?.etag ?? null, guardada)
  }

  const vaciar = async (): Promise<boolean> => {
    if (!personaId || !guardada) return true
    try {
      await vaciarDireccion(personaId, guardada.etag)
      enMemoria(null)
      setVaciando(false)
      onVaciada()
      return true
    } catch (x) {
      if (esVencida(x)) return true
      const f = leerFallo(x)
      // 404: ya no había: lo que se pidió ya pasó.
      if (f.status === 404) {
        enMemoria(null)
        setVaciando(false)
        onVaciada()
        return true
      }
      const actual = leerConflictoDireccion(x)
      if (actual) {
        enMemoria(actual)
        setValores(valoresDe(actual))
        setVaciando(false)
        setAvisoVaciar(true)
        enfocar('aviso-vaciar', 60)
        return true
      }
      return false
    }
  }

  const volverTexto = desde === 'resumen' ? PEDIDO.volverAAntesDePagar : desde === 'grupo' ? PEDIDO.volverAGrupo : PEDIDO.volverATuPedido

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <PestanasInsumos activa="/insumos/pedido" />
      <Volver onClick={onVolver}>{volverTexto}</Volver>
      <div>
        <Titulo className="text-3xl @2xl/main:text-5xl">{PEDIDO.dirTitulo}</Titulo>
        <p className="mt-1.5 max-w-prose text-base text-tenue">
          {PEDIDO.dirAyuda} {PEDIDO.dirGuardamosPara(pila)}
        </p>
      </div>
      <div className="mt-4 flex max-w-2xl flex-col gap-6">
        {avisoVaciar && (
          <Nota id="aviso-vaciar" tono="atenta" rol="alert" enfocable>
            {PEDIDO.vaciarConflicto}
          </Nota>
        )}
        {conflicto && (
          <Conflicto
            suya={conflicto}
            mia={entradaDe(valores, conflicto)}
            ocupado={ocupado}
            onGuardarLaMia={() => void enviar(conflicto.etag, conflicto)}
            onDejarLaSuya={() => {
              enMemoria(conflicto)
              setConflicto(null)
              onDejarLaSuya()
            }}
          />
        )}
        {/* 13.1: con el conflicto a la vista, «Guardar la mía» es el único macizo: el formulario espera. */}
        <form ref={form} noValidate onSubmit={guardar} hidden={!!conflicto} className="flex flex-col gap-5">
          <div className="grid grid-cols-1 gap-5 @xl/main:grid-cols-[minmax(0,1fr)_10rem]">
            <CampoConAyuda etiqueta={PEDIDO.calle} value={valores.calle} onChange={(e) => cambiar('calle', e.target.value)} autoComplete="address-line1" maxLength={LARGOS.calle} error={errores.calle} />
            <CampoConAyuda
              etiqueta={PEDIDO.numero}
              value={valores.numero}
              onChange={(e) => cambiar('numero', e.target.value)}
              autoComplete="off"
              inputMode="text"
              maxLength={LARGOS.numero}
              anchoCampo="w-40 max-w-full @xl/main:w-full"
              error={errores.numero}
            />
          </div>
          <div className="grid grid-cols-1 gap-5 @xl/main:grid-cols-[10rem_minmax(0,1fr)]">
            <CampoConAyuda
              etiqueta={PEDIDO.depto}
              value={valores.depto}
              onChange={(e) => cambiar('depto', e.target.value)}
              autoComplete="address-line2"
              maxLength={LARGOS.depto}
              anchoCampo="w-40 max-w-full @xl/main:w-full"
              error={errores.depto}
            />
            <CampoConAyuda etiqueta={PEDIDO.comuna} value={valores.comuna} onChange={(e) => cambiar('comuna', e.target.value)} autoComplete="address-level2" maxLength={LARGOS.comuna} error={errores.comuna} />
          </div>
          <CampoConAyuda
            etiqueta={PEDIDO.referencia}
            ayuda={PEDIDO.referenciaAyuda}
            value={valores.referencia}
            onChange={(e) => cambiar('referencia', e.target.value)}
            autoComplete="off"
            maxLength={LARGOS.referencia}
            error={errores.referencia}
          />
          {falla && (
            <Anunciado urgencia="alert">
              <MensajeError>{falla === '422' ? PEDIDO.errDireccion : GENERAL.error}</MensajeError>
            </Anunciado>
          )}
          <Acciones>
            <Boton type="submit" ocupado={ocupado} textoOcupado={PEDIDO.guardando}>
              {PEDIDO.guardarDireccion}
            </Boton>
          </Acciones>
        </form>
        {guardada && !conflicto && (
          <div className="mt-4 flex flex-col items-start gap-3 border-t border-linea pt-6">
            <p className="max-w-prose text-base text-tenue">{PEDIDO.vaciarFrase}</p>
            <Boton id={ID_VACIAR} variante="textoPeligro" aria-label={PEDIDO.vaciarDe(pila)} onClick={() => setVaciando(true)}>
              {PEDIDO.vaciar}
            </Boton>
          </div>
        )}
      </div>
      {vaciando && (
        <DialogoPedido
          titulo={PEDIDO.vaciarPregunta(pila)}
          texto={PEDIDO.vaciarTexto}
          confirmar={PEDIDO.vaciar}
          confirmando={PEDIDO.vaciando}
          seguir={PEDIDO.dejarla}
          error={PEDIDO.errVaciar}
          onConfirmar={vaciar}
          onCerrar={() => {
            setVaciando(false)
            enfocar(ID_VACIAR, 0)
          }}
        />
      )}
    </div>
  )
}

/** 8.5: las dos direcciones a la vista y elegir en un toque. No es un error: `atenta`, nunca `pronto`. */
function Conflicto({
  suya,
  mia,
  ocupado,
  onGuardarLaMia,
  onDejarLaSuya,
}: {
  suya: DireccionVista
  mia: DireccionEntrada
  ocupado: boolean
  onGuardarLaMia: () => void
  onDejarLaSuya: () => void
}) {
  return (
    <div className="flex flex-col gap-4">
      <Nota
        id="conflicto-direccion"
        tono="atenta"
        borde
        rol="alert"
        enfocable
        iconoEnLinea
        icono={<TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}
        titulo={PEDIDO.conflictoTitulo}
      >
        <p>{PEDIDO.conflictoTexto}</p>
      </Nota>
      <div className="grid grid-cols-1 gap-4 @xl/main:grid-cols-2">
        <div>
          <h2 className="text-lg font-bold">{PEDIDO.laQueGuardo}</h2>
          <p className="text-base break-words">{direccionEnTexto(suya)}</p>
          {suya.referencia && <p className="text-base text-tenue break-words">{suya.referencia}</p>}
        </div>
        <div>
          <h2 className="text-lg font-bold">{PEDIDO.laTuya}</h2>
          <p className="text-base break-words">{direccionEnTexto({ calle: mia.calle, numero: mia.numero, depto: mia.depto ?? null, comuna: mia.comuna })}</p>
          {mia.referencia && <p className="text-base text-tenue break-words">{mia.referencia}</p>}
        </div>
      </div>
      <Acciones>
        <Boton ocupado={ocupado} textoOcupado={PEDIDO.guardando} onClick={onGuardarLaMia}>
          {PEDIDO.guardarLaMia}
        </Boton>
        <Boton variante="secundario" onClick={onDejarLaSuya}>
          {PEDIDO.dejarLaSuya}
        </Boton>
      </Acciones>
    </div>
  )
}
