.PHONY: up down logs load-mock psql

up:
	docker compose up -d
	docker compose ps

logs:
	docker compose logs -f db

down:
	docker compose down -v

load-mock:
	python -m src.ingestion.load_mock_jobs data/raw/mock_jobs.csv

psql:
	docker compose exec -it db psql -U $$POSTGRES_USER -d $$POSTGRES_DB
