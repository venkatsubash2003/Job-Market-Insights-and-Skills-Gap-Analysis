import os
from dotenv import load_dotenv
load_dotenv()

def to_psycopg(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    sqlalchemy_url = to_psycopg(DATABASE_URL)
    if "sslmode=" not in sqlalchemy_url:
        sep = "&" if "?" in sqlalchemy_url else "?"
        sqlalchemy_url = f"{sqlalchemy_url}{sep}sslmode=require"
else:
    host = os.getenv("POSTGRES_HOST")
    db   = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    pwd  = os.getenv("POSTGRES_PASSWORD")
    sqlalchemy_url = f"postgresql+psycopg://{user}:{pwd}@{host}/{db}?sslmode=require"

class Settings:
    sqlalchemy_url = sqlalchemy_url

settings = Settings()
