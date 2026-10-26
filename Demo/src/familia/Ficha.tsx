// Ficha de relevo: los tres campos a la izquierda y la hoja como la verá el relevo a la derecha.
// Compartir, enlaces, quién la vio y la vista para imprimir son pestañas de la misma sección.
import { useEffect, useState, type ReactNode } from 'react'
import { Check, CircleAlert, Circle, Clock3, KeyRound, Link2, Lock, Mic, PencilLine, Send, ShieldCheck, Share2, TriangleAlert, Unlink, UserRound } from 'lucide-react'
import { useDemo } from '../demo/estado'
import {
  abrirCampo,
  avisar,
  completados,
  cortarAcceso,
  crearAcceso,
  escribir,
  guardarCampo,
  nombrePila,
  pantallaFamilia,
  pilaFamilia,
  reemplazar,
  resolverConflicto,
  siguienteCampoVacio,
  volver,
  type DatosCompartir,
} from '../demo/logica'
import { CAMPOS, MAX_CARACTERES, TEXTO_CAMPO } from '../demo/datos'
import { DIA, accesoVigente, estadoAccesoTexto, fmtCuando, fmtFecha, fmtHora, fmtRestante, finDeSemana } from '../demo/calculos'
import type { CampoId, Estado } from '../demo/tipos'
import { Acciones, BarraCampos, Boton, CampoTexto, Chip, Etiqueta, Logo, MensajeError, Nota, Stepper, Subtitulo } from '../components/Ui'
import { HojaFicha } from '../components/HojaFicha'
import { useMovimientoReducido } from '../components/movimiento'
import { Columna, Columnas, Pagina, Pestanas } from './Shell'

const listaCampos = (campos: CampoId[]) => {
  const t = campos.map((c) => TEXTO_CAMPO[c].titulo)
  return t.length <= 1 ? t.join('') : `${t.slice(0, -1).join(', ')} y ${t[t.length - 1]}`
}

const textosDe = (s: Estado): Record<CampoId, string> => ({
  su_dia: s.ficha.su_dia.texto,
  si_se_altera: s.ficha.si_se_altera.texto,
  a_quien_llamar: s.ficha.a_quien_llamar.texto,
})

function PestanasFicha() {
  const { s, haz } = useDemo()
  const top = pantallaFamilia(s).id
  const activa =
    top === 'compartir' || top === 'enlace-pin' ? 'compartir' : top === 'enlaces' ? 'enlaces' : top === 'quien-vio' ? 'quien-vio' : top === 'imprimir' ? 'imprimir' : 'ficha'
  const t = (texto: string, id: 'ficha' | 'compartir' | 'enlaces' | 'quien-vio' | 'imprimir') => ({
    texto,
    activa: activa === id,
    ir: () => haz((x) => pilaFamilia(x, id === 'ficha' ? ['ficha'] : ['ficha', id])),
  })
  return (
    <Pestanas
      items={[t('Campos', 'ficha'), t('Compartir', 'compartir'), t('Enlaces', 'enlaces'), t('Quién la vio', 'quien-vio'), t('Para imprimir', 'imprimir')]}
    />
  )
}

function PaginaFicha({ children, volver = false, bajada }: { children: ReactNode; volver?: boolean; bajada?: ReactNode }) {
  return (
    <Pagina titulo="Ficha de relevo" volver={volver} bajada={bajada} pestanas={<PestanasFicha />}>
      {children}
    </Pagina>
  )
}

function VistaPrevia({ titulo = 'Así la ve quien te reemplaza', campos, escribiendo, textos }: { titulo?: string; campos?: CampoId[]; escribiendo?: CampoId | null; textos?: Record<CampoId, string> }) {
  const { s } = useDemo()
  const pila = nombrePila(s)
  return (
    <Columna etiqueta={titulo}>
      <Subtitulo>{titulo}</Subtitulo>
      <HojaFicha
        etiqueta={`Hoja de la ficha de ${pila}`}
        textos={textos ?? textosDe(s)}
        campos={campos}
        escribiendo={escribiendo}
        encabezado={<p className="titular text-2xl @2xl:text-4xl">Ficha de {pila}</p>}
      />
    </Columna>
  )
}

// ---------- Campos ----------

