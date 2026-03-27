#!/bin/sh

# this is for prod
# run npm run build in frontend first

cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir .
tailscale serve --bg --https=443 http:127.0.0.1:8000