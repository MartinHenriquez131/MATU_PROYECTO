// Editor de una sección complementaria (especificación MATU-49, sección 4): copia el editor de un
// campo (MATU-39 3.7) con su tope (500, u 800 en Sus remedios), la ayuda, el ejemplo y, solo si la
// sección ya existe, «Quitar». Sin interfaz optimista: la ficha cambia solo con la respuesta. Un 412
// se muestra, nunca se esconde, y nada se borra sin que se vea la versión nueva.
import { useEffect, useRef, useState } from 'react'
import { CircleAlert, Info, Trash2, TriangleAlert } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  guardarSeccion,
  leerConflicto,
  leerConflictoSeccion,
  leerFicha,
  nombrePilaDe,
  quitarSeccion,
  seccionesDe,
  type Conflicto as DatosConflicto,
  type EstadoSeccion,
  type Ficha,
} from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { AVISO_REMEDIOS, avisoDe, topeDe } from '../compartido/secciones'
import { Boton } from '../compartido/ui/Boton'
import type { Seccion } from './datos'
import { BotonDictar, useDictado } from './Dictado'
import { puedeCompartir, useFamilia } from './estado'
import { AvisoDeLlegada, Bloqueada, bloqueoDe, Estado, PantallaConflicto, SinAcceso, useFicha, type Bloqueo } from './Ficha'
import { navegar } from './ruteo'
import { COMPARTIR, CONFLICTO, FICHA, GENERAL, MAS } from './textos'
import { Acciones, HojaSeccion, horaDe, MensajeError, Nota, Titulo, Volver } from './ui'

export function EditorDeSeccion({ seccion }: { seccion: Seccion }) {
  const { ficha, persona, personaId } = useFamilia()
  const { carga, pedir } = useFicha()
  if (carga.tipo !== 'lista' || !ficha || !personaId) return <Estado carga={carga} pedir={() => void pedir()} />
  return <Editor key={`${personaId}-${seccion.api}`} seccion={seccion} ficha={ficha} pila={persona ? nombrePilaDe(persona) : ''} personaId={personaId} />
}

type FallaGuardar = 'falta-version' | 'muy-largo' | 'red' | null
type Quitar = 'cerrado' | 'abierto' | 'error'

/** La ficha con una sección cambiada (`null` = quitada). */
function conSeccion(f: Ficha, api: Seccion['api'], estado: EstadoSeccion | null): Ficha {
  const s = { ...seccionesDe(f) }
  if (estado) s[api] = estado
  else delete s[api]
  return { ...f, secciones: s }
}

