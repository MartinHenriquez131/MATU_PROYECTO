"""MATU · Semilla de demostración (MATU-30 y MATU-64, estrategia de pruebas, sección 9).

Deja la base LOCAL o la de la demo lista para probar los recorridos críticos, con datos inventados:

- Familia Soto: Carmen (admin, la cuidadora), Luisa (cuidadora de reemplazo), Rodrigo (hijo, pagador con
  puede_ver_plan) y Javiera (nieta, observadora). María es la persona cuidada, con autorización de cuidadora de
  hecho. Están los cuatro roles. Coincide con la demo web.
- Familia Riquelme: Patricia (admin) y Tomás (observador). Hernán, con autorización del titular.

Cada cuenta nueva acepta la política de privacidad vigente al crearse, por el mismo caso de uso que POST /v1/usuarios
(MATU-75): queda su fila en aceptacion_politica con la versión y la huella. Una cuenta que ya existía no se completa.
Sin POLITICA_VERSION con su texto publicado y POLITICA_ACTUALIZADA_EN la semilla no corre.

Cada persona trae, todo por los casos de uso de la API y conectada como matu_app:

1. Su alta con la autorización para la ficha (MATU-07) y la autorización para calcular sus insumos (MATU-36).
2. Su ficha de relevo completa: los tres campos y algunas secciones complementarias (MATU-12 y MATU-50), cifradas
   con el CifradorSecciones real (AES-256-GCM, una clave por persona). Nada se guarda en claro.
3. Sus insumos (MATU-36), hechos para que uno se acabe pronto: el trabajo diario (MATU-37) corre al final, solo
   para los grupos de la semilla, y deja la alerta abierta sin esperar a las 04:00.
4. Familia Soto: un acceso de relevo de ejemplo vigente por 7 días (MATU-18), con las secciones «quién es» y
   «lo que le gusta». Con SEMILLA_PIN (4 dígitos) el PIN es ese; si no, uno aleatorio.

Antes de las familias siembra el catálogo curado de MATU-59 (infra/semillas/catalogo_demo.py): los insumos se
anotan con sus productos. Cada cuenta tiene su propio correo (example.com o example.org, dominios reservados) y su
propio celular de la serie +56 9 0000 00xx, que no se asigna a nadie.

Solo dos escrituras no tienen caso de uso, y van como matu_app, nunca como superusuario:
- la membresía del resto de los miembros, porque las invitaciones aún no existen (contexto del admin y su grupo);
- el celular de una cuenta que ya existía con otro (contexto de la propia cuenta, política usuario_propio_editar): las
  semillas anteriores a MATU-64 daban a todas el mismo.
La ficha, los insumos, la alerta, el relevo y el restablecer pasan por los casos de uso.

Es idempotente: lo que ya existe (cuenta por email, grupo por nombre entre los del admin, membresía, persona por
nombre, autorización vigente, campo o sección ya escritos, insumo del mismo producto, relevo vigente de ejemplo) no
se duplica. Una cuenta que ya existía conserva su contraseña.

--restablecer deja las dos familias como recién sembradas: borra al tiro a cada persona de sus grupos con el mismo
caso de uso de «Borrar sus datos» (MATU-72: corta los enlaces, destruye la clave, borra la ficha y los insumos)
y vuelve a sembrar. Las cuentas y los grupos quedan, con su contraseña. No toca cuentas ni grupos creados durante
la demo fuera de las dos familias.

Contraseña de las cuentas nuevas: la de la variable SEMILLA_CONTRASENA (10 a 128 caracteres) o, si no está, una
aleatoria. --restablecer no cambia las contraseñas.

Credenciales (regla de Jorge del 08-11: los logs nunca llevan PIN ni tokens): por omisión la salida NUNCA trae el
PIN, el enlace del relevo ni la contraseña aleatoria. Van a infra/semillas/salida/ (relevo-demo.txt y
contrasena-demo.txt), que git ignora, con permisos solo para el dueño si el sistema lo permite, y la salida dice
solo dónde quedaron. Vale también si la corrida se detiene a la mitad. Con SEMILLA_PIN, el PIN no se escribe en el
archivo ni se imprime nunca: el archivo dice que es el de SEMILLA_PIN. --mostrar-credenciales las imprime en la
terminal: para una sesión railway ssh o local, donde la salida queda solo en la terminal.

Desde la raíz del repositorio, con el entorno virtual de backend/ activo:

    python infra/semillas/demo.py                          siembra lo que falta
    python infra/semillas/demo.py --restablecer            borra lo de las dos familias y vuelve a sembrar
    python infra/semillas/demo.py --mostrar-credenciales   además imprime el PIN, el enlace y la contraseña

Se niega a correr con ENTORNO=produccion, y si DATABASE_URL no entra como matu_app (SELECT current_user), sin
mostrar la URL. Necesita CUSTODIA_KEK=entorno_sintetico con KEK_ENTORNO (la ficha) y PEPPER_PIN (el relevo). Ojo:
las pruebas del backend vacían la base local (test_aislamiento.py), y con ella esta semilla. Después de correrlas,
se vuelve a sembrar.

Recorridos 5 (pedido y pago) y 6 (retiro en el comercio): dependen de MATU-61 a 63. Se agregan en
Sembradora.capa_3, que hoy no hace nada.
"""

import argparse
import importlib.util
import os
import re
import secrets
import sys
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any
from zoneinfo import ZoneInfo

