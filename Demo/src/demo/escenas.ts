// Escenas del panel del presentador: cada una deja el estado listo para mostrar una
// pantalla, con una nota de una línea sobre lo que demuestra.
import { TEXTO_CAMPO, TEXTO_RODRIGO } from './datos'
import {
  abrirCampo,
  abrirRelevo,
  accesoDelRelevo,
  accesoPorDefecto,
  canjear,
  conFamilia,
  cortarAcceso,
  estadoInicial,
  pedidoHasta,
  personaEjemplo,
  pilaComercio,
  pilaFamilia,
  rodrigoEdita,
  ultimoAcceso,
  vaciarInsumos,
  elegirMedio,
  etapa,
} from './logica'
import { accesoVigente } from './calculos'
import type { Estado, PantallaComercioId, PantallaFamiliaId, Rol } from './tipos'

export type Capa = 1 | 2 | 3 | 4

export interface Escena {
  id: string
  capa: Capa
  titulo: string
  nota: string
  rol: Rol
  preparar: (s: Estado) => Estado
}

export const CAPAS: { capa: Capa; titulo: string; bajada: string }[] = [
  { capa: 1, titulo: 'Ficha de relevo', bajada: 'El producto' },
  { capa: 2, titulo: 'Consumo y predicción', bajada: 'El diferenciador' },
  { capa: 3, titulo: 'Pedido y pago', bajada: 'El servicio, un solo pagador' },
  { capa: 4, titulo: 'Casos borde', bajada: 'Lo que sale mal, dicho claro' },
]

const familia = (ids: Parameters<typeof pilaFamilia>[1]) => (s: Estado) => pilaFamilia(conFamilia(s), ids)

function conAccesoActivo(s: Estado): Estado {
  const a = ultimoAcceso(s)
  return a && accesoVigente(a, s.ahora) ? s : { ...accesoPorDefecto(s), pinVisible: null }
}

function pedidoBorrador(s: Estado): Estado {
  let t = conFamilia(s)
  if (!t.pedido || t.pedido.estado !== 'borrador') t = pedidoHasta({ ...t, pedido: null }, 'borrador')
  return t
}

