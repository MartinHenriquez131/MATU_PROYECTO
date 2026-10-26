// Transiciones puras del estado de la demo. Sin efectos: la URL del relevo se maneja
// en un efecto aparte (RelevoUrl), y nada se escribe en el almacenamiento del navegador.
import {
  BOLETA_EJEMPLO,
  CAMPOS,
  CODIGO_RETIRO,
  MONTO_REAL_EJEMPLO,
  EQUIVALENTES,
  PEDIDO_NUMERO,
  PIN_DEMO,
  SIN_STOCK,
  TEXTO_CAMPO,
  insumosIniciales,
  AVISO_CUIDADOR,
} from './datos'
import {
  DIA,
  MAX_INTENTOS_PIN,
  accesoVigente,
  finDeSemana,
  lineasLista,
  montoAPagar,
  nuevoPin,
  nuevoToken,
  totalEstimado,
} from './calculos'
import type {
  Acceso,
  Calidad,
  Campo,
  CampoId,
  Estado,
  EstadoPedido,
  Evento,
  Medio,
  Pantalla,
  PantallaComercioId,
  PantallaFamiliaId,
  Persona,
  Rol,
} from './tipos'

const campoVacio = (): Campo => ({ texto: '', version: 0, autor: '', minuto: null })

export function estadoInicial(rol: Rol = 'familia', tokenInicial: string | null = null): Estado {
  return {
    rol,
    nav: {
      familia: [{ id: 'bienvenida', n: 1 }],
      comercio: [{ id: 'c-pedidos', n: 2 }],
    },
    dir: 'adelante',
    ahora: 0,
    cuenta: null,
    persona: null,
    consentimiento: null,
    ficha: { su_dia: campoVacio(), si_se_altera: campoVacio(), a_quien_llamar: campoVacio() },
    borrador: null,
    conflicto: null,
    accesos: [],
    pinVisible: null,
    eventos: [],
    insumos: insumosIniciales().map((i) => ({ ...i, declarado: false })),
    ajustesLista: {},
    pedido: null,
    relevo: { token: tokenInicial, fase: tokenInicial ? 'no_disponible' : 'pin', pinErroneo: false, urlLimpia: false },
    texto200: false,
    escenaFija: null,
    aviso: null,
    seq: 10,
  }
}

// ---------- utilidades ----------

function sig(s: Estado): [number, Estado] {
  return [s.seq + 1, { ...s, seq: s.seq + 1 }]
}

export function avisar(s: Estado, texto: string): Estado {
  const [id, t] = sig(s)
  return { ...t, aviso: { id, texto } }
}

function avanzar(s: Estado, minutos: number): Estado {
  return { ...s, ahora: s.ahora + minutos }
}

function registrar(s: Estado, texto: string, tono: Evento['tono'] = 'normal', minuto = s.ahora): Estado {
  const [id, t] = sig(s)
  return { ...t, eventos: [{ id, minuto, texto, tono }, ...t.eventos].sort((a, b) => b.minuto - a.minuto) }
}

export function nombrePila(s: Estado): string {
  return s.persona?.nombrePila || 'María'
}

// ---------- navegación ----------

export function ir(s: Estado, id: PantallaFamiliaId | PantallaComercioId, p?: string): Estado {
  const [n, t] = sig(s)
  if (t.rol === 'comercio') {
    return { ...t, dir: 'adelante', nav: { ...t.nav, comercio: [...t.nav.comercio, { id: id as PantallaComercioId, p, n }] } }
  }
  return { ...t, dir: 'adelante', nav: { ...t.nav, familia: [...t.nav.familia, { id: id as PantallaFamiliaId, p, n }] } }
}

export function reemplazar(s: Estado, id: PantallaFamiliaId, p?: string): Estado {
  const [n, t] = sig(s)
  const pila = t.nav.familia.slice(0, -1)
  return { ...t, dir: 'adelante', nav: { ...t.nav, familia: [...pila, { id, p, n }] } }
}

export function volver(s: Estado): Estado {
  const clave = s.rol === 'comercio' ? 'comercio' : 'familia'
  const pila = s.nav[clave]
  if (pila.length <= 1) return s
  const t = { ...s, dir: 'atras' as const, nav: { ...s.nav, [clave]: pila.slice(0, -1) } }
  // Al salir de la pantalla del PIN, el PIN ya no se vuelve a mostrar.
  return pila[pila.length - 1].id === 'enlace-pin' ? { ...t, pinVisible: null } : t
}