# backend/ en la ruta de importación: la semilla usa los casos de uso de la API
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from dotenv import dotenv_values  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import Configuracion, obtener_configuracion  # noqa: E402
from app.core.db import fabrica_sesiones, sesion_tenant  # noqa: E402
from app.modules.care_circle.application.autorizaciones import (  # noqa: E402
    SolicitudAutorizacion,
    otorgar_autorizacion,
)
from app.modules.care_circle.application.borrado import SolicitudBorrado, borrar_persona  # noqa: E402
from app.modules.care_circle.application.grupos import crear_grupo, listar_grupos  # noqa: E402
from app.modules.care_circle.application.personas import SolicitudAlta, dar_de_alta, listar_personas  # noqa: E402
from app.modules.care_circle.application.ports import DatosDireccion  # noqa: E402
from app.modules.care_circle.application.retiro import EfectoDelRetiro  # noqa: E402
from app.modules.care_circle.domain.avisos import AVISO_CUIDADOR_DE_HECHO  # noqa: E402
from app.modules.care_circle.domain.declaraciones import huella_declaracion_pedidos  # noqa: E402
from app.modules.care_circle.domain.personas import (  # noqa: E402
    FINALIDAD_CONSUMO,
    FINALIDAD_DESPACHO,
    FINALIDAD_PLAN_CUIDADO,
    AvisoMostrado,
    CalidadOtorgante,
    EstadoAutorizacion,
    estado_autorizacion,
)
from app.modules.care_circle.domain.retiro import finalidades_retirables  # noqa: E402
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion  # noqa: E402
from app.modules.care_circle.infrastructure.membresia import rol_activo  # noqa: E402
from app.modules.care_circle.infrastructure.repositorio_autorizaciones import (  # noqa: E402
    RepositorioAutorizacionesSQL,
)
from app.modules.care_circle.infrastructure.repositorio_borrado import RepositorioBorradoSQL  # noqa: E402
from app.modules.care_circle.infrastructure.repositorio_grupos import RepositorioGruposSQL  # noqa: E402
from app.modules.care_circle.infrastructure.repositorio_personas import RepositorioPersonasSQL  # noqa: E402
from app.modules.care_circle.infrastructure.repositorio_retiros import RepositorioRetirosSQL  # noqa: E402
from app.modules.care_plan.api.esquemas import SolicitudCampo  # noqa: E402
from app.modules.care_plan.application.ficha import PeticionFicha, guardar_campo  # noqa: E402
from app.modules.care_plan.application.ports import CustodiaClaves  # noqa: E402
from app.modules.care_plan.application.relevo import AccesoEntregado, SolicitudCompartir, compartir  # noqa: E402
from app.modules.care_plan.application.secciones import guardar_seccion  # noqa: E402
from app.modules.care_plan.domain.ficha import CampoFicha, SiNoExiste  # noqa: E402
from app.modules.care_plan.domain.relevo import MotivoAcceso  # noqa: E402
from app.modules.care_plan.domain.secciones import SeccionComplementaria, validar_texto_seccion  # noqa: E402
from app.modules.care_plan.infrastructure.auditoria_ficha import AuditoriaFichaRegistro  # noqa: E402
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm  # noqa: E402
from app.modules.care_plan.infrastructure.credenciales_relevo import GeneradorSecrets, HuellasHmac  # noqa: E402
from app.modules.care_plan.infrastructure.custodia_kek_entorno import (  # noqa: E402
    CustodiaKekEntorno,
    CustodiaNoPermitida,
)
from app.modules.care_plan.infrastructure.efecto_retiro import EfectoRetiroFicha  # noqa: E402
from app.modules.care_plan.infrastructure.repositorio_accesos import RepositorioAccesosSQL  # noqa: E402
from app.modules.care_plan.infrastructure.repositorio_claves import RepositorioClavesSQL  # noqa: E402
from app.modules.care_plan.infrastructure.repositorio_ficha import RepositorioFichaSQL  # noqa: E402
from app.modules.consumption.application import perfiles  # noqa: E402
from app.modules.consumption.application.perfiles import DatosPerfil, PeticionConsumo  # noqa: E402
from app.modules.consumption.infrastructure.efecto_retiro import EfectoRetiroConsumo  # noqa: E402
from app.modules.consumption.infrastructure.repositorio_perfiles import RepositorioPerfilesSQL  # noqa: E402
from app.modules.consumption.infrastructure.tarea_quiebres import recalcular_grupo  # noqa: E402
from app.modules.iam.application.politica import politica_vigente  # noqa: E402
from app.modules.iam.application.ports import HasherContrasenas  # noqa: E402
from app.modules.iam.application.registro import registrar_usuario  # noqa: E402
from app.modules.iam.domain.credenciales import (  # noqa: E402
    LARGO_MAXIMO_CONTRASENA,
    LARGO_MINIMO_CONTRASENA,
    EmailYaRegistrado,
    indice_email,
    normalizar_email,
)
from app.modules.iam.domain.politica import PoliticaNoDisponible, PoliticaVigente  # noqa: E402
from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id  # noqa: E402
from app.modules.iam.infrastructure.repositorio_usuarios import RepositorioUsuariosSQL  # noqa: E402
from app.modules.iam.infrastructure.textos_politica import texto_publicado  # noqa: E402
from app.shared.auditoria_sql import RegistroAuditoriaSql  # noqa: E402
from app.shared.celular import normalizar_celular  # noqa: E402
from app.shared.puertos import Reloj  # noqa: E402
from app.shared.reloj_sistema import RelojSistema  # noqa: E402

# Los nombres de las variables, no sus valores
VARIABLE_CONTRASENA = "SEMILLA_CONTRASENA"  # pragma: allowlist secret
VARIABLE_PIN = "SEMILLA_PIN"

# El único rol con el que la semilla escribe: RLS se aplica a matu_app, no al dueño ni a un superusuario
ROL_ESPERADO = "matu_app"

# Donde quedan el enlace y el PIN del relevo de ejemplo y la contraseña aleatoria. infra/semillas/.gitignore
# ignora la carpeta
CARPETA_SALIDA = Path(__file__).resolve().parent / "salida"
ARCHIVO_RELEVO = CARPETA_SALIDA / "relevo-demo.txt"
ARCHIVO_CONTRASENA = CARPETA_SALIDA / "contrasena-demo.txt"

# Cuánto vale el relevo de ejemplo: alcanza para preparar y dar la demo (el máximo de MATU-18 es 30 días)
VIGENCIA_RELEVO = timedelta(days=7)

HORA_CHILE = ZoneInfo("America/Santiago")

MENSAJE_PRODUCCION = "La semilla de demostración no corre con ENTORNO=produccion."

# --- Los datos, todos sintéticos ----------------------------------------------------------------------


@dataclass(frozen=True)
class CuentaDemo:
    nombre: str
    email: str
    rol: str
    # Celular sintético en E.164, obligatorio desde MATU-39 (decisión 65). Serie +56 9 0000 00xx, sin dueño.
    # Uno distinto por cuenta (MATU-64)
    telefono: str
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
class FichaDemo:
    """Los tres campos de la ficha (su día, si se altera, a quién llamar) y las secciones complementarias."""

    campos: Mapping[CampoFicha, str]
    secciones: Mapping[SeccionComplementaria, str] = field(default_factory=dict)


@dataclass(frozen=True)
class InsumoDemo:
    """Un insumo del catálogo de MATU-59, por su clave en catalogo_demo.py. La tasa y lo que queda deciden si se
    acaba pronto: días que quedan = stock_unidades * tasa_dias / tasa_unidades, y avisa con dias_aviso o menos."""

    producto: str
    tasa_unidades: int
    tasa_dias: int
    stock_unidades: int
    dias_aviso: int
    unidades_por_envase: int | None = None

    def dias_que_quedan(self) -> int:
        return self.stock_unidades * self.tasa_dias // self.tasa_unidades

    def se_acaba_pronto(self) -> bool:
        return self.dias_que_quedan() <= self.dias_aviso


@dataclass(frozen=True)
class RelevoDemo:
    nombre: str
    telefono: str
    motivo: MotivoAcceso
    secciones: tuple[SeccionComplementaria, ...]


@dataclass(frozen=True)
class FamiliaDemo:
    grupo: str
    admin: CuentaDemo
    miembros: tuple[CuentaDemo, ...]
    persona: PersonaDemo
    ficha: FichaDemo
    insumos: tuple[InsumoDemo, ...]
    relevo: RelevoDemo | None = None
    # MATU-61: la autorización de pedidos (despacho), para probar el recorrido 5 en vivo. La semilla no siembra pedidos
    autoriza_pedidos: bool = False


