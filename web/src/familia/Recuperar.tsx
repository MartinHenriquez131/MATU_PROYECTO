// Recuperar el acceso (especificación MATU-57, secciones 2 y 3). El correo vive en memoria (`correo`
// del estado de la familia), nunca en la URL ni en el almacenamiento del navegador. La API de pedir
// el código responde siempre 202 (decisión 84): la pantalla nunca dice si la cuenta existe ni a qué
// canal fue el código.
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { flushSync } from 'react-dom'
import { leerFallo } from '../compartido/api/cliente'
import { cambiarContrasenaConCodigo, pedirCodigoRecuperacion } from '../compartido/api/familia'
import { Boton } from '../compartido/ui/Boton'
import { BotonMostrar, Encabezado, MarcoAlta, enfocarPrimerError } from './Alta'
import { CampoCodigo, useEspera } from './Codigo'
import { useFamilia } from './estado'
import { navegar } from './ruteo'
import { Acciones, CampoTexto, Nota, Volver } from './ui'
import { ENTRAR, GENERAL, RECUPERAR } from './textos'

type Falla = 'no-disponible' | 'red' | null

// ---------------------------------------------------------------- 2. Pedir el código

export function PedirCodigo() {
  const { correo, fijar } = useFamilia()
  const [email, setEmail] = useState(correo)
  const [error, setError] = useState<string | null>(null)
  const [falla, setFalla] = useState<Falla>(null)
  const [ocupado, setOcupado] = useState(false)
  const form = useRef<HTMLFormElement>(null)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado) return
    const limpio = email.trim()
    setFalla(null)
    if (!limpio.includes('@')) {
      setError(RECUPERAR.errCorreo)
      return enfocarPrimerError(form.current)
    }
    setError(null)
    setOcupado(true)
    try {
      await pedirCodigoRecuperacion(limpio)
      fijar({ correo: limpio, avisoEntrar: null })
      navegar('/entrar/recuperar/codigo')
    } catch (x) {
      const f = leerFallo(x)
      if (f.status === 422) {
        // Tras un `await`, React puede confirmar el estado después del setTimeout de enfocarPrimerError:
        // flushSync deja el campo con `aria-invalid` antes de buscarlo (como en Crear cuenta).
        flushSync(() => setError(RECUPERAR.errCorreo))
        enfocarPrimerError(form.current)
      } else setFalla(f.status === 503 ? 'no-disponible' : 'red')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <MarcoAlta>
      <Encabezado bajada={RECUPERAR.bajada} antes={<Volver onClick={() => volverAEntrar(fijar, email)}>{RECUPERAR.volver}</Volver>}>
        {RECUPERAR.titulo}
      </Encabezado>
      <form ref={form} noValidate className="flex flex-col gap-5" onSubmit={(e) => void enviar(e)}>
        <CampoTexto
          etiqueta={RECUPERAR.correo}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          maxLength={254}
          error={error}
          className="max-w-md"
        />
        <AvisoFalla falla={falla} />
        <Acciones>
          <Boton type="submit" ocupado={ocupado} textoOcupado={RECUPERAR.enviando}>
            {RECUPERAR.boton}
          </Boton>
        </Acciones>
      </form>
    </MarcoAlta>
  )
}

function volverAEntrar(fijar: ReturnType<typeof useFamilia>['fijar'], email: string) {
  fijar({ correo: email.trim(), avisoEntrar: null })
  navegar('/entrar')
}

function AvisoFalla({ falla }: { falla: Falla }) {
  if (!falla) return null
  return (
    <Nota tono="pronto" rol="alert">
      {falla === 'no-disponible' ? ENTRAR.noDisponible : GENERAL.error}
    </Nota>
  )
}

// ---------------------------------------------------------------- 3. El código y la contraseña nueva

type Errores = Partial<Record<'codigo' | 'contrasena', string>>

