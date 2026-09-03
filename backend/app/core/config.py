from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "IPO Intelligence API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./ipo_intelligence.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "local-development-secret-change-me"
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 14
    cors_origins: str = "http://localhost:3000"
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    groq_api_key: str = ""
    environment: str = "development"
    upload_dir: str = "./data/uploads"
    task_eager: bool = True

    def model_post_init(self, __context) -> None:
        if self.environment == "production" and self.jwt_secret == "local-development-secret-change-me":
            raise ValueError("In production, a secure JWT_SECRET must be provided.")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def ensure_storage(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
