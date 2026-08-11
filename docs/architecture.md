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
                         +-- Docker via approved delegated source
                         +-- Uptime Kuma
                         +-- Beszel
                         +-- Kopia
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

The existing `GoreeCloud Kopia Backup` check is also displayed as a protection signal. This is intentionally described as Healthchecks-derived monitoring evidence, not as direct Kopia repository or snapshot verification. A future Kopia adapter must independently define how Manager can obtain read-only snapshot/repository status without receiving excessive Docker, host, SSH, or repository authority.

## Network Boundary

The Docker development deployment retains an internal application network and a separate bridge for outbound HTTPS required by integration APIs. This egress path does not publish the Manager backend. The development host binding remains loopback-only.

For the current private Healthchecks service, Compose may map `healthchecks.goreecloud.com` to the configured GoreeCloud private Caddy/NetBird address. The HTTPS hostname is retained, allowing normal TLS certificate validation while avoiding a host-wide DNS change.

Production connectivity must be validated separately and should use the approved GoreeCloud private-service path wherever practical.

## Security Boundary

The Manager container must not receive the Docker socket, host root filesystem, SSH private keys, broad administrative tokens, Healthchecks read-write keys, or Kopia repository credentials merely to provide visibility. Production integrations require service-specific least-privilege credentials or an explicitly approved delegated read-only status source.

## Static Assets

WhiteNoise serves collected static assets from the application process so the initial Manager container remains self-contained. Production startup runs `collectstatic` before Gunicorn. User-uploaded media is not part of the v0.1 design.
