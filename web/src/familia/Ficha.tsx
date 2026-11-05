// La ficha y su editor (especificación 3.6 a 3.9), copiados de `TuFicha`, `Completar`, `Guardado`
// y `Conflicto` de la demo (Demo/src/familia/Ficha.tsx). Guardado por campo contra la API con
// `If-Match` / `If-None-Match: *`, sin interfaz optimista: la ficha cambia solo con la respuesta, y
// un 412 se muestra como conflicto, nunca se esconde.
import { useCallback, useEffect, useRef, useState } from 'react'
import { ExternalLink, Lock, PencilLine, ShieldAlert, ShieldQuestion, TriangleAlert, WifiOff } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { guardarCampo, leerConflicto, leerFicha, nombrePilaDe, type CampoApi, type Conflicto as DatosConflicto, type EstadoCampo, type Ficha } from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { AVISO_CONTADOR, CAMPOS, MAX_CARACTERES, type Campo } from './datos'
import { BotonDictar, useDictado } from './Dictado'
import { puedeEditar, puedeVerFicha, useFamilia } from './estado'
import { navegar } from './ruteo'
import { Acciones, BarraCampos, camposListos, Cuando, HojaFicha, horaDe, Listo, MensajeError, Nota, Pagina, Titulo, Volver } from './ui'
import { CONFLICTO, ESTADOS, FICHA, GENERAL, MAS } from './textos'
import { useDemora } from './Estados'
import { UltimasAperturas } from './QuienLaVio'
import { MasSobre, seccionesEnHoja } from './Secciones'
import type { SeccionEnHoja } from './ui'

export type Bloqueo = 'sin-consentimiento' | 'revision-vencida' | 'sin-acceso'
type Carga = { tipo: 'cargando' } | { tipo: 'lista' } | { tipo: 'bloqueo'; bloqueo: Bloqueo } | { tipo: 'red' }

export function bloqueoDe(e: unknown): Bloqueo | 'red' {
  const f = leerFallo(e)
  if (f.status === 403 && f.tipo === '/errores/revision-vencida') return 'revision-vencida'
  if (f.status === 403) return 'sin-consentimiento'
  if (f.status === 404) return 'sin-acceso'
  return 'red'
}

const textosDe = (f: Ficha | null): Record<CampoApi, string | null> => ({
  rutina: f?.campos.rutina.texto ?? null,
  manejo_situaciones: f?.campos.manejo_situaciones.texto ?? null,
  red_apoyo: f?.campos.red_apoyo.texto ?? null,
})
const listo = (c: EstadoCampo | undefined) => !!c?.texto?.trim()

/** Carga la ficha de la persona elegida si no está en memoria. */
export function useFicha() {
  const { ficha, personaId, rol, grupo, fijar } = useFamilia()
  const permitido = puedeVerFicha(rol, grupo)
  const [carga, setCarga] = useState<Carga>(() => (!permitido ? { tipo: 'bloqueo', bloqueo: 'sin-acceso' } : ficha ? { tipo: 'lista' } : { tipo: 'cargando' }))
  const pedir = useCallback(async () => {
    if (!personaId) return
    setCarga({ tipo: 'cargando' })
    try {
      const f = await leerFicha(personaId)
      fijar({ ficha: f })
      setCarga({ tipo: 'lista' })
    } catch (e) {
      if (esVencida(e)) return
      const b = bloqueoDe(e)
      setCarga(b === 'red' ? { tipo: 'red' } : { tipo: 'bloqueo', bloqueo: b })
    }
  }, [personaId, fijar])
  useEffect(() => {
    // El observador nunca pide la ficha (2.2).
    if (!permitido) return setCarga({ tipo: 'bloqueo', bloqueo: 'sin-acceso' })
    if (ficha && ficha.persona_id === personaId) return setCarga({ tipo: 'lista' })
    void pedir()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personaId, permitido])
  return { carga, pedir }
}

// ---------------------------------------------------------------- estados de la ficha

