from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    port: int = 8003
    log_level: str = "INFO"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dim: int = 1024
    chunk_size: int = 512
    chunk_overlap: int = 64
