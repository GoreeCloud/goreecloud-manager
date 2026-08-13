# GoreeCloud Manager

GoreeCloud Manager is an original GoreeCloud application intended to become the central management and operational console for the GoreeCloud personal-cloud platform.

## Current Status

**v0.1 development — read-only integration and production-readiness work.** The authenticated Django application shell, minimal health endpoint, Docker packaging, CI, Glaze UI foundation, live read-only NetBird adapter, read-only Healthchecks monitoring adapter, Uptime Kuma metrics adapter, delegated read-only Kopia status-artifact adapter, delegated read-only Beszel resource adapter, and GoreeCloud Tasks read-only API adapter are implemented.

Beszel Milestone 3D has completed its development/live-validation gate, including the delegated credential boundary, live resource data, fail-soft behavior, timer operation, minimal health endpoint, and authenticated loopback/SSH-tunnel UI review. This does **not** approve production publication. GoreeCloud Tasks has passed disposable cross-application and final-topology validation, and Manager now provides a data-minimized Tasks integration-specific monitoring signal. The actual production Tasks identity, credential, network, private publication, external monitor registration/alert delivery, and activation remain separate approval-controlled work.

Docker inventory visibility and ntfy remain planned Manager integrations.

## Principles

- Private by default.
- Read-only integrations first.
- Least privilege.
- No reusable secrets in source control.
- No direct public backend exposure.
- No Docker socket mounted into the Manager container.
- Specialized services remain authoritative for their own operations.
- GoreeCloud Tasks remains authoritative for task content and task authorization.
- Backup and recovery are required before production dependency.
- Glaze UI must improve usability without obscuring operational state or weakening accessibility.

## Technology Stack

- Python 3.14
- Django 5.2 LTS
- Server-rendered Django templates
- Plain CSS and minimal vanilla JavaScript
- SQLite for development / initial MVP
- Gunicorn
- WhiteNoise for containerized static-file serving
- Docker / Docker Compose
- GitHub Actions

## Glaze UI

Manager uses the GoreeCloud Glaze UI design language for its shared application shell and operational surfaces. The implementation includes reusable design tokens, layered surfaces, semantic status colors, responsive navigation, visible keyboard focus, a skip link, reduced-motion and reduced-transparency behavior, and System/Light/Dark appearance modes.

The explicit appearance preference is stored only in browser `localStorage` under `goreecloud-manager-theme`. Returning to System removes the stored override. No theme choice is written to the Manager database or sent to an integration.

No external font, analytics package, telemetry SDK, or third-party browser script is required by the Glaze UI implementation.

See [`docs/glaze-ui.md`](docs/glaze-ui.md) for the repository-local UI, privacy, and accessibility contract.

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

The metrics interface does not safely expose paused-monitor inventory or per-monitor heartbeat timestamps, so Manager reports that limitation instead of reading Uptime Kuma's database or inventing values.

## Beszel Native Read-Only Resource Visibility

Manager does not receive the Beszel service-account password, PocketBase auth token, Hub data volume, Beszel Agent key/token, or Docker socket. Instead, a root-owned host-side collector authenticates with a dedicated Beszel `readonly` identity scoped to the approved system.

The collector performs the required PocketBase authentication POST, verifies the role and system scope, then performs only approved GET reads for current resource data. It writes a sanitized versioned JSON artifact containing approved CPU/load, uptime, memory, swap, root-disk, network/temperature, system-detail, and current container resource/state fields.

Configure Manager to read only the sanitized artifact:

```dotenv
BESZEL_ENABLED=true
BESZEL_STATUS_HOST_DIR=/srv/docker/appdata/goreecloud-manager/integrations/beszel
BESZEL_STATUS_PATH=/app/integrations/beszel/status.json
BESZEL_STATUS_MAX_AGE_SECONDS=900
BESZEL_DATA_MAX_AGE_SECONDS=1800
```

The populated collector credential stays outside Manager under protected host-side secret storage. Collector authentication/network/query failures are represented by sanitized collector state; previously sanitized data may be preserved for context while Manager marks the integration degraded. Missing or malformed artifacts fail soft without affecting `/healthz/`.

Beszel remains authoritative for historical charts, alerting, and resource-monitoring configuration. Manager's Beszel section is resource visibility only and is not a substitute for Uptime Kuma service availability, Healthchecks scheduled-job monitoring, or Kopia protection state.

## Kopia Native Read-Only Protection Visibility

Manager does not execute Kopia and does not receive the Docker socket, repository password, SFTP private key, repository configuration, or broad access to Kopia secrets. Instead, the existing root-owned backup workflow invokes the delegated `ops/kopia-status-collector.py` helper. The collector normalizes an approved non-secret subset and atomically writes a small status artifact.

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

## GoreeCloud Tasks Read-Only Integration

