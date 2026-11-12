// «Tus datos» (`/cuenta/datos`, MATU-54, especificación docs/diseno/matu-54-mis-datos.md v1.1, sección
// 5): lo que MATU guarda de la propia cuenta, para leerlo y descargarlo. Cualquier rol la abre. Nunca
// nombra a una persona cuidada (P5). Abrir la página es pedir una copia (P1): un solo GET, que suma
// «Pediste una copia de tus datos» a los ingresos.
import { flushSync } from 'react-dom'
import { Bell, Check, Circle, CircleDashed, Clock, Eye, EyeOff, Info, X, type LucideIcon } from 'lucide-react'
import {
  pedirCopiaCuenta,
  type AvisoEnviadoCopia,
  type CondicionesCopia,
  type CopiaDatosCuenta,
  type DispositivoCopia,
  type EventoCuentaCopia,
  type PagoCuentaCopia,
} from '../compartido/api/misDatos'
import type { EventoCuenta } from '../compartido/api/familia'
import { Boton } from '../compartido/ui/Boton'
import type { EntradaIndice } from '../compartido/ui/Indice'
import { celularEnPantalla } from './celularEnPantalla'
import { ID_VER_TUS_DATOS } from './Cuenta'
import { iconoClase, LineaIngreso, seMuestra } from './DondeEntraste'
import { useFamilia } from './estado'
import { navegar } from './ruteo'
import { CUENTA_PROPIA } from './textos'
import { pesos } from './textosCatalogo'
import { MIEMBROS, ROL } from './textosInvitar'
import { MIS_DATOS as T } from './textosMisDatos'
import { Etiqueta, Nota, Pagina, Volver } from './ui'
import {
  AvisoDeCarga,
  Bloque,
  BotonVerMas,
  Cargando,
  ConFechaHora,
  CuerpoConIndice,
  DiaDeInstante,
  enNoventaDias,
  FechaHora,
  FraseNoventa,
  PanelDescarga,
  PorDia,
  SUPERFICIE,
  useCopia,
  useVerMas,
  Vacio,
} from './PiezasMisDatos'


/**
 * P3: la API manda el celular completo (E.164) y la pantalla lo muestra como «Tu cuenta»,
 * «+56 9 •••• ••37». Un número con otra forma muestra solo sus dos últimas cifras.
 */
export function enmascararCelular(e164: string): string {
  const m = /^\+56(9)(\d{8})$/.exec(e164.replace(/\s/g, ''))
  if (m) return celularEnPantalla(`+56 9 •••• ••${m[2].slice(-2)}`)
  return `•••• ••${e164.replace(/\D/g, '').slice(-2)}`
}

export function TusDatos() {
  const { fijar } = useFamilia()
  const { estado, reintentar } = useCopia(pedirCopiaCuenta, false)

  const volver = () => {
    flushSync(() => fijar({ focoAlVolver: ID_VER_TUS_DATOS }))
    navegar('/cuenta')
  }

  const copia = estado.estado === 'lista' ? estado.copia : null
  // 5.6: no hay 404; si llega uno, es un defecto y se trata como el error.
  const aviso = estado.estado === 'no-encontrado' ? ({ estado: 'error' } as const) : estado
  const bajada = copia ? (
    <>
      {T.bajadaCuenta[0]}
      <FechaHora iso={copia.datos.generado_en} fin={T.bajadaCuenta[2]} />
    </>
  ) : undefined

  return (
    <Pagina titulo={T.cuentaTitulo} bajada={bajada} antes={<Volver onClick={volver}>{T.volverACuenta}</Volver>}>
      {estado.estado === 'cargando' && <Cargando />}
      {estado.estado !== 'cargando' && estado.estado !== 'lista' && <AvisoDeCarga e={aviso} reintentar={reintentar} />}
      {copia && (
        <>
          <PanelDescarga copia={copia} texto={T.dialogoCuenta} />
          <Nota tono="rocio" className="mt-6" icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
            <p>{T.personasEnGrupo}</p>
            <Boton variante="texto" className="text-left" onClick={() => navegar('/grupo')}>
              {T.irAGrupo}
            </Boton>
          </Nota>
          <Copia datos={copia.datos} />
        </>
      )}
    </Pagina>
  )
}

