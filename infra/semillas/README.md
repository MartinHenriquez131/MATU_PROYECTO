# Semillas

Datos sintéticos para la base **local** o la de **demostración** (estrategia de pruebas, sección 9). Ninguna persona real: nombres inventados, correos de `example.com` y `example.org` (dominios reservados, RFC 2606) y celulares de la serie `+56 9 0000 00xx`, que no se asigna a nadie. Hasta MATU-25 los correos eran de `correo.ejemplo`, que no es reservado; se cambió porque staging solo acepta correos de dominios reservados (decisión 105 de `docs/api/README.md`), y la semilla los exige también al registrar. La semilla no envía correo ni mensajes.

## `demo.py` · la demo lista para los recorridos críticos (MATU-30 y MATU-64)

| Grupo | Cuenta | Rol | Celular |
|---|---|---|---|
| Familia Soto | Carmen Fuentes, `carmen@example.com` | admin (la cuidadora) | +56 9 0000 0001 |
| Familia Soto | Luisa Contreras, `luisa@example.org` | cuidador (la reemplaza) | +56 9 0000 0002 |
| Familia Soto | Rodrigo Soto, `rodrigo@example.com` | pagador, ve el plan | +56 9 0000 0003 |
| Familia Soto | Javiera Soto, `javiera@example.org` | observador | +56 9 0000 0004 |
| Familia Riquelme | Patricia Riquelme, `patricia@example.com` | admin | +56 9 0000 0005 |
| Familia Riquelme | Tomás Riquelme, `tomas@example.org` | observador | +56 9 0000 0006 |

La familia Soto tiene los cuatro roles. Usa los mismos nombres que la demo web de `Demo/` (Carmen cuida a María y Rodrigo es su hijo), pero no los mismos correos: la demo web sigue con `@correo.ejemplo` y no apunta a staging.

Cada persona cuidada trae:

| | María Soto (Familia Soto) | Hernán Riquelme (Familia Riquelme) |
|---|---|---|
| Autorización | cuidadora de hecho, para la ficha y para los insumos | titular, para la ficha y para los insumos |
| Ficha de relevo | los tres campos, y «quién es», «lo que le gusta» y «alimentación» | los tres campos, y «quién es» y «movilidad» |
| Insumos | pañal (se acaba en 2 días: **alerta abierta**), toallitas y crema | suplemento (se acaba en 4 días: **alerta abierta**) y protectores |
| Relevo de ejemplo | Rosa, por 7 días, con «quién es» y «lo que le gusta» | no |

- **La ficha va cifrada** con el `CifradorSecciones` real (AES-256-GCM, una clave por persona, envuelta con la KEK de `KEK_ENTORNO`). En la base no queda texto en claro.
- **La alerta se ve de inmediato:** al final la semilla corre el trabajo diario de MATU-37 solo para sus dos grupos, sin esperar a las 04:00.
- **El catálogo** de MATU-59 (`catalogo_demo.py`: seis productos y dos comercios ficticios) se siembra antes, porque los insumos se anotan con sus productos.

Todo pasa por los casos de uso de la API, conectada como `matu_app`: registro con Argon2id y `PEPPER_EMAIL`, grupo, alta con su autorización y su auditoría, autorización de consumo, ficha con `If-None-Match: *`, insumos, trabajo diario, compartir con el relevo y borrar sus datos. Solo dos escrituras no tienen caso de uso, siempre como `matu_app` y nunca como superusuario: la membresía del resto de los miembros, porque las invitaciones aún no existen (contexto del admin y su grupo), y el celular de una cuenta que una semilla anterior dejó con el celular compartido (contexto de la propia cuenta; el celular queda sin verificar).

### Cómo correrla

Con la base levantada, migrada (`alembic upgrade head`) y el `.env` completo: `DATABASE_URL`, `PEPPER_EMAIL`, `POLITICA_VERSION`, `PEPPER_PIN`, `CUSTODIA_KEK=entorno_sintetico` con `KEK_ENTORNO`, y `ORIGEN_WEB` para el enlace del relevo. Desde la **raíz del repositorio**, con el entorno virtual de `backend/` activo:

```
python infra/semillas/demo.py                 # siembra lo que falta
python infra/semillas/demo.py --restablecer   # deja las dos familias como recién sembradas
```

- **Contraseña.** Las cuentas nuevas usan la de la variable de entorno `SEMILLA_CONTRASENA` (10 a 128 caracteres), definida solo en la terminal donde se corre la semilla, y que no se imprime. Si no está, la semilla genera una aleatoria y la imprime **una sola vez**, también si la siembra se corta a medias: anótala. Nunca se guarda en un archivo ni en el repositorio.
- **El relevo de ejemplo.** Su enlace y su PIN salen **una sola vez** en la salida y quedan en `infra/semillas/salida/relevo-demo.txt`, que git ignora (`infra/semillas/.gitignore`). La base guarda solo sus huellas: si el archivo se pierde, `--restablecer` crea uno nuevo. Con `SEMILLA_PIN` (4 dígitos) en la terminal, el PIN es ese, para que el equipo lo conozca de antemano; si no, es aleatorio. No corras la semilla donde su salida quede en un log compartido.
- **Idempotente.** Se puede correr varias veces: lo que ya existe no se duplica (cuenta por correo, grupo, membresía, persona por nombre, autorización vigente, campo o sección ya escritos, insumo del mismo producto, relevo vigente), y la segunda corrida no deja ni una fila más en la auditoría. Una cuenta que ya existía conserva su contraseña.
- **Restablecer en menos de 10 minutos** (unos 10 segundos en local). `--restablecer` borra al tiro a cada persona de los dos grupos con el mismo caso de uso de «Borrar sus datos» (MATU-72): corta sus enlaces, destruye su clave y borra su ficha, sus insumos y sus alertas. Después vuelve a sembrar todo y deja el catálogo con sus precios y stock. Las cuentas y los grupos quedan, con su contraseña. No toca las cuentas ni los grupos que se crearon durante la demo (el recorrido 1): para repetirlo, usa otro correo de `example.com`.
- **Nunca en producción.** Con `ENTORNO=produccion` se niega a correr.
- **Solo como `matu_app`.** Al conectarse comprueba `SELECT current_user`. Si `DATABASE_URL` entra con otro rol (el dueño de la base o un superusuario), se detiene con salida 2 antes de escribir nada, sin mostrar la URL.

> **Las pruebas del backend vacían la base local** (`test_aislamiento.py` hace `TRUNCATE` al empezar), y con ella esta semilla. Después de correr `pytest`, vuelve a sembrar. No guardes datos de trabajo en la base local.

### Los recorridos que deja listos

1. Crear la cuenta, la persona y la autorización, y llenar la ficha (con una cuenta nueva, o mirando la de María).
2. Compartir con un relevo con PIN, abrir la ficha en otro teléfono y cortar el acceso (el de Rosa ya está creado).
3. Anotar los insumos y ver el aviso de que se acaban (el pañal de María y el suplemento de Hernán).
4. La lista de reposición: exportar, imprimir o compartir, y anotar una compra.

Los recorridos 5 (pedido y pago) y 6 (retiro en el comercio) dependen de MATU-61 a 63. Se agregarán en `Sembradora.capa_3`, que hoy no hace nada.

La prueba `backend/tests/test_semilla_demo.py` siembra familias con correos únicos y una copia única del catálogo, y verifica los roles, los celulares, la ficha cifrada, la alerta, el relevo con su PIN, la idempotencia y `--restablecer`. Borra todo al terminar.
