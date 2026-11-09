// La página pública /privacidad (especificación docs/diseno/matu-75-privacidad.md, sección 1).
// Condiciones del analista: sin sesión, sin cookies, sin analítica y sin registrar quién la lee; con
// el distintivo del piloto, y sin leer el fragmento ni el token del relevo. Por eso main.tsx la monta
// en su propia rama, sin `ProveedorFamilia`, y `GET /v1/politica` va por `apiPublica`, sin cookies.
// El marco es propio: el logo no es un enlace y no hay navegación, «Entrar» ni «Salir».
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, CircleAlert } from 'lucide-react'
import { leerPolitica, type Politica } from '../compartido/api/politica'
import { fechaCorta } from '../compartido/fechas'
import { POLITICA } from '../compartido/textosPolitica'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { DistintivoPiloto, Logo } from '../compartido/ui/Marca'
import { useDemora } from '../compartido/useDemora'
import { Documento } from './Documento'
import { leerMarkdown, type Seccion } from './markdown'
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

function ListaIndice({ secciones }: { secciones: Seccion[] }) {
  return (
    // `role="list"`: Safari quita la semántica de lista cuando no hay viñetas.
    <ul role="list" className="flex flex-col">
      {secciones.map(
        (s) =>
          s.titulo && (
            <li key={s.titulo.id}>
              <a
                href={`#${s.titulo.id}`}
                className="flex min-h-12 items-center rounded-lg px-3 angosto:px-2 py-2 text-base leading-snug text-turquesa hover:bg-rocio hover:underline"
              >
                {s.titulo.texto}
              </a>
            </li>
          ),
      )}
    </ul>
  )
}

function Contenido({ politica }: { politica: Politica }) {
  const secciones = useMemo(() => leerMarkdown(politica.texto), [politica.texto])
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
      <details id="indice" ref={indice} className="group mt-6 rounded-xl bg-hoja ring-1 ring-linea @4xl/main:hidden">
        <summary
          ref={resumen}
          className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-2 px-4 angosto:px-2 font-bold text-turquesa [&::-webkit-details-marker]:hidden"
        >
          {POLITICA.indice}
          <ChevronDown aria-hidden className="size-5 shrink-0 group-open:rotate-180" />
        </summary>
        <nav aria-label={POLITICA.indice} className="px-4 angosto:px-2 pb-3">
          <ListaIndice secciones={secciones} />
        </nav>
      </details>

      <div className="mt-8 grid grid-cols-1 gap-10 @4xl/main:grid-cols-[var(--container-xs)_minmax(0,1fr)] @4xl/main:gap-16">
        {/* Pantalla ancha: columna fija a la izquierda, que sigue a la vista al desplazarse. */}
        <nav aria-labelledby="indice-ancho-t" className="sticky top-6 hidden max-h-[calc(100dvh-3rem)] self-start overflow-y-auto [scrollbar-width:thin] @4xl/main:block">
          <h2 id="indice-ancho-t" className="px-3 text-base font-bold text-tenue">
            {POLITICA.indice}
          </h2>
          <ListaIndice secciones={secciones} />
        </nav>
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
