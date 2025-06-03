.PHONY: help install test format lint docs clean

help:  ## Show available commands
	@echo "Essential MeasureIt development commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install with development dependencies
	uv pip install -e ".[dev,docs,jupyter]"
	pre-commit install

test:  ## Run tests with coverage
	pytest --cov=src/MeasureIt --cov-report=html --cov-report=term-missing

format:  ## Format and lint code
	ruff format src/ tests/
	ruff check --fix src/ tests/

lint:  ## Check code quality (format + lint + type check)
	ruff format --check src/ tests/
	ruff check src/ tests/
	mypy src/

docs:  ## Build documentation
	cd docs/source && make html

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete 