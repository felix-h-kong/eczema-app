#!/bin/sh

if [ "$1" = "--prod" ]; then
  # Prod mode: build frontend, serve everything via uvicorn
  cd frontend && npm run build && cd ..
  tailscale serve --bg --https=443 http://127.0.0.1:8000
  cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir .
else
  # Dev mode: Vite dev server (hot reload) + uvicorn (auto reload)
  # Tailscale points at Vite (5173), which proxies /api to uvicorn (8000)
  tailscale serve --bg --https=443 http://127.0.0.1:5173
  cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir . &
  cd frontend && npm run dev
fi