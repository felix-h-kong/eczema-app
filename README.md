# Eczema Trigger Tracker

A self-hosted PWA for logging food, skin checks, and medications, then statistically correlating ingredients with eczema flares over time. Accessed via Tailscale VPN from an Android phone.

## Tech Stack

- **Frontend:** React + TypeScript, Vite, Service Workers, Web Push
- **Backend:** Python, FastAPI, SQLite, Claude API (ingredient parsing & analysis)
- **Infra:** Tailscale VPN with `tailscale serve` for HTTPS

## Setup

```bash
# Install dependencies
cd backend && pip install -r requirements.txt
cd frontend && npm install

# Copy and configure environment
cp backend/.env.example backend/.env  # Add your Anthropic API key and VAPID keys
```

## Running

**Development:**
```bash
make dev          # Runs backend + frontend concurrently
```

**Production:**
```bash
cd frontend && npm run build   # Build static files into backend/static/
./run.sh                       # Starts uvicorn + tailscale serve (HTTPS on 443)
```

**Other:**
```bash
make test         # Run tests
make backup       # SQLite backup to data/backups/
```

## Troubleshooting

**HTTPS not working / ERR_SSL_PROTOCOL_ERROR:**
- Verify `tailscale serve` is active: `tailscale serve status`
- If not, run: `tailscale serve --bg --https=443 http://127.0.0.1:8000`
- Make sure your phone is on the Tailscale VPN and using the correct hostname (check `tailscale status`)

**PWA won't load / shows blank screen after install:**
- The service worker may have cached a stale response. Uninstall the app from your phone and re-add it from the browser.
- In Chrome, you can also clear site data: tap the lock icon in the address bar > Site settings > Clear & reset.

**Backend shows "invalid http request":**
- Something is sending HTTPS/TLS traffic directly to uvicorn (port 8000), which only speaks HTTP. Make sure you're accessing the app through `tailscale serve` on port 443, not hitting port 8000 directly with HTTPS.
