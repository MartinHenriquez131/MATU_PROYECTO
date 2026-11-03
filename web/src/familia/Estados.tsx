// Estados transversales (especificación 3.1 y 5).
import { useEffect, useState } from 'react'
import { UserRound, WifiOff } from 'lucide-react'
import { Boton } from '../compartido/ui/Boton'
import { useFamilia } from './estado'
import { navegar } from './ruteo'
import { Nota, Pagina, Titulo } from './ui'
import { ENTRAR, ESTADOS, FICHA, GENERAL } from './textos'

/** `true` pasados 400 ms: lo que carga rápido no muestra nada (3.1 y 5.1). */
export function useDemora(ms = 400) {
  const [ver, setVer] = useState(false)
  useEffect(() => {
    const t = window.setTimeout(() => setVer(true), ms)
    return () => window.clearTimeout(t)
  }, [ms])
  return ver
}

/** 3.1: al abrir la app, mientras renueva. */
export function Abriendo() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.abriendo : ''}
    </p>
  )
}

/** 5.2 al abrir: no se pudo saber si hay entrada (red o 5xx al renovar). */
export function ErrorAlAbrir() {
  const { cargar } = useFamilia()
  return (
    <div className="flex max-w-prose flex-col items-start gap-4">
      <Titulo>MATU</Titulo>
      <Nota tono="pronto" rol="alert" icono={<WifiOff aria-hidden className="mt-0.5 size-5 shrink-0 text-pronto" />}>
        {GENERAL.errorAlCargar}
      </Nota>
      <Boton variante="secundario" onClick={() => void cargar()}>
        {GENERAL.volverAIntentar}
      </Boton>
    </div>
  )
}

/** 5.4: con grupo y sin personas, para pagador u observador. */
export function SinPersona() {
  const { grupo } = useFamilia()
  return (
    <Pagina titulo={ESTADOS.insumosTitulo}>
      <Nota tono="rocio" icono={<UserRound aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
        {ESTADOS.sinPersona(grupo?.nombre ?? '')}
      </Nota>
    </Pagina>
  )
}

/** 5.5: Compartir, mientras MATU-48 no existe. */
export function CompartirPronto() {
  return (
    <Pagina titulo={ESTADOS.compartirTitulo}>
      <p className="max-w-prose text-tenue">{ESTADOS.compartirPronto}</p>
    </Pagina>
  )
}

/** Insumos: el lugar donde se monta MATU-36. */
export function InsumosPronto() {
  return <Pagina titulo={ESTADOS.insumosTitulo} />
}

/** 5.7: la entrada venció con texto sin guardar. Nunca se guarda en el navegador. */
export function TextoPerdido() {
  const { textoPerdido, fijar } = useFamilia()
  return (
    <div className="flex max-w-prose flex-col gap-5">
      <Titulo>{ENTRAR.titulo}</Titulo>
      <Nota tono="atenta" rol="alert">
        {FICHA.vencidaConTexto}
      </Nota>
      <p className="rounded-xl bg-hoja px-4 py-3 whitespace-pre-line ring-1 ring-linea select-text">{textoPerdido}</p>
      <div>
        <Boton
          onClick={() => {
            fijar({ textoPerdido: null })
            navegar('/entrar')
          }}
        >
          {ENTRAR.boton}
        </Boton>
      </div>
    </div>
  )
}
