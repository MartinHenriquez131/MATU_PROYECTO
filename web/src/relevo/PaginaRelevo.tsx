// La página /r#<token> (MATU-23, especificación 3.0). Tres momentos: quién te la mandó y el PIN,
// la ficha y, si el enlace ya no sirve, qué pasó y qué hacer.
//
// Datos sensibles: el token se lee del fragmento, vive solo en memoria y viaja en el cuerpo de un
// POST. Después del canje la dirección queda en /r (history.replaceState). Nada de la ficha va a
// localStorage, sessionStorage ni a la URL. Tras un 401, 410 o 423 la ficha se saca del estado.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { leerFallo } from '../compartido/api/cliente'
import { canjear, leerFicha, presentar, type FichaRelevo, type Presentacion } from '../compartido/api/relevo'
import { clasificar, ESTADOS, type EstadoNoAbre } from './estados'
import { Marco } from './Marco'
import { PantallaFicha, type ResultadoActualizar } from './PantallaFicha'
import { PantallaPin, type ResultadoCanje } from './PantallaPin'
import { Cargando, PantallaError, PantallaEstado } from './PantallasSimples'
import { CARGANDO, TITULO_DOCUMENTO, tituloDocumentoDeEstado } from './textos'

type Peticion = 'enlace' | 'ficha'

type Momento =
  | { tipo: 'cargando'; que: Peticion }
  | { tipo: 'pin'; presentacion: Presentacion }
  | { tipo: 'ficha'; ficha: FichaRelevo }
  | { tipo: 'estado'; estado: EstadoNoAbre; minutos: number | null }
  | { tipo: 'error'; que: Peticion; reintentando: boolean; intento: number }

/** Lo que viene después de `#`. Vacío = no hay enlace en la dirección (se recargó tras entrar). */
function tokenDelFragmento(): string | null {
  const t = window.location.hash.slice(1)
  return t ? t : null
}

/** Deja la dirección en /r, sin el fragmento, sin agregar una entrada al historial. */
function limpiarDireccion() {
  window.history.replaceState(window.history.state, '', window.location.pathname)
}

// setTimeout no admite más de 2^31 - 1 ms (unos 24 días).
const ESPERA_MAXIMA_MS = 2_147_483_647

