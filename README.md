# job-market-insights/ (Step 1 scaffold)

A minimal, runnable scaffold so you can `git init`, push to GitHub, bring up Postgres, and load a tiny sample dataset end‑to‑end.

---

## 📁 Repository layout

```
job-market-insights/
  README.md
  .gitignore
  .env.example
  pyproject.toml
  uv.lock                 # (optional; created after `uv sync` or you can delete)
  docker-compose.yml
  Makefile
  .github/workflows/ci.yml
  infra/
    init/DDL.sql
    init/SEED_sample.sql
  data/
    raw/mock_jobs.csv
  src/
    common/config.py
    ingestion/load_mock_jobs.py
```

---

## README.md

```md
# Job Market Insights & Skill Gap Analysis (NLP + Web Scraping)

**One‑liner:** Ingest job postings → extract/normalize skills → serve insights & gap analysis via API + dashboard.

## Quickstart (Step 1: Setup & Data)
1. Copy `.env.example` to `.env` and adjust values if needed.
2. Start services: `docker compose up -d`.
3. Verify DB is healthy: `docker compose logs db | tail` (wait until “database system is ready”).
4. Seed tables are created automatically from `infra/init/DDL.sql` and `SEED_sample.sql`.
5. Install Python deps (using **uv**): `pip install uv && uv sync` (or `pip install -r requirements.txt` if you prefer).
6. Load the mock CSV: `make load-mock`.
7. Optional: open Adminer at http://localhost:8080 (server: db, user: ${POSTGRES_USER}, db: ${POSTGRES_DB}).

> Next steps (Step 2+): implement rule‑based skill extraction, normalization, API & app.

## Project structure
See top‑level tree above. Modularized for ETL, NLP, API, and UI.

## Reproducibility
- Dockerized DB + init scripts
- Pinned deps in `pyproject.toml`

## Ethics & Terms
Use public datasets and respect ToS/robots.txt for any scraping. Strip PII from text.
```

---

## .gitignore

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.env

# uv / pip / poetry artifacts
.venv/
.uv/
uv.lock
poetry.lock
*.egg-info/

# VSCode
.vscode/

# OS
.DS_Store
```

---

## .env.example

```bash
# Postgres
POSTGRES_DB=jobs
POSTGRES_USER=jobs_user
POSTGRES_PASSWORD=jobs_pass
POSTGRES_PORT=5432
POSTGRES_HOST=db

# App
APP_ENV=dev
```

---

## pyproject.toml (using uv / PEP 621)

```toml
[project]
name = "job-market-insights"
version = "0.1.0"
description = "End-to-end NLP job market insights & skill gap analysis"
authors = [{ name = "Venkat Sai Subash Panchakarla" }]
requires-python = ">=3.10"
dependencies = [
  "pandas>=2.2",
  "polars>=1.4",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "python-dotenv>=1.0",
  "tqdm>=4.66",
]

[tool.uv]
managed = true

[tool.black]
line-length = 100

[tool.ruff]
line-length = 100
select = ["E","F","B","I"]
```

> If you don’t want **uv**, you can generate a `requirements.txt` later with `uv pip compile` or swap to `pip`.

---

## docker-compose.yml

```yaml
version: "3.9"
services:
  db:
    image: postgres:16
    container_name: jmi_db
    env_file: .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./infra/init:/docker-entrypoint-initdb.d:ro

  adminer:
    image: adminer:4
    container_name: jmi_adminer
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8080:8080"

volumes:
  db_data:
```

---

## Makefile

```makefile
.PHONY: up down logs load-mock psql

up:
	docker compose up -d
	docker compose ps

logs:
	docker compose logs -f db

down:
	docker compose down -v

load-mock:
	uv run python -m src.ingestion.load_mock_jobs data/raw/mock_jobs.csv

psql:
	docker compose exec -it db psql -U $$POSTGRES_USER -d $$POSTGRES_DB
```

---

## .github/workflows/ci.yml

```yaml
name: ci
on:
  push:
    branches: [ main ]
  pull_request:

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run python -V
      - run: uv run python -m pip install ruff black
      - run: ruff check .
      - run: black --check .
```

---

## infra/init/DDL.sql

```sql
-- Core tables
CREATE TABLE IF NOT EXISTS jobs (
  job_id SERIAL PRIMARY KEY,
  title_raw TEXT NOT NULL,
  description_raw TEXT,
  company TEXT,
  source TEXT,
  post_date DATE,
  location_raw TEXT,
  salary_raw TEXT,
  url TEXT,
  collected_at TIMESTAMP DEFAULT NOW()
);

