from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

URL_BD = "postgresql://matu_owner:matu_password_local@localhost:5432/matu_db"

engine = create_engine(URL_BD)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()