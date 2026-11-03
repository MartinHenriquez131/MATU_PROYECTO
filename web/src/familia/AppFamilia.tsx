// La app de la familia: decide qué pantalla va en cada ruta según la entrada, el grupo, la persona
// y el rol (especificación 1, 2 y 5). El foco va al título y el <title> nunca lleva nombres.
import { useEffect, useLayoutEffect } from 'react'
import { AQuien, Autorizacion, CrearCuenta, CrearGrupo, Entrar } from './Alta'
import { ConfirmarCelular, TuCuenta } from './Cuenta'
import { campoDeRuta } from './datos'
import { Abriendo, CompartirPronto, ErrorAlAbrir, InsumosPronto, SinPersona, TextoPerdido } from './Estados'
import { ProveedorFamilia, puedeCompartir, puedeEditar, puedeVerFicha, useFamilia } from './estado'
import { Editor, SinAcceso, TuFicha } from './Ficha'
import { CambiarConCodigo, PedirCodigo } from './Recuperar'
import { esRuta, navegar, PUBLICAS, useRuta, type Ruta } from './ruteo'
import { MarcoSimple, ShellFamilia } from './Shell'
import { FICHA, TITULOS } from './textos'

export function AppFamilia() {
  return (
    <ProveedorFamilia>
      <Rutas />
    </ProveedorFamilia>
  )
}

/** Adónde lleva `/` (y las rutas que no aplican) según lo que hay. */
function inicio(s: ReturnType<typeof useFamilia>): Ruta {
  if (s.fase !== 'dentro') return '/entrar'
  if (!s.grupos.length) return '/empezar/grupo'
  if (!s.personas.length) return puedeEditar(s.rol) ? '/empezar/persona' : '/insumos'
  return puedeVerFicha(s.rol, s.grupo) ? '/ficha' : '/insumos'
}

/** La redirección que corresponde, o `null` si la ruta se muestra tal cual. */
function redireccion(ruta: string, s: ReturnType<typeof useFamilia>): Ruta | null {
  if (!esRuta(ruta) || ruta === '/') return inicio(s)
  if (s.fase !== 'dentro') return PUBLICAS.has(ruta) ? null : '/entrar'
  if (PUBLICAS.has(ruta)) return inicio(s)
  // MATU-57: «Tu cuenta» no depende del grupo ni de la persona.
  if (ruta === '/cuenta' || ruta === '/cuenta/celular') return null
  const editor = puedeEditar(s.rol)
  if (ruta === '/empezar/grupo') return s.grupos.length ? '/empezar/persona' : null
  // 5.3: sin grupo, toda sección lleva a crear el grupo.
  if (!s.grupos.length) return '/empezar/grupo'
  if (ruta === '/empezar/persona' || ruta === '/empezar/autorizacion') return editor ? null : inicio(s)
  // 5.4: sin persona, el admin y el cuidador van a registrarla.
  if (!s.personas.length && editor) return '/empezar/persona'
  if (ruta === '/compartir' && !puedeCompartir(s.rol)) return inicio(s)
  return null
}

function tituloDe(ruta: string) {
  if (campoDeRuta(ruta)) return campoDeRuta(ruta)!.titulo
  return TITULOS[ruta] ?? FICHA.titulo
}

function Rutas() {
  const s = useFamilia()
  const ruta = useRuta()
  const destino = s.fase === 'cargando' || s.fase === 'error' || s.textoPerdido ? null : redireccion(ruta, s)

  useEffect(() => {
    if (!destino) return
    // Ruta que pide haber entrado, sin haber entrado: se guarda en memoria para volver (1).
    if (s.fase === 'fuera' && destino === '/entrar' && esRuta(ruta) && ruta !== '/' && !PUBLICAS.has(ruta)) s.fijar({ destino: ruta })
    navegar(destino, { reemplazar: true })
  }, [destino, ruta, s])

  // 2.5 y 2.6: título del documento y foco en el h1 al cambiar de pantalla.
  useLayoutEffect(() => {
    document.title = `${tituloDe(ruta)} · MATU`
  }, [ruta])
  useEffect(() => {
    if (s.fase === 'cargando') return
    const t = window.setTimeout(() => document.getElementById('titulo-pagina')?.focus({ preventScroll: false }), 0)
    return () => window.clearTimeout(t)
  }, [ruta, s.fase, s.personaId])

  if (s.fase === 'cargando')
    return (
      <MarcoSimple>
        <Abriendo />
      </MarcoSimple>
    )
  if (s.fase === 'error')
    return (
      <MarcoSimple>
        <ErrorAlAbrir />
      </MarcoSimple>
    )
  if (s.textoPerdido)
    return (
      <MarcoSimple>
        <TextoPerdido />
      </MarcoSimple>
    )
  if (destino) return null

  switch (ruta) {
    case '/crear-cuenta':
      return <CrearCuenta />
    case '/entrar':
      return <Entrar />
    case '/entrar/recuperar':
      return <PedirCodigo />
    case '/entrar/recuperar/codigo':
      return <CambiarConCodigo />
    case '/empezar/grupo':
      return <CrearGrupo />
    case '/empezar/persona':
      return <AQuien />
    case '/empezar/autorizacion':
      return <Autorizacion />
  }

  const campo = campoDeRuta(ruta)
  let pantalla
  if (ruta === '/cuenta') pantalla = <TuCuenta />
  else if (ruta === '/cuenta/celular') pantalla = <ConfirmarCelular />
  else if (!s.persona) pantalla = <SinPersona />
  else if (ruta === '/ficha' || campo) {
    if (!puedeVerFicha(s.rol, s.grupo)) pantalla = <SinAcceso />
    else pantalla = campo ? <Editor campo={campo} /> : <TuFicha />
  } else if (ruta === '/compartir') pantalla = <CompartirPronto />
  else pantalla = <InsumosPronto />

  return (
    <ShellFamilia>
      <div key={`${ruta}-${s.personaId}`} className="animate-aparecer">
        {pantalla}
      </div>
    </ShellFamilia>
  )
}
