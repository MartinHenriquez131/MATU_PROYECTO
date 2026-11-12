// «Dónde entraste» (MATU-55, especificación docs/diseno/matu-55-donde-entraste.md v1.1, sección 2):
// los teléfonos y computadores con la cuenta abierta y los últimos ingresos de la propia cuenta.
// Cada sección pide lo suyo al abrir la página y nada se guarda en el navegador (C6). «Cerrar en ese
// teléfono» confirma en un diálogo y espera el 204: sin interfaz optimista.
import { Fragment, useCallback, useEffect, useId, useRef, useState } from 'react'
import { Bell, BellOff, CircleDot, Download, Globe, KeyRound, Laptop, LogIn, LogOut, MonitorSmartphone, Phone, ShieldAlert, Smartphone } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  cerrarDispositivo,
  leerIngresos,
  listarDispositivos,
  type ClaseDispositivo,
  type Dispositivo,
  type EventoCuenta,
  type UltimosIngresos,
} from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { diaRelativoDeChile, diasAtrasEnChile, fechaYHoraDeChile } from '../compartido/fechas'
import { Boton } from '../compartido/ui/Boton'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { useCorreoPrivacidad } from './Cuenta'
import { DialogoConfirmar } from './DialogoConfirmar'
import { useDemora } from './Estados'
import { useFamilia } from './estado'
import { navegar } from './ruteo'
import { Cola, Etiqueta, Nota, Pagina, Volver } from './ui'
import { CUENTA_PROPIA, GENERAL, MARCO } from './textos'
import { DONDE, FRASE_INGRESO } from './textosDondeEntraste'

type Carga<T> = { estado: 'cargando' } | { estado: 'error' } | { estado: 'lista'; datos: T }

/** Una lectura que se pide al montar. `recargar(true)` la vuelve a pedir sin pasar por «Cargando…». */
function useLectura<T>(leer: () => Promise<T>, valida: (t: T) => boolean = () => true) {
  const [carga, setCarga] = useState<Carga<T>>({ estado: 'cargando' })
  const vivo = useRef(true)
  const recargar = useCallback(
    async (silencio = false) => {
      if (!silencio) setCarga({ estado: 'cargando' })
      try {
        const datos = await leer()
        if (!vivo.current) return
        if (valida(datos)) setCarga({ estado: 'lista', datos })
        else if (!silencio) setCarga({ estado: 'error' })
      } catch (x) {
        if (!vivo.current || esVencida(x)) return
        // Una recarga silenciosa que falla deja lo que ya se veía.
        if (!silencio) setCarga({ estado: 'error' })
      }
    },
    // `leer` y `valida` no cambian entre renders: se leen una vez.
    [],
  )
  useEffect(() => {
    vivo.current = true
    void recargar()
    return () => {
      vivo.current = false
    }
  }, [recargar])
  return { carga, setCarga, recargar }
}

function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.cargando : ''}
    </p>
  )
}

function ErrorLectura({ texto, reintentar }: { texto: string; reintentar: () => void }) {
  return (
    <div className="flex max-w-prose flex-col items-start gap-4">
      <Nota tono="pronto" rol="alert">
        {texto}
      </Nota>
      <Boton variante="secundario" onClick={reintentar}>
        {GENERAL.volverAIntentar}
      </Boton>
    </div>
  )
}

const instanteValido = (iso: string | null | undefined) => !!iso && !Number.isNaN(new Date(iso).getTime())

export const iconoClase = (clase: ClaseDispositivo) => (clase === 'telefono' ? Smartphone : clase === 'computador' ? Laptop : Globe)

/** «Última vez: hoy a las 10:14» (2.4): «hoy», «ayer» o DD/MM/AAAA, y la hora, en dos `cifras`. */
function UltimaVez({ iso }: { iso: string }) {
  const d = new Date(iso)
  const { fecha, hora } = fechaYHoraDeChile(d)
  const atras = diasAtrasEnChile(d, new Date())
  const dia = atras <= 0 ? DONDE.hoy : atras === 1 ? DONDE.ayer : fecha
  return (
    <p className="text-base text-tenue tabular-nums">
      {DONDE.ultimaVez}{' '}
      <time dateTime={iso} title={`${fecha} ${hora}`}>
        <span className="cifras">{dia}</span> {DONDE.aLas} <span className="cifras">{hora}</span>
      </time>
    </p>
  )
}

