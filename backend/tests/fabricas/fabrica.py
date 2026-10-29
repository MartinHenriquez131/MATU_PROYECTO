"""Fábricas de datos sintéticos de MATU (MATU-30, estrategia de pruebas, secciones 3 y 9).

Cada método de ``Fabrica`` crea una cosa, con valores por omisión razonables y todo sobreescribible
por argumento, y devuelve un dataclass con los identificadores creados:

    fabrica = Fabrica()
    familia = fabrica.familia()                       # admin, un miembro por rol y persona, sin ficha
    con_ficha = fabrica.familia(con_ficha=True)       # lo mismo, con el plan de cuidado ya creado
    carmen = fabrica.usuario(nombre="Carmen Soto")
    grupo = fabrica.grupo(admin=carmen)
    rodrigo = fabrica.usuario(nombre="Rodrigo Soto")
    fabrica.membresia(grupo, rodrigo, "pagador", puede_ver_plan=True)
    maria = fabrica.persona_cuidada(grupo, calidad="cuidador_de_hecho")
    ficha = fabrica.ficha(maria)                      # el plan, sin secciones
    con_texto = fabrica.ficha(otra, textos={"rutina": "..."}, custodia=custodia)  # secciones cifradas
    fabrica.limpiar()

Siembran como superusuario (MATU_TEST_DSN), igual que las pruebas existentes: la API no tiene aún
invitaciones, y RLS no deja que matu_app escriba la membresía de otro usuario sin contexto de grupo.
Las verificaciones de las pruebas corren después como matu_app.

La fábrica anota lo que crea y ``limpiar()`` lo borra en orden inverso. En las pruebas se usa con
la fixture ``fabrica`` de tests/conftest.py, que limpia al terminar.

Sin factory-boy: las fábricas escriben con SQL y necesitan ids conocidos antes del INSERT (la misma
razón por la que la aplicación los genera en vez de usar RETURNING).
"""

import json
import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import psycopg

from app.core.config import POLITICA_VERSION_FABRICA
from app.modules.care_circle.domain.personas import (
    FINALIDAD_PLAN_CUIDADO,
    CalidadOtorgante,
    evidencia,
    revision_vence_en,
)
from app.modules.care_plan.application.ports import CustodiaClaves, DekEnvuelta
from app.modules.care_plan.domain.cifrado import ClaveGuardada
from app.modules.care_plan.domain.ficha import CampoFicha, completitud, normalizar_texto
from app.modules.care_plan.infrastructure.cifrador_aes_gcm import CifradorAesGcm
from app.modules.iam.domain.credenciales import indice_email, normalizar_email
from tests.base_datos import DSN
from tests.fabricas import datos
from tests.fabricas.sql import (
    ACTUALIZAR_COMPLETITUD,
    BORRAR_CONTENIDO_DE_GRUPOS,
    CLAVE_DE_PERSONA,
    CREAR_CLAVE,
    INSERTAR_CONSENTIMIENTO,
    INSERTAR_DIRECCION,
    INSERTAR_INDICE,
    INSERTAR_PERSONA,
    INSERTAR_PLAN,
    INSERTAR_SECCION,
    INSERTAR_USUARIO,
    LEER_CLAVE,
    insertar_grupo,
    insertar_membresia,
)

ROLES = ("admin", "cuidador", "pagador", "observador")

# Referencia sintética al documento de un representante legal. Nunca el documento (MATU-07)
REFERENCIA_SINTETICA = "Resolución sintética 123-2026"

# Las etiquetas de los miembros que crea familia(). "pagador_con_plan" es un pagador con puede_ver_plan
MIEMBROS_POR_OMISION = ("cuidador", "pagador_con_plan", "pagador", "observador")

# Las únicas tablas que anotar() acepta y limpiar() borra por id. limpiar() interpola el nombre en el
# DELETE, y anotar() es público: la lista blanca evita que un nombre arbitrario llegue al SQL.
TABLAS_ANOTABLES = frozenset(
    {
        "usuario",
        "grupo_familiar",
        "membresia",
        "direccion",
        "persona_cuidada",
        "consentimiento",
        "plan_cuidado",
        "clave_datos",
    }
)


