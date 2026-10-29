# Contratos de la API de MATU

Esta carpeta guarda los contratos OpenAPI 3.1 que el frontend usa para construir pantallas (CLAUDE.md, agente 3) y que el backend implementa. Un contrato se acuerda **antes** de implementar (MATU-09, arquitectura 15.5, regla 1).

```
docs/api/
├── README.md                     este archivo
├── openapi.json                  rutas implementadas (todavía no existe, ver abajo)
└── propuestos/
    ├── ficha.openapi.yaml        MATU-09 parte 1: ficha de relevo
    └── relevo.openapi.yaml       MATU-09 parte 2: acceso de relevo
```

## Propuestos e implementados

- **`propuestos/`** tiene los contratos acordados y todavía no implementados. Su `info.version` termina en `-propuesto`. El frontend puede construir contra ellos con un doble (MATU-23 lo hace así).
- **`openapi.json`** tiene solo rutas implementadas. Una ruta pasa de `propuestos/` a `openapi.json` cuando su historia se termina: se exporta desde `GET /openapi.json` de la API y se quita del archivo propuesto en el mismo PR.
- **La puerta openapi-diff** compara `openapi.json` contra lo que expone la API, y nunca mira `propuestos/`. Un cambio en un contrato propuesto no rompe el pipeline; un cambio en una ruta implementada sí.
- Hoy ni `openapi.json` ni la puerta openapi-diff existen en el pipeline (`.github/workflows/ci.yml`). Las rutas ya implementadas (`/v1/usuarios`, `/v1/sesiones`, `/v1/grupos`, `/v1/grupos/{grupo_id}/personas-cuidadas`) se ven en `GET /openapi.json` con la API levantada. Crear los dos queda pendiente, fuera de MATU-09.
- **Las rutas de la ficha (MATU-12) están implementadas pero siguen en `propuestos/`** (revisado el 28-10). El contrato promete dos cosas: 412 y 428 con `If-Match` / `If-None-Match` (MATU-13, pendiente) y el registro de `plan.leer` y `plan.editar` (MATU-14, ya cumplido). Siguen en `propuestos/` solo por MATU-13. Pasarlas a `openapi.json` ahora fijaría como "implementado" un contrato que la API todavía no cumple. Como la puerta openapi-diff no existe y, cuando exista, no mirará `propuestos/`, el CI no puede fallar por esto: MATU-12 no crea `openapi.json` ni toca `ci.yml`. La historia que cierre la última de las dos (MATU-13 o MATU-14) exporta las rutas a `openapi.json` y las quita del propuesto, como dice la regla de arriba. Diferencias que verá openapi-diff ese día: FastAPI agrega un 422 genérico a `GET …/plan/ficha` (por sus parámetros), y `X-Grupo-Id` sale como `string | null` sin `format: uuid`, igual que en las rutas de MATU-07.
- Cada archivo propuesto es autocontenido: no hace `$ref` a otro archivo. Los componentes comunes (`Problema`, `ProblemaValidacion`, `ErrorCampo`, `CampoFicha`, `Autor`, `XGrupoId`, `PersonaId`, `bearerAuth`, las cabeceras `XRequestId`, `CacheControlNoStore` y `WWWAuthenticateBearer`, y el cuerpo de `NoAutenticado`, `NoEncontrado` y `SinConsentimiento`) son idénticos en los dos.
- **Cabeceras de respuesta.** Toda respuesta, también las de error, declara `X-Request-ID` (UUID, el mismo `request_id` de los logs y del problema; lo pone `app/core/logs.py`). Llevan `Cache-Control: no-store` las que traen texto de la ficha, PIN o enlace, y también la lista de accesos y `/plan/aperturas`, porque dicen a quién se compartió la ficha y cuándo la abrió.

## Rutas

| Método y ruta | Historia | Estado |
|---|---|---|
| `GET /v1/personas-cuidadas/{persona_id}/plan/ficha` | MATU-12, MATU-14 | Implementado por MATU-12, con la auditoría `plan.leer` de MATU-14. Sigue en propuestos solo por MATU-13 |
| `PUT /v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}` | MATU-12, MATU-13, MATU-11, MATU-14 | Implementado por MATU-12, con la auditoría `plan.editar` de MATU-14, sin 412/428 (MATU-13). Sigue en propuestos solo por MATU-13 |
| `POST /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo` | MATU-18 | Propuesto |
| `GET /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo` | MATU-18, MATU-20 | Propuesto |
| `DELETE /v1/accesos-relevo/{acceso_id}` | MATU-20 | Propuesto |
| `POST /v1/relevo/presentacion` | MATU-19, MATU-23 | Propuesto |
| `POST /v1/relevo/canje` | MATU-19, MATU-25 | Propuesto |
| `GET /v1/relevo/ficha` | MATU-19, MATU-20, MATU-23 | Propuesto |
| `GET /v1/personas-cuidadas/{persona_id}/plan/aperturas` | MATU-19 (RF-08) | Propuesto |

## Catálogo de `type` (RFC 7807)

Mismo formato que `backend/app/core/errores.py`: `type`, `title`, `status`, `detail`, `errores[]` y `request_id`, en `application/problem+json`. Los `type` marcados **nuevo** no existen todavía en el código y los agrega la historia que los usa.

