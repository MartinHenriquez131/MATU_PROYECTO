"""MATU-05a · Casos de uso de la sesión y adaptador JWT, sin base (RF-37).

El repositorio y el hasher son dobles en memoria. El emisor es el real (PyJWT), con una clave
sintética por prueba.
"""

import base64
import json
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.modules.iam.application.ports import CredencialGuardada
from app.modules.iam.application.sesion import iniciar_sesion, validar_acceso
from app.modules.iam.domain.credenciales import indice_email
from app.modules.iam.domain.sesion import CredencialesInvalidas, TokenInvalido
from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT
from tests.dobles.reloj_fijo import RelojFijo

PEPPER = b"p" * 32


@dataclass
class HasherFalso:
    """Guarda "falso$<contraseña>" y registra cada verificación, para contar cuántas hubo."""

    verificados: list[str] = field(default_factory=list)

    def hashear(self, contrasena: str) -> str:
        return "falso$" + contrasena

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        self.verificados.append(hash_guardado)
        return hash_guardado == "falso$" + contrasena


@dataclass
class RepositorioEnMemoria:
    credenciales: dict[bytes, CredencialGuardada] = field(default_factory=dict)
    buscados: list[bytes] = field(default_factory=list)

    def crear(self, usuario: object) -> None:  # pragma: no cover - no se usa aquí
        raise NotImplementedError

    def buscar_credencial(self, email_hash: bytes) -> CredencialGuardada | None:
        self.buscados.append(email_hash)
        return self.credenciales.get(email_hash)


@pytest.fixture
def clave() -> bytes:
    return secrets.token_hex(32).encode()


@pytest.fixture
def emisor(clave: bytes) -> EmisorJWT:
    return EmisorJWT(clave)


@pytest.fixture
def cuenta() -> CredencialGuardada:
    return CredencialGuardada(usuario_id=uuid.uuid4(), password_hash="falso$clave-sintetica", estado="activo")


@pytest.fixture
def repositorio(cuenta: CredencialGuardada) -> RepositorioEnMemoria:
    return RepositorioEnMemoria({indice_email(PEPPER, "familiar@ejemplo.cl"): cuenta})


def _iniciar(
    email: str,
    contrasena: str,
    repositorio: RepositorioEnMemoria,
    emisor: EmisorJWT,
    reloj: RelojFijo,
    hasher: HasherFalso | None = None,
) -> object:
    return iniciar_sesion(
        email=email,
        contrasena=contrasena,
        pepper=PEPPER,
        hasher=hasher or HasherFalso(),
        repositorio=repositorio,
        emisor=emisor,
        reloj=reloj,
    )


