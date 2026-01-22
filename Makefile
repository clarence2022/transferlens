# TransferLens Makefile
# =====================
#
# Common commands for development and operations.
#
# Usage:
#   make up        - Start all services
#   make down      - Stop all services
#   make seed      - Load demo data
#   make predict   - Generate predictions
#   make test      - Run all tests
#
# See `make help` for all commands.

.PHONY: help up down logs restart build seed migrate predict test \
        train features signals daily clean reset shell-api shell-db \
        shell-worker lint format

# Default target
.DEFAULT_GOAL := help

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

#=============================================================================
# HELP
#=============================================================================

help: ## Show this help message
	@echo "$(CYAN)TransferLens Development Commands$(RESET)"
	@echo ""
	@echo "$(GREEN)Quick Start:$(RESET)"
	@echo "  make up      - Start all services"
	@echo "  make seed    - Load demo data"
	@echo "  make predict - Generate predictions"
	@echo ""
	@echo "$(GREEN)Available Commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-15s$(RESET) %s\n", $$1, $$2}'

#=============================================================================
# DOCKER COMPOSE
#=============================================================================

up: ## Start all services (api, web, postgres, redis)
	@echo "$(GREEN)Starting services...$(RESET)"
	docker compose up -d
	@echo "$(GREEN)Services started!$(RESET)"
	@echo "  Web: http://localhost:3000"
	@echo "  API: http://localhost:8000"
	@echo "  Docs: http://localhost:8000/docs"

up-all: ## Start all services including worker
	@echo "$(GREEN)Starting all services with worker...$(RESET)"
	docker compose --profile worker up -d
	@echo "$(GREEN)All services started!$(RESET)"

down: ## Stop all services
	@echo "$(YELLOW)Stopping services...$(RESET)"
	docker compose down
	@echo "$(GREEN)Services stopped.$(RESET)"

logs: ## View logs (use LOGS=api to filter)
	@if [ -z "$(LOGS)" ]; then \
		docker compose logs -f; \
	else \
		docker compose logs -f $(LOGS); \
	fi

restart: ## Restart all services
	@echo "$(YELLOW)Restarting services...$(RESET)"
	docker compose restart
	@echo "$(GREEN)Services restarted.$(RESET)"

build: ## Rebuild Docker images
	@echo "$(GREEN)Building images...$(RESET)"
	docker compose build --no-cache
	@echo "$(GREEN)Build complete.$(RESET)"

#=============================================================================
# DATABASE
#=============================================================================

migrate: ## Run database migrations
	@echo "$(GREEN)Running migrations...$(RESET)"
	docker compose exec api alembic upgrade head
	@echo "$(GREEN)Migrations complete.$(RESET)"

seed: ## Load demo data
	@echo "$(GREEN)Seeding demo data...$(RESET)"
	docker compose exec api python scripts/seed.py
	@echo "$(GREEN)Seeding complete.$(RESET)"

seed-worker: ## Load demo data via worker CLI
	@echo "$(GREEN)Seeding demo data via worker...$(RESET)"
	docker compose --profile worker up -d worker
	docker compose exec worker python -m worker.cli ingest:demo --force
	@echo "$(GREEN)Seeding complete.$(RESET)"

reset-db: ## Reset database (DESTRUCTIVE)
	@echo "$(YELLOW)WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker compose down -v
	docker compose up -d postgres redis
	sleep 3
	docker compose up -d api web
	$(MAKE) migrate
	@echo "$(GREEN)Database reset complete.$(RESET)"

refresh-views: ## Refresh materialized views
	@echo "$(GREEN)Refreshing materialized views...$(RESET)"
	docker compose exec postgres psql -U transferlens -d transferlens \
		-c "REFRESH MATERIALIZED VIEW player_market_view"
	@echo "$(GREEN)Views refreshed.$(RESET)"

#=============================================================================
# WORKER JOBS
#=============================================================================

predict: ## Generate predictions (runs daily pipeline)
	@echo "$(GREEN)Running prediction pipeline...$(RESET)"
	docker compose --profile worker up -d worker
	docker compose exec worker python -m worker.cli daily:run --horizon 90
	@echo "$(GREEN)Predictions generated.$(RESET)"

