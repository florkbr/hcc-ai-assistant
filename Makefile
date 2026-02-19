# Makefile for AI Assistant Service

.PHONY: install install-dev run test clean lint format help

# Install production dependencies
install:
	uv sync

# Install with development dependencies
install-dev:
	uv sync --extra dev

# Reinstall lightspeed-stack (fix broken installation)
reinstall-lightspeed:
	uv pip uninstall lightspeed-stack
	uv sync --reinstall-package lightspeed-stack

# Run the application
run:
	uv run main.py

# Run the full service stack (llama-stack + lightspeed + metrics)
services:
	uv run python start_service.py

# Run with uvicorn for development
dev:
	uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	uv run pytest

# Clean build artifacts
clean:
	rm -rf .pytest_cache
	rm -rf __pycache__
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Lint code
lint:
	uv run ruff check .
	uv run mypy .

# Format code
format:
	uv run black .
	uv run ruff check --fix .

# Show help
help:
	@echo "Available commands:"
	@echo "  install     - Install production dependencies"
	@echo "  install-dev - Install with development dependencies"
	@echo "  reinstall-lightspeed - Fix broken lightspeed-stack installation"
	@echo "  run         - Run the application"
	@echo "  services    - Run full service stack (llama-stack + lightspeed + metrics)"
	@echo "  dev         - Run with uvicorn in development mode"
	@echo "  test        - Run tests"
	@echo "  clean       - Clean build artifacts"
	@echo "  lint        - Lint code"
	@echo "  format      - Format code"
	@echo "  help        - Show this help message"