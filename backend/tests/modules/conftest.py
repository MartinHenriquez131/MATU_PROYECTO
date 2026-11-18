"""Fixtures compartidas por las pruebas de módulos: la API con sus logs capturados, un pepper y una
clave JWT sintéticos, un reloj fijo y limpieza de las cuentas creadas."""

import io
import json
import secrets
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Annotated, Any

import psycopg
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.main import crear_app
from app.modules.care_circle.api.router_autorizaciones import finalidades_activas
from app.modules.care_circle.domain.retiro import finalidades_retirables
from app.modules.iam.api.dependencias import UsuarioActual, obtener_clave_jwt, obtener_reloj, usuario_actual
from app.modules.iam.api.router import obtener_pepper_email
from app.modules.iam.api.router_mfa import obtener_almacen_mfa, obtener_cifrador_mfa
from app.modules.iam.api.router_politica import obtener_politica_vigente
from app.modules.iam.api.router_recuperacion import (
    obtener_almacen_codigos,
    obtener_contadores_envio,
    obtener_enviador,
    obtener_pepper_recuperacion,
)
from app.modules.iam.api.sesion_web import obtener_contadores, obtener_pepper_limites
from app.modules.iam.domain.mfa import hotp, paso_de
from app.modules.iam.infrastructure.cifrador_mfa import CifradorMfaKek
from app.modules.iam.infrastructure.enviador_simulado import EnviadorSimulado
from app.shared.notas_operacion import CustodiaNotas, obtener_custodia_notas
from tests.base_datos import DSN
from tests.dobles.contador_ventana_en_memoria import ContadorVentanaEnMemoria, limite_ip_en_memoria
from tests.dobles.contadores_en_memoria import ContadoresEnMemoria
from tests.dobles.mfa_en_memoria import AlmacenMfaEnMemoria
from tests.dobles.recuperacion_en_memoria import AlmacenCodigosEnMemoria, ContadoresEnvioEnMemoria
from tests.dobles.reloj_fijo import RelojFijo
from tests.politica import POLITICA_PRUEBAS


