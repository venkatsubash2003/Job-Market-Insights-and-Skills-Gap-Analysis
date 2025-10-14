from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv("POSTGRES_HOST", "localhost")
    db_port: int = int(os.getenv("POSTGRES_PORT", 5432))
    db_user: str = os.getenv("POSTGRES_USER", "jobs_user")
    db_pass: str = os.getenv("POSTGRES_PASSWORD", "jobs_pass")
    db_name: str = os.getenv("POSTGRES_DB", "jobs")

    @property
    def sqlalchemy_url(self) -> str:
        return f"postgresql+psycopg://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
