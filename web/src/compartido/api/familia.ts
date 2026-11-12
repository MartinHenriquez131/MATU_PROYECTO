// Rutas de la app de la familia (contrato docs/api/openapi.json, tipos en familia.openapi.ts,
// regenerados con `npm run contrato:familia`). El grupo viaja en `X-Grupo-Id` y el token en
// `Authorization`, los dos desde la memoria de sesion.ts. Nunca se registra un cuerpo.
import { isAxiosError } from 'axios'
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'
import type { SeccionApi } from '../secciones'

type S = components['schemas']

/** `POST /v1/usuarios`, con el celular (`telefono`, decisión 65). */
export type SolicitudRegistro = S['SolicitudRegistro']
export type CuentaCreada = S['CuentaCreadaRespuesta']
/** `GET /v1/grupos`, con `puede_ver_plan` para el pagador (D3). */
export type Grupo = S['GrupoRespuesta']
export type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'
export type PersonaCompleta = S['PersonaVistaCompleta']
export type PersonaListada = S['PersonaVistaCompleta'] | S['PersonaVistaPagador'] | S['PersonaVistaObservador']
/** `etiqueta` y `region` tienen valor por omisión en el contrato («Casa», «Metropolitana»): no se piden en este sprint. */
type DireccionNueva = Omit<S['DireccionNueva'], 'etiqueta' | 'region'> & Partial<Pick<S['DireccionNueva'], 'etiqueta' | 'region'>>
export type SolicitudPersona = Omit<S['SolicitudPersona'], 'direccion'> & { direccion?: DireccionNueva | null }
export type PersonaCreada = S['PersonaCreada']
export type Calidad = S['CalidadOtorgante']
/** `GET …/plan/ficha`, con `secciones` (MATU-50): solo las secciones agregadas. */
export type Ficha = S['FichaVista']
export type EstadoCampo = S['EstadoCampoVista']
export type CampoGuardado = S['CampoGuardadoVista']
export type CampoApi = keyof S['CamposVista']

/** Un rol que no se reconoce se trata como `observador` (especificación 2.2). */
export function rolDe(g: Grupo | null | undefined): Rol {
  const r = g?.rol
  return r === 'admin' || r === 'cuidador' || r === 'pagador' ? r : 'observador'
}

export const nombrePilaDe = (p: PersonaListada) => ('nombre_pila' in p && p.nombre_pila ? p.nombre_pila : p.nombre)

export async function crearCuenta(cuerpo: SolicitudRegistro): Promise<CuentaCreada> {
  return (await apiFamilia.post<CuentaCreada>('/v1/usuarios', cuerpo)).data
}

export async function listarGrupos(): Promise<Grupo[]> {
  return (await apiFamilia.get<Grupo[]>('/v1/grupos')).data
}

export async function crearGrupo(nombre: string): Promise<Grupo> {
  const cuerpo: S['SolicitudGrupo'] = { nombre }
  return (await apiFamilia.post<Grupo>('/v1/grupos', cuerpo)).data
}

export async function listarPersonas(grupoId: string): Promise<PersonaListada[]> {
  const r = await apiFamilia.get<PersonaListada[]>(`/v1/grupos/${encodeURIComponent(grupoId)}/personas-cuidadas`, {
    headers: { 'X-Grupo-Id': grupoId },
  })
  return r.data
}

export async function registrarPersona(grupoId: string, cuerpo: SolicitudPersona): Promise<PersonaCreada> {
  const r = await apiFamilia.post<PersonaCreada>(`/v1/grupos/${encodeURIComponent(grupoId)}/personas-cuidadas`, cuerpo, {
    headers: { 'X-Grupo-Id': grupoId },
  })
  return r.data
}

export async function leerFicha(personaId: string): Promise<Ficha> {
  return (await apiFamilia.get<Ficha>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/ficha`)).data
}

/**
 * `PUT …/plan/ficha/{campo}`: siempre condicional. Con `etag` manda `If-Match`; sin él (campo nunca
 * escrito), `If-None-Match: *`. Devuelve el campo guardado con su `ETag`.
 */
export async function guardarCampo(personaId: string, campo: CampoApi, texto: string, etag: string | null): Promise<CampoGuardado> {
  const cuerpo: S['SolicitudCampo'] = { texto }
  const r = await apiFamilia.put<CampoGuardado>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/ficha/${campo}`, cuerpo, {
    headers: etag ? { 'If-Match': etag } : { 'If-None-Match': '*' },
  })
  const cabecera = r.headers?.etag
  return { ...r.data, etag: typeof cabecera === 'string' && cabecera ? cabecera : r.data.etag }
}

