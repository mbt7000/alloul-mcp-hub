from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    port: int = 8007
    log_level: str = "INFO"
