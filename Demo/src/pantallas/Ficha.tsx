import { useEffect, useState } from 'react'
import {
  CircleAlert,
  Clock3,
  Eye,
  KeyRound,
  Link2,
  Lock,
  Mic,
  PackageOpen,
  Printer,
  Send,
  ShieldCheck,
  Share2,
  Smartphone,
  TriangleAlert,
  Unlink,
  UserRound,
} from 'lucide-react'
import { useDemo } from '../demo/estado'
import {
  abrirCampo,
  abrirRelevo,
  avisar,
  completados,
  cortarAcceso,
  crearAcceso,
  escribir,
  guardarCampo,
  ir,
  nombrePila,
  pilaFamilia,
  reemplazar,
  resolverConflicto,
  siguienteCampoVacio,
  volver,
  type DatosCompartir,
} from '../demo/logica'
import { CAMPOS, MAX_CARACTERES, TEXTO_CAMPO } from '../demo/datos'
import {
  DIA,
  accesoVigente,
  diaDeLaSemana,
  diasRestantes,
  estadoAccesoTexto,
  fmtCuando,
  fmtFecha,
  fmtHora,
  fmtRestante,
  finDeSemana,
  nivel,
} from '../demo/calculos'
import type { CampoId } from '../demo/tipos'
import { Pantalla } from '../components/Pantalla'
import { BarraCampos, Boton, CampoTexto, Chip, Etiqueta, Fila, Logo, Nota, Sello, Stepper, Tarjeta } from '../components/Ui'
import { TextoCampo } from '../components/TextoFicha'
import { useMovimientoReducido } from '../components/movimiento'

const listaCampos = (campos: CampoId[]) => {
  const t = campos.map((c) => TEXTO_CAMPO[c].titulo)
  return t.length <= 1 ? t.join('') : `${t.slice(0, -1).join(', ')} y ${t[t.length - 1]}`
}