/** 5.6: sin acceso a la ficha. Sabemos que la persona es del grupo, así que no revela nada. */
export function SinAcceso() {
  const { persona } = useFamilia()
  return (
    <Pagina titulo={FICHA.titulo}>
      <Nota tono="rocio" icono={<Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
        {ESTADOS.sinAcceso(persona?.nombre ?? '')}
      </Nota>
    </Pagina>
  )
}

/** 6.4 y 6.4b: avisos, no errores en rojo. Si había texto escrito, se muestra para copiarlo. */
export function Bloqueada({ bloqueo, escrito }: { bloqueo: 'sin-consentimiento' | 'revision-vencida'; escrito?: string }) {
  const { persona } = useFamilia()
  const pila = persona ? nombrePilaDe(persona) : ''
  const revision = bloqueo === 'revision-vencida'
  return (
    <Pagina titulo={FICHA.titulo}>
      <div className="flex max-w-prose flex-col gap-5">
        <Nota
          tono="atenta"
          borde
          rol="status"
          icono={revision ? <ShieldAlert aria-hidden className="mt-0.5 size-6 shrink-0 text-atenta" /> : <ShieldQuestion aria-hidden className="mt-0.5 size-6 shrink-0 text-atenta" />}
          titulo={revision ? FICHA.revisionTitulo(pila) : FICHA.sinConsentimientoTitulo(pila)}
        >
          {revision ? (
            <div className="flex flex-col gap-2">
              <p>{FICHA.revision}</p>
              <p>{FICHA.revisionPide}</p>
              <p>
                <a
                  href={FICHA.chileAtiendeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-12 min-w-0 max-w-full flex-wrap items-center gap-x-1.5 font-bold text-turquesa underline underline-offset-4 wrap-anywhere"
                >
                  {FICHA.chileAtiende}
                  <ExternalLink aria-hidden className="size-4 shrink-0" />
                  <span className="font-normal">{FICHA.chileAtiendeNota}</span>
                </a>
              </p>
            </div>
          ) : (
            <p>{FICHA.sinConsentimiento}</p>
          )}
        </Nota>
        {escrito && <TextoParaCopiar texto={escrito} aviso={FICHA.loEscrito} />}
      </div>
    </Pagina>
  )
}

function TextoParaCopiar({ texto, aviso }: { texto: string; aviso: string }) {
  return (
    <section className="flex flex-col gap-2">
      <p className="font-bold">{aviso}</p>
      <p className="max-w-prose rounded-xl bg-hoja px-4 py-3 whitespace-pre-line ring-1 ring-linea select-text">{texto}</p>
    </section>
  )
}

export function ErrorAlCargar({ reintentar }: { reintentar: () => void }) {
  return (
    <div className="flex max-w-prose flex-col items-start gap-4">
      <Nota tono="pronto" rol="alert" icono={<WifiOff aria-hidden className="mt-0.5 size-5 shrink-0 text-pronto" />}>
        {GENERAL.errorAlCargar}
      </Nota>
      <Boton variante="secundario" onClick={reintentar}>
        {GENERAL.volverAIntentar}
      </Boton>
    </div>
  )
}

function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.cargando : ''}
    </p>
  )
}

export function Estado({ carga, pedir }: { carga: Carga; pedir: () => void }) {
  if (carga.tipo === 'cargando')
    return (
      <Pagina titulo={FICHA.titulo}>
        <Cargando />
      </Pagina>
    )
  if (carga.tipo === 'red')
    return (
      <Pagina titulo={FICHA.titulo}>
        <ErrorAlCargar reintentar={pedir} />
      </Pagina>
    )
  if (carga.tipo === 'bloqueo') return carga.bloqueo === 'sin-acceso' ? <SinAcceso /> : <Bloqueada bloqueo={carga.bloqueo} />
  return null
}

function VistaPrevia({
  titulo,
  textos,
  escribiendo,
  secciones,
  nota,
}: {
  titulo: string
  textos: Record<CampoApi, string | null>
  escribiendo?: CampoApi
  secciones?: SeccionEnHoja[]
  nota?: string
}) {
  const { persona } = useFamilia()
  return (
    <section aria-labelledby="vista-t" className="flex min-w-0 flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h2 id="vista-t" className="text-xl font-bold leading-snug">
          {titulo}
        </h2>
        {nota && <p className="text-sm text-tenue">{nota}</p>}
      </div>
      <HojaFicha pila={persona ? nombrePilaDe(persona) : ''} textos={textos} escribiendo={escribiendo} secciones={secciones} />
    </section>
  )
}

