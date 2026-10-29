// Cargando (3.1), estados en que el enlace no abre (3.4 a 3.10) y error general (3.12).
import { useEffect, useState } from 'react'
import { CircleAlert } from 'lucide-react'
import { Boton } from '../compartido/ui/Boton'
import { ESTADOS, type EstadoNoAbre } from './estados'
import { Baldosa, Columna, Titulo } from './Marco'
import { ERROR, QUE_HAGO } from './textos'

/** Sin esqueleto ni ícono girando: una línea que aparece recién a los 400 ms. */
export function Cargando({ texto }: { texto: string }) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const t = window.setTimeout(() => setVisible(true), 400)
    return () => window.clearTimeout(t)
  }, [])
  return (
    <Columna>
      <p role="status" className="text-lg text-tenue">
        {visible ? texto : ''}
      </p>
    </Columna>
  )
}

/** Sin botones: nada que Rosa toque arregla el enlace. Sin el aviso 7.5 y sin la ficha. */
export function PantallaEstado({ estado, minutos }: { estado: EstadoNoAbre; minutos: number | null }) {
  const d = ESTADOS[estado]
  return (
    <Columna>
      <Baldosa icono={d.icono} tono="neutra" />
      <div className="flex flex-col items-center gap-2">
        <Titulo>{d.titulo}</Titulo>
        {d.texto && <p className="max-w-md text-lg text-tenue">{d.texto(minutos)}</p>}
      </div>
      {d.accion && (
        <div className="w-full rounded-xl bg-rocio px-4 py-3 text-start">
          <p className="font-bold">{QUE_HAGO.titulo}</p>
          <p className="text-base font-bold">{d.accion}</p>
        </div>
      )}
    </Columna>
  )
}

/** Falló la primera petición de una pantalla. «Volver a intentar» repite esa misma petición. */
export function PantallaError({ ocupado, textoOcupado, onReintentar }: { ocupado: boolean; textoOcupado: string; onReintentar: () => void }) {
  return (
    <Columna>
      <Baldosa icono={CircleAlert} tono="neutra" />
      <div className="flex flex-col items-center gap-2">
        <Titulo>{ERROR.titulo}</Titulo>
        <p className="max-w-md text-lg text-tenue">{ERROR.conexion}</p>
      </div>
      <Boton ocupado={ocupado} textoOcupado={textoOcupado} onClick={onReintentar}>
        {ERROR.reintentar}
      </Boton>
    </Columna>
  )
}
