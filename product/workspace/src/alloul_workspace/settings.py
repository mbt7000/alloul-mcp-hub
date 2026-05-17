from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    redis_url: str = "redis://localhost:6379/0"
    alloulq_backend_url: str = "http://alloulq-backend:3000"
    handex_backend_url: str = "http://handex-backend:4000"
    port: int = 8006
    log_level: str = "INFO"
