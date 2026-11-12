// Invitar a alguien al grupo (MATU-42 y MATU-53, especificación docs/diseno/matu-53-invitar-grupo.md
// v1.1, sección 3). Contrato: `POST …/invitaciones` con solo el rol (decisiones 294 a 297).
//
// - Ningún rol elegido de partida, y ningún campo de correo, teléfono ni nombre (D-42-1 a).
// - La `url` y el `codigo` salen una sola vez: viven en la memoria de `/grupo/invitar/listo` y se
//   pierden al salir o recargar (3.6). Nunca van a la URL, al `<title>`, a `history.state` ni al
//   almacenamiento del navegador, y el texto que se comparte nunca lleva el código (C33).
// - Los dígitos del código aparecen quietos: la caída es solo del PIN del relevo (3.4).
import { useEffect, useId, useRef, useState } from 'react'
import { CircleCheck, Copy, KeyRound, Link2, MailPlus, Send } from 'lucide-react'
import { flushSync } from 'react-dom'
import { esperaDe, leerFallo } from '../compartido/api/cliente'
import { crearInvitacion, listarGrupos, listarMiembros, nombrePilaDe, type InvitacionCreada, type Rol } from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { urlCorta } from './Compartir'
import { useFamilia } from './estado'
import { IconoTelefono } from './Miembros'
import { FechaYHora } from './PiezasInvitar'
import { navegar } from './ruteo'
import { GRUPO_FAMILIAR } from './textosGrupo'
import { descripcionRol, INVITACION, INVITAR as T, ROL, teInvita } from './textosInvitar'
import { Acciones, CampoTexto, GrupoOpciones, MensajeError, Nota, Titulo, Volver } from './ui'

const ROLES: Rol[] = ['admin', 'cuidador', 'pagador', 'observador']

/**
 * La invitación recién creada, de camino a `/grupo/invitar/listo`. La pantalla la toma al montarse y
 * la borra de aquí: recargar o volver a entrar muestra «El código ya no se puede ver» (3.6).
 */
let creadaPendiente: InvitacionCreada | null = null

// ---------------------------------------------------------------- 3.1 a 3.3 /grupo/invitar