Manager consumes the dedicated GoreeCloud Tasks Manager API and never reads the Tasks database directly. Tasks maps the bearer token to one existing active Tasks identity and applies normal task-visibility authorization before returning active project-scoped work marked as GoreeCloud operational work.

Configure Manager with the Tasks application base URL and exactly one token source:

```dotenv
TASKS_ENABLED=true
TASKS_API_URL=https://tasks.goreecloud.com
TASKS_ACCESS_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
TASKS_TIMEOUT_SECONDS=5
```

For an isolated development environment only, `TASKS_ACCESS_TOKEN` may be used in the uncommitted `.env` instead of the file setting.

Manager appends `/api/v1/manager/operational-tasks/`, authenticates with Bearer authorization, validates the `goreecloud.tasks.manager.v1` response contract, and normalizes only approved operational fields. The authenticated `/tasks/` page displays the resulting read-only task summary and task details.

The intended Tasks principal is a dedicated non-interactive integration account with Viewer membership only in projects explicitly approved for Manager visibility. Manager cannot choose another Tasks identity through the API. Membership revocation is therefore the task-visibility revocation mechanism. The integration does not expose personal Inbox tasks, ordinary non-operational tasks, descriptions, comments, labels, reminder state, account details, or task mutation operations.

Manager also exposes a dedicated sanitized integration signal at `GET /healthz/integrations/tasks/`. The endpoint exercises the real adapter but returns only Manager service identity, the GoreeCloud Tasks integration label, the broad adapter state, and a fine-grained monitoring condition. It returns HTTP 200 only when the integration condition is `healthy`; disabled, misconfigured, unreachable, authentication-rejected, authorization-denied, endpoint-unavailable, upstream-error, and schema-invalid conditions return HTTP 503. The response is uncached and contains no task data, task counts, configured Tasks username, token value, secret path, raw upstream response, or adapter detail string. Manager's generic `/healthz/` remains independent.

Disposable cross-application and final-topology CI validate the application contract, authorization/data minimization, file-backed synthetic credential pattern, database isolation, membership revocation/restoration, invalid credentials, fail-soft behavior, and secret/log minimization. The final-topology gate is the production-pattern compatibility location for the new monitoring signal. These tests do not provision or authorize a real production integration identity, token, network, private publication path, external monitor, alert route, or activation.

See [`docs/tasks-integration.md`](docs/tasks-integration.md) for the complete security and production boundary.

## Tests and Validation

```bash
python -m pip check
node --check core/static/core/js/theme.js
python manage.py collectstatic --noinput
python manage.py check
python manage.py test
```

Integration tests use mocked API responses, disposable application environments, or fixture status artifacts and do not require or consume live production credentials.

Material interface changes should additionally receive authenticated browser review at supported desktop and mobile widths in both light and dark appearance modes before release promotion.

## Docker

```bash
cp .env.example .env
# Set a unique DJANGO_SECRET_KEY and any protected integration credentials required for testing.
docker compose up --build
```

The development Compose file binds Manager to loopback only. A dedicated bridge provides outbound connectivity required for approved read-only API integrations. The external `manager-healthchecks` network provides only the approved Healthchecks service path, the external `manager-uptime` network provides only the approved Uptime Kuma metrics path, and Kopia/Beszel status enters Manager only through read-only bind mounts containing sanitized status data. None of these paths publishes the Manager backend.

Production publication, external Tasks integration monitor registration/alert delivery, and the real production Tasks integration path remain deferred until their production-readiness requirements are separately satisfied.

## Documentation

See:

- [`docs/project-specification.md`](docs/project-specification.md) — current v0.1 implementation blueprint and milestone state.
- [`docs/glaze-ui.md`](docs/glaze-ui.md) — Manager Glaze UI, appearance, privacy, and accessibility contract.
- [`docs/integrations/netbird.md`](docs/integrations/netbird.md) — NetBird adapter contract.
- [`docs/integrations/healthchecks.md`](docs/integrations/healthchecks.md) — Healthchecks adapter contract.
- [`docs/integrations/uptime-kuma.md`](docs/integrations/uptime-kuma.md) — Uptime Kuma metrics adapter contract.
- [`docs/integrations/beszel.md`](docs/integrations/beszel.md) — delegated Beszel status-artifact contract.
- [`docs/integrations/kopia.md`](docs/integrations/kopia.md) — delegated Kopia status-artifact contract.
- [`docs/tasks-integration.md`](docs/tasks-integration.md) — GoreeCloud Tasks API, authorization, and monitoring boundary.
- [`docs/tasks-production-readiness-validation.md`](docs/tasks-production-readiness-validation.md) — Manager-side Tasks production-readiness evidence plan.

## License

MIT. See [`LICENSE`](LICENSE).
