from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "exchange-game"
    database_url: str = "sqlite+aiosqlite:///./app.db"
    echo_sql: bool = False
    api_key: str = "changeme"
    base_task_cost: int = 100
    cost_growth_per_minute: int = 5
    exchange_step_percent: int = 10
    solve_discount_percent: int = 10
    attempt_limit: int = 6
    wrong_attempt_growth_percent: int = 3

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