function Editor({ seccion, ficha, pila, personaId }: { seccion: Seccion; ficha: Ficha; pila: string; personaId: string }) {
  const { fijar, sinGuardar, rol } = useFamilia()
  const original = seccionesDe(ficha)[seccion.api] ?? null
  const existe = !!original?.texto?.trim()
  const tope = topeDe(seccion.api)
  const umbral = avisoDe(seccion.api)
  const [texto, setTexto] = useState(original?.texto ?? '')
  const [ocupado, setOcupado] = useState(false)
  const [falla, setFalla] = useState<FallaGuardar>(null)
  const [bloqueo, setBloqueo] = useState<Bloqueo | null>(null)
  const [conflicto, setConflicto] = useState<DatosConflicto | null>(null)
  const [conflictoQuitar, setConflictoQuitar] = useState<{ actual: EstadoSeccion; etag: string } | null>(null)
  /** 4.6: el PUT con `If-Match` respondió 412 sin versión: otra persona la quitó. */
  const [quitadaPorOtra, setQuitadaPorOtra] = useState(false)
  const [quitar, setQuitar] = useState<Quitar>('cerrado')
  const [quitando, setQuitando] = useState(false)
  const [confirmarSalida, setConfirmarSalida] = useState(false)
  const [anuncioTope, setAnuncioTope] = useState('')
  const sucio = texto !== (original?.texto ?? '')
  const textoRef = useRef(texto)
  textoRef.current = texto
  const botonQuitar = useRef<HTMLButtonElement>(null)
  const tituloQuitar = useRef<HTMLParagraphElement>(null)

  const d = useDictado({ texto, onTexto: setTexto, tope })

  // 5.7 de MATU-39: si la entrada vence con texto sin guardar, se muestra antes de ir a entrar.
  useEffect(() => {
    sinGuardar.current = () => (textoRef.current !== (original?.texto ?? '') ? textoRef.current : null)
    return () => {
      sinGuardar.current = null
    }
  }, [sinGuardar, original?.texto])

  // El contador se anuncia solo al cruzar el 90 % y el tope (4.3).
  const previo = useRef(texto.length)
  useEffect(() => {
    const a = previo.current
    const b = texto.length
    if ((a < umbral) !== (b < umbral) || (a < tope) !== (b < tope)) setAnuncioTope(MAS.contador(b, tope))
    previo.current = b
  }, [texto.length, umbral, tope])

  // 4.5: al abrir la confirmación, el foco a su título.
  useEffect(() => {
    if (quitar === 'abierto') tituloQuitar.current?.focus()
  }, [quitar])

  /** 403, 404 y red: lo común de guardar y quitar. */
  const otroFallo = (e: unknown) => {
    const f = leerFallo(e)
    if (f.status === 428) setFalla('falta-version')
    else if (f.status === 422 && f.errores.some((x) => x.tipo === 'largo_maximo' || x.tipo === 'string_too_long')) setFalla('muy-largo')
    else if (f.status === 403 || f.status === 404) {
      const b = bloqueoDe(e)
      if (b !== 'red') setBloqueo(b)
      if (b === 'sin-consentimiento' || b === 'revision-vencida') fijar({ autorizacion: b })
      else setFalla('red')
    } else setFalla('red')
  }

  /** PUT con `If-Match` o, sin `etag`, `If-None-Match: *`. Devuelve la ficha nueva o `null`. */
  const enviar = async (valor: string, conEtag: string | null): Promise<Ficha | null> => {
    setOcupado(true)
    setFalla(null)
    try {
      const g = await guardarSeccion(personaId, seccion.api, valor, conEtag)
      return conSeccion(ficha, seccion.api, { texto: g.texto, etag: g.etag, actualizado_por: g.actualizado_por, actualizado_en: g.actualizado_en })
    } catch (e) {
      if (esVencida(e)) return null
      const s = leerConflictoSeccion(e)
      if (s && !s.actual) {
        setConflicto(null)
        setQuitadaPorOtra(true)
        return null
      }
      const c = leerConflicto(e)
      if (c) {
        setConflicto(c)
        return null
      }
      otroFallo(e)
      return null
    } finally {
      setOcupado(false)
    }
  }

  /** 4.4: la nota de llegada a la ficha. Una sección nueva suma la frase de los enlaces. */
  const avisoGuardado = (nueva: boolean) =>
    nueva
      ? {
          titulo: MAS.agregaste(seccion.titulo),
          texto: MAS.conEnlaces,
          // MATU-48 2.3: al lado del texto, «Crear un enlace nuevo».
          accion: puedeCompartir(rol) ? { texto: COMPARTIR.crearNuevo, ruta: '/compartir' as const, variante: 'texto' as const } : undefined,
        }
      : { titulo: MAS.guardamos(seccion.titulo) }

  const guardar = async () => {
    if (ocupado) return
    d.detener()
    if (!texto.trim()) {
      // Vacío sobre una sección que no está: no se envía nada ni hay mensaje.
      if (!existe) return navegar('/ficha')
      // Vacío sobre una que está: dejarla en blanco es quitarla (4.4).
      return setQuitar('abierto')
    }
    const nueva = await enviar(texto, original?.etag ?? null)
    if (nueva) {
      fijar({ ficha: nueva, aviso: avisoGuardado(!existe) })
      navegar('/ficha')
    }
  }

  /** DELETE con `If-Match`. El 412 sin `actual` es «ya no estaba» (contrato). */
  const borrar = async (etag: string) => {
    if (quitando) return
    d.detener()
    setQuitando(true)
    setFalla(null)
    try {
      await quitarSeccion(personaId, seccion.api, etag)
      fijar({ ficha: conSeccion(ficha, seccion.api, null), aviso: { titulo: MAS.quitaste(seccion.titulo) } })
      navegar('/ficha')
    } catch (e) {
      if (esVencida(e)) return
      const c = leerConflictoSeccion(e)
      if (c && !c.actual) {
        fijar({ ficha: conSeccion(ficha, seccion.api, null), aviso: { titulo: MAS.yaNoEstaba(seccion.titulo), tono: 'rocio' } })
        navegar('/ficha')
        return
      }
      if (c?.actual && c.etag) {
        setConflictoQuitar({ actual: c.actual, etag: c.etag })
        return
      }
      setQuitar('error')
      otroFallo(e)
    } finally {
      setQuitando(false)
    }
  }

  const seguirDespues = () => {
    d.detener()
    if (sucio) return setConfirmarSalida(true)
    navegar('/ficha')
  }

  if (bloqueo === 'sin-acceso') return <SinAcceso />
  if (bloqueo) return <Bloqueada bloqueo={bloqueo} escrito={texto.trim() ? texto : undefined} />

  if (conflictoQuitar)
    return (
      <ConflictoAlQuitar
        titulo={seccion.titulo}
        actual={conflictoQuitar.actual}
        ocupado={quitando}
        quitarIgual={() => void borrar(conflictoQuitar.etag)}
        dejarla={() => {
          const autor = conflictoQuitar.actual.actualizado_por?.nombre || CONFLICTO.otraPersona
          const aviso = MAS.dejasteComoLaGuardo(seccion.titulo, autor)
          fijar({ ficha: conSeccion(ficha, seccion.api, conflictoQuitar.actual), aviso: { titulo: aviso } })
          navegar('/ficha')
        }}
      />
    )

  if (quitadaPorOtra)
    return (
      <QuitadaPorOtra
        titulo={seccion.titulo}
        mio={texto}
        ocupado={ocupado}
        error={falla === 'red'}
        agregar={async () => {
          // Es una sección nueva para los accesos ya creados: lleva la frase de los enlaces.
          const nueva = await enviar(texto, null)
          if (nueva) {
            setQuitadaPorOtra(false)
            fijar({ ficha: nueva, aviso: avisoGuardado(true) })
            navegar('/ficha')
          }
        }}
        dejarla={() => {
          const aviso = MAS.dejasteQuitada(seccion.titulo)
          fijar({ ficha: conSeccion(ficha, seccion.api, null), aviso: { titulo: aviso, tono: 'rocio' } })
          navegar('/ficha')
        }}
      />
    )

  if (conflicto)
    return (
      <PantallaConflicto
        titulo={seccion.titulo}
        mio={texto}
        conflicto={conflicto}
        ocupado={ocupado}
        dejarSuya={async (autor) => {
          // Se queda con lo vigente, sin PUT, y se vuelve a leer la ficha.
          try {
            const f = await leerFicha(personaId)
            fijar({ ficha: f, aviso: { titulo: CONFLICTO.dejasteSuya(autor) } })
          } catch {
            const vigente = conflicto.actual.texto?.trim() ? (conflicto.actual as EstadoSeccion) : null
            fijar({ ficha: conSeccion(ficha, seccion.api, vigente), aviso: { titulo: CONFLICTO.dejasteSuya(autor) } })
          }
          navegar('/ficha')
        }}
        dejarMia={async () => {
          // Con el `ETag` del 412; si la otra persona la quitó, no hay ETag y se agrega de nuevo.
          const nueva = await enviar(texto, conflicto.etag)
          if (nueva) {
            setConflicto(null)
            fijar({ ficha: nueva, aviso: { titulo: CONFLICTO.dejasteTuya } })
            navegar('/ficha')
          }
        }}
      />
    )

  const cerca = texto.length >= umbral
  const remedios = seccion.api === 'remedios'
  const describe = [remedios ? 'seccion-aviso' : '', 'seccion-cuenta', 'seccion-ayuda', 'seccion-ejemplo'].filter(Boolean).join(' ')
  return (
    <>
      <AvisoDeLlegada />
      <div className="grid grid-cols-1 items-start gap-x-16 gap-y-10 @4xl/main:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <section aria-label="Editar una sección" className="flex min-w-0 flex-col gap-5">
          <Volver onClick={seguirDespues}>{FICHA.volverALaFicha}</Volver>
          <div className="flex flex-col gap-1">
            <p className="text-sm text-tenue">{MAS.titulo(pila)}</p>
            <Titulo>{seccion.titulo}</Titulo>
          </div>
          {remedios && (
            <Nota id="seccion-aviso" tono="atenta" borde icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
              {AVISO_REMEDIOS}
            </Nota>
          )}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="seccion-texto" className="text-base font-bold">
              {seccion.pregunta}
            </label>
            <textarea
              id="seccion-texto"
              rows={8}
              maxLength={tope}
              value={texto}
              readOnly={ocupado || quitando}
              onChange={(e) => {
                setTexto(e.target.value)
                setConfirmarSalida(false)
              }}
              aria-invalid={falla === 'muy-largo' ? true : undefined}
              aria-describedby={describe}
              // Alto mínimo: 8 renglones de `renglones` (1,75rem cada uno) más el py-3 (1,5rem).
              className={`renglones min-h-[calc(8*1.75rem+1.5rem)] w-full resize-y rounded-xl bg-hoja px-4 py-3 leading-7 ring-2 ring-inset focus-visible:ring-turquesa ${
                falla === 'muy-largo' ? 'ring-pronto' : 'ring-borde'
              }`}
            />
            <p id="seccion-cuenta" className={`flex items-center gap-1.5 text-sm ${cerca ? 'font-bold text-atenta' : 'text-tenue'}`}>
              {cerca && <TriangleAlert aria-hidden className="size-4 shrink-0" />}
              {/* Solo las cifras en `cifras` (sin partirse): la frase completa desborda a 320 px con 200 %. */}
              <span className="min-w-0">
                <span className="cifras">{texto.length}</span> {MAS.contador(texto.length, tope).replace(/^\d+ /, '')}
              </span>
            </p>
            <span aria-live="polite" className="sr-only">
              {anuncioTope}
            </span>
            {falla === 'muy-largo' && (
              <MensajeError>
                {MAS.muyLargo[0]}
                <span className="cifras">{tope}</span>
                {MAS.muyLargo[1]}
              </MensajeError>
            )}
            <div id="seccion-ayuda" className="text-base text-tenue">
              <p>{MAS.ayuda}</p>
              {seccion.alergias && <p>{MAS.alergias}</p>}
            </div>
            <p id="seccion-ejemplo" className="border-s-2 border-linea ps-3 text-base text-tenue">
              {MAS.ejemplo(seccion.ejemplo)}
            </p>
          </div>
          {/*
            Decisión de Jorge del 03-11: sin dictado en Sus remedios. El reconocimiento de voz del
            navegador (Web Speech API) envía el audio a un tercero (Google en Chrome), y el audio de
            un dato de salud está en consulta legal. Se reactiva quitando esta condición cuando haya
            respuesta legal. Las otras cinco secciones y los tres campos base siguen con dictado.
            Sin el botón, el reconocimiento nunca arranca: `useDictado` solo escucha al tocarlo.
          */}
          {seccion.api !== 'remedios' && <BotonDictar d={d} deshabilitado={ocupado || quitando} />}
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
            <Nota tono="atenta" rol="alert" titulo={FICHA.sinGuardar(seccion.titulo)}>
              <Acciones className="mt-2">
                <Boton variante="secundario" onClick={() => navegar('/ficha')}>
                  {FICHA.salirSinGuardar}
                </Boton>
                <Boton
                  variante="texto"
                  onClick={() => {
                    setConfirmarSalida(false)
                    document.getElementById('seccion-texto')?.focus()
                  }}
                >
                  {FICHA.seguirEscribiendo}
                </Boton>
              </Acciones>
            </Nota>
          )}
          <Acciones>
            <Boton onClick={() => void guardar()} ocupado={ocupado} textoOcupado={FICHA.guardando} disabled={quitando}>
              {FICHA.guardar}
            </Boton>
            <Boton variante="texto" onClick={seguirDespues}>
              {FICHA.seguirDespues}
            </Boton>
          </Acciones>

          {/* 4.5: solo si la sección existe, abajo y separado. Nunca junto a «Guardar». */}
          {existe && original?.etag && (
            <div className="mt-10 border-t border-linea pt-6">
              {quitar === 'cerrado' ? (
                <Boton ref={botonQuitar} variante="textoPeligro" icono={<Trash2 aria-hidden className="size-5" />} onClick={() => setQuitar('abierto')}>
                  {MAS.quitar(seccion.titulo)}
                </Boton>
              ) : (
                <div
                  aria-busy={quitando || undefined}
                  className="flex max-w-prose gap-3 rounded-xl bg-pronto-fondo px-4 py-3"
                >
                  <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-pronto" />
                  <div className="flex min-w-0 flex-col gap-2">
                    <p ref={tituloQuitar} tabIndex={-1} className="font-bold outline-none focus-visible:outline-3 focus-visible:outline-pronto">
                      {MAS.quitarPregunta(seccion.titulo)}
                    </p>
                    <p className="text-base leading-relaxed">{MAS.quitarTexto}</p>
                    <Acciones className="mt-1">
                      <Boton variante="peligro" ocupado={quitando} textoOcupado={MAS.quitando} onClick={() => void borrar(original.etag)}>
                        {MAS.quitarYBorrar}
                      </Boton>
                      <Boton
                        variante="texto"
                        disabled={quitando}
                        onClick={() => {
                          setQuitar('cerrado')
                          window.setTimeout(() => botonQuitar.current?.focus(), 0)
                        }}
                      >
                        {MAS.dejarla}
                      </Boton>
                    </Acciones>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
        <section aria-labelledby="vista-s" className="flex min-w-0 flex-col gap-5">
          <h2 id="vista-s" className="text-xl font-bold leading-snug">
            {FICHA.vistaPrevia}
          </h2>
          <HojaSeccion pila={pila} seccion={seccion.api} texto={texto} />
        </section>
      </div>
    </>
  )
}

/**
 * 4.6: guardar cuando otra persona la quitó (412 con `actual: null`). No hay versión de otra
 * persona que elegir: solo «La tuya». Construcción de 4.8 para 320 px con texto al 200 %.
 */
function QuitadaPorOtra({
  titulo,
  mio,
  ocupado,
  error,
  agregar,
  dejarla,
}: {
  titulo: string
  mio: string
  ocupado: boolean
  /** Red o 5xx al agregarla de nuevo: lo escrito sigue a la vista. */
  error: boolean
  agregar: () => Promise<void>
  dejarla: () => void
}) {
  useEffect(() => {
    document.getElementById('titulo-pagina')?.focus()
  }, [])
  return (
    <div className="flex max-w-prose flex-col gap-6">
      <div role="alert" className="flex gap-3 border-l-4 border-pronto bg-pronto-fondo px-4 angosto:px-2 py-3.5">
        <TriangleAlert aria-hidden className="mt-1 size-6 shrink-0 text-pronto angosto:hidden" />
        <div className="min-w-0">
          <Titulo className="text-2xl angosto:text-xl wrap-anywhere hyphens-auto">{MAS.quitadaTitulo(titulo)}</Titulo>
          <p className="mt-1">{MAS.quitadaTexto}</p>
        </div>
      </div>
      <section aria-labelledby="v-mia-q" className="flex flex-col gap-3 rounded-sm bg-hoja px-5 angosto:px-2 py-4 ring-2 ring-turquesa">
        <h2 id="v-mia-q" className="font-bold">
          {CONFLICTO.laTuya}
          <span className="block text-sm font-normal text-tenue">{CONFLICTO.laTuyaDetalle}</span>
        </h2>
        <p className="leading-relaxed whitespace-pre-line select-text">{mio}</p>
      </section>
      {error && (
        <Nota tono="pronto" rol="alert">
          {GENERAL.error}
        </Nota>
      )}
      <Acciones>
        <Boton ocupado={ocupado} textoOcupado={FICHA.guardando} onClick={() => void agregar()}>
          {MAS.agregarlaDeNuevo}
        </Boton>
        <Boton variante="texto" disabled={ocupado} onClick={dejarla}>
          {MAS.dejarlaQuitada}
        </Boton>
      </Acciones>
      <p className="text-base text-tenue">{MAS.quitadaPie}</p>
    </div>
  )
}

/** 4.6: otra persona cambió la sección mientras se iba a quitar. Nada se borra sin verla. */
function ConflictoAlQuitar({
  titulo,
  actual,
  ocupado,
  quitarIgual,
  dejarla,
}: {
  titulo: string
  actual: EstadoSeccion
  ocupado: boolean
  quitarIgual: () => void
  dejarla: () => void
}) {
  const autor = actual.actualizado_por?.nombre || CONFLICTO.otraPersona
  const hora = horaDe(actual.actualizado_en)
  useEffect(() => {
    document.getElementById('titulo-pagina')?.focus()
  }, [actual])
  return (
    <div className="flex max-w-prose flex-col gap-6">
      {/* 4.8: a 320 px con texto al 200 %, sin desplazamiento horizontal. */}
      <div role="alert" className="flex gap-3 border-l-4 border-pronto bg-pronto-fondo px-4 angosto:px-2 py-3.5">
        <TriangleAlert aria-hidden className="mt-1 size-6 shrink-0 text-pronto angosto:hidden" />
        <div className="min-w-0">
          <Titulo className="text-2xl angosto:text-xl wrap-anywhere hyphens-auto">{MAS.conflictoQuitar(autor, titulo)}</Titulo>
          <p className="mt-1">{MAS.versionDe(autor)}</p>
        </div>
      </div>
      <section aria-labelledby="v-suya-q" className="flex flex-col gap-3 rounded-sm bg-hoja px-5 angosto:px-2 py-4 ring-1 ring-linea">
        <h2 id="v-suya-q" className="font-bold">
          {CONFLICTO.laDe(autor)}
          {hora && (
            <span className="block text-sm font-normal text-tenue">
              {CONFLICTO.guardadaA} <span className="cifras">{hora}</span>
            </span>
          )}
        </h2>
        <p className="leading-relaxed whitespace-pre-line select-text">{actual.texto}</p>
      </section>
      <Acciones>
        <Boton variante="peligro" ocupado={ocupado} textoOcupado={MAS.quitando} onClick={quitarIgual}>
          {MAS.quitarlaIgual}
        </Boton>
        <Boton variante="texto" disabled={ocupado} onClick={dejarla}>
          {MAS.dejarla}
        </Boton>
      </Acciones>
    </div>
  )
}