-- For later steps, but created now for convenience
CREATE TABLE IF NOT EXISTS skills (
  skill_id SERIAL PRIMARY KEY,
  skill_raw TEXT NOT NULL,
  skill_norm TEXT,
  confidence NUMERIC,
  extractor_version TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs_skills (
  job_id INT REFERENCES jobs(job_id) ON DELETE CASCADE,
  skill_id INT REFERENCES skills(skill_id) ON DELETE CASCADE,
  PRIMARY KEY (job_id, skill_id)
);

CREATE TABLE IF NOT EXISTS compensation (
  job_id INT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
  min NUMERIC,
  max NUMERIC,
  currency TEXT,
  period TEXT,
  parsed_confidence NUMERIC
);

CREATE TABLE IF NOT EXISTS locations (
  job_id INT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
  city TEXT,
  state TEXT,
  country TEXT,
  lat NUMERIC,
  lon NUMERIC,
  geocode_confidence NUMERIC
);

CREATE TABLE IF NOT EXISTS metadata (
  run_id TEXT PRIMARY KEY,
  git_sha TEXT,
  data_version TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## infra/init/SEED_sample.sql

```sql
-- A few seed rows just to sanity-check the pipeline
INSERT INTO jobs (title_raw, description_raw, company, source, post_date, location_raw, salary_raw, url)
VALUES
 ('Data Scientist', 'We need NLP, Python, and SQL. Experience with scikit-learn and AWS is a plus.', 'Acme AI', 'mock', '2025-09-28', 'New York, NY, USA', '$130k-$160k/yr', 'https://example.com/acme-ds'),
 ('Machine Learning Engineer', 'Deploy ML models to production. PyTorch, Docker, Kubernetes preferred.', 'Nimbus Tech', 'mock', '2025-10-01', 'Remote - US', 'USD 70-90/hour', 'https://example.com/nimbus-mle'),
 ('Data Analyst', 'Strong SQL, Tableau, and Python for EDA. Optional: dbt.', 'RetailCo', 'mock', '2025-09-20', 'Cincinnati, OH, USA', '55k-75k', 'https://example.com/retailco-da');
```

---

## data/raw/mock_jobs.csv

```csv
title_raw,description_raw,company,source,post_date,location_raw,salary_raw,url
Data Scientist,"We need NLP, Python, and SQL. Experience with scikit-learn and AWS is a plus.",Acme AI,mock,2025-09-28,"New York, NY, USA","$130k-$160k/yr",https://example.com/acme-ds
Machine Learning Engineer,"Deploy ML models to production. PyTorch, Docker, Kubernetes preferred.",Nimbus Tech,mock,2025-10-01,Remote - US,"USD 70-90/hour",https://example.com/nimbus-mle
Data Analyst,"Strong SQL, Tableau, and Python for EDA. Optional: dbt.",RetailCo,mock,2025-09-20,"Cincinnati, OH, USA",55k-75k,https://example.com/retailco-da
```

---

## src/common/config.py

```python
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
```

---

## src/ingestion/load_mock_jobs.py

```python
from __future__ import annotations
import sys
import pandas as pd
from sqlalchemy import create_engine
from src.common.config import settings

def main(csv_path: str) -> None:
    engine = create_engine(settings.sqlalchemy_url)
    df = pd.read_csv(csv_path)
    # Basic schema alignment
    expected_cols = [
        "title_raw", "description_raw", "company", "source",
        "post_date", "location_raw", "salary_raw", "url",
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns in CSV: {missing}")

    # Normalize date
    df["post_date"] = pd.to_datetime(df["post_date"], errors="coerce").dt.date

    with engine.begin() as conn:
        df.to_sql("jobs", conn, if_exists="append", index=False)
    print(f"Loaded {len(df)} rows into jobs.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m src.ingestion.load_mock_jobs <path_to_csv>")
    main(sys.argv[1])
```

---

## How to run (local commands)

```bash
# 1) Initialize repo
mkdir -p job-market-insights && cd job-market-insights
# (paste these files)

git init
cp .env.example .env

# 2) Bring up Postgres + Adminer
docker compose up -d

# 3) (Optional) watch DB logs
make logs

# 4) Install deps via uv (or pip)
pip install uv
uv sync

# 5) Load the mock CSV into the DB
make load-mock

# 6) Inspect in Adminer: http://localhost:8080 (server: db, user/pass from .env, db: jobs)
```

---

## What you have after Step 1

* ✅ Dockerized Postgres with schema auto‑created
* ✅ Seed data via SQL and CSV loader
* ✅ CI skeleton (lint/format)
* ✅ Config module + ingestion script

**Next (Step 2):** Implement rule‑based skill extraction (spaCy PhraseMatcher) and persist to `skills` + `jobs_skills`.


## Slight change in README


## Step 5
### Adding dynamic insights.