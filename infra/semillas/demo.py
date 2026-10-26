"""MATU · Semilla de demostración (MATU-30, estrategia de pruebas, sección 9).

Crea en la base LOCAL dos familias sintéticas y un pagador con permiso para ver el plan:

- Familia Soto: Carmen (admin, la cuidadora), Rodrigo (hijo, pagador con puede_ver_plan) y María,
  la persona cuidada, con consentimiento de cuidadora de hecho. Coincide con la demo web.
- Familia Riquelme: Patricia (admin), Tomás (observador) y Hernán, con consentimiento del titular.

Usa los casos de uso de la API, conectada como matu_app (DATABASE_URL), para que las cuentas sirvan
para iniciar sesión: registro con Argon2id y el HMAC del email con PEPPER_EMAIL (MATU-04), grupo
con su admin (MATU-06) y alta de la persona con su consentimiento y su auditoría (MATU-07). La
versión de la política es POLITICA_VERSION.

Única escritura sin caso de uso: la membresía del segundo miembro de cada familia, porque las
invitaciones aún no existen. Va como matu_app, dentro del contexto del admin y de su grupo
(política membresia_familia), nunca como superusuario.

Es idempotente: lo que ya existe (cuenta por email, grupo por nombre entre los del admin, membresía,
persona por nombre) no se duplica. Una cuenta que ya existía conserva su contraseña.

Contraseña de las cuentas nuevas: la de la variable SEMILLA_CONTRASENA (10 a 128 caracteres) o, si
no está, una aleatoria que se imprime una sola vez. Nunca se escribe en el repositorio.

Se corre desde la raíz del repositorio, con el entorno virtual de backend/ activo:

    python infra/semillas/demo.py

Se niega a correr con ENTORNO=produccion. Ojo: las pruebas del backend vacían la base local
(test_aislamiento.py), y con ella esta semilla. Después de correrlas, se vuelve a sembrar.
"""

import os
import secrets
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# backend/ en la ruta de importación: la semilla usa los casos de uso de la API
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import obtener_configuracion  # noqa: E402
from app.core.db import fabrica_sesiones, sesion_tenant  # noqa: E402
from app.modules.care_circle.application.grupos import crear_grupo, listar_grupos  # noqa: E402
from app.modules.care_circle.application.personas import SolicitudAlta, dar_de_alta, listar_personas  # noqa: E402
from app.modules.care_circle.application.ports import DatosDireccion  # noqa: E402
from app.modules.care_circle.domain.avisos import AVISO_CUIDADOR_DE_HECHO  # noqa: E402
from app.modules.care_circle.domain.personas import AvisoMostrado, CalidadOtorgante  # noqa: E402
from app.modules.care_circle.infrastructure.membresia import rol_activo  # noqa: E402
from app.modules.care_circle.infrastructure.repositorio_grupos import RepositorioGruposSQL  # noqa: E402
from app.modules.care_circle.infrastructure.repositorio_personas import RepositorioPersonasSQL  # noqa: E402
from app.modules.iam.application.ports import HasherContrasenas  # noqa: E402
from app.modules.iam.application.registro import registrar_usuario  # noqa: E402
from app.modules.iam.domain.credenciales import (  # noqa: E402
    LARGO_MAXIMO_CONTRASENA,
    LARGO_MINIMO_CONTRASENA,
    EmailYaRegistrado,
    indice_email,
    normalizar_email,
)
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id  # noqa: E402
from app.modules.iam.infrastructure.repositorio_usuarios import RepositorioUsuariosSQL  # noqa: E402
from app.shared.puertos import Reloj  # noqa: E402
from app.shared.reloj_sistema import RelojSistema  # noqa: E402

# El nombre de la variable, no su valor
VARIABLE_CONTRASENA = "SEMILLA_CONTRASENA"  # pragma: allowlist secret

# --- Los datos, todos sintéticos ----------------------------------------------------------------------


@dataclass(frozen=True)
class CuentaDemo:
    nombre: str
    email: str
    rol: str
    puede_ver_plan: bool = False


@dataclass(frozen=True)
class PersonaDemo:
    nombre: str
    nombre_pila: str
    nivel_apoyo: str
    calidad: CalidadOtorgante
    direccion: DatosDireccion | None
    referencia_documento: str | None = None


@dataclass(frozen=True)
class FamiliaDemo:
    grupo: str
    admin: CuentaDemo
    miembros: tuple[CuentaDemo, ...]
    persona: PersonaDemo


FAMILIAS: tuple[FamiliaDemo, ...] = (
    FamiliaDemo(
        grupo="Familia Soto",
        admin=CuentaDemo("Carmen Fuentes", "carmen@correo.ejemplo", "admin"),
        miembros=(CuentaDemo("Rodrigo Soto", "rodrigo@correo.ejemplo", "pagador", puede_ver_plan=True),),
        persona=PersonaDemo(
            nombre="María Soto",
            nombre_pila="María",
            nivel_apoyo="apoyo_parcial",
            calidad=CalidadOtorgante.CUIDADOR_DE_HECHO,
            direccion=DatosDireccion(
                etiqueta="Casa",
                calle="Los Aromos",
                numero="123",
                depto=None,
                comuna="La Reina",
                region="Metropolitana",
                referencia=None,
            ),
        ),
    ),
    FamiliaDemo(
        grupo="Familia Riquelme",
        admin=CuentaDemo("Patricia Riquelme", "patricia@correo.ejemplo", "admin"),
        miembros=(CuentaDemo("Tomás Riquelme", "tomas@correo.ejemplo", "observador"),),
        persona=PersonaDemo(
            nombre="Hernán Riquelme",
            nombre_pila="Hernán",
            nivel_apoyo="autovalente_con_supervision",
            calidad=CalidadOtorgante.TITULAR,
            direccion=DatosDireccion(
                etiqueta="Casa",
                calle="Las Acacias",
                numero="456",
                depto="21",
                comuna="Ñuñoa",
                region="Metropolitana",
                referencia=None,
            ),
        ),
    ),
)

# --- La siembra ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CuentaSembrada:
    nombre: str
    email: str
    grupo: str
    rol: str
    puede_ver_plan: bool
    # False si la cuenta ya existía: conserva su contraseña
    creada: bool


@dataclass(frozen=True)
class FamiliaSembrada:
    grupo_id: uuid.UUID
    usuarios: tuple[uuid.UUID, ...]
    persona_creada: bool


class SemillaInconsistente(RuntimeError):
    """Lo que ya existe en la base no calza con la semilla. El mensaje nunca lleva emails."""


_MEMBRESIA = text("SELECT rol, puede_ver_plan FROM membresia WHERE grupo_id = :grupo_id AND usuario_id = :usuario_id")
_INSERTAR_MEMBRESIA = text(
    "INSERT INTO membresia (grupo_id, usuario_id, rol, puede_ver_plan, invitado_por)"
    " VALUES (:grupo_id, :usuario_id, :rol, :puede_ver_plan, :invitado_por)"
)