/** Vuelve hasta la pantalla `indice` de la pila (0 es la raíz). */
export function volverHasta(s: Estado, indice: number): Estado {
  const clave = s.rol === 'comercio' ? 'comercio' : 'familia'
  const pila = s.nav[clave]
  if (indice < 0 || indice >= pila.length - 1) return s
  const sale = pila.slice(indice + 1)
  const t = { ...s, dir: 'atras' as const, nav: { ...s.nav, [clave]: pila.slice(0, indice + 1) } }
  return sale.some((x) => x.id === 'enlace-pin') ? { ...t, pinVisible: null } : t
}

/** Reemplaza la pila completa de la familia. */
export function pilaFamilia(s: Estado, ids: (PantallaFamiliaId | [PantallaFamiliaId, string])[]): Estado {
  let t = s
  const pila: Pantalla<PantallaFamiliaId>[] = []
  for (const x of ids) {
    const [n, u] = sig(t)
    t = u
    pila.push(Array.isArray(x) ? { id: x[0], p: x[1], n } : { id: x, n })
  }
  return { ...t, rol: 'familia', dir: 'adelante', pinVisible: null, nav: { ...t.nav, familia: pila } }
}

export function pilaComercio(s: Estado, ids: PantallaComercioId[]): Estado {
  let t = s
  const pila: Pantalla<PantallaComercioId>[] = []
  for (const id of ids) {
    const [n, u] = sig(t)
    t = u
    pila.push({ id, n })
  }
  return { ...t, rol: 'comercio', dir: 'adelante', nav: { ...t.nav, comercio: pila } }
}

export function pantallaFamilia(s: Estado): Pantalla<PantallaFamiliaId> {
  return s.nav.familia[s.nav.familia.length - 1]
}
export function pantallaComercio(s: Estado): Pantalla<PantallaComercioId> {
  return s.nav.comercio[s.nav.comercio.length - 1]
}

// ---------- alta ----------

export function crearCuenta(s: Estado, nombre: string, email: string, real: boolean): Estado {
  return ir(avanzar({ ...s, cuenta: { nombre, email, real } }, 1), 'a-quien')
}

/** Después de iniciar sesión: si el grupo ya tiene a la persona, al inicio; si no, al alta. */
export function entrar(s: Estado, email: string, nombre: string, real: boolean, persona: Persona | null, calidad: Calidad | null): Estado {
  let t: Estado = { ...s, cuenta: { nombre, email, real } }
  if (!persona) return pilaFamilia(t, ['bienvenida', 'a-quien'])
  t = { ...t, persona }
  if (calidad) {
    t = {
      ...t,
      consentimiento: {
        calidad,
        referenciaDocumento: '',
        avisoId: calidad === 'cuidador_de_hecho' ? AVISO_CUIDADOR.id : null,
        avisoVersion: calidad === 'cuidador_de_hecho' ? AVISO_CUIDADOR.version : null,
        minuto: s.ahora,
        revisionMinuto: calidad === 'cuidador_de_hecho' ? s.ahora + 365 * DIA : null,
      },
    }
  }
  return avisar(pilaFamilia(conFamilia(t), ['inicio']), `Hola de nuevo. Encontramos a ${persona.nombrePila}.`)
}

export function guardarPersona(s: Estado, persona: Persona): Estado {
  return ir({ ...s, persona }, 'permiso')
}

export function darPermiso(s: Estado, calidad: Calidad, referenciaDocumento: string): Estado {
  const esCuidador = calidad === 'cuidador_de_hecho'
  // La persona y su consentimiento se guardan juntos, o no se guarda nada (MATU-07).
  let t: Estado = {
    ...s,
    consentimiento: {
      calidad,
      referenciaDocumento,
      avisoId: esCuidador ? AVISO_CUIDADOR.id : null,
      avisoVersion: esCuidador ? AVISO_CUIDADOR.version : null,
      minuto: s.ahora,
      revisionMinuto: esCuidador ? s.ahora + 365 * DIA : null,
    },
  }
  t = avanzar(t, 1)
  t = pilaFamilia(t, ['inicio'])
  return avisar(t, `Permiso registrado. ${nombrePila(t)} ya está en MATU.`)
}

/** La persona cuidada del ejemplo: María, con dirección para el pedido. */
export function personaEjemplo(): Persona {
  return {
    nombre: 'María Soto',
    nombrePila: 'María',
    apoyo: 'apoyo_parcial',
    direccion: 'Los Aromos 123, La Reina',
    partes: { calle: 'Los Aromos', numero: '123', comuna: 'La Reina' },
    idReal: null,
  }
}

/** Datos de una familia que ya usa MATU: para "Ya tengo cuenta" y para saltar escenas. */
export function conFamilia(s: Estado): Estado {
  let t = s
  if (!t.cuenta) t = { ...t, cuenta: { nombre: 'Carmen', email: 'carmen@correo.ejemplo', real: false } }
  if (!t.persona) t = { ...t, persona: personaEjemplo() }
  if (!t.consentimiento) {
    t = {
      ...t,
      consentimiento: {
        calidad: 'cuidador_de_hecho',
        referenciaDocumento: '',
        avisoId: AVISO_CUIDADOR.id,
        avisoVersion: AVISO_CUIDADOR.version,
        minuto: -20 * DIA,
        revisionMinuto: 345 * DIA,
      },
    }
    // Historia previa: un enlace del fin de semana pasado, que ya venció.
    if (t.accesos.length === 0) {
      t = {
        ...t,
        accesos: [
          {
            id: 'acc-previo',
            token: nuevoToken(),
            pin: nuevoPin(),
            nombre: 'Rosa',
            telefono: '+56 9 8765 4321',
            campos: ['su_dia', 'si_se_altera'],
            motivo: 'Fin de semana fuera',
            creadoMin: -9860,
            venceMin: -6621,
            estado: 'activo',
            intentosFallidos: 0,
          },
        ],
      }
      t = registrar(t, 'Rosa abrió la ficha', 'normal', -8895)
      t = registrar(t, 'Venció el enlace del fin de semana', 'normal', -6621)
    }
  }
  if (!t.ficha.su_dia.texto) {
    t = {
      ...t,
      ficha: { ...t.ficha, su_dia: { texto: TEXTO_CAMPO.su_dia.dictado, version: 1, autor: 'Carmen', minuto: -2 * DIA } },
    }
  }
  if (!t.insumos.some((i) => i.declarado)) t = { ...t, insumos: insumosIniciales(), ajustesLista: {} }
  return t
}

// ---------- ficha ----------

export function completados(s: Estado): number {
  return CAMPOS.filter((c) => s.ficha[c].texto.trim()).length
}

export function siguienteCampoVacio(s: Estado): CampoId | null {
  return CAMPOS.find((c) => !s.ficha[c].texto.trim()) ?? null
}

export function abrirCampo(s: Estado, campo: CampoId): Estado {
  const actual = s.ficha[campo]
  return ir({ ...s, borrador: { campo, texto: actual.texto, versionBase: actual.version } }, 'completar', campo)
}

export function escribir(s: Estado, texto: string): Estado {
  return s.borrador ? { ...s, borrador: { ...s.borrador, texto } } : s
}

export function guardarCampo(s: Estado): Estado {
  const b = s.borrador
  if (!b) return s
  const actual = s.ficha[b.campo]
  // Como un If-Match: si alguien escribió después de que abrí el campo, no piso nada.
  if (actual.version !== b.versionBase) {
    return reemplazar({ ...s, conflicto: { campo: b.campo, suyo: actual, mio: b.texto } }, 'conflicto')
  }
  const t = avanzar(
    {
      ...s,
      borrador: null,
      ficha: { ...s.ficha, [b.campo]: { texto: b.texto.trim(), version: actual.version + 1, autor: 'Carmen', minuto: s.ahora } },
    },
    1,
  )
  return reemplazar(t, 'guardado', b.campo)
}

/** Rodrigo guarda el mismo campo mientras Carmen escribe. */
export function rodrigoEdita(s: Estado, campo: CampoId, texto: string): Estado {
  const actual = s.ficha[campo]
  return avanzar(
    { ...s, ficha: { ...s.ficha, [campo]: { texto, version: actual.version + 1, autor: 'Rodrigo', minuto: s.ahora } } },
    1,
  )
}

export function resolverConflicto(s: Estado, dejar: 'suyo' | 'mio'): Estado {
  const c = s.conflicto
  if (!c) return s
  let t: Estado = { ...s, conflicto: null, borrador: null }
  if (dejar === 'mio') {
    const actual = t.ficha[c.campo]
    t = { ...t, ficha: { ...t.ficha, [c.campo]: { texto: c.mio.trim(), version: actual.version + 1, autor: 'Carmen', minuto: t.ahora } } }
  }
  t = reemplazar(avanzar(t, 1), 'guardado', c.campo)
  return avisar(t, dejar === 'mio' ? 'Dejaste tu versión.' : `Dejaste la versión de ${c.suyo.autor}.`)
}

// ---------- compartir ----------

export interface DatosCompartir {
  nombre: string
  telefono: string
  campos: CampoId[]
  vigencia: '24h' | 'finde' | 'dias'
  dias: number
  motivo: string
}

export function crearAcceso(s: Estado, d: DatosCompartir, pinFijo?: string): Estado {
  const vence =
    d.vigencia === '24h' ? s.ahora + DIA : d.vigencia === 'finde' ? finDeSemana(s.ahora) : s.ahora + Math.min(30, Math.max(1, d.dias)) * DIA
  const [n, t0] = sig(s)
  const acceso: Acceso = {
    id: `acc-${n}`,
    token: nuevoToken(),
    pin: pinFijo ?? nuevoPin(),
    nombre: d.nombre.trim() || 'Rosa',
    telefono: d.telefono,
    campos: d.campos,
    motivo: d.motivo,
    creadoMin: s.ahora,
    venceMin: vence,
    estado: 'activo',
    intentosFallidos: 0,
  }
  let t: Estado = { ...t0, accesos: [acceso, ...t0.accesos], pinVisible: acceso.id }
  t = registrar(t, `Creaste un enlace para ${acceso.nombre}`)
  return avanzar(t, 2)
}

export function cortarAcceso(s: Estado, id: string): Estado {
  const a = s.accesos.find((x) => x.id === id)
  if (!a) return s
  let t: Estado = { ...s, accesos: s.accesos.map((x) => (x.id === id ? { ...x, estado: 'revocado' as const } : x)) }
  t = registrar(t, `Cortaste el enlace de ${a.nombre}`)
  return avisar(avanzar(t, 1), `Enlace cortado. Ya no abre para ${a.nombre}.`)
}

export function accesoPorDefecto(s: Estado): Estado {
  return crearAcceso(
    s,
    { nombre: 'Rosa', telefono: '+56 9 8765 4321', campos: [...CAMPOS], vigencia: '24h', dias: 1, motivo: 'Salgo unas horas' },
    PIN_DEMO,
  )
}

export function ultimoAcceso(s: Estado): Acceso | null {
  return s.accesos.find((a) => a.id !== 'acc-previo') ?? null
}

// ---------- relevo ----------

export function abrirRelevo(s: Estado, accesoId?: string): Estado {
  let t = conFamilia(s)
  let a = accesoId ? t.accesos.find((x) => x.id === accesoId) : ultimoAcceso(t)
  if (!a) {
    t = { ...accesoPorDefecto(t), pinVisible: null }
    a = ultimoAcceso(t)!
  }
  return {
    ...t,
    rol: 'relevo',
    pinVisible: null,
    relevo: { token: a.token, fase: 'pin', pinErroneo: false, urlLimpia: false },
  }
}

export function accesoDelRelevo(s: Estado): Acceso | null {
  return s.accesos.find((a) => a.token === s.relevo.token) ?? null
}

export function canjear(s: Estado, token: string | null, pin: string): Estado {
  const a = s.accesos.find((x) => x.token === token)
  if (!a || !accesoVigente(a, s.ahora)) {
    return { ...s, relevo: { ...s.relevo, fase: 'no_disponible', pinErroneo: false } }
  }
  if (pin === a.pin) {
    let t: Estado = {
      ...s,
      accesos: s.accesos.map((x) => (x.id === a.id ? { ...x, intentosFallidos: 0 } : x)),
      relevo: { ...s.relevo, fase: 'ficha', pinErroneo: false, urlLimpia: true },
    }
    t = registrar(t, `${a.nombre} abrió la ficha`)
    return avanzar(t, 1)
  }
  const intentos = a.intentosFallidos + 1
  const bloqueado = intentos >= MAX_INTENTOS_PIN
  let t: Estado = {
    ...s,
    accesos: s.accesos.map((x) =>
      x.id === a.id ? { ...x, intentosFallidos: intentos, estado: bloqueado ? ('bloqueado' as const) : x.estado } : x,
    ),
    relevo: { ...s.relevo, fase: bloqueado ? 'no_disponible' : 'pin', pinErroneo: !bloqueado },
  }
  t = registrar(t, `${a.nombre} escribió mal el PIN`, 'atento')
  if (bloqueado) t = registrar(t, `El enlace de ${a.nombre} se bloqueó por PIN incorrecto`, 'atento')
  return t
}

/** El relevo vuelve a consultar: si lo cortaron o venció, ya no ve la ficha. */
export function relevoRevalida(s: Estado): Estado {
  const a = accesoDelRelevo(s)
  if (s.relevo.fase === 'ficha' && (!a || !accesoVigente(a, s.ahora))) {
    return { ...s, relevo: { ...s.relevo, fase: 'no_disponible' } }
  }
  return s
}

// ---------- consumo ----------

export function declarar(s: Estado, id: string, porDia: number, quedan: number): Estado {
  const t: Estado = {
    ...s,
    insumos: s.insumos.map((i) => (i.id === id ? { ...i, porDia, quedan, declarado: true } : i)),
    ajustesLista: {},
  }
  return avisar(avanzar(t, 1), 'Consumo guardado. La fecha se recalculó.')
}

export function yaLoCompre(s: Estado, id: string, paquetes: number): Estado {
  const t: Estado = {
    ...s,
    insumos: s.insumos.map((i) => (i.id === id ? { ...i, quedan: i.quedan + paquetes * i.tamanoPaquete } : i)),
    ajustesLista: {},
  }
  return avisar(avanzar(t, 1), 'Compra anotada. La fecha se recalculó.')
}

export function ajustarLista(s: Estado, id: string, paquetes: number): Estado {
  return { ...s, ajustesLista: { ...s.ajustesLista, [id]: Math.max(0, Math.min(20, paquetes)) } }
}

export function vaciarInsumos(s: Estado): Estado {
  return { ...s, insumos: s.insumos.map((i) => ({ ...i, declarado: false })), ajustesLista: {} }
}

// ---------- pedido ----------

const ORDEN: EstadoPedido[] = ['borrador', 'pagado', 'preparando', 'listo', 'en_camino', 'entregado']
export const etapa = (e: EstadoPedido) => ORDEN.indexOf(e)

export function armarPedido(s: Estado): Estado {
  const lineas = lineasLista(s.insumos, s.ajustesLista).filter((l) => l.paquetes > 0)
  const estimado = totalEstimado(lineas)
  return {
    ...s,
    pedido: {
      numero: PEDIDO_NUMERO,
      lineas: lineas.map((l) => ({
        insumoId: l.insumo.id,
        nombre: `${l.insumo.nombre} ${l.insumo.presentacion}`,
        paquetes: l.paquetes,
        precio: l.insumo.precio,
        resolucion: 'ok',
        reemplazo: null,
      })),
      estimado,
      aceptaEquivalente: true,
      direccion: s.persona?.direccion ?? '',
      medio: null,
      montoPagado: 0,
      montoReal: null,
      boleta: '',
      estado: 'borrador',
      codigoRetiro: CODIGO_RETIRO,
      hitos: {},
      rechazos: 0,
      sumadoAlStock: false,
    },
  }
}

export function datosPedido(s: Estado, direccion: string, aceptaEquivalente: boolean): Estado {
  if (!s.pedido) return s
  const persona = s.persona && !s.persona.direccion ? { ...s.persona, direccion } : s.persona
  return { ...s, persona, pedido: { ...s.pedido, direccion, aceptaEquivalente } }
}

export function elegirMedio(s: Estado, medio: Medio): Estado {
  if (!s.pedido) return s
  return { ...s, pedido: { ...s.pedido, medio, montoPagado: montoAPagar(s.pedido.estimado, medio) } }
}

