from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseSettings_(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me"
    log_level: str = "INFO"
    identity_mcp_url: str = "http://identity:8001"
    audit_mcp_url: str = "http://audit:8004"