/** El contenido de un 412 `version-desactualizada`: lo vigente y su `ETag`. */
export interface Conflicto {
  actual: EstadoCampo
  /** `ETag` de la respuesta 412, o `actual.etag`; `null` si el campo nunca se escribió. */
  etag: string | null
}

export function leerConflicto(error: unknown): Conflicto | null {
  if (!isAxiosError(error) || error.response?.status !== 412) return null
  const cuerpo = error.response.data as { actual?: EstadoCampo } | undefined
  const actual: EstadoCampo = cuerpo?.actual ?? { texto: null, etag: null, actualizado_por: null, actualizado_en: null }
  const cabecera = error.response.headers?.etag
  return { actual, etag: typeof cabecera === 'string' && cabecera ? cabecera : actual.etag }
}

// ---------------------------------------------------------------- MATU-57: recuperar y la cuenta

export type Cuenta = S['CuentaVista']
export type CanalCelular = NonNullable<S['SolicitudVerificarCelular']['canal']>

/** `POST /v1/recuperacion/codigo`: siempre 202, exista o no la cuenta (decisión 84). */
export async function pedirCodigoRecuperacion(email: string, alCorreo = false): Promise<void> {
  const cuerpo: S['SolicitudCodigoRecuperacion'] = alCorreo ? { email, canal: 'correo' } : { email }
  await apiFamilia.post('/v1/recuperacion/codigo', cuerpo)
}

/** `POST /v1/recuperacion/contrasena`: 204; no emite tokens, se vuelve a entrar (decisión 86). */
export async function cambiarContrasenaConCodigo(email: string, codigo: string, contrasenaNueva: string): Promise<void> {
  const cuerpo: S['SolicitudCambioContrasena'] = { email, codigo, contrasena_nueva: contrasenaNueva }
  await apiFamilia.post('/v1/recuperacion/contrasena', cuerpo)
}

/** `GET /v1/cuenta`: el celular llega enmascarado, nunca completo. */
export async function leerCuenta(): Promise<Cuenta> {
  return (await apiFamilia.get<Cuenta>('/v1/cuenta')).data
}

/** `POST /v1/cuenta/celular/codigo`: 202, 409 o 429. */
export async function pedirCodigoCelular(): Promise<void> {
  await apiFamilia.post('/v1/cuenta/celular/codigo')
}

/** `POST /v1/cuenta/celular/verificar`: 204, 422 `codigo-invalido` o 429. */
export async function confirmarCelular(codigo: string, canal: CanalCelular): Promise<void> {
  const cuerpo: S['SolicitudVerificarCelular'] = { codigo, canal }
  await apiFamilia.post('/v1/cuenta/celular/verificar', cuerpo)
}

/** `GET …/plan/aperturas` (MATU-45): lo que hicieron los relevos, del más reciente al más antiguo. */
export type Apertura = S['AperturaVista']
export type TipoApertura = S['TipoApertura']
export type ListaAperturas = S['ListaAperturasVista']

