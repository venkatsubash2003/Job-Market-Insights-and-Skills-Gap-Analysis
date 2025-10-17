from __future__ import annotations
from sqlalchemy import create_engine, text
from src.common.config import settings

def refresh_materialized_views() -> None:
    engine = create_engine(settings.sqlalchemy_url)
    with engine.begin() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_skill_counts"))
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_monthly_skill_counts"))
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_skill_cooccurrence"))

def main() -> None:
    print("Refreshing analytics materialized views...")
    refresh_materialized_views()
    print("Done.")

if __name__ == "__main__":
    main()
