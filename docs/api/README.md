# Contratos de la API de MATU

Esta carpeta guarda los contratos OpenAPI 3.1 que el frontend usa para construir pantallas (CLAUDE.md, agente 3) y que el backend implementa. Un contrato se acuerda **antes** de implementar (MATU-09, arquitectura 15.5, regla 1).

```
docs/api/
├── README.md                     este archivo
├── openapi.json                  rutas implementadas, exportadas de GET /openapi.json (MATU-13)
└── propuestos/
    ├── ficha.openapi.yaml        MATU-09 parte 1: ficha de relevo
    ├── relevo.openapi.yaml       MATU-09 parte 2: acceso de relevo
    └── app-familia.openapi.yaml  MATU-32: sesión, dispositivos, autorización para el consumo, consumo y alertas
```

## Propuestos e implementados

- **`propuestos/`** tiene los contratos acordados y todavía no implementados. Su `info.version` termina en `-propuesto`. El frontend puede construir contra ellos con un doble (MATU-23 lo hace así).
- **`openapi.json`** tiene solo rutas implementadas. Una ruta pasa de `propuestos/` a `openapi.json` cuando su historia se termina: se exporta desde `GET /openapi.json` de la API y se quita del archivo propuesto en el mismo PR.
- **La puerta openapi-diff** compara `openapi.json` contra lo que expone la API, y nunca mira `propuestos/`. Un cambio en un contrato propuesto no rompe el pipeline; un cambio en una ruta implementada sí.
- Hoy ni `openapi.json` ni la puerta openapi-diff existen en el pipeline (`.github/workflows/ci.yml`). Las rutas ya implementadas (`/v1/usuarios`, `/v1/sesiones`, `/v1/grupos`, `/v1/grupos/{grupo_id}/personas-cuidadas`) se ven en `GET /openapi.json` con la API levantada. Crear los dos queda pendiente, fuera de MATU-09.
- **Las rutas de la ficha (MATU-12) están implementadas pero siguen en `propuestos/`** (revisado el 28-10). El contrato promete dos cosas: 412 y 428 con `If-Match` / `If-None-Match` (MATU-13, pendiente) y el registro de `plan.leer` y `plan.editar` (MATU-14, ya cumplido). Siguen en `propuestos/` solo por MATU-13. Pasarlas a `openapi.json` ahora fijaría como "implementado" un contrato que la API todavía no cumple. Como la puerta openapi-diff no existe y, cuando exista, no mirará `propuestos/`, el CI no puede fallar por esto: MATU-12 no crea `openapi.json` ni toca `ci.yml`. La historia que cierre la última de las dos (MATU-13 o MATU-14) exporta las rutas a `openapi.json` y las quita del propuesto, como dice la regla de arriba. Diferencias que verá openapi-diff ese día: FastAPI agrega un 422 genérico a `GET …/plan/ficha` (por sus parámetros), y `X-Grupo-Id` sale como `string | null` sin `format: uuid`, igual que en las rutas de MATU-07.
- **MATU-13 (29-10) exportó `openapi.json`** desde `app.openapi()` con un comando puntual (no hay script ni puerta openapi-diff todavía; `backend/tests/modules/care_plan/test_ficha_contrato.py` falla si las rutas de la ficha cambian sin volver a exportar): todas las rutas de la API salvo las del relevo, y solo los componentes que esas rutas usan. Las rutas del relevo (`accesos-relevo`, `/v1/relevo/…`) quedan fuera aunque estén implementadas: su contrato sigue en `propuestos/relevo.openapi.yaml` hasta que la historia que lo cierre las exporte, y `/plan/aperturas` aún no existe. `propuestos/ficha.openapi.yaml` se conserva como explicación del orden de evaluación y de las decisiones, que el JSON generado no trae; manda `openapi.json`. Diferencias con el propuesto que se aceptan: `If-Match` e `If-None-Match` salen como `string` sin `const: '*'` (el valor lo valida la ruta: 422 o 428), el 412 y el 428 del PUT llevan esquema (`ProblemaVersion` con `campo` y `actual`, y `falta-version`), ejemplo y cabeceras, pero en línea y no como componentes con nombre; los demás errores (401, 403, 404, 422, 500 y 503) se declaran como `application/problem+json` sin esquema, FastAPI agrega un 422 genérico a `GET …/plan/ficha`, y `X-Grupo-Id` sale como `string | null` sin `format: uuid`.
- Cada archivo propuesto es autocontenido: no hace `$ref` a otro archivo. Los componentes comunes (`Problema`, `ProblemaValidacion`, `ErrorCampo`, `CampoFicha`, `Autor`, `XGrupoId`, `PersonaId`, `bearerAuth`, las cabeceras `XRequestId`, `CacheControlNoStore` y `WWWAuthenticateBearer`, y el cuerpo de `NoAutenticado`, `NoEncontrado` y `SinConsentimiento`) son idénticos en los dos.
- **`app-familia.openapi.yaml` (MATU-32)** copia idénticos de `relevo.openapi.yaml` `Problema`, `ProblemaValidacion`, `ErrorCampo`, `XGrupoId`, `PersonaId`, `Cursor`, `Limite`, `bearerAuth`, `XRequestId`, `CacheControlNoStore`, `WWWAuthenticateBearer`, `NoAutenticado`, `NoEncontrado` y `SinConsentimiento` (verificado con un script que compara los dos YAML). No usa `CampoFicha` ni `Autor`. La descripción de `CacheControlNoStore` habla de la ficha y del relevo; se deja igual para no romper la copia, y el `info.description` del archivo aclara que vale también para sesión, dispositivos, consumo y alertas. `POST /v1/sesiones` aparece en los dos lugares a propósito: `openapi.json` dice lo implementado y `app-familia.openapi.yaml` el cambio que hace MATU-38, que vuelve a exportar `openapi.json`.
- **Cabeceras de respuesta.** Toda respuesta, también las de error, declara `X-Request-ID` (UUID, el mismo `request_id` de los logs y del problema; lo pone `app/core/logs.py`). Llevan `Cache-Control: no-store` las que traen texto de la ficha, PIN o enlace, y también la lista de accesos y `/plan/aperturas`, porque dicen a quién se compartió la ficha y cuándo la abrió. En `app-familia.openapi.yaml` la llevan todas las respuestas de sesión, dispositivos, autorización, consumo y alertas.

## Rutas

| Método y ruta | Historia | Estado |
|---|---|---|
| `GET /v1/personas-cuidadas/{persona_id}/plan/ficha` | MATU-12, MATU-14 | Implementado. En `openapi.json` desde MATU-13 |
| `PUT /v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}` | MATU-12, MATU-13, MATU-11, MATU-14 | Implementado, con `If-Match` / `If-None-Match`, 412 y 428 (MATU-13). En `openapi.json` desde MATU-13 |
| `POST /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo` | MATU-18 | Implementado. Contrato en `relevo.openapi.yaml`, fuera de `openapi.json` |
| `GET /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo` | MATU-18, MATU-20 | Implementado. Contrato en `relevo.openapi.yaml`, fuera de `openapi.json` |
| `DELETE /v1/accesos-relevo/{acceso_id}` | MATU-20 | Implementado. Contrato en `relevo.openapi.yaml`, fuera de `openapi.json` |
| `POST /v1/relevo/presentacion` | MATU-19, MATU-23 | Implementado, sin el 429 de MATU-25. Contrato en `relevo.openapi.yaml` |
| `POST /v1/relevo/canje` | MATU-19, MATU-25 | Implementado, sin el 429 de MATU-25. Contrato en `relevo.openapi.yaml` |
| `GET /v1/relevo/ficha` | MATU-19, MATU-20, MATU-23 | Implementado. Contrato en `relevo.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/plan/aperturas` | MATU-19 (RF-08) | Propuesto |
| `POST /v1/sesiones` | MATU-05a; cambio de MATU-38 | Implementado en `openapi.json`. **Nuevo:** cambio propuesto en `app-familia.openapi.yaml` (cookie del refresh, dispositivo y 429) |
| `POST /v1/sesiones/renovar` | MATU-38 (RF-37) | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `POST /v1/sesiones/cerrar` | MATU-38 (RF-37) | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `GET /v1/dispositivos` | MATU-38 | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `DELETE /v1/dispositivos/{dispositivo_id}` | MATU-38 | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `PUT /v1/dispositivos/actual/push` | MATU-38, la usa MATU-41 | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `DELETE /v1/dispositivos/actual/push` | MATU-38, la usa MATU-41 | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `POST /v1/personas-cuidadas/{persona_id}/consentimientos` | MATU-36 | **Nuevo.** Propuesto en `app-familia.openapi.yaml`. Solo `finalidad: consumo` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo` | MATU-36 (RF-10, RF-11) | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `POST /v1/personas-cuidadas/{persona_id}/consumo` | MATU-36 (RF-10, RF-11) | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}` | MATU-36 | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `PATCH /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}` | MATU-36 | **Nuevo.** Propuesto en `app-familia.openapi.yaml`, con `If-Match`, 412 y 428 |
| `POST /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/desactivar` | MATU-36 | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo/por-acabarse` | MATU-37 (RF-11, RF-12) | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo/alertas` | MATU-37 (RF-12) | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |
| `POST /v1/personas-cuidadas/{persona_id}/consumo/alertas/{alerta_id}/descartar` | MATU-37 (RF-12) | **Nuevo.** Propuesto en `app-familia.openapi.yaml` |

Las filas del relevo decían "Propuesto" aunque MATU-18, MATU-19 y MATU-20 ya se fusionaron: se corrigieron en MATU-32 con lo que hay en `backend/app/modules/care_plan/api/` (31-10). Sus contratos siguen en `relevo.openapi.yaml` hasta que la historia que los cierre los exporte a `openapi.json`.

## Catálogo de `type` (RFC 7807)