export async function listarAperturas(personaId: string, cursor: string | null = null, limite = 20): Promise<ListaAperturas> {
  const params: { limite: number; cursor?: string } = { limite }
  if (cursor) params.cursor = cursor
  return (await apiFamilia.get<ListaAperturas>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/aperturas`, { params })).data
}

// ---------------------------------------------------------------- secciones complementarias (MATU-50)

export type EstadoSeccion = S['EstadoSeccionVista']
export type SeccionGuardada = S['SeccionGuardadaVista']
export type SeccionesFicha = Partial<Record<SeccionApi, EstadoSeccion>>

export const seccionesDe = (f: Ficha | null | undefined): SeccionesFicha => (f?.secciones ?? {}) as SeccionesFicha

const rutaSeccion = (personaId: string, seccion: SeccionApi) => `/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/secciones/${seccion}`

/**
 * `PUT …/plan/secciones/{seccion}`: siempre condicional, como un campo base. Con `etag`, `If-Match`;
 * sin él (la sección no está), `If-None-Match: *`. 201 si se agregó, 200 si se editó.
 */
export async function guardarSeccion(personaId: string, seccion: SeccionApi, texto: string, etag: string | null): Promise<SeccionGuardada> {
  const cuerpo: S['SolicitudSeccion'] = { texto }
  const r = await apiFamilia.put<SeccionGuardada>(rutaSeccion(personaId, seccion), cuerpo, {
    headers: etag ? { 'If-Match': etag } : { 'If-None-Match': '*' },
  })
  const cabecera = r.headers?.etag
  return { ...r.data, etag: typeof cabecera === 'string' && cabecera ? cabecera : r.data.etag }
}

/**
 * `DELETE …/plan/secciones/{seccion}` con `If-Match`: borra el texto. 204 sin cuerpo. Si otra
 * persona la cambió, 412 con lo actual; si ya no está, 412 con `actual: null` (contrato).
 */
export async function quitarSeccion(personaId: string, seccion: SeccionApi, etag: string): Promise<void> {
  await apiFamilia.delete(rutaSeccion(personaId, seccion), { headers: { 'If-Match': etag } })
}

/** El 412 de una sección distingue «la cambió otra persona» (`actual`) de «ya no está» (`null`). */
export function leerConflictoSeccion(error: unknown): { actual: EstadoSeccion | null; etag: string | null } | null {
  if (!isAxiosError(error) || error.response?.status !== 412) return null
  const cuerpo = error.response.data as { actual?: EstadoSeccion | null } | undefined
  const actual = cuerpo?.actual && typeof cuerpo.actual.texto === 'string' ? cuerpo.actual : null
  const cabecera = error.response.headers?.etag
  return { actual, etag: typeof cabecera === 'string' && cabecera ? cabecera : (actual?.etag ?? null) }
}

// ---------------------------------------------------------------- accesos de relevo (MATU-48)

/** `POST …/plan/accesos-relevo`. Sin `campos` (deprecado): los tres campos base van siempre. */
export type SolicitudAcceso = Omit<S['SolicitudAccesoVista'], 'campos'>
/** El 201: la `url` y el `pin` se muestran una sola vez y viven solo en la memoria de la pantalla. */
export type AccesoCreado = S['AccesoCreadoVista']
export type AccesoResumen = S['AccesoResumenVista']
export type EstadoAcceso = S['EstadoAcceso']
export type MotivoAcceso = S['MotivoAcceso']
export type ListaAccesos = S['ListaAccesosVista']

const rutaAccesos = (personaId: string) => `/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/accesos-relevo`

export async function crearAcceso(personaId: string, cuerpo: SolicitudAcceso): Promise<AccesoCreado> {
  return (await apiFamilia.post<AccesoCreado>(rutaAccesos(personaId), cuerpo)).data
}

/** `GET …/plan/accesos-relevo`, del más nuevo al más antiguo. `estado` filtra en el servidor. */
export async function listarAccesos(
  personaId: string,
  { estado = null, cursor = null, limite = 20 }: { estado?: EstadoAcceso | null; cursor?: string | null; limite?: number } = {},
): Promise<ListaAccesos> {
  const params: { limite: number; estado?: EstadoAcceso; cursor?: string } = { limite }
  if (estado) params.estado = estado
  if (cursor) params.cursor = cursor
  return (await apiFamilia.get<ListaAccesos>(rutaAccesos(personaId), { params })).data
}

/** `DELETE /v1/accesos-relevo/{id}`: 204, idempotente (ya cortado o vencido también es 204). */
export async function cortarAcceso(accesoId: string): Promise<void> {
  await apiFamilia.delete(`/v1/accesos-relevo/${encodeURIComponent(accesoId)}`)
}

// ---------------------------------------------------------------- MATU-44: retirar y volver a autorizar

/** `plan_cuidado` es la ficha y `consumo` los insumos (decisión 123). */
export type Finalidad = S['AutorizacionVista']['finalidad']
export type EstadoAutorizacion = S['EstadoVista']
/**
 * `GET …/consentimientos` (decisión 127): `AutorizacionVista` para admin y cuidador y
 * `AutorizacionVistaResumen` (sin `calidad_otorgante`) para pagador y observador. La pantalla usa
 * solo lo que tienen en común, así que nunca muestra la calidad. MATU-42 (decisión 311):
 * `autorizo_alguien_que_ya_no_esta` llega solo a admin y cuidador; para los otros roles no viene.
 */
export type AutorizacionVista = S['AutorizacionVistaResumen'] & Partial<Pick<S['AutorizacionVista'], 'autorizo_alguien_que_ya_no_esta'>>
export interface RetiroAutorizacion {
  autorizacion: AutorizacionVista
  enlaces_cortados: number
}
export type SolicitudAutorizacion = S['SolicitudAutorizacionEntrada']

/** Lo que la pantalla usa: la calidad de quien autorizó no se guarda ni se muestra (P2, sección 8). */
const sinCalidad = (a: AutorizacionVista): AutorizacionVista => ({
  finalidad: a.finalidad,
  estado: a.estado,
  id: a.id,
  otorgado_en: a.otorgado_en,
  revision_vence_en: a.revision_vence_en,
  revocado_en: a.revocado_en,
  borrado_en: a.borrado_en,
  borrada: a.borrada,
  se_puede_otorgar: a.se_puede_otorgar,
  ...(a.autorizo_alguien_que_ya_no_esta === true ? { autorizo_alguien_que_ya_no_esta: true } : {}),
})

const rutaConsentimientos = (personaId: string) => `/v1/personas-cuidadas/${encodeURIComponent(personaId)}/consentimientos`

/**
 * `plan_cuidado` y `consumo`, y `despacho` con la capa 3 encendida (MATU-61, decisión 192 y C2) o, con
 * la capa apagada, si la persona tiene un registro de ella (decisión 251). Pueden ser 2 o 3 ítems.
 */
export async function leerAutorizaciones(personaId: string): Promise<AutorizacionVista[]> {
  const r = await apiFamilia.get<S['AutorizacionesPersona'] | S['AutorizacionesPersonaResumen']>(rutaConsentimientos(personaId))
  return r.data.autorizaciones.map(sinCalidad)
}

/** `POST …/consentimientos/{finalidad}/retiro`, sin cuerpo: 200, 409 `ya-retirada` o 404. */
export async function retirarAutorizacion(personaId: string, finalidad: Finalidad): Promise<RetiroAutorizacion> {
  const r = await apiFamilia.post<S['RetiroAutorizacion']>(`${rutaConsentimientos(personaId)}/${finalidad}/retiro`)
  return { autorizacion: sinCalidad(r.data.autorizacion), enlaces_cortados: r.data.enlaces_cortados }
}

/** `POST …/consentimientos` (decisión 128; `despacho` con su `huella_declaracion`, decisión 192): 201, 409 `autorizacion-vigente` o 422. */
export async function autorizar(personaId: string, cuerpo: SolicitudAutorizacion): Promise<void> {
  await apiFamilia.post(rutaConsentimientos(personaId), cuerpo)
}

// ---------------------------------------------------------------- MATU-72: borrar los datos de la persona

/** El 200 del borrado (decisión 152): sin el nombre ni nada de la persona, solo los contadores. */
export type BorradoPersona = S['BorradoPersona']

/**
 * `POST /v1/personas-cuidadas/{persona_id}/borrado`, sin cuerpo, con `X-Grupo-Id` (decisión 149):
 * 200, 404 (otro rol, otro grupo o ya no está) o 409 `ya-borrada` (decisión 151).
 */
export async function borrarPersona(personaId: string): Promise<BorradoPersona> {
  return (await apiFamilia.post<BorradoPersona>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/borrado`)).data
}

