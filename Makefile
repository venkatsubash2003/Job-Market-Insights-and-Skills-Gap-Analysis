# Pin the interpreter you want to use:
PYTHON := /Library/Frameworks/Python.framework/Versions/3.11/bin/python3

.PHONY: up down logs load-mock psql install-spacy-model extract-skills

up:
	docker compose up -d
	docker compose ps

logs:
	docker compose logs -f db

down:
	docker compose down -v

load-mock:
	$(PYTHON) -m src.ingestion.load_mock_jobs data/raw/mock_jobs.csv

psql:
	docker compose exec -it db psql -U $$POSTGRES_USER -d $$POSTGRES_DB

install-spacy-model:
	$(PYTHON) -m spacy download en_core_web_sm

extract-skills:
	$(PYTHON) -m src.nlp.skill_extraction

.PHONY: analytics-init analytics-refresh top-skills top-trends top-pairs

# Create the materialized views (run once or after SQL changes)
analytics-init:
	cat infra/analytics/ANALYTICS.sql | docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f -'

# Refresh the views after new data/extraction
analytics-refresh:
	$(PYTHON) -m src.analytics.aggregates

# Convenience queries
top-skills:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT skill, job_count, last_seen FROM mv_skill_counts ORDER BY job_count DESC, skill LIMIT 20;"'

top-trends:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT to_char(month, '\''YYYY-MM'\'') AS month, skill, job_count FROM mv_monthly_skill_counts ORDER BY month DESC, job_count DESC LIMIT 50;"'

top-pairs:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT skill_a, skill_b, pair_count FROM mv_skill_cooccurrence ORDER BY pair_count DESC, skill_a, skill_b LIMIT 20;"'

.PHONY: app
app:
	PYTHONPATH="$(CURDIR)" streamlit run "src/app/dashboard.py"