Mismo formato que `backend/app/core/errores.py`: `type`, `title`, `status`, `detail`, `errores[]` y `request_id`, en `application/problem+json`. Los `type` marcados **nuevo** no existen todavía en el código y los agrega la historia que los usa. Los del relevo pasaron de **nuevo** a "Existe" en MATU-32 (31-10), porque MATU-19 y MATU-20 ya los agregaron (`backend/app/modules/care_plan/api/`).

| `type` | Status | Cuándo | Origen |
|---|---|---|---|
| `/errores/no-autenticado` | 401 | Falta el access token | Existe (por defecto del 401) |
| `/errores/token-invalido` | 401 | Token inválido, alterado o vencido. En la app de familia significa "renueva" (`POST /v1/sesiones/renovar`) | Existe (MATU-05a) |
| `/errores/credenciales-invalidas` | 401 | `POST /v1/sesiones`: email o contraseña incorrectos, o cuenta que no puede entrar. El mismo cuerpo en todos los casos | Existe (MATU-05a). Faltaba en este catálogo |
| `/errores/sesion-expirada` | 401 | `POST /v1/sesiones/renovar`: sin cookie, cookie desconocida, sesión vencida o revocada, o refresh reutilizado (que revoca la familia). El mismo 401, borra la cookie. Significa "vuelve a entrar" (decisión 44) | **Nuevo** (MATU-38) |
| `/errores/sin-consentimiento` | 403 | Sin consentimiento vigente para `plan_cuidado`. **Nuevo uso:** en el consumo, sin consentimiento vigente para `consumo`, con el miembro de extensión `finalidad: consumo` (decisión 44) | Existe (MATU-12). MATU-07 no definió uno. El uso en el consumo lo agrega MATU-36 |
| `/errores/revision-vencida` | 403 | El consentimiento lo dio un cuidador de hecho y venció su revisión anual (decisión 33). **Nuevo uso:** en el consumo, con `finalidad: consumo` | Existe (MATU-12). El uso en el consumo lo agrega MATU-36 |
| `/errores/no-encontrado` | 404 | No miembro, rol que no alcanza, recurso de otro grupo o inexistente | Existe |
| `/errores/version-desactualizada` | 412 | `If-Match` desactualizado o `If-None-Match: *` sobre un campo que ya existe. **Nuevo uso:** `PATCH` de un perfil de consumo con `If-Match` desactualizado, con el perfil en `actual` | Existe (por defecto del 412) |
| `/errores/validacion` | 422 | Cuerpo, cabeceras o consulta inválidos | Existe |
| `/errores/falta-version` | 428 | Escritura sin `If-Match` ni `If-None-Match`. **Nuevo uso:** `PATCH` de un perfil de consumo sin `If-Match` o con `If-Match: *` | Existe (por defecto del 428) |
| `/errores/email-registrado` | 409 | `POST /v1/usuarios`: ese email ya tiene una cuenta | Existe (MATU-04). Faltaba en este catálogo |
| `/errores/autorizacion-vigente` | 409 | `POST …/consentimientos`: la persona ya tiene una autorización no revocada para esa finalidad (`consentimiento_vigente_uq`) | **Nuevo** (MATU-36) |
| `/errores/perfil-duplicado` | 409 | `POST …/consumo`: ya hay un perfil activo de la persona con ese `producto_id` (`perfil_consumo_producto_uq`) | **Nuevo** (MATU-36) |
| `/errores/perfil-inactivo` | 409 | `PATCH …/consumo/{perfil_id}` sobre un perfil desactivado | **Nuevo** (MATU-36) |
| `/errores/alerta-cerrada` | 409 | `POST …/alertas/{alerta_id}/descartar` sobre una alerta `resuelta` o `descartada`, con el `estado` actual como miembro de extensión | **Nuevo** (MATU-37) |
| `/errores/pin-incorrecto` | 401 | PIN incorrecto, del 1.º al 4.º intento, con `intentos_restantes` | Existe (MATU-19) |
| `/errores/sin-sesion-relevo` | 401 | `GET /v1/relevo/ficha` sin cookie, o con una cookie que no corresponde a una sesión en Redis (alterada o vencida por su TTL). Nunca por revocar | Existe (MATU-19) |
| `/errores/relevo-vencido` | 410 | El acceso venció (presentación, canje, o cualquier petición con cookie válida) | Existe (MATU-19) |
| `/errores/relevo-revocado` | 410 | El acceso se revocó (presentación, canje, o cualquier petición con cookie válida) | Existe (MATU-20) |
| `/errores/relevo-no-disponible` | 410 | El token no corresponde a ningún acceso (presentación o canje) | Existe (MATU-19) |
| `/errores/relevo-pausado` | 410 | La autorización de la persona del acceso no está vigente (consentimiento retirado o revisión anual vencida). No dice el motivo. Presentación, canje y ficha (decisión 33 en el relevo, de Martín del 28-10, pendiente de revisión de Jorge) | Existe (MATU-19) |
| `/errores/relevo-bloqueado` | 423 | 5 PIN incorrectos (presentación, canje o sesión) | Existe (MATU-19) |
| `/errores/error-interno` | 500 | Error inesperado, o una sección de la ficha que no se puede descifrar (alterada o movida). Nunca lleva el texto | Existe (por defecto del 500) |
| `/errores/servicio-no-disponible` | 503 | La custodia de la clave maestra no está configurada, o no envolvió o no desenvolvió la clave de datos (decisión 32). **Nuevo uso:** `POST /v1/sesiones` sin Redis para la demora progresiva (decisión 49) | Existe (MATU-12, por defecto del 503) |
| `/errores/demasiadas-peticiones` | 429 | Más de 30 presentaciones o más de 10 canjes por hora desde una IP, en contadores separados. **Nuevo uso:** demora progresiva de `POST /v1/sesiones`, con `Retry-After` de hasta 900 segundos (decisión 49) | Existe (por defecto del 429), lo usan MATU-25 y MATU-38 |

## Lo que usa la app de familia (MATU-32)

Todas las rutas que usa la app de familia: MATU-39 (la app), MATU-48 y MATU-45 (sus pantallas), MATU-36 (consumo) y MATU-37 (predicción y alertas). La columna "Historia" es la que implementa la ruta en el backend. Revisado contra `backend/app/` el 31-10.

| Método y ruta | Historia | Estado | Contrato |
|---|---|---|---|
| `POST /v1/usuarios` | MATU-04 | Implementado | `openapi.json` |
| `POST /v1/sesiones` | MATU-05a; cambio de MATU-38 | Implementado. Cambio propuesto: cookie del refresh, dispositivo y 429 | `openapi.json`; el cambio en `app-familia.openapi.yaml` |
| `GET /v1/grupos` | MATU-06 | Implementado. Devuelve `id`, `nombre` y `rol`: la app elige el grupo para `X-Grupo-Id` y sabe su rol | `openapi.json` |
| `POST /v1/grupos` | MATU-06 | Implementado | `openapi.json` |
| `GET /v1/grupos/{grupo_id}/personas-cuidadas` | MATU-07 | Implementado, con la vista de cada rol | `openapi.json` |
| `POST /v1/grupos/{grupo_id}/personas-cuidadas` | MATU-07 | Implementado | `openapi.json` |
| `GET /v1/personas-cuidadas/{persona_id}/plan/ficha` | MATU-12, MATU-14 | Implementado | `openapi.json` |
| `PUT /v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}` | MATU-12, MATU-13, MATU-14 | Implementado | `openapi.json` |
| `POST /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo` | MATU-18 | Implementado | `relevo.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo` | MATU-18, MATU-20 | Implementado | `relevo.openapi.yaml` |
| `DELETE /v1/accesos-relevo/{acceso_id}` | MATU-20 | Implementado | `relevo.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/plan/aperturas` | MATU-19 (RF-08) | Propuesto, sin implementar | `relevo.openapi.yaml` |
| `POST /v1/sesiones/renovar` | MATU-38 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `POST /v1/sesiones/cerrar` | MATU-38 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `GET /v1/dispositivos` | MATU-38 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `DELETE /v1/dispositivos/{dispositivo_id}` | MATU-38 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `PUT /v1/dispositivos/actual/push` | MATU-38, para MATU-41 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `DELETE /v1/dispositivos/actual/push` | MATU-38, para MATU-41 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `POST /v1/personas-cuidadas/{persona_id}/consentimientos` | MATU-36 | **Nuevo**, propuesto. Pendiente de Jorge (decisión 37) y de la política 0.10 | `app-familia.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo` | MATU-36 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `POST /v1/personas-cuidadas/{persona_id}/consumo` | MATU-36 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}` | MATU-36 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `PATCH /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}` | MATU-36 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `POST /v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/desactivar` | MATU-36 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo/por-acabarse` | MATU-37 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `GET /v1/personas-cuidadas/{persona_id}/consumo/alertas` | MATU-37 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |
| `POST /v1/personas-cuidadas/{persona_id}/consumo/alertas/{alerta_id}/descartar` | MATU-37 | **Nuevo**, propuesto | `app-familia.openapi.yaml` |

La app de familia no usa `/v1/relevo/…` (es la página del relevo, MATU-23) ni `GET /v1/salud`.

**Cómo arranca la app** (decisiones 39 y 40): al abrir o recargar no tiene access token, porque vive solo en memoria. Llama a `POST /v1/sesiones/renovar` con `X-MATU-Cliente: web`: un 200 trae el access token, y un 401 `sesion-expirada` lleva a la pantalla de entrada. Después, `GET /v1/grupos` para elegir el grupo y conocer el rol. Ante un 401 `token-invalido` en cualquier ruta, renueva una vez y repite la petición; si la renovación responde 401, vuelve a la entrada.

**Lo que no hay, y la app no debe inventar** (verificado en `backend/app/` el 31-10):