@dataclass
class Sembradora:
    fabrica: sessionmaker[Session]
    pepper: bytes
    version_politica: str
    reloj: Reloj
    hasher: HasherContrasenas

    def cuenta(self, cuenta: CuentaDemo, contrasena: str) -> tuple[uuid.UUID, bool]:
        """Registra la cuenta (MATU-04). Si el email ya tiene cuenta, devuelve la existente."""
        repositorio = RepositorioUsuariosSQL(self.fabrica)
        try:
            creada = registrar_usuario(
                nombre=cuenta.nombre,
                email=cuenta.email,
                contrasena=contrasena,
                pepper=self.pepper,
                hasher=self.hasher,
                repositorio=repositorio,
            )
            return creada.id, True
        except EmailYaRegistrado:
            existente = repositorio.buscar_credencial(indice_email(self.pepper, normalizar_email(cuenta.email)))
            if existente is None:
                raise SemillaInconsistente(
                    "Una cuenta de la semilla existe pero no se encuentra con este PEPPER_EMAIL"
                ) from None
            return existente.usuario_id, False

    def grupo(self, admin_id: uuid.UUID, nombre: str) -> uuid.UUID:
        """El grupo con ese nombre donde la cuenta es admin, o uno nuevo (MATU-06)."""
        repositorio = RepositorioGruposSQL(self.fabrica)
        for grupo in listar_grupos(admin_id, repositorio):
            if grupo.nombre == nombre and grupo.rol == "admin":
                return grupo.id
        return crear_grupo(admin_id, nombre, repositorio).id

    def membresia(self, admin_id: uuid.UUID, grupo_id: uuid.UUID, usuario_id: uuid.UUID, cuenta: CuentaDemo) -> None:
        """La membresía del miembro, escrita como matu_app en el contexto del admin y su grupo.

        Reemplaza a la invitación, que aún no existe. Si ya hay una con otro rol, se detiene.
        """
        with sesion_tenant(self.fabrica, usuario_id=admin_id, grupo_id=grupo_id) as sesion:
            if rol_activo(sesion, admin_id, grupo_id) != "admin":
                raise SemillaInconsistente("El admin de la semilla no es admin activo de su grupo")
            existente = sesion.execute(_MEMBRESIA, {"grupo_id": grupo_id, "usuario_id": usuario_id}).first()
            if existente is not None:
                if (existente.rol, existente.puede_ver_plan) != (cuenta.rol, cuenta.puede_ver_plan):
                    raise SemillaInconsistente("Un miembro de la semilla ya está en el grupo con otro rol")
                return
            sesion.execute(
                _INSERTAR_MEMBRESIA,
                {
                    "grupo_id": grupo_id,
                    "usuario_id": usuario_id,
                    "rol": cuenta.rol,
                    "puede_ver_plan": cuenta.puede_ver_plan,
                    "invitado_por": admin_id,
                },
            )

    def persona(self, admin_id: uuid.UUID, grupo_id: uuid.UUID, persona: PersonaDemo) -> bool:
        """Da de alta a la persona con su consentimiento (MATU-07), si el grupo no la tiene ya."""
        with sesion_tenant(self.fabrica, usuario_id=admin_id, grupo_id=grupo_id) as sesion:
            repositorio = RepositorioPersonasSQL(sesion, grupo_id)
            if any(p.nombre == persona.nombre for p in listar_personas("admin", repositorio)):
                return False
            aviso = None
            if persona.calidad is CalidadOtorgante.CUIDADOR_DE_HECHO:
                # La semilla declara haber mostrado el aviso vigente, como lo haría la pantalla
                aviso = AvisoMostrado(id=AVISO_CUIDADOR_DE_HECHO.id, version=AVISO_CUIDADOR_DE_HECHO.version)
            solicitud = SolicitudAlta(
                usuario_id=admin_id,
                grupo_id=grupo_id,
                rol="admin",
                nombre=persona.nombre,
                nombre_pila=persona.nombre_pila,
                nivel_apoyo=persona.nivel_apoyo,
                calidad_otorgante=persona.calidad,
                referencia_documento=persona.referencia_documento,
                aviso=aviso,
                direccion=persona.direccion,
            )
            dar_de_alta(solicitud, self.version_politica, self.reloj, repositorio)
            return True

    def familia(self, familia: FamiliaDemo, contrasena: str) -> tuple[FamiliaSembrada, list[CuentaSembrada]]:
        admin_id, admin_creada = self.cuenta(familia.admin, contrasena)
        grupo_id = self.grupo(admin_id, familia.grupo)
        cuentas = [_sembrada(familia, familia.admin, admin_creada)]
        usuarios = [admin_id]
        for miembro in familia.miembros:
            usuario_id, creada = self.cuenta(miembro, contrasena)
            self.membresia(admin_id, grupo_id, usuario_id, miembro)
            cuentas.append(_sembrada(familia, miembro, creada))
            usuarios.append(usuario_id)
        persona_creada = self.persona(admin_id, grupo_id, familia.persona)
        return FamiliaSembrada(grupo_id=grupo_id, usuarios=tuple(usuarios), persona_creada=persona_creada), cuentas