export function Inicio() {
  const { s, haz } = useDemo()
  const pila = nombrePila(s)
  const hechos = completados(s)
  const declarados = s.insumos.filter((i) => i.declarado)
  const urgente = [...declarados].sort((a, b) => diasRestantes(a) - diasRestantes(b))[0]
  const dUrg = urgente ? diasRestantes(urgente) : 0
  const vigentes = s.accesos.filter((a) => accesoVigente(a, s.ahora))
  const pedidoEnCurso = s.pedido && s.pedido.estado !== 'borrador' && s.pedido.estado !== 'entregado'
  const textoAvance =
    hechos === 0
      ? 'Empieza por «Su día». Con eso alguien ya podría reemplazarte unas horas.'
      : hechos < 3
        ? 'Con lo que ya escribiste, alguien podría reemplazarte unas horas.'
        : 'Lista. Quien te reemplace va a saber qué hacer.'

  return (
    <Pantalla
      titulo={`Hola, ${s.cuenta?.nombre ?? 'Carmen'}`}
      encabezado={
        <header className="relative shrink-0 overflow-hidden bg-pino px-5 pt-5 pb-6 text-papel">
          <svg aria-hidden className="pointer-events-none absolute -right-16 -bottom-24 size-64 opacity-[0.12]" viewBox="0 0 200 200">
            {[40, 62, 84].map((r) => (
              <circle key={r} cx="100" cy="100" r={r} fill="none" stroke="currentColor" strokeWidth="9" />
            ))}
          </svg>
          <div className="relative flex items-center gap-3">
            <Logo claro className="size-11 shrink-0" />
            <div className="min-w-0">
              <p className="font-display text-[1.45rem] leading-tight font-bold tracking-[-0.02em]">Hola, {s.cuenta?.nombre ?? 'Carmen'}</p>
              <p className="text-[0.95rem] opacity-90">
                Cuidado de {pila} · <span className="capitalize">{diaDeHoy(s.ahora)}</span>
              </p>
            </div>
          </div>
        </header>
      }
    >
      <Tarjeta>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-[1.15rem] font-bold">Ficha de relevo</h2>
          <Etiqueta tono={hechos === 3 ? 'ok' : 'pino'}>
            <span className="cifras">{hechos} de 3</span>
          </Etiqueta>
        </div>
        <BarraCampos hechos={hechos} />
        <p className="text-tenue">{textoAvance}</p>
        {hechos < 3 && (
          <Boton onClick={() => haz((x) => abrirCampo(x, siguienteCampoVacio(x)!))}>Completar la ficha</Boton>
        )}
        <Boton variante="secundario" icono={<Share2 aria-hidden className="size-5" />} onClick={() => haz((x) => ir(x, 'compartir'))}>
          Compartir con un relevo
        </Boton>
      </Tarjeta>

      {urgente ? (
        <Tarjeta tono={nivel(dUrg) === 'pronto' ? 'pronto' : nivel(dUrg) === 'atenta' ? 'atenta' : 'ok'}>
          <h2 className="flex items-center gap-2 font-bold">
            <TriangleAlert aria-hidden className="size-5 shrink-0" />
            {nivel(dUrg) === 'tranquila' ? 'Los insumos están bien' : `Se acaba: ${urgente.nombre.toLowerCase()}`}
          </h2>
          <p>
            Queda para <b className="cifras">{dUrg} días</b>, hasta el <span className="cifras">{fmtFecha(s.ahora + dUrg * DIA)}</span>. Te
            avisamos antes para que no te pille.
          </p>
          <Boton onClick={() => haz((x) => ir(x, 'se-acaba'))}>Ver qué reponer</Boton>
        </Tarjeta>
      ) : (
        <Tarjeta tono="borde">
          <h2 className="flex items-center gap-2 font-bold">
            <PackageOpen aria-hidden className="size-5 shrink-0 text-pino" />
            ¿Qué usa {pila}?
          </h2>
          <p className="text-tenue">Cuéntanos de un producto y te avisamos antes de que se acabe.</p>
          <Boton variante="suave" onClick={() => haz((x) => ir(x, 'se-acaba'))}>
            Empezar
          </Boton>
        </Tarjeta>
      )}

      {pedidoEnCurso && (
        <button
          type="button"
          onClick={() => haz((x) => ir(x, 'seguimiento'))}
          className="flex min-h-13 items-center gap-3 rounded-[1.35rem] bg-hoja p-4 text-left ring-1 ring-linea hover:ring-pino/50"
        >
          <PackageOpen aria-hidden className="size-6 shrink-0 text-pino" />
          <span className="min-w-0 flex-1">
            <span className="block font-bold">Pedido #{s.pedido!.numero}</span>
            <span className="text-tenue">{ESTADO_PEDIDO_CORTO[s.pedido!.estado]}</span>
          </span>
        </button>
      )}

      {vigentes.length > 0 && (
        <button
          type="button"
          onClick={() => haz((x) => ir(x, 'enlaces'))}
          className="flex min-h-13 items-center gap-3 rounded-[1.35rem] bg-hoja p-4 text-left ring-1 ring-linea hover:ring-pino/50"
        >
          <Link2 aria-hidden className="size-6 shrink-0 text-pino" />
          <span className="min-w-0 flex-1">
            <span className="block font-bold">
              {vigentes[0].nombre} puede ver la ficha{vigentes.length > 1 ? ` y ${vigentes.length - 1} más` : ''}
            </span>
            <span className="text-tenue">Vence en {fmtRestante(vigentes[0].venceMin, s.ahora)}</span>
          </span>
        </button>
      )}
    </Pantalla>
  )
}

const ESTADO_PEDIDO_CORTO: Record<string, string> = {
  pagado: 'Pagado. La farmacia lo va a preparar',
  preparando: 'La farmacia lo está preparando',
  listo: 'Listo para retiro',
  en_camino: 'En camino',
}

function diaDeHoy(min: number) {
  return `${diaDeLaSemana(min)} ${fmtFecha(min)}`
}

