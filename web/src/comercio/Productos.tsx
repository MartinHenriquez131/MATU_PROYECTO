// Tus productos (especificación MATU-63, sección 8): cuántos tiene de cada producto y si lo ofrece en
// MATU. El precio se lee y no se edita (D-63-2). Un solo editor abierto a la vez: su «Guardar» es la
// única acción principal de la pantalla en ese momento.
import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Ban, TriangleAlert } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { cambiarProducto, listarProductos, type ProductoDelComercio, type SolicitudProducto } from '../compartido/api/comercio'
import { esVencida } from '../compartido/api/sesion'
import { anunciar } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { pesos } from '../familia/textosCatalogo'
import { Acciones, CampoTexto, Etiqueta, MensajeError, Titulo } from '../familia/ui'
import { useComercio } from './estado'
import { Pie, RotuloPiloto } from './Marco'
import { PRODUCTOS as T } from './textos'

const ordenar = (lista: ProductoDelComercio[]) =>
  [...lista].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es-CL') || a.presentacion.localeCompare(b.presentacion, 'es-CL'))

const idCambiar = (oferta: string) => `cambiar-${oferta}`

export function PantallaProductos() {
  const { contacto, quedoInactiva } = useComercio()
  const [productos, setProductos] = useState<ProductoDelComercio[] | null>(null)
  const [error, setError] = useState(false)
  const [abierto, setAbierto] = useState<string | null>(null)
  const verCargando = useDemora(1000)

  const traer = useCallback(async (): Promise<ProductoDelComercio[] | null> => {
    try {
      const lista = ordenar(await listarProductos())
      setProductos(lista)
      setError(false)
      return lista
    } catch (x) {
      if (esVencida(x)) return null
      if (leerFallo(x).status === 403) {
        quedoInactiva()
        return null
      }
      setError(true)
      return null
    }
  }, [quedoInactiva])

  useEffect(() => {
    void traer()
  }, [traer])

  const reemplazar = (p: ProductoDelComercio) => setProductos((l) => l?.map((x) => (x.oferta_id === p.oferta_id ? p : x)) ?? l)

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Titulo className="text-3xl">{T.titulo}</Titulo>
        <p className="max-w-prose text-base text-tenue">{T.bajada}</p>
      </div>
      {error && (
        <div className="flex flex-col items-start gap-3">
          <Nota tono="pronto" rol="alert">
            {T.errorAlTraer}
          </Nota>
          <Boton variante="secundario" onClick={() => void traer()}>
            {T.volverAIntentar}
          </Boton>
        </div>
      )}
      {productos === null && !error && (
        <p className="text-tenue" aria-busy="true">
          {verCargando ? T.cargando : ''}
        </p>
      )}
      {productos && !productos.length && (
        <div className="flex flex-col gap-1">
          <p className="text-xl font-bold">{T.vacioTitulo}</p>
          <p className="break-words text-tenue">{T.vacioTexto(contacto)}</p>
        </div>
      )}
      {productos && productos.length > 0 && (
        <ul className="flex flex-col gap-3">
          {productos.map((p) => (
            <li key={p.oferta_id}>
              <FilaProducto
                producto={p}
                abierto={abierto === p.oferta_id}
                otroAbierto={abierto !== null && abierto !== p.oferta_id}
                onAbrir={() => setAbierto(p.oferta_id)}
                onCerrar={() => setAbierto(null)}
                onCambio={reemplazar}
                recargar={traer}
                onInactiva={quedoInactiva}
              />
            </li>
          ))}
        </ul>
      )}
      <RotuloPiloto texto={T.rotuloTexto} />
      <Pie />
    </div>
  )
}

type Aviso = 'otra-persona' | 'red' | 'casilla' | null

