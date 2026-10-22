"""Piezas transversales a todos los módulos: puertos comunes, eventos, outbox y auditoría.

Cualquier módulo puede importar app.shared. app.shared nunca importa app.modules
(arquitectura, sección 6.4, lo verifica tests/test_arquitectura.py).
"""
