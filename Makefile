.PHONY: help install dev test lint type-check generate-models docker-up docker-down clean fmt check up down logs status publish publish-repo seed

# Default target
help:
	@echo "Finance AI V3 - Available targets:"
	@echo ""
	@echo "  install          Install all dependencies (Python + Node.js)"
	@echo "  up               Start the full stack (one command: docker compose + nginx on :8080)"
	@echo "  down             Stop the full stack"
	@echo "  dev              Start development environment (Docker + API + Dashboard)"
	@echo "  test             Run all tests (pytest)"
	@echo "  lint             Run linters (ruff)"
	@echo "  fmt              Format code (ruff format)"
	@echo "  type-check       Run type checker (mypy --strict)"
	@echo "  generate-models  Generate Pydantic models from JSON schemas"
	@echo "  docker-up        Start Docker Compose services (legacy alias for 'up')"
	@echo "  docker-down      Stop Docker Compose services"
	@echo "  docker-logs      Show Docker Compose logs"
	@echo "  clean            Remove build artifacts and caches"
	@echo "  check            Run all checks (lint + type-check + test)"
	@echo "  publish          Push to an existing GitHub remote (REMOTE=github.com/USER/REPO)"
	@echo "  publish-repo     Create GitHub repo via gh + push (SLUG=owner/repo)"
	@echo "  seed             Run one-shot OHLCV seeder (after the stack is up)"
	@echo ""

# =============================================================================
# Installation
# =============================================================================

install:
	@echo "Installing Python dependencies..."
	uv sync
	@echo "Installing Node.js dependencies..."
	pnpm install
	@echo "Installation complete."

# =============================================================================
# Development
# =============================================================================

dev: docker-up
	@echo "Starting development servers..."
	@echo "API Gateway: http://localhost:8000"
	@echo "Dashboard:   http://localhost:8080"
	@echo "n8n:         http://localhost:5678"
	@echo "API Docs:    http://localhost:8000/docs"
	@echo ""
	@echo "Press Ctrl+C to stop."
	PYTHONPATH=apps/api-gateway/src uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# =============================================================================
# Testing
# =============================================================================

test:
	@echo "Running tests..."
	uv run pytest tests/ -v --cov=services --cov=apps --cov-report=term-missing --cov-fail-under=80

test-unit:
	@echo "Running unit tests..."
	uv run pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	uv run pytest tests/integration/ -v

test-e2e:
	@echo "Running e2e tests..."
	uv run playwright test

# =============================================================================
# Code Quality
# =============================================================================

lint:
	@echo "Running ruff linter..."
	uv run ruff check services/ apps/ --fix
	@echo "Checking code format..."
	uv run ruff format --check services/ apps/
	@echo "Linting dashboard..."
	pnpm --filter dashboard lint || true

fmt:
	@echo "Formatting code..."
	uv run ruff format services/ apps/
	pnpm --filter dashboard fmt || true

type-check:
	@echo "Running mypy type checker..."
	uv run mypy --strict services/ apps/
	@echo "Checking dashboard types..."
	pnpm --filter dashboard type-check || true

# =============================================================================
# Code Generation
# =============================================================================

generate-models:
	@echo "Generating Pydantic models from JSON schemas..."
	./scripts/generate_models.sh
	@echo "Model generation complete."

# =============================================================================
# Docker (one-command stack)
# =============================================================================
COMPOSE_FILE := infra/docker/docker-compose.yml
ENV_FILE     := infra/docker/.env.docker
DC           := docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)

# Legacy aliases (kept for back-compat with the original Makefile).
docker-up: up
docker-down: down
docker-logs: logs

up:
	@echo "Booting Finance AI V3 stack (one command: docker compose up + wait_for)…"
	$(DC) up -d --build
	@./scripts/wait_for.sh
	@echo ""
	@echo "Stack is up:"
	@echo "  Dashboard  http://localhost:8080"
	@echo "  API docs   http://localhost:8000/docs"
	@echo "  n8n        http://localhost:5678 (admin / $${N8N_PASSWORD:-admin_dev})"
	@echo "  Grafana    http://localhost:3001 (admin / admin)"
	@echo "  Prometheus http://localhost:9090"
	@echo "  Qdrant     http://localhost:6333/dashboard"
	@echo ""

down:
	$(DC) down

logs:
	$(DC) logs -f --tail=200

status:
	$(DC) ps

seed:
	$(DC) run --rm seed

# =============================================================================
# Database
# =============================================================================

db-migrate:
	@echo "Running database migrations..."
	uv run alembic upgrade head

db-migrate-create:
	@echo "Creating new migration..."
	@read -p "Migration name: " name; uv run alembic revision --autogenerate -m "$$name"

db-rollback:
	@echo "Rolling back last migration..."
	uv run alembic downgrade -1

# =============================================================================
# Utilities
# =============================================================================

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov/ .pytest_cache/
	@echo "Clean complete."

# =============================================================================
# CI/CD
# =============================================================================

check: lint type-check test
	@echo "All checks passed!"

# =============================================================================
# Security
# =============================================================================

security-scan:
	@echo "Running security scans..."
	uv run bandit -r services/ apps/
	uv run trufflehog filesystem .
	uv run pip-audit

# =============================================================================
# Documentation
# =============================================================================

docs:
	@echo "Generating documentation..."
	uv run pdoc3 --html --output-dir docs services/ apps/

# =============================================================================
# Publishing
# =============================================================================

# Push to an existing remote (REMOTE=github.com/USER/REPO).
publish:
	@if [ -z "$$REMOTE" ]; then \
		echo 'Set REMOTE=github.com/<user>/<repo> first, e.g. make publish REMOTE=github.com/BatuhanAcikgoz/finance-ai-v3'; \
		exit 1; \
	fi
	git remote remove origin 2>/dev/null || true
	git remote add origin $$REMOTE
	git push -u origin main

# Create the GitHub repo via gh, then push (SLUG=owner/repo).
publish-repo:
	@if [ -z "$$SLUG" ]; then echo 'set SLUG=owner/repo'; exit 1; fi
	./scripts/publish.sh $$SLUG
