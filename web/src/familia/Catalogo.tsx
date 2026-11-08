// «Catálogo», la tercera pestaña de Insumos (MATU-59, RF-20, capa 3; especificación
// docs/diseno/matu-59-catalogo.md v1.0, con N1 y N2 decididas por Jorge el 08-11). Los productos
// por categoría y, en cada uno, cada comercio con su precio y si lo tiene. No se pide nada desde
// aquí (D4): sin botones ni enlaces dentro de las tarjetas.
//
// Igual para los cuatro roles: no depende del grupo ni de la persona, y no se cruza con lo que
// anotó la familia. Se pide cada vez que se abre la pantalla. Nada se guarda en el navegador ni
// va en la URL; si falla, nunca se muestra un catálogo viejo.
import { useEffect, useState } from 'react'
import { CircleCheck, CircleMinus, CloudOff, Info, Store } from 'lucide-react'
import { verCatalogo, type Catalogo as CatalogoApi, type CategoriaCatalogo, type OfertaCatalogo, type ProductoCatalogo } from '../compartido/api/catalogo'
import { esVencida } from '../compartido/api/sesion'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { useDemora } from './Estados'
import { PestanasInsumos } from './Insumos'
import { GENERAL } from './textos'
import { CATALOGO, pesos } from './textosCatalogo'
import { Etiqueta, Nota, Titulo } from './ui'

type Carga = 'cargando' | 'listo' | 'red'

/**
 * 3.1: categorías por `orden` (la API ya las manda así; el orden es estable). Productos y comercios en
 * el orden en que llegan, nunca por precio (D6). Se esconde un producto sin ofertas y una categoría
 * sin productos, por si llegan.
 */
function visibles(c: CatalogoApi): CategoriaCatalogo[] {
  return [...c.categorias]
    .sort((x, y) => x.orden - y.orden)
    .map((cat) => ({ ...cat, productos: cat.productos.filter((p) => p.comercios.length > 0) }))
    .filter((cat) => cat.productos.length > 0)
}

export function Catalogo() {
  const [carga, setCarga] = useState<Carga>('cargando')
  const [catalogo, setCatalogo] = useState<CatalogoApi | null>(null)

  const cargar = async () => {
    setCarga('cargando')
    setCatalogo(null)
    try {
      setCatalogo(await verCatalogo())
      setCarga('listo')
    } catch (x) {
      // 401: la app renueva la entrada una vez y, si falla, lleva a Entrar.
      if (esVencida(x)) return
      setCarga('red')
    }
  }

  // 3.2: una vez al llegar, y otra cada vez que se vuelve a entrar (la pantalla se monta de nuevo).
  useEffect(() => {
    void cargar()
  }, [])

  const cuerpo = () => {
    if (carga === 'cargando') return <Cargando />
    if (carga === 'red')
      return (
        <div className="mt-2 flex flex-col items-start gap-5">
          <span className="grid size-16 place-items-center rounded-2xl bg-tinta/7 text-tenue">
            <CloudOff aria-hidden className="size-9" />
          </span>
          <Anunciado urgencia="alert" como="p" className="max-w-prose text-lg">
            {CATALOGO.errCarga}
          </Anunciado>
          <Boton onClick={() => void cargar()}>{GENERAL.volverAIntentar}</Boton>
        </div>
      )
    const categorias = catalogo ? visibles(catalogo) : []
    if (!categorias.length)
      return (
        <div className="mt-2 flex flex-col items-start gap-5">
          <span className="grid size-16 place-items-center rounded-2xl bg-tinta/7 text-tenue">
            <Store aria-hidden className="size-9" />
          </span>
          <p className="max-w-prose text-lg">{CATALOGO.vacio}</p>
        </div>
      )
    const deEjemplo = catalogo!.precios_de_ejemplo
    return (
      <div>
        {deEjemplo && (
          <Nota
            tono="atenta"
            borde
            titulo={CATALOGO.avisoTitulo}
            icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}
            iconoEnLinea
            className="mt-1"
          >
            <p>{CATALOGO.aviso}</p>
          </Nota>
        )}
        <p className="mt-4 max-w-prose text-base text-tenue">{CATALOGO.notaStock}</p>
        <p className="mt-1 max-w-prose text-base text-tenue">{CATALOGO.notaEnvio}</p>
        {categorias.map((cat, i) => (
          <Categoria key={cat.id} categoria={cat} primera={i === 0} deEjemplo={deEjemplo} />
        ))}
      </div>
    )
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <PestanasInsumos activa="/insumos/catalogo" />
      <div>
        <Titulo className="text-3xl @2xl/main:text-5xl">{CATALOGO.titulo}</Titulo>
        <p className="mt-1.5 max-w-prose text-base text-tenue">{CATALOGO.bajada}</p>
      </div>
      {cuerpo()}
    </div>
  )
}

