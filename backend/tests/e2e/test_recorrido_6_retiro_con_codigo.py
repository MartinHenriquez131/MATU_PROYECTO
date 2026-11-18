"""MATU-80 · Recorrido 6 de MATU-64: retirar con código en el comercio y ver el pedido retirado.

Desde el pedido pagado del recorrido 5: el comercio simulado ve su parte solo por su referencia, la prepara y la deja
lista; operación genera el código de retiro con la ruta de MATU-63; quien retira lo dicta, el comercio lo valida, y la
familia ve su parte retirada en el seguimiento y, cuando operación lo entrega, el pedido entregado en «Tus pedidos».

La cuenta del comercio y la de operación las crea la fixture ``despacho`` como superusuario: ninguna ruta las crea.
Operación entra hoy con su contraseña y ``usuario.es_operacion`` (más un secreto de MFA sintético, que exige el CHECK
usuario_operacion_mfa).
[PENDIENTE: MATU-81 pide MFA en las rutas de operación (hallazgo H2 de TESTER 16-11). Cuando se fusione, este
recorrido tiene que entrar como operación con el segundo factor, y ``Despacho.operacion`` cambia con él.]
"""

import re

import pytest

from tests.base_datos import requiere_base
from tests.e2e.conftest import Recorrido

pytestmark = [requiere_base, pytest.mark.e2e, pytest.mark.rf("RF-20"), pytest.mark.rf("RF-26")]


def test_recorrido_retiro_con_codigo(recorrido: Recorrido) -> None:
    r = recorrido
    d = r.d
    f = r.familia()
    pedido, _, total = r.pagar_desde_la_lista(f)

    # Dado el comercio, que ve su parte del pedido pagado solo con su referencia, sin nada de la familia
    partes = d.comercio("uno", "GET", "/partes")
    assert partes.status_code == 200, partes.text
    [parte] = partes.json()["partes"]
    assert re.fullmatch(r"[2-9A-HJKMNP-Z]{6}", parte["referencia"])
    assert (parte["estado"], parte["estado_codigo"]) == ("enviada", "sin_codigo")
    assert "Elena" not in partes.text and "Calle de Prueba" not in partes.text
    vista = d.comercio("uno", "GET", f"/partes/{parte['id']}")
    assert vista.status_code == 200, vista.text

    # Cuando la prepara: «Empezar a preparar», «Lo tengo» en su producto y «Listo para retirar»
    preparando = d.comercio("uno", "POST", f"/partes/{parte['id']}/preparar", **{"If-Match": vista.headers["ETag"]})
    assert preparando.status_code == 200, preparando.text
    [linea] = preparando.json()["lineas"]
    marcada = d.comercio(
        "uno",
        "PUT",
        f"/partes/{parte['id']}/lineas/{linea['id']}",
        {"estado": "preparada"},
        **{"If-Match": preparando.headers["ETag"]},
    )
    assert marcada.status_code == 200, marcada.text
    lista = d.comercio("uno", "POST", f"/partes/{parte['id']}/listo", **{"If-Match": marcada.headers["ETag"]})
    assert lista.status_code == 200, lista.text
    assert lista.json()["estado"] == "lista"
    [fila] = r.tus_pedidos(f)
    assert fila["estado"] == "listo_retiro"

    # Y operación ve en su lista la parte lista y sin código, y genera el código de retiro, que se entrega una sola vez
    # y no se guarda en caché
    en_curso = d.operacion("GET", "/pedidos")
    assert en_curso.status_code == 200, en_curso.text
    [de_operacion] = [p for p in en_curso.json()["pedidos"] if p["id"] == pedido["id"]]
    [parte_operacion] = de_operacion["partes"]
    assert (parte_operacion["id"], parte_operacion["estado"], parte_operacion["estado_codigo"]) == (
        parte["id"],
        "lista",
        "sin_codigo",
    )
    generado = d.operacion("POST", f"/partes/{parte_operacion['id']}/codigo")
    assert generado.status_code == 201, generado.text
    assert generado.headers["cache-control"] == "no-store"
    codigo = str(generado.json()["codigo"])
    assert re.fullmatch(r"\d{6}", codigo)

    # Entonces un código errado no se acepta, y el correcto deja la parte retirada
    errado = f"{(int(codigo) + 1) % 1_000_000:06d}"
    no_es = d.comercio("uno", "POST", f"/partes/{parte['id']}/validar-codigo", {"codigo": errado})
    assert (no_es.json()["resultado"], no_es.json()["intentos_restantes"]) == ("no_es", 4)
    correcto = d.comercio("uno", "POST", f"/partes/{parte['id']}/validar-codigo", {"codigo": codigo})
    assert correcto.status_code == 200, correcto.text
    assert correcto.json()["resultado"] == "correcto"
    assert (correcto.json()["parte"]["estado"], correcto.json()["parte"]["estado_codigo"]) == ("retirada", "usado")

    # Y la familia ve su parte retirada en el seguimiento. El pedido se sigue leyendo «Listo para salir»
    # (listo_retiro): «Tus pedidos» agrupa retirado con listo_retiro (MATU-92, lenguaje.md 38)
    seguimiento = r.pedir(f, "GET", f"/v1/pedidos/{pedido['id']}/seguimiento")
    assert seguimiento.status_code == 200, seguimiento.text
    [parte_familia] = seguimiento.json()["partes"]
    assert parte_familia["estado"] == "retirada"
    tus = r.de_la_persona(f, "GET", "/pedidos")
    [fila] = tus.json()["items"]
    assert (fila["pedido_id"], fila["estado"], fila["total"], fila["devuelto"]) == (
        pedido["id"],
        "listo_retiro",
        total,
        0,
    )
    for texto in (tus.text, seguimiento.text):
        assert codigo not in texto and parte["referencia"] not in texto

    # Y cuando operación lo lleva y lo entrega, en «Tus pedidos» aparece entregado
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino").json()["estado"] == "en_ruta"
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").json()["estado"] == "entregado"
    [fila] = r.tus_pedidos(f)
    assert (fila["estado"], fila["total"], fila["devuelto"]) == ("entregado", total, 0)
    assert fila["entregado_en"] is not None

    # Y el código no sirve dos veces, ni llega a los logs
    assert (
        d.comercio("uno", "POST", f"/partes/{parte['id']}/validar-codigo", {"codigo": codigo}).json()["resultado"]
        == "usado"
    )
    logs = r.logs()
    assert logs.strip()
    assert codigo not in logs and errado not in logs
