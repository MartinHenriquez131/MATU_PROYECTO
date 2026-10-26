// Inicio: la hoja de la ficha a la izquierda y, a la derecha, lo que necesita atención, ordenado
// por urgencia. Resumen antes que detalle.
import type { ReactNode } from 'react'
import { Check, Circle, Link2, PackageOpen, Share2 } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { abrirCampo, completados, ir, nombrePila, pilaFamilia, siguienteCampoVacio } from '../demo/logica'
import { CAMPOS, TEXTO_CAMPO } from '../demo/datos'
import { DIA, accesoVigente, diasRestantes, fmtCuando, fmtFecha, fmtRestante, nivel } from '../demo/calculos'
import type { Cambio } from '../demo/estado'
import { Acciones, BarraCampos, BarraDias, Boton, EtiquetaNivel, Hoja, Subtitulo } from '../components/Ui'
import { Columna, Columnas, Pagina } from './Shell'

const ESTADO_PEDIDO: Record<string, string> = {
  pagado: 'Pagado. La farmacia lo va a preparar.',
  preparando: 'La farmacia lo está preparando.',
  listo: 'Listo para retiro.',
  en_camino: 'En camino.',
}

function Atencion({
  franja,
  titulo,
  children,
  accion,
  onAccion,
}: {
  franja: string
  titulo: ReactNode
  children?: ReactNode
  accion: string
  onAccion: () => void
}) {
  return (
    <li className={`flex flex-col gap-2 border-l-4 bg-hoja py-3.5 pr-4 pl-4 ${franja}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">{titulo}</div>
      {children}
      <button type="button" onClick={onAccion} className="min-h-10 self-start font-bold text-pino underline decoration-pino/40 underline-offset-4 hover:decoration-pino">
        {accion}
      </button>
    </li>
  )
}

export function Inicio() {
  const { s, haz } = useDemo()
  const pila = nombrePila(s)
  const hechos = completados(s)
  const nombre = s.cuenta?.nombre || ''
  const declarados = [...s.insumos.filter((i) => i.declarado)].sort((a, b) => diasRestantes(a) - diasRestantes(b))
  const urgente = declarados[0]
  const vigentes = s.accesos.filter((a) => accesoVigente(a, s.ahora))
  const p = s.pedido
  const pedidoEnCurso = p && p.estado !== 'borrador' && p.estado !== 'entregado'
  const ultimaApertura = s.eventos.find((e) => e.texto.includes('abrió'))
  const textoAvance =
    hechos === 0
      ? 'Empieza por «Su día». Con eso alguien ya podría reemplazarte unas horas.'
      : hechos < 3
        ? 'Con lo que ya escribiste, alguien podría reemplazarte unas horas.'
        : 'Lista. Quien te reemplace va a saber qué hacer.'
  const a = (c: Cambio) => () => haz(c)

  return (
    <Pagina titulo={nombre ? `Hola, ${nombre}` : 'Hola'} bajada={`Esto es lo que hay hoy en el cuidado de ${pila}.`}>
      <Columnas izquierda="angosta">
        <Columna etiqueta="Ficha de relevo">
          <Hoja inclinada etiqueta={`Ficha de ${pila}`}>
            <h2 className="titular text-2xl @2xl:text-4xl">Ficha de {pila}</h2>
            <ul className="renglones mt-3 leading-7">
              {CAMPOS.map((c) => {
                const listo = !!s.ficha[c].texto.trim()
                return (
                  <li key={c} className="flex items-center justify-between gap-2">
                    <span className={listo ? '' : 'text-tenue'}>{TEXTO_CAMPO[c].titulo}</span>
                    <span className={`inline-flex items-center gap-1 text-sm font-bold ${listo ? 'text-ok' : 'text-tenue'}`}>
                      {listo ? <Check aria-hidden className="size-4" strokeWidth={3} /> : <Circle aria-hidden className="size-3.5" strokeWidth={2.5} />}
                      {listo ? 'Listo' : 'Falta'}
                    </span>
                  </li>
                )
              })}
            </ul>
            <BarraCampos hechos={hechos} className="mt-4" />
            <p className="mt-2 text-base text-tenue">{textoAvance}</p>
          </Hoja>
          <Acciones>
            {hechos < 3 && <Boton onClick={a((x) => abrirCampo(x, siguienteCampoVacio(x)!))}>Completar la ficha</Boton>}
            <Boton variante={hechos < 3 ? 'secundario' : 'primario'} icono={<Share2 aria-hidden className="size-5" />} onClick={a((x) => pilaFamilia(x, ['ficha', 'compartir']))}>
              Compartir con un relevo
            </Boton>
          </Acciones>
        </Columna>

        <Columna etiqueta="Lo que necesita atención">
          <Subtitulo>Lo que necesita atención</Subtitulo>
          <ul className="flex flex-col gap-3">
            {urgente ? (
              <Atencion
                franja={{ pronto: 'border-pronto', atenta: 'border-atenta', tranquila: 'border-ok' }[nivel(diasRestantes(urgente))]}
                titulo={
                  <>
                    <span className="font-bold">
                      {nivel(diasRestantes(urgente)) === 'tranquila' ? 'Los insumos alcanzan' : `Se acaban ${urgente.corto}`}
                    </span>
                    <EtiquetaNivel nivel={nivel(diasRestantes(urgente))} />
                  </>
                }
                accion="Ver qué reponer"
                onAccion={a((x) => pilaFamilia(x, ['se-acaba']))}
              >
                <p>
                  Alcanzan para <b className="cifras">{diasRestantes(urgente)} días</b>, hasta el{' '}
                  <span className="cifras">{fmtFecha(s.ahora + diasRestantes(urgente) * DIA)}</span>.
                </p>
                <BarraDias dias={diasRestantes(urgente)} nivel={nivel(diasRestantes(urgente))} />
              </Atencion>
            ) : (
              <Atencion
                franja="border-tinta/20"
                titulo={
                  <span className="flex items-center gap-2 font-bold">
                    <PackageOpen aria-hidden className="size-5 text-pino" />
                    ¿Qué usa {pila}?
                  </span>
                }
                accion="Empezar"
                onAccion={a((x) => ir(x, 'se-acaba'))}
              >
                <p className="text-tenue">Cuéntanos de un producto y te avisamos antes de que se acabe.</p>
              </Atencion>
            )}

            {pedidoEnCurso && (
              <Atencion
                franja="border-pino"
                titulo={<span className="font-bold">Pedido #{p.numero}</span>}
                accion="Ver el pedido"
                onAccion={a((x) => pilaFamilia(x, ['seguimiento']))}
              >
                <p>{ESTADO_PEDIDO[p.estado]}</p>
              </Atencion>
            )}

            {vigentes.length > 0 ? (
              <Atencion
                franja="border-pino"
                titulo={
                  <span className="flex items-center gap-2 font-bold">
                    <Link2 aria-hidden className="size-5 text-pino" />
                    {vigentes[0].nombre} puede ver la ficha{vigentes.length > 1 ? ` y ${vigentes.length - 1} más` : ''}
                  </span>
                }
                accion="Ver los enlaces"
                onAccion={a((x) => pilaFamilia(x, ['ficha', 'enlaces']))}
              >
                <p>
                  El enlace vence en <span className="cifras">{fmtRestante(vigentes[0].venceMin, s.ahora)}</span>.
                </p>
              </Atencion>
            ) : (
              hechos > 0 && (
                <Atencion
                  franja="border-tinta/20"
                  titulo={<span className="font-bold">Nadie más puede ver la ficha ahora</span>}
                  accion="Compartir con un relevo"
                  onAccion={a((x) => pilaFamilia(x, ['ficha', 'compartir']))}
                >
                  <p className="text-tenue">Cuando salgas, compártela con quien te reemplace, con un PIN y hasta cuándo tú digas.</p>
                </Atencion>
              )
            )}

            {ultimaApertura && (
              <Atencion
                franja="border-tinta/20"
                titulo={<span className="font-bold">{ultimaApertura.texto}</span>}
                accion="Ver quién la vio"
                onAccion={a((x) => pilaFamilia(x, ['ficha', 'quien-vio']))}
              >
                <p className="cifras text-tenue">{fmtCuando(ultimaApertura.minuto, s.ahora)}</p>
              </Atencion>
            )}
          </ul>
        </Columna>
      </Columnas>
    </Pagina>
  )
}
