// «Datos de {nombre_pila}» (`/grupo/datos`, MATU-54, especificación docs/diseno/matu-54-mis-datos.md
// v1.1, sección 3): todo lo que MATU guarda de la persona cuidada, para leerlo y descargarlo. La pide
// admin o cuidador. La persona sale de la memoria de la app (`datosDe`), nunca de la ruta. Abrir la
// página es pedir una copia (P1): un solo GET, y «Descargar» guarda esos mismos caracteres.
import type { ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { Circle, FileText, Hourglass, Info, RefreshCw, ShieldCheck, ShieldOff, ShieldQuestion, Trash2, type LucideIcon } from 'lucide-react'
import { nombrePilaDe, type PersonaListada } from '../compartido/api/familia'
import {
  pedirCopiaPersona,
  type AutorizacionCopia,
  type AvisoInsumoCopia,
  type CompraCopia,
  type CopiaDatosPersona,
  type DireccionCopia,
  type EnlaceRelevoCopia,
  type EntregaCopia,
  type EstadoBloque,
  type FichaCopia,
  type InsumoCopia,
  type InsumosCopia,
  type PedidoCopia,
  type PersonaNombrada,
} from '../compartido/api/misDatos'
import { TITULO_SECCION } from '../compartido/secciones'
import type { EntradaIndice } from '../compartido/ui/Indice'
import { useCorreoPrivacidad } from './Cuenta'
import { APOYOS, CAMPOS } from './datos'
import { useFamilia } from './estado'
import { INSUMOS } from './textosInsumos'
import { pesos } from './textosCatalogo'
import { AvisoPiloto } from './PiezasPedido'
import { LineaApertura } from './QuienLaVio'
import { navegar } from './ruteo'
import { COMPARTIR } from './textos'
import { MIS_DATOS as T } from './textosMisDatos'
import { PEDIDO } from './textosPedido'
import { Cola, Etiqueta, Nota, Pagina, Volver } from './ui'
import {
  AvisoDeCarga,
  Bloque,
  BotonVerMas,
  Cargando,
  ConDia,
  ConFechaHora,
  CuerpoConIndice,
  Dia,
  DiaDeInstante,
  enNoventaDias,
  FechaHora,
  FraseConCorreo,
  FraseNoventa,
  LineaHistorial,
  nombreDe,
  PanelDescarga,
  PorDia,
  seMuestraHecho,
  SUPERFICIE,
  useCopia,
  useVerMas,
  Vacio,
} from './PiezasMisDatos'

/** El `id` del botón de Grupo familiar que abre esta página, para devolverle el foco (2). */
export const idVerDatos = (personaId: string) => `datos-${personaId}`

export function DatosDePersona() {
  const { datosDe, personas } = useFamilia()
  const persona = personas.find((p) => p.id === datosDe) ?? null
  // Sin la persona en memoria la regla de ruta ya lleva a `/grupo` (1).
  if (!persona) return null
  return <PaginaDatosPersona persona={persona} />
}

function PaginaDatosPersona({ persona }: { persona: PersonaListada }) {
  const { fijar } = useFamilia()
  const pila = nombrePilaDe(persona)
  const correo = useCorreoPrivacidad()
  const { estado, reintentar } = useCopia(() => pedirCopiaPersona(persona.id), true)

  const volver = () => {
    // El foco vuelve al botón «Ver los datos de…» cuando Grupo familiar lo pinta (2).
    flushSync(() => fijar({ focoAlVolver: idVerDatos(persona.id) }))
    navegar('/grupo')
  }

  const copia = estado.estado === 'lista' ? estado.copia : null
  const bajada = copia ? (
    <>
      {T.bajadaPersona(pila)[0]}
      <FechaHora iso={copia.datos.generado_en} fin={T.bajadaPersona(pila)[2]} />
    </>
  ) : undefined

  return (
    <Pagina titulo={T.titulo(pila)} bajada={bajada} ayuda={T.limiteCopias} antes={<Volver onClick={volver}>{T.volverAGrupo}</Volver>}>
      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado !== 'cargando' && estado.estado !== 'lista' && <AvisoDeCarga e={estado} reintentar={reintentar} />}
      {copia && (
        <>
          <PanelDescarga
            copia={copia}
            texto={copia.datos.ficha.estado === 'disponible' ? T.dialogoPersona : T.dialogoPersonaSinFicha}
            destacado={T.dialogoRelevo}
          />
          <Copia datos={copia.datos} correo={correo} />
        </>
      )}
    </Pagina>
  )
}

