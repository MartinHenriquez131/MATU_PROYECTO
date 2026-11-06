"""MATU-41 · La preferencia guarda solo el canal que la persona cambia (decisión 111, aprobada por Jorge tras la
revisión de cierre del analista). RF-39, contra PostgreSQL.

Sin fila guardada, cada canal sigue el valor por omisión del rol en cada grupo (decisión 78). Si el PUT
guardara los dos canales, una persona admin en un grupo y observadora en otro, que solo apaga el push,
quedaría con el correo activado también en el grupo donde es observadora, sin haberlo elegido.
"""

from collections.abc import Iterator

import pytest

from app.shared.outbox import Hecho
from tests.base_datos import requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import Fabrica, FamiliaCreada, UsuarioCreado
from tests.modules.conftest import EntornoIam
from tests.modules.notifications.conftest import INICIO, EntornoAvisos, filas

pytestmark = [requiere_base, pytest.mark.rf("RF-39")]

RUTA = "/v1/yo/avisos"


@pytest.fixture
def fabrica_iam(entorno_iam: EntornoIam) -> Iterator[Fabrica]:
    fabrica = Fabrica(pepper=entorno_iam.pepper)
    try:
        yield fabrica
    finally:
        fabrica.limpiar()


def _put(iam: EntornoIam, usuario: UsuarioCreado, cuerpo: dict[str, bool]) -> dict[str, bool]:
    sesion = iam.iniciar_sesion(email=usuario.email, contrasena=usuario.contrasena)
    cabeceras = {"Authorization": f"Bearer {sesion.json()['access_token']}"}
    respuesta = iam.cliente.put(RUTA, json=cuerpo, headers=cabeceras)
    assert respuesta.status_code == 200, respuesta.text
    resultado: dict[str, bool] = respuesta.json()
    return resultado


def _guardadas(usuario: UsuarioCreado) -> dict[str, bool]:
    return dict(filas(
        "SELECT canal, activo FROM preferencia_notificacion WHERE usuario_id = %s AND tipo_evento = 'quiebre_proximo'",
        usuario.id,
    ))


def _grupo_con(fabrica: Fabrica, usuario: UsuarioCreado, rol: str) -> FamiliaCreada:
    """Un grupo de otra persona, con la autorización de consumo vigente, donde ``usuario`` es ``rol``."""
    familia = fabrica.familia(miembros=())
    fabrica.membresia(familia.grupo, usuario, rol)
    fabrica.autorizacion_consumo(familia.persona, otorgante=familia.admin, otorgado_en=INICIO)
    return familia


def test_admin_en_a_y_observador_en_b_que_apaga_el_push_no_recibe_correos_de_b(
    entorno_iam: EntornoIam, fabrica_iam: Fabrica
) -> None:
    grupo_a = fabrica_iam.familia(miembros=())
    persona = grupo_a.admin
    grupo_b = _grupo_con(fabrica_iam, persona, "observador")

    # El GET dice true/true (es admin en A); la persona solo apaga el push
    assert _put(entorno_iam, persona, {"correo": True, "push": False}) == {"correo": True, "push": False}

    # Solo se guarda el canal que cambió: el correo queda sin elegir
    assert _guardadas(persona) == {"push": False}

    # Llega un aviso del grupo B: como observadora y sin haber elegido el correo, no lo recibe
    e = EntornoAvisos(fabrica=fabrica_iam, reloj=RelojFijo(INICIO))
    avisado = e.avisar(grupo_b)
    assert isinstance(e.consumir(avisado), Hecho)
    assert persona.id not in {u for u, _ in e.avisos(grupo_b)}
    assert persona.id not in {x.usuario_id for x in e.correo.enviados}
    # El admin de B sí recibe
    assert (grupo_b.admin.id, "correo") in e.avisos(grupo_b)


def test_observador_que_activa_el_correo_si_recibe(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    persona = fabrica_iam.usuario()
    grupo = _grupo_con(fabrica_iam, persona, "observador")

    # El GET dice false/false; activa solo el correo
    assert _put(entorno_iam, persona, {"correo": True, "push": False}) == {"correo": True, "push": False}
    assert _guardadas(persona) == {"correo": True}

    e = EntornoAvisos(fabrica=fabrica_iam, reloj=RelojFijo(INICIO))
    assert isinstance(e.consumir(e.avisar(grupo)), Hecho)
    assert e.avisos(grupo)[(persona.id, "correo")] == ("enviada", None)


def test_un_canal_ya_guardado_se_actualiza_aunque_coincida_con_el_rol(
    entorno_iam: EntornoIam, fabrica_iam: Fabrica
) -> None:
    admin = fabrica_iam.familia(miembros=()).admin
    _put(entorno_iam, admin, {"correo": False, "push": True})
    assert _guardadas(admin) == {"correo": False}
    # Vuelve a encender el correo: ya había fila, se guarda true (la elección es de la persona)
    assert _put(entorno_iam, admin, {"correo": True, "push": True}) == {"correo": True, "push": True}
    assert _guardadas(admin) == {"correo": True}


def test_la_preferencia_ajena_sigue_inaccesible(entorno_iam: EntornoIam, fabrica_iam: Fabrica) -> None:
    carmen = fabrica_iam.familia(miembros=()).admin
    rodrigo = fabrica_iam.familia(miembros=()).admin
    _put(entorno_iam, carmen, {"correo": False, "push": False})
    # Rodrigo guarda lo suyo y la de Carmen no cambia
    assert _put(entorno_iam, rodrigo, {"correo": False, "push": True}) == {"correo": False, "push": True}
    assert _guardadas(carmen) == {"correo": False, "push": False}
    assert _guardadas(rodrigo) == {"correo": False}
