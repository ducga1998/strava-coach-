.PHONY: up down migrate backend frontend test build

up:
	docker compose up -d

down:
	docker compose down

migrate:
	cd backend && alembic upgrade head

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest tests/ -v

build:
	cd frontend && npm run build
