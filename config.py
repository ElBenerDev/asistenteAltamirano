from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    openai_api_key: str
    environment: str = "development"
    max_tokens: int = 150
    temperature: float = 0.7
    log_level: str = "INFO"
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"

settings = Settings()