#!/bin/bash
set -e

if [ -z "$PORT" ]; then
  export PORT=8080
fi

echo "==> Replacing TEMP_PORT with $PORT in nginx.conf..."
sed "s/TEMP_PORT/$PORT/g" /app/nginx.conf > /etc/nginx/nginx.conf

rm -f /etc/nginx/sites-enabled/default

echo "==> Verifying Nginx configuration..."
nginx -t

echo "==> Starting FastAPI app on 127.0.0.1:8502..."
# Bind on 127.0.0.1 so it's only accessible via Nginx proxy setup
uvicorn api_server:api --host 127.0.0.1 --port 8502 --log-level info &

echo "==> Starting Streamlit admin on 127.0.0.1:8501..."
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.enableCORS false \
    --server.enableXsrfProtection false &

# Simple readiness poll checking Streamlit / FastAPI before Nginx forwards traffic 
echo "==> Waiting for Streamlit..."
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:8501/_stcore/health > /dev/null 2>&1; then
    echo "==> Streamlit ready after ${i}s!"
    break
  fi
  sleep 2
done

echo "==> Starting Nginx on port $PORT..."
exec nginx -g 'daemon off;'
