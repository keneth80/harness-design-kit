.PHONY: dev down logs migrate revision \
	test test-api test-web test-unit test-integration test-e2e test-e2e-smoke test-a11y \
	lint lint-api lint-web \
	format typecheck \
	install load \
	ci help \
	api-shell worker-shell

API_DIR := apps/api
WEB_DIR := apps/web

# =============================================================================
# CORE TASKS
# =============================================================================

help:
	@echo "Music Maker — Development & Testing Commands"
	@echo ""
	@echo "📦 Setup & Infrastructure"
	@echo "  make dev              Start docker-compose (API + Worker + DB + Redis)"
	@echo "  make down             Stop docker-compose"
	@echo "  make install          Install API dev dependencies"
	@echo ""
	@echo "🧪 Testing"
	@echo "  make test             Run all tests (API unit + Web unit)"
	@echo "  make test-unit        API + Web unit tests"
	@echo "  make test-api         API tests (unit + integration)"
	@echo "  make test-web         Web Vitest unit tests"
	@echo "  make test-e2e         Playwright E2E (MSW mocked)"
	@echo "  make test-e2e-smoke   Smoke tests (real API, requires RUN_SMOKE=1)"
	@echo "  make test-a11y        Accessibility tests only"
	@echo "  make load             Load tests (10 users, 5 min)"
	@echo ""
	@echo "🔍 Linting & Type Checking"
	@echo "  make lint             API + Web linting"
	@echo "  make lint-api         Ruff check on API"
	@echo "  make lint-web         ESLint on Web"
	@echo "  make typecheck        API MyPy + Web TSC"
	@echo "  make format           Auto-format API code"
	@echo ""
	@echo "🚀 CI/CD"
	@echo "  make ci               Run full CI pipeline (lint + test + build)"
	@echo ""
	@echo "💻 Utilities"
	@echo "  make logs             Tail docker-compose logs"
	@echo "  make migrate          Run Alembic migrations"
	@echo "  make api-shell        Bash into API container"
	@echo "  make worker-shell     Bash into Worker container"

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

install:
	cd $(API_DIR) && pip install -e ".[dev]"

migrate:
	cd $(API_DIR) && alembic upgrade head

revision:
	cd $(API_DIR) && alembic revision --autogenerate -m "$(m)"

# =============================================================================
# TESTING
# =============================================================================

# All tests: API + Web unit
test: test-unit

# API: unit + integration
test-api:
	cd $(API_DIR) && pytest -v

# Web: Vitest
test-web:
	cd $(WEB_DIR) && pnpm test

# Unit tests only (API + Web)
test-unit: test-unit-api test-unit-web

# API unit tests
test-unit-api:
	cd $(API_DIR) && pytest tests/unit -v --cov=app --cov-fail-under=70

# Web unit tests
test-unit-web:
	cd $(WEB_DIR) && pnpm test

# API integration tests (requires DB + Redis running)
test-integration:
	cd $(API_DIR) && pytest tests/integration -v -m integration

# E2E tests (Playwright, MSW mocked)
test-e2e:
	cd $(WEB_DIR) && pnpm test:e2e

# E2E accessibility tests
test-a11y:
	cd $(WEB_DIR) && pnpm playwright test --grep @a11y

# Smoke tests (real API, only if RUN_SMOKE=1)
test-e2e-smoke:
	cd $(WEB_DIR) && RUN_SMOKE=1 pnpm playwright test --grep @smoke

# Load tests (requires mock Mureka server)
load:
	@echo "Starting mock Mureka server..."
	cd $(API_DIR)/tests/load && python mock_mureka_server.py &
	@sleep 2
	@echo "Running load tests (10 users, 5 min)..."
	cd $(API_DIR)/tests/load && locust -f locustfile.py \
		--headless \
		--users 10 \
		--spawn-rate 2 \
		--run-time 5m \
		--host http://localhost:8000
	@killall python 2>/dev/null || true

# =============================================================================
# LINTING & TYPE CHECKING
# =============================================================================

lint: lint-api lint-web

lint-api:
	cd $(API_DIR) && ruff check .

lint-web:
	cd $(WEB_DIR) && pnpm lint

typecheck: typecheck-api typecheck-web

typecheck-api:
	cd $(API_DIR) && mypy app

typecheck-web:
	cd $(WEB_DIR) && pnpm typecheck

format:
	cd $(API_DIR) && ruff format .

# =============================================================================
# CI/CD
# =============================================================================

ci: lint typecheck test-unit build-check

build-check: build-check-api build-check-web

build-check-api:
	@echo "Building API Docker image (test only)..."
	docker build --no-cache $(API_DIR) -t music-maker-api:test

build-check-web:
	cd $(WEB_DIR) && pnpm build

# =============================================================================
# UTILITIES
# =============================================================================

api-shell:
	docker compose exec api /bin/bash

worker-shell:
	docker compose exec worker /bin/bash