@dataclass
class EntornoIam:
    cliente: TestClient
    salida_logs: io.StringIO
    pepper: bytes
    clave_jwt: bytes
    reloj: RelojFijo
    contadores: ContadoresEnMemoria = field(default_factory=ContadoresEnMemoria)
    pepper_limites: bytes = b""
    limite_ip: ContadorVentanaEnMemoria | None = None
    creados: list[uuid.UUID] = field(default_factory=list)
    # MATU-57: códigos, envíos y el envío simulado, en memoria
    almacen: AlmacenCodigosEnMemoria | None = None
    envios: ContadoresEnvioEnMemoria | None = None
    enviador: EnviadorSimulado = field(default_factory=EnviadorSimulado)
    pepper_recuperacion: bytes = b""
    # MATU-81: el segundo factor, con una KEK sintética de la prueba y el almacén en memoria
    almacen_mfa: AlmacenMfaEnMemoria | None = None
    cifrador_mfa: CifradorMfaKek | None = None
    # MATU-81 (decisión 471): la clave de las notas de operación, envuelta con una KEK de la prueba
    custodia_notas: CustodiaNotas | None = None
    pasos_usados: dict[uuid.UUID, int] = field(default_factory=dict)

    def dar_alta_operacion(self, usuario_id: uuid.UUID) -> bytes:
        """Marca la cuenta como de operación con un secreto TOTP sintético, como superusuario (lo que hace la tarea
        operacion-alta con matu_scheduler). Devuelve el secreto, que solo conoce la prueba."""
        assert self.cifrador_mfa is not None
        secreto = secrets.token_bytes(20)
        with psycopg.connect(DSN, autocommit=True) as cx:
            cx.execute(
                "UPDATE usuario SET es_operacion = true, mfa_secreto_cifrado = %s WHERE id = %s",
                (self.cifrador_mfa.cifrar(secreto, usuario_id), usuario_id),
            )
        return secreto

    def codigo_mfa(self, usuario_id: uuid.UUID, secreto: bytes) -> str:
        """El código del paso actual o, si ya se usó, el del siguiente (la ventana admite ±1)."""
        paso = max(paso_de(self.reloj.ahora()), self.pasos_usados.get(usuario_id, -1) + 1)
        self.pasos_usados[usuario_id] = paso
        return hotp(secreto, paso)

    def entrar_operacion(self, email: str, contrasena: str, usuario_id: uuid.UUID, secreto: bytes) -> Any:
        """Los dos pasos de la entrada de operación. Devuelve la respuesta del segundo."""
        primero = self.iniciar_sesion(email=email, contrasena=contrasena)
        assert primero.status_code == 401 and primero.json()["type"] == "/errores/mfa-requerido", primero.text
        return self.cliente.post(
            "/v1/sesiones/mfa",
            json={"desafio": primero.json()["desafio"], "codigo": self.codigo_mfa(usuario_id, secreto)},
        )

    def registrar(self, **cuerpo: Any) -> Any:
        # El celular es obligatorio desde MATU-39. Si la prueba no lo trae, va uno sintético;
        # telefono=None lo omite del cuerpo
        cuerpo.setdefault("telefono", "+56 9 0000 0001")
        if cuerpo["telefono"] is None:
            del cuerpo["telefono"]
        # MATU-75: la casilla de la política, obligatoria. acepta_politica=None la omite del cuerpo
        cuerpo.setdefault("acepta_politica", True)
        if cuerpo["acepta_politica"] is None:
            del cuerpo["acepta_politica"]
        # Decisión 182: la huella de la política que se mostró, obligatoria. huella_politica=None la omite
        cuerpo.setdefault("huella_politica", POLITICA_PRUEBAS.huella)
        if cuerpo["huella_politica"] is None:
            del cuerpo["huella_politica"]
        respuesta = self.cliente.post("/v1/usuarios", json=cuerpo)
        if respuesta.status_code == 201:
            self.creados.append(uuid.UUID(respuesta.json()["id"]))
        return respuesta

    def iniciar_sesion(self, **cuerpo: Any) -> Any:
        return self.cliente.post("/v1/sesiones", json=cuerpo)

    def yo(self, token: str | None = None, *, autorizacion: str | None = None) -> Any:
        """GET /prueba/yo, una ruta protegida por usuario_actual que solo existe en las pruebas."""
        if autorizacion is None and token is not None:
            autorizacion = f"Bearer {token}"
        cabeceras = {"Authorization": autorizacion} if autorizacion is not None else {}
        return self.cliente.get("/prueba/yo", headers=cabeceras)

    def texto_log(self) -> str:
        return self.salida_logs.getvalue()

    def lineas_log(self) -> list[dict[str, Any]]:
        return [json.loads(linea) for linea in self.texto_log().splitlines() if linea.strip()]


@pytest.fixture
def email_sintetico() -> str:
    return f"familiar.{uuid.uuid4().hex[:12]}@ejemplo.cl"


@pytest.fixture
def contrasena_sintetica() -> str:
    """Una contraseña única que nunca debe aparecer en una respuesta, un log ni la base."""
    return f"clave-{secrets.token_hex(8)}"


@pytest.fixture
def rutas_de_prueba() -> Callable[[FastAPI], None]:
    """Registra rutas que solo existen en las pruebas. Cada módulo la sobreescribe en su conftest."""
    return lambda app: None


