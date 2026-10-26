# Semillas

Datos sintéticos para la base **local** de demostración (estrategia de pruebas, sección 9). Ninguna persona real: nombres inventados y correos del dominio reservado `correo.ejemplo`.

## `demo.py` · dos familias y un pagador con permiso para ver el plan

| Grupo | Cuenta | Rol | Persona cuidada |
|---|---|---|---|
| Familia Soto | Carmen Fuentes, `carmen@correo.ejemplo` | admin (la cuidadora) | María Soto, cuidadora de hecho |
| Familia Soto | Rodrigo Soto, `rodrigo@correo.ejemplo` | pagador, ve el plan | |
| Familia Riquelme | Patricia Riquelme, `patricia@correo.ejemplo` | admin | Hernán Riquelme, titular |
| Familia Riquelme | Tomás Riquelme, `tomas@correo.ejemplo` | observador | |

La familia Soto coincide con la demo web (Carmen cuida a María y Rodrigo es su hijo).

Usa los casos de uso de la API conectada como `matu_app`: registro con Argon2id y `PEPPER_EMAIL`, grupo con su admin y alta de la persona con su consentimiento y su auditoría. Por eso las cuentas sirven para iniciar sesión en la API y en el modo real de la demo. La única escritura sin caso de uso es la membresía del segundo miembro de cada familia, porque las invitaciones aún no existen: va como `matu_app` en el contexto del admin y de su grupo, nunca como superusuario. La ficha de relevo no se siembra: llega con MATU-11 y MATU-12.

### Cómo correrla

Con la base levantada, migrada (`alembic upgrade head`) y el `.env` completo (`DATABASE_URL`, `PEPPER_EMAIL`, `POLITICA_VERSION`). Desde la **raíz del repositorio**, con el entorno virtual de `backend/` activo:

```
python infra/semillas/demo.py
```

- **Contraseña.** Las cuentas nuevas usan la de la variable `SEMILLA_CONTRASENA` (10 a 128 caracteres), que no se imprime. Si no está, la semilla genera una aleatoria y la imprime **una sola vez**: anótala. Nunca se guarda en un archivo ni en el repositorio.

  ```
  SEMILLA_CONTRASENA='una-clave-larga' python infra/semillas/demo.py
  ```

- **Idempotente.** Se puede correr varias veces: lo que ya existe no se duplica, y una cuenta que ya existía conserva su contraseña. Para cambiarlas hay que vaciar la base y volver a sembrar.
- **Nunca en producción.** Con `ENTORNO=produccion` se niega a correr.

> **Las pruebas del backend vacían la base local** (`test_aislamiento.py` hace `TRUNCATE` al empezar), y con ella esta semilla. Después de correr `pytest`, vuelve a sembrar. No guardes datos de trabajo en la base local.

La prueba `backend/tests/test_semilla_demo.py` siembra familias con emails únicos, verifica las membresías, los consentimientos, el inicio de sesión y la idempotencia, y las borra al terminar.