// ---------------------------------------------------------------- los nueve bloques (3.1)

function Copia({ datos, correo }: { datos: CopiaDatosPersona; correo: string | null }) {
  const pila = datos.persona.nombre_pila
  const insumosVisibles = datos.insumos.estado === 'disponible'
  const entradas: EntradaIndice[] = [
    { id: 'sus-datos', texto: T.bloques.persona },
    { id: 'autorizaciones', texto: T.bloques.autorizaciones },
    { id: 'su-ficha', texto: T.bloques.ficha },
    { id: 'enlaces-de-relevo', texto: T.bloques.enlaces },
    { id: 'sus-insumos', texto: T.bloques.insumos },
    ...(insumosVisibles
      ? [
          { id: 'compras-anotadas', texto: T.bloques.compras },
          { id: 'avisos-de-insumos', texto: T.bloques.avisosInsumos },
        ]
      : []),
    ...(datos.pedidos !== null ? [{ id: 'sus-pedidos', texto: T.bloques.pedidos }] : []),
    { id: 'quien-abrio', texto: T.bloques.historial },
  ]
  return (
    <CuerpoConIndice entradas={entradas}>
      <Bloque id="sus-datos" titulo={T.bloques.persona}>
        <SusDatos datos={datos} correo={correo} />
      </Bloque>
      <Bloque id="autorizaciones" titulo={T.bloques.autorizaciones}>
        <Autorizaciones lista={datos.autorizaciones} pila={pila} correo={correo} />
      </Bloque>
      <Bloque id="su-ficha" titulo={T.bloques.ficha}>
        <SuFicha ficha={datos.ficha} pila={pila} />
      </Bloque>
      <Bloque id="enlaces-de-relevo" titulo={T.bloques.enlaces}>
        <Enlaces lista={datos.enlaces_relevo} generadoEn={datos.generado_en} />
      </Bloque>
      <Bloque id="sus-insumos" titulo={T.bloques.insumos}>
        <SusInsumos insumos={datos.insumos} pila={pila} />
      </Bloque>
      {insumosVisibles && (
        <>
          <Bloque id="compras-anotadas" titulo={T.bloques.compras}>
            <Compras compras={datos.insumos.compras ?? []} generadoEn={datos.generado_en} />
          </Bloque>
          <Bloque id="avisos-de-insumos" titulo={T.bloques.avisosInsumos}>
            <AvisosInsumos avisos={datos.insumos.avisos ?? []} generadoEn={datos.generado_en} />
          </Bloque>
        </>
      )}
      {/* D-54-15: con la capa 3 quitada el bloque no existe; apagada o sin autorización, se ve igual. */}
      {datos.pedidos !== null && (
        <Bloque id="sus-pedidos" titulo={T.bloques.pedidos}>
          <Pedidos pedidos={datos.pedidos} generadoEn={datos.generado_en} />
        </Bloque>
      )}
      <Bloque id="quien-abrio" titulo={T.bloques.historial}>
        <Historial datos={datos} correo={correo} />
      </Bloque>
    </CuerpoConIndice>
  )
}

// ---------------------------------------------------------------- 3.4.1 Sus datos

const FILA_DL = 'flex flex-col gap-0.5 py-4 @3xl/main:grid @3xl/main:grid-cols-[12rem_minmax(0,1fr)] @3xl/main:gap-x-6'

export const direccionEnLinea = (d: DireccionCopia | EntregaCopia) => [`${d.calle} ${d.numero}`, d.depto, d.comuna, d.region].filter((x) => x && x.trim()).join(', ')