FICHA_MARIA = FichaDemo(
    campos={
        CampoFicha.RUTINA: (
            "08:00 se levanta y toma desayuno en la cocina: té con leche y pan con palta.\n"
            "11:00 sale a caminar a la plaza del frente, siempre acompañada.\n"
            "13:30 almuerza. 15:00 duerme siesta una hora.\n"
            "20:00 ve las noticias y se acuesta a las 22:00 con la luz del pasillo encendida."
        ),
        CampoFicha.MANEJO_SITUACIONES: (
            "Si se angustia en la tarde, ponerle boleros a volumen bajo y conversarle de su jardín.\n"
            "No discutirle: cambiar de tema con calma y ofrecerle un té.\n"
            "Si no quiere comer, esperar diez minutos y ofrecer de nuevo."
        ),
        CampoFicha.RED_APOYO: (
            "Carmen (la cuidadora): +56 9 0000 0001\n"
            "Rodrigo (hijo): +56 9 0000 0003\n"
            "Vecina Ana, casa 5: avisarle si hay que salir de urgencia."
        ),
    },
    secciones={
        SeccionComplementaria.QUIEN_ES: (
            "Fue profesora de música en un colegio de La Reina. Le gusta que la llamen por su nombre."
        ),
        SeccionComplementaria.PREFERENCIAS: "Le gustan los boleros, el jardín y las sopaipillas los días de lluvia.",
        SeccionComplementaria.ALIMENTACION: "Come de todo, en porciones chicas. El té, tibio y con poca azúcar.",
    },
)

FICHA_HERNAN = FichaDemo(
    campos={
        CampoFicha.RUTINA: (
            "07:30 se levanta solo y se prepara el desayuno; hay que mirar que apague la tetera.\n"
            "10:00 lee el diario en el living. 13:00 almuerza.\n"
            "17:00 juega dominó con su vecino los martes y jueves."
        ),
        CampoFicha.MANEJO_SITUACIONES: (
            "Si se pone inquieto en la noche, conversarle de fútbol y acompañarlo a la cocina por un vaso de agua.\n"
            "Prefiere que le pregunten antes de ayudarlo."
        ),
        CampoFicha.RED_APOYO: "Patricia (hija): +56 9 0000 0005\nTomás (nieto): +56 9 0000 0006",
    },
    secciones={
        SeccionComplementaria.QUIEN_ES: "Trabajó cuarenta años en una imprenta. Es hincha de la U.",
        SeccionComplementaria.MOVILIDAD: "Camina con bastón dentro de la casa. En la calle, del brazo.",
    },
)

