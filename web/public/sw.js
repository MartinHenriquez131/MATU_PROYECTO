// Service worker de MATU (MATU-55, especificación 3.4, decisión de Jorge D6 = a). Solo existe para
// recibir los avisos de un insumo que se está acabando. No intercepta peticiones, no guarda nada en
// caché y nunca lee el contenido del aviso: el texto es siempre el mismo y no dice qué insumo ni de
// quién (lenguaje.md, sección 20). En el piloto el envío es simulado, así que no llega nada.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))

self.addEventListener('push', (e) => {
  e.waitUntil(
    self.registration.showNotification('MATU', {
      body: 'Un insumo se está acabando. Abre la app para ver cuál.',
      lang: 'es-CL',
      icon: '/icono-192.png',
      tag: 'matu-insumo',
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
