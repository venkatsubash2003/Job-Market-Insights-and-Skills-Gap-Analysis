from __future__ import annotations
import sys
import pandas as pd
from sqlalchemy import create_engine
from src.common.config import settings


def main(csv_path: str) -> None:
    engine = create_engine(settings.sqlalchemy_url)
    df = pd.read_csv(csv_path)
    expected_cols = [
        "title_raw",
        "description_raw",
        "company",
        "source",
        "post_date",
        "location_raw",
        "salary_raw",
        "url",
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns in CSV: {missing}")

    df["post_date"] = pd.to_datetime(df["post_date"], errors="coerce").dt.date

    with engine.begin() as conn:
        df.to_sql("jobs", conn, if_exists="append", index=False)
    print(f"Loaded {len(df)} rows into jobs.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m src.ingestion.load_mock_jobs <path_to_csv>")
    main(sys.argv[1])