function FilaProducto({
  producto: p,
  abierto,
  otroAbierto,
  onAbrir,
  onCerrar,
  onCambio,
  recargar,
  onInactiva,
}: {
  producto: ProductoDelComercio
  abierto: boolean
  otroAbierto: boolean
  onAbrir: () => void
  onCerrar: () => void
  onCambio: (p: ProductoDelComercio) => void
  recargar: () => Promise<ProductoDelComercio[] | null>
  onInactiva: () => void
}) {
  const { comercio } = useComercio()
  const id = useId()
  const [valor, setValor] = useState('')
  const [errorCampo, setErrorCampo] = useState<string | null>(null)
  const [aviso, setAviso] = useState<Aviso>(null)
  const [guardando, setGuardando] = useState(false)
  const [ofreciendo, setOfreciendo] = useState(false)
  const form = useRef<HTMLFormElement>(null)

  const enfocarCambiar = () => window.setTimeout(() => document.getElementById(idCambiar(p.oferta_id))?.focus(), 0)

  const abrir = () => {
    setValor(String(p.stock))
    setErrorCampo(null)
    setAviso(null)
    onAbrir()
    window.setTimeout(() => form.current?.querySelector<HTMLInputElement>('input')?.focus(), 0)
  }

  const cerrar = () => {
    onCerrar()
    setErrorCampo(null)
    setAviso(null)
    enfocarCambiar()
  }

  /** 412: se vuelve a pedir la lista y se muestra cómo quedó; el editor sigue con lo escrito. */
  const otraVersion = async () => {
    await recargar()
    setAviso('otra-persona')
  }

  /** Lo que es común a guardar la cantidad y la casilla. `true` si ya se resolvió aquí. */
  const fallo = async (x: unknown): Promise<boolean> => {
    if (esVencida(x)) return true
    const s = leerFallo(x).status
    if (s === 403) return onInactiva(), true
    if (s === 412) return await otraVersion(), true
    return false
  }

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (guardando) return
    const limpio = valor.trim()
    if (!/^\d+$/.test(limpio)) {
      setErrorCampo(T.errNumero)
      return form.current?.querySelector<HTMLInputElement>('input')?.focus()
    }
    const n = Number.parseInt(limpio, 10)
    if (n > 9999) {
      setErrorCampo(T.errMaximo)
      return form.current?.querySelector<HTMLInputElement>('input')?.focus()
    }
    setErrorCampo(null)
    setAviso(null)
    setGuardando(true)
    try {
      const nuevo = await cambiarProducto(p.oferta_id, { stock: n } satisfies SolicitudProducto, p.etag)
      onCambio(nuevo)
      onCerrar()
      anunciar(T.guardado(nuevo.stock, nuevo.nombre), 'status')
      enfocarCambiar()
    } catch (x) {
      if (!(await fallo(x))) setAviso('red')
    } finally {
      setGuardando(false)
    }
  }

  const ofrecer = async (disponible: boolean) => {
    if (ofreciendo) return
    setOfreciendo(true)
    setAviso(null)
    try {
      onCambio(await cambiarProducto(p.oferta_id, { disponible }, p.etag))
    } catch (x) {
      if (!(await fallo(x))) setAviso('casilla')
    } finally {
      setOfreciendo(false)
    }
  }

  const sinDisponibles = p.disponibles <= 0
  return (
    <article
      aria-labelledby={`${id}-n`}
      className="flex flex-col gap-3 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea @xl/main:grid @xl/main:grid-cols-[minmax(0,1fr)_auto] @xl/main:gap-x-8"
    >
      <div className="flex min-w-0 flex-col gap-1">
        <h2 id={`${id}-n`} className="text-lg font-bold break-words">
          {p.nombre}
        </h2>
        <p className="text-tenue">{p.presentacion}</p>
        <p>
          <span className="cifras">{pesos(p.precio)}</span>
          {comercio?.ficticio && <span className="text-tenue"> · {T.precioDeEjemplo}</span>}
        </p>
        <label className="flex min-h-12 max-w-full cursor-pointer items-center gap-3 font-bold">
          <input
            type="checkbox"
            checked={p.disponible}
            aria-busy={ofreciendo || undefined}
            onChange={(e) => void ofrecer(e.target.checked)}
            className="size-6 shrink-0 accent-turquesa"
          />
          {T.loOfreces}
        </label>
        {!p.disponible && (
          <div className="flex flex-col items-start gap-1">
            <Etiqueta>
              <Ban aria-hidden className="size-4 shrink-0" />
              {T.noSeOfrece}
            </Etiqueta>
            {p.apartado > 0 && <p className="text-tenue">{T.apartadoSigue}</p>}
          </div>
        )}
        {aviso === 'casilla' && <MensajeError>{T.noPudimosGuardar}</MensajeError>}
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 angosto:grid-cols-1">
          <dt className="text-tenue">{T.tienes}</dt>
          <dd className="cifras text-right angosto:text-left">{p.stock}</dd>
          <dt className="text-tenue">{T.apartados}</dt>
          <dd className="cifras text-right angosto:text-left">{p.apartado}</dd>
          <dt className="font-bold text-tenue">{T.disponibles}</dt>
          <dd className="flex flex-wrap items-center justify-end gap-2 font-bold angosto:justify-start">
            {sinDisponibles && (
              <Etiqueta tono="atenta">
                <TriangleAlert aria-hidden className="size-4 shrink-0" />
                {T.sinDisponibles}
              </Etiqueta>
            )}
            <span className="cifras">{Math.max(0, p.disponibles)}</span>
          </dd>
        </dl>
        {p.stock < p.apartado && <Nota tono="atenta">{T.menosQueApartados}</Nota>}
        {aviso === 'otra-persona' && (
          <Nota tono="atenta" rol="status">
            {T.otraPersona}
          </Nota>
        )}
        {abierto ? (
          <form ref={form} noValidate className="flex flex-col gap-3" onSubmit={(e) => void guardar(e)}>
            <CampoTexto
              etiqueta={T.cuantosAhora}
              inputMode="numeric"
              autoComplete="off"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              ayuda={T.ayuda}
              error={errorCampo}
              className="[&_input]:max-w-40"
            />
            {aviso === 'red' && <MensajeError>{T.error}</MensajeError>}
            <Acciones>
              <Boton type="submit" ocupado={guardando} textoOcupado={T.guardando}>
                {T.guardar}
              </Boton>
              <Boton variante="texto" onClick={cerrar}>
                {T.cancelar}
              </Boton>
            </Acciones>
          </form>
        ) : (
          !otroAbierto && (
            <Acciones>
              <Boton id={idCambiar(p.oferta_id)} variante="secundario" onClick={abrir}>
                {T.cambiar}
              </Boton>
            </Acciones>
          )
        )}
      </div>
    </article>
  )
}
