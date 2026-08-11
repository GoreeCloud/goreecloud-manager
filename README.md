# GoreeCloud Manager

GoreeCloud Manager is an original GoreeCloud application intended to become the central management and operational console for the GoreeCloud personal-cloud platform.

## Current Status

**v0.1 development — Milestone 3 protection and monitoring work.** The authenticated application shell, health endpoint, Docker packaging, tests, project documentation, live read-only NetBird adapter, read-only Healthchecks monitoring adapter, and delegated read-only Kopia status-artifact adapter are implemented. Integrations become live only when their approved least-privilege runtime sources are configured.

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

On the GoreeCloud VPS, Manager reaches the Healthchecks application container directly over the dedicated external `manager-healthchecks` Docker network. Manager does not join Healthchecks' application/database network, no new host port is published, and Caddy/NetBird publication controls remain unchanged. The direct request presents the existing canonical `healthchecks.goreecloud.com` host and forwarded HTTPS scheme so Healthchecks' host validation remains intact.

Configure the protected runtime environment:

```dotenv
HEALTHCHECKS_ENABLED=true
HEALTHCHECKS_API_URL=http://healthchecks:8000/api/v3
HEALTHCHECKS_API_KEY=<project read-only API key>
HEALTHCHECKS_TIMEOUT_SECONDS=5
HEALTHCHECKS_CANONICAL_HOST=healthchecks.goreecloud.com
HEALTHCHECKS_FORWARDED_PROTO=https
```

Manager displays normalized check status, last/next ping timing, schedule or period, grace, and tags. A `down` or `grace` check degrades the Healthchecks summary but does not prevent the rest of Manager from loading.

The `GoreeCloud Kopia Backup` Healthchecks check is presented as a **backup monitoring signal only**. Kopia remains authoritative for snapshot, repository, verification, retention, and restore state.

## Kopia Native Read-Only Protection Visibility

Manager does not execute Kopia and does not receive the Docker socket, repository password, SFTP private key, repository configuration, or broad access to Kopia secrets. Instead, the existing root-owned backup workflow invokes the delegated `ops/kopia-status-collector.py` helper. That collector queries only the supported read-only snapshot-list output when appropriate, normalizes an approved non-secret subset, and atomically writes a small status artifact.

The Manager container receives only that sanitized directory as a read-only bind mount:

```dotenv
KOPIA_ENABLED=true
KOPIA_STATUS_HOST_DIR=/srv/docker/appdata/goreecloud-manager/integrations/kopia
KOPIA_STATUS_PATH=/app/integrations/kopia/status.json
KOPIA_STATUS_MAX_AGE_SECONDS=28800
KOPIA_SNAPSHOT_MAX_AGE_SECONDS=43200
```

The native Kopia section can show the latest backup-attempt state, repository-query state, artifact freshness, latest snapshot ID/timestamps, protected size, total files/directories, snapshot error count, and retention reasons. A skipped or failed scheduled attempt is shown separately from the last known successful snapshot.

This is deliberately separate from Healthchecks. A current heartbeat and a recent Kopia snapshot are both useful evidence, but neither proves that a restore will succeed. Restore and integrity validation remain separate recovery concerns.

## Tests

```bash
python manage.py check
python manage.py test
```

Integration tests use mocked API responses or fixture status artifacts and do not require or consume live NetBird, Healthchecks, or Kopia repository credentials.

## Docker

```bash
cp .env.example .env
# Set a unique DJANGO_SECRET_KEY and any protected integration credentials required for testing.
docker compose up --build
```

The development Compose file binds Manager to loopback only. A dedicated bridge provides outbound connectivity required for read-only internet/API integrations, the external `manager-healthchecks` network provides only the approved direct Healthchecks service path, and Kopia status enters Manager only through a read-only bind mount containing sanitized status data. None of these paths publishes the Manager backend. Production publication through GoreeCloud private DNS, NetBird, and Caddy remains deferred until production-readiness validation.

## Documentation

See:

- [`docs/project-specification.md`](docs/project-specification.md) — v0.1 implementation blueprint.
- [`docs/integrations/netbird.md`](docs/integrations/netbird.md) — NetBird adapter contract.
- [`docs/integrations/healthchecks.md`](docs/integrations/healthchecks.md) — Healthchecks adapter contract.
- [`docs/integrations/kopia.md`](docs/integrations/kopia.md) — delegated Kopia status-artifact contract.

## License

MIT. See [`LICENSE`](LICENSE).
