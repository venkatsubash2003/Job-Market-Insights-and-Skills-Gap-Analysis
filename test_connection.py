import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

url = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}/{os.getenv('POSTGRES_DB')}?sslmode=require"

print(f"Connecting to: {url}")
try:
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM jobs"))
        print(f"Rows in jobs table: {result.scalar()}")
except Exception as e:
    print("❌ Error connecting to the database:")
    print(e)
