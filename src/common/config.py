import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    sqlalchemy_url = DATABASE_URL if "sslmode=" in DATABASE_URL else f"{DATABASE_URL}?sslmode=require"
else:
    host = os.getenv("POSTGRES_HOST")
    db   = os.getenv("POSTGRES_DB")
    user = os.getenv("POSTGRES_USER")
    pwd  = os.getenv("POSTGRES_PASSWORD")
    sqlalchemy_url = f"postgresql+psycopg://{user}:{pwd}@{host}/{db}?sslmode=require"

class Settings:
    sqlalchemy_url = sqlalchemy_url

settings = Settings()
