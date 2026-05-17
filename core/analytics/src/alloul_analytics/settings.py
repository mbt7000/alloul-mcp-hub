from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    redis_url: str = "redis://localhost:6379/0"
    port: int = 8005
    log_level: str = "INFO"
    cache_ttl_seconds: int = 900
