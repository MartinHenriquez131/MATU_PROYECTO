"""La política de privacidad de las pruebas (MATU-75): la 0.11 publicada, con un correo, un proveedor y un país de
prueba (dominio reservado example.org). Esos valores viven solo aquí, en la configuración de las pruebas: nunca en el
texto versionado.

No depende del .env del equipo ni de POLITICA_VERSION: las pruebas de la API la fijan con dependency_overrides.
"""

from datetime import date

from app.modules.iam.application.politica import politica_vigente
from app.modules.iam.infrastructure.textos_politica import plantilla_publicada

VERSION_PRUEBAS = "0.11"
FECHA_PRUEBAS = date(2026, 11, 9)
CORREO_PRUEBAS = "privacidad@example.org"
PROVEEDOR_PRUEBAS = "Correo de Prueba (correo.example.org)"
PAIS_PRUEBAS = "País de Prueba"

# Las variables de entorno equivalentes, para las pruebas que cargan la configuración
ENTORNO_POLITICA = {
    "POLITICA_VERSION": VERSION_PRUEBAS,
    "POLITICA_ACTUALIZADA_EN": FECHA_PRUEBAS.isoformat(),
    "CORREO_PRIVACIDAD": CORREO_PRUEBAS,
    "PROVEEDOR_CORREO_PRIVACIDAD": PROVEEDOR_PRUEBAS,
    "PAIS_PROVEEDOR_CORREO": PAIS_PRUEBAS,
}

POLITICA_PRUEBAS = politica_vigente(
    version=VERSION_PRUEBAS,
    actualizada_en=FECHA_PRUEBAS,
    correo=CORREO_PRUEBAS,
    plantilla_de=plantilla_publicada,
    proveedor_correo=PROVEEDOR_PRUEBAS,
    pais_proveedor_correo=PAIS_PRUEBAS,
)
