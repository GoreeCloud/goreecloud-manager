# Architecture

GoreeCloud Manager begins as a small Django monolith. This is an intentional complexity boundary, not a permanent architecture commitment.

```text
Authorized administrator
        |
   Private HTTPS
        |
      Caddy          (production path, not enabled by this scaffold)
        |
GoreeCloud Manager
  |      |      |
  |      |      +-- Django authentication / sessions
  |      +--------- Server-rendered UI
  +---------------- Read-only integration adapters
                         |
                         +-- NetBird REST API (implemented)
                         +-- Healthchecks Management API (implemented)
                         +-- Kopia delegated status artifact (implemented)
                         +-- Docker via approved delegated source
                         +-- Uptime Kuma
                         +-- Beszel
                         +-- ntfy
```

## Integration Boundary

Each external system remains authoritative for its own state. Manager normalizes selected information for display. The v0.1 integration contract is read-only and fail-soft: one unavailable integration must not prevent the Manager shell from loading.

### NetBird Adapter

The first live adapter uses NetBird's documented `GET /api/peers` endpoint. Manager sends a service-user personal access token in the `Authorization: Token ...` request header and normalizes only the peer fields required by the administrative Overview: peer identifier, name, DNS label, NetBird IPv4/IPv6 addresses, connection state, last-seen timestamp, operating-system description, and NetBird version.

The adapter does not implement POST, PUT, PATCH, or DELETE operations. NetBird remains authoritative for peers, groups, policies, routes, setup keys, users, DNS settings, and all other private-network configuration.

API failures are converted into a small sanitized state (`disabled`, `misconfigured`, `healthy`, or `unavailable`). Raw upstream bodies and authentication headers are not rendered.

### Healthchecks Adapter

The monitoring adapter uses the documented Healthchecks Management API v3 checks-list endpoint. Manager authenticates with a project-specific read-only API key in the `X-Api-Key` header and normalizes only fields needed to understand scheduled-job health.

The Healthchecks adapter does not implement write-capable management operations. A `down` or `grace` check changes the Manager summary to `degraded` while preserving availability of the rest of the application.

The existing `GoreeCloud Kopia Backup` check is displayed as a monitoring/protection signal. It is intentionally described as Healthchecks-derived evidence, not as direct Kopia repository or snapshot verification.

### Kopia Status-Artifact Adapter

Native Kopia visibility uses a delegated file boundary rather than direct repository or Docker access.

The existing root-owned Kopia backup workflow runs `ops/kopia-status-collector.py` on the host. After successful snapshot creation the collector invokes the existing pinned Kopia Compose service only for a read-only `snapshot list /source --json --max-results=1` query. It normalizes a strict non-secret subset and atomically writes a versioned JSON artifact under the Manager integration-data directory.

On skipped or failed scheduled attempts the collector updates the attempt state while preserving the last known successful snapshot from the previous artifact. This lets the Manager distinguish an unavailable backup target from the absence of any known successful snapshot.

Manager receives only the sanitized artifact directory through a read-only bind mount. Manager does not execute Kopia and does not receive:

- the Docker socket
- Kopia repository configuration or password
- SFTP private keys or known-hosts material
- the Kopia stack or secrets directory
- snapshot create/delete/retention/maintenance/restore authority

The adapter treats missing, malformed, unsupported, or stale artifacts as fail-soft integration states. A valid artifact may be `degraded` if the latest scheduled attempt was skipped/failed/unknown, the latest snapshot is too old, the snapshot reports errors, or a repository refresh failed.

Healthchecks and native Kopia visibility remain separate signals. Restore readiness remains a third, independent recovery assurance boundary.

## Network and Data Boundaries

The Docker development deployment retains an internal application network and a separate bridge for outbound HTTPS required by API integrations. This egress path does not publish the Manager backend. The development host binding remains loopback-only.

Healthchecks is reached directly over the dedicated external `manager-healthchecks` Docker network. Manager does not join Healthchecks' application/database network, and the Healthchecks database does not join the Manager service network. The direct request preserves the canonical `healthchecks.goreecloud.com` host and forwarded HTTPS scheme so application host validation remains intact without weakening Caddy's private access policy.

Kopia uses no Manager network path. The only Kopia-to-Manager data path is the sanitized host-side status artifact mounted read-only into the Manager container.

Production connectivity and publication must be validated separately and should use the approved GoreeCloud private-service model wherever practical.

## Security Boundary

The Manager container must not receive the Docker socket, host root filesystem, SSH private keys, broad administrative tokens, Healthchecks read-write keys, or Kopia repository credentials merely to provide visibility. Production integrations require service-specific least-privilege credentials or an explicitly approved delegated read-only status source.

The Kopia artifact is deliberately non-secret and contains only approved operational metadata. Raw Kopia command stderr/stdout, repository endpoints, usernames, secret paths, root object IDs, and repository configuration are excluded.

## Static Assets

WhiteNoise serves collected static assets from the application process so the initial Manager container remains self-contained. Production startup runs `collectstatic` before Gunicorn. User-uploaded media is not part of the v0.1 design.
