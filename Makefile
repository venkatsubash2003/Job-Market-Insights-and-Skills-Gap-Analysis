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

.PHONY: enrich-salary enrich-locations salary-by-skill jobs-by-country

enrich-salary:
	$(PYTHON) -m src.pipeline.enrich_compensation

enrich-locations:
	$(PYTHON) -m src.pipeline.enrich_locations

salary-by-skill:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT s.skill_norm AS skill, ROUND(AVG(c.min)) AS avg_min, ROUND(AVG(c.max)) AS avg_max, COUNT(*) AS n FROM jobs_skills js JOIN skills s ON s.skill_id=js.skill_id JOIN compensation c ON c.job_id=js.job_id WHERE c.min IS NOT NULL AND c.max IS NOT NULL GROUP BY s.skill_norm ORDER BY n DESC, skill LIMIT 20;"'

jobs-by-country:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT COALESCE(country, '\''Unknown'\'' ) AS country, COUNT(*) AS jobs FROM locations GROUP BY COALESCE(country, '\''Unknown'\'') ORDER BY jobs DESC;"'

.PHONY: trends-init trends-refresh top-risers top-fallers salary-trend country-trend

# Create/replace the new Step 5 trend MVs (pipe SQL inside container)
trends-init:
	cat infra/analytics/ANALYTICS.sql | docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -f -'

# Reuse your analytics-refresh or add this alias
trends-refresh: analytics-refresh

top-risers:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT skill, month, job_count, prev_job_count, mom_growth_pct FROM mv_skill_mom_growth WHERE mom_growth_pct IS NOT NULL ORDER BY month DESC, mom_growth_pct DESC, skill LIMIT 20;"'

top-fallers:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT skill, month, job_count, prev_job_count, mom_growth_pct FROM mv_skill_mom_growth WHERE mom_growth_pct IS NOT NULL ORDER BY month DESC, mom_growth_pct ASC, skill LIMIT 20;"'

salary-trend:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT to_char(month, '\''YYYY-MM'\'' ) AS month, skill, ROUND(avg_min) AS avg_min, ROUND(avg_max) AS avg_max, n FROM mv_monthly_salary_by_skill ORDER BY month DESC, n DESC LIMIT 50;"'

country-trend:
	docker compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT to_char(month, '\''YYYY-MM'\'' ) AS month, country, job_count FROM mv_monthly_jobs_by_country ORDER BY month DESC, job_count DESC LIMIT 50;"'


.PHONY: refresh-all app
refresh-all:
	make extract-skills
	make enrich-salary
	make enrich-locations
	make analytics-refresh
	make trends-refresh

app:
	PYTHONPATH="$(CURDIR)" streamlit run "src/app/dashboard.py"