export const ESCENAS: Escena[] = [
  // Capa 1
  {
    id: 'bienvenida',
    capa: 1,
    titulo: 'Bienvenida',
    nota: 'Una promesa en una línea y una sola acción.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(s, ['bienvenida']),
  },
  {
    id: 'cuenta',
    capa: 1,
    titulo: 'Crear cuenta',
    nota: 'Solo nombre, email y contraseña: nada más para empezar.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(s, ['bienvenida', 'cuenta']),
  },
  {
    id: 'entrar',
    capa: 1,
    titulo: 'Entrar',
    nota: 'Inicia sesión y trae el grupo y la persona que ya existen.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(s, ['bienvenida', 'entrar']),
  },
  {
    id: 'a-quien',
    capa: 1,
    titulo: '¿A quién cuidas?',
    nota: 'Pide lo mínimo. No pregunta qué enfermedad tiene y la dirección es opcional.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(s, ['bienvenida', 'cuenta', 'a-quien']),
  },
  {
    id: 'permiso',
    capa: 1,
    titulo: 'Permiso',
    nota: 'Queda registrado en qué calidad se autoriza. Quien cuida de hecho ve un aviso y lo acepta.',
    rol: 'familia',
    // Sin persona, "Acepto y continúo" no tenía a quién dar de alta y no hacía nada.
    preparar: (s) => pilaFamilia(s.persona ? s : { ...s, persona: personaEjemplo() }, ['bienvenida', 'cuenta', 'a-quien', 'permiso']),
  },
  {
    id: 'inicio',
    capa: 1,
    titulo: 'Inicio',
    nota: 'Lo primero que se ve es la ficha, contada por campos: 1 de 3, no un porcentaje.',
    rol: 'familia',
    preparar: (s) => {
      const t = conFamilia(s)
      const f = { ...t.ficha, si_se_altera: { ...t.ficha.si_se_altera, texto: '' }, a_quien_llamar: { ...t.ficha.a_quien_llamar, texto: '' } }
      return pilaFamilia({ ...t, ficha: f }, ['inicio'])
    },
  },
  {
    id: 'completar',
    capa: 1,
    titulo: 'Completar un campo',
    nota: 'Tres campos cortos, cada uno con su pregunta guía y un ejemplo.',
    rol: 'familia',
    preparar: (s) => {
      const t = pilaFamilia(conFamilia(s), ['inicio'])
      const campo = t.ficha.si_se_altera.texto ? 'a_quien_llamar' : 'si_se_altera'
      return abrirCampo(t, campo)
    },
  },
  {
    id: 'ficha',
    capa: 1,
    titulo: 'Tu ficha',
    nota: 'El estado se dice con palabra, Listo o Falta, no solo con color.',
    rol: 'familia',
    preparar: familia(['ficha']),
  },
  {
    id: 'compartir',
    capa: 1,
    titulo: 'Compartir',
    nota: 'Quién reemplaza, qué campos ve y hasta cuándo. 24 horas por defecto.',
    rol: 'familia',
    preparar: familia(['ficha', 'compartir']),
  },
  {
    id: 'enlace-pin',
    capa: 1,
    titulo: 'Enlace y PIN',
    nota: 'El PIN se muestra una sola vez y se dicta por teléfono: viaja por otro canal que el enlace.',
    rol: 'familia',
    preparar: (s) => {
      const t = accesoPorDefecto(conFamilia(s))
      const id = t.pinVisible
      return { ...pilaFamilia(t, ['ficha', 'compartir', 'enlace-pin']), pinVisible: id }
    },
  },
  {
    id: 'relevo-pin',
    capa: 1,
    titulo: 'Relevo: escribe el PIN',
    nota: 'Rosa abre sin cuenta. El token viaja en el fragmento /r#… y se borra al entrar.',
    rol: 'relevo',
    preparar: (s) => {
      const t = conAccesoActivo(conFamilia(s))
      return abrirRelevo(t, ultimoAcceso(t)!.id)
    },
  },
  {
    id: 'relevo-ficha',
    capa: 1,
    titulo: 'Relevo: la ficha',
    nota: 'Solo los campos habilitados, el nombre de pila y hasta cuándo está disponible.',
    rol: 'relevo',
    preparar: (s) => {
      let t = conAccesoActivo(conFamilia(s))
      t = abrirRelevo(t, ultimoAcceso(t)!.id)
      const a = accesoDelRelevo(t)!
      return canjear(t, a.token, a.pin)
    },
  },
  {
    id: 'quien-vio',
    capa: 1,
    titulo: 'Quién la vio',
    nota: 'Una línea por apertura, en lenguaje simple. Respaldo, no vigilancia.',
    rol: 'familia',
    preparar: familia(['ficha', 'quien-vio']),
  },
  {
    id: 'enlaces',
    capa: 1,
    titulo: 'Cortar un acceso',
    nota: 'Un toque y el enlace deja de abrir en la siguiente apertura.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(conAccesoActivo(conFamilia(s)), ['ficha', 'quien-vio', 'enlaces']),
  },
  {
    id: 'imprimir',
    capa: 1,
    titulo: 'Para imprimir',
    nota: 'La ficha en una hoja, para el refrigerador. Sin conexión y sin aplicación.',
    rol: 'familia',
    preparar: familia(['ficha', 'imprimir']),
  },
  // Capa 2
  {
    id: 'se-acaba',
    capa: 2,
    titulo: 'Qué se está acabando',
    nota: 'Días = lo que queda ÷ lo que usa al día. Ordenado por urgencia, con palabra y color.',
    rol: 'familia',
    preparar: familia(['se-acaba']),
  },
  {
    id: 'declarar',
    capa: 2,
    titulo: 'Declarar consumo',
    nota: 'Dos números por producto y nada más. La fecha se recalcula al tocar.',
    rol: 'familia',
    preparar: familia(['se-acaba', ['declarar', 'panal-m']]),
  },
  {
    id: 'ya-compre',
    capa: 2,
    titulo: 'Ya lo compré',
    nota: 'Sin esto la cuenta se desalinea. Se suma lo comprado y cambia la fecha.',
    rol: 'familia',
    preparar: familia(['se-acaba', ['ya-compre', 'panal-m']]),
  },
  {
    id: 'reponer',
    capa: 2,
    titulo: 'Lista de reposición',
    nota: 'Cuánto comprar para cubrir tres semanas. Funciona sin ningún comercio.',
    rol: 'familia',
    preparar: (s) => pilaFamilia({ ...conFamilia(s), ajustesLista: {} }, ['se-acaba', 'reponer']),
  },
  {
    id: 'exportar',
    capa: 2,
    titulo: 'Exportar la lista',
    nota: 'Copiar, compartir o descargar la lista para quien vaya a comprar.',
    rol: 'familia',
    preparar: familia(['se-acaba', 'reponer', 'exportar']),
  },
  // Capa 3
  {
    id: 'pedido',
    capa: 3,
    titulo: 'Tu pedido',
    nota: 'Paga una sola persona. La dirección se pide recién aquí.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoBorrador(s), ['se-acaba', 'reponer', 'pedido']),
  },
  {
    id: 'medio',
    capa: 3,
    titulo: 'Crédito o débito',
    nota: 'Antes de pagar se explica qué se reserva o se cobra, y qué vuelve.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoBorrador(s), ['reponer', 'pedido', 'medio']),
  },
  {
    id: 'pasarela',
    capa: 3,
    titulo: 'Pasarela simulada',
    nota: 'Transbank en ambiente de prueba. MATU nunca ve los datos de la tarjeta.',
    rol: 'familia',
    preparar: (s) => {
      const t = pedidoBorrador(s)
      return pilaFamilia(t.pedido?.medio ? t : elegirMedio(t, 'credito'), ['pedido', 'medio', 'pasarela'])
    },
  },
  {
    id: 'seguimiento',
    capa: 3,
    titulo: 'Seguimiento',
    nota: 'Estimado, lo reservado y, cuando se sabe, el monto real.',
    rol: 'familia',
    preparar: (s) => {
      const t = conFamilia(s)
      const listo = t.pedido && etapa(t.pedido.estado) >= etapa('pagado') && t.pedido.estado !== 'entregado'
      return pilaFamilia(listo ? t : pedidoHasta(t, 'pagado'), ['seguimiento'])
    },
  },
  {
    id: 'c-pedidos',
    capa: 3,
    titulo: 'Comercio: pedidos del día',
    nota: 'Segundo rol. Una pantalla, sin aprendizaje previo.',
    rol: 'comercio',
    preparar: (s) => {
      const t = conFamilia(s)
      const ok = t.pedido && etapa(t.pedido.estado) >= etapa('pagado')
      return pilaComercio(ok ? t : pedidoHasta(t, 'pagado'), ['c-pedidos'])
    },
  },
  {
    id: 'c-preparar',
    capa: 3,
    titulo: 'Comercio: preparar',
    nota: 'Resuelve lo que falta con la regla que dejó la familia. Ve el nombre de pila, no la dirección.',
    rol: 'comercio',
    preparar: (s) => pilaComercio(pedidoHasta(s, 'preparando'), ['c-pedidos', 'c-preparar']),
  },
  {
    id: 'c-monto',
    capa: 3,
    titulo: 'Comercio: monto real',
    nota: 'El monto de la boleta, nunca sobre el tope autorizado.',
    rol: 'comercio',
    preparar: (s) => {
      let t = pedidoHasta(s, 'preparando')
      if (t.pedido!.estado !== 'preparando') t = pedidoHasta({ ...t, pedido: null }, 'preparando')
      const lineas = t.pedido!.lineas.map((l) =>
        l.resolucion === 'sin_stock' ? { ...l, resolucion: 'reemplazado' as const, reemplazo: { nombre: 'Toallitas húmedas x80, otra marca', precio: 5_290 } } : l,
      )
      return pilaComercio({ ...t, pedido: { ...t.pedido!, lineas } }, ['c-pedidos', 'c-preparar', 'c-monto'])
    },
  },
  {
    id: 'c-codigo',
    capa: 3,
    titulo: 'Comercio: código de retiro',
    nota: 'Código de un solo uso. En el semestre la entrega se marca desde aquí.',
    rol: 'comercio',
    preparar: (s) => {
      let t = pedidoHasta(s, 'listo')
      if (t.pedido!.estado !== 'listo') t = pedidoHasta({ ...t, pedido: null }, 'listo')
      return pilaComercio(t, ['c-pedidos', 'c-codigo'])
    },
  },
  {
    id: 'entregado',
    capa: 3,
    titulo: 'Entregado',
    nota: 'Reserva $69.000, cobro $51.340: la prueba real de Transbank, explicada.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoHasta(s, 'entregado'), ['entregado']),
  },
  // Casos borde
  {
    id: 'vacio',
    capa: 4,
    titulo: 'Todavía no hay nada',
    nota: 'Estado vacío: propone la acción más barata y dice qué se gana.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(vaciarInsumos(conFamilia(s)), ['se-acaba']),
  },
  {
    id: 'conflicto',
    capa: 4,
    titulo: 'Dos versiones',
    nota: 'Otra persona editó el mismo campo. No se fusiona ni se oculta: se elige.',
    rol: 'familia',
    preparar: (s) => {
      let t = pilaFamilia(conFamilia(s), ['ficha'])
      t = { ...t, ficha: { ...t.ficha, si_se_altera: { texto: '', version: 0, autor: '', minuto: null } } }
      t = abrirCampo(t, 'si_se_altera')
      t = { ...t, borrador: { ...t.borrador!, texto: TEXTO_CAMPO.si_se_altera.dictado.split(' Si pregunta')[0] } }
      t = rodrigoEdita(t, 'si_se_altera', TEXTO_RODRIGO)
      const b = t.borrador!
      const suyo = t.ficha.si_se_altera
      const conConflicto = { ...t, conflicto: { campo: b.campo, suyo, mio: b.texto } }
      return pilaFamilia(conConflicto, ['ficha', ['completar', 'si_se_altera'], 'conflicto'])
    },
  },
  {
    id: 'rechazado',
    capa: 4,
    titulo: 'El pago no pasó',
    nota: 'Sin culpar a nadie y sin jerga de pasarela. No se cobró nada.',
    rol: 'familia',
    preparar: (s) => {
      const t = pedidoBorrador(s)
      const u = t.pedido?.medio ? t : elegirMedio(t, 'credito')
      return pilaFamilia({ ...u, pedido: { ...u.pedido!, rechazos: u.pedido!.rechazos + 1 } }, ['pedido', 'medio', 'rechazado'])
    },
  },
  {
    id: 'pin-incorrecto',
    capa: 4,
    titulo: 'Relevo: PIN incorrecto',
    nota: 'Dice cuántos intentos quedan. Al quinto error el enlace se bloquea.',
    rol: 'relevo',
    preparar: (s) => {
      let t = conFamilia(s)
      t = { ...accesoPorDefecto(t), pinVisible: null }
      t = abrirRelevo(t, ultimoAcceso(t)!.id)
      t = canjear(t, t.relevo.token, '1357')
      return canjear(t, t.relevo.token, '4812')
    },
  },
  {
    id: 'no-disponible',
    capa: 4,
    titulo: 'Relevo: enlace no disponible',
    nota: 'Vencido, cortado o bloqueado: misma pantalla y una sola acción.',
    rol: 'relevo',
    preparar: (s) => {
      let t = conAccesoActivo(conFamilia(s))
      const a = ultimoAcceso(t)!
      t = cortarAcceso(t, a.id)
      t = { ...abrirRelevo(t, a.id), aviso: null }
      return canjear(t, a.token, a.pin)
    },
  },
  {
    id: 'texto-200',
    capa: 4,
    titulo: 'Texto al 200%',
    nota: 'Todo sigue tocable y nada se corta con el texto al doble.',
    rol: 'familia',
    preparar: (s) => ({ ...pilaFamilia(conFamilia(s), ['inicio']), texto200: true }),
  },
]