- **`GET /v1/usuarios/yo` no existe.** Tras recargar, la app no sabe el nombre de quien entró: solo sus grupos y su rol (`GET /v1/grupos`). Si una pantalla lo necesita (un saludo, "Tus dispositivos"), queda como pregunta para Jorge: se propondría `GET /v1/usuarios/yo` con `{id, nombre}` en una historia del eje B. Este contrato no la define.
- **`GET /v1/personas-cuidadas/{persona_id}` no existe**, ni editar o borrar una persona. La app usa la lista `GET /v1/grupos/{grupo_id}/personas-cuidadas` y elige por `id`.
- **No hay ruta para consultar las autorizaciones.** La vista de la persona trae solo la de `plan_cuidado` (`consentimiento`). Que falta la de `consumo` se sabe por el 403 con `finalidad: consumo` de `GET …/consumo`.
- **No hay catálogo** (`/v1/catalogo/…`, arquitectura 9.4). En el sprint 3 la app anota insumos con `nombre_libre`.
- **No hay invitaciones ni cambio de roles** (MATU-42 y MATU-53, sprint 4), ni salir de un grupo.
- **No hay reposiciones** ("Ya lo compré", MATU-51), **ni lista de reposición ni exportarla** (sprint 4).
- **No hay `/v1/consumo/{id}` ni `/v1/alertas`** sin la persona, como dice la arquitectura 9.3: todo cuelga de `/v1/personas-cuidadas/{persona_id}/consumo…` (decisión 54).
- **No hay preferencias de aviso** (`preferencia_notificacion`), ni cambiar o recuperar la contraseña, ni "cerrar todas las sesiones" (se sacan los dispositivos uno por uno).
- **No hay exportación de la ficha** (`GET …/plan/exportar`, RF-09).

## Decisiones tomadas en este contrato

Jorge aprobó la parte 1 (ficha) y la parte 2 (acceso de relevo) el 27-10, después de la fusión del PR #15. Los archivos siguen en `propuestos/` porque todavía no se implementan.

1. **La ficha cuelga de `/v1/personas-cuidadas/{persona_id}/plan/ficha`.** El backlog fija las rutas del relevo bajo `/v1/personas-cuidadas/{id}/plan/…` y la arquitectura 9.2 ya usa `/plan/ficha`: la ficha va con el mismo prefijo. No lleva `plan_id` porque el plan es único por persona. No se anida en `/v1/grupos/{grupo_id}/…` (como el alta de MATU-07) porque el grupo viaja en `X-Grupo-Id` (arquitectura 9.1).
2. **Un PUT por campo** (`/plan/ficha/{campo}`), no uno para los tres. El `ETag`, el 412 y el 428 son por campo (MATU-13): si dos personas editan campos distintos, ninguna pisa a la otra ni recibe un 412.
3. **`X-Grupo-Id` es obligatoria** en toda ruta de la familia, también en `DELETE /v1/accesos-relevo/{id}`. Es la única forma de fijar `app.grupo_id` con `sesion_de_grupo` (MATU-02). Sin ella, o sin membresía, 404. En el contrato se declara `required: false`, igual que en el código (`Header(alias="X-Grupo-Id")` con valor por omisión `None`): si fuera `required: true`, FastAPI respondería 422 al faltar y openapi-diff marcaría la diferencia al implementar.
4. **Un rol que no alcanza recibe 404, también para escribir**, igual que en MATU-07 (el pagador y el observador reciben 404 al dar de alta). Así 403 tiene una sola causa en la capa 1, el consentimiento, y la pantalla sabe qué mostrar.
5. **Toda escritura de un campo es condicional.** Sin `If-Match` ni `If-None-Match`, 428 (también en un campo nuevo). `If-Match: *` responde 428, porque no protege de pisar a otro. `If-Match` sobre un campo nunca escrito, 412 con `actual.etag: null`. Primera escritura 201, actualización 200.
6. **`etag: null` significa "nunca escrito".** Un campo vaciado con `texto: ""` conserva su `etag`. Así el cliente sabe cuál de las dos cabeceras mandar sin adivinar.
   **`If-None-Match: *` con `texto` vacío responde 422** (`errores[].tipo = vacio_sin_crear`), no 201 con `texto: null`. Razones: un 201 dejaría el campo en el estado "vaciado" (`texto: null` con `etag`), que para la persona es igual a "nunca escrito" pero obliga al cliente a cambiar a `If-Match`; además crearía el plan y la clave de la persona, gastaría una versión y registraría un `plan.editar` sin contenido. Se decide solo con la cabecera y el cuerpo, sin leer la base (paso 6 del orden), así que es determinista y no revela si otra persona ya creó el campo. La pantalla no debería enviarlo: "Guardar" con el campo vacío y nunca escrito no hace nada.
7. **El `ETag` es `"v<version>"`** (de `plan_seccion.version`), fuerte y opaco para el cliente.
8. **El 412 lleva el contenido actual** en `actual`, más `campo`, como miembros de extensión del problema. Esa lectura queda auditada como `plan.leer`.
9. **El canje responde 204, no 200.** La sesión va en la cookie y la ficha se lee siempre con `GET /v1/relevo/ficha`, que es lo que se audita como apertura (`relevo.abrir`) y suma `usos`. Un solo camino de lectura.
10. **PIN incorrecto: 401, no 422.** El PIN es una credencial: está bien formado y no coincide, como la contraseña en `POST /v1/sesiones` (401 `credenciales-invalidas`). Así 422 queda para "el PIN no son 4 dígitos", que no cuenta como intento, y la página distingue los dos casos. El cuerpo solo trae `intentos_restantes`. Igual que `/v1/sesiones`, el 401 del canje no lleva `WWW-Authenticate`: no hay un esquema HTTP estándar para un PIN, y se acepta esa desviación de RFC 9110.
11. **El 5.º PIN incorrecto responde 423** (no 401 con 0 intentos), y un acceso bloqueado responde 423 aunque después llegue el PIN correcto. Un PIN correcto antes del bloqueo vuelve el contador a 0: solo puede hacerlo quien sabe el PIN.
12. **Tres 410 distintos** (`vencido`, `revocado`, `no-disponible`), porque MATU-23 pide un texto por estado. Un token desconocido o cortado es `no-disponible`, también cuando `indice_token` ya se purgó tras vencer. Ninguno cuenta como intento. Ver la decisión 22: revocar no borra `indice_token`, así que un enlace revocado responde `revocado`, nunca `no-disponible`.
13. **`GET /v1/relevo/ficha` responde 423 si el acceso se bloqueó después del canje.** Que alguien pruebe 5 PIN con el enlace indica que el enlace se filtró: se corta también la sesión abierta. Requiere revisar `pin_intentos_fallidos` en la aplicación, porque la política `acceso_relevo_propio` mira solo `revocado_en` y `expira_en`.
14. **La cookie se llama `__Secure-matu-relevo`** y dura lo que ocurra primero: 12 horas o el vencimiento del acceso. 12 horas cubren un turno de noche; después se vuelve a pedir el PIN. Las respuestas 410 y 423 de la ficha la borran. El 401 `sin-sesion-relevo` queda solo para "sin cookie" o cookie que no corresponde a una sesión viva (alterada o vencida por su TTL).
15. **La vigencia se pide como `expira_en`** (opcional, 24 horas por defecto), no como duración: la pantalla ofrece "hasta el domingo" y "por N días", y los dos se traducen a una fecha. El servidor valida el máximo de 30 días con su reloj.
16. **`nombre_relevo` y `telefono_relevo` son obligatorios** al crear, aunque MATU-18 no los nombra: `acceso_relevo.otorgado_a_nombre` y `otorgado_a_telefono` son `NOT NULL` en el esquema, la arquitectura 9.2 los pide en el cuerpo y la política de privacidad v0.9 informa que se guardan. El teléfono solo sale en la lista de accesos, para `admin` y `cuidador` (decisión 31), y su finalidad la fija la decisión 24. **`motivo` es obligatorio**, por la misma razón (`NOT NULL`), y es un **enumerado** (`salgo_unas_horas`, `fin_de_semana_fuera`, `turno_de_noche`, `otro`) **sin texto libre**: queda en la auditoría 3 años, y un texto libre de 120 caracteres podría guardar un dato de salud que no se puede borrar (revisión del analista normativo). Cabe en la columna `text` sin migración.
17. **`campos`, no `secciones`.** La interfaz y el backlog hablan de campos, y la ficha solo admite tres (`rutina`, `manejo_situaciones`, `red_apoyo`), aunque `plan_seccion` acepte ocho tipos.
18. **Compartir exige consentimiento vigente; revocar y listar no.** Revocar siempre tiene que ser posible.
19. **`/plan/aperturas` lista solo lo que hicieron los relevos** (presentación, apertura, PIN incorrecto y bloqueo), sin IP. `presentacion` se agregó antes de implementar (decisión 30), para que no sea un cambio incompatible después. Las lecturas de los miembros se auditan, pero mostrarlas es otra decisión (RF-08, pantalla del sprint 3). Si después se agregan, `tipo` gana valores nuevos, y para un cliente estricto eso es un cambio incompatible: conviene decidirlo antes de implementar.
20. **El `mensaje` de los 422 es hoy el texto de Pydantic, en inglés** (`app/core/errores.py` copia `msg`). Los ejemplos lo muestran así. La interfaz se guía por `campo` y `tipo` y muestra el texto de `docs/lenguaje.md`.
21. **No entran en este contrato:** `en_nombre_de` del llenado asistido (RF-42), `GET /plan/exportar` (RF-09), el envío del PIN por SMS (*Debería*) y cerrar la sesión del relevo desde la página.
22. **Revocar no borra `indice_token` ni las sesiones de relevo** (corrección de QA, manda el backlog). MATU-20 exige que "la siguiente petición del relevo responde 410, aunque tenga una cookie válida". Si revocar borrara la sesión, esa petición respondería 401 `sin-sesion-relevo`, y si borrara `indice_token`, el canje respondería `relevo-no-disponible`: el 410 `relevo-revocado` nunca ocurriría. Por eso `DELETE /v1/accesos-relevo/{id}` solo fija `revocado_en`, en `acceso_relevo` y en `indice_token` (decisión 23). La cookie y el token siguen identificando el acceso, y la API verifica su estado en **cada** petición del relevo (canje y `GET /v1/relevo/ficha`). Revocado → 410 `relevo-revocado`, y vencido → 410 `relevo-vencido`. Las respuestas 410 y 423 descartan la sesión en ese momento.
23. **`indice_token` guarda también `revocado_en`** (MATU-19, opción (a), decisión de Jorge del 27-10). Una migración de Alembic reversible agrega `revocado_en timestamptz NULL` a `indice_token`. `DELETE /v1/accesos-relevo/{id}` la fija en la misma transacción que `acceso_relevo.revocado_en`, y una prueba verifica que las dos columnas coinciden. Así el canje y la sesión de relevo deciden con una sola lectura de `indice_token`, que no tiene RLS ni dato sensible: `revocado_en` da `revocado` y `expira_en` da `vencido`. La migración la hace MATU-19 o MATU-20, no este contrato.
    - **Descartada, opción (b):** leer `acceso_relevo.revocado_en` y `expira_en` con `app.rol = 'sistema'` cuando la lectura como `relevo` devuelve cero filas. Evitaba la migración y dejaba una sola fuente de verdad, pero abría un camino con el rol `sistema` en una ruta pública.
