FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies (supports requirements.txt)
COPY requirements.txt* /app/
RUN if [ -f requirements.txt ]; then \
      pip install --no-cache-dir -r requirements.txt; \
    fi

# Copy source
COPY . /app

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=8000

# Gunicorn entry (uses wsgi.py)
CMD ["bash", "-lc", "gunicorn wsgi:app -b 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120"]