/** 2.4: una fila de «Tus teléfonos y computadores». El orden es el del servidor. */
export function FilaDispositivo({ d, onSalir, onCerrar }: { d: Dispositivo; onSalir: () => void; onCerrar: (d: Dispositivo) => void }) {
  const uid = useId()
  const Icono = iconoClase(d.clase)
  const ultima = instanteValido(d.ultimo_uso_en) ? d.ultimo_uso_en! : d.creado_en
  return (
    <li className="flex items-start gap-3 py-4 angosto:flex-col angosto:gap-2">
      <Icono aria-hidden className="mt-0.5 size-6 shrink-0 text-tenue" />
      <div className="flex min-w-0 flex-col items-start gap-1 angosto:self-stretch">
        <p id={`${uid}-n`} className="max-w-full font-bold break-words">
          {d.nombre}
        </p>
        {d.actual && (
          <Etiqueta tono="activo">
            <CircleDot aria-hidden className="size-4 shrink-0" />
            {DONDE.este(d.clase)}
          </Etiqueta>
        )}
        {instanteValido(ultima) && <UltimaVez iso={ultima} />}
        {d.actual ? (
          <Boton variante="texto" icono={<LogOut aria-hidden className="size-5" />} onClick={onSalir}>
            {MARCO.salir}
          </Boton>
        ) : (
          <Boton id={idCerrar(d.id)} variante="peligro" className="mt-1 self-start angosto:self-stretch" aria-describedby={`${uid}-n`} onClick={() => onCerrar(d)}>
            {DONDE.cerrarEnEse(d.clase)}
          </Boton>
        )}
      </div>
    </li>
  )
}

const idCerrar = (id: string) => `cerrar-${id}`

/** Los diez tipos (2.5): diez formas, y dos de ellas en `atenta`. Nunca `pronto`. */
const ICONO_INGRESO: Record<EventoCuenta['tipo'], typeof LogIn> = {
  entraste: LogIn,
  saliste: LogOut,
  cerraste_en_dispositivo: MonitorSmartphone,
  salida_por_seguridad: ShieldAlert,
  contrasena_cambiada: KeyRound,
  celular_confirmado: Phone,
  codigo_recuperacion_pedido: ShieldAlert,
  avisos_activados: Bell,
  avisos_desactivados: BellOff,
  avisos_cambiados: Bell,
  // MATU-54 (5.5): la cola dice solo la hora, como los tipos de la cuenta sin dispositivo.
  pediste_una_copia: Download,
}
const ATENTA = new Set<EventoCuenta['tipo']>(['salida_por_seguridad', 'codigo_recuperacion_pedido'])
const CON_COLA = new Set<EventoCuenta['tipo']>(['entraste', 'saliste'])

/** Un tipo que el cliente no conoce no se muestra (contrato, `TipoEventoCuenta`). */
export const seMuestra = (e: EventoCuenta) => Object.hasOwn(FRASE_INGRESO, e.tipo) && instanteValido(e.ocurrido_en)

