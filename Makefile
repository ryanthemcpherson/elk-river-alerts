.PHONY: install install-dev lint format fix test clean

# Install production dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
install-dev: install
	pip install -r requirements-dev.txt
	pre-commit install

# Run linting checks
lint:
	ruff check .
	ruff format . --check

# Format code
format:
	ruff format .

# Fix auto-fixable issues and format
fix:
	ruff check . --fix
	ruff format .

# Run tests
test:
	pytest

# Run tests with coverage
test-cov:
	pytest --cov=. --cov-report=html --cov-report=term

# Clean up cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .ruff_cache