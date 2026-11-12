// La app de la familia: decide qué pantalla va en cada ruta según la entrada, el grupo, la persona
// y el rol (especificación 1, 2 y 5). El foco va al título y el <title> nunca lleva nombres.
import { useEffect, useLayoutEffect } from 'react'
import { AQuien, Autorizacion, CrearCuenta, CrearGrupo, Entrar } from './Alta'
import { ConfirmarCelular, TuCuenta } from './Cuenta'
import { DondeEntraste } from './DondeEntraste'
import { DatosDePersona } from './DatosPersona'
import { TusDatos } from './TusDatos'
import { campoDeRuta, seccionDeRuta } from './datos'
import { EditorDeSeccion } from './EditorSeccion'
import { Compartir, EnlaceListo, Enlaces } from './Compartir'
import { Catalogo } from './Catalogo'
import { useRevisarVersion } from '../compartido/version'
import { Abriendo, ErrorAlAbrir, SinPersona, TextoPerdido } from './Estados'
import { AutorizarFicha, AutorizarInsumos, AutorizarPedidosDesdeGrupo, GrupoFamiliar } from './Grupo'
import { Insumos } from './Insumos'
import { PaginaInvitacion } from './Invitacion'
import { InvitacionLista, Invitar } from './Invitar'
import { ListaDeInsumos } from './ListaInsumos'
import { PantallaPedido } from './Pedido'
import { PantallaPago, VueltaSinSesion } from './Pago'
import { hayVuelta, RUTA_PAGO } from './vueltaPago'
import { ProveedorFamilia, puedeCompartir, puedeEditar, puedeVerFicha, useFamilia } from './estado'
import { AvisoDeLlegada, Editor, ID_AVISO_LLEGADA, SinAcceso, TuFicha } from './Ficha'
import { QuienLaVio } from './QuienLaVio'
import { CambiarConCodigo, PedirCodigo } from './Recuperar'
import { esRuta, navegar, PUBLICAS, useRuta, type Ruta } from './ruteo'
import { MarcoSimple, ShellFamilia } from './Shell'
import { FICHA, TITULOS } from './textos'

export function AppFamilia() {
  // MATU-67: revisa si hay una versión nueva al volver a la pestaña y cada 15 minutos.
  useRevisarVersion()
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
  // MATU-53 (2.1): la invitación se ve igual con sesión y sin ella, con grupo o sin él.
  if (ruta === '/invitacion') return null
  if (!esRuta(ruta) || ruta === '/') return inicio(s)
  // MATU-62 (7.10): la vuelta de Webpay se muestra aunque no se recupere la sesión, sin montos ni tarjeta.
  if (s.fase !== 'dentro' && ruta === RUTA_PAGO && hayVuelta()) return null
  if (s.fase !== 'dentro') return PUBLICAS.has(ruta) ? null : '/entrar'
  if (PUBLICAS.has(ruta)) return inicio(s)
  // MATU-57: «Tu cuenta» no depende del grupo ni de la persona.
  // MATU-55: «Dónde entraste» tampoco. MATU-54: «Tus datos» tampoco, y la ve todo rol.
  if (ruta === '/cuenta' || ruta === '/cuenta/celular' || ruta === '/cuenta/donde-entraste' || ruta === '/cuenta/datos') return null
  const editor = puedeEditar(s.rol)
  if (ruta === '/empezar/grupo') return s.grupos.length ? '/empezar/persona' : null
  // 5.3: sin grupo, toda sección lleva a crear el grupo.
  if (!s.grupos.length) return '/empezar/grupo'
  // MATU-54 (1): «Datos de…», solo admin y cuidador y solo desde «Ver los datos de…» (la persona en
  // memoria). Al recargar, o si la persona ya no está, se vuelve a Grupo familiar sin aviso.
  if (ruta === '/grupo/datos') return editor && s.datosDe && s.personas.some((p) => p.id === s.datosDe) ? null : '/grupo'
  if (ruta === '/empezar/persona' || ruta === '/empezar/autorizacion') return editor ? null : inicio(s)
  // MATU-53 (decisión del 12-11): Grupo familiar se alcanza sin persona registrada, para todos los
  // roles, para ver quiénes forman el grupo y poder salir. Invitar, solo admin (más abajo).
  const delGrupo = ruta === '/grupo' || ruta === '/grupo/invitar' || ruta === '/grupo/invitar/listo'
  // 5.4: sin persona, el admin y el cuidador van a registrarla.
  if (!s.personas.length && editor && !delGrupo) return '/empezar/persona'
  // MATU-48 2.1: crear y ver el PIN, solo admin y cuidador. La lista de enlaces también la ve el
  // pagador con `puede_ver_plan`, sin teléfono ni «Cortar».
  if ((ruta === '/compartir' || ruta === '/compartir/listo') && !puedeCompartir(s.rol)) return inicio(s)
  if (ruta === '/compartir/enlaces' && !puedeCompartir(s.rol) && !(s.rol === 'pagador' && s.grupo?.puede_ver_plan)) return inicio(s)
  // MATU-44 2.1: volver a autorizar, solo admin y cuidador y solo desde «Volver a autorizar» (con la
  // persona elegida en memoria). Al recargar no hay intención y se vuelve a Grupo familiar.
  if (ruta === '/grupo/autorizar-ficha' || ruta === '/grupo/autorizar-insumos' || ruta === '/grupo/autorizar-pedidos') {
    const finalidad = ruta === '/grupo/autorizar-ficha' ? 'plan_cuidado' : ruta === '/grupo/autorizar-insumos' ? 'consumo' : 'despacho'
    const r = s.reautorizar
    if (!editor || !r || r.finalidad !== finalidad || r.personaId !== s.personaId) return '/grupo'
  }
  // MATU-61 2.1: la dirección es de admin y cuidador, y el observador no llega al resumen (su vista
  // no lo trae). Quien no puede ver una ruta del pedido llega a «Tu pedido».
  // MATU-53 (2): invitar es solo de quien administra; los demás roles vuelven a Grupo familiar.
  if ((ruta === '/grupo/invitar' || ruta === '/grupo/invitar/listo') && s.rol !== 'admin') return '/grupo'
  if (ruta === '/insumos/pedido/direccion' && !editor) return '/insumos/pedido'
  if (ruta === '/insumos/pedido/resumen' && s.rol === 'observador') return '/insumos/pedido'
  // MATU-62 2.1: el observador llega a «Tu pedido». Con una vuelta de Webpay no: el grupo elegido al
  // abrir es el primero, y la vuelta fija después el del pedido.
  if (ruta === RUTA_PAGO && s.rol === 'observador' && !hayVuelta()) return '/insumos/pedido'
  return null
}

