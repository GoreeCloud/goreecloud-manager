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
                         +-- Healthchecks
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

## Network Boundary

The Docker development deployment retains an internal application network and adds a separate bridge for outbound HTTPS required by integration APIs. This egress path does not publish the Manager backend. The development host binding remains loopback-only.

Production connectivity must be validated separately and should use the approved GoreeCloud private-service path wherever practical.

## Security Boundary

The Manager container must not receive the Docker socket, host root filesystem, SSH private keys, or broad administrative tokens. Production integrations require service-specific least-privilege credentials.

## Static Assets

WhiteNoise serves collected static assets from the application process so the initial Manager container remains self-contained. Production startup runs `collectstatic` before Gunicorn. User-uploaded media is not part of the v0.1 design.