// ---------------------------------------------------------------- los bloques (5.1)

function Copia({ datos }: { datos: CopiaDatosCuenta }) {
  const conPagos = !!datos.pagos?.length
  const conCondiciones = !!datos.condiciones_aceptadas?.length
  const B = T.bloquesCuenta
  const entradas: EntradaIndice[] = [
    { id: 'tu-cuenta', texto: B.cuenta },
    { id: 'politica', texto: B.politica },
    { id: 'tus-grupos', texto: B.grupos },
    { id: 'tus-dispositivos', texto: B.dispositivos },
    { id: 'ultimos-ingresos', texto: B.eventos },
    { id: 'tus-avisos', texto: B.avisos },
    { id: 'avisos-enviados', texto: B.avisosEnviados },
    ...(conPagos ? [{ id: 'tus-pagos', texto: B.pagos }] : []),
    ...(conCondiciones ? [{ id: 'condiciones', texto: B.condiciones }] : []),
  ]
  return (
    <CuerpoConIndice entradas={entradas}>
      <Bloque id="tu-cuenta" titulo={B.cuenta}>
        <TuCuenta datos={datos} />
      </Bloque>
      <Bloque id="politica" titulo={B.politica}>
        {datos.politica ? (
          <div className="flex flex-col gap-1">
            <p className="max-w-prose text-base">
              {T.aceptasteVersion(datos.politica.version)[0]}
              <FechaHora iso={datos.politica.aceptada_en} fin="." />
            </p>
            <p className="max-w-prose text-base text-tenue break-all">
              {T.huella}
              {datos.politica.huella}
            </p>
          </div>
        ) : (
          <Vacio>{T.sinPolitica}</Vacio>
        )}
      </Bloque>
      <Bloque id="tus-grupos" titulo={B.grupos}>
        {/* 1.3 (5.3): con solo grupos dejados, la frase de vacío va arriba de ellos. */}
        {!datos.grupos.length && <Vacio>{T.sinGrupos}</Vacio>}
        {datos.grupos.length || datos.grupos_que_dejaste.length ? (
          <ul className={SUPERFICIE}>
            {datos.grupos.map((g, i) => (
              <li key={`${g.nombre}-${i}`} className="flex min-w-0 flex-col gap-1 py-4">
                <p className="font-bold break-words">{g.nombre}</p>
                {ROL[g.rol] && <p className="text-base">{ROL[g.rol]}</p>}
                <p className="text-base text-tenue">
                  {T.teUniste[0]}
                  <DiaDeInstante iso={g.unido_en} fin={T.teUniste[1]} />
                </p>
                {g.puede_ver_ficha !== null && (
                  <p className="flex items-center gap-2 text-base">
                    {g.puede_ver_ficha ? <Eye aria-hidden className="size-5 shrink-0 text-tenue" /> : <EyeOff aria-hidden className="size-5 shrink-0 text-tenue" />}
                    {g.puede_ver_ficha ? MIEMBROS.puedeVerFicha : MIEMBROS.noVeFicha}
                  </p>
                )}
              </li>
            ))}
            {/* F2 (decisión 401): los grupos de los que salió, sin el nombre, que ya no puede leer. */}
            {datos.grupos_que_dejaste.map((g, i) => (
              <li key={`dejaste-${g.unido_en}-${i}`} className="flex min-w-0 flex-col gap-1 py-4">
                <p className="font-bold break-words">{T.grupoQueDejaste}</p>
                {ROL[g.rol] && <p className="text-base">{ROL[g.rol]}</p>}
                <p className="text-base text-tenue">
                  {T.teUniste[0]}
                  <DiaDeInstante iso={g.unido_en} fin={T.teUniste[1]} />
                </p>
                {g.retirado_en && (
                  <p className="text-base text-tenue">
                    {T.saliste[0]}
                    <DiaDeInstante iso={g.retirado_en} fin={T.saliste[1]} />
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : null}
      </Bloque>
      <Bloque id="tus-dispositivos" titulo={B.dispositivos}>
        {datos.dispositivos.length ? (
          <ul className={SUPERFICIE}>
            {datos.dispositivos.map((d, i) => (
              <FilaDispositivoCopia key={`${d.nombre}-${d.creado_en}-${i}`} d={d} />
            ))}
          </ul>
        ) : (
          <Vacio>{T.sinDispositivos}</Vacio>
        )}
        <Boton variante="texto" className="self-start" onClick={() => navegar('/cuenta/donde-entraste')}>
          {T.verDondeEntraste}
        </Boton>
      </Bloque>
      <Bloque id="ultimos-ingresos" titulo={B.eventos}>
        <UltimosIngresos eventos={datos.eventos} generadoEn={datos.generado_en} />
      </Bloque>
      <Bloque id="tus-avisos" titulo={B.avisos}>
        <dl className={SUPERFICIE}>
          <div className="flex flex-col gap-0.5 py-4">
            <dt className="text-base text-tenue">{T.porCorreo}</dt>
            <dd className="font-bold">{datos.preferencia_avisos.correo ? T.si : T.no}</dd>
          </div>
          <div className="flex flex-col gap-0.5 py-4">
            <dt className="text-base text-tenue">{T.enTusTelefonos}</dt>
            <dd className="font-bold">{datos.preferencia_avisos.push ? T.si : T.no}</dd>
          </div>
        </dl>
        <p className="max-w-prose text-base text-tenue">{T.cambiarAvisos}</p>
      </Bloque>
      <Bloque id="avisos-enviados" titulo={B.avisosEnviados}>
        <AvisosEnviados avisos={datos.avisos_enviados} simulado={datos.envio_simulado} generadoEn={datos.generado_en} />
      </Bloque>
      {conPagos && (
        <Bloque id="tus-pagos" titulo={B.pagos}>
          <ul className={SUPERFICIE}>
            {datos.pagos!.map((p, i) => (
              <Pago key={`${p.referencia}-${i}`} p={p} />
            ))}
          </ul>
        </Bloque>
      )}
      {conCondiciones && (
        <Bloque id="condiciones" titulo={B.condiciones}>
          <ul className={SUPERFICIE}>
            {datos.condiciones_aceptadas!.map((c, i) => (
              <Condiciones key={`${c.huella}-${i}`} c={c} />
            ))}
          </ul>
        </Bloque>
      )}
    </CuerpoConIndice>
  )
}

// ---------------------------------------------------------------- 5.3 Tu cuenta

const FILA = 'flex flex-col gap-0.5 py-4 @3xl/main:grid @3xl/main:grid-cols-[12rem_minmax(0,1fr)] @3xl/main:gap-x-6'

function TuCuenta({ datos }: { datos: CopiaDatosCuenta }) {
  const c = datos.cuenta
  return (
    <dl className={SUPERFICIE}>
      <div className={FILA}>
        <dt className="text-base text-tenue">{T.tuNombre}</dt>
        <dd className="font-bold break-words">{c.nombre}</dd>
      </div>
      <div className={FILA}>
        <dt className="text-base text-tenue">{CUENTA_PROPIA.correo}</dt>
        <dd className="font-bold [overflow-wrap:anywhere]">{c.correo}</dd>
      </div>
      <div className={FILA}>
        <dt className="text-base text-tenue">{CUENTA_PROPIA.celular}</dt>
        {c.celular ? (
          <dd className="flex flex-col items-start gap-1">
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="cifras font-bold angosto:whitespace-normal">{enmascararCelular(c.celular)}</span>
              {c.celular_confirmado ? (
                <Etiqueta className="self-start" tono="ok">
                  <Check aria-hidden className="size-4 angosto:hidden" strokeWidth={3} />
                  {CUENTA_PROPIA.confirmado}
                </Etiqueta>
              ) : (
                <Etiqueta className="self-start">
                  <Circle aria-hidden className="size-3.5 angosto:hidden" strokeWidth={2.5} />
                  {CUENTA_PROPIA.sinConfirmar}
                </Etiqueta>
              )}
            </span>
            <span className="text-base text-tenue">{T.completoEnArchivo}</span>
          </dd>
        ) : (
          <dd className="text-tenue">{CUENTA_PROPIA.sinCelular}</dd>
        )}
      </div>
      <div className={FILA}>
        <dt className="text-base text-tenue">{T.codigosLlegan}</dt>
        <dd className="font-bold">{T.canalCodigos[c.canal_codigos] ?? ''}</dd>
      </div>
      <div className={FILA}>
        <dt className="text-base text-tenue">{T.cuentaCreada}</dt>
        <dd className="font-bold">
          <DiaDeInstante iso={c.creada_en} />
        </dd>
      </div>
    </dl>
  )
}

// ---------------------------------------------------------------- dispositivos, sin acciones ni el actual

function FilaDispositivoCopia({ d }: { d: DispositivoCopia }) {
  const Icono = iconoClase(d.clase)
  return (
    <li className="flex items-start gap-3 py-4 angosto:flex-col angosto:items-stretch angosto:gap-2">
      <Icono aria-hidden className="mt-0.5 size-6 shrink-0 text-tenue" />
      <div className="flex min-w-0 flex-col gap-1">
        <p className="max-w-full font-bold break-words">{d.nombre}</p>
        {d.cerrado_en && (
          <Etiqueta className="self-start">
            <Circle aria-hidden className="size-3.5 shrink-0" strokeWidth={2.5} />
            {T.cerrado}
          </Etiqueta>
        )}
        <p className="text-base text-tenue">
          {T.desde[0]}
          <DiaDeInstante iso={d.creado_en} fin={T.desde[1]} />
        </p>
        {d.ultimo_uso_en && (
          <p className="text-base text-tenue">
            {T.ultimaVez}
            <FechaHora iso={d.ultimo_uso_en} />
          </p>
        )}
        {d.cerrado_en && (
          <p className="text-base text-tenue">
            <ConFechaHora partes={[T.seCerro, '.']} iso={d.cerrado_en} />
          </p>
        )}
        {d.avisos_activos && (
          <p className="flex items-center gap-2 text-base">
            <Bell aria-hidden className="size-5 shrink-0 text-tenue" />
            {T.recibeAvisos}
          </p>
        )}
      </div>
    </li>
  )
}

// ---------------------------------------------------------------- Últimos ingresos (5.3 y 5.5)

/** La forma de `LineaIngreso` de MATU-55, sin `actual`: aquí nada dice «(este teléfono)». */
const comoEvento = (e: EventoCuentaCopia): EventoCuenta => ({ tipo: e.tipo, ocurrido_en: e.ocurrido_en, dispositivo: e.dispositivo ? { ...e.dispositivo, actual: false } : null })

function UltimosIngresos({ eventos, generadoEn }: { eventos: EventoCuentaCopia[]; generadoEn: string }) {
  const conocidos = eventos.map(comoEvento).filter(seMuestra)
  const { dentro, hayAnterior } = enNoventaDias(conocidos, (e) => e.ocurrido_en, generadoEn)
  const mas = useVerMas(dentro.length, 20)
  return (
    <>
      <FraseNoventa hayAnterior={hayAnterior} />
      {dentro.length ? (
        <PorDia items={dentro.slice(0, mas.visibles)} instante={(e) => e.ocurrido_en} linea={(e, i) => <LineaIngreso key={`${e.tipo}-${e.ocurrido_en}-${i}`} e={e} foco={mas.foco(i)} />} />
      ) : (
        <Vacio>{T.sinEventos}</Vacio>
      )}
      {mas.hayMas && <BotonVerMas onClick={mas.mas} />}
    </>
  )
}

// ---------------------------------------------------------------- 5.4 Avisos que te enviamos

const ICONO_RESULTADO: Record<AvisoEnviadoCopia['resultado'], LucideIcon> = {
  salio: Check,
  no_salio: X,
  en_el_piloto_no_salio: CircleDashed,
  pendiente: Clock,
}

function AvisosEnviados({ avisos, simulado, generadoEn }: { avisos: AvisoEnviadoCopia[]; simulado: boolean; generadoEn: string }) {
  const conocidos = avisos.filter((a) => Object.hasOwn(ICONO_RESULTADO, a.resultado))
  const { dentro, hayAnterior } = enNoventaDias(conocidos, (a) => a.enviado_en ?? a.creado_en, generadoEn)
  const mas = useVerMas(dentro.length, 20)
  return (
    <>
      <FraseNoventa hayAnterior={hayAnterior} />
      {simulado && (
        <Nota tono="atenta" icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
          {T.pilotoAvisos}
        </Nota>
      )}
      {dentro.length ? (
        <ol className={SUPERFICIE}>
          {dentro.slice(0, mas.visibles).map((a, i) => {
            const Icono = ICONO_RESULTADO[a.resultado]
            const foco = mas.foco(i)
            return (
              <li key={`${a.creado_en}-${i}`} ref={foco} tabIndex={foco ? -1 : undefined} className="flex items-start gap-3 py-3 outline-none">
                <Icono aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue" />
                <span className="min-w-0 text-base tabular-nums break-words">
                  <FechaHora iso={a.enviado_en ?? a.creado_en} />
                  {` · ${T.canalAviso[a.canal] ?? ''} · ${T.resultadoAviso[a.resultado]}`}
                </span>
              </li>
            )
          })}
        </ol>
      ) : (
        <Vacio>{T.sinAvisosEnviados}</Vacio>
      )}
      {mas.hayMas && <BotonVerMas onClick={mas.mas} />}
    </>
  )
}

// ---------------------------------------------------------------- 5.4 Tus pagos y las condiciones

function Pago({ p }: { p: PagoCuentaCopia }) {
  return (
    <li className="flex min-w-0 flex-col gap-1 py-4">
      <h3 className="text-lg font-bold break-words">
        {p.referencia ? (
          <>
            {T.pago('')}
            <span className="cifras">{p.referencia}</span>
          </>
        ) : (
          <>
            {T.pagoDel}
            <DiaDeInstante iso={p.pagado_en} />
          </>
        )}
      </h3>
      <p className="text-base text-tenue">
        <FechaHora iso={p.pagado_en} />
      </p>
      <p className="max-w-prose text-base break-words">
        <span className="cifras">{pesos(p.cobrado)}</span>
        {T.enGrupo(p.grupo)}
      </p>
      <p className="max-w-prose text-base">
        {p.tarjeta ? (
          <>
            {T.tarjeta(p.tarjeta.tipo)}
            <span className="cifras">{p.tarjeta.ultimos4}</span>
            {T.cuotas(p.tarjeta.cuotas)}
          </>
        ) : (
          T.sinTarjeta
        )}
      </p>
      {p.devuelto > 0 && (
        <p className="text-base">
          {T.devuelto}
          <span className="cifras">{pesos(p.devuelto)}</span>
        </p>
      )}
      {/* F3 (decisión 402): el mismo código de su comprobante. */}
      {p.codigo_autorizacion && (
        <p className="text-base">
          {T.codigoAutorizacion}
          <span className="cifras">{p.codigo_autorizacion}</span>
        </p>
      )}
      {p.pago_de_prueba && <p className="max-w-prose text-base font-bold">{T.pagoDePrueba}</p>}
    </li>
  )
}

function Condiciones({ c }: { c: CondicionesCopia }) {
  return (
    <li className="flex min-w-0 flex-col gap-1 py-4">
      <p className="font-bold">
        {T.versionEl(c.version)[0]}
        <FechaHora iso={c.aceptadas_en} fin="." />
      </p>
      <p className="max-w-prose text-base break-words">{c.referencia ? T.paraPedido(c.grupo, c.referencia) : T.paraPedidoSinPagar(c.grupo)}</p>
      <p className="max-w-prose text-base text-tenue break-all">
        {T.huella}
        {c.huella}
      </p>
    </li>
  )
}

