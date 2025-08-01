FROM python:3.11-slim

ARG SUPERCRONIC_VERSION="0.2.29"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    cron \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
COPY cron/monitor.crontab /app/cron/monitor.crontab

# Install supercronic
RUN curl -fsSL -o /usr/local/bin/supercronic \
    https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64 \
    && chmod +x /usr/local/bin/supercronic

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import settings; settings.get_webhook_url()" || exit 1

# Run the application with supercronic
ENTRYPOINT ["supercronic", "-log-level", "debug", "/app/cron/monitor.crontab"]
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.server:app", "--bind", "0.0.0.0:8000"]
