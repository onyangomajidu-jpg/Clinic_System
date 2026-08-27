FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies needed to build psycopg2 and friends
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so this layer is cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 clinicuser \
    && chown -R clinicuser:clinicuser /app
USER clinicuser

EXPOSE 8000

# Production: collect static files, run migrations, then start gunicorn.
# Uses ${PORT:-8000} so it works on Render (which assigns $PORT) and locally
# (defaults to 8000). Shell form is required so $PORT expands at runtime.
CMD python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput && \
    gunicorn clinic_system.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120