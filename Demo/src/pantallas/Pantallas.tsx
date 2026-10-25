import { useDemo } from '../demo/estado'
import { pantallaComercio, pantallaFamilia } from '../demo/logica'
import { AQuien, Bienvenida, Cuenta, Entrar, Permiso } from './Alta'
import { Compartir, Completar, Conflicto, EnlacePin, Enlaces, Guardado, Imprimir, Inicio, QuienVio, TuFicha } from './Ficha'
import { Agregar, Declarar, Exportar, Reponer, SeAcaba, YaCompre } from './Consumo'
import { Entregado, MedioPago, Pasarela, PedidoPantalla, Rechazado, Seguimiento } from './Pedido'
import { RelevoApp } from './Relevo'
import { CCodigo, CMonto, CPedidos, CPreparar } from './Comercio'

export function Pantallas() {
  const { s } = useDemo()
  if (s.rol === 'relevo') return <RelevoApp />
  if (s.rol === 'comercio') {
    switch (pantallaComercio(s).id) {
      case 'c-preparar':
        return <CPreparar />
      case 'c-monto':
        return <CMonto />
      case 'c-codigo':
        return <CCodigo />
      default:
        return <CPedidos />
    }
  }
  switch (pantallaFamilia(s).id) {
    case 'bienvenida':
      return <Bienvenida />
    case 'cuenta':
      return <Cuenta />
    case 'entrar':
      return <Entrar />
    case 'a-quien':
      return <AQuien />
    case 'permiso':
      return <Permiso />
    case 'inicio':
      return <Inicio />
    case 'completar':
      return <Completar />
    case 'guardado':
      return <Guardado />
    case 'ficha':
      return <TuFicha />
    case 'compartir':
      return <Compartir />
    case 'enlace-pin':
      return <EnlacePin />
    case 'quien-vio':
      return <QuienVio />
    case 'enlaces':
      return <Enlaces />
    case 'imprimir':
      return <Imprimir />
    case 'conflicto':
      return <Conflicto />
    case 'se-acaba':
      return <SeAcaba />
    case 'declarar':
      return <Declarar />
    case 'agregar':
      return <Agregar />
    case 'ya-compre':
      return <YaCompre />
    case 'reponer':
      return <Reponer />
    case 'exportar':
      return <Exportar />
    case 'pedido':
      return <PedidoPantalla />
    case 'medio':
      return <MedioPago />
    case 'pasarela':
      return <Pasarela />
    case 'rechazado':
      return <Rechazado />
    case 'seguimiento':
      return <Seguimiento />
    case 'entregado':
      return <Entregado />
  }
}