FAMILIAS: tuple[FamiliaDemo, ...] = (
    FamiliaDemo(
        grupo="Familia Soto",
        admin=CuentaDemo("Carmen Fuentes", "carmen@example.com", "admin", "+56900000001"),
        miembros=(
            CuentaDemo("Luisa Contreras", "luisa@example.org", "cuidador", "+56900000002"),
            CuentaDemo("Rodrigo Soto", "rodrigo@example.com", "pagador", "+56900000003", puede_ver_plan=True),
            CuentaDemo("Javiera Soto", "javiera@example.org", "observador", "+56900000004"),
        ),
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
        ficha=FICHA_MARIA,
        insumos=(
            # Se acaban en 2 días y avisa con 7: «se acaba pronto» y la alerta abierta
            InsumoDemo("panal", tasa_unidades=4, tasa_dias=1, stock_unidades=8, dias_aviso=7, unidades_por_envase=30),
            InsumoDemo("toallitas", tasa_unidades=6, tasa_dias=1, stock_unidades=150, dias_aviso=7,
                       unidades_por_envase=80),
            InsumoDemo("crema", tasa_unidades=5, tasa_dias=1, stock_unidades=90, dias_aviso=7,
                       unidades_por_envase=100),
        ),
        relevo=RelevoDemo(
            nombre="Rosa",
            telefono="+56900000099",
            motivo=MotivoAcceso.FIN_DE_SEMANA_FUERA,
            secciones=(SeccionComplementaria.QUIEN_ES, SeccionComplementaria.PREFERENCIAS),
        ),
        autoriza_pedidos=True,
    ),
    FamiliaDemo(
        grupo="Familia Riquelme",
        admin=CuentaDemo("Patricia Riquelme", "patricia@example.com", "admin", "+56900000005"),
        miembros=(CuentaDemo("Tomás Riquelme", "tomas@example.org", "observador", "+56900000006"),),
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
        ficha=FICHA_HERNAN,
        insumos=(
            # Se acaba en 4 días y avisa con 5
            InsumoDemo("suplemento", tasa_unidades=30, tasa_dias=1, stock_unidades=120, dias_aviso=5,
                       unidades_por_envase=400),
            InsumoDemo("protectores", tasa_unidades=2, tasa_dias=1, stock_unidades=40, dias_aviso=7,
                       unidades_por_envase=20),
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
class RelevoSembrado:
    """El relevo de ejemplo. ``entregado`` trae el token y el PIN solo si se creó en esta corrida."""

    acceso_id: uuid.UUID
    grupo: str
    nombre_relevo: str
    expira_en: datetime
    entregado: AccesoEntregado | None = field(default=None, repr=False)


@dataclass(frozen=True)
class FamiliaSembrada:
    grupo_id: uuid.UUID
    usuarios: tuple[uuid.UUID, ...]
    persona_id: uuid.UUID
    persona_creada: bool
    campos_escritos: int = 0
    secciones_escritas: int = 0
    insumos_creados: int = 0
    relevo: RelevoSembrado | None = None


@dataclass(frozen=True)
class SemillaSembrada:
    familias: list[FamiliaSembrada]
    cuentas: list[CuentaSembrada]
    alertas_creadas: int = 0


class SemillaInconsistente(RuntimeError):
    """Lo que ya existe en la base no calza con la semilla. El mensaje nunca lleva emails ni nombres."""


class GeneradorCredencialesDemo:
    """El puerto GeneradorCredencialesRelevo de la semilla: el token del adaptador real y, si se pidió, el PIN
    conocido de la demo (SEMILLA_PIN). Sin PIN, el del adaptador real."""

    def __init__(self, pin: str | None) -> None:
        self._real = GeneradorSecrets()
        self._pin = pin

    def __repr__(self) -> str:
        return "GeneradorCredencialesDemo(pin=****)"

    def token(self) -> bytes:
        return self._real.token()

    def pin(self) -> str:
        return self._pin if self._pin is not None else self._real.pin()


_MEMBRESIA = text("SELECT rol, puede_ver_plan FROM membresia WHERE grupo_id = :grupo_id AND usuario_id = :usuario_id")
_INSERTAR_MEMBRESIA = text(
    "INSERT INTO membresia (grupo_id, usuario_id, rol, puede_ver_plan, invitado_por)"
    " VALUES (:grupo_id, :usuario_id, :rol, :puede_ver_plan, :invitado_por)"
)
_TELEFONO = text("SELECT telefono FROM usuario WHERE id = :id")
# El trigger usuario_celular_cambia (0012) deja el celular sin verificar
_CAMBIAR_TELEFONO = text("UPDATE usuario SET telefono = :telefono, actualizado_en = now() WHERE id = :id")
_RELEVO_VIGENTE = text(
    "SELECT a.id, a.expira_en FROM acceso_relevo a JOIN plan_cuidado p ON p.id = a.plan_id"
    " WHERE a.grupo_id = :grupo_id AND p.persona_cuidada_id = :persona_id AND a.otorgado_a_nombre = :nombre"
    " AND a.revocado_en IS NULL AND a.expira_en > :ahora ORDER BY a.creado_en DESC LIMIT 1"
)


@dataclass
class Sembradora:
    fabrica: sessionmaker[Session]
    pepper: bytes
    version_politica: str
    reloj: Reloj
    hasher: HasherContrasenas
    # La custodia de la KEK de la ficha (CustodiaKekEntorno; en las pruebas, la misma con una KEK de prueba)
    custodia: CustodiaClaves
    # PEPPER_PIN: el HMAC del PIN del relevo, el mismo de la API
    pepper_pin: bytes
    # MATU-75: la política vigente, que cada cuenta nueva acepta al crearse
    politica: PoliticaVigente
    # SEMILLA_PIN, o None para uno aleatorio
    pin_relevo: str | None = field(default=None, repr=False)
    # Cuántas cuentas creó: si la siembra se corta a medias, main igual muestra su contraseña
    cuentas_creadas: int = 0
    # Recibe el relevo recién creado apenas se confirma su transacción: main lo guarda en el archivo, así el enlace
    # y el PIN quedan aunque la corrida se detenga después
    al_crear_relevo: Callable[["RelevoSembrado"], None] | None = field(default=None, repr=False)

    # --- Cuentas, grupo, membresías y persona (MATU-30) ---------------------------------------------------

    def cuenta(self, cuenta: CuentaDemo, contrasena: str) -> tuple[uuid.UUID, bool]:
        """Registra la cuenta (MATU-04). Si el email ya tiene cuenta, devuelve la existente con el celular de la
        semilla."""
        repositorio = RepositorioUsuariosSQL(self.fabrica)
        try:
            creada = registrar_usuario(
                nombre=cuenta.nombre,
                email=cuenta.email,
                contrasena=contrasena,
                telefono=cuenta.telefono,
                pepper=self.pepper,
                hasher=self.hasher,
                repositorio=repositorio,
                # MATU-75: acepta la política vigente por el camino normal, como la casilla de «Crear cuenta»
                politica=self.politica,
                ahora=self.reloj.ahora(),
                # La huella que la casilla mostró, como la envía la web (decisión 182)
                huella_mostrada=self.politica.huella,
                # Los correos de la semilla son de dominios reservados: así también sirve en staging, que
                # rechaza los demás (decisión 105)
                solo_dominios_reservados=True,
            )
            self.cuentas_creadas += 1
            return creada.id, True
        except EmailYaRegistrado:
            existente = repositorio.buscar_credencial(indice_email(self.pepper, normalizar_email(cuenta.email)))
            if existente is None:
                raise SemillaInconsistente(
                    "Una cuenta de la semilla existe pero no se encuentra con este PEPPER_EMAIL"
                ) from None
            self._celular(existente.usuario_id, cuenta.telefono)
            return existente.usuario_id, False

    def _celular(self, usuario_id: uuid.UUID, telefono: str) -> None:
        """MATU-64: una cuenta de una semilla anterior pasa a su propio celular, en su propio contexto."""
        with sesion_tenant(self.fabrica, usuario_id=usuario_id) as sesion:
            actual = sesion.execute(_TELEFONO, {"id": usuario_id}).scalar_one_or_none()
            if actual != telefono:
                sesion.execute(_CAMBIAR_TELEFONO, {"id": usuario_id, "telefono": telefono})

    def grupo(self, admin_id: uuid.UUID, nombre: str) -> uuid.UUID:
        """El grupo con ese nombre donde la cuenta es admin, o uno nuevo (MATU-06)."""
        existente = self.grupo_existente(admin_id, nombre)
        if existente is not None:
            return existente
        return crear_grupo(admin_id, nombre, RepositorioGruposSQL(self.fabrica)).id

    def grupo_existente(self, admin_id: uuid.UUID, nombre: str) -> uuid.UUID | None:
        for grupo in listar_grupos(admin_id, RepositorioGruposSQL(self.fabrica)):
            if grupo.nombre == nombre and grupo.rol == "admin":
                return grupo.id
        return None

    def _contexto_admin(self, admin_id: uuid.UUID, grupo_id: uuid.UUID) -> AbstractContextManager[Session]:
        """La transacción del admin en su grupo, como sesion_de_grupo: verifica que siga siendo admin."""
        return _contexto_admin(self.fabrica, admin_id, grupo_id)

    def membresia(self, admin_id: uuid.UUID, grupo_id: uuid.UUID, usuario_id: uuid.UUID, cuenta: CuentaDemo) -> None:
        """La membresía del miembro, escrita como matu_app en el contexto del admin y su grupo.

        Reemplaza a la invitación, que aún no existe. Si ya hay una con otro rol, se detiene.
        """
        with self._contexto_admin(admin_id, grupo_id) as sesion:
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

    def persona(self, admin_id: uuid.UUID, grupo_id: uuid.UUID, persona: PersonaDemo) -> tuple[uuid.UUID, bool]:
        """Da de alta a la persona con su autorización para la ficha (MATU-07), si el grupo no la tiene ya."""
        with self._contexto_admin(admin_id, grupo_id) as sesion:
            repositorio = RepositorioPersonasSQL(sesion, grupo_id)
            for existente in listar_personas("admin", repositorio):
                if existente.nombre == persona.nombre:
                    return existente.id, False
            solicitud = SolicitudAlta(
                usuario_id=admin_id,
                grupo_id=grupo_id,
                rol="admin",
                nombre=persona.nombre,
                nombre_pila=persona.nombre_pila,
                nivel_apoyo=persona.nivel_apoyo,
                calidad_otorgante=persona.calidad,
                referencia_documento=persona.referencia_documento,
                aviso=_aviso(persona.calidad),
                direccion=persona.direccion,
            )
            return dar_de_alta(solicitud, self.version_politica, self.reloj, repositorio).alta.persona_id, True

    # --- Autorización de consumo, ficha, insumos y relevo (MATU-64) ---------------------------------------

    def autorizacion_consumo(
        self, admin_id: uuid.UUID, grupo_id: uuid.UUID, persona_id: uuid.UUID, persona: PersonaDemo
    ) -> bool:
        """La autorización para calcular los insumos (MATU-36), si no hay una vigente. True si la dio ahora."""
        with self._contexto_admin(admin_id, grupo_id) as sesion:
            registro = RegistroAuditoriaSql(sesion, self.reloj)
            repositorio = RepositorioAutorizacionesSQL(sesion, grupo_id, registro)
            if repositorio.hay_vigente(persona_id, FINALIDAD_CONSUMO):
                return False
            otorgar_autorizacion(
                SolicitudAutorizacion(
                    usuario_id=admin_id,
                    grupo_id=grupo_id,
                    rol="admin",
                    persona_id=persona_id,
                    calidad_otorgante=persona.calidad,
                    referencia_documento=persona.referencia_documento,
                    aviso=_aviso(persona.calidad),
                    finalidad=FINALIDAD_CONSUMO,
                ),
                self.version_politica,
                self.reloj,
                repositorio,
            )
            return True

    def autorizacion_pedidos(
        self, admin_id: uuid.UUID, grupo_id: uuid.UUID, persona_id: uuid.UUID, persona: PersonaDemo
    ) -> bool:
        """La autorización de pedidos (despacho, MATU-61 D1), con la huella de su declaración, si no hay una vigente.
        True si la dio ahora. Solo otorga el consentimiento: no siembra pedidos (el recorrido 5 se arma en vivo)."""
        with self._contexto_admin(admin_id, grupo_id) as sesion:
            registro = RegistroAuditoriaSql(sesion, self.reloj)
            repositorio = RepositorioAutorizacionesSQL(sesion, grupo_id, registro)
            if repositorio.hay_vigente(persona_id, FINALIDAD_DESPACHO):
                return False
            otorgar_autorizacion(
                SolicitudAutorizacion(
                    usuario_id=admin_id,
                    grupo_id=grupo_id,
                    rol="admin",
                    persona_id=persona_id,
                    calidad_otorgante=persona.calidad,
                    referencia_documento=persona.referencia_documento,
                    aviso=_aviso(persona.calidad),
                    finalidad=FINALIDAD_DESPACHO,
                    huella_declaracion=huella_declaracion_pedidos(persona.calidad),
                ),
                self.version_politica,
                self.reloj,
                repositorio,
            )
            return True

    def _exigir_vigente(self, sesion: Session, grupo_id: uuid.UUID, persona_id: uuid.UUID, finalidad: str) -> None:
        """Como la API (403 sin autorización): sin una vigente para la finalidad, la semilla no escribe nada."""
        encontrada = persona_con_autorizacion(sesion, grupo_id, persona_id, finalidad, bloquear=True)
        if encontrada is None or estado_autorizacion(encontrada.autorizacion, self.reloj.ahora()) is not (
            EstadoAutorizacion.VIGENTE
        ):
            raise SemillaInconsistente(f"La persona de la semilla no tiene una autorización vigente para {finalidad}")

    def ficha(
        self, admin_id: uuid.UUID, grupo_id: uuid.UUID, persona_id: uuid.UUID, ficha: FichaDemo
    ) -> tuple[int, int]:
        """Escribe los campos y las secciones que faltan, cifrados (MATU-12 y MATU-50), con If-None-Match: *.

        Lo que ya está escrito no se toca ni se lee: así una segunda corrida no deja un plan.leer. Devuelve
        cuántos campos y cuántas secciones escribió.
        """
        with self._contexto_admin(admin_id, grupo_id) as sesion:
            self._exigir_vigente(sesion, grupo_id, persona_id, FINALIDAD_PLAN_CUIDADO)
            registro = RegistroAuditoriaSql(sesion, self.reloj)
            fichas = RepositorioFichaSQL(sesion, grupo_id)
            cifrador = CifradorAesGcm(self.custodia, RepositorioClavesSQL(sesion))
            auditoria = AuditoriaFichaRegistro(sesion, registro)
            peticion = PeticionFicha(grupo_id=grupo_id, usuario_id=admin_id, persona_cuidada_id=persona_id)
            plan = fichas.obtener_plan(persona_id)
            campos = secciones = 0
            for campo, texto in ficha.campos.items():
                if plan is not None and fichas.seccion(plan.id, campo.value) is not None:
                    continue
                # El mismo esquema del PUT: largo, caracteres de control y normalización
                valido = SolicitudCampo(texto=texto).texto
                guardar_campo(peticion, campo, valido, SiNoExiste(), fichas, cifrador, auditoria, self.reloj)
                plan = fichas.obtener_plan(persona_id)
                campos += 1
            for seccion, texto in ficha.secciones.items():
                if plan is not None and fichas.seccion(plan.id, seccion.value) is not None:
                    continue
                normalizado = validar_texto_seccion(seccion, texto)
                guardar_seccion(peticion, seccion, normalizado, SiNoExiste(), fichas, cifrador, auditoria, self.reloj)
                plan = fichas.obtener_plan(persona_id)
                secciones += 1
            return campos, secciones

    def insumos(
        self,
        admin_id: uuid.UUID,
        grupo_id: uuid.UUID,
        persona_id: uuid.UUID,
        insumos: Sequence[InsumoDemo],
        productos: Mapping[str, uuid.UUID],
    ) -> int:
        """Anota los insumos que la persona aún no sigue (MATU-36). Devuelve cuántos anotó."""
        with self._contexto_admin(admin_id, grupo_id) as sesion:
            self._exigir_vigente(sesion, grupo_id, persona_id, FINALIDAD_CONSUMO)
            repositorio = RepositorioPerfilesSQL(sesion, grupo_id)
            registro = RegistroAuditoriaSql(sesion, self.reloj)
            peticion = PeticionConsumo(grupo_id=grupo_id, usuario_id=admin_id, persona_id=persona_id)
            creados = 0
            for insumo in insumos:
                producto_id = productos[insumo.producto]
                if repositorio.hay_activo_del_producto(persona_id, producto_id, salvo=None):
                    continue
                perfiles.crear(
                    peticion,
                    DatosPerfil(
                        producto_id=producto_id,
                        nombre_libre=None,
                        unidad=None,
                        tasa_unidades=insumo.tasa_unidades,
                        tasa_dias=insumo.tasa_dias,
                        stock_unidades=insumo.stock_unidades,
                        dias_aviso=insumo.dias_aviso,
                        unidades_por_envase=insumo.unidades_por_envase,
                    ),
                    self.reloj,
                    repositorio,
                    registro,
                )
                creados += 1
            return creados

    def relevo(
        self, admin_id: uuid.UUID, grupo_id: uuid.UUID, persona_id: uuid.UUID, grupo: str, relevo: RelevoDemo
    ) -> RelevoSembrado:
        """El acceso de relevo de ejemplo (MATU-18). Si ya hay uno vigente con ese nombre, lo deja como está: su
        enlace y su PIN no se pueden volver a mostrar (la base guarda solo sus huellas)."""
        telefono = normalizar_celular(relevo.telefono)
        if telefono is None:
            raise SemillaInconsistente("El celular del relevo de ejemplo no es un celular chileno")
        with self._contexto_admin(admin_id, grupo_id) as sesion:
            self._exigir_vigente(sesion, grupo_id, persona_id, FINALIDAD_PLAN_CUIDADO)
            ahora = self.reloj.ahora()
            vigente = sesion.execute(
                _RELEVO_VIGENTE,
                {"grupo_id": grupo_id, "persona_id": persona_id, "nombre": relevo.nombre, "ahora": ahora},
            ).first()
            if vigente is not None:
                return RelevoSembrado(
                    acceso_id=vigente.id, grupo=grupo, nombre_relevo=relevo.nombre, expira_en=vigente.expira_en
                )
            registro = RegistroAuditoriaSql(sesion, self.reloj)
            entregado = compartir(
                PeticionFicha(grupo_id=grupo_id, usuario_id=admin_id, persona_cuidada_id=persona_id),
                SolicitudCompartir(
                    nombre_relevo=relevo.nombre,
                    telefono_relevo=telefono,
                    secciones=relevo.secciones,
                    motivo=relevo.motivo,
                    expira_en=ahora + VIGENCIA_RELEVO,
                ),
                RepositorioFichaSQL(sesion, grupo_id),
                RepositorioAccesosSQL(sesion, grupo_id, registro),
                GeneradorCredencialesDemo(self.pin_relevo),
                HuellasHmac(self.pepper_pin),
                self.reloj,
            )
        # Fuera del with: la transacción ya se confirmó
        creado = RelevoSembrado(
            acceso_id=entregado.id,
            grupo=grupo,
            nombre_relevo=relevo.nombre,
            expira_en=entregado.expira_en,
            entregado=entregado,
        )
        if self.al_crear_relevo is not None:
            self.al_crear_relevo(creado)
        return creado

    def alertas(self, grupo_id: uuid.UUID) -> int:
        """El trabajo diario de MATU-37 para este grupo, ahora: deja la alerta abierta sin esperar a las 04:00.
        Una segunda corrida no crea otra (alerta_quiebre_uq)."""
        return recalcular_grupo(self.fabrica, grupo_id, self.reloj).materializadas

    def capa_3(self, familias: Sequence[FamiliaSembrada]) -> None:
        """Recorridos 5 (pedido y pago) y 6 (retiro en el comercio): llegan con MATU-61 a 63. Aquí se sembrarán
        un pedido de ejemplo y su retiro, por los casos de uso de ordering, payments y fulfillment."""

    # --- La familia completa ------------------------------------------------------------------------------

    def familia(
        self, familia: FamiliaDemo, contrasena: str, productos: Mapping[str, uuid.UUID]
    ) -> tuple[FamiliaSembrada, list[CuentaSembrada]]:
        admin_id, admin_creada = self.cuenta(familia.admin, contrasena)
        grupo_id = self.grupo(admin_id, familia.grupo)
        cuentas = [_sembrada(familia, familia.admin, admin_creada)]
        usuarios = [admin_id]
        for miembro in familia.miembros:
            usuario_id, creada = self.cuenta(miembro, contrasena)
            self.membresia(admin_id, grupo_id, usuario_id, miembro)
            cuentas.append(_sembrada(familia, miembro, creada))
            usuarios.append(usuario_id)
        persona_id, persona_creada = self.persona(admin_id, grupo_id, familia.persona)
        self.autorizacion_consumo(admin_id, grupo_id, persona_id, familia.persona)
        if familia.autoriza_pedidos:
            self.autorizacion_pedidos(admin_id, grupo_id, persona_id, familia.persona)
        campos, secciones = self.ficha(admin_id, grupo_id, persona_id, familia.ficha)
        insumos = self.insumos(admin_id, grupo_id, persona_id, familia.insumos, productos)
        relevo = None
        if familia.relevo is not None:
            relevo = self.relevo(admin_id, grupo_id, persona_id, familia.grupo, familia.relevo)
        sembrada = FamiliaSembrada(
            grupo_id=grupo_id,
            usuarios=tuple(usuarios),
            persona_id=persona_id,
            persona_creada=persona_creada,
            campos_escritos=campos,
            secciones_escritas=secciones,
            insumos_creados=insumos,
            relevo=relevo,
        )
        return sembrada, cuentas

    # --- Restablecer ----------------------------------------------------------------------------------------

    def vaciar(self, familia: FamiliaDemo) -> int:
        """Borra al tiro a cada persona del grupo de la familia con el caso de uso de MATU-72, en el contexto del
        admin: corta sus enlaces, destruye su clave y borra su ficha, sus insumos y sus alertas. Si la cuenta o el
        grupo no existen, no hay nada que borrar. Devuelve cuántas personas borró."""
        repositorio = RepositorioUsuariosSQL(self.fabrica)
        credencial = repositorio.buscar_credencial(indice_email(self.pepper, normalizar_email(familia.admin.email)))
        if credencial is None:
            return 0
        admin_id = credencial.usuario_id
        grupo_id = self.grupo_existente(admin_id, familia.grupo)
        if grupo_id is None:
            return 0
        with self._contexto_admin(admin_id, grupo_id) as sesion:
            personas = [p.id for p in listar_personas("admin", RepositorioPersonasSQL(sesion, grupo_id))]
        for persona_id in personas:
            with self._contexto_admin(admin_id, grupo_id) as sesion:
                registro = RegistroAuditoriaSql(sesion, self.reloj)
                efectos: dict[str, EfectoDelRetiro] = {
                    FINALIDAD_PLAN_CUIDADO: EfectoRetiroFicha(sesion, grupo_id, registro),
                    FINALIDAD_CONSUMO: EfectoRetiroConsumo(sesion, grupo_id, registro),
                }
                capa3 = obtener_configuracion().capa3_habilitada
                if capa3:
                    # MATU-61 (D2): los pedidos sin pagar armados en vivo se cancelan con el borrado. Capa 3: se importa
                    # solo encendida, como en app.main
                    pedidos = importlib.import_module("app.modules.ordering.infrastructure.efecto_retiro")
                    efectos[FINALIDAD_DESPACHO] = pedidos.EfectoRetiroPedidos(sesion, grupo_id, registro)
                borrar_persona(
                    SolicitudBorrado(usuario_id=admin_id, rol="admin", persona_id=persona_id),
                    self.reloj,
                    RepositorioBorradoSQL(sesion, grupo_id, registro),
                    RepositorioRetirosSQL(sesion, grupo_id, registro),
                    efectos,
                    finalidades_retirables(capa3),
                )
        return len(personas)


@contextmanager
def _contexto_admin(fabrica: sessionmaker[Session], admin_id: uuid.UUID, grupo_id: uuid.UUID) -> Iterator[Session]:
    """sesion_tenant con el admin y su grupo, y la comprobación de sesion_de_grupo: sigue siendo admin activo."""
    with sesion_tenant(fabrica, usuario_id=admin_id, grupo_id=grupo_id) as sesion:
        if rol_activo(sesion, admin_id, grupo_id) != "admin":
            raise SemillaInconsistente("El admin de la semilla no es admin activo de su grupo")
        yield sesion


def _aviso(calidad: CalidadOtorgante) -> AvisoMostrado | None:
    # La semilla declara haber mostrado el aviso vigente del cuidador de hecho, como lo haría la pantalla
    if calidad is CalidadOtorgante.CUIDADOR_DE_HECHO:
        return AvisoMostrado(id=AVISO_CUIDADOR_DE_HECHO.id, version=AVISO_CUIDADOR_DE_HECHO.version)
    return None


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
    sembradora: Sembradora,
    contrasena: str,
    productos: Mapping[str, uuid.UUID],
    familias: Sequence[FamiliaDemo] = FAMILIAS,
) -> SemillaSembrada:
    """Siembra las familias. ``productos`` son los ids del catálogo sembrado (CatalogoSembrado.productos)."""
    familias_sembradas: list[FamiliaSembrada] = []
    cuentas: list[CuentaSembrada] = []
    for familia in familias:
        sembrada, suyas = sembradora.familia(familia, contrasena, productos)
        familias_sembradas.append(sembrada)
        cuentas.extend(suyas)
    # Al final, con todos los insumos ya anotados: el trabajo diario solo de los grupos de la semilla
    alertas = sum(sembradora.alertas(f.grupo_id) for f in familias_sembradas)
    sembradora.capa_3(familias_sembradas)
    return SemillaSembrada(familias=familias_sembradas, cuentas=cuentas, alertas_creadas=alertas)


def restablecer(sembradora: Sembradora, familias: Sequence[FamiliaDemo] = FAMILIAS) -> int:
    """Vacía las familias de la semilla (Sembradora.vaciar). Después se vuelve a sembrar. Devuelve cuántas
    personas borró."""
    return sum(sembradora.vaciar(familia) for familia in familias)


def rol_de_la_conexion(fabrica: sessionmaker[Session]) -> str:
    """El rol con el que DATABASE_URL entra a la base (SELECT current_user)."""
    with fabrica() as sesion:
        return str(sesion.execute(text("SELECT current_user")).scalar_one())


# --- Línea de comandos -----------------------------------------------------------------------------------


def cargar_catalogo_demo() -> ModuleType:
    """La semilla del catálogo (MATU-59), hermana de este archivo. Se carga por ruta: infra/ no es un paquete."""
    ruta = Path(__file__).resolve().parent / "catalogo_demo.py"
    spec = importlib.util.spec_from_file_location("semilla_catalogo_demo", ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Registrado antes de ejecutarlo: dataclasses busca el módulo de cada clase en sys.modules
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def sembrar_catalogo_demo(fabrica: sessionmaker[Session]) -> Any:
    """Siembra el catálogo de MATU-59 y devuelve lo sembrado (CatalogoSembrado de catalogo_demo.py)."""
    return cargar_catalogo_demo().sembrar_catalogo(fabrica)


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


def _pin() -> str | None:
    """SEMILLA_PIN (4 dígitos), o None para que el PIN del relevo sea aleatorio. El valor nunca se imprime aquí."""
    valor = os.environ.get(VARIABLE_PIN, "")
    if not valor:
        return None
    if re.fullmatch(r"\d{4}", valor) is None:
        raise SystemExit(f"{VARIABLE_PIN} debe tener 4 dígitos.")
    return valor


def _custodia() -> CustodiaClaves | None:
    """La custodia de la KEK de la configuración, la misma de la API. None si no está encendida."""
    config = obtener_configuracion()
    if config.custodia_kek != "entorno_sintetico" or config.kek_entorno is None:
        return None
    return CustodiaKekEntorno(config.kek_entorno, kek_version=config.kek_version, entorno=config.entorno)


def _escribir_privado(archivo: Path, contenido: str) -> None:
    """Escribe ``contenido`` en ``archivo`` (de infra/semillas/salida/, que git ignora) con permisos solo para el
    dueño si el sistema lo permite. En Windows chmod solo cambia el atributo de solo lectura."""
    archivo.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(archivo, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as salida:
        salida.write(contenido)
    try:
        archivo.chmod(0o600)
    except OSError:  # pragma: no cover - depende del sistema de archivos
        pass


def enlace_relevo(relevo: RelevoSembrado, origen_web: str) -> str:
    assert relevo.entregado is not None
    return f"{origen_web}/r#{relevo.entregado.token}"


def guardar_relevo(
    relevo: RelevoSembrado, origen_web: str, archivo: Path = ARCHIVO_RELEVO, *, pin_de_entorno: bool = False
) -> str:
    """Escribe el enlace del relevo recién creado en ``archivo`` (ignorado por git). Devuelve el enlace.

    El PIN se escribe solo si es aleatorio, porque el archivo es la única forma de conocerlo. Si viene de
    SEMILLA_PIN (``pin_de_entorno``), el equipo ya lo conoce: el archivo dice que es ese, sin escribirlo."""
    assert relevo.entregado is not None
    enlace = enlace_relevo(relevo, origen_web)
    linea_pin = (
        f"pin: el de la variable {VARIABLE_PIN} (no se escribe aquí)\n"
        if pin_de_entorno
        else f"pin: {relevo.entregado.pin}\n"
    )
    _escribir_privado(
        archivo,
        "Relevo de ejemplo de la demo de MATU. Datos sintéticos. No subir a git ni compartir fuera del equipo.\n"
        f"acceso: {relevo.acceso_id}\n"
        f"grupo: {relevo.grupo}\n"
        f"relevo: {relevo.nombre_relevo}\n"
        f"vence: {relevo.expira_en.isoformat()}\n"
        f"enlace: {enlace}\n" + linea_pin,
    )
    return enlace


def guardar_contrasena(contrasena: str, creadas: int, archivo: Path = ARCHIVO_CONTRASENA) -> None:
    """Escribe la contraseña aleatoria de las cuentas creadas en ``archivo`` (ignorado por git)."""
    _escribir_privado(
        archivo,
        "Contraseña de las cuentas de la demo de MATU creadas en la última corrida que creó cuentas. Datos"
        " sintéticos. No subir a git ni compartir fuera del equipo.\n"
        f"cuentas creadas: {creadas}\n"
        f"contrasena: {contrasena}\n",
    )


def _contrasena_de_las_creadas(creadas: int, contrasena: str, desde_entorno: bool, mostrar: bool) -> None:
    """Dónde quedó la contraseña de las cuentas creadas en esta corrida, también si la siembra se cortó a medias.
    Solo con --mostrar-credenciales sale el valor."""
    if creadas == 0:
        print("No se creó ninguna cuenta.\n")
    elif desde_entorno:
        print(f"Contraseña de las {creadas} cuentas creadas: la de {VARIABLE_CONTRASENA}.\n")
    else:
        guardar_contrasena(contrasena, creadas, ARCHIVO_CONTRASENA)
        print(f"Contraseña aleatoria de las {creadas} cuentas creadas: en {ARCHIVO_CONTRASENA}.")
        if mostrar:
            print(f"  contraseña: {contrasena}")
        print()


def _relevo_creado(relevo: RelevoSembrado, origen_web: str, mostrar: bool, pin_de_entorno: bool = False) -> None:
    """Guarda el relevo recién creado y dice dónde quedó. Solo con --mostrar-credenciales salen el enlace y, si es
    aleatorio, el PIN. El PIN de SEMILLA_PIN nunca se imprime ni se escribe: el equipo ya lo conoce."""
    enlace = guardar_relevo(relevo, origen_web, ARCHIVO_RELEVO, pin_de_entorno=pin_de_entorno)
    assert relevo.entregado is not None
    vence = (
        f"Relevo de ejemplo ({relevo.grupo}, para {relevo.nombre_relevo}), vence el "
        f"{relevo.expira_en.astimezone(HORA_CHILE):%d/%m/%Y %H:%M} (hora de Chile)."
    )
    if pin_de_entorno:
        print(f"{vence} Su enlace: en {ARCHIVO_RELEVO}. Su PIN: el de {VARIABLE_PIN}.")
    else:
        print(f"{vence} Su enlace y su PIN: en {ARCHIVO_RELEVO}.")
    if mostrar:
        print(f"  enlace: {enlace}")
        print(f"  PIN: el de {VARIABLE_PIN}" if pin_de_entorno else f"  PIN: {relevo.entregado.pin}")


def _argumentos(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semilla de demostración de MATU (datos sintéticos).")
    parser.add_argument(
        "--restablecer",
        action="store_true",
        help="borra lo de las dos familias de la semilla (personas, fichas, insumos, alertas y relevos) y vuelve a"
        " sembrar. Las cuentas y los grupos quedan, con su contraseña: no la cambia",
    )
    parser.add_argument(
        "--mostrar-credenciales",
        action="store_true",
        help="imprime en la terminal el PIN y el enlace del relevo y la contraseña aleatoria, además de guardarlos en"
        " infra/semillas/salida/. El PIN de SEMILLA_PIN no se imprime nunca. Solo en una sesión railway ssh o local:"
        " nunca donde la salida quede en un log",
    )
    return parser.parse_args(argv)


def _entorno_declarado() -> str | None:
    """ENTORNO como lo declara el entorno o el .env, sin validar el resto de la configuración. Lee solo esa clave y
    nunca la muestra: sirve para responder con el mensaje de siempre cuando la configuración no carga."""
    if valor := os.environ.get("ENTORNO"):
        return valor
    archivo = Configuracion.model_config.get("env_file")
    if not isinstance(archivo, (str, Path)) or not Path(archivo).is_file():
        return None
    return dotenv_values(archivo).get("ENTORNO")


def main(argv: Sequence[str] = ()) -> int:
    argumentos = _argumentos(argv)
    mostrar = bool(argumentos.mostrar_credenciales)
    try:
        configuracion = obtener_configuracion()
    except ValidationError:
        # Sin el texto del error: pydantic incluye los valores que rechaza. Con ENTORNO=produccion, por ejemplo, la
        # KEK en variable de entorno no se admite y la configuración no carga: es el mismo «no corre en producción»
        if _entorno_declarado() == "produccion":
            print(MENSAJE_PRODUCCION, file=sys.stderr)
        else:
            print(
                "La configuración del .env no es válida y la semilla no corre. Revísala como para la API: este mensaje"
                " no muestra sus valores.",
                file=sys.stderr,
            )
        return 2
    if configuracion.entorno == "produccion":
        print(MENSAJE_PRODUCCION, file=sys.stderr)
        return 2
    if configuracion.pepper_email is None:
        print("Falta PEPPER_EMAIL en el .env: sin él las cuentas no sirven para iniciar sesión.", file=sys.stderr)
        return 2
    if configuracion.pepper_pin is None:
        print("Falta PEPPER_PIN en el .env: sin él no se puede crear el relevo de ejemplo.", file=sys.stderr)
        return 2
    try:
        custodia = _custodia()
    except CustodiaNoPermitida:
        custodia = None
    if custodia is None:
        print(
            "La ficha de ejemplo necesita CUSTODIA_KEK=entorno_sintetico y KEK_ENTORNO en el .env, como la API.",
            file=sys.stderr,
        )
        return 2
    assert configuracion.politica_version is not None  # la configuración la exige fuera de pruebas
    try:
        politica = politica_vigente(
            version=configuracion.politica_version,
            actualizada_en=configuracion.politica_actualizada_en,
            correo=configuracion.correo_privacidad,
            texto_de=texto_publicado,
        )
    except PoliticaNoDisponible as error:
        # El motivo nombra la variable que falta, nunca un valor
        print(f"Las cuentas aceptan la política de privacidad, y no está disponible: {error.motivo}.", file=sys.stderr)
        return 2

    # Antes de escribir nada: la semilla solo corre como matu_app, para que RLS se aplique igual que
    # en la API. Los mensajes nunca muestran DATABASE_URL ni el texto del error del driver.
    fabrica = fabrica_sesiones()
    try:
        rol = rol_de_la_conexion(fabrica)
    except SQLAlchemyError:
        print("No se pudo conectar a la base con DATABASE_URL. Revisa que esté levantada y migrada.", file=sys.stderr)
        return 1
    if rol != ROL_ESPERADO:
        print(
            f"La semilla solo corre conectada como {ROL_ESPERADO}, y DATABASE_URL entra como otro rol. "
            "Corrige DATABASE_URL en el .env: nunca el dueño de la base ni un superusuario.",
            file=sys.stderr,
        )
        return 2

    contrasena, desde_entorno = _contrasena()
    pin_relevo = _pin()
    sembradora = Sembradora(
        fabrica=fabrica,
        pepper=configuracion.pepper_email.get_secret_value().encode("utf-8"),
        version_politica=configuracion.politica_version,
        reloj=RelojSistema(),
        hasher=HasherArgon2id(),
        custodia=custodia,
        pepper_pin=configuracion.pepper_pin.get_secret_value().encode("utf-8"),
        politica=politica,
        pin_relevo=pin_relevo,
        al_crear_relevo=lambda relevo: _relevo_creado(
            relevo, configuracion.origen_web, mostrar, pin_de_entorno=pin_relevo is not None
        ),
    )
    print(f"Semilla de demostración (ENTORNO={configuracion.entorno}).\n")
    try:
        if argumentos.restablecer:
            borradas = restablecer(sembradora)
            ARCHIVO_RELEVO.unlink(missing_ok=True)
            print(f"Restablecer: {borradas} personas cuidadas borradas con sus fichas, insumos, alertas y relevos.\n")
        # MATU-59: el catálogo curado primero, porque los insumos se anotan con sus productos
        catalogo = sembrar_catalogo_demo(fabrica)
        resultado = sembrar(sembradora, contrasena, catalogo.productos)
    except SemillaInconsistente as error:
        print(f"No se pudo sembrar: {error}.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        # Sin el texto del error: puede traer valores de la sentencia
        print(
            "La base rechazó una escritura de la semilla. Revisa que esté migrada (alembic upgrade head).",
            file=sys.stderr,
        )
        return 1
    finally:
        _contrasena_de_las_creadas(sembradora.cuentas_creadas, contrasena, desde_entorno, mostrar)

    for c in resultado.cuentas:
        permiso = ", ve el plan" if c.puede_ver_plan else ""
        estado = "creada" if c.creada else "ya existía, conserva su contraseña"
        print(f"  {c.grupo:<18} {c.nombre:<18} {c.rol + permiso:<20} {c.email:<24} {estado}")

    familias = resultado.familias
    print(
        f"\nCatálogo: {len(catalogo.productos)} productos y {len(catalogo.ofertas)} ofertas de "
        f"{len(catalogo.comercios)} comercios ficticios, con precios de ejemplo."
    )
    print(f"Personas cuidadas dadas de alta ahora: {sum(f.persona_creada for f in familias)} de {len(familias)}.")
    print(
        f"Ficha de relevo: {sum(f.campos_escritos for f in familias)} campos y "
        f"{sum(f.secciones_escritas for f in familias)} secciones escritas ahora, cifradas."
    )
    print(
        f"Insumos anotados ahora: {sum(f.insumos_creados for f in familias)}. "
        f"Alertas de «se acaba pronto» creadas ahora: {resultado.alertas_creadas}."
    )
    for f in familias:
        if f.relevo is None:
            continue
        if f.relevo.entregado is None:
            print(
                f"\nRelevo de ejemplo ({f.relevo.grupo}): ya existía y sigue vigente. Su enlace y su PIN están en "
                f"{ARCHIVO_RELEVO} si se creó en este equipo; si no, --restablecer crea uno nuevo."
            )
    print(
        "\nListo para probar los recorridos 1 a 4: cuenta, persona, autorización y ficha; compartir con un relevo y"
        " cortar el acceso; insumos y aviso de que se acaba; lista de insumos y anotar una compra."
        "\nLos recorridos 5 y 6 (pedido, pago y retiro) llegan con MATU-61 a 63."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
