// Cuentas de ejemplo del doble de la familia: solo datos, sin dependencias de Node, porque las
// importa también la lista de /ejemplos en el navegador. Datos sintéticos.

export const CONTRASENA_DE_EJEMPLO = 'contrasena-ejemplo' // pragma: allowlist secret

export interface CuentaDeEjemplo {
  email: string
  que: string
}

export const CUENTAS: CuentaDeEjemplo[] = [
  { email: 'carmen@ejemplo.cl', que: 'Admin con María y «Su día» escrito (1 de 3). Quién la vio: 27 líneas en dos páginas (los 4 tipos, Carla sin abrir la ficha, Pedro bloqueado; hoy, ayer, hace 3 días y desde hace 10). Enlaces: Rosa y Carla abren ahora, Tomás cortado, Pedro bloqueado y un enlace anterior de Rosa vencido con el teléfono ya borrado («Ya no guardamos su teléfono.»). El correo ya tiene cuenta: úsalo en Crear cuenta para ver el 409' },
  { email: 'vacia@ejemplo.cl', que: 'Admin con la ficha en 0 de 3, nadie que la haya abierto (Quién la vio vacío) y sin enlaces (Enlaces vacío; Compartir con los tres campos «Sin completar»)' },
  { email: 'cuidador@ejemplo.cl', que: 'Cuidador con las mismas aperturas que Carmen' },
  { email: 'aperturas-falla@ejemplo.cl', que: 'Quién la vio: la primera página abre y «Ver aperturas anteriores» responde 500' },
  { email: 'completa@ejemplo.cl', que: 'Ficha en 3 de 3 (un campo lo escribió Rodrigo)' },
  { email: 'dos-grupos@ejemplo.cl', que: 'Dos grupos y dos personas: selector de persona' },
  { email: 'sin-persona@ejemplo.cl', que: 'Admin con grupo y sin persona: va a «¿A quién cuidas?»' },
  { email: 'sin-persona-pagador@ejemplo.cl', que: 'Pagador con grupo y sin persona: «Todavía no hay nadie registrado…»' },
  { email: 'pagador@ejemplo.cl', que: 'Pagador sin puede_ver_plan: sin «Ficha» en la navegación; /ficha muestra «No tienes acceso»' },
  { email: 'pagador-ve@ejemplo.cl', que: 'Pagador con puede_ver_plan: ve la ficha y Quién la vio; al guardar, 404 y «No tienes acceso». Ve los enlaces (Quién la vio y /compartir/enlaces) sin teléfono ni «Cortar»; /compartir lo lleva a su inicio' },
  { email: 'observador@ejemplo.cl', que: 'Observador: solo Insumos; /ficha y /ficha/quien-la-vio a mano no piden nada' },
  { email: 'sin-autorizacion@ejemplo.cl', que: 'La ficha responde 403 sin-consentimiento (lenguaje 6.4)' },
  { email: 'renovar-autorizacion@ejemplo.cl', que: 'La ficha responde 403 revision-vencida (lenguaje 6.4b)' },
  { email: 'revision-al-guardar@ejemplo.cl', que: 'La ficha abre y al guardar responde 403 revision-vencida: lo escrito se muestra para copiar' },
  { email: 'conflicto@ejemplo.cl', que: 'Cada primer guardado de un campo responde 412: Rodrigo lo guardó mientras escribías' },
  { email: 'defectos@ejemplo.cl', que: 'Guardar «Su día» 428, «Si se altera» 422 string_too_long, «A quién llamar» 500' },
  { email: 'vence@ejemplo.cl', que: 'El token dura 20 s y la entrada 40 s: escribe y guarda pasado ese tiempo para ver la entrada vencida con texto sin guardar' },
  { email: 'lento@ejemplo.cl', que: 'Cada respuesta tarda 2 s: «Cargando…», «Guardando…»' },
  { email: 'largos@ejemplo.cl', que: 'Nombres largos y un campo de 480 caracteres, para revisar el texto al 200%' },
  // MATU-50: secciones complementarias
  { email: 'secciones-ninguna@ejemplo.cl', que: 'Ficha en 3 de 3 sin secciones: «Más sobre María» con las seis en «Puedes agregar», sin línea de lo agregado' },
  { email: 'secciones-algunas@ejemplo.cl', que: 'Ficha en 3 de 3 con Quién es y Cómo hablarle: «Agregaste 2 secciones.»' },
  { email: 'secciones-remedios@ejemplo.cl', que: 'Ficha en 1 de 3 con Lo que le hace bien y Sus remedios (aviso en la tarjeta, en la hoja y en el editor; tope 800)' },
  { email: 'secciones-todas@ejemplo.cl', que: 'Las seis secciones: sin «Puedes agregar»' },
  { email: 'secciones-conflicto@ejemplo.cl', que: 'Primer guardado o quitar de cada sección: 412 (Rodrigo la cambió o la agregó). Moverse y descansar: Rodrigo la quitó (412 sin versión): al guardar, «Otra persona quitó…» con «Agregarla de nuevo»; al quitar, «ya no estaba»' },
  { email: 'secciones-defectos@ejemplo.cl', que: 'Guardar o quitar «Quién es» 428, «Lo que le hace bien» 422 largo_maximo, cualquier otra 500' },
  { email: 'secciones-pagador@ejemplo.cl', que: 'Pagador con puede_ver_plan y dos secciones: ve los botones y al guardar, 404 y «No tienes acceso»' },
  { email: 'secciones-largas@ejemplo.cl', que: 'Nombres largos y las seis secciones en su tope (500 y 800), para el texto al 200%' },
  // MATU-48: compartir y cortar
  { email: 'enlaces-pausa@ejemplo.cl', que: 'La revisión anual venció (403 revision-vencida en la ficha) y hay enlaces que la API lista como vigentes: en Enlaces, el aviso de pausa y «En pausa» en vez de «Activo»; «Cortar» sigue disponible. Abre primero la ficha (es lo que dice a la app que la autorización venció)' },
  { email: 'enlaces-muchos@ejemplo.cl', que: 'Un enlace activo y 25 que ya no abren: «Ver enlaces anteriores» y «No hay más.»' },
  { email: 'enlaces-cortar-falla@ejemplo.cl', que: 'Cortar responde 500: «No pudimos cortar el enlace… El enlace todavía abre.» y la tarjeta sigue «Activo»' },
  { email: 'enlaces-lista-falla@ejemplo.cl', que: 'La lista de enlaces responde 500: error en Enlaces y en «Quién puede verla ahora»' },
  { email: 'compartir-nombre@ejemplo.cl', que: 'Crear enlace responde 422 nombre_relevo' },
  { email: 'compartir-telefono@ejemplo.cl', que: 'Crear enlace responde 422 telefono_relevo' },
  { email: 'compartir-avise@ejemplo.cl', que: 'Crear enlace responde 422 relevo_informado (con la casilla marcada)' },
  { email: 'compartir-vence-pasada@ejemplo.cl', que: 'Crear enlace responde 422 expira_en vigencia_pasada' },
  { email: 'compartir-vence-maxima@ejemplo.cl', que: 'Crear enlace responde 422 expira_en vigencia_maxima' },
  { email: 'compartir-seccion@ejemplo.cl', que: 'Con secciones: al crear con alguna marcada, Rodrigo quita la primera y responde 422 seccion_no_agregada (la ficha se vuelve a leer)' },
  { email: 'compartir-caido@ejemplo.cl', que: 'Crear enlace responde 503 (compartir falla cerrado)' },
  { email: 'compartir-falla@ejemplo.cl', que: 'Crear enlace responde 500: texto general, el formulario se queda' },
  { email: 'espera@ejemplo.cl', que: 'Entrar responde 429 con Retry-After: 90 («Espera 2 minutos»)' },
  { email: 'espera-1@ejemplo.cl', que: 'Entrar responde 429 con Retry-After: 30 («Espera 1 minuto»)' },
  { email: 'caido@ejemplo.cl', que: 'Entrar responde 503' },
]
