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
                         +-- NetBird
                         +-- Healthchecks
                         +-- Docker via approved delegated source
                         +-- Uptime Kuma
                         +-- Beszel
                         +-- Kopia
                         +-- ntfy
```

## Integration Boundary

Each external system remains authoritative for its own state. Manager normalizes selected information for display. The v0.1 integration contract is read-only and fail-soft: one unavailable integration must not prevent the Manager shell from loading.

## Security Boundary

The Manager container must not receive the Docker socket, host root filesystem, SSH private keys, or broad administrative tokens. Production integrations require service-specific least-privilege credentials.

## Static Assets

WhiteNoise serves collected static assets from the application process so the initial Manager container remains self-contained. Production startup runs `collectstatic` before Gunicorn. User-uploaded media is not part of the v0.1 design.
