import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sanket - Rural B2B Intelligence Engine"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sanket-super-secret-key-change-in-production-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database: fallback to local SQLite file sanket.db if DATABASE_URL is not set or postgres unavailable
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sanket.db")
    
    # AI / LLM Configuration
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    FREE_LLM_API_KEY: str = os.getenv("FREE_LLM_API_KEY", "")

    class Config:
        case_sensitive = True

settings = Settings()
