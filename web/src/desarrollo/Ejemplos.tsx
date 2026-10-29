// Solo en desarrollo: enlaces de ejemplo del doble del contrato, uno por estado, para la revisión
// del diseñador (especificación MATU-23, sección 8). main.tsx lo carga bajo import.meta.env.DEV,
// así que el build de producción no lo incluye. No es una pantalla de MATU.
import { ESCENARIOS, PIN_DE_EJEMPLO, SIN_FRAGMENTO, TOKEN_LARGO } from '../../doble/escenarios'

export function Ejemplos() {
  // Se abre en una pestaña nueva: el fragmento cambia y la página arranca de cero.
  const enlace = (token: string) => `/r#${token}`
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-8">
      <h1 className="titular text-3xl">Doble del contrato del relevo (solo desarrollo)</h1>
      <p className="text-tenue">
        PIN correcto en todos los ejemplos: <b className="digitos">{PIN_DE_EJEMPLO}</b>. Los intentos y las sesiones viven en la memoria
        del servidor de desarrollo: reinicia <code>npm run dev</code> para volver a cero.
      </p>
      <ul className="flex flex-col gap-3">
        {ESCENARIOS.map((e) => (
          <li key={e.token} className="flex flex-col">
            <a className="inline-flex min-h-12 items-center font-bold text-turquesa underline underline-offset-4" href={enlace(e.token)} target="_blank" rel="noopener noreferrer">
              /r#{e.token}
            </a>
            <span className="text-base text-tenue">{e.que}</span>
          </li>
        ))}
        <li className="flex flex-col">
          <a className="inline-flex min-h-12 items-center font-bold text-turquesa underline underline-offset-4" href="/r" target="_blank" rel="noopener noreferrer">
            /r
          </a>
          <span className="text-base text-tenue">{SIN_FRAGMENTO}</span>
        </li>
        <li className="flex flex-col">
          <a className="inline-flex min-h-12 items-center font-bold text-turquesa underline underline-offset-4" href={enlace('x'.repeat(129))} target="_blank" rel="noopener noreferrer">
            /r#xxx… (129 caracteres)
          </a>
          <span className="text-base text-tenue">{TOKEN_LARGO}</span>
        </li>
      </ul>
    </main>
  )
}
