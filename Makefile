.PHONY: help install dev test lint format clean docker-build docker-up docker-down seed

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run Celery worker
	celery -A app.ingestion.workers worker --loglevel=INFO --concurrency=2

test: ## Run tests
	pytest tests/ -v --cov=app --cov-report=html

test-quick: ## Run tests without coverage
	pytest tests/ -v

lint: ## Run linting
	flake8 app tests --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 app tests --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format: ## Format code
	black app tests
	isort app tests

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start Docker containers
	docker-compose up -d

docker-down: ## Stop Docker containers
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

seed: ## Seed knowledge base with sample data
	python scripts/seed_knowledge.py

setup-azure: ## Setup Azure resources
	bash scripts/setup_azure.sh

test-api: ## Test API endpoints
	bash scripts/test_api.sh