def _validar_tabla(tabla: str) -> None:
    if tabla not in TABLAS_ANOTABLES:
        raise ValueError(f"tabla no anotable: {tabla!r}. Permitidas: {', '.join(sorted(TABLAS_ANOTABLES))}")


@dataclass(frozen=True)
class UsuarioCreado:
    id: uuid.UUID
    nombre: str
    email: str
    # La contraseña en claro, para iniciar sesión en la API. None si la prueba entregó el hash
    contrasena: str | None


@dataclass(frozen=True)
class GrupoCreado:
    id: uuid.UUID
    nombre: str
    admin_id: uuid.UUID
    membresia_admin_id: uuid.UUID


@dataclass(frozen=True)
class MembresiaCreada:
    id: uuid.UUID
    grupo_id: uuid.UUID
    usuario_id: uuid.UUID
    rol: str
    puede_ver_plan: bool
    estado: str


@dataclass(frozen=True)
class PersonaCreada:
    id: uuid.UUID
    grupo_id: uuid.UUID
    nombre: str
    nombre_pila: str
    direccion_id: uuid.UUID | None
    # None si se creó sin consentimiento (con_consentimiento=False)
    consentimiento_id: uuid.UUID | None
    calidad_otorgante: str | None


@dataclass(frozen=True)
class FichaCreada:
    plan_id: uuid.UUID
    grupo_id: uuid.UUID
    persona_cuidada_id: uuid.UUID
    # Los campos que la fábrica escribió, cifrados. Vacío si se creó sin textos
    campos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Miembro:
    usuario: UsuarioCreado
    membresia: MembresiaCreada


@dataclass(frozen=True)
class FamiliaCreada:
    grupo: GrupoCreado
    admin: UsuarioCreado
    # Por etiqueta: "cuidador", "pagador_con_plan", "pagador", "observador" o las que pidió la prueba
    miembros: dict[str, Miembro]
    persona: PersonaCreada
    ficha: FichaCreada | None


def _hash_argon2id(contrasena: str) -> str:
    """Argon2id real, con el costo mínimo: las pruebas crean muchas cuentas. El hash guarda sus
    parámetros, así que HasherArgon2id de la API lo verifica igual y la cuenta sirve para iniciar
    sesión. Se importa aquí para que cargar el paquete no exija argon2."""
    from argon2 import PasswordHasher, Type

    from app.modules.iam.infrastructure.hasher_argon2 import HasherArgon2id

    rapido = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1, type=Type.ID)
    return HasherArgon2id(rapido).hashear(contrasena)


def _id(valor: Any) -> uuid.UUID:
    """Acepta el dataclass creado o su id."""
    return valor if isinstance(valor, uuid.UUID) else uuid.UUID(str(valor.id))


