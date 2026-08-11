# GoreeCloud Manager

GoreeCloud Manager is an original GoreeCloud application intended to become the central management and operational console for the GoreeCloud personal-cloud platform.

## Current Status

**v0.1 development — Milestone 2 implementation.** The authenticated application shell, integration registry, health endpoint, Docker packaging, tests, project documentation, and first read-only NetBird adapter are implemented. NetBird becomes live only when the protected runtime environment supplies the approved service-user token.

## Principles

- Private by default.
- Read-only integrations first.
- Least privilege.
- No reusable secrets in source control.
- No direct public backend exposure.
- No Docker socket mounted into the Manager container.
- Specialized services remain authoritative for their own operations.
- Backup and recovery are required before production dependency.

## Initial Stack

- Python 3.14
- Django 5.2 LTS
- Server-rendered Django templates
- SQLite for development / initial MVP
- Gunicorn
- WhiteNoise for containerized static-file serving
- Docker / Docker Compose
- GitHub Actions

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Replace DJANGO_SECRET_KEY in .env with a unique development value.
set -a
. ./.env
set +a
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with the administrator account you created.

## NetBird Read-Only Integration

Manager uses NetBird's documented `GET /api/peers` endpoint. The adapter performs no write-capable API operation.

Configure the protected runtime environment:

```dotenv
NETBIRD_ENABLED=true
NETBIRD_API_URL=https://netbird.goreecloud.com/api
NETBIRD_API_TOKEN=<read-only service-user token>
NETBIRD_TIMEOUT_SECONDS=5
```

The intended credential is a NetBird service-user personal access token with read-only/Auditor authority. Never commit the populated token, place it in screenshots, or store it in ordinary documentation. When the API is disabled, misconfigured, unreachable, rejects authentication, or returns malformed data, Manager degrades to a sanitized status instead of failing the Overview page.

## Tests

```bash
python manage.py check
python manage.py test
```

The NetBird adapter tests use mocked responses and do not require or consume a live token.

## Docker

```bash
cp .env.example .env
# Set a unique DJANGO_SECRET_KEY and, when testing NetBird, the protected API token.
docker compose up --build
```

The development Compose file binds Manager to loopback only. A dedicated bridge provides outbound connectivity required for read-only integration API calls; it does not publish the Manager backend. Production publication through GoreeCloud private DNS, NetBird, and Caddy remains deferred until production-readiness validation.

## Documentation

See [`docs/project-specification.md`](docs/project-specification.md) for the v0.1 implementation blueprint and [`docs/integrations/netbird.md`](docs/integrations/netbird.md) for the NetBird adapter contract.

## License

MIT. See [`LICENSE`](LICENSE).