export function resultadoPago(s: Estado, aprobado: boolean): Estado {
  const p = s.pedido
  if (!p || !p.medio) return s
  if (!aprobado) return { ...s, pedido: { ...p, rechazos: p.rechazos + 1 } }
  const lineas = p.lineas.map((l) => (SIN_STOCK.has(l.insumoId) ? { ...l, resolucion: 'sin_stock' as const } : l))
  return avanzar({ ...s, pedido: { ...p, lineas, estado: 'pagado', hitos: { pagado: s.ahora } } }, 3)
}

export function empezarPreparacion(s: Estado): Estado {
  const p = s.pedido
  if (!p || p.estado !== 'pagado') return s
  return avanzar({ ...s, pedido: { ...p, estado: 'preparando', hitos: { ...p.hitos, preparando: s.ahora } } }, 4)
}

export function resolverLinea(s: Estado, insumoId: string, como: 'reemplazado' | 'no_disponible'): Estado {
  const p = s.pedido
  if (!p) return s
  const lineas = p.lineas.map((l) =>
    l.insumoId === insumoId
      ? { ...l, resolucion: como, reemplazo: como === 'reemplazado' ? (EQUIVALENTES[insumoId] ?? null) : null }
      : l,
  )
  return { ...s, pedido: { ...p, lineas } }
}

export function cerrarMonto(s: Estado, montoReal: number, boleta: string): Estado {
  const p = s.pedido
  if (!p) return s
  let t: Estado = {
    ...s,
    pedido: { ...p, montoReal, boleta, estado: 'listo', hitos: { ...p.hitos, listo: s.ahora } },
  }
  t = avanzar(t, 12)
  return t
}

export function validarCodigo(s: Estado): Estado {
  const p = s.pedido
  if (!p) return s
  return avanzar({ ...s, pedido: { ...p, estado: 'en_camino', hitos: { ...p.hitos, en_camino: s.ahora } } }, 25)
}

export function marcarEntregado(s: Estado): Estado {
  const p = s.pedido
  if (!p || p.estado !== 'en_camino') return s
  let t: Estado = { ...s, pedido: { ...p, estado: 'entregado', hitos: { ...p.hitos, entregado: s.ahora } } }
  // Lo que llegó se suma solo a la cuenta de insumos: las capas 2 y 3 conversan.
  const llegado = new Map(p.lineas.filter((l) => l.resolucion !== 'no_disponible').map((l) => [l.insumoId, l.paquetes]))
  t = {
    ...t,
    insumos: t.insumos.map((i) => (llegado.has(i.id) ? { ...i, quedan: i.quedan + llegado.get(i.id)! * i.tamanoPaquete } : i)),
    ajustesLista: {},
    pedido: { ...t.pedido!, sumadoAlStock: true },
  }
  return avanzar(t, 1)
}

/** Lleva el pedido hasta la etapa pedida con los valores de la prueba real. */
export function pedidoHasta(s: Estado, objetivo: EstadoPedido, medio: Medio = 'credito'): Estado {
  let t = conFamilia(s)
  if (!t.pedido || etapa(t.pedido.estado) > etapa(objetivo) || (t.pedido.estado === 'borrador' && t.pedido.lineas.length === 0)) {
    // Un pedido nuevo para una escena parte siempre de los insumos del ejemplo: estimado de
    // $60.000, reserva de $69.000 y cobro de $51.340. Antes se armaba con el stock del momento,
    // y después de una entrega (que suma al stock) salía otro monto y el real superaba el tope.
    t = armarPedido({ ...t, insumos: insumosIniciales(), ajustesLista: {} })
  }
  const pasos: [EstadoPedido, (x: Estado) => Estado][] = [
    ['pagado', (x) => resultadoPago(x.pedido?.medio ? x : elegirMedio(x, medio), true)],
    ['preparando', empezarPreparacion],
    [
      'listo',
      (x) => {
        let y = x
        for (const l of x.pedido!.lineas) if (l.resolucion === 'sin_stock') y = resolverLinea(y, l.insumoId, 'reemplazado')
        return cerrarMonto(y, MONTO_REAL_EJEMPLO, BOLETA_EJEMPLO)
      },
    ],
    ['en_camino', validarCodigo],
    ['entregado', marcarEntregado],
  ]
  for (const [e, paso] of pasos) {
    if (etapa(t.pedido!.estado) < etapa(e) && etapa(e) <= etapa(objetivo)) t = paso(t)
  }
  return t
}
