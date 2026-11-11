// Cuentas de ejemplo del doble de la familia: solo datos, sin dependencias de Node, porque las
// importa también la lista de /ejemplos en el navegador. Datos sintéticos.

export const CONTRASENA_DE_EJEMPLO = 'contrasena-ejemplo' // pragma: allowlist secret

export interface CuentaDeEjemplo {
  email: string
  que: string
}

export const CUENTAS: CuentaDeEjemplo[] = [
  { email: 'carmen@example.com', que: 'Admin con María y «Su día» escrito (1 de 3). Quién la vio: 27 líneas en dos páginas (los 4 tipos, Carla sin abrir la ficha, Pedro bloqueado; hoy, ayer, hace 3 días y desde hace 10). Enlaces: Rosa y Carla abren ahora, Tomás cortado, Pedro bloqueado y un enlace anterior de Rosa vencido con el teléfono ya borrado («Ya no guardamos su teléfono.»). Insumos: la lista completa (6, 1, 0 y −2 días, 60 caracteres, por sobre, cada 2 días, dos sin seguir en la primera página y «Ver más» con el tercero). El correo ya tiene cuenta: úsalo en Crear cuenta para ver el 409' },
  { email: 'vacia@example.com', que: 'Admin con la ficha en 0 de 3, nadie que la haya abierto (Quién la vio vacío) y sin enlaces (Enlaces vacío; Compartir con los tres campos «Sin completar»)' },
  { email: 'cuidador@example.com', que: 'Cuidador con las mismas aperturas que Carmen' },
  { email: 'aperturas-falla@example.com', que: 'Quién la vio: la primera página abre y «Ver aperturas anteriores» responde 500' },
  { email: 'completa@example.com', que: 'Ficha en 3 de 3 (un campo lo escribió Rodrigo)' },
  { email: 'dos-grupos@example.com', que: 'Dos grupos y dos personas: selector de persona' },
  { email: 'sin-persona@example.com', que: 'Admin con grupo y sin persona: va a «¿A quién cuidas?»' },
  { email: 'sin-persona-pagador@example.com', que: 'Pagador con grupo y sin persona: «Todavía no hay nadie registrado…»' },
  { email: 'pagador@example.com', que: 'Pagador sin puede_ver_plan: sin «Ficha» en la navegación; /ficha muestra «No tienes acceso». Insumos: la lista, solo lectura' },
  { email: 'pagador-ve@example.com', que: 'Pagador con puede_ver_plan: ve la ficha y Quién la vio; al guardar, 404 y «No tienes acceso». Ve los enlaces (Quién la vio y /compartir/enlaces) sin teléfono ni «Cortar»; /compartir lo lleva a su inicio' },
  { email: 'observador@example.com', que: 'Observador: solo Insumos, sin el permiso del consumo («Falta el permiso…»); /ficha y /ficha/quien-la-vio a mano no piden nada' },
  { email: 'sin-autorizacion@example.com', que: 'La autorización de la ficha se retiró hace una hora: la ficha responde 403 sin-consentimiento (lenguaje 6.4) con «Volver a autorizar»' },
  { email: 'renovar-autorizacion@example.com', que: 'La ficha responde 403 revision-vencida (lenguaje 6.4b)' },
  { email: 'revision-al-guardar@example.com', que: 'La ficha abre y al guardar responde 403 revision-vencida: lo escrito se muestra para copiar' },
  { email: 'conflicto@example.com', que: 'Cada primer guardado de un campo responde 412: Rodrigo lo guardó mientras escribías' },
  { email: 'defectos@example.com', que: 'Guardar «Su día» 428, «Si se altera» 422 string_too_long, «A quién llamar» 500' },
  { email: 'vence@example.com', que: 'El token dura 20 s y la entrada 40 s: escribe y guarda pasado ese tiempo para ver la entrada vencida con texto sin guardar' },
  { email: 'lento@example.com', que: 'Cada respuesta tarda 2 s: «Cargando…», «Guardando…»' },
  { email: 'largos@example.com', que: 'Nombres largos y un campo de 480 caracteres, para revisar el texto al 200%' },
  // MATU-50: secciones complementarias
  { email: 'secciones-ninguna@example.com', que: 'Ficha en 3 de 3 sin secciones: «Más sobre María» con las seis en «Puedes agregar», sin línea de lo agregado' },
  { email: 'secciones-algunas@example.com', que: 'Ficha en 3 de 3 con Quién es y Cómo hablarle: «Agregaste 2 secciones.»' },
  { email: 'secciones-remedios@example.com', que: 'Ficha en 1 de 3 con Lo que le hace bien y Sus remedios (aviso en la tarjeta, en la hoja y en el editor; tope 800)' },
  { email: 'secciones-todas@example.com', que: 'Las seis secciones: sin «Puedes agregar»' },
  { email: 'secciones-conflicto@example.com', que: 'Primer guardado o quitar de cada sección: 412 (Rodrigo la cambió o la agregó). Moverse y descansar: Rodrigo la quitó (412 sin versión): al guardar, «Otra persona quitó…» con «Agregarla de nuevo»; al quitar, «ya no estaba»' },
  { email: 'secciones-defectos@example.com', que: 'Guardar o quitar «Quién es» 428, «Lo que le hace bien» 422 largo_maximo, cualquier otra 500' },
  { email: 'secciones-pagador@example.com', que: 'Pagador con puede_ver_plan y dos secciones: ve los botones y al guardar, 404 y «No tienes acceso»' },
  { email: 'secciones-largas@example.com', que: 'Nombres largos y las seis secciones en su tope (500 y 800), para el texto al 200%' },
  // MATU-48: compartir y cortar
  { email: 'enlaces-pausa@example.com', que: 'La revisión anual venció (403 revision-vencida en la ficha) y hay enlaces que la API lista como vigentes: en Enlaces, el aviso de pausa y «En pausa» en vez de «Activo»; «Cortar» sigue disponible, también al abrir /compartir/enlaces directo' },
  // MATU-44: Grupo familiar, retirar y volver a autorizar
  { email: 'retirar@example.com', que: 'Grupo familiar: la ficha y los insumos autorizados, con dos enlaces que abren («Hoy abren 2»). Retirar los corta; volver a autorizar dentro de los 90 días' },
  { email: 'retirada@example.com', que: 'Grupo familiar: la ficha y los insumos retirados hace 2 días («se borra el…»). Enlaces con la nota «Se retiró la autorización de la ficha.»' },
  { email: 'borrada@example.com', que: 'Grupo familiar: la ficha de María se retiró hace 100 días y ya se borró. Volver a autorizar la deja en blanco: la ficha abre en 0 de 3, sin secciones, y los enlaces siguen cortados' },
  { email: 'grupo-estados@example.com', que: 'Grupo familiar con los cinco estados: María por renovar (sus enlaces «en pausa») y sin el permiso de insumos, Juan retirada, Elena ya borrada (volver a autorizar empieza en blanco)' },
  { email: 'grupo-pagador@example.com', que: 'Grupo familiar como pagador: los mismos estados, sin botones ni la calidad' },
  { email: 'grupo-observador@example.com', que: 'Grupo familiar como observador: los mismos estados, sin botones ni la calidad' },
  { email: 'retiro-falla@example.com', que: 'Retirar responde 500: el error dentro de la confirmación y «Todo sigue como estaba»' },
  { email: 'retiro-otra@example.com', que: 'Retirar responde 409 ya-retirada: «Otra persona de tu grupo ya retiró esta autorización.»' },
  { email: 'retiro-lento@example.com', que: 'Cada respuesta tarda 2 s: «Retirando…», con Esc y «No retirar» sin efecto' },
  { email: 'enlaces-muchos@example.com', que: 'Un enlace activo y 25 que ya no abren: «Ver enlaces anteriores» y «No hay más.»' },
  // MATU-59: el catálogo (/insumos/catalogo). Con carmen@, cuidador@, pagador@ y observador@ se ve con la semilla; con lento@, «Cargando…»
  { email: 'catalogo-vacio@example.com', que: 'Catálogo sin productos: «Todavía no hay productos en el catálogo.»' },
  { email: 'catalogo-apagado@example.com', que: 'Capa 3 apagada, el catálogo responde 404: «El catálogo no está disponible por ahora.», sin reintento' },
  { email: 'catalogo-falla@example.com', que: 'Catálogo responde 503: «No pudimos traer el catálogo…» y «Volver a intentar» falla otra vez' },
  { email: 'enlaces-cortar-falla@example.com', que: 'Cortar responde 500: «No pudimos cortar el enlace… El enlace todavía abre.» y la tarjeta sigue «Activo»' },
  { email: 'enlaces-lista-falla@example.com', que: 'La lista de enlaces responde 500: error en Enlaces y en «Quién puede verla ahora»' },
  { email: 'compartir-nombre@example.com', que: 'Crear enlace responde 422 nombre_relevo' },
  { email: 'compartir-telefono@example.com', que: 'Crear enlace responde 422 telefono_relevo' },
  { email: 'compartir-avise@example.com', que: 'Crear enlace responde 422 relevo_informado (con la casilla marcada)' },
  { email: 'compartir-vence-pasada@example.com', que: 'Crear enlace responde 422 expira_en vigencia_pasada' },
  { email: 'compartir-vence-maxima@example.com', que: 'Crear enlace responde 422 expira_en vigencia_maxima' },
  { email: 'compartir-seccion@example.com', que: 'Con secciones: al crear con alguna marcada, Rodrigo quita la primera y responde 422 seccion_no_agregada (la ficha se vuelve a leer)' },
  { email: 'compartir-caido@example.com', que: 'Crear enlace responde 503 (compartir falla cerrado)' },
  { email: 'compartir-falla@example.com', que: 'Crear enlace responde 500: texto general, el formulario se queda' },
  { email: 'espera@example.com', que: 'Entrar responde 429 con Retry-After: 90 («Espera 2 minutos»)' },
  { email: 'espera-1@example.com', que: 'Entrar responde 429 con Retry-After: 30 («Espera 1 minuto»)' },
  { email: 'caido@example.com', que: 'Entrar responde 503' },
  // MATU-36: Insumos (/insumos)
  { email: 'insumos-permiso@example.com', que: 'Insumos: cuidador sin el permiso del consumo (403 sin-consentimiento): pide el permiso y luego «Anotar un insumo»' },
  { email: 'insumos-vacio@example.com', que: 'Insumos: admin con permiso y sin insumos (lista vacía)' },
  { email: 'insumos-observador@example.com', que: 'Insumos: observador con la lista completa, solo lectura' },
  { email: 'insumos-renovar@example.com', que: 'Insumos: 403 revision-vencida (por renovar)' },
  { email: 'insumos-renovar-observador@example.com', que: 'Insumos: 403 revision-vencida con rol observador' },
  // MATU-37: «Se acaban pronto» dentro de Insumos
  { email: 'alertas@example.com', que: 'Se acaban pronto: admin con cuatro avisos (6, 1, 0 y −2 días; título «(4)»); el último no tiene alerta aún (alerta_id null). «Ya lo resolví» los cierra uno a uno' },
  { email: 'alertas-sin@example.com', que: 'Se acaban pronto: admin sin avisos (todo alcanza para más de 7 días): la pantalla es la de MATU-36, sin bloque' },
  { email: 'alertas-cero@example.com', que: 'Se acaban pronto: admin con un insumo que ya no queda y se usa 4 al día; «Ya lo resolví» con 1 a 3 deja el recálculo en 0 («Si te quedan menos, cámbialo en la lista.»)' },
  { email: 'alertas-observador@example.com', que: 'Se acaban pronto: observador, ve el bloque y «Te estamos avisando» sin «Ya lo resolví»' },
  { email: 'alertas-cerrada@example.com', que: 'Se acaban pronto: cuidador; el primer «Ya lo resolví» de cada insumo responde 409 alerta-cerrada («Alguien de tu familia ya resolvió este aviso» y «Ver cómo quedó»)' },
  { email: 'alertas-conflicto@example.com', que: 'Se acaban pronto: cuidador; el primer «Ya lo resolví» de cada insumo responde 412 (Rodrigo lo cambió: «… mientras lo resolvías» y «Ver cómo quedó»). Resolver exige If-Match (sin él, 428)' },
  { email: 'alertas-error@example.com', que: 'Se acaban pronto: «Ya lo resolví» responde 500 («No pudimos guardar…»)' },
  { email: 'alertas-error-carga@example.com', que: 'Se acaban pronto: por-acabarse responde 500; la lista se ve y el bloque dice «No pudimos ver qué se acaba pronto»' },
  { email: 'insumos-defectos@example.com', que: 'Insumos: cambiar «Pañal» responde 412 una vez, «Apósitos» 409 perfil-inactivo, «Guantes» 500; anotar «Error» responde 500; stock 100000 con uso 1 da 422 cobertura_maxima' },
  // MATU-60: la lista de insumos (/insumos/lista)
  { email: 'lista@example.com', que: 'Lista de insumos: admin con seis líneas (6, 5, 3, 1, 0 y −2 días; con envase, en sobres, en ml con 1 envase y un nombre de 60 caracteres sin espacios). «Se acaban pronto» en Insumos muestra los mismos' },
  { email: 'lista-cuidador@example.com', que: 'Lista de insumos: cuidador, la misma lista' },
  { email: 'lista-pagador@example.com', que: 'Lista de insumos: pagador, cambia, agrega, quita y saca la lista, con la nota «lo que anotó la familia»' },
  { email: 'lista-observador@example.com', que: 'Lista de insumos: observador, ve las líneas sin campos ni botones' },
  { email: 'lista-vacia@example.com', que: 'Lista de insumos: admin con un solo insumo, que alcanza para 40 días: «No hay insumos que se acaben pronto»' },
  { email: 'lista-permiso-cuidador@example.com', que: 'Lista de insumos: cuidador sin el permiso (403 sin-consentimiento): /insumos/lista lleva a Insumos, que pide el permiso' },
  { email: 'lista-permiso-observador@example.com', que: 'Lista de insumos: observador sin el permiso (403 sin-consentimiento): «Falta el permiso…»' },
  { email: 'lista-renovar@example.com', que: 'Lista de insumos: 403 revision-vencida («Hay que renovar…»)' },
  { email: 'lista-error@example.com', que: 'Lista de insumos: la lista responde 500 («No pudimos traer la lista…» y «Volver a intentar»)' },
  // MATU-51: «Compré» y «Me quedan» en cada insumo (/insumos)
  { email: 'compre@example.com', que: 'Compré y Me quedan: admin. Pañal con envases de 20 en «Se acaban pronto» (comprar 2 lo saca del bloque), toallitas sin envase también en el bloque, champú en sobres, crema en ml con envases de 250 ml, agua en ml que con 1 bidón pasa de 100.000 ml (422 stock_maximo), bolsas que con 1.000 más alcanzan para más de 10 años (422 cobertura_maxima), un nombre de 60 caracteres con envases de 10.000 y uno sin seguir' },
  { email: 'compre-cuidador@example.com', que: 'Compré y Me quedan: cuidador, la misma lista' },
  { email: 'compre-pagador@example.com', que: 'Compré y Me quedan: pagador, la misma lista sin los botones' },
  { email: 'compre-observador@example.com', que: 'Compré y Me quedan: observador, la misma lista sin los botones' },
  { email: 'compre-defectos@example.com', que: 'Compré y Me quedan: el pañal responde 412 una vez (Rodrigo lo cambió), las toallitas 409 perfil-inactivo («Ver cómo quedó» la deja en «Sin seguir»), el champú 404 (ya no está) y la crema 500. El agua y las bolsas dan los 422 de la cuenta compre@' },
  { email: 'compre-renovar@example.com', que: 'Compré y Me quedan: la primera anotación responde 403 revision-vencida («Hay que renovar…»)' },
  { email: 'compre-lento@example.com', que: 'Compré y Me quedan: cada respuesta tarda 2 segundos («Guardando…» y la fila sin cambios hasta la respuesta)' },
  // MATU-84: «Me quedan» y el formulario del insumo en envases (/insumos)
  { email: 'envases@example.com', que: 'Me quedan en envases: admin. Pañal con 20 por envase (abre en envases), champú con 10 sobres por caja, toallitas sin envase («Contar en envases» lo anota con un solo PATCH), guantes con envase de 1 (como sin envase), crema en ml (sin enlace), un nombre de 60 caracteres con 10.000 por envase y bolsas que con unas 2.000 alcanzan para más de 10 años (422 cobertura_maxima)' },
  { email: 'envases-defectos@example.com', que: 'Me quedan en envases: el pañal responde 412 una vez (Rodrigo lo cambió), las toallitas 500 al anotar lo que queda y 422 en unidades_por_envase al anotar el envase, y los guantes 500 al anotar el envase' },
  { email: 'envases-lento@example.com', que: 'Me quedan en envases: cada respuesta tarda 2 segundos («Guardando…», los campos en solo lectura y los enlaces sin efecto)' },
  // MATU-57: recuperar el acceso y confirmar el celular. Los códigos solo se ven en la consola del doble.
  { email: 'celular-verificado@example.com', que: 'Celular confirmado: «Tu cuenta» dice «Confirmado»; recuperar envía el código «al celular»' },
  { email: 'celular-sin-verificar@example.com', que: 'Celular sin confirmar: «Tu cuenta» ofrece «Confirmar celular» (SMS o WhatsApp)' },
  { email: 'celular-espera@example.com', que: 'Pedir el código del celular responde 429 con Retry-After: 120' },
  { email: 'sin-celular@example.com', que: 'Cuenta anterior a MATU-39, sin celular: «Tu cuenta» lo dice, y tampoco tiene registro de la política' },
  // MATU-75: la política de privacidad en «Tu cuenta». Las demás cuentas también la aceptaron, el 09/11/2026.
  { email: 'politica-aceptada@example.com', que: '«Tu cuenta»: «Aceptaste la versión 0.11 el 09/11/2026.», el enlace a la política y cómo pedir con el correo' },
  { email: 'politica-sin-registro@example.com', que: '«Tu cuenta»: «No tenemos registro de qué versión aceptaste.» (una cuenta anterior a MATU-75)' },
  { email: 'recuperar-espera@example.com', que: 'Cambiar la contraseña con el código responde 429 con Retry-After: 120' },
  { email: 'codigo-invalido@example.com', que: 'Cambiar la contraseña responde siempre 422 codigo-invalido' },
  // MATU-61: el pedido (/insumos/pedido). Todas con la autorización de pedidos vigente y dirección, salvo donde se dice.
  { email: 'pedido@example.com', que: 'Pedido: admin con tres productos en borrador; «Ver el total», el resumen, «Cambiar el pedido» y cancelar' },
  { email: 'pedido-cuidador@example.com', que: 'Pedido: cuidadora con el mismo carrito (también cancela, JC3)' },
  { email: 'pedido-vacio@example.com', que: 'Pedido: sin pedido y sin dirección («Tu pedido está vacío.»); agregar desde el catálogo y «Agregar la dirección»' },
  { email: 'pedido-permiso@example.com', que: 'Pedido: cuidadora sin la autorización de pedidos ni dirección, con una lista que trae productos del catálogo («Pedir estos productos»)' },
  { email: 'pedido-renovar@example.com', que: 'Pedido: la autorización de pedidos por renovar («Renovar la autorización»)' },
  { email: 'pedido-pagador@example.com', que: 'Pedido: pagador con el total ya confirmado («Ver el resumen», sin cambiar nada)' },
  { email: 'pedido-observador@example.com', que: 'Pedido: observador, el carrito sin la entrega ni controles' },
  { email: 'pedido-observador-sin@example.com', que: 'Pedido: observador sin la autorización de pedidos («Falta la autorización de pedidos…»)' },
  { email: 'pedido-cambios@example.com', que: 'Pedido: al confirmar, el pañal baja de precio, los protectores pasan a otro comercio y las toallitas salen' },
  { email: 'pedido-plazo@example.com', que: 'Pedido: el total vale 130 s: «Quedan 2 minutos…» a los 10 s, y vence a los 130 s' },
  { email: 'pedido-conflicto@example.com', que: 'Pedido: guardar la dirección responde 412 la primera vez (otra persona la cambió)' },
  { email: 'pedido-falla@example.com', que: 'Pedido: «Ver el total» responde 503 («No pudimos confirmar el total…»)' },
  // MATU-62: el pago. «Pagar» abre la página falsa de Webpay del doble, donde se elige qué pasa.
  { email: 'pago@example.com', que: 'Pago: admin con el total confirmado. «Pagar» → Webpay del doble: débito, crédito en 3 cuotas, prepago, no aprobado, anular compra, tiempo agotado, pendiente 25 s, tardío respetado, anulado (hecho o en curso), sin sesión y token desconocido. «Atrás» desde Webpay deja el pago en curso' },
  { email: 'pago-pagador@example.com', que: 'Pago: pagador con el total confirmado; paga él (casilla y «Pagar»)' },
  { email: 'pago-cuidador@example.com', que: 'Pago: cuidadora con el total confirmado («Pagan quien administra el grupo y quien paga.», sin «Pagar»)' },
  { email: 'pago-en-curso@example.com', que: 'Pago: otra persona está pagando (6.1 en el pedido, 6.2 en el resumen); «Revisar de nuevo» sigue en curso; cancelar suma el párrafo en negrita' },
  { email: 'pago-en-curso-cuidador@example.com', que: 'Pago: cuidadora con un pago en curso (6.1 en el pedido y en el resumen)' },
  { email: 'pago-en-curso-pagador@example.com', que: 'Pago: pagador con un pago en curso (6.2 en el resumen)' },
  { email: 'pago-webpay-caido@example.com', que: 'Pago: «Pagar» responde 503 pasarela-no-disponible («Webpay no responde ahora…»)' },
  { email: 'pago-red@example.com', que: 'Pago: «Pagar» responde 500 («No pudimos abrir Webpay…»)' },
  { email: 'pago-vencido@example.com', que: 'Pago: «Pagar» responde 409 estado-pedido vencido (el estado vencido de 9.6)' },
  { email: 'pago-condiciones@example.com', que: 'Pago: el primer «Pagar» responde 409 condiciones-cambiaron (la casilla se desmarca); el segundo abre Webpay' },
  { email: 'pago-409@example.com', que: 'Pago: «Pagar» responde 409 pago-en-curso (6.2 con el foco)' },
  { email: 'pago-pagado@example.com', que: 'Pago: un pedido pagado con débito por Carmen y un borrador nuevo: «Pedido pagado» al final y «Ver el comprobante» (tarjeta y código, correo del piloto)' },
  { email: 'pago-pagado-otro@example.com', que: 'Pago: lo pagó otra persona (Rodrigo): «Lo pagó otra persona de tu grupo.», sin tarjeta ni correo' },
  { email: 'pago-devoluciones@example.com', que: 'Pago: crédito en 3 cuotas, una devolución hecha (resta, «Pagaste en total») y otra en curso (no resta)' },
  { email: 'pago-devoluciones-otro@example.com', que: 'Pago: las mismas devoluciones vistas por una cuidadora que no pagó («a la tarjeta con que se pagó»)' },
  { email: 'pago-prepago@example.com', que: 'Pago: pagador que pagó con prepago («Tarjeta de prepago terminada en 7720»)' },
  { email: 'pago-tardio@example.com', que: 'Pago: pago tardío respetado (7.6)' },
  { email: 'pago-observador@example.com', que: 'Pago: observador con un pedido pagado: solo «Pedido pagado» y «Pagado»' },
  { email: 'pedido-retirada@example.com', que: 'Pedido: la autorización de pedidos retirada; Grupo familiar con «Ver la dirección de entrega» y «Volver a autorizar»' },
]

