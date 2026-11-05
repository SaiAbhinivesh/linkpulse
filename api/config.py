# api/config.py reads settings from .env

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    base_url: str = "http://localhost:8000"

    redis_url: str
    cache_ttl_seconds: int = 3600

    create_rate_limit_per_minute: int = 10

    kafka_bootstrap_servers: str = "localhost:9092"
    clicks_topic: str = "clicks"

    app_version: str = "dev"


settings = Settings()