function SusDatos({ datos, correo }: { datos: CopiaDatosPersona; correo: string | null }) {
  const p = datos.persona
  const apoyo = APOYOS.find((a) => a.valor === p.nivel_apoyo)?.texto
  return (
    <>
      <dl className={SUPERFICIE}>
        <div className={FILA_DL}>
          <dt className="text-base text-tenue">{T.nombre}</dt>
          <dd className="font-bold break-words">{p.nombre}</dd>
        </div>
        <div className={FILA_DL}>
          <dt className="text-base text-tenue">{T.leDicen}</dt>
          <dd className="font-bold break-words">{p.nombre_pila}</dd>
        </div>
        {apoyo && (
          <div className={FILA_DL}>
            <dt className="text-base text-tenue">{T.apoyo}</dt>
            <dd className="font-bold break-words">{apoyo}</dd>
          </div>
        )}
        <div className={FILA_DL}>
          <dt className="text-base text-tenue">{T.direccion}</dt>
          {p.direccion ? (
            <dd className="font-bold break-words">
              <span className="block">{direccionEnLinea(p.direccion)}</span>
              {p.direccion.referencia && <span className="block">{T.referencia(p.direccion.referencia)}</span>}
            </dd>
          ) : (
            <dd className="text-tenue">{T.sinDireccion}</dd>
          )}
        </div>
        <div className={FILA_DL}>
          <dt className="text-base text-tenue">{T.enMatuDesde}</dt>
          <dd className="font-bold">
            <DiaDeInstante iso={p.alta_en} />
          </dd>
        </div>
      </dl>
      {/* Cubre la rectificación mientras no exista MATU-91 (P8). Sin correo configurado, no va. */}
      {correo && (
        <p className="max-w-prose text-base text-tenue">
          <FraseConCorreo partes={T.rectificar} correo={correo} />
        </p>
      )}
    </>
  )
}

// ---------------------------------------------------------------- 3.4.2 Autorizaciones

const ICONO_AUTORIZACION: Record<AutorizacionCopia['estado'], LucideIcon> = {
  vigente: ShieldCheck,
  revision_vencida: Hourglass,
  retirada: ShieldOff,
  reemplazada: RefreshCw,
}
const TONO_AUTORIZACION = { vigente: 'ok', revision_vencida: 'atenta', retirada: 'neutro', reemplazada: 'neutro' } as const