export function PaginaRelevo() {
  const token = useRef<string | null>(tokenDelFragmento())
  const [momento, setMomento] = useState<Momento>(() => ({ tipo: 'cargando', que: token.current ? 'enlace' : 'ficha' }))
  // Cada petición lleva un número: una respuesta que llega tarde no pisa a la más nueva.
  const secuencia = useRef(0)
  // Peticiones de la ficha en curso: la revalidación silenciosa no se suma a una que ya va.
  const fichaEnCurso = useRef(0)

  const aEstado = useCallback((estado: EstadoNoAbre, minutos: number | null) => {
    setMomento({ tipo: 'estado', estado, minutos })
  }, [])

  const abrirEnlace = useCallback(
    async (intento = 0) => {
      const t = token.current
      if (!t) return
      const n = ++secuencia.current
      try {
        const p = await presentar(t)
        if (n !== secuencia.current) return
        setMomento({ tipo: 'pin', presentacion: p })
      } catch (e) {
        if (n !== secuencia.current) return
        const c = clasificar(leerFallo(e), 'presentacion')
        if (c.clase === 'estado') aEstado(c.estado, c.minutos)
        else setMomento({ tipo: 'error', que: 'enlace', reintentando: false, intento })
      }
    },
    [aEstado],
  )

  const abrirFicha = useCallback(
    async (intento = 0) => {
      const n = ++secuencia.current
      fichaEnCurso.current += 1
      try {
        const f = await leerFicha()
        if (n !== secuencia.current) return
        setMomento({ tipo: 'ficha', ficha: f })
      } catch (e) {
        if (n !== secuencia.current) return
        const c = clasificar(leerFallo(e), 'ficha')
        if (c.clase === 'estado') aEstado(c.estado, c.minutos)
        else setMomento({ tipo: 'error', que: 'ficha', reintentando: false, intento })
      } finally {
        fichaEnCurso.current -= 1
      }
    },
    [aEstado],
  )

  /** Vuelve a pedir la ficha ya abierta. `silenciosa` = sin "Actualizando…" ni confirmación. */
  const revalidar = useCallback(
    async (silenciosa: boolean): Promise<ResultadoActualizar> => {
      if (silenciosa && fichaEnCurso.current > 0) return 'ok'
      const n = ++secuencia.current
      fichaEnCurso.current += 1
      try {
        const f = await leerFicha()
        if (n !== secuencia.current) return 'salio'
        setMomento({ tipo: 'ficha', ficha: f })
        return 'ok'
      } catch (e) {
        if (n !== secuencia.current) return 'salio'
        const c = clasificar(leerFallo(e), 'ficha')
        // 401, 410 o 423: la hoja se descarta antes de pintar el estado.
        if (c.clase === 'estado') {
          aEstado(c.estado, c.minutos)
          return 'salio'
        }
        if (c.clase === 'general' && c.descartar) {
          setMomento({ tipo: 'error', que: 'ficha', reintentando: false, intento: 0 })
          return 'salio'
        }
        // Red o 5xx: la hoja sigue a la vista.
        return 'error'
      } finally {
        fichaEnCurso.current -= 1
      }
    },
    [aEstado],
  )

  const onCanjear = useCallback(
    async (pin: string): Promise<ResultadoCanje> => {
      const t = token.current
      if (!t) return { tipo: 'conexion' }
      const n = ++secuencia.current
      try {
        await canjear(t, pin)
        if (n !== secuencia.current) return { tipo: 'salio' }
        // 204: el token sale de la memoria y de la dirección, y se pide la ficha con la cookie.
        token.current = null
        limpiarDireccion()
        setMomento({ tipo: 'cargando', que: 'ficha' })
        void abrirFicha()
        return { tipo: 'salio' }
      } catch (e) {
        if (n !== secuencia.current) return { tipo: 'salio' }
        const c = clasificar(leerFallo(e), 'canje')
        if (c.clase === 'estado') {
          aEstado(c.estado, c.minutos)
          return { tipo: 'salio' }
        }
        if (c.clase === 'pin-incorrecto') return { tipo: 'incorrecto', intentos: c.intentos }
        if (c.clase === 'pin-incompleto') return { tipo: 'incompleto' }
        return { tipo: 'conexion' }
      }
    },
    [aEstado, abrirFicha],
  )

  const reintentar = () => {
    if (momento.tipo !== 'error' || momento.reintentando) return
    const siguiente = momento.intento + 1
    setMomento({ ...momento, reintentando: true })
    if (momento.que === 'enlace' && token.current) void abrirEnlace(siguiente)
    else void abrirFicha(siguiente)
  }

  // Primera petición. El ref evita pedir dos veces con el doble montaje de StrictMode.
  const iniciado = useRef(false)
  useEffect(() => {
    if (iniciado.current) return
    iniciado.current = true
    if (token.current) void abrirEnlace()
    else void abrirFicha()
  }, [abrirEnlace, abrirFicha])

  // Si se abre otro enlace en la misma pestaña, el navegador solo cambia el fragmento.
  useEffect(() => {
    const alCambiar = () => {
      const t = tokenDelFragmento()
      if (!t || t === token.current) return
      token.current = t
      setMomento({ tipo: 'cargando', que: 'enlace' })
      void abrirEnlace()
    }
    window.addEventListener('hashchange', alCambiar)
    return () => window.removeEventListener('hashchange', alCambiar)
  }, [abrirEnlace])

  // Con la ficha abierta, se vuelve a pedir al volver a la pestaña y cuando pasa el vencimiento:
  // si cortaron o venció el enlace, Rosa ve el estado y no un texto que ya no debería ver.
  const venceEn = momento.tipo === 'ficha' ? momento.ficha.vence_en : null
  useEffect(() => {
    if (venceEn === null) return
    const alVolver = () => {
      if (document.visibilityState === 'visible') void revalidar(true)
    }
    document.addEventListener('visibilitychange', alVolver)
    const faltan = Date.parse(venceEn) - Date.now() + 1000
    const reloj = faltan > 0 ? window.setTimeout(() => void revalidar(true), Math.min(faltan, ESPERA_MAXIMA_MS)) : undefined
    return () => {
      document.removeEventListener('visibilitychange', alVolver)
      window.clearTimeout(reloj)
    }
  }, [venceEn, revalidar])

  // Al cambiar de momento, el foco va al título de la pantalla nueva y cambia el <title>.
  const clave =
    momento.tipo === 'estado'
      ? `estado-${momento.estado}`
      : momento.tipo === 'error'
        ? `error-${momento.intento}`
        : momento.tipo === 'cargando'
          ? `cargando-${momento.que}`
          : momento.tipo
  useLayoutEffect(() => {
    document.getElementById('titulo-pagina')?.focus()
  }, [clave])
  useEffect(() => {
    document.title = momento.tipo === 'estado' ? tituloDocumentoDeEstado(ESTADOS[momento.estado].titulo) : TITULO_DOCUMENTO
  }, [momento])

  return (
    <Marco ocupado={momento.tipo === 'cargando'}>
      {momento.tipo === 'cargando' && <Cargando key={momento.que} texto={CARGANDO[momento.que]} />}
      {momento.tipo === 'pin' && <PantallaPin presentacion={momento.presentacion} onCanjear={onCanjear} />}
      {momento.tipo === 'ficha' && <PantallaFicha ficha={momento.ficha} onActualizar={() => revalidar(false)} />}
      {momento.tipo === 'estado' && <PantallaEstado estado={momento.estado} minutos={momento.minutos} />}
      {momento.tipo === 'error' && (
        <PantallaError ocupado={momento.reintentando} textoOcupado={CARGANDO[momento.que]} onReintentar={reintentar} />
      )}
    </Marco>
  )
}
