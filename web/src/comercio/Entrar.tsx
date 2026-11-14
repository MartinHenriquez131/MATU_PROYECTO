// Entrar como comercio (especificación MATU-63, sección 4). La lógica de `Entrar` de la familia
// (MATU-39 3.3): los mismos campos, el 429 con `aria-disabled` y el foco que se queda en el botón.
// Sin `MarcoAlta`: su panel es la bienvenida de la familia. El token queda solo en memoria.
import { useEffect, useState, type FormEvent } from 'react'
import { esperaDe, leerFallo } from '../compartido/api/cliente'
import { entrar } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { BotonMostrar } from '../familia/Alta'
import { navegar } from '../familia/ruteo'
import { Acciones, CampoTexto, MensajeError, Nota, Titulo } from '../familia/ui'
import { useComercio } from './estado'
import { MarcoEntrar } from './Marco'
import { ENTRAR_COMERCIO as T } from './textos'

type Falla = { tipo: 'faltan' | 'credenciales' | 'no-disponible' | 'red' } | { tipo: 'espera'; minutos: number; hasta: number }

export function EntrarComercio() {
  const { avisoEntrar, destino, contacto, alEntrar, fijar } = useComercio()
  const [email, setEmail] = useState('')
  const [clave, setClave] = useState('')
  const [ver, setVer] = useState(false)
  const [falla, setFalla] = useState<Falla | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [esperando, setEsperando] = useState(false)

  useEffect(() => {
    if (falla?.tipo !== 'espera') return
    setEsperando(true)
    const t = window.setTimeout(() => setEsperando(false), Math.max(0, falla.hasta - Date.now()))
    return () => window.clearTimeout(t)
  }, [falla])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado || esperando) return
    if (!email.trim() || !clave) return setFalla({ tipo: 'faltan' })
    setFalla(null)
    setOcupado(true)
    try {
      // O1: una cuenta de familia ve el aviso y se queda aquí; nunca se dice si el correo existe.
      if ((await entrar(email.trim(), clave)) !== 'comercio') {
        setClave('')
        return fijar({ avisoEntrar: 'familia' })
      }
      if ((await alEntrar()) === 'inactiva') {
        setClave('')
        return fijar({ avisoEntrar: 'inactiva' })
      }
      const ir = destino ?? '/comercio'
      fijar({ destino: null, avisoEntrar: null })
      navegar(ir, { reemplazar: true })
    } catch (x) {
      const f = leerFallo(x)
      const espera = esperaDe(f)
      if (f.status === 401) setFalla({ tipo: 'credenciales' })
      else if (f.status === 404) fijar({ avisoEntrar: 'familia' })
      else if (espera) setFalla({ tipo: 'espera', minutos: espera.minutos, hasta: Date.now() + espera.segundos * 1000 })
      else if (f.status === 503) setFalla({ tipo: 'no-disponible' })
      else setFalla({ tipo: 'red' })
    } finally {
      setOcupado(false)
    }
  }

  return (
    <MarcoEntrar>
      <div className="flex flex-col gap-2">
        <Titulo className="text-3xl">{T.titulo}</Titulo>
        <p className="max-w-prose text-lg text-tenue">{T.bajada}</p>
      </div>
      {avisoEntrar === 'familia' && (
        <Nota tono="atenta" rol="status" titulo={T.familiaTitulo}>
          {T.familiaTexto}
        </Nota>
      )}
      {avisoEntrar === 'inactiva' && (
        <Nota tono="atenta" rol="status" titulo={T.inactivaTitulo}>
          {T.inactivaTexto(contacto)}
        </Nota>
      )}
      {(avisoEntrar === 'vencida' || avisoEntrar === 'salio') && (
        <Nota tono="rocio" rol="status">
          {avisoEntrar === 'vencida' ? T.vencida : T.salio}
        </Nota>
      )}
      {falla?.tipo === 'espera' && (
        <Nota tono="atenta" rol="status">
          {T.espera(falla.minutos)}
        </Nota>
      )}
      {falla?.tipo === 'no-disponible' && (
        <Nota tono="pronto" rol="alert">
          {T.noDisponible}
        </Nota>
      )}
      {falla?.tipo === 'red' && (
        <Nota tono="pronto" rol="alert">
          {T.error}
        </Nota>
      )}
      <form noValidate className="flex flex-col gap-5" onSubmit={(e) => void enviar(e)}>
        <CampoTexto etiqueta={T.correo} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={254} />
        <CampoTexto
          etiqueta={T.contrasena}
          type={ver ? 'text' : 'password'}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          autoComplete="current-password"
          maxLength={128}
          junto={<BotonMostrar visible={ver} onCambio={() => setVer((v) => !v)} />}
        />
        {falla?.tipo === 'faltan' && <MensajeError>{T.faltan}</MensajeError>}
        {falla?.tipo === 'credenciales' && (
          <Nota tono="pronto" rol="alert">
            {T.credenciales}
          </Nota>
        )}
        <Acciones>
          <Boton
            type="submit"
            ocupado={ocupado}
            textoOcupado={T.enviando}
            aria-disabled={esperando || undefined}
            className="aria-disabled:cursor-not-allowed aria-disabled:opacity-60 aria-disabled:focus-visible:outline-tinta"
          >
            {T.boton}
          </Boton>
        </Acciones>
      </form>
      {/* 4.1: sin enlace a recuperar: la recuperación por celular (MATU-57) es de las cuentas de familia. */}
      <p className="max-w-prose text-base break-words text-tenue">{T.olvido(contacto)}</p>
      <p className="max-w-prose">
        {T.aLaFamiliaAntes}
        <EnlaceEnFrase href="/entrar">{T.aLaFamiliaEnlace}</EnlaceEnFrase>
        {T.aLaFamiliaDespues}
      </p>
    </MarcoEntrar>
  )
}
