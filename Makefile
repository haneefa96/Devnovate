# Munshi Project Makefile
# Common development commands

.PHONY: help dev test seed agents eval spike lint format clean

help:
	@echo "Munshi Development Commands"
	@echo "==========================="
	@echo "dev      - Start backend (:8000) and frontend (:5173) in development mode"
	@echo "test     - Run unit tests (pytest)"
	@echo "seed     - Seed demo business, customers, and mental models"
	@echo "agents   - Start Collector and Risk agents with Band room"
	@echo "eval     - Run A/B/C evaluation across seeds 1,2,3"
	@echo "spike    - Run Day 1-2 go/no-go memory test"
	@echo "lint     - Run ruff linter on backend"
	@echo "format   - Auto-format Python files with ruff"
	@echo "clean    - Remove Python and Node cache directories"

dev:
	@echo "Starting backend and frontend in development mode..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173"
	@echo "Press Ctrl+C to stop"
	@echo "Note: Make sure Hindsight is running (docker compose up hindsight)"
	@echo "      and .env is configured (cp .env.example .env && vim .env)"
	@echo ""
	@echo "Start backend in one terminal:"
	@echo "  cd backend && uv run fastapi dev main.py"
	@echo ""
	@echo "Start frontend in another terminal:"
	@echo "  cd frontend && npm run dev"

test:
	@echo "Running unit tests..."
	@cd backend && uv run pytest tests/ -v

seed:
	@echo "Seeding demo business, customers, and mental models..."
	@cd backend && uv run python -m munshi.db.seed

agents:
	@echo "Starting Collector and Risk agents with Band room..."
	@cd backend && uv run python -m munshi.band.run_agents

eval:
	@echo "Running A/B/C evaluation across seeds 1,2,3..."
	@cd backend && uv run python -m eval.run_eval

spike:
	@echo "Running Day 1-2 go/no-go memory test..."
	@cd backend && uv run python scripts/spike_one_customer.py

lint:
	@echo "Running ruff linter..."
	@cd backend && uv run ruff check .

format:
	@echo "Auto-formatting Python files with ruff..."
	@cd backend && uv run ruff format .

clean:
	@echo "Cleaning cache and temporary files..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.db" -delete 2>/dev/null || true
	@rm -rf backend/.pytest_cache
	@rm -rf frontend/node_modules
	@rm -rf frontend/dist
	@echo "Clean complete."