24. **`telefono_relevo` sigue obligatorio y tiene finalidad declarada** (decisión de Jorge del 27-10). Sirve para que quien comparte le envíe el enlace al relevo, por WhatsApp o SMS desde su propio teléfono, y para que la familia pueda contactarlo. La API no envía nada (decisión 21). Devuelve el teléfono solo en la lista de accesos, a `admin` y `cuidador` (decisión 31). Como visión, fuera de MATU-09: MATU se piensa como app móvil, y ahí el teléfono será esencial para identificar a la persona, enviar la ficha y la lista, y contactar al repartidor.
25. **El teléfono del relevo se borra 30 días después de que el acceso vence o se revoca. El resto del registro se conserva 3 años** (decisión de Jorge del 27-10). El nombre del relevo, el motivo y las fechas del acceso se conservan igual que la auditoría, porque identifican a quién se entregó la ficha. Ya no requiere consulta legal. Para borrar el teléfono hace falta quitar el `NOT NULL` de `acceso_relevo.otorgado_a_telefono` con una migración, y una tarea que lo borre al cumplirse el plazo. Las hace la tarjeta de Trello "S3 · Borrar el teléfono del relevo y anonimizar el nombre de pila", no este contrato.
26. **Si se borra a la persona cuidada, su nombre de pila copiado en `acceso_relevo` se anonimiza** (decisión de Jorge del 27-10). Lo hace la historia de borrado.
27. **La clave del contador por IP en Redis es una huella de la IP, nunca la IP en claro** (condición de MATU-25, decisión de Jorge del 27-10). La huella es un HMAC con un secreto que vive en `.env` vía `pydantic-settings`, y la clave vence a la hora. Sin esto, la política de privacidad, que dice que la IP no se guarda, no sería cierta.
28. **El relevo ve quién compartió y de quién es la ficha antes del PIN** (decisión de Jorge del 27-10). La pantalla del PIN dice "Carmen te compartió la ficha de María", como la demo. Razón: quien envía lo hace a su nombre y de forma voluntaria a través de la app, y recibir algo que pide un PIN sin saber qué es no da confianza. Riesgo aceptado por Jorge: quien reciba un enlace reenviado ve los dos nombres de pila sin el PIN.
    - **`POST /v1/relevo/presentacion`**, ruta nueva y pública. Recibe el token en el cuerpo, nunca en la URL, porque viaja en el fragmento. Responde 200 con `nombre_pila_comparte` y `nombre_pila`, y nada más. Evalúa el límite por IP, el token y el estado igual que el canje: los mismos 410 (`vencido`, `revocado`, `no-disponible`) y el mismo 423. No cuenta como intento de PIN, no crea sesión, no suma `usos` y no registra `relevo.abrir`. Tiene su propio contador por IP (decisión 29) y registra `relevo.presentar` (decisión 30). Lleva `Cache-Control: no-store`.
    - **`GET /v1/relevo/ficha` también devuelve `nombre_pila_comparte`**, para decir "Solo Carmen puede cambiar esta ficha".
    - **`acceso_relevo` guarda el nombre de pila de quien comparte** al crear el acceso, igual que `nombre_pila_persona`, para que el relevo nunca lea `usuario`. La migración la hace MATU-18, no este contrato.
29. **Contadores por IP separados** (decisión de Jorge del 27-10). `POST /v1/relevo/presentacion` admite 30 por hora por IP y `POST /v1/relevo/canje` sigue en 10. Los dos usan la huella HMAC de la decisión 27, con TTL de 1 hora y claves distintas. Razón: en Chile muchos celulares comparten IP pública (CGNAT), y la presentación no permite adivinar enlaces, porque el token tiene 256 bits, ni muestra más que dos nombres de pila.
30. **La presentación se audita** (decisión de Jorge del 27-10). Cada presentación con 200 queda en `auditoria` como `relevo.presentar`, sin IP. `/plan/aperturas` la muestra con `tipo: presentacion`, junto a `apertura`, `pin_incorrecto` y `bloqueo`. Sirve para detectar un enlace reenviado: se abrió la página y nunca se escribió el PIN. Se agrega ahora, antes de implementar, para no cambiar `tipo` después (decisión 19).
31. **La lista de accesos devuelve `telefono_relevo` a `admin` y `cuidador`** (decisión de Jorge del 27-10). Así la familia puede contactar al relevo (decisión 24). Para el `pagador` con `puede_ver_plan` la propiedad no aparece. Es `null` cuando ya se borró, a los 30 días (decisión 25). La respuesta ya lleva `Cache-Control: no-store`.

## Decisiones de Jorge del 28-10

Las tomó Jorge al implementar MATU-12, con las condiciones del analista normativo. Siguen la numeración de las decisiones del contrato.

32. **D-A · La KEK en una variable de entorno, solo en el semestre y solo con datos sintéticos** (desvío explícito del ADR-016). El adaptador `CustodiaKekEntorno` (`backend/app/modules/care_plan/infrastructure/custodia_kek_entorno.py`) implementa el puerto `CustodiaClaves` con la KEK de la configuración. Condiciones del analista normativo:
    - (a) Solo se construye con `ENTORNO` en {`local`, `pruebas`}, una lista permitida: con `produccion` o cualquier otro valor, la configuración no carga y la API no arranca.
    - (b) Se enciende explícitamente con `CUSTODIA_KEK=entorno_sintetico`. Encendida sin `KEK_ENTORNO`, la configuración no carga y la API no arranca (observación P3 de QA). Sin `CUSTODIA_KEK`, las rutas de la ficha responden **503** `/errores/servicio-no-disponible` y fallan cerradas: nunca se genera una KEK al arrancar ni se usa el doble de pruebas.
    - (c) `KEK_ENTORNO` son 32 bytes aleatorios en base64, como `SecretStr`, con el largo validado y distinta de `JWT_CLAVE` y `PEPPER_EMAIL`. No sale del adaptador ni aparece en su `repr`, en los errores ni en los logs. Nunca va en el repositorio ni en `docker-compose.yml`, y `.env.example` solo tiene el marcador vacío.
    - (d) `KEK_VERSION` es fija (1 por omisión) y viene de la configuración. Si la clave cambia sin cambiar la versión, el resultado es un error genérico (503), nunca una DEK nueva.
    - (e) Al arrancar registra un WARNING fijo, sin la clave: "KEK en variable de entorno: solo datos sintéticos". El docstring del adaptador declara la limitación de la arquitectura 11.4: la KEK vive en el mismo servidor que las DEK envueltas.
    - (f) Lo prueban `backend/tests/modules/care_plan/test_custodia_kek_entorno.py` (no arranca con `produccion` ni con un entorno desconocido; la KEK no aparece en el `repr`, los errores ni los logs) y `test_ficha_api.py` (503 sin custodia; otra KEK con la misma versión no crea una DEK nueva).
    - **Envoltura: AES Key Wrap (RFC 3394, NIST SP 800-38F), no AES-GCM.** Es el algoritmo hecho para envolver claves: determinista y sin nonce (no hay nonce que generar ni riesgo de repetirlo con la misma KEK) y con su propio control de integridad, así que una DEK envuelta alterada o desenvuelta con otra KEK falla en vez de entregar bytes erróneos. Los datos asociados de GCM no aportan aquí: el puerto `envolver(dek)` no recibe contexto y la versión ya elige la KEK. La DEK envuelta ocupa 40 bytes.
    - El adaptador de producción lo decide el ADR-019. Con este, MATU no recibe datos reales.
