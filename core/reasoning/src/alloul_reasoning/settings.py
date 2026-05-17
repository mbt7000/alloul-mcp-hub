from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    ollama_base_url: str = "http://ollama:11434"
    database_url: str = "postgresql+asyncpg://alloul:localdev@localhost:5432/alloul_hub"
    redis_url: str = "redis://localhost:6379/0"
    port: int = 8002
    log_level: str = "INFO"
    claude_model: str = "claude-opus-4-7"
    claude_input_cost_per_mtok: int = 15_000_000
    claude_output_cost_per_mtok: int = 75_000_000
    deepseek_input_cost_per_mtok: int = 140_000
    deepseek_output_cost_per_mtok: int = 280_000