function tituloDe(ruta: string) {
  if (campoDeRuta(ruta)) return campoDeRuta(ruta)!.titulo
  if (seccionDeRuta(ruta)) return seccionDeRuta(ruta)!.titulo
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

  // 2.5 y 2.6: título del documento y foco en el h1 al cambiar de pantalla. MATU-72 4.3: si la pantalla
  // trae una nota de llegada que pide el foco (la persona elegida se borró y quedan otras), va a ella.
  useLayoutEffect(() => {
    document.title = `${tituloDe(ruta)} · MATU`
  }, [ruta])
  // MATU-61 (2.2): la pestaña «Pedido» depende de la capa 3. El catálogo y el pedido ya piden el
  // catálogo y la fijan ellos: ahí no se pregunta dos veces.
  const { fase, capa3, conocerCapa3 } = s
  useEffect(() => {
    // Revisión P2-3: la dirección no pide el catálogo, así que al entrar directo a ella (desde Grupo
    // familiar o al recargar) se pregunta aquí, y «Pedido» aparece activa.
    // MATU-62: la vuelta de Webpay y el comprobante tampoco piden el catálogo.
    const propia = ruta === '/insumos/catalogo' || (ruta.startsWith('/insumos/pedido') && ruta !== '/insumos/pedido/direccion' && ruta !== RUTA_PAGO)
    if (fase === 'dentro' && capa3 === null && ruta.startsWith('/insumos') && !propia) conocerCapa3()
  }, [fase, capa3, conocerCapa3, ruta])
  useEffect(() => {
    if (s.fase === 'cargando') return
    // MATU-54 (2 y 4): al volver de «Datos de…» o de «Tus datos», la pantalla devuelve el foco al botón
    // que la abrió cuando ya lo pintó; aquí no se lleva al `h1`. Si se fue a otra ruta antes de que
    // esa pantalla cargara, el foco pendiente se olvida y vale la regla de siempre.
    if (s.focoAlVolver) {
      if (ruta === '/grupo' || ruta === '/cuenta') return
      s.fijar({ focoAlVolver: null })
    }
    const t = window.setTimeout(() => (document.getElementById(ID_AVISO_LLEGADA) ?? document.getElementById('titulo-pagina'))?.focus({ preventScroll: false }), 0)
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

  if (s.fase !== 'dentro' && ruta === RUTA_PAGO)
    return (
      <MarcoSimple>
        <VueltaSinSesion />
      </MarcoSimple>
    )

  // MATU-53 (2.1): la página de la persona invitada, sin el `Shell`, con su marco público.
  if (ruta === '/invitacion') return <PaginaInvitacion />

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
  const seccion = seccionDeRuta(ruta)
  let pantalla
  if (ruta === '/cuenta') pantalla = <TuCuenta />
  else if (ruta === '/cuenta/celular') pantalla = <ConfirmarCelular />
  else if (ruta === '/cuenta/donde-entraste') pantalla = <DondeEntraste />
  else if (ruta === '/cuenta/datos') pantalla = <TusDatos />
  // MATU-59 (2.2): el catálogo no depende de la persona ni de su autorización.
  else if (ruta === '/insumos/catalogo') pantalla = <Catalogo />
  // MATU-62: la vuelta de Webpay fija ella la persona del pedido (7.1), así que no depende de la elegida.
  else if (ruta === RUTA_PAGO && (s.persona || hayVuelta())) pantalla = <PantallaPago />
  // MATU-53: Grupo familiar y lo de invitar no dependen de la persona elegida.
  else if (ruta === '/grupo') pantalla = <GrupoFamiliar />
  else if (ruta === '/grupo/invitar') pantalla = <Invitar />
  else if (ruta === '/grupo/invitar/listo') pantalla = <InvitacionLista />
  // MATU-54: la persona de «Datos de…» es la de `datosDe`, no la elegida en el encabezado.
  else if (ruta === '/grupo/datos') pantalla = <DatosDePersona />
  else if (!s.persona) pantalla = <SinPersona />
  else if (ruta === '/ficha/quien-la-vio') pantalla = <QuienLaVio />
  else if (ruta === '/ficha' || campo || seccion) {
    if (!puedeVerFicha(s.rol, s.grupo)) pantalla = <SinAcceso />
    else pantalla = campo ? <Editor campo={campo} /> : seccion ? <EditorDeSeccion seccion={seccion} /> : <TuFicha />
  } else if (ruta === '/compartir') pantalla = <Compartir />
  else if (ruta === '/compartir/listo') pantalla = <EnlaceListo />
  else if (ruta === '/compartir/enlaces') pantalla = <Enlaces />
  else if (ruta === '/insumos/lista') pantalla = <ListaDeInsumos />
  // MATU-61: las tres rutas del pedido son una sola pantalla, que conserva el pedido en memoria al
  // pasar del carrito a la dirección y al resumen (la `key` de abajo no cambia entre ellas).
  else if (ruta.startsWith('/insumos/pedido')) pantalla = <PantallaPedido />
  else if (ruta === '/grupo/autorizar-ficha') pantalla = <AutorizarFicha />
  else if (ruta === '/grupo/autorizar-insumos') pantalla = <AutorizarInsumos />
  else if (ruta === '/grupo/autorizar-pedidos') pantalla = <AutorizarPedidosDesdeGrupo />
  // MATU-53 (4.6 y 7.2): «Ya eres parte de…» y «Saliste de…» al llegar al inicio del pagador o del observador.
  else if (ruta === '/insumos')
    pantalla = (
      <>
        <AvisoDeLlegada />
        <Insumos />
      </>
    )
  else pantalla = <Insumos />

  return (
    <ShellFamilia>
      <div key={`${ruta.startsWith('/insumos') ? '/insumos' : ruta}-${s.personaId}`} className="animate-aparecer">
        {pantalla}
      </div>
    </ShellFamilia>
  )
}
