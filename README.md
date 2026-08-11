# GoreeCloud Manager

GoreeCloud Manager is an original GoreeCloud application intended to become the central management and operational console for the GoreeCloud personal-cloud platform.

## Current Status

**v0.1 development — Milestone 3 protection and monitoring work.** The authenticated application shell, health endpoint, Docker packaging, tests, project documentation, live read-only NetBird adapter, read-only Healthchecks monitoring adapter, delegated read-only Kopia status-artifact adapter, Uptime Kuma metrics adapter, and delegated read-only Beszel resource adapter are implemented. Integrations become live only when their approved least-privilege runtime sources are configured.

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

## Uptime Kuma Read-Only Monitoring Visibility

Manager uses Uptime Kuma's protected Prometheus `/metrics` endpoint with a dedicated API key. The key is passed as the password portion of HTTP Basic authentication with an empty username; Manager does not receive the Uptime Kuma administrator password or Socket.IO management authority.

On the GoreeCloud VPS, Manager reaches Uptime Kuma directly over the dedicated external `manager-uptime` Docker network. Uptime Kuma keeps its existing private Caddy path on the separate `proxy` network and publishes no new host port.

Configure the protected runtime environment:

```dotenv
UPTIME_KUMA_ENABLED=true
UPTIME_KUMA_METRICS_URL=http://uptime-kuma:3001/metrics
UPTIME_KUMA_API_KEY=<dedicated metrics API key>
UPTIME_KUMA_TIMEOUT_SECONDS=5
```

The raw metrics payload may include target-oriented labels. Manager discards those labels and retains only approved monitor name, monitor type, normalized state, and response-time data. `down`, `pending`, or unknown monitor state degrades the Uptime Kuma summary; maintenance is shown separately.

The metrics interface does not safely expose paused-monitor inventory or per-monitor heartbeat timestamps, so Manager explicitly reports that limitation instead of reading Uptime Kuma's database or inventing values.

## Beszel Native Read-Only Resource Visibility

Manager does not receive the Beszel service-account password, PocketBase auth token, Hub data volume, Beszel Agent key/token, or Docker socket. Instead, a root-owned host-side collector authenticates with a dedicated Beszel `readonly` identity that can see only the explicitly shared `goreecloud-vps-01` system.

The collector performs the required PocketBase authentication POST, verifies the role and one-system scope, then performs only approved GET reads for current system/resource data. It writes a sanitized versioned JSON artifact containing current CPU/load, uptime, memory, swap, root-disk, selected network/temperature data, approved system details, and current container resource/state fields.

Configure Manager to read only the sanitized artifact:

```dotenv
BESZEL_ENABLED=true
BESZEL_STATUS_HOST_DIR=/srv/docker/appdata/goreecloud-manager/integrations/beszel
BESZEL_STATUS_PATH=/app/integrations/beszel/status.json
BESZEL_STATUS_MAX_AGE_SECONDS=900
BESZEL_DATA_MAX_AGE_SECONDS=1800
```

The populated collector credential stays outside Manager under protected host-side secret storage. A collector authentication/network/query failure is represented by sanitized collector state; previously sanitized data may be preserved for context while Manager marks the integration degraded. Missing or malformed artifacts fail soft without affecting `/healthz/`.

Beszel remains authoritative for historical charts, alerting, and resource-monitoring configuration. Manager's Beszel section is resource visibility only and is not a substitute for Uptime Kuma service-availability monitoring, Healthchecks scheduled-job monitoring, or Kopia protection state.

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

Integration tests use mocked API responses or fixture status artifacts and do not require or consume live NetBird, Healthchecks, Uptime Kuma, Beszel, or Kopia repository credentials.

## Docker

```bash
cp .env.example .env
# Set a unique DJANGO_SECRET_KEY and any protected integration credentials required for testing.
docker compose up --build
```

The development Compose file binds Manager to loopback only. A dedicated bridge provides outbound connectivity required for read-only internet/API integrations, the external `manager-healthchecks` network provides only the approved direct Healthchecks service path, the external `manager-uptime` network provides only the approved Uptime Kuma metrics path, and Kopia/Beszel status enters Manager only through read-only bind mounts containing sanitized status data. None of these paths publishes the Manager backend. Production publication through GoreeCloud private DNS, NetBird, and Caddy remains deferred until production-readiness validation.

## Documentation

See:

- [`docs/project-specification.md`](docs/project-specification.md) — v0.1 implementation blueprint.
- [`docs/integrations/netbird.md`](docs/integrations/netbird.md) — NetBird adapter contract.
- [`docs/integrations/healthchecks.md`](docs/integrations/healthchecks.md) — Healthchecks adapter contract.
- [`docs/integrations/uptime-kuma.md`](docs/integrations/uptime-kuma.md) — Uptime Kuma metrics adapter contract.
- [`docs/integrations/beszel.md`](docs/integrations/beszel.md) — delegated Beszel status-artifact contract.
- [`docs/integrations/kopia.md`](docs/integrations/kopia.md) — delegated Kopia status-artifact contract.

## License

MIT. See [`LICENSE`](LICENSE).