| `type` | Status | Cuándo | Origen |
|---|---|---|---|
| `/errores/no-autenticado` | 401 | Falta el access token | Existe (por defecto del 401) |
| `/errores/token-invalido` | 401 | Token inválido, alterado o vencido | Existe (MATU-05a) |
| `/errores/sin-consentimiento` | 403 | Sin consentimiento vigente para `plan_cuidado` | Existe (MATU-12). MATU-07 no definió uno |
| `/errores/revision-vencida` | 403 | El consentimiento lo dio un cuidador de hecho y venció su revisión anual (decisión 33) | Existe (MATU-12) |
| `/errores/no-encontrado` | 404 | No miembro, rol que no alcanza, recurso de otro grupo o inexistente | Existe |
| `/errores/version-desactualizada` | 412 | `If-Match` desactualizado o `If-None-Match: *` sobre un campo que ya existe | Existe (por defecto del 412) |
| `/errores/validacion` | 422 | Cuerpo, cabeceras o consulta inválidos | Existe |
| `/errores/falta-version` | 428 | Escritura sin `If-Match` ni `If-None-Match` | Existe (por defecto del 428) |
| `/errores/pin-incorrecto` | 401 | PIN incorrecto, del 1.º al 4.º intento, con `intentos_restantes` | **Nuevo** (MATU-19) |
| `/errores/sin-sesion-relevo` | 401 | `GET /v1/relevo/ficha` sin cookie, o con una cookie que no corresponde a una sesión en Redis (alterada o vencida por su TTL). Nunca por revocar | **Nuevo** (MATU-19) |
| `/errores/relevo-vencido` | 410 | El acceso venció (presentación, canje, o cualquier petición con cookie válida) | **Nuevo** (MATU-19) |
| `/errores/relevo-revocado` | 410 | El acceso se revocó (presentación, canje, o cualquier petición con cookie válida) | **Nuevo** (MATU-20) |
| `/errores/relevo-no-disponible` | 410 | El token no corresponde a ningún acceso (presentación o canje) | **Nuevo** (MATU-19) |
| `/errores/relevo-pausado` | 410 | La autorización de la persona del acceso no está vigente (consentimiento retirado o revisión anual vencida). No dice el motivo. Presentación, canje y ficha (decisión 33 en el relevo, de Martín del 28-10, pendiente de revisión de Jorge) | **Nuevo** (MATU-19) |
| `/errores/relevo-bloqueado` | 423 | 5 PIN incorrectos (presentación, canje o sesión) | **Nuevo** (MATU-19) |
| `/errores/error-interno` | 500 | Error inesperado, o una sección de la ficha que no se puede descifrar (alterada o movida). Nunca lleva el texto | Existe (por defecto del 500) |
| `/errores/servicio-no-disponible` | 503 | La custodia de la clave maestra no está configurada, o no envolvió o no desenvolvió la clave de datos (decisión 32) | Existe (MATU-12, por defecto del 503) |
| `/errores/demasiadas-peticiones` | 429 | Más de 30 presentaciones o más de 10 canjes por hora desde una IP, en contadores separados | Existe (por defecto del 429), lo usa MATU-25 |

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

- **Decisión 33 en el relevo: `410 /errores/relevo-pausado`** (decisión de Martín del 28-10, **pendiente de revisión de Jorge**). Si la autorización de la persona del acceso no está vigente (consentimiento para `plan_cuidado` revocado, o cuidador de hecho con `revision_vence_en` igual o anterior al instante del Reloj), presentación, canje y `GET /v1/relevo/ficha` responden 410 `relevo-pausado`, con `title` «Ya no está disponible» y un `detail` neutro. Se evalúa después de los 410 de estado y del 423, y antes del PIN. No cuenta como intento ni crea sesión; en la ficha borra la cookie y descarta la sesión. Si se renueva la autorización, el mismo enlace vuelve a servir. Lo decide la función `relevo_autorizacion_vigente(ahora)` (migración 0006), `SECURITY DEFINER`, que devuelve solo un booleano: el relevo sigue sin leer `consentimiento`. Esto cierra en parte el "Riesgo abierto" de más arriba: retirar la autorización ya corta la lectura del relevo, aunque no revoca los accesos.
- **Migración 0006:** `indice_token.revocado_en` (decisión 23), la política `acceso_relevo_propio` (FOR ALL) reemplazada por `acceso_relevo_leer` (SELECT) y `acceso_relevo_contar` (UPDATE) más un trigger que limita al relevo a `pin_intentos_fallidos`, `usos` y `ultimo_uso_en`, y la función de la decisión 33.
- **Canje sin `PEPPER_PIN`:** 503 `/errores/servicio-no-disponible` después de los 410/423 y antes de comparar el PIN. Tampoco con Redis caído (503). El contrato lo declara como `RelevoSinServicio` en el canje y en la ficha. La sesión en Redis se crea después del commit del canje: si Redis falla, queda `relevo.canje` sin sesión y se responde 503.
- **Sin entrada en `indice_token`** con una cookie válida (purgado tras vencer), la ficha responde 410 `relevo-vencido`.
- **429 por IP** (MATU-25) y **`/plan/aperturas`** (sprint 3) no están implementados.
