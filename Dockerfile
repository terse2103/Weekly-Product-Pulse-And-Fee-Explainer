# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

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

# Expose the port Railway will assign (via $PORT env var)
EXPOSE 8080

# Start FastAPI directly via uvicorn
CMD uvicorn api_server:api --host 0.0.0.0 --port ${PORT:-8080} --log-level info
