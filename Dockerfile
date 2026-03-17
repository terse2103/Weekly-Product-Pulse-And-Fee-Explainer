# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=true

# Install system dependencies (no Nginx needed anymore)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Work directory
WORKDIR /app

# Copy packages.txt and install any system packages listed in it
COPY packages.txt .
RUN if [ -s packages.txt ]; then \
    grep -v '^#' packages.txt | xargs apt-get install -y 2>/dev/null || true; \
    fi

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Fix Windows line endings in start.sh and make it executable
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# Ensure output and data directories exist with write permissions
RUN mkdir -p output data && chmod -R 777 output data

# Start all services
CMD ["./start.sh"]
