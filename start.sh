#!/bin/bash
set -e

# Ensure PORT is set, default to 8080 if not
if [ -z "$PORT" ]; then
  export PORT=8080
fi

echo "==> Replacing TEMP_PORT with $PORT in nginx.conf..."
sed "s/TEMP_PORT/$PORT/g" /app/nginx.conf > /etc/nginx/nginx.conf

# Remove the default site configuration to prevent port 80 conflicts
rm -f /etc/nginx/sites-enabled/default

# Verify Nginx configuration is valid before starting anything
echo "==> Verifying Nginx configuration..."
nginx -t

echo "==> Starting FastAPI app on 127.0.0.1:8502..."
uvicorn api_server:api --host 127.0.0.1 --port 8502 --log-level info &
FASTAPI_PID=$!

echo "==> Starting Streamlit app on 127.0.0.1:8501..."
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.enableCORS false \
    --server.enableXsrfProtection false &
STREAMLIT_PID=$!

# Wait for Streamlit to be ready before starting Nginx (up to 60 seconds)
echo "==> Waiting for Streamlit to become ready..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8501/_stcore/health > /dev/null 2>&1; then
    echo "==> Streamlit is ready after ${i}s!"
    break
  fi
  echo "    Attempt $i/30 — Streamlit not yet ready, waiting 2s..."
  sleep 2
done

# Wait for FastAPI to be ready (up to 30 seconds)
echo "==> Waiting for FastAPI to become ready..."
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:8502/api/status > /dev/null 2>&1; then
    echo "==> FastAPI is ready after ${i}s!"
    break
  fi
  echo "    Attempt $i/15 — FastAPI not yet ready, waiting 2s..."
  sleep 2
done

# Start Nginx in the foreground — this keeps the container alive
echo "==> Starting Nginx on port $PORT..."
nginx -g 'daemon off;'