export function Completar() {
  const { s, haz } = useDemo()
  const reducido = useMovimientoReducido()
  const [dictando, setDictando] = useState(false)
  const b = s.borrador
  const campo = b?.campo ?? 'su_dia'
  const t = TEXTO_CAMPO[campo]
  const indice = CAMPOS.indexOf(campo) + 1

  // Dictado simulado: escribe el ejemplo de a poco, como si se dictara.
  useEffect(() => {
    if (!dictando) return
    const objetivo = t.dictado
    if (reducido) {
      haz((x) => escribir(x, objetivo))
      setDictando(false)
      return
    }
    let i = 0
    const id = window.setInterval(() => {
      i = Math.min(objetivo.length, i + 3)
      haz((x) => escribir(x, objetivo.slice(0, i)))
      if (i >= objetivo.length) {
        window.clearInterval(id)
        setDictando(false)
      }
    }, 28)
    return () => window.clearInterval(id)
  }, [dictando, reducido, t.dictado, haz])

  if (!b) return null
  const otros = CAMPOS.filter((c) => c !== campo && s.ficha[c].texto.trim()).length
  return (
    <Pantalla
      titulo={`Ficha de ${nombrePila(s)}`}
      pie={
        <Fila>
          <Boton variante="secundario" onClick={() => haz(volver)}>
            Después
          </Boton>
          <Boton onClick={() => haz(guardarCampo)} disabled={dictando}>
            Guardar
          </Boton>
        </Fila>
      }
    >
      <p className="text-sm font-bold tracking-wide text-tenue uppercase">Campo {indice} de 3</p>
      <BarraCampos hechos={otros + (b.texto.trim() ? 1 : 0)} />
      <label htmlFor="campo-texto" className="font-display text-[1.6rem] leading-tight font-bold tracking-[-0.02em]">
        {t.titulo}
      </label>
      <p id="campo-pregunta" className="-mt-2 text-[1.05rem]">
        {t.pregunta}
      </p>
      <div className="relative">
        <textarea
          id="campo-texto"
          rows={6}
          maxLength={MAX_CARACTERES}
          value={b.texto}
          onChange={(e) => haz((x) => escribir(x, e.target.value))}
          aria-describedby="campo-pregunta campo-ejemplo campo-cuenta"
          className="w-full resize-none rounded-2xl bg-hoja px-4 pt-3 pb-8 leading-relaxed ring-2 ring-linea ring-inset outline-none focus-visible:ring-pino"
        />
        <span id="campo-cuenta" className="cifras pointer-events-none absolute right-3 bottom-2 text-sm text-tenue">
          {b.texto.length}/{MAX_CARACTERES}
        </span>
      </div>
      <p id="campo-ejemplo" className="text-[0.95rem] text-tenue">
        {t.ejemplo}
      </p>
      <Boton
        variante="suave"
        icono={<Mic aria-hidden className={`size-5 ${dictando ? 'animate-pulse' : ''}`} />}
        onClick={() => setDictando(true)}
        disabled={dictando}
      >
        {dictando ? 'Escuchando…' : 'Dictar en vez de escribir'}
      </Boton>
      <p className="text-center text-sm text-tenue">El dictado está simulado en la demo.</p>
    </Pantalla>
  )
}

export function Guardado() {
  const { s, haz } = useDemo()
  const hechos = completados(s)
  const sig = siguienteCampoVacio(s)
  return (
    <Pantalla
      titulo={`Ficha de ${nombrePila(s)}`}
      pie={
        sig ? (
          <>
            <Boton onClick={() => haz((x) => abrirCampo(volver(x), sig))}>Seguir con «{TEXTO_CAMPO[sig].titulo}»</Boton>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['ficha']))}>
              Ver mi ficha
            </Boton>
          </>
        ) : (
          <Fila>
            <Boton variante="secundario" onClick={() => haz((x) => pilaFamilia(x, ['inicio']))}>
              Volver al inicio
            </Boton>
            <Boton onClick={() => haz((x) => pilaFamilia(x, ['ficha']))}>Ver mi ficha</Boton>
          </Fila>
        )
      }
    >
      <div className="flex flex-col items-center gap-3 pt-6 text-center">
        <Sello>
          <svg viewBox="0 0 24 24" className="size-10" aria-hidden>
            <path
              d="M5 12.5l4.5 4.5L19 7.5"
              pathLength={1}
              fill="none"
              stroke="currentColor"
              strokeWidth="2.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="1"
              className="animate-trazo"
            />
          </svg>
        </Sello>
        <p className="font-display text-[1.7rem] font-bold">Guardado</p>
        <p className="max-w-[18rem] text-tenue">
          {hechos === 3 ? 'La ficha está completa.' : `Vas en ${hechos} de 3.`} Puedes seguir cuando quieras, no se pierde nada.
        </p>
        <div className="w-full max-w-[14rem]">
          <BarraCampos hechos={hechos} />
        </div>
      </div>
    </Pantalla>
  )
}

