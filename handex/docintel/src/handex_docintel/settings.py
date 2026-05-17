from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    reasoning_mcp_url: str = "http://reasoning:8002"
    port: int = 8008
    log_level: str = "INFO"
    storage_base_path: str = "/app/storage"
