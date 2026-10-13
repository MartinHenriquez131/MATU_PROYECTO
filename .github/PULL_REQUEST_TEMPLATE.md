## Descripción del cambio

(Explica brevemente qué resuelve este PR y a qué historia de Trello corresponde, por ejemplo MATU-04)

## Definición de terminado

Antes de aprobar, verifica que el cambio cumple la definición de terminado de la estrategia de pruebas (sección 12):

- [ ] Tiene pruebas de dominio de sus reglas nuevas
- [ ] Tiene al menos una prueba de integración del camino feliz y una del principal camino de error
- [ ] El pipeline pasa completo, incluidas las pruebas de arquitectura y de aislamiento
- [ ] Si toca una pantalla, cumple el checklist de accesibilidad
- [ ] Si toca dinero o datos sensibles, lo revisó la otra persona del equipo
- [ ] Si corrige un defecto, deja una prueba que falla sin la corrección
- [ ] Si el código lo generó un asistente de IA, se revisó igual que el escrito a mano y no se le entregaron datos reales ni secretos
