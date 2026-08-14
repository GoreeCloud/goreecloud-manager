# syntax=docker/dockerfile:1
# GoreeCloud Manager application image.
FROM python:3.14.6-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system manager && adduser --system --ingroup manager manager

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/staticfiles /app/data /app/backups && chown -R manager:manager /app

USER manager

# Static assets are immutable application artifacts. Build them into the image so a
# production container does not require a writable application root at startup.
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput

EXPOSE 8000

# Image-level liveness is database-aware so container health reflects Manager-owned
# readiness rather than only the presence of a Gunicorn process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz/', timeout=3).read()" || exit 1

CMD ["gunicorn", "goreecloud_manager.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]
