.PHONY: help up down logs test test-unit test-contract test-e2e clean

help:
	@echo "MediKiosk — available targets:"
	@echo "  make up            — docker compose up -d --build"
	@echo "  make down          — docker compose down"
	@echo "  make logs          — tail backend logs"
	@echo "  make test-unit     — pytest tests/unit"
	@echo "  make test-contract — pytest tests/contract"
	@echo "  make test-e2e      — Playwright (requires running web)"
	@echo "  make clean         — prune docker system"

up:
	cd infra/compose && docker compose up -d --build

down:
	cd infra/compose && docker compose down

logs:
	cd infra/compose && docker compose logs -f --tail=100

test-unit:
	uv run pytest tests/unit -v

test-contract:
	uv run pytest tests/contract -v

test-e2e:
	cd apps/web && pnpm exec playwright test

clean:
	docker system prune -af --volumes
