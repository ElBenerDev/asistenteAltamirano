# db_config.py
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    DATABASE_URL = "postgresql://neondb_owner:npg_mTJhLZ5FtRA3@ep-little-term-a8x9ojn0-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
    logger.info("Configurando conexión a la base de datos...")
    
    engine = create_engine(DATABASE_URL)
    logger.info("Motor de base de datos creado")
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Sesión de base de datos configurada")

except Exception as e:
    logger.error(f"Error al configurar la base de datos: {str(e)}")
    raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()