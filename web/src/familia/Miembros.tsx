// Quiénes forman el grupo, las invitaciones sin usar y salir del grupo (MATU-42 y MATU-53,
// especificación docs/diseno/matu-53-invitar-grupo.md v1.1, secciones 5 a 7). Contrato:
// `GET …/miembros`, `PATCH` y `DELETE …/miembros/{id}`, `POST …/salida`, `GET` y `DELETE
// …/invitaciones` (decisiones 302 a 308).
//
// - Sin interfaz optimista: la lista cambia solo con la respuesta de la API (cambiar el rol, el
//   permiso de la ficha, sacar, salir y anular).
// - `PATCH` lleva `If-Match` con el `etag` de la fila. Un 412 no se oculta: el diálogo se queda, muestra
//   el valor vigente y pide volver a elegir (6.6).
// - Ninguna ruta lleva el id de una membresía ni de una invitación: el elegido vive en el estado del diálogo.
// - El foco se mueve en un efecto, después del render que dibuja su destino. Sin `setTimeout`.
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { CloudOff, Eye, EyeOff, Lock, Phone } from 'lucide-react'
import { isAxiosError } from 'axios'
import { leerFallo } from '../compartido/api/cliente'
import {
  anularInvitacion,
  cambiarMiembro,
  leerConflictoMiembro,
  listarGrupos,
  listarInvitaciones,
  listarMiembros,
  sacarMiembro,
  salirDelGrupo,
  type InvitacionPendiente,
  type Miembro,
  rolDe,
  type Rol,
} from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { nombreDeAutor } from './autor'
import { useFamilia } from './estado'
import { esTipo } from './insumosComun'
import { DialogoGrupo, FechaYHora, Puntos, SoloFecha } from './PiezasInvitar'
import { navegar } from './ruteo'
import { GRUPO_FAMILIAR } from './textosGrupo'
import { ANULAR, CAMBIAR_ROL as CR, descripcionRol, INVITACIONES_SE_ANULAN as SE_ANULAN, MIEMBROS as M, PERMISO_FICHA as PF, ROL, SACAR, SALIR } from './textosInvitar'
import { Etiqueta, GrupoOpciones, MensajeError, Nota } from './ui'

const ROLES: Rol[] = ['admin', 'cuidador', 'pagador', 'observador']
const editaFicha = (r: Rol) => r === 'admin' || r === 'cuidador'
const ID_NOTA = 'nota-miembros'

type Carga = 'cargando' | 'lista' | 'red'
type NotaMiembros = { tono: 'ok' | 'rocio'; texto: string; /** `null`: arriba de la lista; un id: bajo esa fila. */ fila: string | null }

/**
 * La lista y las invitaciones, y lo que hace falta para volver a pedirlas. La usan los dos bloques de
 * Grupo familiar: «Quiénes forman el grupo», arriba, y «Salir del grupo», al final (5.1).
 */
export function useMiembros() {
  const { grupo, rol, alEntrar, fijar } = useFamilia()
  const grupoId = grupo?.id ?? null
  const admin = rol === 'admin'
  const [carga, setCarga] = useState<Carga>('cargando')
  const [miembros, setMiembros] = useState<Miembro[]>([])
  const [invitaciones, setInvitaciones] = useState<InvitacionPendiente[]>([])

  /** 5.9 «Me sacaron»: la app vuelve a pedir los grupos y sigue la regla de MATU-39. */
  const meSacaron = useCallback(async () => {
    try {
      await alEntrar()
    } catch {
      // Sin red: la regla de la ruta se aplica igual con lo que hay.
    }
    navegar('/', { reemplazar: true })
  }, [alEntrar])

  /**
   * Vuelve a pedir los grupos, para el rol propio (5.9 «Dejé de administrar» y 6.4). Devuelve el rol
   * nuevo, `null` si el grupo ya no está (me sacaron: la app sigue la regla de MATU-39) y `undefined`
   * si no se pudo saber (sin red: el rol queda como estaba y la siguiente petición lo corrige).
   */
  const refrescarRol = useCallback(async (): Promise<Rol | null | undefined> => {
    try {
      const grupos = await listarGrupos()
      const mio = grupos.find((g) => g.id === grupoId)
      if (!mio) {
        void meSacaron()
        return null
      }
      fijar({ grupos })
      return rolDe(mio)
    } catch {
      return undefined
    }
  }, [grupoId, fijar, meSacaron])

  const cargar = useCallback(async () => {
    if (!grupoId) return
    setCarga('cargando')
    try {
      const [lista, pendientes] = await Promise.all([
        listarMiembros(grupoId),
        // Las invitaciones son solo de quien administra (C10). Si fallan, el bloque no aparece y la
        // lista se muestra igual: los bloques fallan por separado (5.9).
        admin ? listarInvitaciones(grupoId).catch(() => [] as InvitacionPendiente[]) : Promise.resolve([] as InvitacionPendiente[]),
      ])
      setMiembros(lista)
      setInvitaciones(pendientes)
      setCarga('lista')
    } catch (x) {
      if (esVencida(x)) return
      if (leerFallo(x).status === 404) return void meSacaron()
      setCarga('red')
    }
  }, [grupoId, admin, meSacaron])

  useEffect(() => {
    void cargar()
  }, [cargar])

  /**
   * v1.3 (O4): quien deja de administrar pierde sus invitaciones sin usar (decisión 322). Se vuelven a
   * pedir solas, sin «Cargando…»: la lista de miembros y su nota no se desmontan.
   */
  const recargarInvitaciones = useCallback(async () => {
    if (!grupoId || !admin) return
    try {
      setInvitaciones(await listarInvitaciones(grupoId))
    } catch {
      // Si falla, la lista queda como estaba; la próxima carga la corrige.
    }
  }, [grupoId, admin])

  return { carga, miembros, setMiembros, invitaciones, setInvitaciones, cargar, recargarInvitaciones, refrescarRol, meSacaron }
}

