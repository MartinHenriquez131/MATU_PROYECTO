// Piezas que comparten «Tu pedido» y «Antes de pagar» (MATU-61, especificación 7, 9 y 10): la hora
// del total, la columna de un estado, el aviso del piloto, el retracto, «Si falta», el teléfono de
// contacto y el diálogo de cancelar.
import { useEffect, useState, type ReactNode } from 'react'
import { Info } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { cancelarPedido, type Pedido, type Regla } from '../compartido/api/pedido'
import { esVencida } from '../compartido/api/sesion'
import { anunciar } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { PATRON_CELULAR } from './datos'
import { CampoConAyuda } from './Direccion'
import { DialogoPedido } from './DialogoPedido'
import { enfocar, esTipo } from './insumosComun'
import { telefonoEnTexto } from './pedidoComun'
import { CATALOGO } from './textosCatalogo'
import { PEDIDO } from './textosPedido'
import { PAGO } from './textosPago'
import { Acciones, Nota } from './ui'

export const ID_CAMBIAR_TELEFONO = 'cambiar-telefono'

/** «16:45», la hora de Chile en que vence el total, del `vence_en` del servidor. */
export function horaDeVencimiento(p: Pick<Pedido, 'vence_en'>): string {
  if (!p.vence_en) return ''
  const d = new Date(p.vence_en)
  if (Number.isNaN(d.getTime())) return ''
  return new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(d)
}

/**
 * El fondo y el color de la baldosa de un estado. MATU-62 (especificación, «Tokens») suma `ok`, el
 * mismo par de `Etiqueta tono="ok"`, para «Pagaste tu pedido».
 */
export const FONDO_BALDOSA = { neutro: 'bg-tinta/7 text-tenue', atenta: 'bg-atenta-fondo text-atenta', rocio: 'bg-rocio text-turquesa', ok: 'bg-ok-fondo text-ok' } as const
export type TonoBaldosa = keyof typeof FONDO_BALDOSA

export function Baldosa({ tono, icono }: { tono: TonoBaldosa; icono: ReactNode }) {
  return <span className={`grid size-16 shrink-0 place-items-center rounded-2xl ${FONDO_BALDOSA[tono]}`}>{icono}</span>
}

export function UnaColumna({ tono, icono, children }: { tono: TonoBaldosa; icono: ReactNode; children: ReactNode }) {
  return (
    <div className="mt-2 flex flex-col items-start gap-5">
      <Baldosa tono={tono} icono={icono} />
      {children}
    </div>
  )
}

/** El aviso del piloto (lenguaje 11), una vez por pantalla con precios, arriba (12). */
export function AvisoPiloto() {
  return (
    <Nota tono="atenta" borde titulo={CATALOGO.avisoTitulo} icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />} iconoEnLinea>
      <p>{CATALOGO.aviso}</p>
    </Nota>
  )
}

/** «Derecho a retracto: …» con letra igual a la del precio (C2): `text-lg` los dos. */
export function Retracto({ pierde, className = '' }: { pierde: boolean; className?: string }) {
  return (
    <p className={`max-w-prose text-lg text-tinta ${className}`}>
      <strong className="font-bold">{PEDIDO.retractoTitulo}</strong> {PEDIDO.retracto}
      {pierde && ` ${PEDIDO.retractoSello}`}
    </p>
  )
}

export const siFaltaTexto = (r: Regla) => (r === 'quitar' ? PEDIDO.siFaltaQuitar : PEDIDO.siFaltaOtro)

/**
 * 7.8.1 y 9.7: el teléfono de contacto, con «Cambiar teléfono» que abre el campo en el lugar. Antes
 * de confirmar vive en memoria (`onGuardar` lo deja ahí); en el resumen va con `PUT …/contacto`.
 */
