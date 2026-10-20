#!/bin/sh
# Start the existing application without initializing or restoring any database.
set -eu
cd "$(dirname "$0")/.."
: "${DATABASE_URL:?Set DATABASE_URL to the intended PostgreSQL database}"
exec python -m streamlit run supermarket_app/app.py \
  --server.address 0.0.0.0 \
  --server.port "${PORT:-8501}" \
  --server.headless true \
  --browser.gatherUsageStats false
