from pydantic_settings import BaseSettings
from pydantic import SecretStr, Field
from typing import Optional, Any
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI
import os
from functools import lru_cache

load_dotenv()
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    app_name: str = "Asistente Inmobiliario Altamirano"
    openai_api_key: SecretStr = os.getenv("OPENAI_API_KEY")
    tokko_api_key: SecretStr = os.getenv("TOKKO_API_KEY")
    tokko_base_url: str = os.getenv("TOKKO_BASE_URL", "https://www.tokkobroker.com/api/v1")
    debug: bool = False
    
    # Add fields for clients
    openai_client: Optional[Any] = None
    tokko_client: Optional[Any] = None

    class Config:
        arbitrary_types_allowed = True
        env_file = ".env"
        env_file_encoding = "utf-8"

    async def initialize_openai(self):
        """Initialize OpenAI client"""
        try:
            self.openai_client = AsyncOpenAI(
                api_key=self.openai_api_key.get_secret_value(),
                timeout=60.0
            )
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    async def initialize_tokko(self):
        """Initialize Tokko client"""
        try:
            from app.services.tokkoClient import TokkoClient
            self.tokko_client = TokkoClient()
            logger.info("Tokko client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Tokko client: {e}")
            raise

@lru_cache()
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as e:
        print(f"Error loading settings: {e}")
        raise

settings = get_settings()