export function TelefonoContacto({
  mostrado,
  esTuyo,
  editable,
  abiertoAlInicio,
  error: errorFuera,
  onGuardar,
  conPrefijo = false,
  nombradoPor,
}: {
  /** Lo que se muestra: el celular enmascarado de la cuenta o el número escrito. `null` si no hay. */
  mostrado: string | null
  esTuyo: boolean
  editable: boolean
  abiertoAlInicio: boolean
  error?: string | null
  /** Guarda y devuelve el error a mostrar bajo el campo, o `null` si guardó. */
  onGuardar: (telefono: string) => Promise<string | null>
  /** 9.7: «Teléfono de contacto: {telefono}» en una línea, sin título aparte. */
  conPrefijo?: boolean
  /** Revisión P3-2: el id del título que ya dice «Teléfono de contacto». El campo se nombra con él. */
  nombradoPor?: string
}) {
  const [abierto, setAbierto] = useState(abiertoAlInicio)
  const [valor, setValor] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const errorVisto = error ?? errorFuera ?? null

  useEffect(() => {
    if (errorFuera) setAbierto(true)
  }, [errorFuera])

  const guardar = async () => {
    if (ocupado) return
    const t = valor.trim()
    if (!PATRON_CELULAR.test(t)) {
      setError(PEDIDO.errTelefono)
      enfocar('telefono-contacto', 0)
      return
    }
    setOcupado(true)
    const e = await onGuardar(t).finally(() => setOcupado(false))
    if (e) {
      setError(e)
      enfocar('telefono-contacto', 0)
      return
    }
    setError(null)
    setValor('')
    setAbierto(false)
    anunciar(PEDIDO.guardamosTelefono, 'status')
    enfocar(ID_CAMBIAR_TELEFONO)
  }

  const cerrar = () => {
    setAbierto(false)
    setError(null)
    setValor('')
    enfocar(ID_CAMBIAR_TELEFONO)
  }

  const numero = mostrado && (
    <span className="cifras angosto:whitespace-normal">{telefonoEnTexto(mostrado)}</span>
  )

  return (
    <div className="flex flex-col items-start gap-1">
      {conPrefijo ? (
        <p className="text-base">
          {PEDIDO.telefonoDe} {numero}
          {esTuyo && <span className="text-tenue"> {PEDIDO.tuCelular}</span>}
        </p>
      ) : (
        !abierto &&
        mostrado && (
          <p className="text-base">
            {numero}
            {esTuyo && <span className="text-tenue"> {PEDIDO.tuCelular}</span>}
          </p>
        )
      )}
      {editable && !abierto && (
        <Boton id={ID_CAMBIAR_TELEFONO} variante="texto" aria-expanded={false} onClick={() => setAbierto(true)}>
          {PEDIDO.cambiarTelefono}
        </Boton>
      )}
      {editable && abierto && (
        <form
          noValidate
          className="flex w-full max-w-md flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            void guardar()
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape' && mostrado) {
              e.preventDefault()
              cerrar()
            }
          }}
        >
          <CampoConAyuda
            id="telefono-contacto"
            etiqueta={PEDIDO.telefono}
            aria-labelledby={nombradoPor}
            ayuda={PEDIDO.telefonoAyuda}
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            value={valor}
            onChange={(e) => {
              setValor(e.target.value)
              if (error) setError(null)
            }}
            error={errorVisto}
          />
          <Acciones>
            <Boton type="submit" variante="secundario" ocupado={ocupado} textoOcupado={PEDIDO.guardando}>
              {PEDIDO.guardarTelefono}
            </Boton>
            {mostrado && (
              <Boton variante="texto" onClick={cerrar}>
                {PEDIDO.cancelar}
              </Boton>
            )}
          </Acciones>
        </form>
      )}
    </div>
  )
}

/** 10: «¿Cancelar este pedido?». El 409 de uno ya cancelado no es un error: lo que se pidió ya pasó. */
export function DialogoCancelar({
  pedidoId,
  pagoEnCurso = false,
  onCerrar,
  onCancelado,
  manejar,
}: {
  pedidoId: string
  /** MATU-62 (6.3): con un pago en curso, el párrafo en negrita de la anulación. */
  pagoEnCurso?: boolean
  onCerrar: () => void
  onCancelado: (yaCancelado: boolean) => void
  manejar: (x: unknown) => boolean
}) {
  return (
    <DialogoPedido
      titulo={PEDIDO.cancelarPregunta}
      texto={PEDIDO.cancelarTexto}
      destacado={pagoEnCurso ? PAGO.cancelarConPago : undefined}
      confirmar={PEDIDO.cancelarPedido}
      confirmando={PEDIDO.cancelando}
      seguir={PEDIDO.seguir}
      error={PEDIDO.errCancelar}
      onConfirmar={async () => {
        try {
          await cancelarPedido(pedidoId)
          onCancelado(false)
          return true
        } catch (x) {
          if (esVencida(x)) return true
          const f = leerFallo(x)
          if (f.status === 409 && esTipo(f.tipo, 'estado-pedido')) {
            onCancelado(true)
            return true
          }
          if (f.status === 404) {
            onCancelado(true)
            return true
          }
          if (f.status !== null && manejar(x)) return true
          return false
        }
      }}
      onCerrar={onCerrar}
    />
  )
}