export function Invitar() {
  const { grupo, personas, capa3, conocerCapa3, fijar } = useFamilia()
  const [rol, setRol] = useState<Rol | null>(null)
  const [sinRol, setSinRol] = useState(false)
  const [falla, setFalla] = useState<'red' | 'tope' | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [miNombre, setMiNombre] = useState<string | null>(null)
  // Tras validar sin rol, el foco va a la primera opción, cuando el error ya está en pantalla (3.2).
  const [enfocarOpcion, setEnfocarOpcion] = useState(0)
  const nombreRadios = `rol-invitacion-${useId()}`
  const enCurso = useRef(false)
  const pilas = (personas ?? []).map(nombrePilaDe)

  useEffect(() => {
    if (capa3 === null) conocerCapa3?.()
  }, [capa3, conocerCapa3])

  // 3.2: la vista previa usa el nombre de pila de quien invita, el mismo que verá la persona (la
  // primera palabra del nombre en la lista del grupo). Si no se puede pedir, la vista previa no aparece.
  useEffect(() => {
    if (!grupo) return
    let vivo = true
    listarMiembros(grupo.id)
      .then((ms) => {
        const yo = ms.find((m) => m.eres_tu)
        if (vivo && yo) setMiNombre(yo.nombre.trim().split(/\s+/)[0] ?? null)
      })
      .catch(() => {})
    return () => {
      vivo = false
    }
  }, [grupo])

  useEffect(() => {
    if (!enfocarOpcion) return
    document.querySelector<HTMLInputElement>(`input[name="${nombreRadios}"]`)?.focus()
  }, [enfocarOpcion, nombreRadios])

  const crear = async () => {
    if (enCurso.current || !grupo) return
    setFalla(null)
    if (!rol) {
      setSinRol(true)
      setEnfocarOpcion((n) => n + 1)
      return
    }
    enCurso.current = true
    setOcupado(true)
    try {
      const creada = await crearInvitacion(grupo.id, rol)
      creadaPendiente = creada
      enCurso.current = false
      navegar('/grupo/invitar/listo')
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (esperaDe(f)) setFalla('tope')
      else if (f.status === 404) {
        // 3.7: dejó de administrar mientras tanto. Vuelve a Grupo familiar con el aviso y el rol nuevo.
        const grupos = await listarGrupos().catch(() => null)
        flushSync(() => fijar({ ...(grupos ? { grupos } : {}), aviso: { titulo: T.yaNoAdministras, tono: 'rocio' } }))
        navegar('/grupo', { reemplazar: true })
      } else setFalla('red')
    } finally {
      enCurso.current = false
      setOcupado(false)
    }
  }

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Volver onClick={() => navegar('/grupo')}>{GRUPO_FAMILIAR.volverAGrupo}</Volver>
        <Titulo className="text-3xl @2xl/main:text-4xl">{T.titulo}</Titulo>
        <p className="max-w-prose text-base text-tenue">{T.bajada}</p>
      </div>
      <div className="grid grid-cols-1 items-start gap-10 @3xl/main:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="flex min-w-0 flex-col gap-6">
          <GrupoOpciones
            nombre={nombreRadios}
            leyenda={T.leyenda}
            valor={rol}
            onCambio={(v) => {
              if (enCurso.current) return
              setRol(v)
              setSinRol(false)
            }}
            error={sinRol ? T.sinRol : null}
            errorArriba
            describirOpciones
            deshabilitada={ocupado}
            opciones={ROLES.map((r) => ({ valor: r, texto: ROL[r], detalle: descripcionRol(r, { capa3: capa3 === true, pilas }) }))}
          />
          {/* 9: la advertencia de admin aparece en una región viva montada desde el principio. */}
          <div aria-live="polite" className="empty:hidden">
            {rol === 'admin' && (
              <Nota tono="atenta" className="max-w-xl">
                {T.avisoAdmin}
              </Nota>
            )}
          </div>
          {pilas.length > 0 && (
            <Nota tono="rocio" icono={<IconoTelefono />} className="max-w-xl">
              {T.cuentale(pilas)}
            </Nota>
          )}
          <div className="flex flex-col items-start gap-3">
            {falla && (
              <Nota tono="atenta" rol="alert">
                {falla === 'tope' ? T.tope : T.errRed}
              </Nota>
            )}
            <p className="text-base text-tenue">{T.vale}</p>
            <Boton ocupado={ocupado} textoOcupado={T.creando} onClick={() => void crear()}>
              {T.crear}
            </Boton>
          </div>
        </div>
        {miNombre && (
          <section aria-labelledby="vista-previa-t" className="flex min-w-0 flex-col gap-3 @3xl/main:sticky @3xl/main:top-6">
            <h2 id="vista-previa-t" className="text-lg font-bold">
              {T.vistaPrevia}
            </h2>
            <div className="flex flex-col gap-2 rounded-xl bg-hoja p-4 angosto:px-2 text-base ring-1 ring-linea">
              <p className="break-words">{teInvita(miNombre, rol)}</p>
              <p>{INVITACION.escribeElCodigo}</p>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- 3.4 a 3.6 /grupo/invitar/listo

export function InvitacionLista() {
  // El estado de esta pantalla es el único lugar donde vive el código. Recargar lo pierde (3.6).
  const [creada] = useState(() => creadaPendiente)
  useEffect(() => {
    creadaPendiente = null
  }, [])
  return creada ? <CodigoUnaVez c={creada} /> : <CodigoPerdido />
}

function CodigoPerdido() {
  return (
    <div className="flex max-w-prose flex-col gap-5">
      <Titulo>{T.lista}</Titulo>
      <Nota tono="rocio" titulo={T.perdidoTitulo} icono={<KeyRound aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
        {T.perdido}
      </Nota>
      <Acciones>
        <Boton variante="secundario" onClick={() => navegar('/grupo')}>
          {GRUPO_FAMILIAR.volverAGrupo}
        </Boton>
      </Acciones>
    </div>
  )
}

function CodigoUnaVez({ c }: { c: InvitacionCreada }) {
  const puedeEnviar = typeof navigator !== 'undefined' && typeof navigator.share === 'function'
  const [copia, setCopia] = useState<'ok' | 'fallo' | null>(null)
  const digitos = useRef<HTMLParagraphElement>(null)
  // «Repetir el código»: el foco va al bloque de los dígitos después del render (sin `setTimeout`).
  const [repetir, setRepetir] = useState(0)
  useEffect(() => {
    if (repetir) digitos.current?.focus()
  }, [repetir])

  const enviar = async () => {
    try {
      // C33: el mensaje lleva solo el enlace. Nunca el código, ni el nombre de la persona ni del grupo.
      await navigator.share({ text: T.mensaje(c.url) })
    } catch {
      // Cerrar la hoja de compartir (AbortError) no es un error. Nada se registra.
    }
  }
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(c.url)
      setCopia('ok')
    } catch {
      setCopia('fallo')
    }
  }

  return (
    <div className="grid grid-cols-1 items-start gap-x-10 gap-y-7 @3xl/main:grid-cols-2">
      {/* A 360 px: título, código, enviar (si el teléfono descarta la pestaña al enviar, el código ya se vio). */}
      <div className="flex min-w-0 flex-col gap-3 @3xl/main:col-start-1 @3xl/main:row-start-1">
        <div className="flex items-center gap-4 angosto:flex-col angosto:items-start angosto:gap-3">
          <span aria-hidden className="grid size-16 shrink-0 place-items-center rounded-2xl bg-rocio text-turquesa">
            <MailPlus className="size-9" />
          </span>
          <div className="min-w-0">
            <Titulo className="text-3xl break-words">{T.lista}</Titulo>
            <p className="mt-1 text-base">
              <FechaYHora iso={c.expira_en} partes={T.valeHasta} />
            </p>
            <p className="text-base text-tenue">{T.para(c.rol)}</p>
          </div>
        </div>
      </div>

      <section
        aria-labelledby="codigo-t"
        className="flex min-w-0 max-w-lg flex-col gap-4 rounded-xl bg-rocio px-6 py-6 angosto:px-2 @3xl/main:col-start-2 @3xl/main:row-span-2 @3xl/main:row-start-1"
      >
        <h2 id="codigo-t" className="flex items-center gap-2 text-xl font-bold">
          <KeyRound aria-hidden className="size-5 shrink-0 text-turquesa" />
          {T.codigoTitulo}
        </h2>
        <p ref={digitos} tabIndex={-1} role="img" aria-label={T.codigoAria(c.codigo)} className="flex justify-center gap-3 angosto:gap-1.5 rounded-xl focus:outline-3 focus:outline-offset-2 focus:outline-turquesa">
          {c.codigo.split('').map((d, i) => (
            <span
              key={i}
              aria-hidden
              className="digitos grid h-22 w-17 place-items-center rounded-xl bg-hoja text-6xl leading-none font-bold text-turquesa telefono:w-auto telefono:min-w-0 telefono:flex-1 angosto:h-16 angosto:w-auto angosto:min-w-0 angosto:flex-1 angosto:text-3xl"
            >
              {d}
            </span>
          ))}
        </p>
        <p className="text-base">
          <b>{T.dictaselo[0]}</b>
          {T.dictaselo[1]}
        </p>
        <Boton variante="texto" className="self-start" onClick={() => setRepetir((n) => n + 1)}>
          {T.repetir}
        </Boton>
      </section>

      <div className="flex min-w-0 flex-col gap-4 @3xl/main:col-start-1 @3xl/main:row-start-2">
        <p className="flex min-w-0 items-center gap-2 border-y border-linea py-3 text-tenue">
          <Link2 aria-hidden className="size-5 shrink-0 text-turquesa" />
          <span className="min-w-0 truncate">{urlCorta(c.url)}</span>
        </p>
        <Acciones>
          {puedeEnviar && (
            <Boton icono={<Send aria-hidden className="size-5" />} onClick={() => void enviar()}>
              {T.enviar}
            </Boton>
          )}
          <Boton variante={puedeEnviar ? 'secundario' : 'principal'} icono={<Copy aria-hidden className="size-5" />} onClick={() => void copiar()}>
            {T.copiar}
          </Boton>
          <Boton variante="texto" onClick={() => navegar('/grupo')}>
            {GRUPO_FAMILIAR.volverAGrupo}
          </Boton>
        </Acciones>
        <div role="status">
          {copia === 'ok' && (
            <p className="flex gap-2 text-base">
              <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" />
              <span className="min-w-0">{T.copiado}</span>
            </p>
          )}
          {copia === 'fallo' && puedeEnviar && <MensajeError>{T.noCopiado}</MensajeError>}
        </div>
        {/* Sin compartir del sistema y sin portapapeles: el único caso en que el enlace se ve completo. */}
        {copia === 'fallo' && !puedeEnviar && (
          <CampoTexto etiqueta={T.enlaceDeLaInvitacion} readOnly value={c.url} autoComplete="off" onFocus={(e) => e.currentTarget.select()} />
        )}
      </div>
    </div>
  )
}