export function TuFicha() {
  const { s, haz } = useDemo()
  return (
    <Pantalla
      titulo={`Ficha de ${nombrePila(s)}`}
      pie={
        <>
          <Boton icono={<Share2 aria-hidden className="size-5" />} onClick={() => haz((x) => ir(x, 'compartir'))}>
            Compartir con un relevo
          </Boton>
          <Fila>
            <Boton variante="secundario" icono={<Eye aria-hidden className="size-5" />} onClick={() => haz((x) => ir(x, 'quien-vio'))}>
              Quién la vio
            </Boton>
            <Boton variante="secundario" icono={<Printer aria-hidden className="size-5" />} onClick={() => haz((x) => ir(x, 'imprimir'))}>
              Imprimir
            </Boton>
          </Fila>
        </>
      }
    >
      <ul className="flex flex-col gap-2.5">
        {CAMPOS.map((c) => {
          const f = s.ficha[c]
          const listo = !!f.texto.trim()
          return (
            <li key={c}>
              <button
                type="button"
                onClick={() => haz((x) => abrirCampo(x, c))}
                className={`flex min-h-16 w-full items-start gap-3 rounded-[1.2rem] bg-hoja p-4 text-left ring-1 ring-linea hover:ring-pino/50 ${
                  listo ? 'border-l-[6px] border-ok' : 'border-l-[6px] border-tinta/15'
                }`}
              >
                <span className="min-w-0 flex-1">
                  <span className="block font-bold">{TEXTO_CAMPO[c].titulo}</span>
                  <span className="line-clamp-2 text-[0.95rem] text-tenue">{listo ? f.texto : 'Todavía sin completar'}</span>
                  {listo && f.autor && f.autor !== 'Carmen' && (
                    <span className="mt-1 block text-sm text-tenue">Lo escribió {f.autor}</span>
                  )}
                </span>
                <Etiqueta tono={listo ? 'ok' : 'neutro'}>{listo ? 'Listo' : 'Falta'}</Etiqueta>
              </button>
            </li>
          )
        })}
      </ul>
      <p className="flex gap-2 text-[0.95rem] text-tenue">
        <Lock aria-hidden className="mt-0.5 size-4.5 shrink-0" />
        Cada campo se guarda protegido. Puedes compartir solo algunos.
      </p>
    </Pantalla>
  )
}

export function Compartir() {
  const { s, haz } = useDemo()
  const [nombre, setNombre] = useState('Rosa')
  const [telefono, setTelefono] = useState('+56 9 8765 4321')
  const [campos, setCampos] = useState<CampoId[]>([...CAMPOS])
  const [vigencia, setVigencia] = useState<DatosCompartir['vigencia']>('24h')
  const [dias, setDias] = useState(3)
  const [motivo, setMotivo] = useState('Salgo unas horas')
  const [error, setError] = useState<string | null>(null)
  const vence = vigencia === '24h' ? s.ahora + DIA : vigencia === 'finde' ? finDeSemana(s.ahora) : s.ahora + dias * DIA
  const vacios = campos.filter((c) => !s.ficha[c].texto.trim())

  const crear = () => {
    if (!nombre.trim()) return setError('Escribe el nombre de quien te reemplaza.')
    if (campos.length === 0) return setError('Elige al menos un campo.')
    haz((x) => reemplazar(crearAcceso(x, { nombre, telefono, campos, vigencia, dias, motivo }), 'enlace-pin'))
  }
  const alternar = (c: CampoId) => setCampos((cs) => (cs.includes(c) ? cs.filter((x) => x !== c) : CAMPOS.filter((x) => x === c || cs.includes(x))))

  return (
    <Pantalla titulo="Compartir la ficha" pie={<Boton icono={<Link2 aria-hidden className="size-5" />} onClick={crear}>Crear enlace</Boton>}>
      <CampoTexto etiqueta="¿Quién te va a reemplazar?" value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="off" error={error && !nombre.trim() ? error : null} />
      <CampoTexto etiqueta="Su teléfono" type="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} autoComplete="off" ayuda="Para enviarle el enlace. El PIN se lo dictas tú." />
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-bold">¿Qué puede ver?</legend>
        <div className="flex flex-wrap gap-2">
          {CAMPOS.map((c) => (
            <Chip key={c} activo={campos.includes(c)} onClick={() => alternar(c)}>
              {TEXTO_CAMPO[c].titulo}
            </Chip>
          ))}
        </div>
        {vacios.length > 0 && (
          <p className="text-sm text-tenue">
            {listaCampos(vacios)} {vacios.length > 1 ? 'están vacíos' : 'está vacío'}: {nombre || 'el relevo'} verá «Sin completar».
          </p>
        )}
      </fieldset>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-bold">¿Hasta cuándo?</legend>
        <div className="flex flex-wrap gap-2">
          <Chip activo={vigencia === '24h'} onClick={() => setVigencia('24h')}>
            24 horas
          </Chip>
          <Chip activo={vigencia === 'finde'} onClick={() => setVigencia('finde')}>
            Fin de semana
          </Chip>
          <Chip activo={vigencia === 'dias'} onClick={() => setVigencia('dias')}>
            Otra fecha
          </Chip>
        </div>
        {vigencia === 'dias' && <Stepper etiqueta="¿Cuántos días?" valor={dias} onCambio={setDias} min={1} max={30} unidad="días" ayuda="Hasta 30 días." />}
        <p className="flex items-center gap-2 text-[0.95rem]">
          <Clock3 aria-hidden className="size-4.5 shrink-0 text-pino" />
          <span>
            Vence el <b className="cifras">{fmtFecha(vence)}</b> a las <b className="cifras">{fmtHora(vence)}</b>
          </span>
        </p>
      </fieldset>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-bold">Motivo (opcional)</legend>
        <div className="flex flex-wrap gap-2">
          {['Salgo unas horas', 'Fin de semana fuera', 'Turno de noche'].map((m) => (
            <Chip key={m} activo={motivo === m} onClick={() => setMotivo(motivo === m ? '' : m)}>
              {m}
            </Chip>
          ))}
        </div>
      </fieldset>
      {error && campos.length === 0 && (
        <p role="alert" className="font-bold text-pronto">
          {error}
        </p>
      )}
    </Pantalla>
  )
}

