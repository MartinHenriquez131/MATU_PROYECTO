// La app de la familia: el alta en su propio marco, la pasarela fuera de MATU, y todo lo demás
// dentro del marco con barra lateral.
import { useDemo } from '../demo/estado'
import { pantallaFamilia } from '../demo/logica'
import type { PantallaFamiliaId } from '../demo/tipos'
import { Alta } from './Alta'
import { ShellFamilia } from './Shell'
import { Inicio } from './Inicio'
import { Compartir, Completar, Conflicto, EnlacePin, Enlaces, Guardado, Imprimir, QuienVio, TuFicha } from './Ficha'
import { Exportar, Reponer, SeAcaba } from './Insumos'
import { Entregado, Pasarela, PedidoPantalla, Rechazado, Seguimiento } from './Pedidos'
import { Grupo } from './Grupo'

const ALTA: PantallaFamiliaId[] = ['bienvenida', 'cuenta', 'entrar', 'a-quien', 'permiso']

function Contenido({ id }: { id: PantallaFamiliaId }) {
  switch (id) {
    case 'ficha':
      return <TuFicha />
    case 'completar':
      return <Completar />
    case 'guardado':
      return <Guardado />
    case 'conflicto':
      return <Conflicto />
    case 'compartir':
      return <Compartir />
    case 'enlace-pin':
      return <EnlacePin />
    case 'enlaces':
      return <Enlaces />
    case 'quien-vio':
      return <QuienVio />
    case 'imprimir':
      return <Imprimir />
    case 'se-acaba':
    case 'declarar':
    case 'ya-compre':
    case 'agregar':
      return <SeAcaba />
    case 'reponer':
      return <Reponer />
    case 'exportar':
      return <Exportar />
    case 'pedido':
      return <PedidoPantalla />
    case 'rechazado':
      return <Rechazado />
    case 'seguimiento':
      return <Seguimiento />
    case 'entregado':
      return <Entregado />
    case 'grupo':
      return <Grupo />
    default:
      return <Inicio />
  }
}

export function AppFamilia() {
  const { s } = useDemo()
  const p = pantallaFamilia(s)
  // La clave reinicia el estado local de cada pantalla al navegar (por ejemplo, los pasos de Declarar).
  if (ALTA.includes(p.id)) return <Alta key={p.n} />
  if (p.id === 'pasarela') return <Pasarela key={p.n} />
  return (
    <ShellFamilia>
      <Contenido key={p.n} id={p.id} />
    </ShellFamilia>
  )
}
