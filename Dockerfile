# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# API_PORT — the FastAPI background thread listens on this port.
# Streamlit will occupy the main $PORT (set by the hosting platform).
ENV API_PORT=8081

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Work directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure output and data directories exist with write permissions
RUN mkdir -p output data && chmod -R 777 output data

# Expose both ports:
#   $PORT  — Streamlit UI (assigned by the hosting platform)
#   8081   — FastAPI REST API (background thread, used by Vercel frontend)
EXPOSE 8080
EXPOSE 8081

# Start Streamlit; the REST API server is launched automatically via
# a daemon thread inside streamlit_app.py.
CMD streamlit run streamlit_app.py \
      --server.port ${PORT:-8080} \
      --server.address 0.0.0.0 \
      --server.headless true \
      --browser.gatherUsageStats false
