#!/bin/bash

# Ensure PORT is set, default to 8080 if not
if [ -z "$PORT" ]; then
  export PORT=8080
fi

echo "==> Starting Streamlit admin panel on port 8501 (internal)..."
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.enableCORS false \
    --server.enableXsrfProtection false &

echo "==> Starting FastAPI on port $PORT (Railway public port)..."
# FastAPI binds directly to Railway's PORT — no Nginx needed
exec uvicorn api_server:api --host 0.0.0.0 --port "$PORT" --log-level info