/** El momento orquestado de la demo: el enlace se arma y el PIN cae dígito a dígito. */
export function EnlacePin() {
  const { s, haz } = useDemo()
  const a = s.accesos.find((x) => x.id === s.pinVisible) ?? null
  const ultimo = a ?? s.accesos[0]
  if (!a || !ultimo) {
    return (
      <Pantalla titulo="Enlace listo" pie={<Boton onClick={() => haz((x) => reemplazar(x, 'compartir'))}>Crear un enlace nuevo</Boton>}>
        <Nota titulo="El PIN ya no se puede ver">Por seguridad se muestra una sola vez. Si se perdió, crea un enlace nuevo y corta el anterior.</Nota>
      </Pantalla>
    )
  }
  const url = `matu.cl/r#${a.token.slice(0, 14)}…`
  return (
    <Pantalla
      titulo="Enlace listo"
      pie={
        <>
          <Boton
            icono={<Send aria-hidden className="size-5" />}
            onClick={() => haz((x) => avisar(x, `Se abriría WhatsApp con el enlace para ${a.nombre}, sin el PIN. (Simulado)`))}
          >
            Enviar enlace por WhatsApp
          </Boton>
          <Boton variante="secundario" icono={<Smartphone aria-hidden className="size-5" />} onClick={() => haz((x) => abrirRelevo(x, a.id))}>
            Abrir como {a.nombre}
          </Boton>
        </>
      }
    >
      <div className="flex flex-col items-center gap-2 pt-2 text-center">
        <div className="relative">
          <span aria-hidden className="absolute inset-0 rounded-[1.6rem] bg-pino animate-onda" />
          <span aria-hidden className="absolute inset-0 rounded-[1.6rem] bg-pino animate-onda [animation-delay:350ms]" />
          <Sello>
            <svg viewBox="0 0 24 24" className="size-9" aria-hidden fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" pathLength={1} strokeDasharray="1" className="animate-trazo" />
              <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" pathLength={1} strokeDasharray="1" className="animate-trazo [animation-delay:250ms]" />
            </svg>
          </Sello>
        </div>
        <p className="mt-2 font-display text-[1.6rem] leading-tight font-bold animate-subir [animation-delay:300ms]">Listo para {a.nombre}</p>
        <p className="text-tenue animate-subir [animation-delay:380ms]">
          Vence el <span className="cifras">{fmtFecha(a.venceMin)}</span> a las <span className="cifras">{fmtHora(a.venceMin)}</span>
        </p>
      </div>

      <div className="flex items-center gap-2 rounded-2xl bg-rocio px-4 py-3 animate-subir [animation-delay:450ms]">
        <Link2 aria-hidden className="size-5 shrink-0 text-pino" />
        <span className="cifras min-w-0 truncate text-[0.95rem]">{url}</span>
      </div>

      <section
        aria-labelledby="pin-t"
        className="relative overflow-hidden rounded-[1.5rem] bg-hoja px-4 pt-4 pb-5 text-center border-2 border-dashed border-pino/70 animate-subir [animation-delay:520ms]"
      >
        <h2 id="pin-t" className="flex items-center justify-center gap-2 font-bold text-tenue">
          <KeyRound aria-hidden className="size-5" />
          PIN para abrir la ficha
        </h2>
        <p className="mt-3 flex justify-center gap-2.5" aria-label={`PIN: ${a.pin.split('').join(' ')}`}>
          {a.pin.split('').map((d, i) => (
            <span
              key={i}
              aria-hidden
              className="cifras grid h-[4.6rem] w-[3.4rem] place-items-center rounded-2xl bg-rocio text-[2.6rem] font-bold text-pino shadow-[inset_0_-3px_0_var(--color-miel)] animate-digito"
              style={{ animationDelay: `${700 + i * 140}ms` }}
            >
              {d}
            </span>
          ))}
        </p>
        <p className="mt-4 text-[0.95rem]">
          <b>Díctaselo por teléfono.</b> No lo mandes junto con el enlace. Solo lo verás ahora.
        </p>
      </section>
    </Pantalla>
  )
}

