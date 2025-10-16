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