// ---------------------------------------------------------------- MATU-42: invitar y quiénes forman el grupo

/** `GET …/miembros` (decisión 302): nunca el correo, el celular ni el id de la cuenta. */
export type Miembro = S['MiembroVista']
/** El 201 de crear: la `url` y el `codigo` salen una sola vez y viven solo en la memoria de la pantalla. */
export type InvitacionCreada = S['InvitacionCreada']
export type InvitacionPendiente = S['InvitacionVista']
export type PresentacionInvitacion = S['PresentacionInvitacion']
/** Sin `intentos_restantes`: van solo en el 422 `codigo-incorrecto` (decisión 325). */
export type VerificacionInvitacion = S['VerificacionInvitacion']
export type Union = S['Union']
export type CambioMiembro = S['SolicitudCambioMiembro']

const rutaGrupo = (grupoId: string) => `/v1/grupos/${encodeURIComponent(grupoId)}`
const conGrupo = (grupoId: string) => ({ headers: { 'X-Grupo-Id': grupoId } })

/** `POST …/invitaciones` (decisiones 294 a 297): solo el rol. Sin `Idempotency-Key` (decisión 296). */
export async function crearInvitacion(grupoId: string, rol: Rol): Promise<InvitacionCreada> {
  const cuerpo: S['SolicitudInvitacion'] = { rol }
  return (await apiFamilia.post<InvitacionCreada>(`${rutaGrupo(grupoId)}/invitaciones`, cuerpo, conGrupo(grupoId))).data
}