export function CambiarConCodigo() {
  const { correo, fijar } = useFamilia()
  const [codigo, setCodigo] = useState('')
  const [clave, setClave] = useState('')
  const [ver, setVer] = useState(false)
  const [errores, setErrores] = useState<Errores>({})
  const [falla, setFalla] = useState<Falla>(null)
  const [aviso, setAviso] = useState<'enviado' | 'reenviado'>('enviado')
  const [minutos, setMinutos] = useState<number | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [reenviando, setReenviando] = useState(false)
  // 60 s entre envíos (decisión 84): el reenvío espera, sin cuenta regresiva.
  const [pausa, setPausa] = useState(true)
  useEffect(() => {
    if (!pausa) return
    const t = window.setTimeout(() => setPausa(false), 60_000)
    return () => window.clearTimeout(t)
  }, [pausa])
  const { esperando, esperar } = useEspera()
  const form = useRef<HTMLFormElement>(null)
  const campoCodigo = useRef<HTMLInputElement>(null)

  // Si se recargó y el correo se perdió, se vuelve a pedirlo, sin aviso de error (especificación 1).
  useEffect(() => {
    if (!correo) navegar('/entrar/recuperar', { reemplazar: true })
  }, [correo])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado || esperando) return
    const err: Errores = {}
    if (codigo.length !== 6) err.codigo = RECUPERAR.errCodigoCorto
    if (clave.length < 10) err.contrasena = RECUPERAR.errClaveCorta
    setErrores(err)
    setFalla(null)
    if (Object.keys(err).length) return enfocarPrimerError(form.current)
    setOcupado(true)
    try {
      await cambiarContrasenaConCodigo(correo, codigo, clave)
      // D3: se vuelve a entrar, con el correo ya escrito (en memoria) y el aviso arriba.
      fijar({ correo, avisoEntrar: 'clave-cambiada' })
      navegar('/entrar', { reemplazar: true })
    } catch (x) {
      const f = leerFallo(x)
      if (f.status === 422 && f.tipo === '/errores/codigo-invalido') {
        // El código se vacía y la contraseña se conserva. flushSync: el campo ya es inválido al recibir el foco.
        flushSync(() => {
          setCodigo('')
          setErrores({ codigo: RECUPERAR.errCodigo })
        })
        window.setTimeout(() => campoCodigo.current?.focus(), 0)
      } else if (f.status === 422 && f.campos.length) {
        const e422: Errores = {}
        if (f.campos.includes('codigo')) e422.codigo = RECUPERAR.errCodigoCorto
        if (f.campos.includes('contrasena_nueva')) e422.contrasena = RECUPERAR.errClave422
        flushSync(() => setErrores(e422))
        if (Object.keys(e422).length) enfocarPrimerError(form.current)
        else setFalla('red')
      } else if (f.status === 429) setMinutos(esperar(f.reintentarEnSegundos))
      else setFalla(f.status === 503 ? 'no-disponible' : 'red')
    } finally {
      setOcupado(false)
    }
  }

  const reenviar = async () => {
    if (reenviando || esperando || pausa) return
    setReenviando(true)
    setFalla(null)
    try {
      await pedirCodigoRecuperacion(correo, true)
      setAviso('reenviado')
      setPausa(true)
      setCodigo('')
      setErrores((x) => ({ contrasena: x.contrasena }))
      setMinutos(null)
    } catch (x) {
      setFalla(leerFallo(x).status === 503 ? 'no-disponible' : 'red')
    } finally {
      setReenviando(false)
    }
  }

  if (!correo) return null

  return (
    <MarcoAlta>
      <Encabezado
        bajada={RECUPERAR.bajadaCodigo}
        antes={
          <>
            <Volver onClick={() => navegar('/entrar/recuperar')}>{RECUPERAR.volverCodigo}</Volver>
            <Nota key={aviso} tono="rocio" rol="status" className="mb-2">
              {aviso === 'enviado' ? RECUPERAR.enviado : RECUPERAR.reenviado}
            </Nota>
          </>
        }
      >
        {RECUPERAR.tituloCodigo}
      </Encabezado>
      {minutos !== null && esperando && (
        <Nota tono="atenta" rol="status">
          {RECUPERAR.esperaCodigo(minutos)}
        </Nota>
      )}
      <form ref={form} noValidate className="flex flex-col gap-5" onSubmit={(e) => void enviar(e)}>
        {/* Ayuda a los gestores de contraseñas a guardar la nueva con el correo correcto. */}
        <input type="email" name="email" autoComplete="username" value={correo} readOnly hidden />
        <CampoCodigo ref={campoCodigo} etiqueta={RECUPERAR.codigo} valor={codigo} onCambio={setCodigo} error={errores.codigo} />
        <CampoTexto
          etiqueta={RECUPERAR.nueva}
          type={ver ? 'text' : 'password'}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          autoComplete="new-password"
          minLength={10}
          maxLength={128}
          ayuda={RECUPERAR.nuevaAyuda}
          error={errores.contrasena}
          className="max-w-md"
          junto={<BotonMostrar visible={ver} onCambio={() => setVer((v) => !v)} />}
        />
        <AvisoFalla falla={falla} />
        <Acciones>
          <Boton type="submit" ocupado={ocupado} textoOcupado={RECUPERAR.cambiando} disabled={esperando}>
            {RECUPERAR.botonCambiar}
          </Boton>
        </Acciones>
      </form>
      <div className="flex flex-col items-start">
        <p className="text-tenue">{RECUPERAR.noLlego}</p>
        <Boton variante="texto" className="justify-start! text-left" ocupado={reenviando} textoOcupado={RECUPERAR.enviando} disabled={esperando || pausa} onClick={() => void reenviar()}>
          {RECUPERAR.reenviar}
        </Boton>
        {pausa && !esperando && <p className="text-base text-tenue">{RECUPERAR.enUnMinuto}</p>}
      </div>
    </MarcoAlta>
  )
}
