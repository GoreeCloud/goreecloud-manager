# Runtime Stability Baseline

This document records the source-level runtime stability contract for GoreeCloud Manager. It does not approve production deployment or satisfy target-environment production-readiness evidence.

## Liveness and readiness

Manager exposes two separate minimal operational endpoints:

- `GET` or `HEAD /healthz/` reports process liveness only. It intentionally does not depend on SQLite or external integrations, so an unavailable upstream service cannot make the Manager process appear dead.
- `GET` or `HEAD /readyz/` reports whether Manager-owned database state is reachable. It performs only a minimal `SELECT 1` against Django's default database and returns HTTP `503` with a sanitized body when that check fails.

Both endpoints set `Cache-Control: no-store`, require no authentication, and return no database path, exception text, integration content, credential material, or other private state.

The dedicated GoreeCloud Tasks integration health signal remains separate at `/healthz/integrations/tasks/`. Integration health must not be folded into generic Manager readiness because integrations are intentionally fail-soft and remain authoritative in their own systems.

## Bounded integration execution

Manager keeps adapter-specific timeout and staleness controls, but the administrative request boundary no longer depends on every adapter behaving perfectly.

Each Gunicorn worker owns one process-local integration executor with exactly six worker slots, matching the six currently implemented read-only integrations. Manager will not submit additional integration work when all six slots are still occupied. A request receives a typed `unavailable` fallback instead of adding work to an unbounded executor queue.

Authenticated Overview, GoreeCloud Tasks page, and Tasks integration-monitoring requests also use `MANAGER_INTEGRATION_BUDGET_SECONDS`. The default is seven seconds and deployment configuration is rejected when the value is non-positive or greater than twenty seconds. When an integration does not finish inside the Manager-level budget:

1. the user-facing or monitoring request stops waiting;
2. the unfinished future is cancelled when cancellation is still possible;
3. already-running adapter work may finish in its bounded background slot under the adapter's own timeout rules;
4. the response receives a sanitized typed fallback rather than raw exception or timeout detail;
5. Manager records only a request correlation ID, integration key, and configured budget in the warning log.

This design bounds Manager's wait time and outstanding integration concurrency without pretending Python can safely kill an arbitrary running thread.

## Request correlation and sanitized logs

Manager assigns a new server-generated 32-character hexadecimal `X-Request-ID` to each Django response. Caller-supplied request IDs are not trusted or reused. The correlation value is copied into integration containment, budget, and capacity log events so one request can be followed across Manager application logs.

Gunicorn uses a source-controlled access-log format containing only timestamp, generated response request ID, HTTP method, URL path, status, duration, and worker process ID. The format intentionally excludes query strings, the raw request line, request headers, cookies, client addresses, authenticated usernames, and other unnecessary request data.

Unexpected adapter failures continue to log only the integration key and exception class. Raw exception messages remain excluded from the top-level containment boundary because they may contain private upstream details.

## Gunicorn process guardrails

`gunicorn.conf.py` makes the application-server runtime contract explicit:

- two synchronous workers, preserving the existing worker count;
- a 30-second hard request timeout;
- a 30-second graceful worker timeout;
- 1,000-request worker recycling with up to 100 requests of jitter;
- stdout/stderr access and error logging;
- the sanitized access-log format described above.

The Manager integration budget is intentionally tighter than the Gunicorn hard timeout. Gunicorn therefore acts as the final process-level guard for requests that become wedged outside the normal integration path, while periodic worker recycling limits the lifetime of accidental process-local resource leaks.

## Compose runtime alignment

The normal Docker Compose path must use the same source-controlled Gunicorn configuration as the image default. Compose may still run the deliberate migration step before application startup, but it must start the application with:

```text
exec gunicorn -c gunicorn.conf.py goreecloud_manager.wsgi:application
```

Compose must not restate worker count, bind address, access-log destination, or other Gunicorn options that are already governed by `gunicorn.conf.py`. Duplicating those values creates a second runtime contract that can drift from the validated image configuration and can silently bypass new process-level safety settings.

A regression test reads the source-controlled Compose file and requires this configuration path while rejecting the previous direct worker/logging override.

## CI runtime baseline

The normal CI job uses an explicit Ubuntu 24.04 runner, CPython 3.14.6, and a 15-minute job timeout. The Python version matches the current application-image runtime version so ordinary source validation does not float independently from the deployed language baseline.

Node.js remains required only for syntax validation of the small browser-side theme script. Python dependency installation continues to run `python -m pip check` before application validation.

The explicit CI baseline reduces runner and language-runtime drift. It does not replace the separate future work required to make the complete Python dependency graph and container base-image identity fully immutable.

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
- mark target-environment evidence satisfied;
- approve production activation.

The production-readiness evidence manifest remains authoritative for target-environment evidence and approval state.