@pytest.fixture
def entorno_iam(reloj_fijo: RelojFijo, rutas_de_prueba: Callable[[FastAPI], None]) -> Iterator[EntornoIam]:
    salida = io.StringIO()
    pepper = secrets.token_bytes(32)
    clave_jwt = secrets.token_hex(32).encode()
    pepper_limites = secrets.token_bytes(32)
    contadores = ContadoresEnMemoria()
    app = crear_app(stream_logs=salida)
    app.dependency_overrides[obtener_pepper_email] = lambda: pepper
    # MATU-38: la demora de la entrada con contadores en memoria, sin depender de Redis
    app.dependency_overrides[obtener_pepper_limites] = lambda: pepper_limites
    app.dependency_overrides[obtener_contadores] = lambda: contadores
    # MATU-25: el límite por IP con un contador en memoria, nuevo en cada prueba, con el mismo pepper
    limite_ip = limite_ip_en_memoria(app, reloj_fijo)
    app.dependency_overrides[obtener_clave_jwt] = lambda: clave_jwt
    # El mismo reloj emite y valida: la prueba lo hace avanzar para vencer el token
    app.dependency_overrides[obtener_reloj] = lambda: reloj_fijo
    # MATU-75: la política 0.11 publicada, con un correo sintético, sin depender del .env del equipo
    app.dependency_overrides[obtener_politica_vigente] = lambda: POLITICA_PRUEBAS
    # MATU-61 (C2): las finalidades de las capas 1 y 2, sin depender de CAPA3_HABILITADA del .env del equipo. Las
    # pruebas del pedido encienden despacho con finalidades_activas
    app.dependency_overrides[finalidades_activas] = lambda: finalidades_retirables(False)

    @app.get("/prueba/yo")
    def yo(usuario: Annotated[UsuarioActual, Depends(usuario_actual)]) -> dict[str, str]:
        return {"id": str(usuario.id)}

    # MATU-57: Redis y el envío, en memoria
    pepper_recuperacion = secrets.token_bytes(32)
    almacen = AlmacenCodigosEnMemoria(reloj_fijo)
    envios = ContadoresEnvioEnMemoria(reloj_fijo)
    enviador = EnviadorSimulado()
    app.dependency_overrides[obtener_pepper_recuperacion] = lambda: pepper_recuperacion
    app.dependency_overrides[obtener_almacen_codigos] = lambda: almacen
    app.dependency_overrides[obtener_contadores_envio] = lambda: envios
    app.dependency_overrides[obtener_enviador] = lambda: enviador

    # MATU-81: el segundo factor en memoria, con una KEK de la prueba
    almacen_mfa = AlmacenMfaEnMemoria(reloj_fijo)
    cifrador_mfa = CifradorMfaKek(secrets.token_bytes(32), 1)
    app.dependency_overrides[obtener_almacen_mfa] = lambda: almacen_mfa
    app.dependency_overrides[obtener_cifrador_mfa] = lambda: cifrador_mfa
    custodia_notas = CustodiaNotas(secrets.token_bytes(32), 1)
    app.dependency_overrides[obtener_custodia_notas] = lambda: custodia_notas

    rutas_de_prueba(app)

    entorno = EntornoIam(
        cliente=TestClient(app, raise_server_exceptions=False),
        salida_logs=salida,
        pepper=pepper,
        clave_jwt=clave_jwt,
        reloj=reloj_fijo,
        contadores=contadores,
        pepper_limites=pepper_limites,
        limite_ip=limite_ip,
        almacen=almacen,
        envios=envios,
        enviador=enviador,
        pepper_recuperacion=pepper_recuperacion,
        almacen_mfa=almacen_mfa,
        cifrador_mfa=cifrador_mfa,
        custodia_notas=custodia_notas,
    )
    with entorno.cliente:
        yield entorno
    if entorno.creados:
        # Las filas se borran como superusuario: matu_app no ve las cuentas de otros (RLS)
        with psycopg.connect(DSN, autocommit=True) as cx:
            # MATU-38: las sesiones y los dispositivos cuelgan del usuario (indice_token no tiene llave)
            cx.execute(
                "DELETE FROM indice_token WHERE tipo = 'refresh' AND usuario_id = ANY(%s)", (entorno.creados,)
            )
            cx.execute("DELETE FROM sesion_refresh WHERE usuario_id = ANY(%s)", (entorno.creados,))
            cx.execute("DELETE FROM dispositivo WHERE usuario_id = ANY(%s)", (entorno.creados,))
            # MATU-41: la preferencia de avisos que la prueba guardó por la API
            cx.execute("DELETE FROM preferencia_notificacion WHERE usuario_id = ANY(%s)", (entorno.creados,))
            # MATU-75: la aceptación de la política no cae con la cuenta (sin ON DELETE CASCADE)
            cx.execute("DELETE FROM aceptacion_politica WHERE usuario_id = ANY(%s)", (entorno.creados,))
            cx.execute("DELETE FROM usuario WHERE id = ANY(%s)", (entorno.creados,))