/**
 * Dominio que el doble rechaza como staging (decisión 105, `dominio_no_permitido`). Tiene que ser uno
 * que staging no acepte (no es example.com, .org ni .net, ni termina en .test, .example, .invalid o
 * .localhost) y que no sea de nadie: `.internal` lo reservó ICANN en 2024 para redes privadas y nunca
 * se delegará en internet. Un `.cl` inventado podría registrarlo alguien mañana.
 */
export const DOMINIO_NO_PERMITIDO = 'dominio-no-permitido.internal'

/** MATU-75: el primer alta con este correo responde 409 `politica-cambio`; el segundo crea la cuenta. */
export const CORREO_POLITICA_CAMBIO = 'politica-cambio@example.com'

/** Correos para «Crear cuenta» que provocan una respuesta: no son cuentas, no entran. */
export const CORREOS_CREAR_CUENTA: CuentaDeEjemplo[] = [
  { email: 'espera-ip@example.com', que: 'Crear cuenta responde 429 del límite por IP con Retry-After: 61 («Vuelve a intentarlo en 2 minutos.»)' },
  { email: 'espera-ip-60@example.com', que: 'Crear cuenta responde 429 con Retry-After: 60 («Vuelve a intentarlo en 1 minuto.»)' },
  { email: 'espera-ip-sin-cabecera@example.com', que: 'Crear cuenta responde 429 sin Retry-After (se espera 1 minuto, el mínimo)' },
  { email: CORREO_POLITICA_CAMBIO, que: 'Crear cuenta responde 409 politica-cambio la primera vez: «Actualizamos la política de privacidad.», la casilla se desmarca y la huella se vuelve a pedir. La segunda vez crea la cuenta' },
  { email: `persona@${DOMINIO_NO_PERMITIDO}`, que: 'Crear cuenta responde 422 dominio_no_permitido, como staging: «En este ambiente de prueba usa un correo terminado en @example.com.»' },
]