export function TuFicha() {
  const { s, haz } = useDemo()
  const hechos = completados(s)
  return (
    <PaginaFicha bajada="Tres campos cortos para que quien te reemplace sepa qué hacer. Cada campo se guarda protegido y puedes compartir solo algunos.">
      <Columnas>
        <Columna etiqueta="Campos de la ficha">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Subtitulo>
              <span className="cifras">{hechos} de 3</span> campos listos
            </Subtitulo>
            <BarraCampos hechos={hechos} className="w-40" />
          </div>
          <ul className="flex flex-col gap-3">
            {CAMPOS.map((c) => {
              const f = s.ficha[c]
              const listo = !!f.texto.trim()
              return (
                <li key={c} className={`flex flex-col gap-2 border-l-4 bg-hoja px-4 py-3.5 ${listo ? 'border-ok' : 'border-tinta/20'}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-lg font-bold">{TEXTO_CAMPO[c].titulo}</h3>
                    <Etiqueta tono={listo ? 'ok' : 'neutro'}>
                      {listo ? <Check aria-hidden className="size-4" strokeWidth={3} /> : <Circle aria-hidden className="size-3.5" strokeWidth={2.5} />}
                      {listo ? 'Listo' : 'Falta'}
                    </Etiqueta>
                  </div>
                  <p className={`line-clamp-2 ${listo ? '' : 'text-tenue'}`}>{listo ? f.texto : TEXTO_CAMPO[c].pregunta}</p>
                  {listo && f.minuto !== null && (
                    <p className="cifras text-sm text-tenue">
                      Lo escribió {f.autor || 'Carmen'}: {fmtCuando(f.minuto, s.ahora)}
                    </p>
                  )}
                  <Boton variante={listo ? 'texto' : 'suave'} className="self-start" icono={<PencilLine aria-hidden className="size-4.5" />} onClick={() => haz((x) => abrirCampo(x, c))}>
                    {listo ? `Editar «${TEXTO_CAMPO[c].titulo}»` : `Completar «${TEXTO_CAMPO[c].titulo}»`}
                  </Boton>
                </li>
              )
            })}
          </ul>
          <Acciones>
            <Boton icono={<Share2 aria-hidden className="size-5" />} onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'compartir']))}>
              Compartir con un relevo
            </Boton>
          </Acciones>
          <p className="flex gap-2 text-base text-tenue">
            <Lock aria-hidden className="mt-0.5 size-4.5 shrink-0" />
            Cada campo se guarda cifrado, por separado.
          </p>
        </Columna>
        <VistaPrevia />
      </Columnas>
    </PaginaFicha>
  )
}

export function Completar() {
  const { s, haz } = useDemo()
  const reducido = useMovimientoReducido()
  const [dictando, setDictando] = useState(false)
  const b = s.borrador
  const campo = b?.campo ?? 'su_dia'
  const t = TEXTO_CAMPO[campo]
  const indice = CAMPOS.indexOf(campo) + 1

  // Dictado simulado: escribe el ejemplo de a poco, como si se dictara.
  useEffect(() => {
    if (!dictando) return
    const objetivo = t.dictado
    if (reducido) {
      haz((x) => escribir(x, objetivo))
      setDictando(false)
      return
    }
    let i = 0
    const id = window.setInterval(() => {
      i = Math.min(objetivo.length, i + 3)
      haz((x) => escribir(x, objetivo.slice(0, i)))
      if (i >= objetivo.length) {
        window.clearInterval(id)
        setDictando(false)
      }
    }, 28)
    return () => window.clearInterval(id)
  }, [dictando, reducido, t.dictado, haz])

  if (!b) return <TuFicha />
  const otros = CAMPOS.filter((c) => c !== campo && s.ficha[c].texto.trim()).length
  const textos = { ...textosDe(s), [campo]: b.texto }
  return (
    <PaginaFicha volver>
      <Columnas>
        <Columna etiqueta="Editar un campo">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-bold text-tenue">Campo {indice} de 3</p>
            <BarraCampos hechos={otros + (b.texto.trim() ? 1 : 0)} className="w-40" />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="campo-texto" className="titular text-3xl">
              {t.titulo}
            </label>
            <p id="campo-pregunta" className="text-base">
              {t.pregunta}
            </p>
          </div>
          <div className="relative">
            <textarea
              id="campo-texto"
              rows={8}
              maxLength={MAX_CARACTERES}
              value={b.texto}
              onChange={(e) => haz((x) => escribir(x, e.target.value))}
              aria-describedby="campo-pregunta campo-ejemplo campo-cuenta"
              className="w-full resize-y rounded-xl bg-hoja px-4 pt-3 pb-8 leading-relaxed ring-2 ring-linea ring-inset outline-none focus-visible:ring-pino"
            />
            <span id="campo-cuenta" className="cifras pointer-events-none absolute right-3 bottom-2.5 text-sm text-tenue">
              {b.texto.length} de {MAX_CARACTERES} caracteres
            </span>
          </div>
          <p id="campo-ejemplo" className="text-base text-tenue">
            {t.ejemplo}
          </p>
          <Acciones>
            <Boton onClick={() => haz(guardarCampo)} disabled={dictando}>
              Guardar
            </Boton>
            <Boton variante="suave" icono={<Mic aria-hidden className={`size-5 ${dictando ? 'motion-safe:animate-pulse' : ''}`} />} onClick={() => setDictando(true)} disabled={dictando}>
              {dictando ? 'Escuchando…' : 'Dictar en vez de escribir'}
            </Boton>
            <Boton variante="texto" onClick={() => haz(volver)}>
              Seguir después
            </Boton>
          </Acciones>
          <p className="text-sm text-tenue">El dictado está simulado en la demo: escribe un ejemplo.</p>
        </Columna>
        <VistaPrevia titulo="La hoja, mientras escribes" textos={textos} escribiendo={campo} />
      </Columnas>
    </PaginaFicha>
  )
}

export function Guardado() {
  const { s, haz } = useDemo()
  const hechos = completados(s)
  const sig = siguienteCampoVacio(s)
  const campo = pantallaFamilia(s).p as CampoId | undefined
  return (
    <PaginaFicha>
      <Columnas>
        <Columna etiqueta="Campo guardado">
          <div className="flex items-center gap-4">
            <span className="grid size-16 shrink-0 place-items-center rounded-2xl bg-pino text-papel">
              <svg viewBox="0 0 24 24" className="size-10" aria-hidden>
                <path d="M5 12.5l4.5 4.5L19 7.5" pathLength={1} fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="1" className="animate-trazo" />
              </svg>
            </span>
            <div>
              <p className="titular text-3xl" role="status">
                {campo ? `«${TEXTO_CAMPO[campo].titulo}» guardado` : 'Guardado'}
              </p>
              <p className="text-tenue">{hechos === 3 ? 'La ficha está completa.' : `Vas en ${hechos} de 3. Puedes seguir cuando quieras, no se pierde nada.`}</p>
            </div>
          </div>
          <BarraCampos hechos={hechos} className="max-w-xs" />
          <Acciones>
            {sig ? (
              <>
                <Boton onClick={() => haz((x) => abrirCampo(volver(x), sig))}>Seguir con «{TEXTO_CAMPO[sig].titulo}»</Boton>
                <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['ficha']))}>
                  Ver los campos
                </Boton>
              </>
            ) : (
              <>
                <Boton icono={<Share2 aria-hidden className="size-5" />} onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'compartir']))}>
                  Compartir con un relevo
                </Boton>
                <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>
                  Volver al inicio
                </Boton>
              </>
            )}
          </Acciones>
        </Columna>
        <VistaPrevia />
      </Columnas>
    </PaginaFicha>
  )
}

export function Conflicto() {
  const { s, haz } = useDemo()
  const c = s.conflicto
  if (!c) return <TuFicha />
  const titulo = TEXTO_CAMPO[c.campo].titulo
  return (
    <PaginaFicha>
      <div className="flex max-w-prose gap-3 border-l-4 border-pronto bg-pronto-fondo px-4 py-3.5" role="alert">
        <TriangleAlert aria-hidden className="mt-0.5 size-6 shrink-0 text-pronto" />
        <div>
          <h2 className="text-xl font-bold">
            {c.suyo.autor || 'Otra persona'} guardó «{titulo}» mientras escribías
          </h2>
          <p>No guardamos lo tuyo encima de lo suyo. Elige qué versión dejar: la otra se descarta.</p>
        </div>
      </div>
      <div className="mt-6 grid items-stretch gap-5 @2xl/main:grid-cols-2">
        <section aria-labelledby="v-suya" className="flex flex-col gap-3 bg-hoja px-5 py-4 ring-1 ring-linea">
          <h3 id="v-suya" className="font-bold">
            La de {c.suyo.autor}
            <span className="cifras block text-sm font-normal text-tenue">Guardada a las {c.suyo.minuto !== null ? fmtHora(c.suyo.minuto) : ''}</span>
          </h3>
          <p className="flex-1 leading-relaxed whitespace-pre-line">{c.suyo.texto}</p>
          <Boton variante="secundario" className="self-start" onClick={() => haz((x) => resolverConflicto(x, 'suyo'))}>
            Dejar la de {c.suyo.autor}
          </Boton>
        </section>
        <section aria-labelledby="v-mia" className="flex flex-col gap-3 bg-hoja px-5 py-4 ring-2 ring-pino">
          <h3 id="v-mia" className="font-bold">
            La tuya
            <span className="block text-sm font-normal text-tenue">Lo que escribiste recién, sin guardar</span>
          </h3>
          <p className="flex-1 leading-relaxed whitespace-pre-line">{c.mio || <i className="text-tenue">Vacía</i>}</p>
          <Boton className="self-start" onClick={() => haz((x) => resolverConflicto(x, 'mio'))}>
            Dejar la mía
          </Boton>
        </section>
      </div>
      <p className="mt-4 max-w-prose text-base text-tenue">MATU no mezcla los textos solo. Si quieres, copia una parte antes de elegir.</p>
    </PaginaFicha>
  )
}

// ---------- Compartir ----------

export function Compartir() {
  const { s, haz } = useDemo()
  const [nombre, setNombre] = useState('Rosa')
  const [telefono, setTelefono] = useState('+56 9 8765 4321')
  const [campos, setCampos] = useState<CampoId[]>([...CAMPOS])
  const [vigencia, setVigencia] = useState<DatosCompartir['vigencia']>('24h')
  const [dias, setDias] = useState(3)
  const [motivo, setMotivo] = useState('Salgo unas horas')
  const [error, setError] = useState<'nombre' | 'campos' | null>(null)
  const vence = vigencia === '24h' ? s.ahora + DIA : vigencia === 'finde' ? finDeSemana(s.ahora) : s.ahora + dias * DIA
  const vacios = campos.filter((c) => !s.ficha[c].texto.trim())
  const quien = nombre.trim() || 'el relevo'

  const crear = () => {
    if (!nombre.trim()) return setError('nombre')
    if (campos.length === 0) return setError('campos')
    haz((x) => reemplazar(crearAcceso(x, { nombre, telefono, campos, vigencia, dias, motivo }), 'enlace-pin'))
  }
  const alternar = (c: CampoId) => {
    setError(null)
    setCampos((cs) => (cs.includes(c) ? cs.filter((x) => x !== c) : CAMPOS.filter((x) => x === c || cs.includes(x))))
  }

  return (
    <PaginaFicha bajada="Quien te reemplaza recibe un enlace por WhatsApp y el PIN se lo dictas tú. El enlace vence solo y lo puedes cortar antes.">
      <Columnas>
        <Columna etiqueta="Datos del enlace">
          <div className="grid gap-4 @lg:grid-cols-2">
            <CampoTexto
              etiqueta="¿Quién te va a reemplazar?"
              value={nombre}
              onChange={(e) => {
                setNombre(e.target.value)
                setError(null)
              }}
              autoComplete="off"
              error={error === 'nombre' ? 'Escribe el nombre de quien te reemplaza.' : null}
            />
            <CampoTexto etiqueta="Su teléfono" type="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} autoComplete="off" ayuda="Para enviarle el enlace." />
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 font-bold">¿Qué puede ver?</legend>
            <div className="flex flex-wrap gap-2">
              {CAMPOS.map((c) => (
                <Chip key={c} activo={campos.includes(c)} onClick={() => alternar(c)}>
                  {TEXTO_CAMPO[c].titulo}
                </Chip>
              ))}
            </div>
            {error === 'campos' && <MensajeError>Elige al menos un campo.</MensajeError>}
            {vacios.length > 0 && (
              <p className="text-sm text-tenue">
                {listaCampos(vacios)} {vacios.length > 1 ? 'están vacíos' : 'está vacío'}: {quien} verá «Sin completar».
              </p>
            )}
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 font-bold">¿Hasta cuándo?</legend>
            <div className="flex flex-wrap gap-2">
              <Chip activo={vigencia === '24h'} onClick={() => setVigencia('24h')}>
                24 horas
              </Chip>
              <Chip activo={vigencia === 'finde'} onClick={() => setVigencia('finde')}>
                Fin de semana
              </Chip>
              <Chip activo={vigencia === 'dias'} onClick={() => setVigencia('dias')}>
                Otra cantidad de días
              </Chip>
            </div>
            {vigencia === 'dias' && <Stepper etiqueta="¿Cuántos días?" valor={dias} onCambio={setDias} min={1} max={30} unidad="días" ayuda="Hasta 30 días." />}
            <p className="flex items-center gap-2">
              <Clock3 aria-hidden className="size-5 shrink-0 text-pino" />
              <span>
                Vence el <b className="cifras">{fmtFecha(vence)}</b> a las <b className="cifras">{fmtHora(vence)}</b>
              </span>
            </p>
          </fieldset>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 font-bold">Motivo, si quieres</legend>
            <div className="flex flex-wrap gap-2">
              {['Salgo unas horas', 'Fin de semana fuera', 'Turno de noche'].map((m) => (
                <Chip key={m} activo={motivo === m} onClick={() => setMotivo(motivo === m ? '' : m)}>
                  {m}
                </Chip>
              ))}
            </div>
          </fieldset>
          <Acciones>
            <Boton icono={<Link2 aria-hidden className="size-5" />} onClick={crear}>
              Crear enlace
            </Boton>
          </Acciones>
        </Columna>
        <VistaPrevia titulo={`Lo que verá ${quien}`} campos={campos} />
      </Columnas>
    </PaginaFicha>
  )
}

/** El momento orquestado de la demo: el enlace se traza y el PIN cae dígito a dígito. */
export function EnlacePin() {
  const { s, haz } = useDemo()
  const a = s.accesos.find((x) => x.id === s.pinVisible) ?? null
  if (!a) {
    return (
      <PaginaFicha>
        <div className="flex max-w-prose flex-col gap-4">
          <Nota titulo="El PIN ya no se puede ver" icono={<KeyRound aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />}>
            Por seguridad se muestra una sola vez. Si se perdió, crea un enlace nuevo y corta el anterior.
          </Nota>
          <Acciones>
            <Boton onClick={() => haz((x) => reemplazar(x, 'compartir'))}>Crear un enlace nuevo</Boton>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'enlaces']))}>
              Ver los enlaces
            </Boton>
          </Acciones>
        </div>
      </PaginaFicha>
    )
  }
  const url = `matu.cl/r#${a.token.slice(0, 14)}…`
  return (
    <PaginaFicha>
      <Columnas>
        <Columna etiqueta="Enlace creado">
          <div className="flex items-center gap-4">
            <span className="grid size-16 shrink-0 place-items-center rounded-2xl bg-pino text-papel">
              <svg viewBox="0 0 24 24" className="size-9" aria-hidden fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" pathLength={1} strokeDasharray="1" className="animate-trazo" />
                <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" pathLength={1} strokeDasharray="1" className="animate-trazo [animation-delay:250ms]" />
              </svg>
            </span>
            <div className="min-w-0">
              <p className="titular text-3xl" role="status">
                Enlace creado para {a.nombre}
              </p>
              <p className="text-tenue">
                Vence el <span className="cifras">{fmtFecha(a.venceMin)}</span> a las <span className="cifras">{fmtHora(a.venceMin)}</span>. Ve {listaCampos(a.campos)}.
              </p>
            </div>
          </div>
          <p className="flex items-center gap-2 border-y border-linea py-3 text-tenue">
            <Link2 aria-hidden className="size-5 shrink-0 text-pino" />
            <span className="min-w-0 truncate">{url}</span>
          </p>
          <Acciones>
            <Boton
              icono={<Send aria-hidden className="size-5" />}
              onClick={() => haz((x) => avisar(x, `En la app se abre WhatsApp con el enlace para ${a.nombre}, sin el PIN. En la demo no se envía nada.`))}
            >
              Enviar el enlace por WhatsApp
            </Boton>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'enlaces']))}>
              Ver los enlaces
            </Boton>
          </Acciones>
        </Columna>

        <Columna etiqueta="PIN">
          <section aria-labelledby="pin-t" className="flex flex-col gap-4 bg-rocio px-6 py-6">
            <h2 id="pin-t" className="flex items-center gap-2 text-xl font-bold">
              <KeyRound aria-hidden className="size-5 text-pino" />
              PIN para abrir la ficha
            </h2>
            <p className="flex justify-center gap-3" aria-label={`PIN: ${a.pin.split('').join(' ')}`}>
              {a.pin.split('').map((d, i) => (
                <span
                  key={i}
                  aria-hidden
                  className="digitos grid h-22 w-17 place-items-center rounded-xl bg-hoja text-6xl leading-none font-bold text-pino animate-digito"
                  style={{ animationDelay: `${600 + i * 160}ms` }}
                >
                  {d}
                </span>
              ))}
            </p>
            <p className="text-base">
              <b>Díctaselo a {a.nombre} por teléfono.</b> No lo mandes junto con el enlace. Solo lo verás ahora.
            </p>
          </section>
        </Columna>
      </Columnas>
    </PaginaFicha>
  )
}

// ---------- Enlaces y quién la vio ----------

export function Enlaces() {
  const { s, haz } = useDemo()
  const lista = [...s.accesos].sort((a, b) => Number(accesoVigente(b, s.ahora)) - Number(accesoVigente(a, s.ahora)) || b.creadoMin - a.creadoMin)
  return (
    <PaginaFicha bajada="Al cortar un enlace deja de abrir de inmediato. Quien lo tenía no recibe aviso.">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Enlaces">
          {lista.length === 0 && <Nota>No hay enlaces todavía. Crea uno desde Compartir.</Nota>}
          <ul className="flex flex-col gap-3">
            {lista.map((a) => {
              const vig = accesoVigente(a, s.ahora)
              const estado = estadoAccesoTexto(a, s.ahora)
              return (
                <li key={a.id} className={`flex flex-col gap-2 border-l-4 bg-hoja px-4 py-3.5 ${vig ? 'border-pino' : estado === 'Bloqueado' ? 'border-atenta' : 'border-tinta/20'}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-lg font-bold">{a.nombre}</h2>
                    {vig ? (
                      <Etiqueta tono="pino">
                        <Clock3 aria-hidden className="size-4" /> Activo, vence en <span className="cifras">{fmtRestante(a.venceMin, s.ahora)}</span>
                      </Etiqueta>
                    ) : (
                      <Etiqueta tono={estado === 'Bloqueado' ? 'atenta' : 'neutro'}>
                        {estado === 'Bloqueado' ? <CircleAlert aria-hidden className="size-4" /> : <Unlink aria-hidden className="size-4" />}
                        {estado}
                      </Etiqueta>
                    )}
                  </div>
                  <p className="text-tenue">
                    Ve {listaCampos(a.campos)}.{a.motivo ? ` ${a.motivo}.` : ''}
                  </p>
                  <p className="cifras text-sm text-tenue">
                    {vig
                      ? `Creado: ${fmtCuando(a.creadoMin, s.ahora)}. Vence: ${fmtCuando(a.venceMin, s.ahora)}.`
                      : estado === 'Vencido'
                        ? `Venció: ${fmtCuando(a.venceMin, s.ahora)}.`
                        : estado === 'Bloqueado'
                          ? 'Se bloqueó porque el PIN se escribió mal cinco veces.'
                          : `Creado: ${fmtCuando(a.creadoMin, s.ahora)}.`}
                  </p>
                  {vig && (
                    <Boton variante="secundario" className="self-start" icono={<Unlink aria-hidden className="size-5" />} onClick={() => haz((x) => cortarAcceso(x, a.id))}>
                      Cortar el enlace de {a.nombre}
                    </Boton>
                  )}
                </li>
              )
            })}
          </ul>
          <Acciones>
            <Boton variante="suave" icono={<Link2 aria-hidden className="size-5" />} onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'compartir']))}>
              Crear un enlace nuevo
            </Boton>
          </Acciones>
        </Columna>
        <Columna etiqueta="Últimas aperturas">
          <Subtitulo>Últimas aperturas</Subtitulo>
          <Eventos maximo={4} />
          <Boton variante="texto" className="self-start" onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'quien-vio']))}>
            Ver todo en Quién la vio
          </Boton>
        </Columna>
      </Columnas>
    </PaginaFicha>
  )
}

function Eventos({ maximo }: { maximo?: number }) {
  const { s } = useDemo()
  const lista = maximo ? s.eventos.slice(0, maximo) : s.eventos
  if (lista.length === 0) return <Nota>Todavía nadie ha abierto la ficha. Cuando alguien la abra, aparece aquí.</Nota>
  return (
    <ol className="flex flex-col">
      {lista.map((e) => (
        <li key={e.id} className="flex items-start gap-3 border-b border-linea py-3 last:border-0">
          <span className={`mt-0.5 grid size-9 shrink-0 place-items-center rounded-full ${e.tono === 'atento' ? 'bg-atenta-fondo text-atenta' : 'bg-rocio text-pino'}`}>
            {e.tono === 'atento' ? <CircleAlert aria-hidden className="size-5" /> : <UserRound aria-hidden className="size-5" />}
          </span>
          <span className="min-w-0">
            <span className="block font-bold">{e.texto}</span>
            <span className="cifras text-base text-tenue">{fmtCuando(e.minuto, s.ahora)}</span>
          </span>
        </li>
      ))}
    </ol>
  )
}

export function QuienVio() {
  const { s, haz } = useDemo()
  const vigentes = s.accesos.filter((a) => accesoVigente(a, s.ahora))
  return (
    <PaginaFicha bajada="Una línea por cada vez que alguien abre la ficha o escribe mal el PIN. Es un respaldo para ti, no una vigilancia.">
      <Columnas izquierda="ancha">
        <Columna etiqueta="Aperturas">
          <Eventos />
        </Columna>
        <Columna etiqueta="Quién puede verla ahora">
          <Subtitulo>Quién puede verla ahora</Subtitulo>
          {vigentes.length === 0 ? (
            <p className="text-tenue">Nadie. No hay enlaces activos.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {vigentes.map((a) => (
                <li key={a.id} className="flex flex-wrap items-baseline justify-between gap-2 border-l-4 border-pino bg-hoja px-4 py-2.5">
                  <span className="font-bold">{a.nombre}</span>
                  <span className="cifras text-tenue">vence en {fmtRestante(a.venceMin, s.ahora)}</span>
                </li>
              ))}
            </ul>
          )}
          <Boton variante="secundario" className="self-start" onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'enlaces']))}>
            Ver y cortar enlaces
          </Boton>
          <p className="flex gap-2 text-base text-tenue">
            <ShieldCheck aria-hidden className="mt-0.5 size-4.5 shrink-0" />
            Nadie de MATU puede abrir la ficha. Si alguna vez pasara, aparecería aquí.
          </p>
        </Columna>
      </Columnas>
    </PaginaFicha>
  )
}

// ---------- Para imprimir ----------

export function Imprimir() {
  const { s } = useDemo()
  const pila = nombrePila(s)
  return (
    <PaginaFicha bajada="La ficha en una hoja, para pegar en el refrigerador. Sirve sin conexión y sin aplicación.">
      <Columnas izquierda="ancha">
        <div className="@container max-w-3xl">
          <HojaFicha
            etiqueta={`Hoja impresa de la ficha de ${pila}`}
            textos={textosDe(s)}
            vacio={`Sin completar. Pregúntale a ${s.cuenta?.nombre || 'Carmen'}.`}
            encabezado={
              <>
                <header className="flex items-end justify-between gap-3 border-b-2 border-tinta pb-3">
                  <div className="min-w-0">
                    <p className="text-tenue">Ficha de relevo de</p>
                    <h2 className="titular text-4xl @2xl:text-5xl leading-none">{pila}</h2>
                  </div>
                  <Logo className="size-10 shrink-0" />
                </header>
                <p className="mt-3">Para quien la cuide hoy. Gracias por estar.</p>
              </>
            }
            pie={
              <footer className="mt-6 border-t border-dashed border-linea pt-2 text-sm text-tenue">
                Impresa el <span className="cifras">{fmtFecha(s.ahora)}</span>. Si algo cambia, vuelve a imprimirla.
              </footer>
            }
          />
        </div>
        <Columna etiqueta="Sobre la hoja impresa">
          <Nota titulo="En la app se descarga lista para imprimir">En la demo se muestra aquí, tal como sale en papel.</Nota>
        </Columna>
      </Columnas>
    </PaginaFicha>
  )
}
