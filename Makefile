.PHONY: install install-web test lint run dry-run web

install:
	python -m pip install -e '.[dev]'

install-web:
	python -m pip install -e '.[dev,web]'

test:
	pytest

lint:
	ruff check .

run:
	repo-courier --config config/config.yaml

dry-run:
	repo-courier --config config/config.yaml --dry-run

web:
	repo-courier-web
