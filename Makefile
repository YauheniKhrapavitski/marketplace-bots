PYTHON ?= python

.PHONY: install lint format typecheck test migrate run run-ttn docker-up docker-down docker-up-ttn

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app ttn_bot

test:
	pytest

migrate:
	alembic upgrade head

run:
	python -m app.main

run-ttn:
	python -m ttn_bot.main

docker-up:
	docker compose up --build

docker-up-ttn:
	docker compose up --build

docker-down:
	docker compose down
