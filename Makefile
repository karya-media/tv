.PHONY: install test lint format typecheck check

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests

format:
	ruff format src tests

typecheck:
	mypy src

check: lint typecheck test
