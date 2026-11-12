// Textos de MATU-54, «Datos de {nombre}» y «Tus datos» (especificación docs/diseno/matu-54-mis-datos.md
// v1.1). Las marcas siguen a la especificación: [L n] ya está en lenguaje.md; [ANALISTA] viene de la
// revisión previa (sección 7) y entra a lenguaje.md 35; [ANALISTA, ajustado] lo cambió la
// especificación; [NUEVO] lo propone la especificación. Nunca «exportar», «auditoría», «registro de
// accesos», «consentimiento», «sesión», «token» ni «usuario».
import type {
  AutorizacionCopia,
  AvisoEnviadoCopia,
  AvisoInsumoCopia,
  CompraCopia,
  DevolucionCopia,
  EnlaceRelevoCopia,
  EstadoPedidoCopia,
  FinalidadCopia,
  PagoCuentaCopia,
  TipoHecho,
} from '../compartido/api/misDatos'
import { miles } from './textoLista'
import { GRUPO_FAMILIAR } from './textosGrupo'
import { GRUPO_PEDIDOS } from './textosPedido'

/** Frases de una fecha: `[antes, después]`, la fecha va en medio, en su `cifras`. */
type Partes = readonly [string, string]

export const MIS_DATOS = {
  // ------------------------------------------------ títulos de pestaña (C26), sin nombres [NUEVO]
  pestanaPersona: 'Datos guardados',
  pestanaCuenta: 'Tus datos',

  // ------------------------------------------------ 2. la entrada en Grupo familiar
  titulo: (pila: string) => `Datos de ${pila}`, // [ANALISTA]
  entradaTexto: (pila: string) => `Todo lo que MATU guarda de ${pila}. Si ${pila} o su representante legal te lo pide, puedes mostrárselo o darle una copia.`, // [ANALISTA]
  entradaBoton: (pila: string) => `Ver los datos de ${pila}`, // [ANALISTA]
  entradaQuienPuede: (pila: string) => `Los puede ver quien administra el grupo o quien cuida a ${pila}.`, // [ANALISTA]

  // ------------------------------------------------ 3. la página
  volverAGrupo: 'Volver a Grupo familiar', // [L 22]
  /** «Lo que MATU guarda hoy de María, al 12/11/2026 a las 10:14.» [NUEVO] */
  bajadaPersona: (pila: string) => [`Lo que MATU guarda hoy de ${pila}, al `, ' a las ', '.'] as const,

  // panel de descarga (3.7)
  ayudaArchivo: 'Es un archivo (JSON) que otro programa puede leer, para llevar estos datos a otro lugar.', // [ANALISTA]
  ayudaNoventa: 'En esta pantalla, los historiales muestran los últimos 90 días. El archivo trae todo lo guardado.', // [NUEVO]
  descargarEnArchivo: 'Descargar en un archivo', // [ANALISTA]
  entregado: 'Te entregamos el archivo. Búscalo en tus descargas.', // [ANALISTA, ajustado: sin «de tu teléfono»]

  // el diálogo
  dialogoTitulo: 'Antes de descargar', // [ANALISTA]
  dialogoPersona:
    'El archivo trae todo lo de esta pantalla, también lo escrito en la ficha y los nombres y teléfonos de «A quién llamar». Queda en tu teléfono o computador, fuera de MATU: no vence, no se puede cortar y MATU no lo puede borrar.', // [ANALISTA, ajustado: «o computador»]
  /** Con la ficha que no está `disponible` (3.7): no promete lo escrito. */
  dialogoPersonaSinFicha:
    'El archivo trae todo lo de esta pantalla, y lo anterior a 90 días. Queda en tu teléfono o computador, fuera de MATU: no vence, no se puede cortar y MATU no lo puede borrar.', // [NUEVO] la primera oración
  dialogoRelevo: 'No lo uses para compartir la ficha con un relevo: para eso está el enlace con PIN.', // [ANALISTA]
  dialogoCuenta: 'El archivo trae tu correo y tu celular completos. Queda en tu teléfono o computador, fuera de MATU.', // [ANALISTA, ajustado: «o computador»]
  descargar: 'Descargar', // [ANALISTA]
  noDescargar: 'No descargar', // [ANALISTA]
  errArchivo: 'No pudimos armar el archivo en este navegador. Prueba en otro navegador o en un computador.', // [NUEVO]

  // estados de la página (3.6)
  errCarga: 'No pudimos traer los datos. Revisa tu conexión y vuelve a intentarlo.', // [ANALISTA]
  errNoDisponible: 'No pudimos traer los datos en este momento. Vuelve a intentarlo en unos minutos.', // [NUEVO]
  /** 429 con `Retry-After`: «… a las {HH:MM}.» [ANALISTA, ajustado] */
  tope: ['Ya pediste los datos varias veces. Vuelve a intentarlo a las ', '.'] as Partes,
  topeSinHora: 'Ya pediste los datos varias veces. Vuelve a intentarlo en una hora.', // [ANALISTA]

  // frases de los historiales (3.4.9)
  noventaConMas: 'Los de los últimos 90 días. Lo anterior va en el archivo.', // [NUEVO]
  noventaSinMas: 'Los de los últimos 90 días.', // [NUEVO]
  verMas: 'Ver más', // [aprobado 03-11, INSUMOS.verMas]

  // ------------------------------------------------ 3.4 los bloques de la persona
  bloques: {
    persona: 'Sus datos', // [ANALISTA]
    autorizaciones: 'Autoriza­ciones', // [ANALISTA], 1.3: con guion suave (P2-1)
    ficha: 'Su ficha', // [ANALISTA]
    enlaces: 'Enlaces de relevo', // [ANALISTA]
    insumos: 'Sus insumos', // [ANALISTA]
    compras: 'Compras anotadas (últimos 90 días)', // [ANALISTA]
    avisosInsumos: 'Avisos de insumos', // [ANALISTA]
    pedidos: 'Sus pedidos', // [ANALISTA, D-54-14]
    historial: 'Quién abrió o editó la ficha', // [ANALISTA]
  },

  // 3.4.1 Sus datos
  nombre: 'Nombre', // [NUEVO]
  leDicen: 'Le dicen', // [NUEVO, de L 25.3]
  apoyo: 'Cuánto apoyo necesita', // [NUEVO, de L 25.3]
  direccion: 'Dirección', // [NUEVO]
  referencia: (r: string) => `Referencia: ${r}`, // [NUEVO]
  sinDireccion: 'Sin dirección.', // [NUEVO]
  enMatuDesde: 'En MATU desde', // [NUEVO]
  /** «Si algo está mal, escribe a {correo} desde el correo de tu cuenta.» [NUEVO, P8] */
  rectificar: ['Si algo está mal, escribe a ', ' desde el correo de tu cuenta.'] as Partes,

  // 3.4.2 Autorizaciones
  sinAutorizaciones: 'Todavía no hay autorizaciones.', // [NUEVO]
  /** El título del bloque de MATU-44 según `finalidad` [L 22]. */
  finalidad: {
    plan_cuidado: GRUPO_FAMILIAR.tituloFicha,
    consumo: GRUPO_FAMILIAR.tituloInsumos,
    despacho: GRUPO_PEDIDOS.titulo,
  } as Record<FinalidadCopia, string>,
  estadoAutorizacion: {
    vigente: 'Vigente', // [L 22]
    revision_vencida: 'En pausa', // [L 22]
    retirada: 'Retirada', // [L 22]
    reemplazada: 'Se renovó', // [NUEVO]
  } as Record<AutorizacionCopia['estado'], string>,
  /** Las calidades de L 25.4, en tercera persona [NUEVO]. */
  laDa: (calidad: AutorizacionCopia['calidad_otorgante'], pila: string) =>
    calidad === 'titular' ? `La da ${pila}, por su cuenta.` : calidad === 'representante_legal' ? 'La da su representante legal.' : 'La da quien la cuida, sin ser su representante legal.',
  laRegistro: (nombre: string) => [`La registró ${nombre} el `, '.'] as const, // [NUEVO]
  hayQueRenovar: ['Hay que renovarla el ', '.'] as Partes, // [NUEVO]
  habiaQueRenovar: ['Había que renovarla el ', '.'] as Partes, // [NUEVO]
  seRetiro: ['Se retiró el ', '.'] as Partes, // [NUEVO]
  seRenovo: ['Se renovó el ', '.'] as Partes, // [NUEVO]
  loAceptado: 'Lo que se aceptó: ', // [NUEVO]
  politicaVersion: 'política de privacidad ', // [NUEVO]
  declaracionVersion: 'declaración ', // [NUEVO]
  avisoVersion: 'aviso ', // [NUEVO]
  /** [ANALISTA, ajustado: el correo sale de la política] */
  documentoRepresentante: ['Hay una referencia al documento del representante legal. Si la necesitas, pídela a ', '.'] as Partes,
  documentoRepresentanteSinCorreo: 'Hay una referencia al documento del representante legal.',

  // 3.5 la nota que reemplaza a la ficha o a los insumos
  estadoFicha: {
    /** «…, y se borra el {borrado_el}.» [ANALISTA]; sin fecha, se omite esa parte. */
    retirada: ['La autorización de la ficha está retirada. Lo escrito sigue guardado sin que nadie lo pueda leer, y se borra el ', '.'] as Partes,
    retiradaSinFecha: 'La autorización de la ficha está retirada. Lo escrito sigue guardado sin que nadie lo pueda leer.',
    en_pausa: 'La ficha está en pausa porque falta renovar la autorización. Cuando se renueve, vuelve a aparecer aquí.', // [ANALISTA]
    borrada: 'La autorización de la ficha se retiró, y lo escrito ya se borró.', // [NUEVO]
    sin_autorizar: (pila: string) => `Nadie ha autorizado todavía guardar la ficha de ${pila}.`, // [NUEVO]
  },
  estadoInsumos: {
    retirada: ['La autorización de los insumos está retirada. Lo anotado se borra el ', '.'] as Partes, // [ANALISTA]
    retiradaSinFecha: 'La autorización de los insumos está retirada.',
    en_pausa: 'Los insumos están en pausa porque falta renovar la autorización. Cuando se renueve, vuelven a aparecer aquí.', // [NUEVO]
    borrada: 'La autorización de los insumos se retiró, y lo anotado ya se borró.', // [NUEVO]
    sin_autorizar: (pila: string) => `Nadie ha autorizado todavía calcular los insumos de ${pila}.`, // [NUEVO]
  },

  // 3.4.3 Su ficha
  loEscribio: (nombre: string) => [`Lo escribió ${nombre} el `, '.'] as const, // [NUEVO]
  sinEscribir: 'Sin escribir.', // [NUEVO]

  // 3.4.4 Enlaces de relevo
  sinTelefonoRelevos: 'No incluimos el teléfono de los relevos.', // [ANALISTA, ajustado]
  sinEnlaces: 'Todavía no hay enlaces de relevo.', // [NUEVO]
  estadoEnlace: {
    vigente: 'Vigente', // [NUEVO]
    vencido: 'Vencido', // [L 9]
    revocado: 'Cortado', // [L 9]
    bloqueado: 'Bloqueado', // [L 9]
  } as Record<EnlaceRelevoCopia['estado'], string>,
  ve: 'Ve: ', // [NUEVO]
  loCompartio: (nombre: string) => [`Lo compartió ${nombre} el `, '.'] as const, // [NUEVO]
  vence: ['Vence el ', '.'] as Partes, // [NUEVO]
  vencio: ['Venció el ', '.'] as Partes, // [NUEVO]
  seCorto: ['Se cortó el ', '.'] as Partes, // [NUEVO]
  noSeAbrio: 'No se ha abierto.', // [NUEVO]
  seAbrioUna: ['Se abrió una vez, el ', '.'] as Partes, // [NUEVO]
  seAbrioVeces: (n: number) => [`Se abrió ${n} veces. La última, el `, '.'] as const, // [NUEVO]

  // 3.4.5 Sus insumos (las de «Usa…» y «Quedaban…» son de INSUMOS, L 21)
  sinInsumos: 'Todavía no hay insumos.', // [NUEVO]
  seAcaba: ['Se acaba el ', '.'] as Partes, // [NUEVO]
  avisa: (n: number) => (n === 0 ? 'Avisa el mismo día.' : `Avisa ${n} ${n === 1 ? 'día' : 'días'} antes.`), // [NUEVO]
  porEnvase: (n: number) => `${n} por envase.`, // [NUEVO]
  loAgregaron: ['Lo agregaron el ', '.'] as Partes, // [NUEVO]
  loCambio: (nombre: string) => [` Lo cambió por última vez ${nombre} el `, '.'] as const, // [NUEVO]
  yaNoSeSigue: 'Ya no se sigue', // [NUEVO]

  // 3.4.6 Compras anotadas
  sinCompras: 'No hay compras anotadas en los últimos 90 días.', // [NUEVO]
  /** 1.3 (decisión 403): las de un pedido de MATU quedan más de 90 días y van en el archivo. [NUEVO] */
  comprasAnteriores: 'Lo anterior va en el archivo.',
  /** (1.2) «{unidades} {unidad} de {insumo}» [NUEVO], con la unidad de la compra (decisión 386) en las palabras de L 21. */
  compra: (n: number, unidad: CompraCopia['unidad'], insumo: string) => {
    const palabra = unidad === 'sobre' ? (n === 1 ? 'sobre' : 'sobres') : unidad === 'ml' ? 'ml' : unidad === 'g' ? 'g' : n === 1 ? 'unidad' : 'unidades'
    // Espacio duro entre la cifra y su unidad: al cortar la línea no quedan separadas.
    return `${miles(n)} ${palabra} de ${insumo}`
  },
  anoto: (nombre: string) => ` · Anotó ${nombre}`, // [NUEVO]
  llegoConPedido: ' · Llegó con un pedido de MATU', // [NUEVO]
  el: 'El ', // [NUEVO]

  // 3.4.7 Avisos de insumos
  sinAvisosInsumos: 'No hay avisos en los últimos 90 días.', // [NUEVO]
  seAcabaInsumo: (insumo: string) => [`${insumo}: se acaba el `, '.'] as const, // [NUEVO]
  estadoAvisoInsumo: {
    pendiente: 'Todavía no se avisa.', // [NUEVO]
    notificada: ['Se avisó el ', '.'] as Partes, // [NUEVO]
    resuelta: ['Se resolvió el ', '.'] as Partes, // [NUEVO]
    descartada: ['Se descartó el ', '.'] as Partes, // [NUEVO]
  } satisfies Record<AvisoInsumoCopia['estado'], string | Partes>,

  // 3.4.8 Sus pedidos
  sinPedidos: 'No hay pedidos.', // [NUEVO]
  pedido: (referencia: string) => `Pedido ${referencia}`, // [NUEVO]
  pedidoDel: 'Pedido del ', // [NUEVO] + fecha
  loArmaron: ['Lo armaron el ', '.'] as Partes, // [NUEVO]
  enComercio: (comercio: string) => `En ${comercio}`, // [NUEVO]
  siFalta: (que: string) => ` · Si falta: ${que}`, // [NUEVO]
  productos: 'Productos', // [NUEVO]
  envio: 'Envío', // [L 27]
  total: 'Total', // [L 27]
  sinPagar: 'Sin pagar.', // [NUEVO]
  pagoEnCurso: 'El pago está en curso.', // [NUEVO]
  loPago: (nombre: string) => [`Lo pagó ${nombre} el `, '.'] as const, // [NUEVO]
  cobrado: 'Cobrado: ', // [NUEVO]
  devuelto: 'Devuelto: ', // [NUEVO]
  noAprobado: 'El pago no se aprobó.', // [NUEVO]
  anulado: 'Se devolvió todo el pago: ', // [NUEVO] + monto + «.»
  pagoDePrueba: 'Pago de prueba: no se cobró dinero real.', // [NUEVO, el rótulo de la pasarela]
  entrega: 'Entrega: ', // [NUEVO]
  estadoPedido: {
    borrador: 'Sin confirmar',
    total_confirmado: 'Por pagar',
    vencido: 'Venció sin pagar',
    pagado: 'Pagado', // [textosPago]
    enviado_a_comercio: 'En preparación',
    preparando: 'En preparación',
    listo_retiro: 'Por despachar',
    asignado: 'Por despachar',
    sin_repartidor: 'Por despachar',
    retirado: 'Por despachar',
    en_ruta: 'En camino',
    entregado: 'Entregado',
    cerrado: 'Entregado',
    no_entregado: 'No se entregó',
    reprogramado: 'Reprogramado',
    cancelado: 'Cancelado',
    cancelado_con_devolucion: 'Cancelado',
  } as Record<EstadoPedidoCopia, string>, // [NUEVO] salvo «Pagado»
  /** «Se devolvieron {monto} porque…» o, en curso, «Se están devolviendo…» [NUEVO] */
  devolucion: (d: DevolucionCopia) => {
    const verbo = d.estado === 'en_curso' ? 'Se están devolviendo ' : 'Se devolvieron '
    const porque =
      d.motivo === 'producto_no_entregado'
        ? d.producto
          ? ` porque no se pudo entregar ${d.producto}.`
          : ' porque no se pudo entregar un producto.'
        : d.motivo === 'pago_tardio'
          ? ' porque el pago llegó cuando el total ya había vencido.'
          : ' porque se canceló el pedido.'
    return [verbo, porque] as const
  },

  // 3.4.9 Quién abrió o editó la ficha
  sinHechos: 'No hay cambios en los últimos 90 días.', // [NUEVO]
  loTuyo: 'Aquí ves solo lo que hiciste tú. La lista completa la ve quien administra el grupo.', // [ANALISTA]
  /** [ANALISTA, ajustado: «ni en el archivo»] */
  sinAsociar: ['Hay cambios antiguos que no podemos mostrar aquí ni en el archivo. Si los necesitas, pídelos a ', '.'] as Partes,
  sinAsociarSinCorreo: 'Hay cambios antiguos que no podemos mostrar aquí ni en el archivo.',
  aLas: 'a las',
  /** MATU-53 5.7: quien salió del grupo, dentro de una oración o al comenzarla. */
  yaNoEsta: 'alguien que ya no está en el grupo',
  yaNoEstaMayuscula: 'Alguien que ya no está en el grupo',

  // ------------------------------------------------ 4. la entrada en «Tu cuenta»
  cuentaTitulo: 'Tus datos', // [ANALISTA]
  cuentaBajada: 'Ver y descargar lo que MATU guarda de tu cuenta.', // [ANALISTA]
  cuentaBoton: 'Ver tus datos', // [NUEVO]

  // ------------------------------------------------ 5. «Tus datos»
  bajadaCuenta: ['Lo que MATU guarda hoy de tu cuenta, al ', ' a las ', '.'] as const, // [NUEVO]
  volverACuenta: 'Volver a tu cuenta', // [MATU-55]
  personasEnGrupo: 'Lo que guardamos de las personas que cuidas lo ves en Grupo familiar.', // [ANALISTA]
  irAGrupo: 'Ir a Grupo familiar', // [ANALISTA]
  bloquesCuenta: {
    cuenta: 'Tu cuenta', // [ANALISTA]
    politica: 'Política de privacidad', // [ANALISTA]
    grupos: 'Tus grupos', // [ANALISTA]
    dispositivos: 'Tus teléfonos y compu­tadores', // [MATU-55], 1.3: con guion suave (P2-1)
    eventos: 'Últimos ingresos', // [MATU-55]
    avisos: 'Tus avisos', // [ANALISTA]
    avisosEnviados: 'Avisos que te enviamos', // [ANALISTA]
    pagos: 'Tus pagos', // [ANALISTA, D-54-16]
    condiciones: 'Condiciones de compra que acep­taste', // [NUEVO], 1.3: con guion suave (P2-1)
  },
  tuNombre: 'Tu nombre', // [NUEVO]
  // «Tu correo» y «Tu celular» son de CUENTA_PROPIA [L 29]
  completoEnArchivo: 'Completo en el archivo.', // [NUEVO]
  codigosLlegan: 'Los códigos te llegan', // [NUEVO]
  canalCodigos: { sms: 'Por SMS', whatsapp: 'Por WhatsApp' }, // [NUEVO, con las palabras de L 19]
  cuentaCreada: 'Cuenta creada', // [NUEVO]
  aceptasteVersion: (version: string) => [`Aceptaste la versión ${version} el `, '.'] as const, // [NUEVO]
  huella: 'Huella: ', // [NUEVO]
  sinPolitica: 'No hay una aceptación registrada.', // [NUEVO]
  sinGrupos: 'No estás en ningún grupo.', // [NUEVO]
  teUniste: ['Te uniste el ', '.'] as Partes, // [NUEVO]
  sinDispositivos: 'Todavía no hay teléfonos ni computadores.', // [NUEVO]
  desde: ['Desde el ', '.'] as Partes, // [NUEVO]
  ultimaVez: 'Última vez: ', // [L 13.3]
  seCerro: 'Se cerró el ', // [NUEVO]
  cerrado: 'Cerrado', // [NUEVO]
  recibeAvisos: 'Recibe avisos.', // [NUEVO]
  verDondeEntraste: 'Ver dónde entraste', // [MATU-55, 3.5]
  sinEventos: 'No hay ingresos en los últimos 90 días.', // [MATU-55, 2.7]
  porCorreo: 'Por correo', // [L 20]
  enTusTelefonos: 'En tus teléfonos', // [MATU-55, ajuste de L 20]
  si: 'Sí', // [NUEVO]
  no: 'No', // [NUEVO]
  cambiarAvisos: 'Puedes cambiarlos en Tu cuenta.', // [NUEVO]
  pilotoAvisos: 'En el piloto los avisos se prueban sin enviarse: aparecen aquí, pero no te llegaron.', // [ANALISTA]
  sinAvisosEnviados: 'No hay avisos en los últimos 90 días.', // [NUEVO]
  canalAviso: { correo: 'Por correo', push: 'En tus teléfonos', sms: 'Por SMS' } as Record<AvisoEnviadoCopia['canal'], string>, // [L 20], [MATU-55], [NUEVO]
  resultadoAviso: {
    salio: 'Salió', // [ANALISTA]
    no_salio: 'No salió', // [ANALISTA]
    en_el_piloto_no_salio: 'En el piloto no salió', // [ANALISTA, D-54-11]
    pendiente: 'Todavía no sale', // [NUEVO]
  } as Record<AvisoEnviadoCopia['resultado'], string>,
  pago: (referencia: string) => `Pago ${referencia}`, // [NUEVO]
  enGrupo: (grupo: string) => ` en ${grupo}`, // [NUEVO], tras el monto
  tarjeta: (tipo: NonNullable<PagoCuentaCopia['tarjeta']>['tipo']) =>
    tipo === 'credito' ? 'Tarjeta de crédito terminada en ' : tipo === 'debito' ? 'Tarjeta de débito terminada en ' : 'Tarjeta de prepago terminada en ', // [NUEVO]
  /** (1.2, P3-4) Con espacio duro antes del «·»: un renglón nunca empieza con el punto. [NUEVO] */
  cuotas: (n: number) => (n >= 2 ? ` · ${n} cuotas` : ' · Sin cuotas'),
  /** Con `referencia: null` (decisión 392, pago anulado por tardío). [NUEVO] */
  pagoDel: 'Pago del ',
  /** F3 (decisión 402): el mismo código que ya ve en su comprobante. [NUEVO] */
  codigoAutorizacion: 'Código de autorización: ',
  /** F2 (decisión 401): sin el nombre del grupo, que la cuenta ya no puede leer. [NUEVO] */
  grupoQueDejaste: 'Un grupo del que saliste',
  saliste: ['Saliste el ', '.'] as Partes, // [NUEVO]
  sinTarjeta: 'Sin datos de la tarjeta.', // [NUEVO]
  versionEl: (version: string) => [`Versión ${version}, el `, '.'] as const, // [NUEVO]
  paraPedido: (grupo: string, referencia: string) => `En ${grupo}, para el pedido ${referencia}.`, // [NUEVO]
  paraPedidoSinPagar: (grupo: string) => `En ${grupo}, para un pedido que no se pagó.`, // [NUEVO]
}

