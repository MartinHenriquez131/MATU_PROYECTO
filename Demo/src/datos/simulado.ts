// Adaptador simulado: las mismas reglas del backend, en memoria y sin red. Es el que usa
// build:single y el que toma la demo si el backend no responde.
import { ErrorApi, type ApiMatu } from './api'
import type { CuentaCreadaRespuesta, GrupoRespuesta, PersonaCreada, PersonaListada } from './contrato'
import { AVISO_CUIDADOR } from '../demo/datos'

/** Huella publicada del aviso v1.0 (política de privacidad v0.9, sección 5). */
const HUELLA_AVISO = '9b33205fd93e18b3eaac569071b794d21071a414ccc0d8bb5b89f9c96af3dfc9'

const espera = (ms = 280) => new Promise((r) => setTimeout(r, ms))
const id = () => crypto.randomUUID()

export function adaptadorSimulado(): ApiMatu {
  const cuentas = new Map<string, { nombre: string; contrasena: string }>()
  const grupos: GrupoRespuesta[] = []
  const personas: PersonaListada[] = []
  let sesion: string | null = null

  const exigirSesion = () => {
    if (!sesion) throw new ErrorApi('http', 'Tu sesión terminó. Entra de nuevo.', 401)
  }

  return {
    modo: 'simulado',
    async crearCuenta(nombre, email, contrasena): Promise<CuentaCreadaRespuesta> {
      await espera()
      const e = email.trim().toLowerCase()
      if (contrasena.length < 10) throw new ErrorApi('http', 'La contraseña necesita al menos 10 caracteres.', 422, { contrasena: 'Al menos 10 caracteres.' })
      if (cuentas.has(e)) throw new ErrorApi('http', 'Ese email ya tiene una cuenta. Entra con tu contraseña.', 409, { email: 'Ese email ya tiene una cuenta.' }, 'email-registrado')
      cuentas.set(e, { nombre, contrasena })
      return { id: id(), nombre, email: e }
    },
    async iniciarSesion(email, contrasena) {
      await espera()
      const c = cuentas.get(email.trim().toLowerCase())
      if (!c || c.contrasena !== contrasena) throw new ErrorApi('http', 'El email o la contraseña no coinciden. Revísalos y vuelve a intentar.', 401)
      sesion = email
    },
    async listarGrupos() {
      await espera(120)
      exigirSesion()
      return [...grupos]
    },
    async crearGrupo(nombre) {
      await espera(160)
      exigirSesion()
      const g = { id: id(), nombre, rol: 'admin' }
      grupos.push(g)
      return g
    },
    elegirGrupo() {},
    async darDeAlta(d): Promise<PersonaCreada> {
      await espera()
      exigirSesion()
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
      personas.push({ ...persona })
      return persona
    },
    async listarPersonas() {
      await espera(120)
      exigirSesion()
      return [...personas]
    },
    cerrar() {
      sesion = null
    },
  }
}
