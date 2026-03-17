# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=true

# Install system dependencies, including Nginx
RUN apt-get update && apt-get install -y \
    nginx \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Work directory
WORKDIR /app

# Copy packages.txt and install if it exists and contains packages
COPY packages.txt .
RUN if [ -s packages.txt ]; then \
    grep -v '^#' packages.txt | xargs apt-get install -y; \
    fi

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Setup permissions for startup script and write logs
RUN sed -i 's/\r$//' start.sh && \
    chmod +x start.sh && \
    mkdir -p /var/log/nginx && \
    chmod -R 777 /var/log/nginx && \
    mkdir -p output data && \
    chmod -R 777 output data

# Start script
CMD ["./start.sh"]
