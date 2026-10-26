"""Настройки оболочки (аналог appsettings.json).

Значения берутся из переменных окружения с префиксом TIMESLICES_; по умолчанию —
локальная разработка. pydantic-settings не используется (его нет в requirements.txt):
хватает pydantic.BaseModel и os.environ.
"""
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent
DEV_SECRET_KEY = "dev-only-secret-key"


class Settings(BaseModel):
    # Development — dev-пользователь создаётся при старте и входит автоматически.
    environment: str = "Development"
    database_url: str = f"sqlite:///{ROOT_DIR / 'app.db'}"
    content_dir: Path = ROOT_DIR / "content"
    # Ключ подписи cookie-сессии; dev-значение допустимо только в Development.
    secret_key: str = DEV_SECRET_KEY
    dev_user_name: str = "dev"

    @property
    def is_development(self) -> bool:
        return self.environment == "Development"


def _from_env() -> Settings:
    values = {}
    for field in Settings.model_fields:
        env = os.environ.get(f"TIMESLICES_{field.upper()}")
        if env is not None:
            values[field] = env
    return Settings(**values)


@lru_cache
def get_settings() -> Settings:
    return _from_env()