def _b64(datos: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()


# --- iniciar_sesion -----------------------------------------------------------------------


@pytest.mark.rf("RF-37")
def test_iniciar_sesion_emite_token_de_15_minutos(
    repositorio: RepositorioEnMemoria, emisor: EmisorJWT, reloj_fijo: RelojFijo, cuenta: CredencialGuardada
) -> None:
    sesion = iniciar_sesion(
        email="  Familiar@Ejemplo.CL ",
        contrasena="clave-sintetica",  # pragma: allowlist secret
        pepper=PEPPER,
        hasher=HasherFalso(),
        repositorio=repositorio,
        emisor=emisor,
        reloj=reloj_fijo,
    )

    assert sesion.usuario_id == cuenta.usuario_id
    assert sesion.duracion_segundos == 900
    assert sesion.expira_en == reloj_fijo.ahora() + timedelta(minutes=15)
    claims = emisor.leer(sesion.access_token)
    assert (claims.sub, claims.iat, claims.exp) == (cuenta.usuario_id, reloj_fijo.ahora(), sesion.expira_en)


@pytest.mark.rf("RF-37")
def test_contrasena_incorrecta_lanza_credenciales_invalidas(
    repositorio: RepositorioEnMemoria, emisor: EmisorJWT, reloj_fijo: RelojFijo
) -> None:
    with pytest.raises(CredencialesInvalidas):
        _iniciar("familiar@ejemplo.cl", "otra-clave", repositorio, emisor, reloj_fijo)


@pytest.mark.rf("RF-37")
def test_email_inexistente_verifica_igual_contra_hash_de_relleno(
    repositorio: RepositorioEnMemoria, emisor: EmisorJWT, reloj_fijo: RelojFijo
) -> None:
    # Para que el tiempo no delate la existencia de la cuenta, también se verifica un hash
    hasher = HasherFalso()

    with pytest.raises(CredencialesInvalidas):
        _iniciar("nadie@ejemplo.cl", "clave-sintetica", repositorio, emisor, reloj_fijo, hasher)

    assert len(hasher.verificados) == 1
    # El relleno no es el hash de la contraseña recibida: nunca la acepta
    assert hasher.verificados[0] != "falso$clave-sintetica"


def test_hash_de_relleno_se_genera_una_sola_vez(
    repositorio: RepositorioEnMemoria, emisor: EmisorJWT, reloj_fijo: RelojFijo
) -> None:
    hasher = HasherFalso()

    for _ in range(3):
        with pytest.raises(CredencialesInvalidas):
            _iniciar("nadie@ejemplo.cl", "clave-sintetica", repositorio, emisor, reloj_fijo, hasher)

    assert len(set(hasher.verificados)) == 1


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("estado", ["bloqueado", "eliminado"])
def test_cuenta_no_activa_lanza_credenciales_invalidas(
    emisor: EmisorJWT, reloj_fijo: RelojFijo, cuenta: CredencialGuardada, estado: str
) -> None:
    no_activa = CredencialGuardada(cuenta.usuario_id, cuenta.password_hash, estado)
    repositorio = RepositorioEnMemoria({indice_email(PEPPER, "familiar@ejemplo.cl"): no_activa})
    hasher = HasherFalso()

    with pytest.raises(CredencialesInvalidas):
        _iniciar("familiar@ejemplo.cl", "clave-sintetica", repositorio, emisor, reloj_fijo, hasher)

    # La contraseña se verificó igual: el tiempo no distingue la cuenta bloqueada
    assert hasher.verificados == [cuenta.password_hash]


# --- validar_acceso ------------------------------------------------------------------------


@pytest.mark.rf("RF-37")
def test_validar_acceso_devuelve_el_usuario(emisor: EmisorJWT, reloj_fijo: RelojFijo) -> None:
    usuario_id = uuid.uuid4()
    token = emisor.emitir(usuario_id, reloj_fijo.ahora(), reloj_fijo.ahora() + timedelta(minutes=15))

    reloj_fijo.avanzar(timedelta(minutes=14, seconds=59))

    assert validar_acceso(token, emisor, reloj_fijo) == usuario_id


@pytest.mark.rf("RF-37")
def test_validar_acceso_rechaza_token_vencido(emisor: EmisorJWT, reloj_fijo: RelojFijo) -> None:
    token = emisor.emitir(uuid.uuid4(), reloj_fijo.ahora(), reloj_fijo.ahora() + timedelta(minutes=15))

    reloj_fijo.avanzar(timedelta(minutes=15))

    with pytest.raises(TokenInvalido):
        validar_acceso(token, emisor, reloj_fijo)


# --- EmisorJWT ------------------------------------------------------------------------------


def test_emisor_firma_hs256_con_sub_iat_exp(emisor: EmisorJWT, clave: bytes) -> None:
    usuario_id = uuid.uuid4()
    emitido = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

    token = emisor.emitir(usuario_id, emitido, emitido + timedelta(minutes=15))

    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    claims = jwt.decode(token, clave, algorithms=["HS256"], options={"verify_exp": False})
    assert claims == {"sub": str(usuario_id), "iat": 1792497600, "exp": 1792497600 + 900}


@pytest.mark.rf("RF-37")
def test_emisor_rechaza_alg_none(emisor: EmisorJWT) -> None:
    token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': str(uuid.uuid4()), 'iat': 1, 'exp': 2_000_000_000})}."

    with pytest.raises(TokenInvalido):
        emisor.leer(token)


def test_emisor_rechaza_otra_clave(emisor: EmisorJWT) -> None:
    ahora = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    ajeno = EmisorJWT(secrets.token_hex(32).encode()).emitir(uuid.uuid4(), ahora, ahora + timedelta(minutes=15))

    with pytest.raises(TokenInvalido):
        emisor.leer(ajeno)


def test_emisor_rechaza_otro_algoritmo_hmac(clave: bytes, emisor: EmisorJWT) -> None:
    # Misma clave, pero HS512: el algoritmo no es negociable
    token = jwt.encode({"sub": str(uuid.uuid4()), "iat": 1, "exp": 2_000_000_000}, clave, algorithm="HS512")

    with pytest.raises(TokenInvalido):
        emisor.leer(token)


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"sub": "u", "iat": 1}, id="sin-exp"),
        pytest.param({"iat": 1, "exp": 2_000_000_000}, id="sin-sub"),
        pytest.param({"sub": "u", "exp": 2_000_000_000}, id="sin-iat"),
        pytest.param({"sub": "no-es-uuid", "iat": 1, "exp": 2_000_000_000}, id="sub-no-uuid"),
        pytest.param({"sub": "u", "iat": True, "exp": 2_000_000_000}, id="iat-booleano"),
        pytest.param({"sub": "u", "iat": 1, "exp": "mañana"}, id="exp-texto"),
        pytest.param({"sub": "u", "iat": 1, "exp": 10**30}, id="exp-fuera-de-rango"),
    ],
)
def test_emisor_rechaza_claims_incompletos_o_malformados(
    clave: bytes, emisor: EmisorJWT, claims: dict[str, object]
) -> None:
    if claims.get("sub") == "u":
        claims = {**claims, "sub": str(uuid.uuid4())}
    token = jwt.encode(claims, clave, algorithm="HS256")

    with pytest.raises(TokenInvalido):
        emisor.leer(token)


@pytest.mark.parametrize("basura", ["", "a.b", "a.b.c", "no es un token", "Bearer x.y.z"])
def test_emisor_rechaza_basura(emisor: EmisorJWT, basura: str) -> None:
    with pytest.raises(TokenInvalido):
        emisor.leer(basura)


def test_emisor_exige_clave() -> None:
    with pytest.raises(ValueError):
        EmisorJWT(b"")