/** 5.1: «Cargando…» a los 400 ms, sin esqueleto ni ícono que gira. */
function Cargando() {
  const ver = useDemora()
  return (
    <div aria-busy="true" className="mt-2">
      <p role="status" className="text-lg text-tenue">
        {ver ? GENERAL.cargando : ''}
      </p>
    </div>
  )
}

function Categoria({ categoria, primera, deEjemplo }: { categoria: CategoriaCatalogo; primera: boolean; deEjemplo: boolean }) {
  const idTitulo = `categoria-${categoria.id}`
  return (
    <section aria-labelledby={idTitulo}>
      <h2 id={idTitulo} className={`titular mb-4 text-2xl ${primera ? 'mt-8' : 'mt-10'}`}>
        {categoria.nombre}
      </h2>
      <ul className="flex max-w-6xl flex-col gap-4">
        {categoria.productos.map((p) => (
          <Producto key={p.id} producto={p} deEjemplo={deEjemplo} />
        ))}
      </ul>
    </section>
  )
}

/** 4.2: la tarjeta. No es un botón ni un enlace: no recibe foco ni cambia al pasar el puntero. */
function Producto({ producto, deEjemplo }: { producto: ProductoCatalogo; deEjemplo: boolean }) {
  const ninguno = producto.comercios.every((o) => !o.disponible)
  const presentacion = producto.presentacion.trim()
  return (
    <li className="@container/producto rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
      {/* 4.7: el orden del DOM no cambia; en ancho, el producto y el retracto a la izquierda y los comercios a la derecha. */}
      <div className="grid grid-cols-1 gap-x-8 @3xl/producto:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] @3xl/producto:grid-rows-[auto_1fr]">
        <div className="min-w-0 @3xl/producto:col-start-1 @3xl/producto:row-start-1">
          <h3 className="text-xl font-bold break-words">{producto.nombre}</h3>
          {/* N3: si la presentación repite el nombre, no se muestra. */}
          {presentacion && presentacion !== producto.nombre.trim() && <p className="mt-0.5 text-base text-tenue">{presentacion}</p>}
          {ninguno && (
            <div className="mt-2">
              <Etiqueta tono="neutro">
                <CircleMinus aria-hidden className="size-4 shrink-0" />
                {CATALOGO.noDisponible}
              </Etiqueta>
            </div>
          )}
        </div>
        <div className="@container/oferta mt-3 min-w-0 @3xl/producto:col-start-2 @3xl/producto:row-span-2 @3xl/producto:row-start-1 @3xl/producto:mt-0">
          <ul className="grid grid-cols-1 gap-x-6 gap-y-3 @md/oferta:grid-cols-2">
            {producto.comercios.map((o) => (
              <Comercio key={o.oferta_id} oferta={o} deEjemplo={deEjemplo} />
            ))}
          </ul>
        </div>
        {/* 4.4: uno por producto, con letra igual al precio (text-lg), y elegido solo por el campo. */}
        <p className="mt-4 max-w-prose border-t border-linea pt-3 text-lg text-tinta @3xl/producto:col-start-1 @3xl/producto:row-start-2 @3xl/producto:mt-3">
          <strong className="font-bold">{CATALOGO.retractoTitulo}</strong> {CATALOGO.retracto}
          {producto.retracto_pierde_al_abrir && ` ${CATALOGO.retractoSello}`}
        </p>
      </div>
    </li>
  )
}

/** 4.3: cada comercio con su precio, aunque no lo tenga, sin tachar ni resaltar. */
function Comercio({ oferta, deEjemplo }: { oferta: OfertaCatalogo; deEjemplo: boolean }) {
  const nombre = oferta.nombre_fantasia
  return (
    <li className="min-w-0 border-t border-linea pt-3">
      <p className="text-base font-bold break-words">{CATALOGO.comercio(nombre)}</p>
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="cifras text-lg font-bold text-tinta">{pesos(oferta.precio)}</span>
        {deEjemplo && <span className="text-base text-tenue">{CATALOGO.precioDeEjemplo}</span>}
      </p>
      <p className="text-base text-tenue">{CATALOGO.ivaIncluido}</p>
      {oferta.disponible ? (
        <p className="mt-1 flex gap-1.5 text-base text-tinta">
          <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" />
          <span className="min-w-0 break-words">{CATALOGO.hay(nombre)}</span>
        </p>
      ) : (
        <p className="mt-1 flex gap-1.5 text-base text-tenue">
          <CircleMinus aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue" />
          <span className="min-w-0 break-words">{CATALOGO.noHay(nombre)}</span>
        </p>
      )}
    </li>
  )
}
