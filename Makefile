.PHONY: install test lint run dry-run

install:
	python -m pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check .

run:
	repo-courier --config config/config.yaml

dry-run:
	repo-courier --config config/config.yaml --dry-run
