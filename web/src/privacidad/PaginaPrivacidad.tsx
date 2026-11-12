// La página pública /privacidad (especificación docs/diseno/matu-75-privacidad.md, sección 1).
// Condiciones del analista: sin sesión, sin cookies, sin analítica y sin registrar quién la lee; con
// el distintivo del piloto, y sin leer el fragmento ni el token del relevo. Por eso main.tsx la monta
// en su propia rama, sin `ProveedorFamilia`, y `GET /v1/politica` va por `apiPublica`, sin cookies.
// El marco es propio: el logo no es un enlace y no hay navegación, «Entrar» ni «Salir».
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CircleAlert } from 'lucide-react'
import { leerPolitica, type Politica } from '../compartido/api/politica'
import { fechaCorta } from '../compartido/fechas'
import { POLITICA } from '../compartido/textosPolitica'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { IndiceAncho, IndiceDesplegable } from '../compartido/ui/Indice'
import { DistintivoPiloto, Logo } from '../compartido/ui/Marca'
import { useDemora } from '../compartido/useDemora'
import { Documento } from './Documento'
import { leerMarkdown } from './markdown'
import { ESTADOS } from './textos'

type Carga = { estado: 'cargando' } | { estado: 'error'; reintentando: boolean } | { estado: 'lista'; politica: Politica }

function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="mt-2 text-base text-tenue">
      {ver ? ESTADOS.cargando : ''}
    </p>
  )
}

/** Sin conexión, 5xx o la política sin publicar (503): en tono neutro, como el relevo. Nada se perdió. */
function ErrorAlCargar({ reintentando, reintentar }: { reintentando: boolean; reintentar: () => void }) {
  return (
    <div className="mt-4 flex flex-col items-start gap-4">
      <Anunciado urgencia="alert" como="p" className="flex max-w-prose items-start gap-2 angosto:block text-base text-tinta">
        <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue angosto:mt-0 angosto:mr-1.5 angosto:inline angosto:align-middle" />
        <span className="min-w-0">
          <b className="font-bold">{ESTADOS.errorTitulo}</b> {ESTADOS.errorConexion}
        </span>
      </Anunciado>
      <Boton variante="secundario" ocupado={reintentando} textoOcupado={ESTADOS.cargando} onClick={reintentar}>
        {ESTADOS.volverAIntentar}
      </Boton>
    </div>
  )
}

function Contenido({ politica }: { politica: Politica }) {
  const secciones = useMemo(() => leerMarkdown(politica.texto), [politica.texto])
  const entradas = useMemo(() => secciones.flatMap((s) => (s.titulo ? [{ id: s.titulo.id, texto: s.titulo.texto }] : [])), [secciones])
  const indice = useRef<HTMLDetailsElement>(null)
  const resumen = useRef<HTMLElement>(null)

  // «Volver al índice»: lo abre si estaba cerrado y deja el foco en su `summary`.
  const volver = useCallback(() => {
    if (indice.current) indice.current.open = true
    resumen.current?.focus()
  }, [])

  return (
    <>
      <p className="mt-2 text-base text-tenue">
        {POLITICA.version} <span className="cifras">{politica.version}</span> {POLITICA.actualizada}{' '}
        <span className="cifras">{fechaCorta(politica.actualizada_en)}</span>
      </p>

      {/* Teléfono y texto al 200 %: el índice es un `details` cerrado, antes de «En un minuto». */}
      <IndiceDesplegable titulo={POLITICA.indice} entradas={entradas} detalles={indice} resumen={resumen} />

      <div className="mt-8 grid grid-cols-1 gap-10 @4xl/main:grid-cols-[var(--container-xs)_minmax(0,1fr)] @4xl/main:gap-16">
        {/* Pantalla ancha: columna fija a la izquierda, que sigue a la vista al desplazarse. */}
        <IndiceAncho titulo={POLITICA.indice} entradas={entradas} />
        <Documento secciones={secciones} alVolver={volver} />
      </div>
    </>
  )
}

export function PaginaPrivacidad() {
  const [carga, setCarga] = useState<Carga>({ estado: 'cargando' })

  const cargar = useCallback(async (reintento: boolean) => {
    if (reintento) setCarga({ estado: 'error', reintentando: true })
    try {
      setCarga({ estado: 'lista', politica: await leerPolitica() })
    } catch {
      setCarga({ estado: 'error', reintentando: false })
    }
  }, [])

  useEffect(() => {
    document.title = POLITICA.tituloDocumento
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
            {POLITICA.titulo}
          </h1>
          {carga.estado === 'cargando' && <Cargando />}
          {carga.estado === 'error' && <ErrorAlCargar reintentando={carga.reintentando} reintentar={() => void cargar(true)} />}
          {carga.estado === 'lista' && <Contenido politica={carga.politica} />}
        </div>
      </main>
    </>
  )
}
