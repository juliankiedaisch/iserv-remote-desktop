FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install psycopg2 for PostgreSQL support
RUN pip install psycopg2-binary

COPY app ./app
COPY assets ./assets
COPY scripts ./scripts
COPY run.py .
COPY scripts/entrypoint.sh .

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 5008

ENV FLASK_ENV=production
ENV FLASK_APP=run.py

# Ensure the folders exist (but let them be overwritten by volumes)
RUN mkdir -p /app/uploads /app/db
RUN mkdir -p /app/uploads/thumbnails /app/uploads/projects

ENTRYPOINT ["/app/entrypoint.sh"]