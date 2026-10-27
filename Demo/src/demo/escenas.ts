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
  pantallaFamilia,
  pedidoHasta,
  personaEjemplo,
  pilaComercio,
  pilaFamilia,
  rodrigoEdita,
  ultimoAcceso,
  vaciarInsumos,
  pasarMinutos,
} from './logica'
import { accesoVigente, devolucion, totalVencido } from './calculos'
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

/** Un pedido con el stock recién confirmado: $57.460, vigente por 15 minutos. */
function pedidoApartado(s: Estado): Estado {
  return pedidoHasta({ ...conFamilia(s), pedido: null }, 'apartado')
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
    nota: 'Quién reemplaza, qué campos ve, hasta cuándo y para qué. 24 horas por defecto.',
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
    nota: 'Rosa abre sin cuenta y ve qué guarda MATU de sus datos. El token viaja en el fragmento /r#… y se borra al entrar. Abrir el enlace ya queda en «Quién la vio».',
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
    nota: 'Una línea cada vez que alguien abre el enlace o la ficha, o escribe mal el PIN. Respaldo, no vigilancia.',
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
    nota: 'Precios exactos de un comercio, envío desde la lista y tres salidas. Exportar y compartir son gratis.',
    rol: 'familia',
    preparar: (s) => pilaFamilia({ ...conFamilia(s), ajustesLista: {}, pedido: null }, ['se-acaba', 'reponer']),
  },
  {
    id: 'exportar',
    capa: 2,
    titulo: 'Exportar o compartir la lista',
    nota: 'Copiar, descargar, enviar a Rodrigo (del grupo) o compartir desde el teléfono. Sin pedir en MATU.',
    rol: 'familia',
    preparar: (s) => pilaFamilia({ ...conFamilia(s), ajustesLista: {}, pedido: null }, ['se-acaba', 'reponer', 'exportar']),
  },
  // Capa 3
  {
    id: 'pedido',
    capa: 3,
    titulo: 'Tu pedido, antes de pagar',
    nota: 'Stock confirmado: las toallitas salieron y el suplemento bajó de precio. Todo lo que exige la ley, antes de pagar.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoApartado(s), ['se-acaba', 'reponer', 'pedido']),
  },
  {
    id: 'pasarela',
    capa: 3,
    titulo: 'Pasarela simulada',
    nota: 'Crédito o débito de prueba, el mismo monto. "Pago de prueba. No se cobra dinero real."',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoApartado(s), ['reponer', 'pedido', 'pasarela']),
  },
  {
    id: 'seguimiento',
    capa: 3,
    titulo: 'Seguimiento',
    nota: 'Pagado una sola vez, con su comprobante.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoHasta({ ...conFamilia(s), pedido: null }, 'pagado'), ['seguimiento']),
  },
  {
    id: 'c-pedidos',
    capa: 3,
    titulo: 'Comercio: pedidos del día',
    nota: 'Lo apartado sin pagar se ve solo como referencia opaca. El pedido pagado no lleva nombres ni dirección.',
    rol: 'comercio',
    preparar: (s) => pilaComercio(pedidoHasta({ ...conFamilia(s), pedido: null }, 'pagado'), ['c-pedidos']),
  },
  {
    id: 'c-preparar',
    capa: 3,
    titulo: 'Comercio: preparar',
    nota: 'El suplemento "ya no está": MATU lo busca en otro local.',
    rol: 'comercio',
    preparar: (s) => pilaComercio(pedidoHasta({ ...conFamilia(s), pedido: null }, 'preparando'), ['c-pedidos', 'c-preparar']),
  },
  {
    id: 'c-codigo',
    capa: 3,
    titulo: 'Comercio: código de retiro',
    nota: 'La farmacia ya no ingresa ningún monto: la familia pagó el total exacto antes.',
    rol: 'comercio',
    preparar: (s) => pilaComercio(pedidoHasta({ ...conFamilia(s), pedido: null }, 'listo'), ['c-pedidos', 'c-codigo']),
  },
  {
    id: 'cambio-local',
    capa: 3,
    titulo: 'Cambio de local',
    nota: 'Mismo producto en otro local: la familia paga lo mismo y MATU pone la diferencia. Reenvío simulado (fase 2).',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoHasta({ ...conFamilia(s), pedido: null }, 'listo'), ['seguimiento']),
  },
  {
    id: 'entregado',
    capa: 3,
    titulo: 'Entregado',
    nota: 'Cobrado = total que viste: el mismo monto del botón Pagar.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoHasta({ ...conFamilia(s), pedido: null }, 'entregado'), ['entregado']),
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
    id: 'total-vencido',
    capa: 4,
    titulo: 'El total venció',
    nota: 'Pasaron 15 minutos: se confirma de nuevo, sin costo. Mientras está vencido no hay botón de pago.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pasarMinutos(pedidoApartado(s), 16), ['se-acaba', 'reponer', 'pedido']),
  },
  {
    id: 'rechazado',
    capa: 4,
    titulo: 'El pago no pasó',
    nota: 'No se cobró nada; el pedido sigue apartado hasta que vence.',
    rol: 'familia',
    preparar: (s) => {
      const t = pedidoApartado(s)
      return pilaFamilia({ ...t, pedido: { ...t.pedido!, rechazos: t.pedido!.rechazos + 1 } }, ['reponer', 'pedido', 'rechazado'])
    },
  },
  {
    id: 'no-llego',
    capa: 4,
    titulo: 'Un producto no llegó',
    nota: 'Nadie lo tenía: se devuelve su precio el mismo día, a la misma tarjeta.',
    rol: 'familia',
    preparar: (s) => pilaFamilia(pedidoHasta({ ...conFamilia(s), pedido: null }, 'entregado', { nadieLoTiene: true }), ['entregado']),
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
  // El 200% es un interruptor del presentador, no de la escena: se mantiene al cambiar de escena
  // hasta que se apaga. La escena 35 solo lo enciende al entrar.
  const t = e.preparar({ ...s, aviso: null, conflicto: id === 'conflicto' ? s.conflicto : null })
  // La 35 muestra Inicio agrandado: sin esta marca, la franja la mostraba como la 6.
  const escenaFija = id === 'texto-200' ? { id, n: pantallaFamilia(t).n } : null
  return { ...t, rol: e.rol, escenaFija }
}

/** Qué escena corresponde a lo que se ve ahora, para marcarla en el panel. */
export function escenaActual(s: Estado): string | null {
  const f = s.escenaFija
  if (f && s.texto200 && s.rol === 'familia' && pantallaFamilia(s).n === f.n) return f.id
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
  const p = s.pedido
  if (id === 'pedido' && p && totalVencido(p, s.ahora)) return 'total-vencido'
  if (id === 'seguimiento' && p?.lineas.some((l) => l.reasignado)) return 'cambio-local'
  if (id === 'entregado' && p && devolucion(p) > 0) return 'no-llego'
  return mapa[id] ?? (ESCENAS.some((e) => e.id === id) ? id : null)
}

/** Escenas que usan la API real cuando el backend está conectado. El resto es simulado. */
export const ESCENAS_REALES = new Set(['cuenta', 'entrar', 'a-quien', 'permiso'])

export function reiniciar(): Estado {
  return estadoInicial()
}