/** Aviso de una sola vez al llegar (guardado o conflicto resuelto). */
export function AvisoDeLlegada() {
  const { aviso, fijar } = useFamilia()
  const [visto] = useState(aviso)
  useEffect(() => {
    if (aviso) fijar({ aviso: null })
  }, [aviso, fijar])
  if (!visto) return null
  return (
    <Nota tono={visto.tono ?? 'ok'} titulo={visto.titulo} rol="status" className="mb-6">
      {visto.texto}
    </Nota>
  )
}

// ---------------------------------------------------------------- 3.6 La ficha

export function TuFicha() {
  const { ficha, persona, rol } = useFamilia()
  const { carga, pedir } = useFicha()
  if (carga.tipo !== 'lista' || !ficha) return <Estado carga={carga} pedir={() => void pedir()} />
  const pila = persona ? nombrePilaDe(persona) : ''
  const hechos = camposListos(ficha.completitud)
  const primeroQueFalta = CAMPOS.find((c) => !listo(ficha.campos[c.api]))
  return (
    <Pagina titulo={FICHA.titulo} bajada={FICHA.bajada}>
      <AvisoDeLlegada />
      <div className="grid grid-cols-1 items-start gap-x-16 gap-y-10 @4xl/main:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="flex min-w-0 flex-col">
          <section aria-label="Campos de la ficha" className="flex min-w-0 flex-col gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-bold leading-snug">
                <span className="cifras">{hechos}</span> {FICHA.avanceResto}
              </h2>
              <BarraCampos hechos={hechos} className="w-40" />
            </div>
            <ul className="flex flex-col gap-3">
              {CAMPOS.map((c) => {
                const f = ficha.campos[c.api]
                const ok = listo(f)
                const principal = primeroQueFalta?.api === c.api
                return (
                  <li key={c.api} className={`flex flex-col gap-2 border-l-4 bg-hoja px-4 angosto:px-2 py-3.5 ${ok ? 'border-ok' : 'border-tinta/20'}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-lg font-bold">{c.titulo}</h3>
                      <Listo listo={ok} />
                    </div>
                    <p className={`line-clamp-2 whitespace-pre-line ${ok ? '' : 'text-tenue'}`}>{ok ? f.texto : c.pregunta(pila)}</p>
                    {ok && f.actualizado_en && (
                      <p className="text-sm text-tenue">
                        {FICHA.loEscribio(f.actualizado_por?.nombre ?? CONFLICTO.otraPersona)} <Cuando iso={f.actualizado_en} />
                      </p>
                    )}
                    {/* El pagador no sabe de antemano si puede editar (D3): el botón está y un 404 lleva a 5.6. */}
                    {(puedeEditar(rol) || rol === 'pagador') && (
                      <Boton
                        variante={principal ? 'principal' : 'secundario'}
                        className="self-start"
                        icono={<PencilLine aria-hidden className="size-5" />}
                        onClick={() => navegar(c.ruta)}
                      >
                        {ok ? FICHA.editar(c.titulo) : FICHA.completar(c.titulo)}
                      </Boton>
                    )}
                  </li>
                )
              })}
            </ul>
            <p className="flex gap-2 text-base text-tenue">
              <Lock aria-hidden className="mt-0.5 size-4.5 shrink-0" />
              {FICHA.cifrado}
            </p>
          </section>
          {/* MATU-49, 3: después de los tres campos, «Más sobre…». */}
          <MasSobre ficha={ficha} pila={pila} rol={rol} />
          <div className="mt-10">
            <UltimasAperturas />
          </div>
        </div>
        <VistaPrevia titulo={FICHA.vistaPrevia} nota={MAS.vistaPrevia} textos={textosDe(ficha)} secciones={seccionesEnHoja(ficha)} />
      </div>
    </Pagina>
  )
}

// ---------------------------------------------------------------- 3.7 El editor

type FallaGuardar = 'falta-version' | 'muy-largo' | 'red' | null

export function Editor({ campo }: { campo: Campo }) {
  const { ficha, persona, rol, personaId, fijar, sinGuardar, anunciar } = useFamilia()
  const { carga, pedir } = useFicha()
  if (carga.tipo !== 'lista' || !ficha || !personaId) return <Estado carga={carga} pedir={() => void pedir()} />
  return <EditorCampo key={`${personaId}-${campo.api}`} campo={campo} ficha={ficha} pila={persona ? nombrePilaDe(persona) : ''} {...{ rol, personaId, fijar, sinGuardar, anunciar }} />
}

function EditorCampo({
  campo,
  ficha,
  pila,
  personaId,
  fijar,
  sinGuardar,
  anunciar,
}: {
  campo: Campo
  ficha: Ficha
  pila: string
  personaId: string
} & Pick<ReturnType<typeof useFamilia>, 'fijar' | 'sinGuardar' | 'anunciar' | 'rol'>) {
  const original = ficha.campos[campo.api]
  const [texto, setTexto] = useState(original.texto ?? '')
  const [etag] = useState(original.etag)
  const [ocupado, setOcupado] = useState(false)
  const [falla, setFalla] = useState<FallaGuardar>(null)
  const [bloqueo, setBloqueo] = useState<Bloqueo | null>(null)
  const [conflicto, setConflicto] = useState<DatosConflicto | null>(null)
  const [confirmarSalida, setConfirmarSalida] = useState(false)
  const [anuncioTope, setAnuncioTope] = useState('')
  const sucio = texto !== (original.texto ?? '')
  const indice = CAMPOS.indexOf(campo) + 1
  const textoRef = useRef(texto)
  textoRef.current = texto

  const d = useDictado({ texto, onTexto: setTexto, tope: MAX_CARACTERES })

  // 5.7: si la entrada vence con texto sin guardar, la app lo muestra antes de ir a entrar.
  useEffect(() => {
    sinGuardar.current = () => (textoRef.current !== (original.texto ?? '') ? textoRef.current : null)
    return () => {
      sinGuardar.current = null
    }
  }, [sinGuardar, original.texto])

  // El contador se anuncia solo al cruzar 450 y 500.
  const previo = useRef(texto.length)
  useEffect(() => {
    const a = previo.current
    const b = texto.length
    if ((a < AVISO_CONTADOR) !== (b < AVISO_CONTADOR) || (a < MAX_CARACTERES) !== (b < MAX_CARACTERES)) setAnuncioTope(FICHA.contador(b))
    previo.current = b
  }, [texto.length])

  /** Después de un guardado: al siguiente campo que falta, o a la ficha si está completa. */
  const despuesDeGuardar = (f: Ficha, titulo: string, texto?: string) => {
    const hechos = camposListos(f.completitud)
    const siguiente = CAMPOS.find((c) => c.api !== campo.api && !listo(f.campos[c.api]))
    fijar({ ficha: f, aviso: { titulo, texto: texto ?? (hechos === 3 ? FICHA.completa : FICHA.vasEn(hechos)) } })
    navegar(siguiente ? siguiente.ruta : '/ficha')
  }

  const enviar = async (valor: string, conEtag: string | null) => {
    setOcupado(true)
    setFalla(null)
    try {
      const g = await guardarCampo(personaId, campo.api, valor, conEtag)
      const nueva: Ficha = {
        ...ficha,
        completitud: g.completitud,
        actualizado_en: g.actualizado_en,
        campos: { ...ficha.campos, [campo.api]: { texto: g.texto, etag: g.etag, actualizado_por: g.actualizado_por, actualizado_en: g.actualizado_en } },
      }
      return nueva
    } catch (e) {
      if (esVencida(e)) return null
      const c = leerConflicto(e)
      if (c) {
        setConflicto(c)
        return null
      }
      const f = leerFallo(e)
      if (f.status === 428) setFalla('falta-version')
      else if (f.status === 422 && f.errores.some((x) => x.tipo === 'string_too_long')) setFalla('muy-largo')
      else if (f.status === 403 || f.status === 404) {
        const b = bloqueoDe(e)
        if (b !== 'red') setBloqueo(b)
      } else setFalla('red')
      return null
    } finally {
      setOcupado(false)
    }
  }

  const guardar = async () => {
    if (ocupado) return
    d.detener()
    // Vacío sobre un campo nunca escrito: no se envía nada y no hay mensaje (lenguaje 5.4).
    if (!texto.trim() && etag === null) return
    const nueva = await enviar(texto, etag)
    if (nueva) despuesDeGuardar(nueva, FICHA.guardado(campo.titulo))
  }

  const seguirDespues = () => {
    d.detener()
    if (sucio) return setConfirmarSalida(true)
    navegar('/ficha')
  }

  if (bloqueo === 'sin-acceso') return <SinAcceso />
  if (bloqueo) return <Bloqueada bloqueo={bloqueo} escrito={texto.trim() ? texto : undefined} />
  if (conflicto)
    return (
      <PantallaConflicto
        titulo={campo.titulo}
        mio={texto}
        conflicto={conflicto}
        ocupado={ocupado}
        dejarSuya={async (autor) => {
          // Se queda con lo vigente, sin PUT, y se vuelve a leer para tener la completitud real.
          try {
            const f = await leerFicha(personaId)
            fijar({ ficha: f, aviso: { titulo: CONFLICTO.dejasteSuya(autor) } })
          } catch {
            fijar({
              ficha: { ...ficha, campos: { ...ficha.campos, [campo.api]: conflicto.actual } },
              aviso: { titulo: CONFLICTO.dejasteSuya(autor) },
            })
          }
          anunciar(CONFLICTO.dejasteSuya(autor))
          navegar('/ficha')
        }}
        dejarMia={async () => {
          const nueva = await enviar(texto, conflicto.etag)
          if (nueva) {
            setConflicto(null)
            fijar({ ficha: nueva, aviso: { titulo: CONFLICTO.dejasteTuya } })
            navegar('/ficha')
          }
        }}
      />
    )

  const cerca = texto.length >= AVISO_CONTADOR
  const textos = { ...textosDe(ficha), [campo.api]: texto }
  return (
    <>
      <AvisoDeLlegada />
      <div className="grid grid-cols-1 items-start gap-x-16 gap-y-10 @4xl/main:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <section aria-label="Editar un campo" className="flex min-w-0 flex-col gap-5">
          <Volver onClick={seguirDespues}>{FICHA.volverALaFicha}</Volver>
          <div className="flex flex-col gap-1">
            <p className="font-bold text-tenue">{FICHA.campoN(indice)}</p>
            <Titulo>{campo.titulo}</Titulo>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="campo-texto" className="text-base">
              {campo.pregunta(pila)}
            </label>
            <textarea
              id="campo-texto"
              rows={8}
              maxLength={MAX_CARACTERES}
              value={texto}
              readOnly={ocupado}
              onChange={(e) => {
                setTexto(e.target.value)
                setConfirmarSalida(false)
              }}
              aria-invalid={falla === 'muy-largo' ? true : undefined}
              aria-describedby="campo-cuenta campo-ejemplo"
              // Alto mínimo: 8 renglones de la utilidad `renglones` (1,75rem cada uno) más el py-3 (1,5rem).
              className={`renglones min-h-[calc(8*1.75rem+1.5rem)] w-full resize-y rounded-xl bg-hoja px-4 py-3 leading-7 ring-2 ring-inset focus-visible:ring-turquesa ${
                falla === 'muy-largo' ? 'ring-pronto' : 'ring-borde'
              }`}
            />
            <p id="campo-cuenta" className={`flex items-center gap-1.5 text-sm ${cerca ? 'font-bold text-atenta' : 'text-tenue'}`}>
              {cerca && <TriangleAlert aria-hidden className="size-4 shrink-0" />}
              {/* Solo las cifras en `cifras` (sin partirse): la frase completa desborda a 320 px con 200 %. */}
              <span className="min-w-0">
                <span className="cifras">{texto.length}</span> {FICHA.contador(texto.length).replace(/^\d+ /, '')}
              </span>
            </p>
            <span aria-live="polite" className="sr-only">
              {anuncioTope}
            </span>
            {falla === 'muy-largo' && <MensajeError>{FICHA.muyLargo}</MensajeError>}
            <p id="campo-ejemplo" className="text-base text-tenue">
              {campo.ejemplo}
            </p>
          </div>
          <BotonDictar d={d} deshabilitado={ocupado} />
          {falla === 'falta-version' && (
            <Nota tono="pronto" rol="alert" titulo={FICHA.faltaVersionTitulo}>
              {FICHA.faltaVersion}
            </Nota>
          )}
          {falla === 'red' && (
            <Nota tono="pronto" rol="alert">
              {GENERAL.error}
            </Nota>
          )}
          {confirmarSalida && (
            <Nota tono="atenta" rol="alert" titulo={FICHA.sinGuardar(campo.titulo)}>
              <Acciones className="mt-2">
                <Boton variante="secundario" onClick={() => navegar('/ficha')}>
                  {FICHA.salirSinGuardar}
                </Boton>
                <Boton
                  variante="texto"
                  onClick={() => {
                    setConfirmarSalida(false)
                    document.getElementById('campo-texto')?.focus()
                  }}
                >
                  {FICHA.seguirEscribiendo}
                </Boton>
              </Acciones>
            </Nota>
          )}
          <Acciones>
            <Boton onClick={() => void guardar()} ocupado={ocupado} textoOcupado={FICHA.guardando}>
              {FICHA.guardar}
            </Boton>
            <Boton variante="texto" onClick={seguirDespues}>
              {FICHA.seguirDespues}
            </Boton>
          </Acciones>
        </section>
        <VistaPrevia titulo={FICHA.mientrasEscribes} textos={textos} escribiendo={campo.api} secciones={seccionesEnHoja(ficha)} />
      </div>
    </>
  )
}

// ---------------------------------------------------------------- 3.8 Conflicto

export function PantallaConflicto({
  titulo,
  mio,
  conflicto,
  ocupado,
  dejarSuya,
  dejarMia,
}: {
  /** El título del campo o de la sección. */
  titulo: string
  mio: string
  conflicto: DatosConflicto
  ocupado: boolean
  dejarSuya: (autor: string) => Promise<void>
  dejarMia: () => Promise<void>
}) {
  const autor = conflicto.actual.actualizado_por?.nombre || CONFLICTO.otraPersona
  const hora = horaDe(conflicto.actual.actualizado_en)
  useEffect(() => {
    document.getElementById('titulo-pagina')?.focus()
  }, [conflicto])
  return (
    <div className="flex flex-col gap-6">
      {/* 4.8 de MATU-49: a 320 px con texto al 200 %, sin desplazamiento horizontal. */}
      <div role="alert" className="flex max-w-prose gap-3 border-l-4 border-pronto bg-pronto-fondo px-4 angosto:px-2 py-3.5">
        <TriangleAlert aria-hidden className="mt-1 size-6 shrink-0 text-pronto angosto:hidden" />
        <div className="min-w-0">
          <Titulo className="text-2xl angosto:text-xl wrap-anywhere hyphens-auto">{CONFLICTO.titulo(autor, titulo)}</Titulo>
          <p className="mt-1">{CONFLICTO.explicacion}</p>
        </div>
      </div>
      <div className="grid grid-cols-1 items-stretch gap-5 @3xl/main:grid-cols-2">
        <section aria-labelledby="v-suya" className="flex flex-col gap-3 rounded-sm bg-hoja px-5 angosto:px-2 py-4 ring-1 ring-linea">
          <h2 id="v-suya" className="font-bold">
            {CONFLICTO.laDe(autor)}
            {hora && (
              <span className="block text-sm font-normal text-tenue">
                {CONFLICTO.guardadaA} <span className="cifras">{hora}</span>
              </span>
            )}
          </h2>
          <p className="flex-1 leading-relaxed whitespace-pre-line select-text">{conflicto.actual.texto || <i className="text-tenue">{CONFLICTO.vacia}</i>}</p>
          <Boton variante="secundario" className="self-start" disabled={ocupado} onClick={() => void dejarSuya(autor)}>
            {CONFLICTO.dejarLaDe(autor)}
          </Boton>
        </section>
        <section aria-labelledby="v-mia" className="flex flex-col gap-3 rounded-sm bg-hoja px-5 angosto:px-2 py-4 ring-2 ring-turquesa">
          <h2 id="v-mia" className="font-bold">
            {CONFLICTO.laTuya}
            <span className="block text-sm font-normal text-tenue">{CONFLICTO.laTuyaDetalle}</span>
          </h2>
          <p className="flex-1 leading-relaxed whitespace-pre-line select-text">{mio || <i className="text-tenue">{CONFLICTO.vacia}</i>}</p>
          <Boton className="self-start" ocupado={ocupado} textoOcupado={FICHA.guardando} onClick={() => void dejarMia()}>
            {CONFLICTO.dejarLaMia}
          </Boton>
        </section>
      </div>
      <p className="max-w-prose text-base text-tenue">{CONFLICTO.nota}</p>
    </div>
  )
}
