from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me"
    port: int = 8001
    log_level: str = "INFO"
    employee_code_prefix: str = "EMP"
