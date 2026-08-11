# GoreeCloud Manager

GoreeCloud Manager is an original GoreeCloud application intended to become the central management and operational console for the GoreeCloud personal-cloud platform.

## Current Status

**v0.1 development — Milestone 3 monitoring work.** The authenticated application shell, health endpoint, Docker packaging, tests, project documentation, live read-only NetBird adapter, and read-only Healthchecks monitoring adapter are implemented. Integrations become live only when the protected runtime environment supplies their approved least-privilege credentials.

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

## Healthchecks Read-Only Integration

Manager uses Healthchecks Management API v3 `GET /checks/` with a project-specific read-only API key. The read-only API response omits write URLs, ping URLs, channel identifiers, and other sensitive management fields.

On the GoreeCloud VPS, Manager reaches the Healthchecks application container directly over the dedicated external `manager-healthchecks` Docker network. Manager does not join Healthchecks' application/database network, no new host port is published, and Caddy/NetBird publication controls remain unchanged.

Configure the protected runtime environment:

```dotenv
HEALTHCHECKS_ENABLED=true
HEALTHCHECKS_API_URL=http://healthchecks:8000/api/v3
HEALTHCHECKS_API_KEY=<project read-only API key>
HEALTHCHECKS_TIMEOUT_SECONDS=5
```

Manager displays normalized check status, last/next ping timing, schedule or period, grace, and tags. A `down` or `grace` check degrades the Healthchecks summary but does not prevent the rest of Manager from loading.

The `GoreeCloud Kopia Backup` Healthchecks check is presented as a **backup monitoring signal only**. Kopia remains authoritative for snapshot, repository, verification, retention, and restore state. Direct Kopia protection visibility is a separate adapter boundary.

## Tests

```bash
python manage.py check
python manage.py test
```

Integration tests use mocked API responses and do not require or consume live NetBird or Healthchecks credentials.

## Docker

```bash
cp .env.example .env
# Set a unique DJANGO_SECRET_KEY and any protected integration credentials required for testing.
docker compose up --build
```

The development Compose file binds Manager to loopback only. A dedicated bridge provides outbound connectivity required for read-only internet/API integrations, and the external `manager-healthchecks` network provides only the approved direct Healthchecks service path. Neither publishes the Manager backend. Production publication through GoreeCloud private DNS, NetBird, and Caddy remains deferred until production-readiness validation.

## Documentation

See:

- [`docs/project-specification.md`](docs/project-specification.md) — v0.1 implementation blueprint.
- [`docs/integrations/netbird.md`](docs/integrations/netbird.md) — NetBird adapter contract.
- [`docs/integrations/healthchecks.md`](docs/integrations/healthchecks.md) — Healthchecks adapter contract.

## License

MIT. See [`LICENSE`](LICENSE).
