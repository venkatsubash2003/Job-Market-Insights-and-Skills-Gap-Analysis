from __future__ import annotations
from sqlalchemy import create_engine, text
from src.common.config import settings
from src.parsing.salary_parse import parse_salary

def main():
    eng = create_engine(settings.sqlalchemy_url)
    with eng.begin() as conn:
        rows = conn.execute(text("""
            SELECT job_id, salary_raw
            FROM jobs
            WHERE salary_raw IS NOT NULL AND salary_raw <> ''
        """)).mappings().all()

        upserts = 0
        for r in rows:
            parsed = parse_salary(r["salary_raw"] or "")
            conn.execute(text("""
                INSERT INTO compensation (job_id, min, max, currency, period, parsed_confidence)
                VALUES (:job_id, :min, :max, :currency, :period, :conf)
                ON CONFLICT (job_id) DO UPDATE SET
                    min = EXCLUDED.min,
                    max = EXCLUDED.max,
                    currency = EXCLUDED.currency,
                    period = EXCLUDED.period,
                    parsed_confidence = EXCLUDED.parsed_confidence
            """), {
                "job_id": r["job_id"],
                "min": parsed.min,
                "max": parsed.max,
                "currency": parsed.currency,
                "period": parsed.period,
                "conf": parsed.confidence,
            })
            upserts += 1
    print(f"compensation upserts: {upserts}")

if __name__ == "__main__":
    main()
