// Solo en desarrollo: enlaces de ejemplo del doble del contrato, uno por estado, para la revisión
// del diseñador (especificación MATU-23, sección 8). main.tsx lo carga bajo import.meta.env.DEV,
// así que el build de producción no lo incluye. No es una pantalla de MATU.
import { ESCENARIOS, PIN_DE_EJEMPLO, SIN_FRAGMENTO, TOKEN_LARGO } from '../../doble/escenarios'
import { CONTRASENA_DE_EJEMPLO, CUENTAS } from '../../doble/familia'

export function Ejemplos() {
  // Se abre en una pestaña nueva: el fragmento cambia y la página arranca de cero.
  const enlace = (token: string) => `/r#${token}`
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-8">
      <h1 className="titular text-3xl">Doble del contrato (solo desarrollo)</h1>
      <h2 className="text-xl font-bold">App de la familia (MATU-39)</h2>
      <p className="text-tenue">
        Abre <a className="font-bold text-turquesa underline" href="/">/</a> y entra con una de estas cuentas. La contraseña de todas es{' '}
        <b className="digitos">{CONTRASENA_DE_EJEMPLO}</b>. Para la primera visita, crea una cuenta nueva con cualquier correo.
      </p>
      <ul className="flex flex-col gap-3">
        {CUENTAS.map((c) => (
          <li key={c.email} className="flex flex-col">
            <b className="digitos">{c.email}</b>
            <span className="text-base text-tenue">{c.que}</span>
          </li>
        ))}
      </ul>
      <h2 className="text-xl font-bold">Página del relevo (MATU-23)</h2>
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