export type DatosMiembros = ReturnType<typeof useMiembros>

// ---------------------------------------------------------------- 5 Quiénes forman el grupo

type Dialogo =
  | { tipo: 'rol'; miembro: Miembro }
  | { tipo: 'dar' | 'quitar'; miembro: Miembro }
  | { tipo: 'sacar'; miembro: Miembro }
  | { tipo: 'anular'; invitacion: InvitacionPendiente }

export function QuienesForman({ datos, pilas }: { datos: DatosMiembros; pilas: readonly string[] }) {
  const { grupo, rol } = useFamilia()
  const admin = rol === 'admin'
  const { carga, miembros, setMiembros, invitaciones, setInvitaciones, cargar, recargarInvitaciones, refrescarRol } = datos
  const [dialogo, setDialogo] = useState<Dialogo | null>(null)
  const [nota, setNota] = useState<NotaMiembros | null>(null)
  const [notaInvitaciones, setNotaInvitaciones] = useState<{ tono: 'ok' | 'rocio'; texto: string } | null>(null)
  // Adónde va el foco después del próximo render: el botón que abrió el diálogo, o una nota.
  const [enfocar, setEnfocar] = useState<{ id: string } | null>(null)

  useEffect(() => {
    if (!enfocar) return
    document.getElementById(enfocar.id)?.focus()
  }, [enfocar])

  const admins = miembros.filter((m) => m.rol === 'admin').length
  const yo = miembros.find((m) => m.eres_tu) ?? null

  const conNota = (n: NotaMiembros) => {
    setNota(n)
    setEnfocar({ id: ID_NOTA })
  }

  const cerrarYVolver = (id: string) => {
    setDialogo(null)
    setEnfocar({ id })
  }

  /**
   * 5.9: 404 al gestionar. Se vuelven a pedir el rol propio y la lista. Si otra persona me bajó de
   * rol, los botones desaparecen (el rol en memoria cambia) y la nota lo dice.
   */
  const noEncontrado = async () => {
    setDialogo(null)
    const nuevo = await refrescarRol()
    if (nuevo === null) return
    await cargar()
    conNota({ tono: 'rocio', texto: nuevo !== undefined && nuevo !== 'admin' ? M.yaNoAdministras : M.yaNoEstaba, fila: null })
  }

  const cambiado = (m: Miembro, texto: string) => {
    setDialogo(null)
    const antes = miembros.find((x) => x.id === m.id)
    setMiembros((xs) => xs.map((x) => (x.id === m.id ? m : x)))
    // v1.3 (O4): si dejó de administrar, sus invitaciones sin usar ya no están.
    if (antes?.rol === 'admin' && m.rol !== 'admin' && !m.eres_tu) void recargarInvitaciones()
    if (m.eres_tu) {
      // 6.4: mi propio rol. La página se vuelve a dibujar con el rol nuevo y la nota va arriba.
      void refrescarRol()
      conNota({ tono: 'ok', texto, fila: null })
    } else conNota({ tono: 'ok', texto, fila: m.id })
  }

  let lista: ReactNode
  if (carga === 'cargando') lista = null
  else if (carga === 'red')
    lista = (
      <div className="flex max-w-prose flex-col items-start gap-4">
        <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
          {M.errCargar}
        </Nota>
        <Boton variante="secundario" onClick={() => void cargar()}>
          {M.volverAIntentar}
        </Boton>
      </div>
    )
  else
    lista = (
      <ul className="flex max-w-3xl flex-col divide-y divide-linea rounded-xl bg-hoja ring-1 ring-linea">
        {miembros.map((m) => (
          <Fila
            key={m.id}
            m={m}
            admin={admin}
            unicoAdmin={admins <= 1}
            nota={nota?.fila === m.id ? nota : null}
            onCambiar={() => setDialogo({ tipo: 'rol', miembro: m })}
            onFicha={() => setDialogo({ tipo: m.puede_ver_plan ? 'quitar' : 'dar', miembro: m })}
            onSacar={() => setDialogo({ tipo: 'sacar', miembro: m })}
          />
        ))}
      </ul>
    )

  return (
    <div className="flex flex-col gap-10">
      <section aria-labelledby="miembros-t" className="flex flex-col gap-4">
        <h2 id="miembros-t" className="text-xl font-bold">
          {M.titulo}
        </h2>
        {nota && nota.fila === null && (
          <Nota id={ID_NOTA} tono={nota.tono} rol="status" enfocable>
            {nota.texto}
          </Nota>
        )}
        {lista}
        {carga === 'lista' && !admin && <p className="max-w-prose text-base text-tenue">{M.soloAdmin}</p>}
        {carga === 'lista' && admin && (
          <div className="flex flex-col items-start gap-4">
            {miembros.length === 1 && yo && <p className="max-w-prose text-base">{M.soloTu}</p>}
            <Boton onClick={() => navegar('/grupo/invitar')}>{M.invitar}</Boton>
          </div>
        )}
      </section>

      {admin && carga === 'lista' && (invitaciones.length > 0 || notaInvitaciones) && (
        <section aria-labelledby="invitaciones-t" className="flex flex-col gap-4">
          <h2 id="invitaciones-t" className="text-xl font-bold">
            {M.invitaciones}
          </h2>
          {notaInvitaciones && (
            <Nota id="nota-invitaciones" tono={notaInvitaciones.tono} rol="status" enfocable>
              {notaInvitaciones.texto}
            </Nota>
          )}
          {invitaciones.length > 0 && (
            <ul className="flex max-w-3xl flex-col divide-y divide-linea rounded-xl bg-hoja ring-1 ring-linea">
              {invitaciones.map((i) => (
                <li key={i.id} className="flex flex-col gap-1 px-4 angosto:px-2 py-4">
                  <p id={`invitacion-${i.id}`} className="text-base font-bold">
                    <LineaInvitacion i={i} />
                  </p>
                  {i.estado === 'bloqueada' && (
                    <p className="flex gap-2 text-base">
                      <Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue" />
                      <span className="min-w-0">{M.bloqueada}</span>
                    </p>
                  )}
                  <p className="text-base text-tenue">{M.laCreo(nombreDeAutor(i.invitada_por) ?? '')}</p>
                  <Boton
                    id={`anular-${i.id}`}
                    variante="textoPeligro"
                    className="self-start"
                    aria-describedby={`invitacion-${i.id}`}
                    onClick={() => setDialogo({ tipo: 'anular', invitacion: i })}
                  >
                    {M.anular}
                  </Boton>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {dialogo?.tipo === 'rol' && (
        <DialogoRol
          miembro={dialogo.miembro}
          pilas={pilas}
          onCancelar={() => cerrarYVolver(`cambiar-${dialogo.miembro.id}`)}
          onHecho={(m, n) => cambiado(m, m.eres_tu ? CR.hechoPropio(m.rol, n) : CR.hecho(m.nombre, m.rol, n))}
          onUltimoAdmin={() => void cargar()}
          onNoEncontrado={() => void noEncontrado()}
        />
      )}
      {(dialogo?.tipo === 'dar' || dialogo?.tipo === 'quitar') && (
        <DialogoFicha
          miembro={dialogo.miembro}
          dar={dialogo.tipo === 'dar'}
          pilas={pilas}
          onCancelar={() => cerrarYVolver(`ficha-${dialogo.miembro.id}`)}
          onHecho={(m) => cambiado(m, m.puede_ver_plan ? PF.dado(m.nombre) : PF.quitado(m.nombre))}
          onNoEncontrado={() => void noEncontrado()}
        />
      )}
      {dialogo?.tipo === 'sacar' && grupo && (
        <DialogoSacar
          grupoId={grupo.id}
          miembro={dialogo.miembro}
          onCancelar={() => cerrarYVolver(`sacar-${dialogo.miembro.id}`)}
          onHecho={(n) => {
            const m = dialogo.miembro
            setDialogo(null)
            setMiembros((xs) => xs.filter((x) => x.id !== m.id))
            // v1.3 (O4): sacar a quien administra anula sus invitaciones sin usar.
            if (m.rol === 'admin') void recargarInvitaciones()
            // 9: la fila ya no existe; el foco va a la nota de arriba de la lista.
            conNota({ tono: 'ok', texto: SACAR.hecho(m.nombre, n), fila: null })
          }}
          onUltimoAdmin={() => void cargar()}
          onNoEncontrado={() => void noEncontrado()}
        />
      )}
      {dialogo?.tipo === 'anular' && grupo && (
        <DialogoAnular
          grupoId={grupo.id}
          invitacion={dialogo.invitacion}
          onCancelar={() => cerrarYVolver(`anular-${dialogo.invitacion.id}`)}
          onHecho={(nota) => {
            const id = dialogo.invitacion.id
            setDialogo(null)
            setInvitaciones((xs) => xs.filter((x) => x.id !== id))
            setNotaInvitaciones(nota)
            setEnfocar({ id: 'nota-invitaciones' })
            // 5.4.1: el 409 vuelve a pedir la lista, que desmonta y vuelve a montar la nota. El foco se
            // le da otra vez cuando terminó, en el efecto del render que la monta: nunca queda en el body.
            if (nota.tono === 'rocio') void cargar().then(() => setEnfocar({ id: 'nota-invitaciones' }))
          }}
          onNoEncontrado={() => void noEncontrado()}
        />
      )}
    </div>
  )
}

/** 5.4 y 5.4.1: «{rol} · vence el {fecha} a las {hora}.» o, bloqueada, «{rol} · se bloqueó.» (v1.2). */
function LineaInvitacion({ i }: { i: InvitacionPendiente }) {
  return i.estado === 'bloqueada' ? (
    <>
      {ROL[i.rol]} {M.seBloqueo}
    </>
  ) : (
    <>
      {ROL[i.rol]} <FechaYHora iso={i.expira_en} partes={M.vence} />
    </>
  )
}

/** 5.3: una persona del grupo. El rol siempre en palabra; el permiso del pagador con ícono y palabra. */
function Fila({
  m,
  admin,
  unicoAdmin,
  nota,
  onCambiar,
  onFicha,
  onSacar,
}: {
  m: Miembro
  admin: boolean
  unicoAdmin: boolean
  nota: NotaMiembros | null
  onCambiar: () => void
  onFicha: () => void
  onSacar: () => void
}) {
  // C9: el permiso del pagador lo ve quien administra en todas las filas, y cada quien en la suya.
  const verPermiso = m.rol === 'pagador' && typeof m.puede_ver_plan === 'boolean' && (admin || m.eres_tu)
  const propiaUnicoAdmin = m.eres_tu && m.rol === 'admin' && unicoAdmin
  return (
    <li className="grid grid-cols-1 gap-y-1 px-4 angosto:px-2 py-4 @3xl/main:grid-cols-[12rem_minmax(0,1fr)] @3xl/main:gap-x-6">
      <p className="text-lg font-bold break-words @3xl/main:col-start-1 @3xl/main:row-start-1">
        {m.nombre}
        {m.eres_tu && <span className="font-normal"> {M.tu}</span>}
      </p>
      <div className="flex min-w-0 flex-col gap-1 @3xl/main:col-start-2 @3xl/main:row-start-1">
        <p className="text-base">{ROL[m.rol]}</p>
        {verPermiso && (
          <p className="flex items-center gap-2 text-base">
            {m.puede_ver_plan ? <Eye aria-hidden className="size-5 shrink-0 text-ok" /> : <EyeOff aria-hidden className="size-5 shrink-0 text-tenue" />}
            {m.puede_ver_plan ? M.puedeVerFicha : M.noVeFicha}
          </p>
        )}
        {propiaUnicoAdmin && <p className="max-w-prose text-base text-tenue">{M.unicoAdmin}</p>}
      </div>
      <p className="text-base text-tenue @3xl/main:col-start-1 @3xl/main:row-start-2">
        {M.seUnio} <SoloFecha iso={m.unido_en} />
      </p>
      {admin && !propiaUnicoAdmin && (
        <div className="flex flex-wrap gap-x-6 gap-y-0 angosto:flex-col angosto:items-start @3xl/main:col-start-2 @3xl/main:row-start-2">
          <Boton id={`cambiar-${m.id}`} variante="texto" aria-label={m.eres_tu ? undefined : M.cambiarDe(m.nombre)} onClick={onCambiar}>
            {m.eres_tu ? M.cambiarTuRol : M.cambiar}
          </Boton>
          {!m.eres_tu && m.rol === 'pagador' && (
            <Boton id={`ficha-${m.id}`} variante="texto" aria-label={m.puede_ver_plan ? M.quitarFichaA(m.nombre) : M.darFichaA(m.nombre)} onClick={onFicha}>
              {m.puede_ver_plan ? M.quitarFicha : M.darFicha}
            </Boton>
          )}
          {/* 5.3: nunca «Sacar del grupo» en la fila propia; para eso está «Salir del grupo». */}
          {!m.eres_tu && (
            <Boton id={`sacar-${m.id}`} variante="textoPeligro" aria-label={M.sacarA(m.nombre)} onClick={onSacar}>
              {M.sacar}
            </Boton>
          )}
        </div>
      )}
      {nota && (
        <Nota id={ID_NOTA} tono={nota.tono} rol="status" enfocable className="mt-2 @3xl/main:col-span-2">
          {nota.texto}
        </Nota>
      )}
    </li>
  )
}

// ---------------------------------------------------------------- 6 Cambiar el rol

/** La petición de un diálogo: sin dos a la vez, y el diálogo no se cierra mientras va (MATU-44 4.4). */
function usePeticion() {
  const enCurso = useRef(false)
  const [ocupado, setOcupado] = useState(false)
  const correr = async (fn: () => Promise<void>) => {
    if (enCurso.current) return
    enCurso.current = true
    setOcupado(true)
    try {
      await fn()
    } finally {
      enCurso.current = false
      setOcupado(false)
    }
  }
  return { enCurso, ocupado, correr }
}

/** El tipo del problema RFC 7807, y un miembro de extensión del cuerpo (`estado` de `invitacion-cerrada`). */
const extension = (x: unknown, campo: string): string | null => {
  if (!isAxiosError(x)) return null
  const v = (x.response?.data as Record<string, unknown> | undefined)?.[campo]
  return typeof v === 'string' ? v : null
}

function DialogoRol({
  miembro: inicial,
  pilas,
  onCancelar,
  onHecho,
  onUltimoAdmin,
  onNoEncontrado,
}: {
  miembro: Miembro
  pilas: readonly string[]
  onCancelar: () => void
  onHecho: (m: Miembro, enlacesCortados: number) => void
  onUltimoAdmin: () => void
  onNoEncontrado: () => void
}) {
  const { grupo, capa3 } = useFamilia()
  const [miembro, setMiembro] = useState(inicial)
  const [elegido, setElegido] = useState<Rol>(inicial.rol)
  const [error, setError] = useState<ReactNode>(null)
  const { enCurso, ocupado, correr } = usePeticion()
  const propia = miembro.eres_tu
  const actual = miembro.rol

  // 6.3: lo que se muestra según el cambio.
  const mismo = elegido === actual
  const dejoDeAdministrar = propia && actual === 'admin' && elegido !== 'admin'
  const pierdeFicha = !propia && ((editaFicha(actual) && !editaFicha(elegido)) || (actual === 'pagador' && miembro.puede_ver_plan === true && elegido === 'observador'))
  // v1.3 (O4): otra persona que administra pasa a «Cuida»: deja de administrar y sigue viendo la ficha.
  const otraDejaDeAdministrar = !propia && actual === 'admin' && elegido !== 'admin'
  // Mi propia fila: si además pierdo la ficha, la frase de los enlaces va antes que la de las invitaciones.
  const pierdoFicha = dejoDeAdministrar && !editaFicha(elegido)
  const misEnlaces = miembro.enlaces_vigentes === null ? '' : GRUPO_FAMILIAR.hoyAbren(miembro.enlaces_vigentes)
  const avisos: string[] = mismo
    ? []
    : dejoDeAdministrar
      ? [CR.dejasDeAdministrar, ...(pierdoFicha ? [[SALIR.seCortan, misEnlaces].filter(Boolean).join(' ')] : []), SE_ANULAN.propia]
      : !propia && elegido === 'admin'
        ? [CR.seraAdmin(miembro.nombre)]
        : pierdeFicha
          ? [
              CR.pierdeFicha(miembro.nombre, editaFicha(actual) ? miembro.enlaces_vigentes : 0),
              ...(elegido === 'pagador' && editaFicha(actual) ? [CR.comoPaga] : []),
              // La nota termina con las invitaciones (v1.3).
              ...(actual === 'admin' ? [SE_ANULAN.otra] : []),
            ]
          : otraDejaDeAdministrar
            ? [CR.dejaraDeAdministrar(miembro.nombre), SE_ANULAN.otra]
            : []
  const quita = dejoDeAdministrar || pierdeFicha || otraDejaDeAdministrar

  const guardar = () =>
    correr(async () => {
      if (!grupo || mismo) return
      setError(null)
      try {
        const r = await cambiarMiembro(grupo.id, miembro, { rol: elegido })
        enCurso.current = false
        onHecho(r.miembro, r.enlaces_cortados)
      } catch (x) {
        if (esVencida(x)) return
        const f = leerFallo(x)
        if (f.status === 412) {
          const vigente = leerConflictoMiembro(x)
          if (!vigente) {
            enCurso.current = false
            return onNoEncontrado()
          }
          // 6.6: lo elegido se pierde, a propósito: se elige sobre lo que hay.
          setMiembro(vigente)
          setElegido(vigente.rol)
          return setError(
            <Nota tono="atenta" className="max-w-none">
              {CR.conflicto(vigente.nombre, vigente.rol)}
            </Nota>,
          )
        }
        if (f.status === 409 && esTipo(f.tipo, 'ultimo-admin')) {
          onUltimoAdmin()
          return setError(<MensajeError>{M.necesitaAdmin}</MensajeError>)
        }
        if (f.status === 404) {
          enCurso.current = false
          return onNoEncontrado()
        }
        setError(<MensajeError>{CR.errRed}</MensajeError>)
      }
    })

  const idMismo = `mismo-${miembro.id}`
  return (
    <DialogoGrupo
      titulo={propia ? CR.preguntaTuya : CR.pregunta(miembro.nombre)}
      error={error}
      ocupado={ocupado}
      enCurso={enCurso}
      onCancelar={onCancelar}
      cancelar={CR.noCambiar}
      confirmar={{
        texto: CR.guardar,
        textoOcupado: CR.guardando,
        variante: quita ? 'peligroPrincipal' : 'principal',
        onClick: () => void guardar(),
        deshabilitado: mismo,
        describe: mismo ? idMismo : undefined,
        junto: mismo ? (
          <span id={idMismo} className="text-base text-tenue">
            {CR.mismoRol}
          </span>
        ) : undefined,
      }}
    >
      <GrupoOpciones
        nombre={`rol-${miembro.id}`}
        leyenda={CR.leyenda}
        valor={elegido}
        onCambio={(v) => {
          if (!enCurso.current) setElegido(v)
        }}
        detalleGrande
        describirOpciones
        opciones={ROLES.map((r) => ({
          valor: r,
          texto: ROL[r],
          detalle: descripcionRol(r, { capa3: capa3 === true, pilas }),
          extra: r === actual ? <Etiqueta>{CR.ahora}</Etiqueta> : undefined,
        }))}
      />
      {/* 9: la advertencia aparece en una región viva montada desde el principio. */}
      <div aria-live="polite" className="flex flex-col gap-2 empty:hidden">
        {avisos.length > 0 && (
          <Nota tono="atenta" className="max-w-none">
            {avisos.join(' ')}
          </Nota>
        )}
      </div>
    </DialogoGrupo>
  )
}

// ---------------------------------------------------------------- 6.7 El permiso del pagador

function DialogoFicha({
  miembro: inicial,
  dar,
  pilas,
  onCancelar,
  onHecho,
  onNoEncontrado,
}: {
  miembro: Miembro
  dar: boolean
  pilas: readonly string[]
  onCancelar: () => void
  onHecho: (m: Miembro) => void
  onNoEncontrado: () => void
}) {
  const { grupo } = useFamilia()
  const [miembro, setMiembro] = useState(inicial)
  const [error, setError] = useState<ReactNode>(null)
  const { enCurso, ocupado, correr } = usePeticion()
  // Tras un 412, si ya no es pagador o el permiso ya está como se quería, no queda nada que confirmar.
  const sentido = miembro.rol === 'pagador' && miembro.puede_ver_plan !== dar

  const guardar = () =>
    correr(async () => {
      if (!grupo || !sentido) return
      setError(null)
      try {
        const r = await cambiarMiembro(grupo.id, miembro, { puede_ver_plan: dar })
        enCurso.current = false
        onHecho(r.miembro)
      } catch (x) {
        if (esVencida(x)) return
        const f = leerFallo(x)
        if (f.status === 412) {
          const vigente = leerConflictoMiembro(x)
          if (!vigente) {
            enCurso.current = false
            return onNoEncontrado()
          }
          setMiembro(vigente)
          return setError(
            <Nota tono="atenta" className="max-w-none">
              {CR.conflicto(vigente.nombre, vigente.rol)}
            </Nota>,
          )
        }
        if (f.status === 404) {
          enCurso.current = false
          return onNoEncontrado()
        }
        setError(<MensajeError>{CR.errRed}</MensajeError>)
      }
    })

  return (
    <DialogoGrupo
      titulo={dar ? PF.darPregunta(miembro.nombre) : PF.quitarPregunta(miembro.nombre)}
      error={error}
      ocupado={ocupado}
      enCurso={enCurso}
      onCancelar={onCancelar}
      cancelar={dar ? PF.darNo : PF.quitarNo}
      confirmar={
        sentido
          ? {
              texto: dar ? PF.darBoton : PF.quitarBoton,
              textoOcupado: CR.guardando,
              variante: dar ? 'principal' : 'peligroPrincipal',
              onClick: () => void guardar(),
            }
          : undefined
      }
    >
      <p>{dar ? PF.darTexto(pilas) : PF.quitarTexto(miembro.nombre)}</p>
    </DialogoGrupo>
  )
}

// ---------------------------------------------------------------- 7.1 Sacar

function DialogoSacar({
  grupoId,
  miembro,
  onCancelar,
  onHecho,
  onUltimoAdmin,
  onNoEncontrado,
}: {
  grupoId: string
  miembro: Miembro
  onCancelar: () => void
  onHecho: (enlacesCortados: number) => void
  onUltimoAdmin: () => void
  onNoEncontrado: () => void
}) {
  const [error, setError] = useState<ReactNode>(null)
  const { enCurso, ocupado, correr } = usePeticion()
  const sacar = () =>
    correr(async () => {
      setError(null)
      try {
        const r = await sacarMiembro(grupoId, miembro.id)
        enCurso.current = false
        onHecho(r.enlaces_cortados)
      } catch (x) {
        if (esVencida(x)) return
        const f = leerFallo(x)
        if (f.status === 404) {
          enCurso.current = false
          return onNoEncontrado()
        }
        if (f.status === 409 && esTipo(f.tipo, 'ultimo-admin')) {
          onUltimoAdmin()
          return setError(<MensajeError>{M.necesitaAdmin}</MensajeError>)
        }
        setError(<MensajeError>{SACAR.errRed(miembro.nombre)}</MensajeError>)
      }
    })
  return (
    <DialogoGrupo
      titulo={SACAR.pregunta(miembro.nombre)}
      error={error}
      ocupado={ocupado}
      enCurso={enCurso}
      onCancelar={onCancelar}
      cancelar={SACAR.no}
      confirmar={{ texto: SACAR.boton, textoOcupado: SACAR.ocupado, variante: 'peligroPrincipal', onClick: () => void sacar() }}
    >
      <Puntos
        puntos={[
          { texto: SACAR.dejaraDeVerlo },
          // 7.1 (v1.2): lo que no vuelve va en negrita; «No tiene enlaces…» (n = 0) no corta nada.
          { texto: SACAR.enlaces(miembro.enlaces_vigentes), fuerte: miembro.enlaces_vigentes !== 0 },
          { texto: SACAR.fichaQueda },
          // v1.3 (O4): solo si administra, sin negrita, antes de «Para volver…».
          ...(miembro.rol === 'admin' ? [{ texto: SE_ANULAN.otra }] : []),
          { texto: SACAR.paraVolver(miembro.nombre) },
        ]}
      />
    </DialogoGrupo>
  )
}

// ---------------------------------------------------------------- 5.4 Anular una invitación

function DialogoAnular({
  grupoId,
  invitacion,
  onCancelar,
  onHecho,
  onNoEncontrado,
}: {
  grupoId: string
  invitacion: InvitacionPendiente
  onCancelar: () => void
  onHecho: (nota: { tono: 'ok' | 'rocio'; texto: string }) => void
  onNoEncontrado: () => void
}) {
  const [error, setError] = useState<ReactNode>(null)
  const { enCurso, ocupado, correr } = usePeticion()
  const anular = () =>
    correr(async () => {
      setError(null)
      try {
        await anularInvitacion(grupoId, invitacion.id)
        enCurso.current = false
        onHecho({ tono: 'ok', texto: M.anulada })
      } catch (x) {
        if (esVencida(x)) return
        const f = leerFallo(x)
        if (f.status === 409 && esTipo(f.tipo, 'invitacion-cerrada')) {
          enCurso.current = false
          return onHecho({ tono: 'rocio', texto: ANULAR.cerrada(extension(x, 'estado')) })
        }
        if (f.status === 404) {
          enCurso.current = false
          return onNoEncontrado()
        }
        setError(<MensajeError>{ANULAR.errRed}</MensajeError>)
      }
    })
  return (
    <DialogoGrupo
      titulo={ANULAR.pregunta}
      error={error}
      ocupado={ocupado}
      enCurso={enCurso}
      onCancelar={onCancelar}
      cancelar={ANULAR.no}
      confirmar={{ texto: ANULAR.boton, textoOcupado: ANULAR.ocupado, variante: 'peligroPrincipal', onClick: () => void anular() }}
    >
      <p className="font-bold">
        <LineaInvitacion i={invitacion} />
      </p>
      <p>{ANULAR.texto}</p>
    </DialogoGrupo>
  )
}

// ---------------------------------------------------------------- 7.2 y 7.3 Salir del grupo

export function SalirDelGrupo({ datos, pilas }: { datos: DatosMiembros; pilas: readonly string[] }) {
  const { grupo, rol, alEntrar, fijar } = useFamilia()
  const { carga, miembros, meSacaron } = datos
  const [abierto, setAbierto] = useState(false)
  const [enfocar, setEnfocar] = useState<{ id: string } | null>(null)

  useEffect(() => {
    if (!enfocar) return
    const destino = enfocar.id === 'borrar' ? document.querySelector<HTMLElement>('button[id^="borrar-"]') : document.getElementById(enfocar.id)
    ;(destino ?? document.getElementById('salir-t'))?.focus()
  }, [enfocar])

  if (!grupo || carga === 'cargando') return null
  const yo = miembros.find((m) => m.eres_tu) ?? null
  const sola = carga === 'lista' && miembros.length === 1 && !!yo
  const unicoAdmin = carga === 'lista' && rol === 'admin' && miembros.filter((m) => m.rol === 'admin').length <= 1

  let cuerpo: ReactNode
  if (sola) cuerpo = <p className="max-w-prose text-base">{SALIR.unicaPersona(grupo.nombre, pilas)}</p>
  else if (unicoAdmin) cuerpo = <p className="max-w-prose text-base">{SALIR.unicoAdmin(grupo.nombre)}</p>
  else
    cuerpo = (
      <>
        <p className="max-w-prose text-base">{SALIR.texto(grupo.nombre)}</p>
        <Boton id="salir-boton" variante="peligro" className="self-start" onClick={() => setAbierto(true)}>
          {SALIR.boton}
        </Boton>
      </>
    )

  return (
    <section aria-labelledby="salir-t" className="flex flex-col gap-3 border-t border-linea pt-6">
      <h2 id="salir-t" tabIndex={-1} className="text-xl font-bold outline-none">
        {SALIR.titulo}
      </h2>
      {cuerpo}
      {abierto && (
        <DialogoSalir
          grupoId={grupo.id}
          grupo={grupo.nombre}
          enlaces={yo?.enlaces_vigentes ?? null}
          pilas={pilas}
          admin={rol === 'admin'}
          onCancelar={(foco) => {
            setAbierto(false)
            setEnfocar({ id: foco })
          }}
          onHecho={async (n) => {
            setAbierto(false)
            try {
              await alEntrar()
            } catch {
              // Sin red: la regla de la ruta se aplica con lo que hay.
            }
            fijar({ aviso: { titulo: SALIR.hecho(grupo.nombre, n), tono: 'ok' } })
            navegar('/', { reemplazar: true })
          }}
          onNoEncontrado={() => {
            setAbierto(false)
            void meSacaron()
          }}
        />
      )}
    </section>
  )
}

function DialogoSalir({
  grupoId,
  grupo,
  enlaces,
  pilas,
  admin,
  onCancelar,
  onHecho,
  onNoEncontrado,
}: {
  grupoId: string
  grupo: string
  enlaces: number | null
  /** v1.3: quien sale administra (sus invitaciones sin usar se anulan). */
  admin: boolean
  pilas: readonly string[]
  /** Con el id adonde va el foco: el botón que lo abrió, o «borrar» tras un 409 `unica-persona` (7.3). */
  onCancelar: (foco: string) => void
  onHecho: (enlacesCortados: number) => void
  onNoEncontrado: () => void
}) {
  const { capa3 } = useFamilia()
  const [error, setError] = useState<ReactNode>(null)
  const [sola, setSola] = useState(false)
  const { enCurso, ocupado, correr } = usePeticion()
  const salir = () =>
    correr(async () => {
      setError(null)
      try {
        const r = await salirDelGrupo(grupoId)
        enCurso.current = false
        onHecho(r.enlaces_cortados)
      } catch (x) {
        if (esVencida(x)) return
        const f = leerFallo(x)
        if (f.status === 409 && esTipo(f.tipo, 'unica-persona')) {
          setSola(true)
          return setError(<MensajeError>{SALIR.unicaPersona(grupo, pilas)}</MensajeError>)
        }
        if (f.status === 409 && esTipo(f.tipo, 'ultimo-admin')) return setError(<MensajeError>{M.necesitaAdmin}</MensajeError>)
        if (f.status === 404) {
          enCurso.current = false
          return onNoEncontrado()
        }
        setError(<MensajeError>{SALIR.errRed}</MensajeError>)
      }
    })
  const enlacesHoy = enlaces === null ? '' : GRUPO_FAMILIAR.hoyAbren(enlaces)
  return (
    <DialogoGrupo
      titulo={SALIR.pregunta(grupo)}
      error={error}
      ocupado={ocupado}
      enCurso={enCurso}
      onCancelar={() => onCancelar(sola ? 'borrar' : 'salir-boton')}
      cancelar={SALIR.quedarme}
      confirmar={sola ? undefined : { texto: SALIR.boton, textoOcupado: SALIR.ocupado, variante: 'peligroPrincipal', onClick: () => void salir() }}
    >
      <Puntos
        puntos={[
          { texto: SALIR.dejarasDeVerlo },
          { texto: [SALIR.seCortan, enlacesHoy].filter(Boolean).join(' '), fuerte: true },
          // 5.10 (v1.2): sin persona registrada no hay ficha, y el punto no aparece.
          ...(pilas.length ? [{ texto: SALIR.fichaQueda(pilas) }] : []),
          // v1.3 (O4): solo si administro, sin negrita, antes de «Para volver…».
          ...(admin ? [{ texto: SE_ANULAN.propia }] : []),
          { texto: SALIR.paraVolver },
        ]}
      />
      {/* 7.2 (v1.3): para todos los roles, el correo como texto, sin enlace. */}
      <p className="text-base text-tenue break-words">{SALIR.pideloA(capa3 === true)}</p>
    </DialogoGrupo>
  )
}

/** 3.2: la nota de «cuéntale» con el teléfono, que también usa Invitar. */
export const IconoTelefono = () => <Phone aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
