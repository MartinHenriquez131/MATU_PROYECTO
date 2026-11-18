// Service worker de MATU (MATU-55, especificación 3.4, decisión de Jorge D6 = a; MATU-76, D-76-1 a).
// Solo existe para recibir los avisos en el teléfono: el de un insumo que se está acabando y los de
// un pedido. No intercepta peticiones, no guarda nada en caché y nunca lee el contenido del aviso,
// que llega vacío: el texto es siempre el mismo, «MATU · Tienes una novedad. Abre la app para verla.»,
// y no dice qué insumo, qué pedido ni de quién. En el piloto el envío es simulado: no llega nada.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))

self.addEventListener('push', (e) => {
  e.waitUntil(
    self.registration.showNotification('MATU', {
      body: 'Tienes una novedad. Abre la app para verla.',
      lang: 'es-CL',
      icon: '/icono-192.png',
      tag: 'matu-novedad',
    }),
  )
})

// El enlace no lleva identificadores ni token: abre la app en su inicio.
self.addEventListener('notificationclick', (e) => {
  e.notification.close()
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((ventanas) => {
      const abierta = ventanas.find((v) => new URL(v.url).origin === self.location.origin && new URL(v.url).pathname !== '/r')
      return abierta ? abierta.focus() : self.clients.openWindow('/')
    }),
  )
})