/** `GET …/invitaciones`: las pendientes y bloqueadas, solo para quien administra (C10). */
export async function listarInvitaciones(grupoId: string): Promise<InvitacionPendiente[]> {
  const lista = (await apiFamilia.get<S['ListaInvitaciones']>(`${rutaGrupo(grupoId)}/invitaciones`, conGrupo(grupoId))).data?.invitaciones
  if (!Array.isArray(lista)) throw new Error('Respuesta sin invitaciones')
  return lista
}

/** `DELETE …/invitaciones/{id}`: 204, o 409 `invitacion-cerrada` con `estado` (decisión 308). */
export async function anularInvitacion(grupoId: string, invitacionId: string): Promise<void> {
  await apiFamilia.delete(`${rutaGrupo(grupoId)}/invitaciones/${encodeURIComponent(invitacionId)}`, conGrupo(grupoId))
}

export async function listarMiembros(grupoId: string): Promise<Miembro[]> {
  const lista = (await apiFamilia.get<S['ListaMiembros']>(`${rutaGrupo(grupoId)}/miembros`, conGrupo(grupoId))).data?.miembros
  // Una respuesta sin la lista es un error al traerla (5.9), no un grupo vacío.
  if (!Array.isArray(lista)) throw new Error('Respuesta sin miembros')
  return lista
}

/**
 * `PATCH …/miembros/{id}` con `If-Match` (decisión 303): el rol, el permiso del pagador o los dos.
 * 412 trae la membresía vigente en `actual` (`leerConflictoMiembro`). El `etag` nuevo viaja en el
 * cuerpo y en la cabecera; manda la cabecera.
 */
export async function cambiarMiembro(grupoId: string, miembro: Pick<Miembro, 'id' | 'etag'>, cambio: CambioMiembro): Promise<S['ResultadoCambioMiembro']> {
  const r = await apiFamilia.patch<S['ResultadoCambioMiembro']>(`${rutaGrupo(grupoId)}/miembros/${encodeURIComponent(miembro.id)}`, cambio, {
    headers: { 'X-Grupo-Id': grupoId, 'If-Match': miembro.etag },
  })
  const cabecera = r.headers?.etag
  return { ...r.data, miembro: { ...r.data.miembro, etag: typeof cabecera === 'string' && cabecera ? cabecera : r.data.miembro.etag } }
}

/** El 412 de `PATCH …/miembros/{id}`: la membresía como quedó, o `null` si no viene. */
export function leerConflictoMiembro(error: unknown): Miembro | null {
  if (!isAxiosError(error) || error.response?.status !== 412) return null
  const actual = (error.response.data as { actual?: Miembro | null } | undefined)?.actual
  return actual && typeof actual.id === 'string' && typeof actual.rol === 'string' ? actual : null
}

/** `DELETE …/miembros/{id}`: 200 con `enlaces_cortados` (decisión 305). Una retirada es 404. */
export async function sacarMiembro(grupoId: string, membresiaId: string): Promise<S['ResultadoSalida']> {
  return (await apiFamilia.delete<S['ResultadoSalida']>(`${rutaGrupo(grupoId)}/miembros/${encodeURIComponent(membresiaId)}`, conGrupo(grupoId))).data
}

/** `POST …/salida`: 200 con `enlaces_cortados`; 409 `ultimo-admin` o `unica-persona` (decisión 304). */
export async function salirDelGrupo(grupoId: string): Promise<S['ResultadoSalida']> {
  return (await apiFamilia.post<S['ResultadoSalida']>(`${rutaGrupo(grupoId)}/salida`, null, conGrupo(grupoId))).data
}

