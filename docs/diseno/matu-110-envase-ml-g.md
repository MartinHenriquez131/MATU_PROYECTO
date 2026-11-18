# MATU-110 · El envase de un insumo en ml o g no habla de «unidades» · Especificación de diseño

**Versión 1.0 · 17/11/2026** · Agente 6, UI/UX. Especifica y no construye. Corrige la sección 9 de `matu-60-lista-insumos.md` (v1.2) para los insumos que se cuentan en ml y en g. No agrega tokens ni componentes.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual. **[L 21]** es un texto ya aprobado de la sección 21 de `docs/lenguaje.md` (repositorio MATU). **[NUEVO]** es un texto que esta especificación propone y que va a la sección 21 en el PR de documentos, para que Jorge lo apruebe. `{u}` es el número de `unidades_por_envase`, con punto de miles.

---

## 0. El problema, visto en el código de hoy

- Al cambiar un insumo en ml, por ejemplo «Crema humectante», el formulario termina con el campo del envase. Su etiqueta sale de `LISTA.envase(unidad)` (`web/src/familia/textos.ts`), que solo distingue `sobre`: para `unidad`, `ml` y `g` dice «¿Cuántas unidades trae cada envase?».
- El sufijo del campo ya está bien: sale de `INSUMOS.sufijoStock(unidad)` y dice «ml» o «g». El resultado es una pregunta por **unidades** con la respuesta en **ml**, que no se entiende.
- El mismo problema está en el conflicto (412): «Sin unidades por envase.» (`LISTA.sinEnvase`), también en ml y g.

## 1. Decisión: el campo se muestra, y pregunta en la unidad del insumo

**Se muestra en ml y en g.** No se esconde, por tres razones que están en el código y en el contrato:

1. **La lista lo usa.** Con `unidades_por_envase`, la API sugiere envases enteros también en ml y g (decisiones 119 a 121), y la lista dice «2 envases de 400 ml» (MATU-60, 4.5, fila «Con envase, en ml o g», [L 21]). Es justo lo que Carmen lleva a la farmacia: un frasco, no «800 ml».
2. **«Compré» lo usa.** Con el envase guardado, «Compré» pregunta en envases con 1 por omisión, sin mirar la unidad (`Insumos.tsx`, `conEnvase`). Para la crema, «Compré 1 envase de 400 ml» es un toque; sin el envase, Carmen tiene que escribir 400.
3. **D2 de MATU-84 no lo quita.** D2 deja fuera de ml y g solo el **conteo** de lo que queda en envases enteros más sueltos («Contar en envases»), porque nadie cuenta «3 frascos y 120 ml». El dato del envase sigue existiendo para la lista y para «Compré». Esconder el campo dejaría un dato guardado que nadie puede ver ni borrar.

**Pregunta en la unidad del insumo**, con la misma forma que la pregunta de «Compré» en esa unidad («¿Cuántos ml compraste?», «¿Cuántos gramos compraste?», aprobadas por Jorge el 03-11): «ml» se dice así, y «g» se escribe «gramos» en la pregunta y «g» en el sufijo.

## 2. Textos exactos

| Parte | `unidad` | `sobre` | `ml` | `g` |
|---|---|---|---|---|
| Etiqueta del campo | «¿Cuántas unidades trae cada envase?» [L 21] | «¿Cuántos sobres trae cada envase?» [L 21, MATU-88] | «¿Cuántos ml trae cada envase?» **[NUEVO]** | «¿Cuántos gramos trae cada envase?» **[NUEVO]** |
| Ayuda (antes del campo) | «Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco.» [L 21] | igual | igual | igual |
| Sufijo | «unidades» | «sobres» | «ml» | «g» |
| Error de rango y 422 | «Escribe un número de 1 a 10.000, o déjalo en blanco.» [L 21] | igual | igual | igual |
| Conflicto 412, con envase | «Cada envase trae `{u}` unidades.» (con 1: «1 unidad») [L 21] | «Cada envase trae `{u}` sobres.» (con 1: «1 sobre») [L 21] | «Cada envase trae `{u}` ml.» [L 21] | «Cada envase trae `{u}` g.» [L 21] |
| Conflicto 412, sin envase | «Sin unidades por envase.» [L 21] | «Sin sobres por envase.» **[NUEVO]** | «Sin ml por envase.» **[NUEVO]** | «Sin gramos por envase.» **[NUEVO]** |

- El sufijo y «Cada envase trae…» no cambian: ya siguen la unidad.
- «Escribe cuántas unidades trae cada envase.» (`errFaltaEnvase`) solo aparece en «Contar en envases», que en ml y g no existe (D2). No necesita versión en ml ni g.
- **Implementación sugerida para el frontend:** `LISTA.envase(unidad)` y `LISTA.sinEnvase` pasan a ser funciones de la unidad, con una tabla `{ unidad, sobre, ml, g }`, como `INSUMOS.sufijoStock`. Ningún otro cambio.

## 3. Esquema a 360 px (insumo en ml, al cambiar)

```
│ ¿Con cuántos días de anticipación  │
│ te avisamos?                       │
│ [ − ] [  7  ] [ + ]  días antes    │
│                                    │
│ ¿Cuántos ml trae cada envase?      │  label font-bold
│ Si lo anotas, la lista sugiere     │  ayuda text-base text-tenue, ANTES del campo
│ envases enteros. Puedes dejarlo en │
│ blanco.                            │
│ ┌──────────┐                       │  campo min-h-12 w-32 (angosto:w-full), ring-2 ring-inset ring-borde
│ │   400    │ ml                    │  sufijo text-base text-tenue
│ └──────────┘                       │
│ ┃ Así, alcanza para …              │  vista previa (sin cambios)
│ [ Guardar ]   Cancelar             │
```

En pantalla ancha es igual que hoy (MATU-60, 9.1): el formulario no cambia de composición. Mismo lugar, mismos tokens, mismo componente `CampoEnvase`.

## 4. Estados

Sin cambios respecto de MATU-60, 9.2 a 9.4: vacío al anotar, con el valor guardado al cambiar, error bajo el campo con `aria-invalid`, y el 412 con los textos de la tabla de la sección 2. No hay estado de carga propio.

## 5. Criterios verificables

1. Un insumo en ml muestra «¿Cuántos ml trae cada envase?» y el sufijo «ml». Ninguna palabra «unidades» en el campo.
2. Un insumo en g muestra «¿Cuántos gramos trae cada envase?» y el sufijo «g».
3. Unidades y sobres siguen con sus textos de hoy, sin ningún cambio visible.
4. En el 412 de un insumo en ml sin envase, el bloque dice «Sin ml por envase.».
5. En ml y g sigue sin aparecer «Contar en envases» (D2).
6. Prueba en `Insumos.test.tsx`: un perfil en ml y uno en g, con la etiqueta exacta, que falla con el texto de hoy (definición de terminado, punto 6).

## 6. Relacionado, fuera de esta tarjeta (decide el orquestador)

En «Mis datos» (`DatosPersona.tsx`, MATU-54), cada insumo dice «`{n}` por envase.» sin la unidad: en la crema se lee «400 por envase.». Con la unidad sería «400 ml por envase.», «20 unidades por envase.», «10 sobres por envase.» (P3). Si se corrige, conviene que use la misma `sufijoCantidad(u, unidad, null)` del conflicto.
