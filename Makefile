# Makefile
# Monolith Breaker — Development Makefile
# Uses uv as package manager, all commands assume .venv is activated

.PHONY: up down dev test lint typecheck seed export drift clean

up:  ## Start Neo4j and OTel collector via Docker Compose
	docker compose up -d neo4j otel-collector

down:  ## Stop all Docker Compose services
	docker compose down

dev:  ## Start FastAPI backend + Streamlit frontend in dev mode
	@echo "Starting FastAPI on :8000 and Streamlit on :8501..."
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
	streamlit run frontend/app.py --server.port 8501

test:  ## Run pytest
	pytest

lint:  ## Run ruff linter
	ruff check backend/ frontend/

typecheck:  ## Run mypy type checker
	mypy backend/

seed:  ## Seed Neo4j with fixture monolith data
	python scripts/seed_neo4j.py

export:  ## Export Neo4j boundary graph as JSON
	python scripts/export_graph.py

drift:  ## Run drift detection scan
	python scripts/drift_cron.py

clean:  ## Remove all generated data directories
	rm -rf data/uploads data/outputs data/chroma
