"""MATU-57 · Casos de uso de la recuperación, sin base (RF-37).

La solicitud cuenta los límites antes de buscar la cuenta, y con una cuenta inexistente no abre
transacciones, no envía ni audita.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from app.modules.iam.application.ports import ContadoresNoDisponibles, CredencialGuardada
from app.modules.iam.application.recuperacion import Peppers, cambiar_contrasena_con_codigo, solicitar_recuperacion
from app.modules.iam.domain.recuperacion import Canal, CodigoInvalido
from app.modules.iam.infrastructure.enviador_simulado import EnviadorSimulado
from tests.dobles.contadores_en_memoria import ContadoresEnMemoria
from tests.dobles.recuperacion_en_memoria import AlmacenCodigosEnMemoria, ContadoresEnvioEnMemoria
from tests.dobles.reloj_fijo import RelojFijo

pytestmark = pytest.mark.rf("RF-37")

PEPPERS = Peppers(email=b"e" * 32, limites=b"l" * 32, recuperacion=b"r" * 32)


@dataclass
class RepositorioVacio:
    buscados: int = 0

    def crear(self, usuario: object) -> None:  # pragma: no cover
        raise NotImplementedError

    def buscar_credencial(self, email_hash: bytes) -> CredencialGuardada | None:
        self.buscados += 1
        return None


class UnidadQueNoSeUsa:
    def transaccion(self, usuario_id: object) -> object:
        raise AssertionError("no debe abrir transacciones con una cuenta inexistente")


def _solicitar(reloj: RelojFijo, repositorio: RepositorioVacio, envios: ContadoresEnvioEnMemoria,
               enviador: EnviadorSimulado, almacen: AlmacenCodigosEnMemoria) -> None:
    unidad: Any = UnidadQueNoSeUsa()
    solicitar_recuperacion(
        email="Nadie@Ejemplo.cl ", solo_correo=False, ip="192.0.2.1", peppers=PEPPERS, repositorio=repositorio,
        unidad=unidad, almacen=almacen, envios=envios, enviador=enviador, reloj=reloj,
    )


def test_cuenta_inexistente_cuenta_el_limite_y_no_envia(reloj_fijo: RelojFijo) -> None:
    repositorio, envios, enviador = RepositorioVacio(), ContadoresEnvioEnMemoria(reloj_fijo), EnviadorSimulado()
    almacen = AlmacenCodigosEnMemoria(reloj_fijo)
    _solicitar(reloj_fijo, repositorio, envios, enviador, almacen)
    assert repositorio.buscados == 1
    assert enviador.enviados == [] and almacen.datos == {}
    # La IP y el email quedan contados por su huella, nunca en claro
    assert len(envios.datos) == 2
    assert all("192.0.2.1" not in h and "nadie" not in h for h in envios.datos)
    # Dentro de los 60 s ni siquiera busca la cuenta: el límite no depende de que exista
    _solicitar(reloj_fijo, repositorio, envios, enviador, almacen)
    assert repositorio.buscados == 1
    reloj_fijo.avanzar(timedelta(seconds=61))
    _solicitar(reloj_fijo, repositorio, envios, enviador, almacen)
    assert repositorio.buscados == 2


def test_redis_caido_lanza_y_no_busca(reloj_fijo: RelojFijo) -> None:
    repositorio = RepositorioVacio()
    with pytest.raises(ContadoresNoDisponibles):
        _solicitar(reloj_fijo, repositorio, ContadoresEnvioEnMemoria(reloj_fijo, caido=True), EnviadorSimulado(),
                   AlmacenCodigosEnMemoria(reloj_fijo))
    assert repositorio.buscados == 0


@dataclass
class AuditoriaFalsa:
    entradas: list[Any] = field(default_factory=list)

    def registrar(self, entrada: Any) -> None:
        self.entradas.append(entrada)


class _Tx:
    def __init__(self, auditoria: AuditoriaFalsa) -> None:
        self.auditoria = auditoria

    def __enter__(self) -> "_Tx":
        return self

    def __exit__(self, *args: object) -> None:
        return None


@dataclass
class UnidadSoloAuditoria:
    auditoria: AuditoriaFalsa = field(default_factory=AuditoriaFalsa)

    def transaccion(self, usuario_id: object) -> _Tx:
        return _Tx(self.auditoria)


def test_cambiar_sin_cuenta_falla_igual_y_suma_fallos(reloj_fijo: RelojFijo) -> None:
    contadores, unidad = ContadoresEnMemoria(), UnidadSoloAuditoria()
    hasher: Any = None
    with pytest.raises(CodigoInvalido):
        cambiar_contrasena_con_codigo(
            email="nadie@ejemplo.cl", codigo="123456", contrasena_nueva="x" * 12, ip="192.0.2.1", peppers=PEPPERS,
            hasher=hasher, repositorio=RepositorioVacio(), unidad=unidad,  # type: ignore[arg-type]
            almacen=AlmacenCodigosEnMemoria(reloj_fijo), contadores=contadores, enviador=EnviadorSimulado(),
            reloj=reloj_fijo,
        )
    assert len(contadores.datos) == 2
    [entrada] = unidad.auditoria.entradas
    assert entrada.accion.value == "cuenta.recuperar_verificar_fallido"
    assert entrada.entidad_id is None and entrada.grupo_id is None


def test_enviador_simulado_escribe_el_registro_de_desarrollo(tmp_path: Path) -> None:
    archivo = tmp_path / ".dev" / "envios.jsonl"
    enviador = EnviadorSimulado(archivo)
    enviador.enviar(Canal.CORREO, "persona@ejemplo.cl", "MATU: prueba")
    assert "persona@ejemplo.cl" in archivo.read_text(encoding="utf-8")
    assert "persona@ejemplo.cl" not in repr(enviador) + repr(enviador.enviados)
