.PHONY: dev dev-backend dev-frontend build backup

dev-backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

build:
	cd frontend && npm run build

test-backend:
	cd backend && python -m pytest tests/ -v

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

backup:
	mkdir -p data/backups
	sqlite3 data/eczema.db ".backup data/backups/eczema-$$(date +%Y%m%d-%H%M%S).db"
