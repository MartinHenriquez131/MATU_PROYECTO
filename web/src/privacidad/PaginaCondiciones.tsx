// La página pública /condiciones-pedido (MATU-61, especificación 9.8 y O6): las condiciones del
// pedido que enlaza el resumen antes de pagar, con el armado de /privacidad (MATU-75). Se abre en
// otra pestaña para no perder el resumen. Sin sesión, sin cookies y sin registrar quién la lee:
// `GET /v1/condiciones-pedido` va por `apiPublica`. Sin índice: son secciones cortas.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { CircleAlert } from 'lucide-react'
import { leerCondiciones, versionDeLaDireccion, type CondicionesPedido } from '../compartido/api/pedido'
import { fechaCorta } from '../compartido/fechas'
import { POLITICA } from '../compartido/textosPolitica'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { DistintivoPiloto, Logo } from '../compartido/ui/Marca'
import { useDemora } from '../compartido/useDemora'
import { Documento } from './Documento'
import { leerMarkdown } from './markdown'
import { ESTADOS } from './textos'

/** [lenguaje 31] El título de la página y del documento. */
const TITULO = 'Condiciones del pedido'
const TITULO_DOCUMENTO = 'Condiciones del pedido · MATU'

type Carga = { estado: 'cargando' } | { estado: 'error'; reintentando: boolean } | { estado: 'lista'; condiciones: CondicionesPedido }

function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="mt-2 text-base text-tenue">
      {ver ? ESTADOS.cargando : ''}
    </p>
  )
}

function Contenido({ condiciones }: { condiciones: CondicionesPedido }) {
  const secciones = useMemo(() => leerMarkdown(condiciones.texto), [condiciones.texto])
  return (
    <>
      <p className="mt-2 text-base text-tenue">
        {POLITICA.version} <span className="cifras">{condiciones.version}</span> {POLITICA.actualizada}{' '}
        <span className="cifras">{fechaCorta(condiciones.actualizada_en)}</span>
      </p>
      <div className="mt-8">
        <Documento secciones={secciones} />
      </div>
    </>
  )
}

export function PaginaCondiciones() {
  const [carga, setCarga] = useState<Carga>({ estado: 'cargando' })
  // MATU-62 (7.5.3, P4): el comprobante enlaza a la versión aceptada, `?version=0.2`. Sin ella, la vigente.
  const [version] = useState(() => versionDeLaDireccion(window.location.search))

  const cargar = useCallback(async (reintento: boolean) => {
    if (reintento) setCarga({ estado: 'error', reintentando: true })
    try {
      setCarga({ estado: 'lista', condiciones: await leerCondiciones(version) })
    } catch {
      setCarga({ estado: 'error', reintentando: false })
    }
  }, [version])

  useEffect(() => {
    document.title = TITULO_DOCUMENTO
    void cargar(false)
  }, [cargar])

  return (
    <>
      <header className="border-b border-linea bg-hoja">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 angosto:px-2 @3xl/app:px-10 py-3">
          <span className="flex items-center gap-2.5">
            <Logo className="size-8" />
            <span className="titular text-xl">MATU</span>
          </span>
          <DistintivoPiloto className="ms-auto" />
        </div>
      </header>
      <main id="contenido" tabIndex={-1} className="@container/main px-4 angosto:px-2 @3xl/app:px-10 pt-6 @3xl/app:pt-14 pb-16 outline-none">
        <div className="mx-auto max-w-6xl">
          <h1 id="titulo-pagina" className="titular text-3xl @2xl/main:text-5xl angosto:text-2xl">
            {TITULO}
          </h1>
          {carga.estado === 'cargando' && <Cargando />}
          {carga.estado === 'error' && (
            <div className="mt-4 flex flex-col items-start gap-4">
              <Anunciado urgencia="alert" como="p" className="flex max-w-prose items-start gap-2 angosto:block text-base text-tinta">
                <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue angosto:mt-0 angosto:mr-1.5 angosto:inline angosto:align-middle" />
                <span className="min-w-0">
                  <b className="font-bold">{ESTADOS.errorTitulo}</b> {ESTADOS.errorConexion}
                </span>
              </Anunciado>
              <Boton variante="secundario" ocupado={carga.reintentando} textoOcupado={ESTADOS.cargando} onClick={() => void cargar(true)}>
                {ESTADOS.volverAIntentar}
              </Boton>
            </div>
          )}
          {carga.estado === 'lista' && <Contenido condiciones={carga.condiciones} />}
        </div>
      </main>
    </>
  )
}