train: ## Train a new model
	@echo "$(GREEN)Training model...$(RESET)"
	docker compose --profile worker up -d worker
	docker compose exec worker python -m worker.cli model:train --horizon 90
	@echo "$(GREEN)Training complete.$(RESET)"

features: ## Build feature tables
	@echo "$(GREEN)Building features...$(RESET)"
	docker compose --profile worker up -d worker
	docker compose exec worker python -m worker.cli features:build
	@echo "$(GREEN)Features built.$(RESET)"

signals: ## Derive signals from user events
	@echo "$(GREEN)Deriving signals...$(RESET)"
	docker compose --profile worker up -d worker
	docker compose exec worker python -m worker.cli signals:derive --window 24h
	@echo "$(GREEN)Signals derived.$(RESET)"

daily: ## Run complete daily pipeline
	@echo "$(GREEN)Running daily pipeline...$(RESET)"
	docker compose --profile worker up -d worker
	docker compose exec worker python -m worker.cli daily:run
	@echo "$(GREEN)Daily pipeline complete.$(RESET)"

#=============================================================================
# TESTING
#=============================================================================

test: ## Run all tests
	@echo "$(GREEN)Running tests...$(RESET)"
	docker compose exec api pytest -v
	@echo "$(GREEN)Tests complete.$(RESET)"

test-api: ## Run API tests only
	@echo "$(GREEN)Running API tests...$(RESET)"
	docker compose exec api pytest apps/api/tests -v
	@echo "$(GREEN)API tests complete.$(RESET)"

test-cov: ## Run tests with coverage
	@echo "$(GREEN)Running tests with coverage...$(RESET)"
	docker compose exec api pytest --cov=app --cov-report=term-missing -v
	@echo "$(GREEN)Coverage report generated.$(RESET)"

#=============================================================================
# SHELLS
#=============================================================================

shell-api: ## Open shell in API container
	docker compose exec api bash

shell-db: ## Open PostgreSQL shell
	docker compose exec postgres psql -U transferlens -d transferlens

shell-worker: ## Open shell in worker container
	docker compose --profile worker up -d worker
	docker compose exec worker bash

shell-redis: ## Open Redis CLI
	docker compose exec redis redis-cli

#=============================================================================
# CODE QUALITY
#=============================================================================

lint: ## Run linters
	@echo "$(GREEN)Running linters...$(RESET)"
	docker compose exec api python -m flake8 app/
	@echo "$(GREEN)Linting complete.$(RESET)"

format: ## Format code
	@echo "$(GREEN)Formatting code...$(RESET)"
	docker compose exec api python -m black app/
	docker compose exec api python -m isort app/
	@echo "$(GREEN)Formatting complete.$(RESET)"

#=============================================================================
# UTILITIES
#=============================================================================

clean: ## Remove build artifacts and caches
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete.$(RESET)"

status: ## Show service status
	@echo "$(CYAN)Service Status:$(RESET)"
	@docker compose ps
	@echo ""
	@echo "$(CYAN)Health Checks:$(RESET)"
	@curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || echo "API not responding"

check: ## Run health checks
	@echo "$(GREEN)Running health checks...$(RESET)"
	@echo ""
	@echo "API Health:"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "  ❌ API not responding"
	@echo ""
	@echo "Database:"
	@docker compose exec postgres pg_isready -U transferlens || echo "  ❌ Database not ready"
	@echo ""
	@echo "Redis:"
	@docker compose exec redis redis-cli ping || echo "  ❌ Redis not responding"

#=============================================================================
# FULL SETUP
#=============================================================================

setup: ## Complete setup from scratch
	@echo "$(GREEN)Setting up TransferLens...$(RESET)"
	@echo ""
	@echo "Step 1/5: Starting services..."
	$(MAKE) up
	@sleep 5
	@echo ""
	@echo "Step 2/5: Running migrations..."
	$(MAKE) migrate
	@echo ""
	@echo "Step 3/5: Seeding demo data..."
	$(MAKE) seed
	@echo ""
	@echo "Step 4/5: Generating predictions..."
	$(MAKE) predict
	@echo ""
	@echo "Step 5/5: Running health checks..."
	$(MAKE) check
	@echo ""
	@echo "$(GREEN)Setup complete!$(RESET)"
	@echo ""
	@echo "Open http://localhost:3000 to view the application."

demo: setup ## Alias for setup
