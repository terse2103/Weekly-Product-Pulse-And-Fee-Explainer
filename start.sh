#!/bin/bash

# Ensure PORT is set, default to 8080 if not
if [ -z "$PORT" ]; then
  export PORT=8080
fi

echo "Replacing TEMP_PORT with $PORT in nginx.conf..."
# Substitute the port in the configuration file copy
sed "s/TEMP_PORT/$PORT/g" /app/nginx.conf > /etc/nginx/nginx.conf

echo "Starting FastAPI app on 127.0.0.1:8502..."
# We run FastAPI on 127.0.0.1 so it's only accessible via Nginx reverse proxy
uvicorn api_server:api --host 127.0.0.1 --port 8502 --log-level info &

echo "Starting Streamlit app on 127.0.0.1:8501..."
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.enableCORS false \
    --server.enableXsrfProtection false &

# Remove the default site configuration to prevent port 80 conflicts
rm -f /etc/nginx/sites-enabled/default

# Verify Nginx configuration is fully valid
nginx -t

# Start Nginx in foreground to keep container running
echo "Starting Nginx on port $PORT..."
nginx -g 'daemon off;'
