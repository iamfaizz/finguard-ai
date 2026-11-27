.PHONY: up down build logs ps test

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose up -d --build

logs:
	docker compose logs -f

ps:
	docker compose ps

test:
	docker compose run --rm -v "$(CURDIR)/data:/app/data:ro" backend python -m pytest data/tests tests