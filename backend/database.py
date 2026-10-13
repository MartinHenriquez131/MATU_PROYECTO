"""Conexión de la aplicación a la base.

La API se conecta como matu_app, que no es dueño de ninguna tabla. Por eso las
políticas RLS lo alcanzan siempre (arquitectura, sección 7.7). La URL se lee de
la variable DATABASE_URL, nunca del repositorio.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

URL_BD = os.environ.get("DATABASE_URL", "")

engine = create_engine(URL_BD) if URL_BD else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
