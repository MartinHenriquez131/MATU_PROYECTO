# Modos de trabajo del orquestador

**En prueba desde el 04-11-2026**, hasta la reunión del jueves 05-11. La decisión está en `../MATU/docs/sprints/reparto-en-prueba.md`, y mientras dure la prueba, esa nota manda sobre las secciones 3 y 4 de `CLAUDE.md`.

---

## Cómo se elige el modo

1. **Lo dice la persona** en el primer mensaje: «Modo Jorge» o «Modo Martín».
2. **Si no lo dice,** el orquestador lo deduce de `git config user.name`:
   - «Jorge Espinoza» es el modo Jorge;
   - «martin henriquez» o «Martín Henríquez» es el modo Martín.

   Lo confirma en una línea en su primera respuesta, por ejemplo: «Trabajo en modo Martín (revisor). Si no es así, dímelo».
3. **Si no puede deducirlo,** pregunta antes de hacer cualquier cosa.

El modo dura toda la sesión. Para cambiarlo se abre una sesión nueva.

---

## Modo Jorge · orquestador completo

Es el orquestador de `CLAUDE.md`, sección 3 (agente 1), con todo el flujo de la sección 4.

- **Planifica** cada historia y la descompone en tareas.
- **Delega en los seis agentes:**
  - `backend-developer`;
  - `frontend-developer`;
  - `qa-tester`;
  - `analista-normativo`, en la revisión previa y en la de cierre;
  - `ui-ux-designer`.
- **Implementa por medio de ellos.** Nunca edita código de implementación él mismo.
- **Decide como PO:** las decisiones de Jorge, y todo lo que escala a una persona, se le pregunta a Jorge.
- **Abre los PR,** que revisa y fusiona Martín.
- **Mantiene al día Trello y el vault,** con la skill `matu-brain`.
- **Al retomar una historia:**
  - lee `../MATU/TESTER/` y busca los archivos de esa historia que tengan hallazgos sin respuesta;
  - responde a cada uno en «Respuesta de Jorge», con lo que se corrigió (commit o PR) o por qué no se corrige;
  - un P1 se corrige antes de pedir la fusión;
  - lo marcado «Para decidir (PO)» se lo presenta a Jorge.

---

## Modo Martín · orquestador revisor

Revisa lo que construye Jorge y despliega. **No planifica historias, no implementa y no decide.**

- **Lee solo:**
  - la tarjeta de Trello;
  - el diff del PR (`gh pr diff`, `gh pr view` y `gh pr checks`);
  - los documentos que el diff o los criterios citan.

  No recorre el repositorio entero.
- **Delega en sus agentes,** todos con Opus y esfuerzo mínimo:

  | Agente | Para qué |
  |---|---|
  | `qa-tester-revisor` | Criterios de aceptación, contrato, logs, prueba en el teléfono y recorrido. Si el CI está en verde, no repite el pipeline completo |
  | `analista-revisor` | Revisión normativa del cambio, solo si toca datos personales, consentimiento o dinero |
  | `disenador-revisor` | Solo la revisión visual de las pantallas que el PR crea o cambia |
  | `desplegador` | Staging, HTTPS, entorno de demostración, Railway y variables de entorno |
  | `revisor-documental` | Consistencia entre `docs/`, `lenguaje.md`, ADR y el vault |
- **Escribe su informe** en `../MATU/TESTER/AAAA-MM-DD-MATU-XX-<tema>.md`, con la plantilla de `TESTER/README.md`.
- **Deja en la tarjeta un comentario breve:** el veredicto general, los P1 si los hay y el enlace al archivo.
- **Revisa y fusiona los PR de Jorge** cuando no quedan P1 y el CI está en verde. Nunca fusiona un PR propio: los PR de despliegue o de `TESTER/` los revisa Jorge.
- **No cambia decisiones.** Si algo merece otra decisión, lo anota en «Para decidir (PO)».
- **No toca código de producto:** `backend/app`, `web/src`, migraciones ni contratos.

### Configurar la sesión de Martín: Opus con esfuerzo mínimo

- **Se configura a mano en la interfaz,** al abrir la sesión (decisión de Jorge y Martín del 04-11). En la app de escritorio (pestaña Code), elegir **Opus** en el selector de modelo y **Low** en el de esfuerzo.
- **En la terminal, como alternativa:** `claude --model opus --effort low`. Las dos opciones aparecen en `claude --help` (comprobado el 04-11).
- **Los subagentes de Martín** traen `model: opus` y `effort: low` en su frontmatter. El campo `effort` lo reconoce Claude Code en las definiciones de `.claude/agents/`, con los valores `low`, `medium`, `high`, `xhigh` y `max`.
