.PHONY: dev dev-backend dev-frontend build cap-sync cap-open cap-build cap-install backup

dev-backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev -- --host 0.0.0.0

dev:
	$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

build:
	cd frontend && npm run build

test-backend:
	cd backend && python -m pytest tests/ -v

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

cap-sync:
	cd frontend && npm run build && npx cap sync android

cap-open:
	cd frontend && npx cap open android

cap-build: cap-sync
	cd frontend/android && ANDROID_HOME=$$HOME/Android/Sdk ./gradlew assembleDebug
	cp frontend/android/app/build/outputs/apk/debug/app-debug.apk app-debug.apk
	@echo "APK ready: app-debug.apk"

cap-install: cap-build
	tailscale file cp app-debug.apk pixel-8:
	@echo "Sent to Pixel 8 via Tailscale"

backup:
	mkdir -p data/backups
	sqlite3 data/eczema.db ".backup data/backups/eczema-$$(date +%Y%m%d-%H%M%S).db"
