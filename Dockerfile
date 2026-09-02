# GoreeCloud Manager application image.
FROM python:3.14.6-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6

# A full Git SHA is supplied by accepted CI/release builds. The local default keeps
# ordinary developer builds usable while making their non-release provenance explicit.
ARG MANAGER_SOURCE_REVISION=local

LABEL org.opencontainers.image.title="GoreeCloud Manager" \
      org.opencontainers.image.description="Private GoreeCloud administrative visibility and control-plane foundation." \
      org.opencontainers.image.source="https://github.com/GoreeCloud/goreecloud-manager" \
      org.opencontainers.image.revision="${MANAGER_SOURCE_REVISION}" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.vendor="GoreeCloud"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system manager && adduser --system --ingroup manager manager

COPY requirements.txt requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock

COPY . .
RUN mkdir -p /app/staticfiles /app/data /app/backups && chown -R manager:manager /app

USER manager

# Static assets are immutable application artifacts. Build them into the image so a
# production container does not require a writable application root at startup.
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput

EXPOSE 8000

# Image-level health is database-aware so container health reflects Manager-owned
# readiness rather than only the presence of a Gunicorn process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz/', timeout=3).read()" || exit 1

# Gunicorn's source-controlled configuration provides explicit worker deadlines,
# bounded worker recycling, and a sanitized access-log format without query strings.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "goreecloud_manager.wsgi:application"]
