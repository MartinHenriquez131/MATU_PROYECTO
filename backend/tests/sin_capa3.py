"""Plugin de pytest que quita la capa 3 antes de cargar cualquier prueba (MATU-40, ADR-002).

    python -m pytest -p tests.sin_capa3 <pruebas de las capas 1 y 2>

Lo usa tests/test_capa3_desacoplable.py en un intérprete aparte. No lo cargues en la corrida normal:
bloquea la capa 3 para todo el proceso.
"""

from tests.capa3 import bloquear

bloquear()
