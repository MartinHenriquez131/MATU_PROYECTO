// Solo en desarrollo: las piezas del paso de compartir de MATU-49 (sección 6) funcionando, para la
// revisión del diseñador mientras la pantalla de MATU-48 no existe. No es una pantalla de MATU, no
// llama a la API y no entra al build (la carga /ejemplos bajo import.meta.env.DEV).
import { useState } from 'react'
import type { SeccionApi } from '../compartido/secciones'
import { Boton } from '../compartido/ui/Boton'
import { ConfirmacionRemedios, ElegirSecciones, useEleccionSecciones } from '../familia/SeccionesCompartir'
import { COMPARTIR_SECCIONES } from '../familia/textos'
import { TITULO_SECCION } from '../compartido/secciones'

const CASOS: { nombre: string; agregadas: SeccionApi[] }[] = [
  { nombre: 'Sin secciones agregadas', agregadas: [] },
  { nombre: 'Dos secciones, sin Sus remedios', agregadas: ['quien_es', 'comunicacion'] },
  { nombre: 'Las seis', agregadas: ['quien_es', 'preferencias', 'alimentacion', 'movilidad', 'comunicacion', 'remedios'] },
]

export function CompartirDeEjemplo() {
  const [caso, setCaso] = useState(2)
  return (
    <section className="flex flex-col gap-4 border-t border-linea pt-6">
      <h2 className="text-xl font-bold">Compartir: qué secciones ve el relevo (MATU-50, lo integra MATU-48)</h2>
      <div className="flex flex-wrap gap-2">
        {CASOS.map((c, i) => (
          <Boton key={c.nombre} variante={i === caso ? 'principal' : 'secundario'} onClick={() => setCaso(i)}>
            {c.nombre}
          </Boton>
        ))}
      </div>
      <Selector key={caso} agregadas={CASOS[caso].agregadas} />
    </section>
  )
}

function Selector({ agregadas }: { agregadas: SeccionApi[] }) {
  const e = useEleccionSecciones()
  const [confirmar, setConfirmar] = useState(false)
  const [creado, setCreado] = useState<SeccionApi[] | null>(null)
  const vence = new Date(Date.now() + 4 * 86_400_000)
  const crear = () => {
    setConfirmar(false)
    setCreado(e.paraEnviar)
  }
  return (
    <div className="flex max-w-prose flex-col gap-6">
      <ElegirSecciones agregadas={agregadas} elegidas={e.elegidas} onElegidas={e.setElegidas} remedios={e.remedios} onRemedios={(v) => (setConfirmar(false), e.setRemedios(v))} />
      {confirmar ? (
        <ConfirmacionRemedios nombre="Rosa" vence={vence} onSi={crear} onNo={() => (setConfirmar(false), e.setRemedios(false))} />
      ) : (
        <Boton className="self-start" onClick={() => (e.remedios ? setConfirmar(true) : crear())}>
          Crear enlace
        </Boton>
      )}
      {creado && (
        <p role="status" className="text-base">
          (Ejemplo, sin petición) {COMPARTIR_SECCIONES.loQueVe(creado.map((s) => TITULO_SECCION[s]))} secciones_adicionales: [{creado.join(', ')}]
        </p>
      )}
    </div>
  )
}