def _sembrada(familia: FamiliaDemo, cuenta: CuentaDemo, creada: bool) -> CuentaSembrada:
    return CuentaSembrada(
        nombre=cuenta.nombre,
        email=normalizar_email(cuenta.email),
        grupo=familia.grupo,
        rol=cuenta.rol,
        puede_ver_plan=cuenta.puede_ver_plan,
        creada=creada,
    )


def sembrar(
    sembradora: Sembradora, contrasena: str, familias: Sequence[FamiliaDemo] = FAMILIAS
) -> tuple[list[FamiliaSembrada], list[CuentaSembrada]]:
    familias_sembradas: list[FamiliaSembrada] = []
    cuentas: list[CuentaSembrada] = []
    for familia in familias:
        sembrada, suyas = sembradora.familia(familia, contrasena)
        familias_sembradas.append(sembrada)
        cuentas.extend(suyas)
    return familias_sembradas, cuentas


# --- Línea de comandos -----------------------------------------------------------------------------------


def _contrasena() -> tuple[str, bool]:
    """La contraseña de las cuentas nuevas y si vino de SEMILLA_CONTRASENA."""
    desde_entorno = os.environ.get(VARIABLE_CONTRASENA, "")
    if desde_entorno:
        if not LARGO_MINIMO_CONTRASENA <= len(desde_entorno) <= LARGO_MAXIMO_CONTRASENA:
            raise SystemExit(
                f"{VARIABLE_CONTRASENA} debe tener entre {LARGO_MINIMO_CONTRASENA} y "
                f"{LARGO_MAXIMO_CONTRASENA} caracteres."
            )
        return desde_entorno, True
    return secrets.token_urlsafe(12), False


def main() -> int:
    configuracion = obtener_configuracion()
    if configuracion.entorno == "produccion":
        print("La semilla de demostración no corre con ENTORNO=produccion.", file=sys.stderr)
        return 2
    if configuracion.pepper_email is None:
        print("Falta PEPPER_EMAIL en el .env: sin él las cuentas no sirven para iniciar sesión.", file=sys.stderr)
        return 2
    assert configuracion.politica_version is not None  # la configuración la exige fuera de pruebas

    contrasena, desde_entorno = _contrasena()
    sembradora = Sembradora(
        fabrica=fabrica_sesiones(),
        pepper=configuracion.pepper_email.get_secret_value().encode("utf-8"),
        version_politica=configuracion.politica_version,
        reloj=RelojSistema(),
        hasher=HasherArgon2id(),
    )
    try:
        familias, cuentas = sembrar(sembradora, contrasena)
    except SemillaInconsistente as error:
        print(f"No se pudo sembrar: {error}.", file=sys.stderr)
        return 1

    print(f"Semilla de demostración en la base local (ENTORNO={configuracion.entorno}).\n")
    for c in cuentas:
        permiso = ", ve el plan" if c.puede_ver_plan else ""
        estado = "creada" if c.creada else "ya existía, conserva su contraseña"
        print(f"  {c.grupo:<18} {c.nombre:<18} {c.rol}{permiso:<13} {c.email:<26} {estado}")
    nuevas = sum(f.persona_creada for f in familias)
    print(f"\nPersonas cuidadas dadas de alta ahora: {nuevas} de {len(familias)}.")

    if not any(c.creada for c in cuentas):
        print("No se creó ninguna cuenta.")
    elif desde_entorno:
        print(f"Contraseña de las cuentas creadas: la de {VARIABLE_CONTRASENA}.")
    else:
        # Única vez que se muestra. No se guarda en ningún archivo
        print(f"Contraseña de las cuentas creadas (anótala, no se vuelve a mostrar): {contrasena}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