33. **D-B · Revisión anual vencida = sin autorización vigente.** Si el consentimiento para `plan_cuidado` lo dio un cuidador de hecho y `revision_vence_en` ya pasó (con el puerto `Reloj`; vencida desde el instante exacto), leer o escribir la ficha responde **403** con un `type` propio, `/errores/revision-vencida`, distinto de `/errores/sin-consentimiento`. Así la pantalla no muestra un error sino un aviso que explica cómo renovar la autorización o hacerse cuidador formal, con un enlace externo. El texto del aviso y el enlace oficial están en `docs/lenguaje.md`, sección 6.4b (repositorio MATU, PR #15); la API no los devuelve. Lo prueba `test_revision_vencida_403`.

34. **Informar y declarar, base de licitud de los datos del relevo** (decisión de Jorge del 28-10). Al crear el acceso, quien comparte declara que le avisó al relevo: `relevo_informado: true` es obligatorio en el cuerpo del POST. Si falta o es `false`, 422 con `errores[].campo = relevo_informado`, sin crear nada. La fecha queda en `acceso_relevo.relevo_informado_en timestamptz NOT NULL` (migración 0004), con el puerto `Reloj`. La base es el interés legítimo de la familia, informado; el relevo además ve el aviso "Tus datos en MATU" (`docs/lenguaje.md`, 7.5) antes del PIN. Texto de la casilla, que la API no devuelve: "Le avisé a {nombre_relevo} que MATU guarda su nombre y su teléfono para enviarle la ficha".
35. **Minimización en la lista de accesos** (decisión de Jorge del 28-10). `GET …/plan/accesos-relevo` devuelve de quien compartió solo el nombre de pila (`acceso_relevo.nombre_pila_comparte`) en `otorgado_por.nombre`, nunca `usuario.nombre` completo.
36. **Quién lee la auditoría** (decisión de Jorge del 28-10). El administrador del grupo lee todas las filas de `auditoria` de su grupo. Cada miembro lee solo las suyas (`actor_ref = app.usuario_id`). El observador lee solo las suyas, y operación y los demás roles no tienen lectura amplia. Lo aplica la migración 0005, que reemplaza la política de SELECT `auditoria_familia` y quita `auditoria_operacion`, sin tocar las de INSERT. Lo prueban `test_lectura_de_auditoria_por_rol`, `test_operacion_no_lee_la_auditoria` y `test_0005_...`.

## Decisiones de Martín del 31-10 (MATU-32), pendientes de aprobación de Jorge

Contrato `propuestos/app-familia.openapi.yaml`. Siguen la numeración de las decisiones del contrato. Las 37 a 40 las tomó Martín el 31-10; las 41 a 54 son de diseño del contrato. **Todas están pendientes de aprobación de Jorge**, que usa el contrato desde el lunes 02-11 para MATU-36, MATU-37 y MATU-39.

37. **Autorización propia para el consumo** (opción (a) del analista normativo). El cálculo de insumos exige un consentimiento con `finalidad = 'consumo'`, separado del de `plan_cuidado`, como ya anuncia la política v0.9 ("Cada uso se autoriza por separado"). Se da con `POST /v1/personas-cuidadas/{persona_id}/consentimientos` (`finalidad: "consumo"`), una ruta de recurso que sirve también para las otras finalidades de la tabla cuando se prioricen. Reutiliza **exactamente** el alta de MATU-07: la misma `calidad_otorgante`, las reglas de `validar_otorgamiento` para `aviso` y `referencia_documento`, el mismo aviso del cuidador de hecho, la evidencia mínima de la migración 0006 con una declaración nueva (`declaracion_consumo_<calidad>`) y la revisión anual de 12 meses. La dan `admin` y `cuidador`. Sin ella, toda ruta de consumo responde 403 con `finalidad: consumo`.
    - **Exige la política 0.10**, con la declaración nueva que el analista dejó como borrador. MATU-36 no habilita la ruta mientras `POLITICA_VERSION` sea 0.9.
    - **Revocar no está en este contrato** (ver "Contradicciones (MATU-32)"): queda con MATU-44.
38. **`nombre_libre` solo con RLS, sin cifrar, de 1 a 60 caracteres.** Una línea, sin caracteres de control, con la descripción "Nombre del producto tal como se vende. No es para remedios ni para explicar para qué se usa". Nunca en logs, errores, auditoría ni eventos, y el 422 no repite el valor.
    - **Consecuencia:** la política v0.9, sección 8, dice que la ficha y el consumo de insumos se dejan "ilegibles de inmediato destruyendo su clave". El consumo no tiene clave propia: para el consumo, la 0.10 debe decir que **se borra**, no que se deja ilegible. Lo redacta el analista normativo en el repositorio MATU.
39. **El refresh va en una cookie `HttpOnly`, con un máximo de 30 días desde el inicio de sesión y sin ventana deslizante.** `__Secure-matu-refresh`, `Secure`, `SameSite=Strict`, `Path=/v1/sesiones`, 256 bits en base64url; la base guarda su SHA-256. Todos los tokens de una familia heredan su `expira_en`: renovar no alarga la sesión, y a los 30 días hay que volver a entrar. Cumple el `CHECK sesion_refresh_vigencia` sin migración.
40. **El access token vive solo en memoria** en el cliente: ni `localStorage`, ni `sessionStorage`, ni IndexedDB, ni la URL. Al recargar se pide otro con la cookie. Al cerrar sesión o sacar un dispositivo, el access token ya emitido sigue valiendo hasta 15 minutos (arquitectura 11.6), y el contrato lo declara.
41. **La edición de un perfil es `PATCH` con `If-Match` obligatorio**, coherente con MATU-13. `PATCH` porque la pantalla más común cambia un solo dato ("quedan 20") y no debería reenviar la tasa ni el aviso. `If-Match` porque dos personas de la familia pueden anotar el stock casi al mismo tiempo y la segunda pisaría a la primera sin saberlo: igual que en la ficha implementada, `If-Match` es un `string` sin patrón: sin él, vacío o con `*`, 428; cualquier otro valor que no coincida con la versión actual (uno viejo, o uno que no es un `ETag` de MATU), 412 con el perfil actual en `actual`, y nunca 422 (corrección H1 de la QA, 31-10). El `ETag` es `"v<version>"` (patrón `^"v[1-9][0-9]*"$`, el de la ficha), y viene también en el cuerpo (`etag`) para que la lista sirva para editar sin otro `GET`. Hace falta la columna `perfil_consumo.version integer NOT NULL DEFAULT 1`: la agrega una migración reversible de MATU-36. `producto_id` y `unidad` no se editan (otro producto u otra unidad es otro perfil).
42. **`stock_medido_en` lo fija el servidor con el `Reloj`**: la fecha de hoy en America/Santiago, al crear y cada vez que el `PATCH` trae `stock_unidades` (aunque sea el mismo número: contar de nuevo vuelve a anclar el cálculo). El cliente no lo envía (422 por campo extra). Razones: la pantalla pregunta "¿cuántos quedan?" sin un selector de fecha, se evita validar fechas futuras y la zona horaria del teléfono, y una cuenta antigua se corrige anotando de nuevo.
43. **Topes:** `tasa_unidades` de 1 a 10.000, `tasa_dias` de 1 a 90, `stock_unidades` de 0 a 100.000, `dias_aviso` de 0 a 60 (7 por omisión) y una cobertura de **3.650 días como máximo** (`piso(stock_unidades * tasa_dias / tasa_unidades)`; si no, 422 `cobertura_maxima`). 10.000 alcanza para ml y g; el tope de cobertura evita fechas absurdas y que `stock_medido_en + días` se salga del rango de fechas de Python (año 9999).
44. **`type` nuevos:**
    - `/errores/sesion-expirada` (401 de la renovación), en vez de reutilizar `token-invalido`: `token-invalido` en una ruta cualquiera significa "renueva", y `sesion-expirada` en la renovación significa "vuelve a entrar". Con uno solo la app podría quedar renovando en un ciclo.
    - `/errores/autorizacion-vigente`, `/errores/perfil-duplicado`, `/errores/perfil-inactivo` y `/errores/alerta-cerrada` (409), uno por conflicto, para que la pantalla elija el texto por `type`.
    - El 403 del consumo reutiliza `sin-consentimiento` y `revision-vencida` con el miembro de extensión `finalidad: consumo`. El 403 de la ficha no lo trae hoy; agregarlo (`plan_cuidado`) sería un cambio a una ruta implementada y no se propone aquí.
45. **Sin `X-MATU-Cliente: web`, 422, no 401.** Se evalúa antes de mirar la cookie, así que no revela nada de ella, y no rota, no revoca ni borra la cookie. Es un error de programación del cliente, no un estado de la sesión: con 401 la app mandaría a la persona a la entrada y escondería el error. Además, así lo hace FastAPI con una cabecera obligatoria (`Header` con `Literal["web"]`), y el contrato coincide con lo que exportará `openapi.json`. Vale para renovar y cerrar.
46. **Desactivar es `POST …/consumo/{perfil_id}/desactivar`**, idempotente y sin `If-Match` (archivar no pisa lo que escribió otro). Nunca borra. En la misma transacción pasa a `descartada` las alertas abiertas del perfil. No hay reactivar: se crea otro perfil.
47. **Un dispositivo es un navegador con sesión.** Iniciar sesión crea un dispositivo `web` con un `nombre` grueso ("Chrome en Android") que arma el servidor sin guardar el agente de usuario, o reutiliza el de la cookie si es del mismo usuario y no está revocado (revocando la familia anterior: una sesión viva por dispositivo). **Cerrar sesión revoca también el dispositivo y borra su `push_token`**: un navegador sin sesión no recibe avisos, y "Tus dispositivos" muestra solo los que tienen una sesión abierta. Sin una cookie propia de dispositivo, que sería un identificador más del navegador.
48. **El access token lleva el claim `did`** (id del dispositivo): así `GET /v1/dispositivos` marca el `actual` y `PUT /v1/dispositivos/actual/push` sabe dónde escribir, sin que la cookie del refresh (que solo viaja a `/v1/sesiones`) salga de su ruta. El access token vence a los 15 minutos **o** cuando vence la familia, lo que ocurra primero. Cambia `tokens_jwt.py` en MATU-38.
49. **Demora progresiva de la entrada.** Dos contadores de fallos en Redis, por huella de la IP y por huella del email normalizado (HMAC-SHA-256 con un secreto nuevo de `.env`, por ejemplo `PEPPER_LIMITES`, que MATU-25 puede compartir con otro prefijo), que vencen a la hora del primer fallo. Sin demora hasta 5 fallos por email y 20 por IP (CGNAT); después 30 s, 1, 2, 4 y 8 minutos, con tope de 15. El mismo 429 exista o no el email, sin leer la base. Nunca bloquea la cuenta. Un 200 borra el contador del email, nunca el de la IP. **Sin Redis, 503**: falla cerrada, como el canje del relevo; quien ya entró sigue con su refresh, que no usa Redis. **Riesgo aceptado, por confirmar:** alguien que conoce un email puede hacer esperar a esa persona hasta 15 minutos por vez, sin bloquearla.
50. **`push_token` es solo un endpoint de Web Push**, `https`, de hasta 1024 caracteres, con el host en una lista cerrada de servicios de push. Sin la lista, un usuario podría hacer que el servidor envíe peticiones a cualquier dirección (incluidas las internas) al avisar. Con solo el endpoint, MATU envía avisos sin contenido (RFC 8030 con VAPID) y el service worker muestra un texto fijo, lo que calza con avisar sin el nombre de la persona ni del producto. Si MATU-41 necesita contenido cifrado, hacen falta las claves `p256dh` y `auth`, y es un cambio a este contrato.
51. **Sin período de gracia para la reutilización.** Dos renovaciones simultáneas con la misma cookie (dos pestañas) revocan la familia. El cliente serializa la renovación entre pestañas (por ejemplo con `navigator.locks`) y nunca la reintenta con la cookie anterior. Si el piloto muestra cierres de sesión inesperados, se evalúa una gracia de pocos segundos (pregunta para Jorge).
52. **Se auditan las escrituras del consumo, no las lecturas.** `consumo.crear`, `consumo.editar`, `consumo.desactivar` y `alerta.descartar` (acciones nuevas en `AccionAuditoria`), más `consentimiento.otorgar`, sin `nombre_libre`, sin cantidades y sin IP. Las lecturas no se auditan: el consumo no está cifrado, se lee en cada pantalla, y "quién la vio" es una vista de la ficha.
53. **Paginación.** La lista de perfiles y la de alertas usan cursor (`cursor`, `limite`), como los accesos de relevo. "Qué se acaba pronto" y los dispositivos no: están acotados. "Qué se acaba pronto" sale de `perfil_consumo` (fecha estimada dentro de `dias_aviso`, incluidos los ya pasados), no de `alerta_quiebre`: se ve aunque el trabajo diario no haya corrido y aunque la alerta se haya descartado.
54. **Consumo y alertas cuelgan de la persona** (`/v1/personas-cuidadas/{persona_id}/consumo…`), con `X-Grupo-Id`, igual que la ficha (decisión 1). La arquitectura 9.3 dice `PATCH /v1/consumo/{id}`, `GET /v1/alertas` y `POST /v1/alertas/{id}/descartar` (ver "Contradicciones (MATU-32)"). Al implementar, las rutas fijas `por-acabarse` y `alertas` se registran antes que `{perfil_id}`.

## Notas de implementación de MATU-12

Decisiones técnicas del backend que no cambian el contrato. Si alguna no corresponde, se corrige antes de fusionar.

- **Orden de los controles.** El rol, la persona, el campo, el consentimiento (y la revisión) y la custodia son dependencias de FastAPI: corren antes de validar el cuerpo y antes de leer el plan. Sin consentimiento no se descifra, no se valida el texto y no se crea ni el plan ni la clave de datos (lo prueba `test_sin_consentimiento_403`). El 503 de custodia va después del 403 y antes del 422.
- **Hasta MATU-13, las escrituras sin cabeceras se aceptan.** 201 si crean el campo, 200 si lo actualizan. Dos escrituras del mismo campo se ordenan por el bloqueo de la fila (`SELECT … FOR UPDATE`) y gana la última; dos primeras escrituras concurrentes dejan un solo plan y una sola sección (`ON CONFLICT DO NOTHING`). Un `texto` vacío sobre un campo nunca escrito responde 422 `vacio_sin_crear` leyendo la base, porque todavía no hay `If-None-Match` que permita decidirlo sin leerla (decisión 6).
- **Un campo vaciado se guarda cifrado con largo 0.** AES-GCM conserva el largo, así que la completitud se calcula con `octet_length(contenido_cifrado) > 0`, sin descifrar los otros campos. El largo de un campo ya se deduce del texto cifrado; esto no revela nada nuevo.
- **Clave de datos destruida (borrado criptográfico): 404**, como una persona eliminada. **Sección ilegible** (alterada o movida de plan o de campo): 500 genérico. **La custodia no envuelve o no desenvuelve:** 503 genérico. Ninguno lleva el texto, y el log solo registra el tipo de error.
- **Auditoría (MATU-14).** Los casos de uso llaman al puerto `AuditoriaFicha` (`registrar_lectura` y `registrar_edicion`) dentro de la transacción, con un `EventoFicha` de solo identificadores. MATU-14 lo implementa con `AuditoriaFichaRegistro` sobre el puerto compartido `RegistroAuditoria`: `plan.leer` sobre `plan_cuidado` y `plan.editar` sobre `plan_seccion`, actor `usuario`, con el `request_id`, sin texto, ETag, versión ni IP. Si registrar falla, la transacción se deshace y no se devuelve el texto. `relevo.compartir` (MATU-18) pasa por el mismo puerto.
- **Las preguntas guía y los ejemplos de cada campo** (`docs/lenguaje.md`, 5.1 a 5.3) no van en la respuesta: el contrato los deja en la interfaz.
- **La decisión 33 vale también para el relevo** (decisión de Jorge del 28-10). Mientras no se renueve la autorización, crear un acceso (`POST …/plan/accesos-relevo`, MATU-18) responde el mismo 403 `revision-vencida`, y un relevo con un enlace anterior tampoco abre la ficha (canje y `GET /v1/relevo/ficha`, MATU-19). Cortar un acceso y ver la lista siguen permitidos (decisión 18). `relevo.openapi.yaml` se actualiza en MATU-18 y MATU-19.

## Notas de implementación de MATU-18

Decisiones técnicas del backend que no cambian el contrato. Si alguna no corresponde, se corrige antes de fusionar.

- **Huellas.** `token_hash` es el SHA-256 de los 32 bytes crudos del token (no del texto base64url), igual en `acceso_relevo` y en `indice_token`. `pin_hash` es HMAC-SHA-256(`PEPPER_PIN`, `"<acceso_id>:<pin>"`) en hexadecimal: ligado al acceso, dos accesos con el mismo PIN tienen huellas distintas. MATU-19 compara con `hmac.compare_digest`.
- **`PEPPER_PIN`** es un secreto nuevo en `.env` (`SecretStr`, al menos 32 caracteres, distinto de `PEPPER_EMAIL`, `JWT_CLAVE` y `KEK_ENTORNO`). Sin él, crear un acceso responde 503 `/errores/servicio-no-disponible`, después del 403 y antes del 422.
- **`ORIGEN_WEB`** (`https://…`, sin barra final) arma el enlace `<origen>/r#<token>` del 201. No es un secreto.
- **Migración 0004:** `acceso_relevo.nombre_pila_comparte text NOT NULL` con `CHECK` de texto no vacío (decisión 28) y `acceso_relevo.relevo_informado_en timestamptz NOT NULL` (decisión 34). Es la primera palabra de `usuario.nombre` al crear el acceso. `indice_token.revocado_en` (decisión 23) queda para MATU-19 o MATU-20.
- **Auditoría `relevo.compartir`:** una fila por acceso con `actor_tipo = 'usuario'`, `entidad = 'acceso_relevo'` y el `motivo` enumerado. Sin nombre ni teléfono del relevo, sin IP, sin token ni PIN.
- **La lista** se ordena por `creado_en` y `id` descendentes; el cursor es base64url de esos dos valores. El `estado` se calcula en SQL con el reloj de la API, también para el filtro.

## Contradicciones con la arquitectura v1.1, sección 9.2

Este contrato sigue el **backlog v1.3**, que es más nuevo. Jorge las corrige en la arquitectura v1.2:

| Arquitectura 9.2 | Este contrato | Fuente |
|---|---|---|
| `GET /v1/relevo/{token}`: token en la URL, vista pública sin sesión | `/r#<token>` en el fragmento, `POST /v1/relevo/canje` con token y PIN en el cuerpo, cookie de sesión y `GET /v1/relevo/ficha` | Backlog v1.3, MATU-09 y MATU-19; arquitectura 11.6 ("se canjea por una cookie de sesión efímera") |
| `GET /v1/personas-cuidadas/{id}/plan` | `GET …/plan/ficha` | Decisión 1 |
| `PUT …/plan/ficha` escribe los tres campos en una llamada | `PUT …/plan/ficha/{campo}`, uno por campo | MATU-13 (ETag por campo), decisión 2 |
| `PUT …/plan/secciones/{tipo}` con `If-Match: "<version>"` | No se expone: el semestre usa solo la ficha (ADR-023) | ADR-023 |
| Cuerpo del acceso con `secciones` | `campos` | Decisión 17 |
| 11.6: el PIN se envía "al teléfono registrado" | La API no envía el PIN: lo entrega una vez en el 201 y la cuidadora se lo dicta al relevo. El envío por SMS es *Debería* y no está en este contrato (decisión 21) | Backlog v1.3, MATU-18; revisión del analista normativo. Se corrige en la v1.2, o se agrega el SMS cuando se priorice |

## Notas para implementar

- **`pin_hash` es un HMAC-SHA-256 con *pepper*, no un hash simple** (revisión del analista normativo). Un PIN de 4 dígitos tiene 10.000 valores: con un hash simple (ni siquiera con sal) quien lea la tabla lo recupera por fuerza bruta en milisegundos. El *pepper* es un secreto que vive fuera de la base, en `.env` vía `pydantic-settings` (CLAUDE.md, política 5), así que una copia de la base sola no basta. La comparación es en tiempo constante (`hmac.compare_digest`). El límite de 5 intentos protege el canje en línea; el HMAC protege la base fuera de línea. El token no lo necesita: 256 bits aleatorios no se recuperan por fuerza bruta, y basta su SHA-256.
- **Revocado frente a vencido:** ver la decisión 23. Hoy `indice_token` (`backend/db/01_esquema.sql`) guarda `expira_en` pero no la revocación, y la política `acceso_relevo_propio` (`backend/db/02_rls.sql`) filtra `revocado_en IS NULL AND expira_en > now()`: con `app.rol = 'relevo'`, un acceso revocado y uno vencido devuelven cero filas. Por eso hace falta la columna nueva.

## Decisiones de Jorge del 27-10

Resuelven los puntos de la revisión del analista normativo que el contrato no resolvía solo.

1. **Teléfono del relevo:** sigue obligatorio, con finalidad declarada. Es la decisión 24.
2. **Conservación:** el teléfono del relevo se borra 30 días después de que el acceso vence o se revoca. El nombre, el motivo y las fechas del acceso se conservan 3 años como la auditoría. Es la decisión 25. Deja de requerir consulta legal. Si se borra a la persona cuidada, su nombre de pila en el acceso se anonimiza (decisión 26).
3. **Retiro de la autorización:** la política de privacidad v0.9, sección 10, mantiene su promesa de cortar los accesos de relevo al retirar la autorización. La historia del sprint 3 que lo hace queda como requisito para operar con datos reales (ver "Riesgo abierto").
4. **IP:** el analista normativo ajusta la política en el repositorio MATU para decir que la IP se usa solo para limitar intentos, por una hora, sin guardarla. MATU-25 queda como está, con una condición: la clave del contador es una huella de la IP (decisión 27).
5. **Aviso al relevo:** Jorge aprobó el texto final. Va en la pantalla del PIN, antes del canje, y vive en `docs/lenguaje.md`, sección 7.5, del repositorio MATU. Este contrato no lo repite. Dice qué se guarda del relevo y para qué, que el teléfono se borra a los 30 días, que cada apertura y cada PIN incorrecto se registran por 3 años, quiénes son los responsables y cómo pedir ver, corregir o borrar sus datos. El correo de contacto sigue pendiente.
6. **Registro de tratamientos:** las entradas de la ficha de relevo y del acceso de relevo en `docs/legal/registro-tratamientos.md` (repositorio MATU) las redacta el analista normativo y las aprueba Jorge. Este contrato no las edita.
7. **MATU-19, revocado frente a vencido:** opción (a), columna `revocado_en` en `indice_token`. Es la decisión 23. La migración la hace MATU-19 o MATU-20.
8. **Quién compartió:** el relevo ve los dos nombres de pila antes del PIN, con una ruta nueva. Es la decisión 28.
9. **Preguntas del PR #19:** contadores por IP separados (decisión 29), auditoría de la presentación (decisión 30) y teléfono en la lista de accesos para `admin` y `cuidador` (decisión 31).

## Diferencias con la demo (`origin/demo-web-viernes-30`, `Demo/src/`)

La demo es simulada y no se modificó. Cuando se conecte a la API, cambia esto:

| Demo | Contrato | Qué hacer |
|---|---|---|
| Campos `su_dia`, `si_se_altera`, `a_quien_llamar` (`demo/tipos.ts`) | `rutina`, `manejo_situaciones`, `red_apoyo` | Mapear en el cliente; los títulos visibles no cambian |
| `Campo.version` numérico hace de ETag | `etag` opaco (`"v3"`) en el cuerpo y en la cabecera | Guardar y reenviar el texto tal cual |
| La pantalla del PIN dice "Carmen te compartió la ficha de María" antes del canje (`relevo/Relevo.tsx`) | Coincide: `POST /v1/relevo/presentacion` devuelve los dos nombres de pila con solo el token, y la ficha trae `nombre_pila_comparte` (decisión 28) | Leer los nombres de la presentación, no de datos fijos. Agregar el aviso al relevo de `docs/lenguaje.md` 7.5 |
| Un solo estado `no_disponible` para vencido, revocado y bloqueado | 410 con tres `type` y 423 aparte | Un texto por estado (MATU-23) |
| Estados del acceso `activo`, `revocado`, `bloqueado`, y "vencido" calculado | `estado`: `vigente`, `vencido`, `revocado`, `bloqueado` | Usar `estado` de la API |
| Motivo opcional ("Motivo, si quieres"), tres chips que se pueden desmarcar | `motivo` obligatorio, enumerado: los tres chips más `otro`, sin texto libre | Agregar el chip "Otro motivo" sin campo de texto, preseleccionar uno y no permitir dejarlos todos desmarcados |
| Teléfono sin validar, con espacios (`+56 9 5555 0137`) | Obligatorio, celular chileno, con o sin `+56`/`56` y espacios | Validar en la pantalla con el mismo patrón |
| El teléfono tiene la ayuda "Para enviarle el enlace" (`familia/Ficha.tsx`) | La API no envía nada: la cuidadora le envía el enlace desde su propio teléfono y dicta el PIN (decisión 24). Ninguna respuesta devuelve el teléfono | Nada: el texto es correcto con la decisión 24. Se mantiene |
| `Problema` sin `request_id` y con `detail` y `errores` opcionales (`datos/contrato.ts`) | Los seis miembros siempre presentes; `detail` y `request_id` pueden ser `null` | Ajustar el tipo |
| Vigencia "24 h", "fin de semana" o "N días" | `expira_en` | Calcular la fecha en el cliente |

Lo que coincide: tope de 500 caracteres, 5 intentos de PIN, contador que vuelve a 0 con el PIN correcto, vigencia por defecto de 24 horas y máxima de 30 días, enlace `/r#<token>` limpiado con `history.replaceState`, PIN visible una sola vez, y conflicto que muestra las dos versiones.

## Riesgo abierto

Mientras no esté "revocar el consentimiento y cortar los accesos de relevo vigentes" (backlog, sección 8, sprint 3), retirar el consentimiento no corta los accesos ya creados: `GET /v1/relevo/ficha` no puede leer `consentimiento`, porque la sesión de relevo no fija `app.grupo_id`. Se cierra cuando esa historia revoque los accesos al retirar el consentimiento.

**Condición de Jorge (27-10):** esa historia es requisito para operar con datos reales. La política de privacidad v0.9 promete cortar los accesos al retirar la autorización, y MATU no recibe datos reales mientras la historia no esté terminada.

## Notas de implementación de MATU-19

- **Decisión 33 en el relevo: `410 /errores/relevo-pausado`** (decisión de Martín del 28-10, **pendiente de revisión de Jorge**). Si la autorización de la persona del acceso no está vigente (consentimiento para `plan_cuidado` revocado, o cuidador de hecho con `revision_vence_en` igual o anterior al instante del Reloj), presentación, canje y `GET /v1/relevo/ficha` responden 410 `relevo-pausado`, con `title` «Ya no está disponible» y un `detail` neutro. Se evalúa después de los 410 de estado y del 423, y antes del PIN. No cuenta como intento ni crea sesión; en la ficha borra la cookie y descarta la sesión. Si se renueva la autorización, el mismo enlace vuelve a servir. Lo decide la función `relevo_autorizacion_vigente(ahora)` (migración 0007), `SECURITY DEFINER`, que devuelve solo un booleano: el relevo sigue sin leer `consentimiento`. Esto cierra en parte el "Riesgo abierto" de más arriba: retirar la autorización ya corta la lectura del relevo, aunque no revoca los accesos.
- **Migración 0007** (era 0006 hasta el merge del PR #25, que tomó ese número): `indice_token.revocado_en` (decisión 23), la política `acceso_relevo_propio` (FOR ALL) reemplazada por `acceso_relevo_leer` (SELECT) y `acceso_relevo_contar` (UPDATE) más un trigger que limita al relevo a `pin_intentos_fallidos`, `usos` y `ultimo_uso_en`, y la función de la decisión 33.
- **Canje sin `PEPPER_PIN`:** 503 `/errores/servicio-no-disponible` después de los 410/423 y antes de comparar el PIN. Tampoco con Redis caído (503). El contrato lo declara como `RelevoSinServicio` en el canje y en la ficha. La sesión en Redis se crea después del commit del canje: si Redis falla, queda `relevo.canje` sin sesión y se responde 503.
- **Sin entrada en `indice_token`** con una cookie válida (purgado tras vencer), la ficha responde 410 `relevo-vencido`.
- **429 por IP** (MATU-25) y **`/plan/aperturas`** (sprint 3) no están implementados.
- **Un 500** lleva `Cache-Control: no-store` siempre y, bajo `/v1/relevo/`, también `Referrer-Policy: no-referrer` y `X-Robots-Tag: noindex`. Lo pone el manejador de `app/core/errores.py`, porque el 500 lo arma `ServerErrorMiddleware` por fuera del middleware de cabeceras.
- **Privilegios del dueño para `relevo_autorizacion_vigente`.** La función corre como su dueño (`matu_owner`). Con un dueño sin superusuario ni `BYPASSRLS`, como en CI y como manda `00_roles.sql`, las políticas que alcanzan sus lecturas (por ejemplo `plan_familia`, que llama a `app_puede_ver_plan()`) leen `membresia`: el dueño necesita `SELECT` sobre `membresia`. El QA lo comprobó con un rol no superusuario. En la base local de desarrollo `matu_owner` es superusuario y no lo nota: revisar cómo se crearon los roles allí.

## Notas para implementar MATU-36, MATU-37, MATU-38 y MATU-41

- **Migraciones de MATU-38**, reversibles y probadas: el valor `dispositivo` en el `CHECK` de `sesion_refresh.motivo_revocacion`. Las políticas de RLS de `dispositivo` y `sesion_refresh` van en "Pendientes para Jorge (MATU-32)".
- **Migraciones de MATU-36**: `perfil_consumo.version integer NOT NULL DEFAULT 1` (decisión 41). Opcionales, en la misma migración: un `CHECK` de exactamente uno de `producto_id` y `nombre_libre` (hoy el `CHECK perfil_consumo_producto` acepta los dos) y otro de `char_length(nombre_libre) <= 60`.
- **La renovación resuelve el token antes de tener contexto** con `indice_token` (`tipo = 'refresh'`, sin RLS, ya previsto en el esquema), y recién después fija `app.usuario_id` para leer `sesion_refresh`, como el relevo (arquitectura 7.7, excepción b).
- **El trabajo diario de MATU-37** (arquitectura 8.5) revisa, por persona, que la autorización para `consumo` esté vigente (no revocada y, si es de un cuidador de hecho, con la revisión al día según el `Reloj`) **antes** de materializar una alerta o de avisar. Sin ella no crea alertas ni avisa. Los eventos del outbox (`QuiebreProximo`) llevan solo identificadores (`alerta_id`, `perfil_id`), como exige `payload_solo_identificadores`.
- **Alertas y cambios del perfil (MATU-37):** cuando un `PATCH` cambia `fecha_quiebre_estimada`, una alerta abierta con otra `fecha_prevista` queda desalineada. Este contrato no decide qué pasa con ella (cerrarla o dejar que el trabajo diario cree la nueva): lo decide MATU-37 y, si cambia lo que ve la app, actualiza este contrato.
- **MATU-41** lee el `push_token` solo para enviar, y el aviso no lleva el nombre de la persona ni del producto (pendiente de Jorge).
- **Logs:** la línea de la petición lleva la plantilla de la ruta, el usuario y el grupo, nunca el cuerpo. La reutilización de un refresh se registra como evento de seguridad con el id de la familia, sin el token.

## Pendientes para Jorge (MATU-32)

1. **Aprobar las decisiones 37 a 54**, en especial la 37 (autorización propia para el consumo), que es la opción (a) del analista.
2. **Quién descarta alertas:** hoy `admin` y `cuidador`. ¿También el `pagador`? Hasta que decidas, recibe 404.
3. **Plazos de conservación** que propone el analista: borrar las filas de `sesion_refresh` 7 días después de que vencen, y un dispositivo 30 días después de sacarlo. Relacionado: un dispositivo cuya sesión venció sin cerrarse sigue en "Tus dispositivos" hasta que se saca; la tarea de conservación podría revocarlo al vencer su última sesión.
4. **Avisos por push y por correo sin el nombre de la persona ni del producto** (MATU-41). Con la decisión 50 el push no lleva contenido.
5. **RLS de `dispositivo` y `sesion_refresh` para operación** (para MATU-38): hoy `dispositivo_operacion` deja a operación leer `push_token`, y `sesion_operacion` es `FOR ALL`. Se propone una migración que acote a operación a lo que necesita (por ejemplo, ver dispositivos sin `push_token` y revocar sesiones), sin leer ni escribir el resto.
6. **Política de escritura por rol en `perfil_consumo`** (opcional): hoy `perfil_familia` es `FOR ALL` por grupo y el rol lo controla solo la API. Una política que exija `admin` o `cuidador` para escribir sería una segunda barrera.
7. **Política de privacidad 0.10 y entradas 5 y 6 del registro de tratamientos** (consumo y sesión/dispositivos). Las redacta el analista normativo y van en otro PR, en el repositorio MATU. Deben cubrir, al menos: la declaración de la autorización para el consumo (decisión 37); la sección 4, "Tu sesión", que hoy dice que la sesión dura 15 minutos y pasa a 30 días con la cookie; los dispositivos y el endpoint de push; la huella de la IP y del email en la demora progresiva; y la sección 8 (decisión 38). MATU-36 no habilita la autorización mientras `POLITICA_VERSION` sea 0.9.
8. **Renovar la revisión anual de la autorización para el consumo**: como hay un solo consentimiento no revocado por persona y finalidad, una fila nueva exige registrar antes la revocación de la vigente, en la misma transacción. Hasta MATU-44, un cuidador de hecho con la revisión vencida queda con 403 `revision-vencida`, igual que hoy en la ficha.
9. **El nombre de quien entra:** ¿alguna pantalla de MATU-39 lo necesita? Si sí, falta `GET /v1/usuarios/yo` (ver "Lo que no hay").
10. **Gracia en la renovación** (decisión 51) y **riesgo de la demora por email** (decisión 49): confirmar que se aceptan.
11. **Para la tarjeta de consulta legal en Trello:**
    - si el consumo de insumos es un dato de salud según la Ley 21.719 y si basta RLS sin cifrado cuando haya datos reales (la política ya lo trata como dato sensible);
    - la base de licitud de los contadores por huella de IP y de email de la demora progresiva.

## Textos propuestos para `lenguaje.md` (MATU-32)

Pendientes de Jorge y del analista normativo. El contrato remite a ellos y no los fija: van a `docs/lenguaje.md` del repositorio MATU en otro PR.

| Dónde | Texto propuesto |
|---|---|
| Qué se acaba pronto, `dias_restantes > 1` | Se acaban en {n} días |
| Qué se acaba pronto, `dias_restantes = 1` | Se acaba en 1 día |
| Qué se acaba pronto, `dias_restantes = 0` | Se acaban hoy |
| Qué se acaba pronto, encabezado, o `dias_restantes < 0` | Pronto se acaba |
| Nota bajo la fecha estimada | Es un cálculo con lo que anotaste. Revisa de vez en cuando cuánto queda |
| Ayuda de `nombre_libre` | Escribe el nombre como aparece en el envase, por ejemplo «Toallitas húmedas». No escribas remedios ni para qué lo usa |
| Botón de descartar | No avisar esta vez |
| 429 de la entrada (`demasiadas-peticiones`), con `{minutos}` = `Retry-After` / 60 redondeado hacia arriba | Hubo varios intentos de entrar. Espera {minutos} minutos y vuelve a intentarlo |
| Dispositivos, título | Tus dispositivos |
| Dispositivos, el `actual` | Este dispositivo |
| Dispositivos, `ultimo_uso_en` | Último uso: {fecha} a las {hora} |
| Dispositivos, botón | Sacar este dispositivo |

Falta definir el texto de `sesion-expirada`, de los cuatro 409 nuevos y de los 422 propios del consumo (`producto_o_nombre`, `cobertura_maxima`, …).

**Inconsistencia en `lenguaje.md`:** la sección 3.2 pide evitar "sesión" (jerga técnica; dice usar "entrar"), pero la sección 8 usa "Tu sesión terminó" para `no-autenticado` y `token-invalido`. Hay que elegir antes de escribir el texto de `sesion-expirada`.

## Contradicciones (MATU-32)

Este contrato sigue el esquema de la base (`backend/db/01_esquema.sql` y las migraciones) y las decisiones de Martín del 31-10. Jorge corrige la arquitectura en la v1.2 (MATU-43).

| Documento | Dice | Este contrato | Fuente |
|---|---|---|---|
| Arquitectura 9.3 | Cuerpo `{producto_id, tasa_uso, unidad_tasa, stock_estimado, dias_aviso}` | `tasa_unidades` / `tasa_dias`, `stock_unidades`, `unidad`, `producto_id` o `nombre_libre` | Esquema (`perfil_consumo`) |
| Arquitectura 7.3 | Campo `tasa_uso_diaria` y `dias_de_cobertura = piso(stock_unidades / tasa_uso_diaria)` | Fracción entera: `piso(stock_unidades * tasa_dias / tasa_unidades)` | Esquema, comentario de `perfil_consumo` |
| Arquitectura 9.3 | `PATCH /v1/consumo/{id}`, `GET /v1/alertas?estado=`, `POST /v1/alertas/{id}/descartar` | Todo bajo `/v1/personas-cuidadas/{persona_id}/consumo…`, con `X-Grupo-Id` | Decisión 54, instrucción de MATU-32 |
| Arquitectura 9.3 | `GET …/lista-reposicion` | `GET …/consumo/por-acabarse`. La lista de reposición (con sugerencias de envases) es del sprint 4 | Decisión 53 |
| Arquitectura 9.1 | "refresh rotativo de 30 días por dispositivo" | 30 días **desde el inicio de sesión**, sin ventana deslizante | Decisión 39 |
| Arquitectura 11.6 | Aplicación móvil: "tokens en el keystore del sistema" | Web (ADR-026): refresh en cookie `HttpOnly` y access token en memoria | Decisiones 39 y 40 |
| Política v0.9, sección 4, "Tu sesión" | "Cuando entras, tu sesión dura 15 minutos" | El access token dura 15 minutos, pero la sesión dura hasta 30 días con la cookie | Decisión 39. Se corrige en la 0.10 |
| Política v0.9, sección 8 | Ficha y consumo: "los dejamos ilegibles de inmediato destruyendo su clave" | El consumo no se cifra: se borra | Decisión 38. Se corrige en la 0.10 |
| Instrucción de MATU-32 | "El consentimiento es inalterable: la revocación y la confirmación anual son filas nuevas" | La migración 0006 registra la revocación **fijando `revocado_en` una sola vez** en la misma fila (trigger `consentimiento_solo_revocacion`), no con una fila nueva. Y `consentimiento_vigente_uq` impide una segunda fila no revocada para la misma finalidad, así que la confirmación anual como fila nueva exige revocar antes la anterior | Migración 0006 y esquema. Por eso revocar queda fuera, con MATU-44 |
| `lenguaje.md` 3.2 frente a 8 | Evitar "sesión" / "Tu sesión terminó" | Sin texto propio: se pregunta | Ver "Textos propuestos" |

## Fuera de este contrato (MATU-32)

- **Las secciones complementarias de la ficha del ADR-028** (MATU-49).
- **Invitaciones y roles** (MATU-42 y MATU-53, sprint 4).
- **Registrar una reposición** ("Ya lo compré", `resuelta`, `reposicion`): MATU-51, sprint 4.
- **La lista de reposición**, con envases sugeridos, y exportarla (sprint 4).
- **Revocar la autorización para el consumo y cortar los accesos** (MATU-44), y renovar la revisión anual (ver la contradicción con la migración 0006).
- **El catálogo** (`/v1/catalogo/…`, capa 3) y las rutas del despacho.
- **Editar el `nombre` de un dispositivo**, las preferencias de aviso y el correo de MATU-41.
