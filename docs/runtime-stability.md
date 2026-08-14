# Runtime Stability Baseline

This document records the source-level runtime stability contract for GoreeCloud Manager. It does not approve production deployment or satisfy target-environment production-readiness evidence.

## Liveness and readiness

Manager exposes two separate minimal operational endpoints:

- `GET` or `HEAD /healthz/` reports process liveness only. It intentionally does not depend on SQLite or external integrations, so an unavailable upstream service cannot make the Manager process appear dead.
- `GET` or `HEAD /readyz/` reports whether Manager-owned database state is reachable. It performs only a minimal `SELECT 1` against Django's default database and returns HTTP `503` with a sanitized body when that check fails.

Both endpoints set `Cache-Control: no-store`, require no authentication, and return no database path, exception text, integration content, credential material, or other private state.

The dedicated GoreeCloud Tasks integration health signal remains separate at `/healthz/integrations/tasks/`. Integration health must not be folded into generic Manager readiness because integrations are intentionally fail-soft and remain authoritative in their own systems.

## Container health

The Dockerfile and Compose healthchecks use `/readyz/` instead of `/healthz/`. A running Gunicorn process is therefore not sufficient for the container to become healthy when Manager cannot query its own database.

Container startup still runs migrations before Gunicorn starts. The readiness endpoint is an additional steady-state database reachability signal rather than a replacement for migration execution.

## Deployment security check

Normal CI continues to run Django system checks and the complete test suite. CI also runs:

```text
python manage.py check --deploy --fail-level WARNING
```

The deployment check uses synthetic CI-only security settings so Django deployment warnings fail the build rather than being ignored.

The following environment-controlled settings support the approved future private HTTPS deployment without changing current loopback development behavior:

- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_SECURE_HSTS_SECONDS`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `DJANGO_SECURE_HSTS_PRELOAD`

Direct loopback development keeps HTTPS redirect and HSTS disabled. They should be enabled only after the approved private Caddy HTTPS path has been validated. The internal `/healthz/` and `/readyz/` endpoints are exempt from Django's HTTPS redirect so Docker can check the backend over loopback without requiring an internal TLS listener.

## Security and production boundary

This increment does not:

- publish Manager;
- create DNS, Caddy, NetBird, firewall, or port changes;
- create or modify production credentials or secret mounts;
- change integration permissions;
- create a production backup or monitoring resource;
- approve production activation.

The production-readiness evidence manifest remains authoritative for target-environment evidence and approval state.
