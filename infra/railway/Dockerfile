# MATU · Imagen de la API para staging en Railway (MATU-25, ADR-019)
#
# Se construye desde la raíz del repositorio (contexto "."), como lo hace Railway con
# infra/railway/railway.json:
#   docker build -f infra/railway/Dockerfile .
#
# Copia solo lo que necesita, archivo por archivo: nunca el .env, node_modules ni las pruebas.
# Arranca con python -m app.servidor: Uvicorn en $PORT, sin log de acceso, y la IP del cliente desde
# X-Forwarded-For solo si la conexión viene de FORWARDED_ALLOW_IPS (nunca '*'), con PROXY_SALTOS
# (app/core/proxy.py; el proxy de Uvicorn queda apagado).
# Las migraciones no corren aquí: las corre el preDeployCommand de railway.json, como matu_owner.

# --- 1. La página del relevo (web/, ADR-026) ------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/index.html web/tsconfig.json web/vite.config.ts ./
COPY web/src ./src
COPY web/doble ./doble
RUN npm run build

# --- 2. La API ------------------------------------------------------------------------------------------
FROM python:3.12-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Si falta la variable en Railway, la API no queda como "local": sin /docs y sin KEK sintética
    ENTORNO=produccion \
    # app/core/config.py busca el build en <raíz>/web/dist; aquí la raíz es /app
    WEB_DIST=/app/web/dist

WORKDIR /app/backend

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/db ./db
COPY --from=web /web/dist /app/web/dist
# Solo para fijar FORWARDED_ALLOW_IPS a mano, por railway ssh (ver infra/railway/README.md)
COPY infra/railway/pares_tcp.py /app/infra/railway/pares_tcp.py
# La semilla de demo (decisión 105): se corre a mano por railway ssh, solo con datos sintéticos
COPY infra/semillas/demo.py /app/infra/semillas/demo.py

# Usuario sin privilegios y sin shell de inicio de sesión. El código queda de root, solo lectura para él
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin matu
USER matu

EXPOSE 8080
CMD ["python", "-m", "app.servidor"]