export function prepararEscena(s: Estado, id: string): Estado {
  const e = ESCENAS.find((x) => x.id === id)
  if (!e) return s
  const base = id === 'texto-200' ? s : { ...s, texto200: false }
  const t = e.preparar({ ...base, aviso: null, conflicto: id === 'conflicto' ? base.conflicto : null })
  return { ...t, rol: e.rol }
}

/** Qué escena corresponde a lo que se ve ahora, para marcarla en el panel. */
export function escenaActual(s: Estado): string | null {
  if (s.texto200) return 'texto-200'
  if (s.rol === 'relevo') {
    if (s.relevo.fase === 'ficha') return 'relevo-ficha'
    if (s.relevo.fase === 'no_disponible') return 'no-disponible'
    return s.relevo.pinErroneo ? 'pin-incorrecto' : 'relevo-pin'
  }
  if (s.rol === 'comercio') {
    const id: PantallaComercioId = s.nav.comercio[s.nav.comercio.length - 1].id
    return id
  }
  const id: PantallaFamiliaId = s.nav.familia[s.nav.familia.length - 1].id
  const mapa: Partial<Record<PantallaFamiliaId, string>> = {
    guardado: 'completar',
    agregar: 'declarar',
  }
  if (id === 'se-acaba' && !s.insumos.some((i) => i.declarado)) return 'vacio'
  return mapa[id] ?? (ESCENAS.some((e) => e.id === id) ? id : null)
}

/** Escenas que usan la API real cuando el backend está conectado. El resto es simulado. */
export const ESCENAS_REALES = new Set(['cuenta', 'entrar', 'a-quien', 'permiso'])

export function reiniciar(): Estado {
  return estadoInicial()
}
