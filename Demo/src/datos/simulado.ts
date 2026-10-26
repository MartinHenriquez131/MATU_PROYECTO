// Adaptador simulado: las mismas reglas del backend, en memoria y sin red. Es el que usa
// build:single y el que toma la demo si el backend no responde.
import { ErrorApi, type ApiMatu } from './api'
import type { CuentaCreadaRespuesta, GrupoRespuesta, PersonaCreada, PersonaListada } from './contrato'
import { AVISO_CUIDADOR } from '../demo/datos'

/** Huella publicada del aviso v1.0 (política de privacidad v0.9, sección 5). */
const HUELLA_AVISO = '9b33205fd93e18b3eaac569071b794d21071a414ccc0d8bb5b89f9c96af3dfc9' // pragma: allowlist secret

/**
 * Cuenta sintética que ya usa MATU, para mostrar "Entrar" sin backend. Antes la escena
 * "Entrar" en modo simulado quedaba con los campos vacíos y no había con qué entrar.
 */
export const CUENTA_EJEMPLO = { nombre: 'Carmen', email: 'carmen@correo.ejemplo', clave: 'maria-los-aromos' }

const espera = (ms = 280) => new Promise((r) => setTimeout(r, ms))
const id = () => crypto.randomUUID()

function personaDelEjemplo(): PersonaListada {
  return {
    id: id(),
    nombre: 'María Soto',
    nombre_pila: 'María',
    nivel_apoyo: 'apoyo_parcial',
    direccion: { etiqueta: 'Casa', calle: 'Los Aromos', numero: '123', depto: null, comuna: 'La Reina', region: 'Metropolitana', referencia: null },
    consentimiento: {
      id: id(),
      calidad_otorgante: 'cuidador_de_hecho',
      finalidad: 'plan_cuidado',
      version_politica: '0.9',
      otorgado_en: '2026-10-10T14:20:00-03:00',
      revision_vence_en: '2027-10-10T14:20:00-03:00',
    },
  }
}

export function adaptadorSimulado(): ApiMatu {
  const cuentas = new Map<string, { nombre: string; contrasena: string }>()
  // Los grupos son de cada cuenta y las personas de cada grupo, como con RLS en el backend.
  const gruposDe = new Map<string, GrupoRespuesta[]>()
  const personasDe = new Map<string, PersonaListada[]>()
  let sesion: string | null = null
  let grupoActual: string | null = null

  {
    const e = CUENTA_EJEMPLO.email
    cuentas.set(e, { nombre: CUENTA_EJEMPLO.nombre, contrasena: CUENTA_EJEMPLO.clave })
    const g = { id: id(), nombre: 'Cuidado de María', rol: 'admin' }
    gruposDe.set(e, [g])
    personasDe.set(g.id, [personaDelEjemplo()])
  }

  const exigirSesion = (): string => {
    if (!sesion) throw new ErrorApi('http', 'No hay una sesión abierta. Crea tu cuenta o entra primero.', 401, {}, 'sin-sesion')
    return sesion
  }
  const exigirGrupo = (email: string): string => {
    const propio = (gruposDe.get(email) ?? []).some((g) => g.id === grupoActual)
    // Un grupo ajeno responde 404, nunca 403 (CLAUDE.md, agente 2, punto 4).
    if (!grupoActual || !propio) throw new ErrorApi('http', 'No encontramos ese grupo para tu cuenta. Entra de nuevo.', 404)
    return grupoActual
  }

  return {
    modo: 'simulado',
    async crearCuenta(nombre, email, contrasena): Promise<CuentaCreadaRespuesta> {
      await espera()
      const e = email.trim().toLowerCase()
      if (contrasena.length < 10) throw new ErrorApi('http', 'La contraseña necesita al menos 10 caracteres.', 422, { contrasena: 'Al menos 10 caracteres.' }) // pragma: allowlist secret
      if (cuentas.has(e)) throw new ErrorApi('http', 'Ese email ya tiene una cuenta. Entra con tu contraseña.', 409, { email: 'Ese email ya tiene una cuenta.' }, 'email-registrado')
      cuentas.set(e, { nombre, contrasena })
      return { id: id(), nombre, email: e }
    },
    async iniciarSesion(email, contrasena) {
      await espera()
      const e = email.trim().toLowerCase()
      const c = cuentas.get(e)
      if (!c || c.contrasena !== contrasena) throw new ErrorApi('http', 'El email o la contraseña no coinciden. Revísalos y vuelve a intentar.', 401)
      sesion = e
      grupoActual = null
    },
    async listarGrupos() {
      await espera(120)
      return [...(gruposDe.get(exigirSesion()) ?? [])]
    },
    async crearGrupo(nombre) {
      await espera(160)
      const e = exigirSesion()
      const g = { id: id(), nombre, rol: 'admin' }
      gruposDe.set(e, [...(gruposDe.get(e) ?? []), g])
      return g
    },
    elegirGrupo(gid) {
      grupoActual = gid
    },
    async darDeAlta(d): Promise<PersonaCreada> {
      await espera()
      const gid = exigirGrupo(exigirSesion())
      if (d.calidad_otorgante === 'representante_legal' && !d.referencia_documento?.trim()) {
        throw new ErrorApi('http', 'Escribe la referencia del documento que te nombra representante.', 422, { referencia_documento: 'Falta la referencia.' })
      }
      if (d.calidad_otorgante === 'cuidador_de_hecho' && !d.aviso) {
        throw new ErrorApi('http', 'Vuelve a mostrar el aviso y acéptalo para seguir.', 422, { aviso: 'Falta el aviso.' })
      }
      const ahora = new Date()
      const revision = d.calidad_otorgante === 'cuidador_de_hecho' ? new Date(ahora.getTime() + 365 * 86_400_000).toISOString() : null
      const direccion = d.direccion
        ? {
            etiqueta: d.direccion.etiqueta ?? 'Casa',
            calle: d.direccion.calle,
            numero: d.direccion.numero,
            depto: d.direccion.depto ?? null,
            comuna: d.direccion.comuna,
            region: d.direccion.region ?? 'Metropolitana',
            referencia: d.direccion.referencia ?? null,
          }
        : null
      const persona: PersonaCreada = {
        id: id(),
        nombre: d.nombre,
        nombre_pila: d.nombre_pila,
        nivel_apoyo: d.nivel_apoyo,
        direccion,
        consentimiento: {
          id: id(),
          calidad_otorgante: d.calidad_otorgante,
          finalidad: 'plan_cuidado',
          version_politica: '0.9',
          otorgado_en: ahora.toISOString(),
          revision_vence_en: revision,
        },
        aviso:
          d.calidad_otorgante === 'cuidador_de_hecho'
            ? { id: AVISO_CUIDADOR.id, version: AVISO_CUIDADOR.version, titulo: AVISO_CUIDADOR.titulo, parrafos: AVISO_CUIDADOR.parrafos, sha256: HUELLA_AVISO }
            : null,
      }
      const { aviso: _aviso, ...listada } = persona
      personasDe.set(gid, [...(personasDe.get(gid) ?? []), listada])
      return persona
    },
    async listarPersonas() {
      await espera(120)
      return [...(personasDe.get(exigirGrupo(exigirSesion())) ?? [])]
    },
    cerrar() {
      sesion = null
      grupoActual = null
    },
  }
}