/** 2.5: una línea de «Últimos ingresos», con el patrón de `LineaApertura` (MATU-45, 4.3). */
export function LineaIngreso({ e, foco }: { e: EventoCuenta; foco?: React.Ref<HTMLLIElement> }) {
  const Icono = ICONO_INGRESO[e.tipo]
  const atenta = ATENTA.has(e.tipo)
  const nombre = e.dispositivo?.nombre ?? DONDE.yaNoEnLista
  const { fecha, hora } = fechaYHoraDeChile(new Date(e.ocurrido_en))
  let cola = null
  if (CON_COLA.has(e.tipo)) {
    // MATU-107 (4): la cola con «·» de la pieza Cola.
    let texto = e.dispositivo ? e.dispositivo.nombre : `en ${DONDE.yaNoEnLista}`
    if (e.dispositivo?.actual) texto += ` ${DONDE.esteEntreParentesis(e.dispositivo.clase)}`
    cola = <Cola>{texto}</Cola>
  }
  return (
    // MATU-54 (3.4.10): con `foco`, es la primera línea nueva de «Ver más» y recibe el foco.
    <li ref={foco} tabIndex={foco ? -1 : undefined} className="flex items-start gap-3 border-b border-linea py-3 outline-none last:border-0 angosto:flex-col angosto:gap-2">
      <span aria-hidden className={`mt-0.5 grid size-9 shrink-0 place-items-center rounded-full ${atenta ? 'bg-atenta-fondo text-atenta' : 'bg-rocio text-turquesa'}`}>
        <Icono className="size-5" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="font-bold leading-snug break-words">{FRASE_INGRESO[e.tipo](nombre)}</span>
        <span className="text-base text-tenue tabular-nums break-words">
          {DONDE.aLas}{' '}
          <time dateTime={e.ocurrido_en} title={`${fecha} ${hora}`} className="cifras">
            {hora}
          </time>
          {cola}
        </span>
        {e.tipo === 'codigo_recuperacion_pedido' && <span className="mt-1 text-base text-tenue">{DONDE.codigoNoCompartas}</span>}
      </span>
    </li>
  )
}

/** Las líneas agrupadas por día de Chile, con un h3 por día (el h2 es «Últimos ingresos»). */
function IngresosPorDia({ eventos }: { eventos: EventoCuenta[] }) {
  const ahora = new Date()
  const grupos: { dia: string; desde: number; lineas: EventoCuenta[] }[] = []
  eventos.forEach((e, i) => {
    const dia = diaRelativoDeChile(new Date(e.ocurrido_en), ahora)
    const ultimo = grupos[grupos.length - 1]
    if (ultimo && ultimo.dia === dia) ultimo.lineas.push(e)
    else grupos.push({ dia, desde: i, lineas: [e] })
  })
  return (
    <div className="flex max-w-prose flex-col">
      {grupos.map((g, n) => (
        <Fragment key={`${g.dia}-${g.desde}`}>
          <h3 className={`text-lg font-bold ${n ? 'mt-6' : ''}`}>{g.dia}</h3>
          <ol className="flex flex-col">
            {g.lineas.map((e, j) => (
              <LineaIngreso key={`${e.tipo}-${e.ocurrido_en}-${g.desde + j}`} e={e} />
            ))}
          </ol>
        </Fragment>
      ))}
    </div>
  )
}

/** 2.5: lo que no se muestra, según `hay_mas`, con el correo de contacto de la política. */
function LoQueNoSeMuestra({ hayMas, correo }: { hayMas: boolean; correo: string | null }) {
  if (!correo) return hayMas ? <p className="max-w-prose text-base text-tenue">{DONDE.conMasSinCorreo}</p> : null
  const [antes, despues] = hayMas ? DONDE.anterioresConMas : DONDE.anterioresSinMas
  return (
    <p className="max-w-prose text-base text-tenue">
      {antes}
      <EnlaceEnFrase href={`mailto:${correo}`} className="[overflow-wrap:anywhere]">
        {correo}
      </EnlaceEnFrase>
      {despues}
    </p>
  )
}

const ID_AVISO = 'aviso-donde-entraste'

type Aviso = { tono: 'ok' | 'atenta'; texto: string } | null

// ---------------------------------------------------------------- la pantalla

