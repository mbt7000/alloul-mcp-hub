from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    port: int = 8004
    log_level: str = "INFO"