@dataclass
class Fabrica:
    """Crea filas sintéticas como superusuario y recuerda cuáles para borrarlas después.

    ``pepper`` es el del HMAC de indice_credencial. Por omisión, uno sintético por fábrica. Para que
    las cuentas sirvan en la API de la prueba, se entrega el mismo pepper que la API usa
    (por ejemplo ``Fabrica(pepper=entorno_iam.pepper)``).
    """

    dsn: str = DSN
    pepper: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    # (tabla, id) en orden de creación
    creados: list[tuple[str, uuid.UUID]] = field(default_factory=list)

    def _conectar(self) -> Any:
        return psycopg.connect(self.dsn, autocommit=True)

    def anotar(self, tabla: str, fila_id: uuid.UUID) -> None:
        """Anota una fila para que limpiar() la borre. Sirve también para lo que la prueba creó por
        otro camino (la API o la semilla): un grupo anotado se vacía entero antes de borrarse.

        ``tabla`` debe estar en TABLAS_ANOTABLES; si no, ValueError.
        """
        _validar_tabla(tabla)
        self.creados.append((tabla, fila_id))

    def ids(self, tabla: str) -> list[uuid.UUID]:
        return [fila_id for t, fila_id in self.creados if t == tabla]

    # --- Usuario --------------------------------------------------------------------------------

    def usuario(
        self,
        *,
        nombre: str | None = None,
        email: str | None = None,
        contrasena: str | None = None,
        password_hash: str | None = None,
        pepper: bytes | None = None,
        estado: str = "activo",
    ) -> UsuarioCreado:
        """Una cuenta con su fila de indice_credencial, como la deja el registro (MATU-04).

        Sin ``password_hash``, hashea ``contrasena`` (o una sintética) con Argon2id. Con él, la
        contraseña queda en None: la fábrica no la conoce.
        """
        nombre = nombre or datos.nombre_completo()
        email_normalizado = normalizar_email(email or datos.email_para(nombre))
        if password_hash is None:
            contrasena = contrasena or datos.contrasena()
            password_hash = _hash_argon2id(contrasena)
        else:
            contrasena = None
        usuario_id = uuid.uuid4()
        with self._conectar() as cx, cx.transaction():
            cx.execute(INSERTAR_USUARIO, (usuario_id, email_normalizado, nombre, password_hash, estado))
            cx.execute(INSERTAR_INDICE, (indice_email(pepper or self.pepper, email_normalizado), usuario_id))
        self.anotar("usuario", usuario_id)
        return UsuarioCreado(id=usuario_id, nombre=nombre, email=email_normalizado, contrasena=contrasena)

    # --- Grupo y membresía ------------------------------------------------------------------------

    def grupo(self, *, admin: UsuarioCreado | uuid.UUID | None = None, nombre: str | None = None) -> GrupoCreado:
        """Un grupo con la membresía admin activa de quien lo crea, como lo deja POST /v1/grupos (MATU-06).

        Sin ``admin``, crea también la cuenta.
        """
        admin_id = _id(admin) if admin is not None else self.usuario().id
        nombre = nombre or f"Familia {datos.nombre_completo().split()[1]}"
        grupo_id = uuid.uuid4()
        with self._conectar() as cx, cx.transaction():
            insertar_grupo(cx, grupo_id, nombre, admin_id)
            membresia_id = insertar_membresia(cx, grupo_id, admin_id, "admin")
        self.anotar("grupo_familiar", grupo_id)
        self.anotar("membresia", membresia_id)
        return GrupoCreado(id=grupo_id, nombre=nombre, admin_id=admin_id, membresia_admin_id=membresia_id)

    def membresia(
        self,
        grupo: GrupoCreado | uuid.UUID,
        usuario: UsuarioCreado | uuid.UUID,
        rol: str,
        *,
        puede_ver_plan: bool = False,
        estado: str = "activa",
        invitado_por: uuid.UUID | None = None,
    ) -> MembresiaCreada:
        """La membresía de ``usuario`` en ``grupo`` con ``rol``. puede_ver_plan solo con pagador.

        ``invitado_por`` es, por omisión, el admin del grupo si se entrega un GrupoCreado.
        """
        if rol not in ROLES:
            raise ValueError(f"rol desconocido: {rol!r}")
        if puede_ver_plan and rol != "pagador":
            raise ValueError("puede_ver_plan solo corresponde al rol pagador (CHECK membresia_permiso_plan)")
        if invitado_por is None and isinstance(grupo, GrupoCreado):
            invitado_por = grupo.admin_id
        grupo_id, usuario_id = _id(grupo), _id(usuario)
        with self._conectar() as cx:
            membresia_id = insertar_membresia(
                cx, grupo_id, usuario_id, rol, estado=estado, puede_ver_plan=puede_ver_plan, invitado_por=invitado_por
            )
        self.anotar("membresia", membresia_id)
        return MembresiaCreada(
            id=membresia_id,
            grupo_id=grupo_id,
            usuario_id=usuario_id,
            rol=rol,
            puede_ver_plan=puede_ver_plan,
            estado=estado,
        )

    def miembro(
        self, grupo: GrupoCreado | uuid.UUID, rol: str, *, puede_ver_plan: bool = False, **usuario: Any
    ) -> Miembro:
        """Una cuenta nueva y su membresía en el grupo. ``usuario`` va a Fabrica.usuario()."""
        cuenta = self.usuario(**usuario)
        return Miembro(usuario=cuenta, membresia=self.membresia(grupo, cuenta, rol, puede_ver_plan=puede_ver_plan))

    # --- Persona cuidada con consentimiento ----------------------------------------------------------

    def persona_cuidada(
        self,
        grupo: GrupoCreado | uuid.UUID,
        *,
        otorgante: UsuarioCreado | uuid.UUID | None = None,
        nombre: str | None = None,
        nombre_pila: str | None = None,
        nivel_apoyo: str = "apoyo_parcial",
        con_direccion: bool = True,
        comuna: str | None = None,
        con_consentimiento: bool = True,
        calidad: CalidadOtorgante | str = CalidadOtorgante.TITULAR,
        referencia_documento: str | None = None,
        version_politica: str = POLITICA_VERSION_FABRICA,
        otorgado_en: datetime | None = None,
    ) -> PersonaCreada:
        """La persona, su dirección y su consentimiento vigente para plan_cuidado, como los deja el
        alta de MATU-07 (sin la fila de auditoría, que es de solo inserción y no se podría limpiar).

        - ``otorgante``: quien da el consentimiento. Por omisión, el admin del grupo (requiere un
          GrupoCreado).
        - ``calidad``: titular, representante_legal (con ``referencia_documento``, por omisión una
          sintética) o cuidador_de_hecho (con revisión a 12 meses y el aviso vigente en la evidencia).
          La evidencia y la revisión salen de las mismas reglas de dominio que usa la API.
        - ``con_consentimiento=False``: la persona sin consentimiento, para probar el 403 de MATU-12.
        """
        grupo_id = _id(grupo)
        nombre = nombre or datos.nombre_completo()
        nombre_pila = nombre_pila or nombre.split()[0]
        persona_id = uuid.uuid4()
        direccion_id = uuid.uuid4() if con_direccion else None
        consentimiento_id: uuid.UUID | None = None
        calidad_valor: str | None = None
        if con_consentimiento and otorgante is None:
            if not isinstance(grupo, GrupoCreado):
                raise ValueError("sin un GrupoCreado hay que indicar el otorgante")
            otorgante = grupo.admin_id

        with self._conectar() as cx, cx.transaction():
            if direccion_id is not None:
                cx.execute(
                    INSERTAR_DIRECCION,
                    (
                        direccion_id,
                        grupo_id,
                        datos.calle(),
                        datos.numero_calle(),
                        comuna or datos.comuna(),
                        "Metropolitana",
                    ),
                )
            cx.execute(INSERTAR_PERSONA, (persona_id, grupo_id, nombre, nombre_pila, nivel_apoyo, direccion_id))
            if con_consentimiento:
                calidad_enum = CalidadOtorgante(calidad)
                calidad_valor = calidad_enum.value
                if calidad_enum is CalidadOtorgante.REPRESENTANTE_LEGAL:
                    referencia_documento = referencia_documento or REFERENCIA_SINTETICA
                instante = otorgado_en or datetime.now(UTC)
                consentimiento_id = uuid.uuid4()
                cx.execute(
                    INSERTAR_CONSENTIMIENTO,
                    (
                        consentimiento_id,
                        grupo_id,
                        persona_id,
                        _id(otorgante),
                        calidad_valor,
                        FINALIDAD_PLAN_CUIDADO,
                        version_politica,
                        json.dumps(evidencia(calidad_enum, version_politica), ensure_ascii=False, sort_keys=True),
                        referencia_documento,
                        instante,
                        revision_vence_en(calidad_enum, instante),
                    ),
                )

        if direccion_id is not None:
            self.anotar("direccion", direccion_id)
        self.anotar("persona_cuidada", persona_id)
        if consentimiento_id is not None:
            self.anotar("consentimiento", consentimiento_id)
        return PersonaCreada(
            id=persona_id,
            grupo_id=grupo_id,
            nombre=nombre,
            nombre_pila=nombre_pila,
            direccion_id=direccion_id,
            consentimiento_id=consentimiento_id,
            calidad_otorgante=calidad_valor,
        )

    # --- Ficha de relevo ----------------------------------------------------------------------------

    def ficha(
        self,
        persona: PersonaCreada,
        *,
        actualizado_por: uuid.UUID | None = None,
        textos: Mapping[str, str] | None = None,
        custodia: CustodiaClaves | None = None,
    ) -> FichaCreada:
        """El plan de cuidado de la persona en modo 'ficha_relevo' y, si llegan ``textos``, sus secciones
        cifradas, como las deja el PUT de la ficha (MATU-12).

        Es un paso aparte y no lo da familia() por omisión: plan_cuidado.persona_cuidada_id es
        UNIQUE, así que la persona admite un solo plan. Las pruebas de MATU-12 (el plan nace en la
        primera escritura) necesitan a la persona sin plan; las que parten de una ficha existente
        la piden con ficha() o con familia(con_ficha=True).

        - ``textos``: campo de la ficha (rutina, manejo_situaciones o red_apoyo) → texto sintético.
          Se normalizan igual que en la API y se cifran con CifradorAesGcm (AES-256-GCM, AAD
          plan_id ‖ tipo) y la DEK de la persona, que se crea y se envuelve con ``custodia`` si no
          existe. Cada sección queda en versión 1, escrita por ``actualizado_por``, y el plan con su
          completitud. Nunca se escribe texto de la ficha en claro, ni siquiera sintético.
        - ``custodia``: obligatoria con ``textos``. Para que la API de la prueba lea la ficha, debe ser
          la misma custodia que usa la API (por ejemplo la fixture ``custodia``, entregada también a
          ``app.dependency_overrides[obtener_custodia]``).
        """
        pedidos = dict(textos or {})
        if pedidos and custodia is None:
            raise ValueError("para escribir textos hace falta la custodia que usa la API")
        # CampoFicha(...) lanza ValueError si el campo no es uno de los tres
        normalizados = {CampoFicha(campo): normalizar_texto(texto) for campo, texto in pedidos.items()}

        plan_id = uuid.uuid4()
        clave_id: uuid.UUID | None = None
        with self._conectar() as cx, cx.transaction():
            cx.execute(INSERTAR_PLAN, (plan_id, persona.grupo_id, persona.id, actualizado_por))
            if normalizados:
                assert custodia is not None
                cifrador = CifradorAesGcm(custodia, _RepositorioClavesFabrica(cx))
                for campo, texto in normalizados.items():
                    seccion = cifrador.cifrar(
                        grupo_id=persona.grupo_id,
                        persona_cuidada_id=persona.id,
                        plan_id=plan_id,
                        tipo=campo.value,
                        texto=texto,
                    )
                    cx.execute(
                        INSERTAR_SECCION,
                        (
                            plan_id,
                            campo.value,
                            seccion.contenido_cifrado,
                            seccion.nonce,
                            seccion.tag_auth,
                            seccion.kek_version,
                            actualizado_por,
                        ),
                    )
                pct = completitud(sum(1 for texto in normalizados.values() if texto))
                cx.execute(ACTUALIZAR_COMPLETITUD, (pct, plan_id))
                fila = cx.execute(CLAVE_DE_PERSONA, (persona.id,)).fetchone()
                clave_id = None if fila is None else fila[0]
        self.anotar("plan_cuidado", plan_id)
        if clave_id is not None:
            self.anotar("clave_datos", clave_id)
        return FichaCreada(
            plan_id=plan_id,
            grupo_id=persona.grupo_id,
            persona_cuidada_id=persona.id,
            campos=tuple(campo.value for campo in normalizados),
        )

    # --- Una familia completa -------------------------------------------------------------------------

    def familia(
        self,
        *,
        nombre: str | None = None,
        miembros: tuple[str, ...] = MIEMBROS_POR_OMISION,
        calidad: CalidadOtorgante | str = CalidadOtorgante.TITULAR,
        con_consentimiento: bool = True,
        con_ficha: bool = False,
    ) -> FamiliaCreada:
        """Un grupo con su admin, un miembro por etiqueta, una persona cuidada con consentimiento
        (otorgado por el admin) y, solo si ``con_ficha=True``, su ficha.

        Sin ficha por omisión: plan_cuidado.persona_cuidada_id es UNIQUE y en MATU-12 el plan nace
        en la primera escritura. Una familia con ficha ya creada haría fallar esas pruebas (409 o
        violación de UNIQUE) u ocultaría el camino de creación. La prueba que necesita la ficha la
        pide explícitamente.

        Etiquetas: los cuatro roles y "pagador_con_plan" (pagador con puede_ver_plan).
        """
        admin = self.usuario()
        grupo = self.grupo(admin=admin, nombre=nombre)
        creados: dict[str, Miembro] = {}
        for etiqueta in miembros:
            rol = "pagador" if etiqueta == "pagador_con_plan" else etiqueta
            creados[etiqueta] = self.miembro(grupo, rol, puede_ver_plan=etiqueta == "pagador_con_plan")
        persona = self.persona_cuidada(grupo, calidad=calidad, con_consentimiento=con_consentimiento)
        ficha = self.ficha(persona) if con_ficha else None
        return FamiliaCreada(grupo=grupo, admin=admin, miembros=creados, persona=persona, ficha=ficha)

    # --- Limpieza -------------------------------------------------------------------------------------

    def limpiar(self) -> None:
        """Borra lo creado, como superusuario.

        1. Vacía los grupos de la fábrica, incluido lo que la prueba escribió en ellos por la API
           (secciones de la ficha, claves de datos, accesos de relevo). Sin esto, borrar una cuenta
           fallaría por una fila que aún la referencia.
        2. Borra lo anotado en orden inverso de creación, y al final las cuentas con lo que la prueba
           haya creado para ellas fuera de los grupos (membresías, sesiones, dispositivos).

        La auditoría se queda: es de solo inserción y solo lleva identificadores.

        Antes de abrir la conexión valida cada tabla contra TABLAS_ANOTABLES (ValueError), porque
        ``creados`` es una lista mutable y pudo llenarse sin pasar por anotar().
        """
        if not self.creados:
            return
        for tabla, _ in self.creados:
            _validar_tabla(tabla)
        grupos = self.ids("grupo_familiar")
        usuarios = self.ids("usuario")
        with self._conectar() as cx, cx.transaction():
            if grupos:
                for sentencia in BORRAR_CONTENIDO_DE_GRUPOS:
                    if "FROM consentimiento" in sentencia:
                        # consentimiento no se borra (trigger consentimiento_sin_borrado, 0006): solo
                        # para esta sentencia, el superusuario apaga los triggers con el rol de réplica
                        cx.execute("SET LOCAL session_replication_role = replica")
                        cx.execute(sentencia, (grupos,))
                        cx.execute("SET LOCAL session_replication_role = origin")
                    else:
                        cx.execute(sentencia, (grupos,))
            for tabla, fila_id in reversed(self.creados):
                if tabla != "usuario":
                    # tabla puede venir de un argumento de anotar(), pero ya pasó por la lista
                    # blanca TABLAS_ANOTABLES arriba: nunca llega al SQL un nombre fuera de ella
                    cx.execute(f"DELETE FROM {tabla} WHERE id = %s", (fila_id,))
            if usuarios:
                # Lo que la prueba pudo crear para esas cuentas fuera de los grupos de la fábrica
                cx.execute("DELETE FROM membresia WHERE usuario_id = ANY(%s::uuid[])", (usuarios,))
                cx.execute("DELETE FROM sesion_refresh WHERE usuario_id = ANY(%s::uuid[])", (usuarios,))
                cx.execute("DELETE FROM dispositivo WHERE usuario_id = ANY(%s::uuid[])", (usuarios,))
                cx.execute("DELETE FROM usuario WHERE id = ANY(%s::uuid[])", (usuarios,))
        self.creados.clear()


class _RepositorioClavesFabrica:
    """El puerto RepositorioClaves sobre la conexión de superusuario de la fábrica.

    Mismas sentencias que RepositorioClavesSQL (FOR SHARE al escribir y ON CONFLICT DO NOTHING al
    crear), dentro de la transacción de la fábrica: la clave y las secciones quedan juntas o no quedan.
    """

    def __init__(self, cx: Any) -> None:
        self._cx = cx

    def obtener(self, persona_cuidada_id: uuid.UUID, *, para_escribir: bool = False) -> ClaveGuardada | None:
        sentencia = LEER_CLAVE + (" FOR SHARE" if para_escribir else "")
        fila = self._cx.execute(sentencia, (persona_cuidada_id,)).fetchone()
        if fila is None:
            return None
        dek_cifrada, kek_version = fila
        return ClaveGuardada(
            kek_version=kek_version, dek_cifrada=bytes(dek_cifrada) if dek_cifrada is not None else None
        )

    def crear(self, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, envuelta: DekEnvuelta) -> bool:
        cursor = self._cx.execute(
            CREAR_CLAVE, (grupo_id, persona_cuidada_id, envuelta.dek_cifrada, envuelta.kek_version)
        )
        return bool(cursor.rowcount == 1)
