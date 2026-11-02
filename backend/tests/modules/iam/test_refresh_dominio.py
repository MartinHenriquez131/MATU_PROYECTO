"""MATU-38 · Reglas puras de la sesión: rotación, reutilización, ventana deslizante, demora progresiva,
dispositivos y conservación (RF-37). Sin base, sin Redis y sin reloj del sistema."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.iam.domain.demora import (
    PREFIJO_EMAIL,
    PREFIJO_IP,
    SIN_FALLOS,
    TOPE_ESPERA_SEGUNDOS,
    UMBRAL_EMAIL,
    UMBRAL_IP,
    ContadorFallos,
    espera_tras_fallos,
    huella,
    retry_after,
    segundos_restantes,
)
from app.modules.iam.domain.dispositivo import (
    NOMBRE_GENERICO,
    dispositivo_se_borra,
    limites_conservacion,
    nombre_dispositivo,
    push_admitido,
    sesion_se_borra,
)
from app.modules.iam.domain.refresh import (
    DURACION_REFRESH,
    MAX_AGE_REFRESH,
    EstadoRefresh,
    Veredicto,
    evaluar_renovacion,
    huella_refresh,
    sigue_vigente,
    tiene_forma_de_refresh,
    vencimiento_refresh,
)

pytestmark = pytest.mark.rf("RF-37")

AHORA = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def _estado(**cambios: object) -> EstadoRefresh:
    campos: dict[str, object] = {
        "expira_en": AHORA + timedelta(days=10),
        "usado_en": None,
        "revocado_en": None,
        "dispositivo_revocado": False,
        "cuenta_activa": True,
    }
    campos.update(cambios)
    return EstadoRefresh(**campos)  # type: ignore[arg-type]


# --- Refresh: forma, huella y ventana deslizante ------------------------------------------------


def test_forma_del_refresh_es_base64url_de_43() -> None:
    assert tiene_forma_de_refresh("A" * 43)
    assert tiene_forma_de_refresh("a-b_" * 10 + "xyz")
    for malo in (None, "", "A" * 42, "A" * 44, "A" * 42 + "=", "A" * 42 + "+", "A" * 42 + " "):
        assert not tiene_forma_de_refresh(malo)


def test_huella_es_sha256_de_32_bytes() -> None:
    assert len(huella_refresh("A" * 43)) == 32
    assert huella_refresh("A" * 43) != huella_refresh("B" * 43)


def test_ventana_deslizante_cada_token_vence_30_dias_despues_de_emitirse() -> None:
    assert MAX_AGE_REFRESH == 2_592_000
    assert vencimiento_refresh(AHORA) == AHORA + timedelta(days=30)
    # Sin tope de la familia: una renovación al día 29 alarga otros 30 desde ella
    renovado = AHORA + timedelta(days=29)
    assert vencimiento_refresh(renovado) - AHORA == timedelta(days=59)
    assert vencimiento_refresh(renovado) - renovado == DURACION_REFRESH


def test_ventana_exige_zona_horaria() -> None:
    with pytest.raises(ValueError):
        vencimiento_refresh(datetime(2026, 11, 2, 12, 0))


# --- Rotación y reutilización ---------------------------------------------------------------------


def test_token_sin_usar_y_vigente_rota() -> None:
    assert evaluar_renovacion(_estado(), AHORA) is Veredicto.VIGENTE
    assert sigue_vigente(_estado(), AHORA)


def test_token_ya_usado_es_reutilizacion() -> None:
    assert evaluar_renovacion(_estado(usado_en=AHORA - timedelta(minutes=1)), AHORA) is Veredicto.REUTILIZACION
    assert not sigue_vigente(_estado(usado_en=AHORA), AHORA)


def test_token_vencido_se_rechaza_en_el_instante_exacto() -> None:
    assert evaluar_renovacion(_estado(expira_en=AHORA), AHORA) is Veredicto.RECHAZADO
    assert evaluar_renovacion(_estado(expira_en=AHORA + timedelta(seconds=1)), AHORA) is Veredicto.VIGENTE


@pytest.mark.parametrize(
    "cambio",
    [
        pytest.param({"revocado_en": AHORA - timedelta(days=1)}, id="revocado"),
        pytest.param({"dispositivo_revocado": True}, id="dispositivo-revocado"),
        pytest.param({"cuenta_activa": False}, id="cuenta-no-activa"),
        # Un token usado de una familia ya revocada no vuelve a revocar: ya está cerrada
        pytest.param({"revocado_en": AHORA, "usado_en": AHORA}, id="usado-y-revocado"),
        # Un token usado que ya venció no cuenta como reutilización
        pytest.param(
            {"expira_en": AHORA - timedelta(days=1), "usado_en": AHORA - timedelta(days=2)}, id="usado-vencido"
        ),
    ],
)
def test_casos_rechazados(cambio: dict[str, object]) -> None:
    assert evaluar_renovacion(_estado(**cambio), AHORA) is Veredicto.RECHAZADO


# --- Demora progresiva (decisión 49) ------------------------------------------------------------------


def test_umbrales_de_la_decision_49() -> None:
    assert (UMBRAL_EMAIL, UMBRAL_IP, TOPE_ESPERA_SEGUNDOS) == (5, 20, 900)


def test_esperas_30s_1_2_4_8_minutos_y_tope_de_15() -> None:
    esperas = [espera_tras_fallos(n, UMBRAL_EMAIL) for n in range(1, 13)]
    assert esperas == [0, 0, 0, 0, 0, 30, 60, 120, 240, 480, 900, 900]
    assert espera_tras_fallos(10_000, UMBRAL_EMAIL) == 900
    assert espera_tras_fallos(20, UMBRAL_IP) == 0 and espera_tras_fallos(21, UMBRAL_IP) == 30


def test_segundos_restantes_cuentan_desde_el_ultimo_fallo_hacia_arriba() -> None:
    contador = ContadorFallos(6, AHORA)
    assert segundos_restantes(contador, UMBRAL_EMAIL, AHORA) == 30
    assert segundos_restantes(contador, UMBRAL_EMAIL, AHORA + timedelta(seconds=29, milliseconds=1)) == 1
    assert segundos_restantes(contador, UMBRAL_EMAIL, AHORA + timedelta(seconds=30)) == 0
    assert segundos_restantes(SIN_FALLOS, UMBRAL_EMAIL, AHORA) == 0
    assert segundos_restantes(ContadorFallos(5, AHORA), UMBRAL_EMAIL, AHORA) == 0


def test_retry_after_es_la_mayor_de_las_dos_huellas() -> None:
    email = ContadorFallos(7, AHORA)  # 60 s
    ip = ContadorFallos(21, AHORA - timedelta(seconds=10))  # 30 s, quedan 20
    assert retry_after(ip, email, AHORA) == 60
    assert retry_after(ip, SIN_FALLOS, AHORA) == 20
    assert retry_after(SIN_FALLOS, SIN_FALLOS, AHORA) == 0


def test_huella_hmac_por_prefijo_sin_el_valor_en_claro() -> None:
    pepper = b"p" * 32
    h_email = huella(pepper, PREFIJO_EMAIL, "familiar@ejemplo.cl")
    h_ip = huella(pepper, PREFIJO_IP, "192.0.2.10")
    assert len(h_email) == 64 and "ejemplo" not in h_email
    assert h_email != huella(pepper, PREFIJO_IP, "familiar@ejemplo.cl")
    assert h_ip != huella(b"q" * 32, PREFIJO_IP, "192.0.2.10")
    with pytest.raises(ValueError):
        huella(b"", PREFIJO_IP, "192.0.2.10")


# --- Dispositivos ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agente", "nombre"),
    [
        ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36",
         "Chrome en Android"),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148"
         " Safari/604.1", "Safari en iPhone"),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0", "Firefox en Windows"),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36 Edg/130.0",
         "Edge en Windows"),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15",
         "Safari en Mac"),
        ("curl/8.0", NOMBRE_GENERICO),
        ("", NOMBRE_GENERICO),
        (None, NOMBRE_GENERICO),
    ],
)
def test_nombre_grueso_sin_el_agente_completo(agente: str | None, nombre: str) -> None:
    assert nombre_dispositivo(agente) == nombre
    assert len(nombre_dispositivo(agente)) <= 60


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/ejemplo-sintetico",
        "https://updates.push.services.mozilla.com/wpush/v2/ejemplo",
        "https://web.push.apple.com/ejemplo",
        "https://wns2-par02p.notify.windows.com/w/?token=ejemplo",
    ],
)
def test_push_de_servicios_admitidos(endpoint: str) -> None:
    assert push_admitido(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/x",
        "https://fcm.googleapis.com:8443/fcm/send/x",
        "https://usuario@fcm.googleapis.com/fcm/send/x",
        "https://fcm.googleapis.com.ejemplo.cl/x",
        "https://push.apple.com/x",
        "https://evilpush.apple.com.ejemplo.cl/x",
        "https://127.0.0.1/x",
        "https://localhost/x",
        "https://metadata.google.internal/x",
        "https://fcm.googleapis.com/" + "x" * 1024,
        "https://fcm.googleapis.com/a b",
        "https://[::1]/x",
    ],
)
def test_push_fuera_de_la_lista_se_rechaza(endpoint: str) -> None:
    assert not push_admitido(endpoint)


# --- Conservación (decisión 59) -------------------------------------------------------------------------


def test_limites_de_conservacion_salen_del_reloj() -> None:
    limites = limites_conservacion(AHORA)
    assert limites.limite_sesion == AHORA - timedelta(days=30)
    assert limites.limite_dispositivo == AHORA - timedelta(days=90)
    with pytest.raises(ValueError):
        limites_conservacion(datetime(2026, 11, 2))


def test_sesion_se_borra_30_dias_despues_de_vencer_o_revocarse() -> None:
    limites = limites_conservacion(AHORA)
    hace = lambda dias: AHORA - timedelta(days=dias)  # noqa: E731
    assert sesion_se_borra(hace(30), None, limites)
    assert not sesion_se_borra(hace(29), None, limites)
    assert sesion_se_borra(AHORA + timedelta(days=5), hace(31), limites)
    assert not sesion_se_borra(AHORA + timedelta(days=5), hace(29), limites)
    assert not sesion_se_borra(AHORA + timedelta(days=5), None, limites)


def test_dispositivo_se_borra_90_dias_sin_uso_y_sin_sesion_vigente() -> None:
    limites = limites_conservacion(AHORA)
    hace = lambda dias: AHORA - timedelta(days=dias)  # noqa: E731
    assert dispositivo_se_borra(hace(90), hace(200), False, limites)
    assert not dispositivo_se_borra(hace(89), hace(200), False, limites)
    assert not dispositivo_se_borra(hace(120), hace(200), True, limites)
    # Nunca usado: cuenta desde que se creó
    assert dispositivo_se_borra(None, hace(91), False, limites)
    assert not dispositivo_se_borra(None, hace(10), False, limites)


# --- El claim did del access token (decisión 48) ----------------------------------------------------


def test_access_token_lleva_did_y_uno_anterior_no() -> None:
    import uuid

    from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT

    emisor = EmisorJWT(b"c" * 32)
    usuario, dispositivo = uuid.uuid4(), uuid.uuid4()
    con_did = emisor.leer(emisor.emitir(usuario, AHORA, AHORA + timedelta(minutes=15), dispositivo))
    assert (con_did.sub, con_did.did) == (usuario, dispositivo)
    assert emisor.leer(emisor.emitir(usuario, AHORA, AHORA + timedelta(minutes=15))).did is None


def test_did_que_no_es_uuid_invalida_el_token() -> None:
    import jwt

    from app.modules.iam.domain.sesion import TokenInvalido
    from app.modules.iam.infrastructure.tokens_jwt import EmisorJWT

    clave = b"c" * 32
    for did in ("no-uuid", 7):
        token = jwt.encode({"sub": "00000000-0000-0000-0000-000000000001", "iat": 1, "exp": 2, "did": did}, clave,
                           algorithm="HS256")
        with pytest.raises(TokenInvalido):
            EmisorJWT(clave).leer(token)


def test_la_sesion_abierta_no_muestra_el_refresh() -> None:
    import uuid

    from app.modules.iam.application.sesiones import SesionAbierta

    sesion = SesionAbierta(uuid.uuid4(), uuid.uuid4(), "acceso-sintetico", 900, "R" * 43)
    assert "R" * 43 not in repr(sesion) and "acceso-sintetico" not in repr(sesion)