/** Lo que precisa la frase de un hecho: el nombre del campo o la sección (L 14.1), la finalidad y la referencia. */
export interface ObjetoHecho {
  nombre: string | null
  finalidad: FinalidadCopia | null
}
/** (1.2, F1) Las de autorizaciones, según `finalidad` [NUEVO]. */
const DE_LA_FINALIDAD: Record<FinalidadCopia, string> = { plan_cuidado: 'de la ficha', consumo: 'de los insumos', despacho: 'de los pedidos' }

/**
 * 3.4.9: los 26 tipos del historial. `campo` y `seccion` ya vienen con su nombre de L 14.1. Las
 * marcadas MATU son del sistema: su cola no lleva nombre. Las de pedidos y pagos tienen dos formas
 * (1.2, F1): `FRASE_CON_REFERENCIA` termina en la referencia, que la pantalla pone en `cifras`, y
 * sin referencia se usa la general de aquí.
 */
export const FRASE_HECHO: Record<TipoHecho, (o: ObjetoHecho) => string> = {
  abrio_la_ficha: () => 'Abrió la ficha', // [ANALISTA]
  edito_la_ficha: ({ nombre: n }) => (n ? `Editó «${n}»` : 'Editó la ficha'), // [ANALISTA] y [NUEVO, decisión 356]
  quito_una_seccion: ({ nombre: n }) => (n ? `Quitó «${n}»` : 'Quitó una sección de la ficha'), // [ANALISTA] y [NUEVO]
  ficha_borrada: () => 'MATU borró lo escrito en la ficha', // [README Q15]
  dio_una_autorizacion: ({ finalidad: f }) => (f && DE_LA_FINALIDAD[f] ? `Dio la autorización ${DE_LA_FINALIDAD[f]}` : 'Dio una autorización'), // [NUEVO]
  retiro_una_autorizacion: ({ finalidad: f }) => (f && DE_LA_FINALIDAD[f] ? `Retiró la autorización ${DE_LA_FINALIDAD[f]}` : 'Retiró una autorización'), // [NUEVO]
  compartio_la_ficha: () => 'Compartió la ficha con un relevo', // [NUEVO]
  corto_un_enlace: () => 'Cortó un enlace de relevo', // [NUEVO]
  agrego_un_insumo: () => 'Agregó un insumo', // [NUEVO]
  edito_un_insumo: () => 'Cambió un insumo', // [NUEVO]
  dejo_de_seguir_un_insumo: () => 'Dejó de seguir un insumo', // [NUEVO]
  volvio_a_seguir_un_insumo: () => 'Volvió a seguir un insumo', // [NUEVO]
  quito_un_insumo: () => 'Quitó un insumo', // [NUEVO]
  anoto_una_compra: () => 'Anotó una compra', // [NUEVO]
  aviso_de_insumo: () => 'MATU avisó que un insumo se está acabando', // [NUEVO]
  descarto_un_aviso: () => 'Descartó un aviso de insumo', // [NUEVO]
  resolvio_un_aviso: () => 'Resolvió un aviso de insumo', // [NUEVO]
  cambio_la_direccion: () => 'Cambió la dirección', // [NUEVO]
  creo_un_pedido: () => 'Armó un pedido', // [NUEVO]
  confirmo_un_pedido: () => 'Confirmó un pedido', // [NUEVO]
  cancelo_un_pedido: () => 'Canceló un pedido', // [NUEVO]
  cambio_que_hacer_si_falta: () => 'Cambió qué hacer si falta un producto', // [NUEVO]
  inicio_un_pago: () => 'Empezó a pagar un pedido', // [NUEVO]
  pago_aprobado: () => 'Se aprobó el pago de un pedido', // [README Q15, ajustado]
  pago_anulado: () => 'Se devolvió dinero de un pago', // [README Q15, ajustado]
  pidio_una_copia: () => 'Pidió una copia de los datos', // [ANALISTA]
}

/** (1.2, F1) Con `referencia`: la frase sin el número, que la pantalla agrega en `cifras`. [NUEVO] */
export const FRASE_CON_REFERENCIA: Partial<Record<TipoHecho, string>> = {
  creo_un_pedido: 'Armó el pedido ',
  confirmo_un_pedido: 'Confirmó el pedido ',
  cancelo_un_pedido: 'Canceló el pedido ',
  cambio_que_hacer_si_falta: 'Cambió qué hacer si falta un producto en el pedido ',
  inicio_un_pago: 'Empezó a pagar el pedido ',
  pago_aprobado: 'Se aprobó el pago del pedido ',
  pago_anulado: 'Se devolvió dinero del pago del pedido ',
}
