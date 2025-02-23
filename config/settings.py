from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from openai import OpenAI
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "Asistente Altamirano"
    port: int = Field(default=8080, env='PORT')
    openai_api_key: str = Field(..., env='OPENAI_API_KEY')
    tokko_api_key: str = Field(..., env='TOKKO_API_KEY')
    tokko_base_url: str = Field(default="https://tokkobroker.com/api/v1", env='TOKKO_BASE_URL')
    openai_client: Optional[OpenAI] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_configured(self) -> bool:
        return bool(
            self.openai_api_key and 
            self.tokko_api_key and 
            self.tokko_base_url
        )

    def initialize_openai(self):
        if not self.openai_client:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        return self.openai_client

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    if not settings.is_configured:
        raise ValueError("Missing required environment variables")
    return settings

settings = get_settings()