function Autorizaciones({ lista, pila, correo }: { lista: AutorizacionCopia[]; pila: string; correo: string | null }) {
  if (!lista.length) return <Vacio>{T.sinAutorizaciones}</Vacio>
  return (
    <ul className="flex flex-col gap-3">
      {lista.map((a, i) => {
        const Icono = ICONO_AUTORIZACION[a.estado] ?? Circle
        // La retirada lleva además borde punteado: el estado nunca solo por el color (MATU-44).
        const forma = a.estado === 'retirada' ? 'bg-papel border-2 border-dashed border-borde' : 'bg-hoja ring-1 ring-linea'
        const partesAceptado = [
          <>
            {T.politicaVersion}
            <span className="cifras">{a.version_politica}</span>
          </>,
          ...(a.declaracion
            ? [
                <>
                  {T.declaracionVersion}
                  <span className="cifras">{a.declaracion.version}</span>
                </>,
              ]
            : []),
          ...(a.aviso
            ? [
                <>
                  {T.avisoVersion}
                  <span className="cifras">{a.aviso.version}</span>
                </>,
              ]
            : []),
        ]
        return (
          <li key={`${a.finalidad}-${a.otorgada_en}-${i}`} className={`flex min-w-0 flex-col gap-2 rounded-xl px-4 angosto:px-2 py-4 ${forma}`}>
            <h3 className="text-lg font-bold break-words">{T.finalidad[a.finalidad] ?? ''}</h3>
            {T.estadoAutorizacion[a.estado] && (
              <Etiqueta className="self-start" tono={TONO_AUTORIZACION[a.estado]}>
                <Icono aria-hidden className="size-4 shrink-0" />
                <span className="min-w-0">{T.estadoAutorizacion[a.estado]}</span>
              </Etiqueta>
            )}
            <p className="max-w-prose text-base">{T.laDa(a.calidad_otorgante, pila)}</p>
            <p className="max-w-prose text-base break-words">
              <ConFechaHora partes={[T.laRegistro(nombreDe(a.registrada_por))[0], T.laRegistro('')[1]]} iso={a.otorgada_en} />
            </p>
            {a.estado === 'vigente' && a.revision_vence_en && (
              <p className="max-w-prose text-base">
                {T.hayQueRenovar[0]}
                <DiaDeInstante iso={a.revision_vence_en} fin={T.hayQueRenovar[1]} />
              </p>
            )}
            {a.estado === 'revision_vencida' && a.revision_vence_en && (
              <p className="max-w-prose text-base">
                {T.habiaQueRenovar[0]}
                <DiaDeInstante iso={a.revision_vence_en} fin={T.habiaQueRenovar[1]} />
              </p>
            )}
            {(a.estado === 'retirada' || a.estado === 'reemplazada') && a.retirada_en && (
              <p className="max-w-prose text-base">
                <ConFechaHora partes={a.estado === 'retirada' ? T.seRetiro : T.seRenovo} iso={a.retirada_en} />
              </p>
            )}
            <p className="max-w-prose text-base text-tenue">
              {T.loAceptado}
              {partesAceptado.map((parte, j) => (
                <span key={j}>
                  {j === 0 ? '' : j === partesAceptado.length - 1 ? ' y ' : ', '}
                  {parte}
                </span>
              ))}
              .
            </p>
            {a.hay_documento_representante && (
              <Nota tono="rocio" iconoEnLinea icono={<FileText aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
                <FraseConCorreo partes={T.documentoRepresentante} correo={correo} sinCorreo={T.documentoRepresentanteSinCorreo} />
              </Nota>
            )}
          </li>
        )
      })}
    </ul>
  )
}

// ---------------------------------------------------------------- 3.5 lo que reemplaza a la ficha o a los insumos

const NOTA_ESTADO: Record<Exclude<EstadoBloque, 'disponible'>, { icono: LucideIcon; punteado: boolean }> = {
  retirada: { icono: ShieldOff, punteado: true },
  en_pausa: { icono: Hourglass, punteado: false },
  borrada: { icono: Trash2, punteado: true },
  sin_autorizar: { icono: ShieldQuestion, punteado: false },
}

function textoEstado(que: 'ficha' | 'insumos', estado: Exclude<EstadoBloque, 'disponible'>, pila: string, borradoEl: string | null): ReactNode {
  const t = que === 'ficha' ? T.estadoFicha : T.estadoInsumos
  if (estado === 'retirada') return borradoEl ? <ConDia partes={t.retirada} dia={borradoEl} /> : t.retiradaSinFecha
  if (estado === 'sin_autorizar') return t.sin_autorizar(pila)
  return t[estado] ?? t.sin_autorizar(pila)
}

/** 3.5: la nota en `rocio`, con el ícono del estado y, si se retiró o se borró, el borde punteado de MATU-44. */
function NotaEstado({ que, estado, pila, borradoEl }: { que: 'ficha' | 'insumos'; estado: Exclude<EstadoBloque, 'disponible'>; pila: string; borradoEl: string | null }) {
  const { icono: Icono, punteado } = NOTA_ESTADO[estado] ?? NOTA_ESTADO.sin_autorizar
  return (
    <Nota tono="rocio" iconoEnLinea className={punteado ? 'border-2 border-dashed border-borde' : ''} icono={<Icono aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
      {textoEstado(que, estado, pila, borradoEl)}
    </Nota>
  )
}

// ---------------------------------------------------------------- 3.4.3 Su ficha

function SuFicha({ ficha, pila }: { ficha: FichaCopia; pila: string }) {
  if (ficha.estado !== 'disponible') return <NotaEstado que="ficha" estado={ficha.estado} pila={pila} borradoEl={ficha.borrado_el} />
  const filas: { clave: string; titulo: string; texto: string | null; autor: PersonaNombrada | null; cuando: string | null; escrito: boolean }[] = []
  for (const c of CAMPOS) {
    const campo = ficha.campos?.find((x) => x.campo === c.api)
    filas.push({ clave: c.api, titulo: c.titulo, texto: campo?.texto ?? null, autor: campo?.escrito_por ?? null, cuando: campo?.actualizado_en ?? null, escrito: !!campo?.texto })
  }
  for (const s of ficha.secciones ?? []) {
    if (!TITULO_SECCION[s.seccion]) continue
    filas.push({ clave: s.seccion, titulo: TITULO_SECCION[s.seccion], texto: s.texto, autor: s.escrito_por, cuando: s.actualizado_en, escrito: true })
  }
  return (
    <ul className={SUPERFICIE}>
      {filas.map((f) => (
        <li key={f.clave} className="flex flex-col gap-2 py-4">
          <h3 className="text-lg font-bold break-words">{f.titulo}</h3>
          {f.escrito ? (
            <>
              {/* Tal cual se escribió, con los nombres y teléfonos de «A quién llamar» (D-54-4). */}
              <p className="max-w-prose text-base whitespace-pre-line break-words">{f.texto}</p>
              {f.cuando && (
                <p className="max-w-prose text-base text-tenue break-words">
                  <ConFechaHora partes={[T.loEscribio(nombreDe(f.autor))[0], '.']} iso={f.cuando} />
                </p>
              )}
            </>
          ) : (
            <p className="text-base text-tenue">{T.sinEscribir}</p>
          )}
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------- 3.4.4 Enlaces de relevo

const queVe = (e: EnlaceRelevoCopia) => {
  const nombres = [
    ...CAMPOS.filter((c) => e.campos.includes(c.api)).map((c) => c.titulo),
    ...(Object.keys(TITULO_SECCION) as (keyof typeof TITULO_SECCION)[]).filter((s) => e.secciones.includes(s)).map((s) => TITULO_SECCION[s]),
  ]
  return nombres.length > 1 ? `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}` : (nombres[0] ?? '')
}

function Enlaces({ lista, generadoEn }: { lista: EnlaceRelevoCopia[]; generadoEn: string }) {
  return (
    <>
      <p className="max-w-prose text-base text-tenue">{T.sinTelefonoRelevos}</p>
      {lista.length ? (
        <ul className={SUPERFICIE}>
          {lista.map((e, i) => (
            <Enlace key={`${e.creado_en}-${i}`} e={e} generadoEn={generadoEn} />
          ))}
        </ul>
      ) : (
        <Vacio>{T.sinEnlaces}</Vacio>
      )}
    </>
  )
}

const ICONO_ENLACE = { vigente: ShieldCheck, vencido: Hourglass, revocado: ShieldOff, bloqueado: ShieldQuestion } as const

function Enlace({ e, generadoEn }: { e: EnlaceRelevoCopia; generadoEn: string }) {
  const Icono = ICONO_ENLACE[e.estado] ?? Circle
  const ve = queVe(e)
  const { dentro } = enNoventaDias(e.aperturas, (a) => a.ocurrido_en, generadoEn)
  const aperturas = dentro.map((a, i) => ({ tipo: a.tipo, ocurrido_en: a.ocurrido_en, acceso: { id: `${e.creado_en}-${i}`, nombre_relevo: e.nombre_relevo } }))
  const mas = useVerMas(aperturas.length, 5)
  return (
    <li className="flex min-w-0 flex-col gap-2 py-4">
      <h3 className="text-lg font-bold break-words">{e.nombre_relevo}</h3>
      {T.estadoEnlace[e.estado] && (
        <Etiqueta className="self-start" tono={e.estado === 'vigente' ? 'activo' : e.estado === 'bloqueado' ? 'atenta' : 'neutro'}>
          <Icono aria-hidden className="size-4 shrink-0" />
          <span className="min-w-0">{T.estadoEnlace[e.estado]}</span>
        </Etiqueta>
      )}
      {COMPARTIR.motivos[e.motivo] && <p className="max-w-prose text-base">{COMPARTIR.motivos[e.motivo]}</p>}
      {ve && (
        <p className="max-w-prose text-base break-words">
          {T.ve}
          {ve}.
        </p>
      )}
      <p className="max-w-prose text-base break-words">
        <ConFechaHora partes={[T.loCompartio(e.compartido_por)[0], '.']} iso={e.creado_en} />
      </p>
      {e.estado === 'vigente' && (
        <p className="max-w-prose text-base">
          <ConFechaHora partes={T.vence} iso={e.vence_en} />
        </p>
      )}
      {e.estado === 'vencido' && (
        <p className="max-w-prose text-base">
          <ConFechaHora partes={T.vencio} iso={e.vence_en} />
        </p>
      )}
      {(e.estado === 'revocado' || e.estado === 'bloqueado') && e.cortado_en && (
        <p className="max-w-prose text-base">
          <ConFechaHora partes={T.seCorto} iso={e.cortado_en} />
        </p>
      )}
      <p className="max-w-prose text-base">
        {e.usos === 0 ? (
          T.noSeAbrio
        ) : e.usos === 1 ? (
          <ConFechaHora partes={T.seAbrioUna} iso={e.ultimo_uso_en} />
        ) : (
          <ConFechaHora partes={[T.seAbrioVeces(e.usos)[0], '.']} iso={e.ultimo_uso_en} />
        )}
      </p>
      {aperturas.length > 0 && (
        <>
          <ol className="flex w-full max-w-prose flex-col">
            {aperturas.slice(0, mas.visibles).map((a, i) => (
              <LineaApertura key={`${a.ocurrido_en}-${i}`} a={a} sinAbrir={false} completa="fecha" notas={false} foco={mas.foco(i)} />
            ))}
          </ol>
          {mas.hayMas && <BotonVerMas onClick={mas.mas} />}
        </>
      )}
    </li>
  )
}

// ---------------------------------------------------------------- 3.4.5 Sus insumos

function SusInsumos({ insumos, pila }: { insumos: InsumosCopia; pila: string }) {
  if (insumos.estado !== 'disponible') return <NotaEstado que="insumos" estado={insumos.estado} pila={pila} borradoEl={insumos.borrado_el} />
  const lista = insumos.lista ?? []
  if (!lista.length) return <Vacio>{T.sinInsumos}</Vacio>
  return (
    <ul className={SUPERFICIE}>
      {lista.map((x, i) => (
        <Insumo key={`${x.nombre}-${i}`} x={x} />
      ))}
    </ul>
  )
}

function Insumo({ x }: { x: InsumoCopia }) {
  return (
    <li className="flex min-w-0 flex-col gap-1 py-4">
      <h3 className="text-lg font-bold break-words">{x.nombre}</h3>
      {!x.se_sigue && (
        <Etiqueta className="self-start">
          <Circle aria-hidden className="size-3.5 shrink-0" strokeWidth={2.5} />
          <span className="min-w-0">{T.yaNoSeSigue}</span>
        </Etiqueta>
      )}
      {/* Las frases de «Usa…» y «Quedaban…» son las de Insumos (L 21). */}
      <p className="max-w-prose text-base">{INSUMOS.usa(x.usa_unidades, x.cada_dias, x.unidad)}</p>
      <p className="max-w-prose text-base">
        <ConDia partes={[`${INSUMOS.quedaban(x.quedaban_unidades, x.unidad)} `, '.']} dia={x.quedaban_el} />
      </p>
      {x.se_sigue && (
        <p className="max-w-prose text-base">
          <ConDia partes={T.seAcaba} dia={x.se_acaba_el} />
        </p>
      )}
      <p className="max-w-prose text-base">{T.avisa(x.dias_aviso)}</p>
      {x.unidades_por_envase !== null && <p className="max-w-prose text-base">{T.porEnvase(x.unidades_por_envase)}</p>}
      <p className="max-w-prose text-base text-tenue break-words">
        {T.loAgregaron[0]}
        <DiaDeInstante iso={x.agregado_en} fin={T.loAgregaron[1]} />
        <ConFechaHora partes={[T.loCambio(nombreDe(x.actualizado_por))[0], '.']} iso={x.actualizado_en} />
      </p>
    </li>
  )
}

// ---------------------------------------------------------------- 3.4.6 Compras anotadas

function Compras({ compras, generadoEn }: { compras: CompraCopia[]; generadoEn: string }) {
  const { dentro, hayAnterior } = enNoventaDias(compras, (c) => c.anotada_en, generadoEn)
  const mas = useVerMas(dentro.length, 10)
  // 1.3 (decisión 403): el título ya dice el plazo; solo si hay algo anterior se dice dónde está.
  const anteriores = hayAnterior && <p className="max-w-prose text-base text-tenue">{T.comprasAnteriores}</p>
  if (!dentro.length)
    return (
      <>
        {anteriores}
        <Vacio>{T.sinCompras}</Vacio>
      </>
    )
  return (
    <>
      {anteriores}
      <ol className={SUPERFICIE}>
        {dentro.slice(0, mas.visibles).map((c, i) => (
          <li key={`${c.anotada_en}-${i}`} ref={mas.foco(i)} tabIndex={mas.foco(i) ? -1 : undefined} className="flex flex-col gap-0.5 py-3 outline-none">
            <span className="font-bold break-words">{T.compra(c.unidades, c.unidad, c.insumo)}</span>
            <span className="text-base text-tenue break-words">
              {T.el}
              <Dia dia={c.el} />
              <Cola>{c.origen === 'pedido_matu' ? T.llegoConPedido : T.anoto(nombreDe(c.anotada_por))}</Cola>
            </span>
          </li>
        ))}
      </ol>
      {mas.hayMas && <BotonVerMas onClick={mas.mas} />}
    </>
  )
}

// ---------------------------------------------------------------- 3.4.7 Avisos de insumos

function AvisosInsumos({ avisos, generadoEn }: { avisos: AvisoInsumoCopia[]; generadoEn: string }) {
  const { dentro, hayAnterior } = enNoventaDias(avisos, (a) => a.creado_en, generadoEn)
  const mas = useVerMas(dentro.length, 20)
  return (
    <>
      <FraseNoventa hayAnterior={hayAnterior} />
      {dentro.length ? (
        <ol className={SUPERFICIE}>
          {dentro.slice(0, mas.visibles).map((a, i) => (
            <li key={`${a.creado_en}-${i}`} ref={mas.foco(i)} tabIndex={mas.foco(i) ? -1 : undefined} className="flex flex-col gap-0.5 py-3 outline-none">
              <span className="font-bold break-words">
                <ConDia partes={[T.seAcabaInsumo(a.insumo)[0], '.']} dia={a.fecha_prevista} />
              </span>
              <span className="text-base text-tenue">
                {a.estado === 'pendiente' ? (
                  T.estadoAvisoInsumo.pendiente
                ) : a.estado === 'notificada' ? (
                  <ConFechaHora partes={T.estadoAvisoInsumo.notificada} iso={a.notificado_en} />
                ) : a.estado === 'resuelta' ? (
                  <ConFechaHora partes={T.estadoAvisoInsumo.resuelta} iso={a.cerrado_en} />
                ) : a.estado === 'descartada' ? (
                  <ConFechaHora partes={T.estadoAvisoInsumo.descartada} iso={a.cerrado_en} />
                ) : null}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <Vacio>{T.sinAvisosInsumos}</Vacio>
      )}
      {mas.hayMas && <BotonVerMas onClick={mas.mas} />}
    </>
  )
}

// ---------------------------------------------------------------- 3.4.8 Sus pedidos

function Pedidos({ pedidos, generadoEn }: { pedidos: PedidoCopia[]; generadoEn: string }) {
  const { dentro, hayAnterior } = enNoventaDias(pedidos, (p) => p.creado_en, generadoEn)
  const mas = useVerMas(dentro.length, 20)
  // `PreciosDeEjemplo`, una sola vez al pie del bloque (DISENO 3).
  const deEjemplo = dentro.some((p) => p.precios_de_ejemplo)
  return (
    <>
      <FraseNoventa hayAnterior={hayAnterior} />
      {dentro.length ? (
        <ul className={SUPERFICIE}>
          {dentro.slice(0, mas.visibles).map((p, i) => (
            <Pedido key={`${p.creado_en}-${i}`} p={p} foco={mas.foco(i)} />
          ))}
        </ul>
      ) : (
        <Vacio>{T.sinPedidos}</Vacio>
      )}
      {mas.hayMas && <BotonVerMas onClick={mas.mas} />}
      {deEjemplo && <AvisoPiloto />}
    </>
  )
}

const FILA_MONTO = 'grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 angosto:grid-cols-1'

function Monto({ n }: { n: number }) {
  return <span className="cifras">{pesos(n)}</span>
}

function Pedido({ p, foco }: { p: PedidoCopia; foco?: React.Ref<HTMLLIElement> }) {
  const estado = T.estadoPedido[p.estado]
  const siFalta = (s: 'otro_comercio' | 'quitar') => (s === 'quitar' ? PEDIDO.quitar : PEDIDO.otroComercio).toLocaleLowerCase('es-CL')
  const pago = p.pago
  return (
    <li ref={foco} tabIndex={foco ? -1 : undefined} className="flex min-w-0 flex-col gap-2 py-4 outline-none">
      <h3 className="text-lg font-bold break-words">
        {p.referencia ? (
          <>
            {T.pedido('')}
            <span className="cifras">{p.referencia}</span>
          </>
        ) : (
          <>
            {T.pedidoDel}
            <DiaDeInstante iso={p.creado_en} />
          </>
        )}
      </h3>
      {estado && (
        <Etiqueta className="self-start">
          <Circle aria-hidden className="size-3.5 shrink-0" strokeWidth={2.5} />
          <span className="min-w-0">{estado}</span>
        </Etiqueta>
      )}
      <p className="max-w-prose text-base text-tenue">
        <ConFechaHora partes={T.loArmaron} iso={p.creado_en} />
      </p>
      {p.lineas.length > 0 && (
        <dl className="flex w-full max-w-prose flex-col gap-3">
          {p.lineas.map((l, i) => (
            <div key={`${l.producto}-${i}`} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 angosto:grid-cols-1">
              <dt className="min-w-0 break-words">
                {l.producto}, {l.presentacion} ×{' '}
                <span className="cifras">{l.cantidad}</span>
              </dt>
              <dd className="text-right angosto:text-left">
                <Monto n={l.subtotal} />
              </dd>
              <dd className="col-span-full text-base text-tenue break-words">
                {T.enComercio(l.comercio)}
                <Cola>{T.siFalta(siFalta(l.si_falta))}</Cola>
              </dd>
            </div>
          ))}
        </dl>
      )}
      {/* 1.3 (P2): en modo angosto, el rótulo y el monto en una columna, como las líneas. */}
      <dl className="flex w-full max-w-prose flex-col gap-1">
        <div className={FILA_MONTO}>
          <dt>{T.productos}</dt>
          <dd className="text-right angosto:text-left">
            <Monto n={p.subtotal_productos} />
          </dd>
        </div>
        <div className={FILA_MONTO}>
          <dt>{T.envio}</dt>
          <dd className="text-right angosto:text-left">
            <Monto n={p.costo_envio} />
          </dd>
        </div>
        {p.total !== null && (
          <div className={`${FILA_MONTO} font-bold`}>
            <dt>{T.total}</dt>
            <dd className="text-right angosto:text-left">
              <Monto n={p.total} />
            </dd>
          </div>
        )}
      </dl>
      <PagoDelPedido pago={pago} />
      {pago?.devoluciones.map((d, i) => {
        const [antes, despues] = T.devolucion(d)
        return (
          <p key={`${d.solicitada_en}-${i}`} className="max-w-prose text-base text-tenue break-words">
            {antes}
            <Monto n={d.monto} />
            {despues}
          </p>
        )
      })}
      {pago?.pago_de_prueba && <p className="max-w-prose text-base font-bold">{T.pagoDePrueba}</p>}
      {p.entrega && (
        <p className="max-w-prose text-base text-tenue break-words">
          {T.entrega}
          {direccionEnLinea(p.entrega)}
        </p>
      )}
    </li>
  )
}

function PagoDelPedido({ pago }: { pago: PedidoCopia['pago'] }) {
  if (!pago || pago.estado === 'sin_intento') return <p className="text-base">{T.sinPagar}</p>
  if (pago.estado === 'pendiente') return <p className="text-base">{T.pagoEnCurso}</p>
  if (pago.estado === 'no_aprobado') return <p className="text-base">{T.noAprobado}</p>
  if (pago.estado === 'anulado')
    return (
      <p className="text-base">
        {T.anulado}
        <span className="cifras">{pesos(pago.devuelto)}.</span>
      </p>
    )
  if (pago.estado !== 'aprobado' && pago.estado !== 'devuelto_parcial') return null
  return (
    <>
      <p className="max-w-prose text-base break-words">
        <ConFechaHora partes={[T.loPago(nombreDe(pago.pagado_por))[0], '.']} iso={pago.pagado_en} />
      </p>
      {/* 54-H4 (MATU-107, 4): la cola con «·» y break-words como red. */}
      <p className="text-base break-words">
        {T.cobrado}
        <span className="cifras">
          {pesos(pago.cobrado)}
          {pago.devuelto > 0 ? '' : '.'}
        </span>
        {pago.devuelto > 0 && (
          <Cola>
            {T.devuelto}
            <span className="cifras">{pesos(pago.devuelto)}.</span>
          </Cola>
        )}
      </p>
    </>
  )
}

// ---------------------------------------------------------------- 3.4.9 Quién abrió o editó la ficha

function Historial({ datos, correo }: { datos: CopiaDatosPersona; correo: string | null }) {
  const h = datos.historial
  const conocidos = h.hechos.filter(seMuestraHecho)
  const { dentro, hayAnterior } = enNoventaDias(conocidos, (x) => x.ocurrido_en, datos.generado_en)
  const mas = useVerMas(dentro.length, 20)
  return (
    <>
      <FraseNoventa hayAnterior={hayAnterior} />
      {h.alcance === 'lo_tuyo' && (
        <Nota tono="rocio" iconoEnLinea icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {T.loTuyo}
        </Nota>
      )}
      {dentro.length ? (
        <PorDia items={dentro.slice(0, mas.visibles)} instante={(x) => x.ocurrido_en} linea={(x, i) => <LineaHistorial key={`${x.tipo}-${x.ocurrido_en}-${i}`} h={x} foco={mas.foco(i)} />} />
      ) : (
        <Vacio>{T.sinHechos}</Vacio>
      )}
      {mas.hayMas && <BotonVerMas onClick={mas.mas} />}
      {h.hay_hechos_sin_asociar && (
        <Nota tono="rocio" iconoEnLinea icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          <FraseConCorreo partes={T.sinAsociar} correo={correo} sinCorreo={T.sinAsociarSinCorreo} />
        </Nota>
      )}
    </>
  )
}