export function QuienVio() {
  const { s, haz } = useDemo()
  return (
    <Pantalla titulo="Quién vio la ficha" pie={<Boton variante="secundario" onClick={() => haz((x) => ir(x, 'enlaces'))}>Ver enlaces activos</Boton>}>
      {s.eventos.length === 0 ? (
        <Nota>Todavía nadie ha abierto la ficha. Cuando alguien la abra, aparece aquí.</Nota>
      ) : (
        <ul className="flex flex-col">
          {s.eventos.map((e) => (
            <li key={e.id} className="flex items-start gap-3 border-b border-linea py-3 last:border-0">
              <span className={`mt-0.5 grid size-9 shrink-0 place-items-center rounded-full ${e.tono === 'atento' ? 'bg-atenta-fondo text-atenta' : 'bg-rocio text-pino'}`}>
                {e.tono === 'atento' ? <CircleAlert aria-hidden className="size-5" /> : <UserRound aria-hidden className="size-5" />}
              </span>
              <span className="min-w-0">
                <span className="block font-bold">{e.texto}</span>
                <span className="cifras text-[0.95rem] text-tenue">{fmtCuando(e.minuto, s.ahora)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="flex gap-2 text-[0.95rem] text-tenue">
        <ShieldCheck aria-hidden className="mt-0.5 size-4.5 shrink-0" />
        Nadie de MATU puede abrir la ficha. Si alguna vez pasara, aparecería aquí.
      </p>
    </Pantalla>
  )
}

export function Enlaces() {
  const { s, haz } = useDemo()
  const lista = [...s.accesos].sort((a, b) => Number(accesoVigente(b, s.ahora)) - Number(accesoVigente(a, s.ahora)) || b.creadoMin - a.creadoMin)
  return (
    <Pantalla titulo="Enlaces" pie={<Boton variante="secundario" onClick={() => haz((x) => ir(x, 'compartir'))}>Crear un enlace nuevo</Boton>}>
      {lista.length === 0 && <Nota>No hay enlaces todavía.</Nota>}
      {lista.map((a) => {
        const vig = accesoVigente(a, s.ahora)
        const estado = estadoAccesoTexto(a, s.ahora)
        return (
          <Tarjeta key={a.id} className={vig ? '' : 'opacity-80'}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-display text-[1.15rem] font-bold">{a.nombre}</h2>
              {vig ? (
                <Etiqueta tono="pino">
                  <Clock3 aria-hidden className="size-4" /> vence en {fmtRestante(a.venceMin, s.ahora)}
                </Etiqueta>
              ) : (
                <Etiqueta tono={estado === 'Bloqueado' ? 'atenta' : 'neutro'}>{estado}</Etiqueta>
              )}
            </div>
            <p className="text-tenue">
              Ve {listaCampos(a.campos)}.{a.motivo ? ` ${a.motivo}.` : ''}
            </p>
            {vig ? (
              <>
                <Boton variante="secundario" icono={<Unlink aria-hidden className="size-5" />} onClick={() => haz((x) => cortarAcceso(x, a.id))}>
                  Cortar este enlace ahora
                </Boton>
                <Boton variante="texto" onClick={() => haz((x) => abrirRelevo(x, a.id))}>
                  Probar el enlace como {a.nombre}
                </Boton>
              </>
            ) : (
              <p className="cifras text-sm text-tenue">
                {estado === 'Vencido' ? `Venció: ${fmtCuando(a.venceMin, s.ahora)}` : `Creado: ${fmtCuando(a.creadoMin, s.ahora)}`}
              </p>
            )}
          </Tarjeta>
        )
      })}
      <p className="text-[0.95rem] text-tenue">Al cortarlo, el enlace deja de abrir de inmediato. Quien lo tenía no recibe aviso.</p>
    </Pantalla>
  )
}

export function Imprimir() {
  const { s } = useDemo()
  const pila = nombrePila(s)
  return (
    <Pantalla titulo="Para imprimir" cuerpoClase="bg-tinta/[0.06]">
      <p className="text-[0.95rem] text-tenue">
        Así queda la hoja para el refrigerador. En la app se descarga lista para imprimir; en la demo se muestra aquí.
      </p>
      <article
        aria-label={`Hoja impresa de la ficha de ${pila}`}
        className="relative rounded-md bg-hoja px-5 pt-6 pb-5 shadow-[0_1px_2px_rgb(0_0_0/0.08),0_12px_28px_-12px_rgb(0_0_0/0.3)] [clip-path:polygon(0_0,calc(100%-1.6rem)_0,100%_1.6rem,100%_100%,0_100%)]"
      >
        <span aria-hidden className="absolute top-0 right-0 size-[1.6rem] rounded-bl-md bg-tinta/10" />
        <header className="flex items-center gap-3 border-b-2 border-tinta pb-3">
          <Logo className="size-9 shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-bold tracking-[0.12em] text-tenue uppercase">Ficha de relevo</p>
            <h2 className="font-display text-[1.7rem] leading-none font-extrabold">{pila}</h2>
          </div>
        </header>
        <p className="mt-3 text-[0.95rem]">Para quien la cuide hoy. Gracias por estar.</p>
        {CAMPOS.map((c) => (
          <section key={c} className="mt-4">
            <h3 className="mb-1.5 font-display text-[1.1rem] font-bold text-pino">{TEXTO_CAMPO[c].titulo}</h3>
            <div className="renglones leading-[1.75rem]">
              <TextoCampo texto={s.ficha[c].texto} vacio={`Sin completar. Pregúntale a ${s.cuenta?.nombre ?? 'Carmen'}.`} />
            </div>
          </section>
        ))}
        <footer className="cifras mt-5 border-t border-dashed border-linea pt-2 text-sm text-tenue">
          Impresa el {fmtFecha(s.ahora)}. Si algo cambia, vuelve a imprimirla.
        </footer>
      </article>
    </Pantalla>
  )
}

export function Conflicto() {
  const { s, haz } = useDemo()
  const c = s.conflicto
  if (!c) return null
  return (
    <Pantalla titulo="Dos versiones">
      <Tarjeta tono="pronto">
        <h2 className="flex items-center gap-2 font-bold">
          <TriangleAlert aria-hidden className="size-5 shrink-0" />
          {c.suyo.autor || 'Otra persona'} editó «{TEXTO_CAMPO[c.campo].titulo}» mientras escribías
        </h2>
        <p>No queremos borrar lo de nadie. Elige cuál dejar.</p>
      </Tarjeta>
      <Tarjeta>
        <p className="cifras text-sm font-bold text-tenue">
          Lo de {c.suyo.autor} · {c.suyo.minuto !== null ? fmtHora(c.suyo.minuto) : ''}
        </p>
        <p className="leading-relaxed">{c.suyo.texto}</p>
        <Boton variante="secundario" onClick={() => haz((x) => resolverConflicto(x, 'suyo'))}>
          Dejar la de {c.suyo.autor}
        </Boton>
      </Tarjeta>
      <Tarjeta>
        <p className="text-sm font-bold text-tenue">Lo tuyo · ahora</p>
        <p className="leading-relaxed">{c.mio || <i className="text-tenue">Vacío</i>}</p>
        <Boton onClick={() => haz((x) => resolverConflicto(x, 'mio'))}>Dejar la mía</Boton>
      </Tarjeta>
      <p className="text-[0.95rem] text-tenue">MATU no mezcla los textos solo. Si quieres, copia una parte antes de elegir.</p>
    </Pantalla>
  )
}
