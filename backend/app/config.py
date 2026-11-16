from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
NAME_PREFIX = "test_plaskin_"


class Settings(BaseSettings):
    keitaro_base_url: str = "https://tlgk.host"
    keitaro_api_key: str = ""
    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return "sqlite:///" + (DATA_DIR / "app.db").as_posix()


settings = Settings()
