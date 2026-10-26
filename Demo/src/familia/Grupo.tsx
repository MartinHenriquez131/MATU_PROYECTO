// Grupo familiar: a quién se cuida, con qué permiso, y quiénes forman el grupo. Solo lectura.
import type { ReactNode } from 'react'
import { Link2, ShieldCheck } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { nombrePila, pilaFamilia } from '../demo/logica'
import { APOYOS, AVISO_CUIDADOR, CALIDADES } from '../demo/datos'
import { accesoVigente, fmtFecha, fmtRestante } from '../demo/calculos'
import { Boton, Etiqueta, Subtitulo } from '../components/Ui'
import { Columna, Columnas, Pagina } from './Shell'

function Dato({ termino, children }: { termino: string; children: ReactNode }) {
  return (
    <div className="grid gap-x-6 gap-y-0.5 border-b border-linea py-2.5 last:border-0 @md:grid-cols-[12rem_minmax(0,1fr)]">
      <dt className="text-tenue">{termino}</dt>
      <dd>{children}</dd>
    </div>
  )
}

export function Grupo() {
  const { s, haz } = useDemo()
  const p = s.persona
  const c = s.consentimiento
  const pila = nombrePila(s)
  const nombre = s.cuenta?.nombre || 'Carmen'
  const calidad = c ? CALIDADES.find((x) => x.valor === c.calidad) : null
  const vigentes = s.accesos.filter((a) => accesoVigente(a, s.ahora))
  return (
    <Pagina titulo="Grupo familiar" bajada={`Las personas que organizan el cuidado de ${pila}.`}>
      <Columnas>
        <Columna etiqueta="Persona cuidada y permiso">
          <section aria-labelledby="persona-t" className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-3">
              <Subtitulo id="persona-t">{p?.nombre ?? pila}</Subtitulo>
              {p?.idReal ? <Etiqueta tono="ok">Guardada en la API</Etiqueta> : <Etiqueta>Simulada</Etiqueta>}
            </div>
            <dl className="bg-hoja px-4 ring-1 ring-linea">
              <Dato termino="Le dicen">{p?.nombrePila ?? pila}</Dato>
              <Dato termino="Apoyo en el día a día">{APOYOS.find((a) => a.valor === p?.apoyo)?.texto ?? 'Sin indicar'}</Dato>
              <Dato termino="Dirección">{p?.direccion || <span className="text-tenue">Sin dirección. Se pide con el primer pedido.</span>}</Dato>
            </dl>
          </section>
          <section aria-labelledby="permiso-t" className="flex flex-col gap-2">
            <Subtitulo id="permiso-t">Permiso para guardar su ficha</Subtitulo>
            {c && calidad ? (
              <dl className="bg-hoja px-4 ring-1 ring-linea">
                <Dato termino="En calidad de">{calidad.texto.replace('Ella', pila)}</Dato>
                <Dato termino="Lo registró">{nombre}</Dato>
                <Dato termino="Registrado">
                  <span className="cifras">{fmtFecha(c.minuto)}</span>, con la política de privacidad 0.9
                </Dato>
                {c.avisoVersion && (
                  <Dato termino="Aviso aceptado">
                    «{AVISO_CUIDADOR.titulo}», versión {c.avisoVersion}
                  </Dato>
                )}
                {c.referenciaDocumento && <Dato termino="Documento">{c.referenciaDocumento}</Dato>}
                {c.revisionMinuto !== null && (
                  <Dato termino="Revisión">
                    Te pediremos confirmarlo el <span className="cifras">{fmtFecha(c.revisionMinuto)}</span>
                  </Dato>
                )}
              </dl>
            ) : (
              <p className="text-tenue">Todavía no hay un permiso registrado.</p>
            )}
            <p className="flex gap-2 text-base text-tenue">
              <ShieldCheck aria-hidden className="mt-0.5 size-4.5 shrink-0" />
              {pila} o su representante legal pueden pedir en cualquier momento que se borren sus datos.
            </p>
          </section>
        </Columna>
        <Columna etiqueta="Integrantes">
          <section aria-labelledby="integrantes-t" className="flex flex-col gap-2">
            <Subtitulo id="integrantes-t">Integrantes</Subtitulo>
            <ul className="flex flex-col divide-y divide-linea bg-hoja ring-1 ring-linea">
              <li className="flex items-center gap-3 px-4 py-3">
                <span aria-hidden className="grid size-10 place-items-center rounded-full bg-rocio font-bold text-pino">
                  {nombre.slice(0, 1)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-bold">{nombre}, tú</span>
                  <span className="text-sm text-tenue">Administra el grupo</span>
                </span>
              </li>
              <li className="flex items-center gap-3 px-4 py-3">
                <span aria-hidden className="grid size-10 place-items-center rounded-full bg-tinta/7 font-bold text-tenue">
                  R
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-bold">Rodrigo, su hijo</span>
                  <span className="text-sm text-tenue">También puede editar la ficha</span>
                </span>
              </li>
            </ul>
          </section>
          <section aria-labelledby="relevos-t" className="flex flex-col gap-2">
            <Subtitulo id="relevos-t">Relevos con acceso ahora</Subtitulo>
            {vigentes.length === 0 ? (
              <p className="text-tenue">Nadie fuera del grupo puede ver la ficha ahora.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {vigentes.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-baseline justify-between gap-2 border-l-4 border-pino bg-hoja px-4 py-2.5">
                    <span className="flex items-center gap-2 font-bold">
                      <Link2 aria-hidden className="size-4.5 text-pino" />
                      {a.nombre}
                    </span>
                    <span className="text-tenue tabular-nums">vence en {fmtRestante(a.venceMin, s.ahora)}</span>
                  </li>
                ))}
              </ul>
            )}
            <Boton variante="texto" className="self-start" icono={<Link2 aria-hidden className="size-5" />} onClick={() => haz((x) => pilaFamilia(x, ['ficha', 'enlaces']))}>
              Ver los enlaces de la ficha
            </Boton>
          </section>
        </Columna>
      </Columnas>
    </Pagina>
  )
}
