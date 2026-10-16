---
name: matu-brain
description: Consulta y mantiene al día el vault de Obsidian de MATU (../Brain/MATU), el "segundo cerebro" del proyecto. Úsalo para buscar contexto del proyecto y, al cerrar una historia, un pull request, una revisión o una decisión, para actualizar, crear o eliminar notas y dejar el cambio en un commit del vault.
---

# Vault de Obsidian de MATU

El vault está en `../Brain/MATU`, al lado de `MATU_PROYECTO` y de `MATU`. Si la carpeta no existe en este equipo, dilo y no sigas: no todos tienen el vault.

**El vault resume y enlaza. No es la fuente de verdad.** Si una nota contradice `docs/` del repositorio MATU o el código, mandan ellos y se corrige la nota.

## Cuándo se usa

- **Para consultar:** antes de planificar, el vault es la forma rápida de encontrar el contexto. Partir por `MATU · Inicio.md` y los `Mapas/`. Si el detalle importa, leer el documento original en `../MATU/docs/`.
- **Para actualizar:** al cerrar cada tarea, sin que lo pidan. Una tarea es una historia, un pull request abierto, revisado o fusionado, una decisión de diseño, un cambio de estado del sprint o un hito del proyecto. Al final se informa a la persona qué notas cambiaron.

## Antes de editar

1. `git -C ../Brain status`. Si hay cambios que no son tuyos, la persona editó en Obsidian: haz commit de ellos primero con el mensaje `Cambios manuales al <fecha>`, para que los tuyos queden separados
2. Antes de crear una nota, busca si ya existe por su título, su `id` o sus `aliases` (`Grep` en `../Brain/MATU`). Se actualiza la existente, no se duplica

## Convenciones del vault

**Propiedades.** Toda nota parte con este bloque:

```yaml
---
tipo: "historia"
tags: ["matu/historia"]
proyecto: "MATU"
actualizado: "2026-10-16"
---
```

- `actualizado` se pone en la fecha de hoy cada vez que la nota cambia
- Lo que tiene un identificador lleva `id` y `aliases: ["MATU-02"]`, para que `[[MATU-02]]` funcione
- Campos por tipo:

| `tipo` | Carpeta | Campos propios | Tag |
|---|---|---|---|
| `historia` | `Planificación/Historias/` | `id`, `sprint`, `responsable`, `horas`, `estado` | `matu/historia` |
| `sprint` | `Planificación/Sprints/` | `sprint`, `inicio`, `fin`, `estado` | `matu/sprint` |
| `adr` | `Decisiones/` | `id`, `estado`, `capa` | `matu/adr` |
| `estado` | `Bitácora/` | `fecha` | `matu/bitacora` |
| `requisito` | `Requisitos/` | `id` | `matu/requisito` |
| `modulo` | `Arquitectura/Módulos/` | | `matu/modulo` |
| `tabla` | `Modelo de datos/Tablas/` | | `matu/tabla` |
| `concepto` | la carpeta del área | | `matu/<área>` |
| `codigo`, `repositorio`, `fuente`, `seccion` | `Fuentes/` | | `matu/fuente` |
| `mapa` | `Mapas/` | | `matu/mapa` |

- Valores de `estado` de una historia: `por hacer`, `en curso`, `en revisión`, `hecha`. De un sprint: `por empezar`, `en curso`, `cerrado`

**Nombres.** Las historias se llaman `MATU-XX Título de la historia.md` y los ADR `ADR-0XX Título.md`, igual que en el backlog.

**Enlaces.**
- Se usa `[[Nota]]` o `[[Nota|texto]]`. Dentro de una tabla, la barra se escapa: `[[Nota\|texto]]`
- La primera mención de un concepto que tiene nota se enlaza
- Ninguna nota queda huérfana: toda nota nueva se enlaza desde su mapa en `Mapas/` y, si corresponde, desde la nota del sprint
- Al final de una nota derivada de un documento va `Fuente: [[...]]`

**Redacción.** Español chileno neutro, sin punto y coma. Fechas como "16 de octubre". Negrita solo para lo que importa. Las entrevistas siempre anonimizadas, nunca con nombres propios. Nunca datos reales de personas, contraseñas ni secretos.

## Qué actualizar al cerrar una tarea

| Pasó esto | Se actualiza |
|---|---|
| Avanza o se cierra una historia | La nota de la historia: `estado`, y una sección `## Avance` con la fecha, la rama, el pull request, lo hecho, las pruebas y lo pendiente. Las horas reales solo si la persona las dio |
| Se abre, revisa o fusiona un pull request | La historia que corresponde. Si no corresponde a una historia, la nota del repositorio en `Equipo/` |
| Se toma una decisión de diseño | Una nota en `Decisiones/` y su fila en `Mapas/Decisiones (ADR).md`. Si reemplaza a otra, la anterior cambia su `estado` |
| Cambia un documento que tiene copia en `Fuentes/` | La copia, por ejemplo el README, `ci.yml` o la plantilla de pull request |
| Un hito del proyecto | Una fila en `Bitácora/Línea de tiempo.md` |
| Empieza o se cierra un sprint | La nota del sprint y una nota nueva `Bitácora/Estado al <fecha>.md`, enlazada desde `MATU · Inicio.md` |

## Eliminar

- Solo se elimina una nota duplicada o equivocada. Lo que quedó obsoleto no se borra: se marca, como `ADR-020 Retirado`
- Antes de eliminar, busca quién la enlaza (`Grep "\[\[Título"`) y corrige esos enlaces
- Se elimina con `git -C ../Brain rm`, para que se pueda recuperar

## Cerrar

1. `git -C ../Brain add -A` y `git -C ../Brain commit -m "<historia o tarea>: <qué cambió>"`. El vault no tiene remoto, así que no se hace push
2. Informa a la persona, en una lista corta, qué notas creaste, cambiaste o eliminaste