export function DondeEntraste() {
  const { salir } = useFamilia()
  const correo = useCorreoPrivacidad()
  const dispositivos = useLectura(listarDispositivos, (items) => items.length > 0)
  const ingresos = useLectura<UltimosIngresos>(leerIngresos)
  const [cerrando, setCerrando] = useState<Dispositivo | null>(null)
  const [aviso, setAviso] = useState<Aviso>(null)
  useEffect(() => {
    if (aviso) document.getElementById(ID_AVISO)?.focus()
  }, [aviso])

  const lista = dispositivos.carga.estado === 'lista' ? dispositivos.carga.datos : []
  const eventos = ingresos.carga.estado === 'lista' ? ingresos.carga.datos.eventos.filter(seMuestra) : []
  // E1: la clase del dispositivo actual. Si su lista no llegó, la de un ingreso hecho desde aquí.
  const claseActual = lista.find((d) => d.actual)?.clase ?? eventos.find((e) => e.dispositivo?.actual)?.dispositivo?.clase ?? null

  const quitar = (id: string) => dispositivos.setCarga((c) => (c.estado === 'lista' ? { estado: 'lista', datos: c.datos.filter((d) => d.id !== id) } : c))

  const confirmarCierre = async (d: Dispositivo): Promise<boolean> => {
    try {
      await cerrarDispositivo(d.id)
      quitar(d.id)
      setAviso({ tono: 'ok', texto: DONDE.cerramos(d.nombre) })
      setCerrando(null)
      // Para que aparezca «Cerraste MATU en…».
      void ingresos.recargar(true)
      return true
    } catch (x) {
      // 401: lo resuelve el cliente de la app (la entrada venció).
      if (esVencida(x)) return true
      if (leerFallo(x).status === 404) {
        quitar(d.id)
        setAviso({ tono: 'atenta', texto: DONDE.yaNoEstaba(d.clase) })
        setCerrando(null)
        return true
      }
      return false
    }
  }

  let cuerpoDispositivos
  if (dispositivos.carga.estado === 'cargando') cuerpoDispositivos = <Cargando />
  else if (dispositivos.carga.estado === 'error') cuerpoDispositivos = <ErrorLectura texto={DONDE.errDispositivos} reintentar={() => void dispositivos.recargar()} />
  else
    cuerpoDispositivos = (
      <ul className="flex flex-col divide-y divide-linea rounded-xl bg-hoja px-4 angosto:px-2 ring-1 ring-linea">
        {lista.map((d) => (
          <FilaDispositivo key={d.id} d={d} onSalir={() => void salir()} onCerrar={(x) => setCerrando(x)} />
        ))}
      </ul>
    )

  let cuerpoIngresos
  if (ingresos.carga.estado === 'cargando') cuerpoIngresos = <Cargando />
  else if (ingresos.carga.estado === 'error') cuerpoIngresos = <ErrorLectura texto={DONDE.errIngresos} reintentar={() => void ingresos.recargar()} />
  else
    cuerpoIngresos = (
      <>
        {eventos.length ? (
          <>
            <IngresosPorDia eventos={eventos} />
            <p className="max-w-prose text-base">{DONDE.noReconoces(claseActual)}</p>
          </>
        ) : (
          <Nota tono="rocio">{DONDE.vacio}</Nota>
        )}
        <LoQueNoSeMuestra hayMas={ingresos.carga.datos.hay_mas} correo={correo} />
      </>
    )

  return (
    <Pagina titulo={DONDE.titulo} bajada={DONDE.bajada} antes={<Volver onClick={() => navegar('/cuenta')}>{CUENTA_PROPIA.volver}</Volver>}>
      <div className="grid grid-cols-1 items-start gap-10 @3xl/main:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <section aria-labelledby="dispositivos-t" className="flex min-w-0 flex-col gap-4">
          <h2 id="dispositivos-t" className="text-xl font-bold leading-snug">
            {DONDE.tusDispositivos}
          </h2>
          {aviso && (
            <Nota id={ID_AVISO} tono={aviso.tono} rol="status" enfocable>
              {aviso.texto}
            </Nota>
          )}
          {cuerpoDispositivos}
        </section>
        <section aria-labelledby="ingresos-t" className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h2 id="ingresos-t" className="text-xl font-bold leading-snug">
              {DONDE.ultimos}
            </h2>
            <p className="max-w-prose text-base text-tenue">{DONDE.ultimosBajada}</p>
          </div>
          {cuerpoIngresos}
        </section>
      </div>
      {cerrando && (
        <DialogoConfirmar
          titulo={DONDE.dialogoTitulo(cerrando.nombre)}
          texto={DONDE.dialogoTexto}
          confirmar={DONDE.cerrarEnEse(cerrando.clase)}
          confirmando={DONDE.cerrando}
          seguir={DONDE.dejarloAbierto}
          error={DONDE.errCerrar(cerrando.clase)}
          onConfirmar={() => confirmarCierre(cerrando)}
          onCerrar={() => {
            const id = cerrando.id
            setCerrando(null)
            window.setTimeout(() => document.getElementById(idCerrar(id))?.focus(), 0)
          }}
        />
      )}
    </Pagina>
  )
}