/**
 * La persona invitada (decisión 299). El token y el código van solo en el cuerpo, nunca en la URL ni
 * en una cabecera. La presentación y la verificación van sin sesión y la aceptación con ella; ninguna
 * lleva `X-Grupo-Id` (sesion.ts).
 */
export async function presentarInvitacion(token: string): Promise<PresentacionInvitacion> {
  const cuerpo: S['SolicitudPresentacionInvitacion'] = { token }
  return (await apiFamilia.post<PresentacionInvitacion>('/v1/invitaciones/presentacion', cuerpo)).data
}

export async function verificarInvitacion(token: string, codigo: string): Promise<VerificacionInvitacion> {
  const cuerpo: S['SolicitudCanjeInvitacion'] = { token, codigo }
  return (await apiFamilia.post<VerificacionInvitacion>('/v1/invitaciones/verificacion', cuerpo)).data
}

export async function aceptarInvitacion(token: string, codigo: string): Promise<Union> {
  const cuerpo: S['SolicitudCanjeInvitacion'] = { token, codigo }
  return (await apiFamilia.post<Union>('/v1/invitaciones/aceptacion', cuerpo)).data
}

// ---------------------------------------------------------------- MATU-55: dónde entraste y los avisos

/** `GET /v1/dispositivos`: los propios, primero el actual y después por último uso. Nunca el endpoint de push. */
export type Dispositivo = S['DispositivoVista']
/** `telefono`, `computador` u `otro`: el sustantivo de la pantalla (E1). */
export type ClaseDispositivo = S['DispositivoVista']['clase']
/** `GET /v1/yo/ingresos`: hasta 20 eventos de los últimos 90 días, y si hay más. */
export type UltimosIngresos = S['UltimosIngresosVista']
export type EventoCuenta = S['EventoCuentaVista']
export type TipoEventoCuenta = S['EventoCuentaVista']['tipo']
/** `GET /v1/dispositivos/actual/push`: la clave pública (o `null`), si este dispositivo está inscrito y si el envío es simulado. */
export type PushActual = S['PushActualVista']
/** `GET` y `PUT /v1/yo/avisos`: los dos canales, para todos los grupos de la persona. */
export type PreferenciaAvisos = S['PreferenciaAvisosVista']

export async function listarDispositivos(): Promise<Dispositivo[]> {
  return (await apiFamilia.get<S['ListaDispositivos']>('/v1/dispositivos')).data.items
}

/** `DELETE /v1/dispositivos/{id}`: 204 (también si ya estaba cerrado) o 404 (ya no está en la lista). */
export async function cerrarDispositivo(id: string): Promise<void> {
  await apiFamilia.delete(`/v1/dispositivos/${encodeURIComponent(id)}`)
}

export async function leerIngresos(): Promise<UltimosIngresos> {
  return (await apiFamilia.get<UltimosIngresos>('/v1/yo/ingresos')).data
}

export async function leerPushActual(): Promise<PushActual> {
  return (await apiFamilia.get<PushActual>('/v1/dispositivos/actual/push')).data
}

/** `PUT /v1/dispositivos/actual/push`: solo el endpoint de la suscripción. 204. */
export async function guardarPushActual(endpoint: string): Promise<void> {
  const cuerpo: S['SolicitudPush'] = { push_token: endpoint }
  await apiFamilia.put('/v1/dispositivos/actual/push', cuerpo)
}

/** `DELETE /v1/dispositivos/actual/push`: 204, idempotente. */
export async function borrarPushActual(): Promise<void> {
  await apiFamilia.delete('/v1/dispositivos/actual/push')
}

export async function leerAvisos(): Promise<PreferenciaAvisos> {
  return (await apiFamilia.get<PreferenciaAvisos>('/v1/yo/avisos')).data
}

/** `PUT /v1/yo/avisos`, con los dos canales. Devuelve lo mismo que el `GET`. Sin versión ni `If-Match`. */
export async function guardarAvisos(preferencia: PreferenciaAvisos): Promise<PreferenciaAvisos> {
  return (await apiFamilia.put<PreferenciaAvisos>('/v1/yo/avisos', preferencia)).data
}
