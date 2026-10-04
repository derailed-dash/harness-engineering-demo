# Makefile for Harness Engineering Demo
# Provides convenient commands for local development, linting, testing, and deployment

.PHONY: help install lint lint-fix typecheck test verify run dev deploy docker-build docker-run clean clean-workspaces

# Default shell
SHELL := /usr/bin/env bash

help: ## Show this help message
	@echo "======================================================================"
	@echo " Harness Engineering Demo - Command Reference"
	@echo "======================================================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo "======================================================================"

install: ## Install dependencies using uv into virtualenv
	uv sync

lint: ## Run complete lint suite (Codespell, Ruff, and Pyright)
	@echo "==> Running Codespell..."
	uvx codespell@latest -s
	@echo "==> Running Ruff check..."
	uvx ruff@latest check .
	@echo "==> Running Pyright type analysis..."
	uv run pyright

lint-fix: ## Automatically fix format and lint warnings
	@echo "==> Auto-fixing with Ruff..."
	uvx ruff@latest check --fix .
	@echo "==> Checking spelling..."
	uvx codespell@latest -s

typecheck: ## Run Pyright static type checker
	uv run pyright

test: ## Run independent golden test suite
	@echo "==> Running Golden Acceptance Tests..."
	uv run pytest golden_tests/ -v

verify: ## Run end-to-end pipeline verification (Unharnessed vs Harnessed)
	@echo "==> Executing Pipeline & Rubric Verification..."
	uv run python verify_demo.py

run: ## Launch the Workbench web server on port 8080
	@echo "==> Starting Harness Workbench at http://localhost:8080..."
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload --reload-dir app

dev: run ## Alias for run

deploy: ## Deploy application to Google Cloud Run
	@echo "==> Deploying to Google Cloud Run via scripts/deploy.sh..."
	./scripts/deploy.sh

docker-build: ## Build production Docker container image
	docker build -t harness-engineering-demo .

docker-run: ## Run production Docker container image locally on port 8080
	docker run -p 8080:8080 -e MODEL_NAME=gemini-3.8-flash harness-engineering-demo

clean-workspaces: ## Clean generated agent workspace code while preserving README files
	@echo "==> Cleaning generated workspaces..."
	@mkdir -p workspaces/unharnessed workspaces/harnessed
	find workspaces/unharnessed workspaces/harnessed -mindepth 1 ! -name 'README.md' -delete

clean: clean-workspaces ## Clean build, cache, and workspace artifacts
	rm -rf .pytest_cache .ruff_cache __pycache__ app/__pycache__ app/*/__pycache__ golden_tests/__pycache__
