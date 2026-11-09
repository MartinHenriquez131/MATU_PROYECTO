"""La política de privacidad de las pruebas (MATU-75): la 0.11 publicada, tal cual, con un correo de contacto de
prueba (dominio reservado example.org) en la configuración.

El texto versionado trae el correo real escrito. CORREO_PRUEBAS solo va en correo_contacto, que la API entrega
aparte; la prueba de coincidencia (test_politica.py) usa el valor real de .env.example.

No depende del .env del equipo ni de POLITICA_VERSION: las pruebas de la API la fijan con dependency_overrides.
"""

from datetime import date

from app.modules.iam.application.politica import politica_vigente
from app.modules.iam.infrastructure.textos_politica import texto_publicado

VERSION_PRUEBAS = "0.11"
FECHA_PRUEBAS = date(2026, 11, 9)
CORREO_PRUEBAS = "privacidad@example.org"

# Las variables de entorno equivalentes, para las pruebas que cargan la configuración
ENTORNO_POLITICA = {
    "POLITICA_VERSION": VERSION_PRUEBAS,
    "POLITICA_ACTUALIZADA_EN": FECHA_PRUEBAS.isoformat(),
    "CORREO_PRIVACIDAD": CORREO_PRUEBAS,
}

POLITICA_PRUEBAS = politica_vigente(
    version=VERSION_PRUEBAS, actualizada_en=FECHA_PRUEBAS, correo=CORREO_PRUEBAS, texto_de=texto_publicado
)
